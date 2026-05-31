---
name: tkinter-cjk-pillow-rendering
description: Render Chinese/emoji/kaomoji in tkinter when Tk lacks Xft (WSL conda) by drawing text to images with Pillow. Use when a tkinter app shows CJK as tofu boxes (□), when font families returns only ('fixed',), or when building cross-platform desktop UIs that must display non-ASCII text reliably.
keywords: [tkinter, Tk, Xft, CJK, Chinese, emoji, kaomoji, Pillow, PIL, ImageTk, tofu, fixed font, WSL, fontconfig]
---

# Rendering CJK / emoji in tkinter via Pillow

## The problem

Some Tk builds — notably the **conda `tk` in WSL/Linux** — are **not linked against
Xft/fontconfig**. Symptoms:

- `tkinter.font.families()` returns only `('fixed',)`.
- All Chinese / emoji / kaomoji render as tofu boxes `□`.
- Copying fonts into `~/.local/share/fonts` + `fc-cache` does **nothing**, because Tk
  never reads fontconfig.

Diagnose definitively:

```bash
python -c "import tkinter,tkinter.font as f; r=tkinter.Tk(); print(f.families())"   # -> ('fixed',)  == broken
ldd <conda_env>/lib/libtk8.6.so | grep -i xft   # no output == no Xft == cannot show CJK
```

Native Windows Tk and most distro Tk packages DO have Xft and render CJK fine — but the
Pillow approach below works **identically on every platform**, so prefer it for portability.

## The solution: draw text to RGBA images with Pillow, show as PhotoImage

Render every piece of user-visible text (labels, bubbles, input previews) to a
`PIL.Image` using a TTF directly, then display via `ImageTk.PhotoImage` on a
`tk.Label`/`tk.Canvas`. This bypasses Tk's font system entirely.

```python
from PIL import Image, ImageDraw, ImageFont, ImageTk

font = ImageFont.truetype("/path/to/msyh.ttc", 18)   # load TTF by absolute path
img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
ImageDraw.Draw(img).multiline_text((0, 0), "你好朵拉", font=font, fill=(60,45,75,255))
photo = ImageTk.PhotoImage(img)            # KEEP a reference or it gets GC'd and vanishes
label.configure(image=photo)
```

**Gotcha:** Tk discards images with no Python reference. Store `self._photo = photo`.

## Cross-platform font discovery

Pick TTF paths by platform; on WSL you can read the Windows fonts at `/mnt/c`.

```python
import os
def cjk_candidates():
    if os.name == "nt":
        d = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "Fonts")
        return [os.path.join(d, n) for n in ("msyh.ttc","msyhl.ttc","simhei.ttf","simsun.ttc")]
    return ["/mnt/c/Windows/Fonts/msyh.ttc",                       # WSL can read Windows fonts
            os.path.expanduser("~/.local/share/fonts/msyh.ttc"),
            "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]     # last-resort, no CJK but won't crash
# emoji: C:\Windows\Fonts\seguiemj.ttf  (PIL needs embedded_color=True for color emoji)
```

## Tofu (□) prevention — sanitize against the .notdef glyph

A font reports a bbox even for missing glyphs (the `.notdef` box), so `getbbox()` alone
can't detect tofu. Compare each char's bitmap to the font's `.notdef` bitmap (probe a
Private-Use codepoint that's guaranteed absent). Strip non-renderable chars from any
untrusted text (e.g. LLM output that emits emoji a CJK font lacks):

```python
def make_sanitizer(font_path, size=24):
    f = ImageFont.truetype(font_path, size)
    notdef = bytes(f.getmask("", mode="1"))   # PUA char -> .notdef bitmap
    def ok(ch):
        if ord(ch) < 0x80 or ch.isspace(): return True
        m = f.getmask(ch, mode="1")
        if m.getbbox() is None: return True          # blank glyph (e.g. full-width space)
        return bytes(m) != notdef
    return lambda s: "".join(c for c in s if ok(c))
```

## Kaomoji that actually render in Microsoft YaHei

YaHei (msyh.ttc) has these; it LACKS `◕ ‿ ᴗ ✧ ♡ ∀ ◔`. Safe building blocks:
`ω ▽ ・ ﾟ д ￣ ≧ ≦ ° 〇 ヾ ノ づ ☆ ^ _`. Verified-safe set:
`(・ω・)  (*￣▽￣*)  ヾ(≧▽≦)ノ  (´-ω-)  (；・ω・)  (°〇°)!  (￣o￣)zzZ`

## Transparency caveat

Under X11/WSL, Tk does **not** support `-transparentcolor` (only `-alpha` whole-window).
Per-pixel transparency isn't available there; design borderless windows as soft rounded
cards with `-alpha` instead. Native Windows supports color-key transparency if needed.

> Reference implementation: `dolores/ui/text_renderer.py` (font discovery + `sanitize`),
> `dolores/ui/bubble.py` (rounded-card bubbles), `dolores/ui/chat_input.py`
> (hidden Entry captures real Unicode even when display is tofu; Pillow renders a preview).
