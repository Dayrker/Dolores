"""GUI 冒烟测试：启动完整 App，几秒后截图并自动退出。"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dolores.app import DoloresApp


def main():
    app = DoloresApp()

    # 启动后依次：显示问候、切到 panic 弹气泡、打开输入框、截图、退出
    def scene1():
        app.ui.set_mood("happy")
        app.ui.say("你好呀主人～朵拉上线啦！这是一段用来测试气泡换行的稍微长一点的话哦 (≧▽≦)")

    def scene2():
        app.ui.set_mood("panic")
        app.ui.say("呜哇！CPU 快冒烟啦！(°〇°)!")

    def shot():
        try:
            import subprocess
            # WSLg 下用 grim 或 import 可能不可用；尝试用 PIL ImageGrab 不行，改用 root 截图
            app.root.update()
            # 用 Tk 自带方式抓主窗范围的屏幕（依赖 X），失败则跳过
            os.system("command -v grim >/dev/null 2>&1 && grim /tmp/dolores_shot.png 2>/dev/null || "
                      "(command -v import >/dev/null 2>&1 && import -window root /tmp/dolores_shot.png 2>/dev/null) || true")
            print("screenshot attempted -> /tmp/dolores_shot.png")
        except Exception as e:
            print("shot err", e)

    app.root.after(1500, scene1)
    app.root.after(3500, scene2)
    app.root.after(4000, lambda: app.ui.open_chat())
    app.root.after(5000, shot)
    app.root.after(6500, app.shutdown)

    app.run()
    print("app exited cleanly")


if __name__ == "__main__":
    main()
