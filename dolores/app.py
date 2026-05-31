"""应用编排：把 感知 → 人设 → 自主 → 大脑 → UI 串起来。

线程模型（关键）：
- 主线程：tkinter 事件循环 + UI（tkinter 要求 UI 全在主线程）。
- 后台线程 BrainWorker：执行可能较慢的大脑推理（尤其 LLM），通过队列收发，避免卡界面。
- 心跳：用 root.after() 周期性采样系统状态、跑自主引擎、把生成意图投给 BrainWorker，
  并轮询回复队列、更新立绘与气泡。
"""
from __future__ import annotations

import logging
import queue
import threading
import time
import tkinter as tk
from dataclasses import dataclass
from typing import List, Optional

from .autonomy import AutonomyEngine, Intent
from .brain import BrainRequest, create_brain
from .brain.factory import HybridBrain
from .config import Config, load_config
from .personality import Personality, PetState
from .sensors import SystemState, create_sensor
from .ui import text_renderer as _tr  # 触发字体探测（也用于 sanitize）
from .ui.pet_window import PetWindow

logger = logging.getLogger("dolores.app")


@dataclass
class _Job:
    """投给大脑工作线程的任务。"""

    req: BrainRequest
    seq: int


@dataclass
class _Result:
    text: str
    mood: Optional[str]
    source: str
    seq: int


class BrainWorker(threading.Thread):
    """后台大脑线程：从 in_q 取任务，生成后放入 out_q。"""

    def __init__(self, brain: HybridBrain):
        super().__init__(daemon=True, name="BrainWorker")
        self.brain = brain
        self.in_q: "queue.Queue[Optional[_Job]]" = queue.Queue()
        self.out_q: "queue.Queue[_Result]" = queue.Queue()
        self._stop = threading.Event()

    def submit(self, job: _Job) -> None:
        self.in_q.put(job)

    def run(self) -> None:
        # 先在后台尝试加载模型（不阻塞 UI 启动）
        try:
            self.brain.warmup()
        except Exception as exc:  # noqa: BLE001
            logger.warning("brain warmup error: %s", exc)

        while not self._stop.is_set():
            try:
                job = self.in_q.get(timeout=0.2)
            except queue.Empty:
                continue
            if job is None:
                break
            try:
                reply = self.brain.generate(job.req)
                text = _tr.sanitize(reply.text) or reply.text
                self.out_q.put(_Result(text=text, mood=reply.mood,
                                       source=reply.source, seq=job.seq))
            except Exception as exc:  # noqa: BLE001
                logger.warning("brain generate error: %s", exc)
                self.out_q.put(_Result(text="（朵拉走神了一下…）", mood=None,
                                       source="error", seq=job.seq))

    def stop(self) -> None:
        self._stop.set()
        self.in_q.put(None)


