import sys, os
sys.path.insert(0, r"D:\Linux\Dolores")
import dolores.app  # noqa
from dolores.sensors import create_sensor
from dolores.ui import text_renderer as tr
from dolores.ui import sprite as sp
import time

print("python:", sys.version.split()[0], "| platform os.name =", os.name)
s = create_sensor()
print("sensor impl:", type(s).__name__)
time.sleep(0.4)
st = s.read()
print("sensor read:", st.summary(), "| available =", st.available)
print("CJK font:", tr.CJK_FONT_PATH)
print("EMOJI font:", tr.EMOJI_FONT_PATH)
img = tr.render_text("原生Windows测试 朵拉 (・ω・)b", size=18, max_width=300)
print("text render:", img.size, "bbox", img.getbbox())
# sprite pack
from dolores.config import load_config
a = sp.make_animator(load_config())
print("sprite pack:", a.pack.name if a.pack else "vector-fallback")
print("NATIVE-WINDOWS-CHECK-OK")
