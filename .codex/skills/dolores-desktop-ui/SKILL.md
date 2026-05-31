---
name: dolores-desktop-ui
description: Project-specific guidance for DOLORES desktop pet UI work. Use when modifying Dolores' tkinter/Pillow windows, sprite rendering, speech bubbles, chat input, window transparency/cropping, or UI smoke tests in the DOLORES repository.
---

# Dolores Desktop UI

Use this together with `desktop-pet-architecture` for broad architecture and
`tkinter-cjk-pillow-rendering` for text rendering issues. This skill captures
DOLORES-specific UI files and pitfalls.

## Map

- Main window: `dolores/ui/pet_window.py`
- Speech bubble: `dolores/ui/bubble.py`
- Manual chat input: `dolores/ui/chat_input.py`
- Sprite animator/vector fallback: `dolores/ui/sprite.py`
- Image-pack loading: `dolores/ui/sprite_loader.py`
- CJK/emoji text rendering: `dolores/ui/text_renderer.py`
- Transparency helpers: `dolores/ui/transparency.py`
- Default sprite assets: `assets/sprites/default/`
- Sprite generation: `scripts/generate_sprites.py`
- GUI smoke test: `scripts/gui_smoketest.py`

## Transparency

Tk does not consistently support per-pixel transparent RGBA windows:

- Native Windows Tk can support `-transparentcolor`.
- The WSL/X11 conda Tk used by this project may only support `-alpha`.
- Avoid relying on `ImageTk.PhotoImage` alpha alone; transparent pixels can show
  as a rectangular Label/Canvas background.

Use `dolores/ui/transparency.py` for windows that display RGBA Pillow images:

- Call `apply_transparent_background(...)` during `Tk`/`Toplevel` setup.
- Set Label/Canvas `bg` to the returned background color.
- When chroma-key transparency is available, pass images through
  `prepare_chroma_key_image(img)` before creating `ImageTk.PhotoImage`.
  Otherwise semi-transparent anti-aliased edges can blend against the bright
  green transparent key and appear as a green outline around the character,
  bubble, or input.
- `prepare_chroma_key_image(...)` should only adjust semi-transparent pixels
  near fully transparent outside areas: drop very faint outer pixels, make
  stronger outer edge pixels opaque, and preserve internal semi-transparent
  details such as blush and highlights.
- If chroma-key transparency is unavailable, call `apply_alpha_shape(win, img)`
  after geometry/image updates to crop the X11 top-level window to the image's
  alpha mask.
- For animated sprites, cache the alpha signature and avoid reapplying the X11
  shape when the silhouette has not changed.

Do not paint fake white or pastel backgrounds around sprites to hide alpha
problems. It creates visible rectangular boxes around the character, speech
bubble, or chat input.

## Sprite Assets

Default frames are RGBA PNGs named `<action>_<NN>.png` under
`assets/sprites/default/`, with action metadata in `manifest.json`.

Before changing window code, verify whether an artifact is:

- A bad sprite asset: inspect `Image.open(path).convert("RGBA").getchannel("A")`.
- A fitting/anchor issue: inspect `SpritePack._fit(...)`.
- A Tk window background issue: inspect `pet_window.py`, `bubble.py`,
  `chat_input.py`, and `transparency.py`.

## Text Cropping

Speech bubbles and chat input previews render text through
`dolores/ui/text_renderer.py`. If Chinese text looks vertically shifted or the
bottom is clipped, check Pillow's `multiline_textbbox()` offsets before changing
outer card padding. Some fonts such as Microsoft YaHei report a positive
`top`; `render_text()` must draw at `(padding_left - bbox[0],
padding_top - bbox[1])` so the real ink bbox starts inside the RGBA image.

## Validation

Use the project conda environment when available:

```bash
/home/dayrker/anaconda3/envs/torch2.10/bin/python -m compileall dolores
```

For transparency-specific changes, run a minimal Tk/X11 probe:

```bash
/home/dayrker/anaconda3/envs/torch2.10/bin/python - <<'PY'
import tkinter as tk
from PIL import Image, ImageDraw
from dolores.ui.transparency import apply_alpha_shape

root = tk.Tk()
root.overrideredirect(True)
root.geometry("80x80+20+20")
img = Image.new("RGBA", (80, 80), (0, 0, 0, 0))
ImageDraw.Draw(img).ellipse((10, 10, 70, 70), fill=(255, 0, 0, 255))
root.update_idletasks()
print("xshape", apply_alpha_shape(root, img))
root.destroy()
PY
```

For chroma-key edge changes, run a pixel check against a default sprite:

```bash
/home/dayrker/anaconda3/envs/torch2.10/bin/python - <<'PY'
from PIL import Image
from dolores.ui.transparency import prepare_chroma_key_image

src = Image.open("assets/sprites/default/idle_00.png").convert("RGBA")
out = prepare_chroma_key_image(src)
sa = src.getchannel("A").tobytes()
oa = out.getchannel("A").tobytes()
changed = sum(1 for a, b in zip(sa, oa) if a != b)
kept = sum(1 for a, b in zip(sa, oa) if 0 < a < 255 and a == b)
print("edge_changed", changed, "internal_partial_kept", kept)
PY
```

Run `scripts/gui_smoketest.py` only when a display server is available. Treat
model-loading shutdown errors separately from UI rendering failures.

## Config

`config.json` may be written by Windows tools with a UTF-8 BOM. Keep config
loading tolerant by using `encoding="utf-8-sig"` in `dolores/config.py`.