class DoloresApp:
    """桌面宠物主应用。"""

    def __init__(self, cfg: Optional[Config] = None):
        self.cfg = cfg or load_config()
        self._setup_logging()

        self.root = tk.Tk()
        self.root.title("Dolores")

        # 核心组件
        night = self.cfg.get("behavior.quiet_hours", {}) or {}
        self.sensor = create_sensor(
            night_start=night.get("start", 1), night_end=night.get("end", 6)
        )
        self.personality = Personality(self.cfg)
        self.autonomy = AutonomyEngine(self.cfg, self.personality)
        self.pet_state = PetState()

        self.brain: HybridBrain = create_brain(self.cfg)
        self.worker = BrainWorker(self.brain)

        # UI
        self.ui = PetWindow(self.root, self.cfg)
        self.ui.on_request_chat = self.ui.open_chat
        self.ui.on_poke = self._on_poke
        self.ui.on_quit = self.shutdown
        self.ui.set_chat_handler(self._on_user_message)

        # 对话历史（喂给 LLM）
        self.history: List[dict] = []
        self._seq = 0
        self._pending_seq = -1          # 正在等待的请求序号，避免叠加
        self._last_state: Optional[SystemState] = None

        self.sensor_interval = int(self.cfg.get("behavior.sensor_interval_ms", 2000))
        self._running = True

    # ---- 基础 ----
    def _setup_logging(self) -> None:
        level = getattr(logging, str(self.cfg.get("logging.level", "INFO")).upper(), logging.INFO)
        handlers: List[logging.Handler] = [logging.StreamHandler()]
        if self.cfg.get("logging.to_file", False):
            handlers.append(logging.FileHandler(
                self.cfg.abspath(self.cfg.get("logging.file", "dolores.log")),
                encoding="utf-8"))
        logging.basicConfig(
            level=level,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            handlers=handlers,
        )

    def _next_seq(self) -> int:
        self._seq += 1
        return self._seq

    # ---- 交互回调 ----
    def _on_poke(self) -> None:
        self.pet_state.note_interaction()
        # 戳一下就高兴一下，蹦跶一下，并自发说句话
        self.ui.set_mood("excited")
        self.ui.trigger_action("bounce")
        self._dispatch(BrainRequest(
            kind="event", event="poked", mood="excited",
            system_summary=self._summary(),
        ), poke=True)

    def _on_user_message(self, text: str) -> None:
        self.pet_state.note_interaction()
        self.history.append({"role": "user", "content": text})
        self.history = self.history[-12:]
        mood = self.personality.derive_mood(
            self._last_state or self.sensor.read(), self.pet_state)
        self._dispatch(BrainRequest(
            kind="chat", user_text=text, mood=mood,
            system_summary=self._summary(), history=list(self.history),
        ), force=True)

    # ---- 大脑调度 ----
    def _summary(self) -> str:
        return self._last_state.summary() if self._last_state else ""

    def _dispatch(self, req: BrainRequest, force: bool = False, poke: bool = False) -> None:
        """把请求投给后台大脑。force=True 时即使有在途请求也提交（用户输入优先）。"""
        if not force and self._pending_seq >= 0:
            return  # 已有自发请求在途，不叠加
        seq = self._next_seq()
        self._pending_seq = seq
        self.worker.submit(_Job(req=req, seq=seq))

    # ---- 心跳 ----
    def _heartbeat(self) -> None:
        if not self._running:
            return
        # 1) 采样
        state = self.sensor.read()
        self._last_state = state

        # 2) 情绪跟随系统状态（气泡不在显示时才平滑切换）
        mood = self.personality.derive_mood(state, self.pet_state)
        self.ui.set_mood(mood)

        # 3) 自主决策
        if self._pending_seq < 0:  # 没有在途请求时才考虑自发
            intent: Optional[Intent] = self.autonomy.tick(state, self.pet_state)
            if intent is not None:
                # 问候时挥手，兴奋时蹦跶——让自主行为更有“身体语言”
                if intent.kind == "greeting":
                    self.ui.trigger_action("wave")
                elif intent.mood == "excited":
                    self.ui.trigger_action("bounce")
                self._dispatch(BrainRequest(
                    kind=intent.kind, mood=intent.mood, event=intent.event,
                    system_summary=state.summary(), history=list(self.history),
                ))

        # 4) 取回大脑结果
        self._drain_results()

        self.root.after(self.sensor_interval, self._heartbeat)

    def _drain_results(self) -> None:
        try:
            while True:
                res: _Result = self.worker.out_q.get_nowait()
                # 只接受最新在途请求的结果
                if res.seq != self._pending_seq:
                    continue
                self._pending_seq = -1
                if res.mood:
                    self.ui.set_mood(res.mood)
                if res.text.strip():
                    self.ui.say(res.text)
                    self.history.append({"role": "assistant", "content": res.text})
                    self.history = self.history[-12:]
        except queue.Empty:
            pass

    # ---- 生命周期 ----
    def run(self) -> None:
        self.worker.start()
        logger.info("Dolores 启动；大脑：%s", self.brain.status)
        self.root.after(300, self._heartbeat)
        self.root.protocol("WM_DELETE_WINDOW", self.shutdown)
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            self.shutdown()

    def shutdown(self) -> None:
        if not self._running:
            return
        self._running = False
        logger.info("Dolores 关闭中…")
        try:
            self.ui.stop()
        except Exception:
            pass
        try:
            self.worker.stop()
        except Exception:
            pass
        try:
            self.brain.close()
        except Exception:
            pass
        try:
            self.root.after(100, self.root.destroy)
        except Exception:
            pass


def main() -> None:
    app = DoloresApp()
    app.run()
