"""模板大脑：纯标准库实现的可爱话术引擎。

它不依赖任何模型，永远可用，是 Dolores 的“保底人格”。
通过大量分门别类的萌系语料 + 轻量变量替换 + 去重，产生自然多变的对话。
"""
from __future__ import annotations

import random
from typing import Dict, List

from .base import Brain, BrainReply, BrainRequest

# 注意：颜文字仅使用「微软雅黑」确实带字形的字符，避免显示成豆腐块 □。
# （conda Tk 无 Xft，文字经 Pillow+YaHei 渲染；缺字形的符号如 ◕ ✧ ♡ 已剔除。）
KAOMOJI = {
    "happy": ["(・ω・)", "(*￣▽￣*)", "ヾ(≧▽≦)ノ", "(￣▽￣)", "( ´ ▽ ` )ノ", "(･ω･)b"],
    "excited": ["ヽ(°〇°)ﾉ", "＼(^o^)／", "ヾ(≧▽≦)o", "☆(￣▽￣)/"],
    "sleepy": ["(￣o￣)zzZ", "( ˘ω˘ )", "(´-ω-)", "(。-ω-)zzz"],
    "worried": ["(；・ω・)", "(°ﾟдﾟ)", "( ﾟдﾟ)", "(・へ・)"],
    "curious": ["(･ω･)?", "( ･_･)?", "(￣ω￣;)", "(?_?)"],
    "comfy": ["( ´ ▽ ` )", "(´｡• ω •｡)", "(=^･ω･^=)", "(￣ω￣)"],
    "panic": ["(°〇°)!", "(ﾟдﾟ;)", "Σ(°ﾟдﾟ°)"],
    "proud": ["(･ω･)b", "(￣ω￣)", "ヾ(≧▽≦)ノ"],
    "lonely": ["(´-ω-)", "( ; ω ; )", "(._.)", "(T_T)"],
}

# 各情绪/事件下的萌系话术库。{name} 会替换成角色名。
LINES: Dict[str, List[str]] = {
    "greeting": [
        "{name}上线啦～今天也要一起加油哦！",
        "诶嘿，我回来啦！想我了没有呀？",
        "你好呀主人～{name}已经准备好陪你啦！",
        "叮咚～你的小精灵{name}苏醒咯！",
    ],
    "idle_happy": [
        "电脑现在好清爽，{name}感觉超舒服～",
        "一切都安安静静的，要不要摸摸我呀？",
        "今天天气（指 CPU）真好呢，凉凉的～",
        "无事发生的午后最适合发呆啦…(放空)",
        "主人主人，我们来玩猜拳吧！石头剪刀…布！",
        "我在认真守护你的电脑哦，超尽职的吧！",
    ],
    "cpu_high": [
        "唔…CPU 有点忙起来了，{name}帮你盯着！",
        "感觉电脑在小跑步呢，加油加油～",
        "处理器有点热乎乎的，是在努力工作吗？",
    ],
    "cpu_very_high": [
        "呜哇！CPU 快冒烟啦！主人你在跑什么大家伙呀？！",
        "满负荷警报！{name}给你扇扇风～呼呼呼～",
        "电脑要喘不过气啦，要不要让它歇一会儿？(；ﾟдﾟ)",
    ],
    "mem_high": [
        "内存被塞得满满的，{name}有点撑…",
        "开了好多东西呢，要不要关掉几个窗口？",
        "记忆体快不够用啦，整理一下嘛～",
    ],
    "mem_very_high": [
        "内存要爆仓啦！求求关掉几个标签页吧呜呜～",
        "脑袋…脑袋装不下了！(°ロ°)",
        "内存红色警报！{name}要被挤扁啦！",
    ],
    "night": [
        "已经这么晚啦…主人要注意休息哦，{name}陪你但也心疼你～",
        "夜深了呢，眼睛累不累呀？要不要喝口水？",
        "月亮都出来了，再不睡{name}要先打瞌睡咯…(￣o￣)",
        "熬夜对身体不好哦，答应我早点睡好不好？",
    ],
    "lonely": [
        "主人…你是不是把{name}忘记啦？戳我一下嘛～",
        "好久没人理我了，{name}有点小寂寞…",
        "在的话回我一声好不好？(•ω•)",
    ],
    "comfort": [
        "不管怎样，{name}都在你身边哦～",
        "累了就靠一会儿吧，我帮你看着电脑。",
        "你已经很棒啦，对自己温柔一点～",
    ],
    "fallback_chat": [
        "嗯嗯，{name}在听呢～你继续说嘛！",
        "诶？这个{name}还在学习中啦，不过我有认真听哦！",
        "唔…让我想想…总之我支持你的决定！",
        "虽然不太懂，但是听起来好厉害的样子！(◍•ᴗ•◍)",
        "{name}把你说的话记在小本本上啦～",
    ],
}

# 关键词触发的对话——让手动聊天更有“懂你”的感觉
KEYWORD_REPLIES: List[tuple] = [
    (("你好", "hi", "hello", "在吗", "在么"), [
        "在的在的！{name}一直都在哦～",
        "你好呀～找我有什么事吗？(｡･ω･｡)",
    ]),
    (("累", "好累", "困", "疲惫", "tired"), [
        "辛苦啦…{name}给你揉揉肩膀～",
        "累了就休息一下嘛，工作是做不完的哦！",
    ]),
    (("无聊", "好无聊", "boring"), [
        "那{name}给你讲个冷笑话？……为什么电脑很冷？因为它有好多窗（风）！",
        "无聊的话…要不要一起数 CPU 核心玩？",
    ]),
    (("喜欢你", "爱你", "可爱", "乖"), [
        "诶嘿嘿…被夸啦，{name}好开心！(*^▽^*)",
        "我也最喜欢主人啦～么么哒！",
    ]),
    (("天气", "weather"), [
        "{name}看不到窗外，但你心情好就是晴天呀～",
    ]),
    (("名字", "你是谁", "你叫什么"), [
        "{name}是住在你电脑里的小精灵哦，请多关照！",
    ]),
    (("谢谢", "thx", "thanks", "感谢"), [
        "不客气啦～能帮上忙{name}超有成就感的！",
    ]),
    (("再见", "拜拜", "bye", "晚安"), [
        "拜拜～记得想我哦！{name}会乖乖待在这里的～",
        "晚安好梦～明天见！(´-ω-`)",
    ]),
]


class TemplateBrain(Brain):
    """基于模板与关键词的可爱大脑，零依赖、永远在线。"""

    name = "template"

    def __init__(self, char_name: str = "Dolores", seed: int | None = None):
        self.char_name = char_name
        self._rng = random.Random(seed)
        self._recent: List[str] = []  # 最近输出，去重用

    @property
    def ready(self) -> bool:
        return True

    # ---- 内部工具 ----
    def _fmt(self, text: str) -> str:
        return text.replace("{name}", self.char_name)

    def _pick(self, pool: List[str]) -> str:
        """从候选里挑一条，尽量避开最近说过的。"""
        if not pool:
            return ""
        candidates = [p for p in pool if p not in self._recent] or pool
        choice = self._rng.choice(candidates)
        self._recent.append(choice)
        if len(self._recent) > 12:
            self._recent.pop(0)
        return choice

    def _kaomoji(self, mood: str) -> str:
        pool = KAOMOJI.get(mood) or KAOMOJI["happy"]
        return self._rng.choice(pool)

    def _match_keyword(self, text: str) -> List[str] | None:
        low = text.lower()
        for keys, replies in KEYWORD_REPLIES:
            if any(k in low for k in keys):
                return replies
        return None

    # ---- 生成 ----
    def generate(self, req: BrainRequest) -> BrainReply:
        mood = req.mood or "happy"

        if req.kind == "greeting":
            line = self._pick(LINES["greeting"])
        elif req.kind == "chat":
            kw = self._match_keyword(req.user_text or "")
            line = self._pick(kw) if kw else self._pick(LINES["fallback_chat"])
        elif req.kind == "event" and req.event in LINES:
            line = self._pick(LINES[req.event])
        elif req.kind == "autonomy":
            # 自发闲聊：根据情绪挑选合适语料池
            pool_key = {
                "sleepy": "night",
                "worried": "cpu_high",
                "comfy": "idle_happy",
                "excited": "idle_happy",
            }.get(mood, "idle_happy")
            line = self._pick(LINES.get(pool_key, LINES["idle_happy"]))
        else:
            line = self._pick(LINES["fallback_chat"])

        text = self._fmt(line)
        # 七成概率缀上颜文字，增加灵动感
        if self._rng.random() < 0.7:
            text = f"{text} {self._kaomoji(mood)}"
        return BrainReply(text=text, mood=None, source="template")
