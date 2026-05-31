"""Small helpers for Tk windows that contain RGBA Pillow images."""
from __future__ import annotations

import ctypes
import os
import tkinter as tk
from ctypes.util import find_library
from functools import lru_cache
from typing import Tuple

from PIL import Image


# A chroma-key color that should not appear in Dolores' pastel artwork.
TRANSPARENT_KEY = "#00ff00"

_SHAPE_BOUNDING = 0
_SHAPE_SET = 0


def apply_transparent_background(
    win: tk.Misc,
    fallback_bg: str,
    fallback_alpha: float | None = None,
) -> Tuple[str, bool]:
    """Return the background color to use and whether chroma transparency worked.

    Native Windows Tk supports ``-transparentcolor`` and can hide every pixel that
    matches ``TRANSPARENT_KEY``. Some Linux/X11 Tk builds do not expose that
    attribute, so callers keep the old soft background as a fallback.
    """
    try:
        win.configure(bg=TRANSPARENT_KEY)
        win.attributes("-transparentcolor", TRANSPARENT_KEY)  # type: ignore[attr-defined]
        return TRANSPARENT_KEY, True
    except tk.TclError:
        win.configure(bg=fallback_bg)
        if fallback_alpha is not None:
            try:
                win.attributes("-alpha", fallback_alpha)  # type: ignore[attr-defined]
            except tk.TclError:
                pass
        return fallback_bg, False


def prepare_chroma_key_image(
    img: Image.Image,
    transparent_threshold: int = 8,
    faint_edge_threshold: int = 64,
    edge_radius: int = 2,
) -> Image.Image:
    """Remove green-key color bleed from semi-transparent outside edges.

    When Tk uses ``-transparentcolor``, semi-transparent anti-aliased pixels can
    blend against ``TRANSPARENT_KEY`` before the window manager removes the key
    color. Only edge pixels next to transparent background are adjusted; internal
    semi-transparent details such as blush/highlights keep their original alpha.
    """
    rgba = img.convert("RGBA")
    w, h = rgba.size
    src = rgba.tobytes()
    out = bytearray(src)
    alpha = src[3::4]
    changed = False

    for y in range(h):
        for x in range(w):
            pos = y * w + x
            a = alpha[pos]
            if a == 0 or a == 255:
                continue

            touches_transparent = False
            for ny in range(max(0, y - edge_radius), min(h, y + edge_radius + 1)):
                row = ny * w
                for nx in range(max(0, x - edge_radius), min(w, x + edge_radius + 1)):
                    if nx == x and ny == y:
                        continue
                    if alpha[row + nx] <= transparent_threshold:
                        touches_transparent = True
                        break
                if touches_transparent:
                    break

            if not touches_transparent:
                continue

            out[pos * 4 + 3] = 0 if a < faint_edge_threshold else 255
            changed = True

    if not changed:
        return rgba
    return Image.frombytes("RGBA", rgba.size, bytes(out))


@lru_cache(maxsize=1)
def _xshape_libs():
    x11_path = find_library("X11")
    xext_path = find_library("Xext")
    if not x11_path or not xext_path:
        return None

    x11 = ctypes.CDLL(x11_path)
    xext = ctypes.CDLL(xext_path)

    x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
    x11.XOpenDisplay.restype = ctypes.c_void_p
    x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
    x11.XCloseDisplay.restype = ctypes.c_int
    x11.XCreateBitmapFromData.argtypes = [
        ctypes.c_void_p,
        ctypes.c_ulong,
        ctypes.c_char_p,
        ctypes.c_uint,
        ctypes.c_uint,
    ]
    x11.XCreateBitmapFromData.restype = ctypes.c_ulong
    x11.XFreePixmap.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
    x11.XFreePixmap.restype = ctypes.c_int
    x11.XFlush.argtypes = [ctypes.c_void_p]
    x11.XFlush.restype = ctypes.c_int

    xext.XShapeCombineMask.argtypes = [
        ctypes.c_void_p,
        ctypes.c_ulong,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_ulong,
        ctypes.c_int,
    ]
    xext.XShapeCombineMask.restype = None
    return x11, xext


def _alpha_mask_bytes(img: Image.Image, threshold: int) -> bytes:
    alpha = img.convert("RGBA").getchannel("A")
    w, h = alpha.size
    raw = alpha.tobytes()
    stride = (w + 7) // 8
    mask = bytearray(stride * h)

    for y in range(h):
        row = y * w
        out = y * stride
        for x in range(w):
            if raw[row + x] >= threshold:
                mask[out + (x // 8)] |= 1 << (x % 8)
    return bytes(mask)


def apply_alpha_shape(win: tk.Misc, img: Image.Image, threshold: int = 8) -> bool:
    """Crop an X11 toplevel window to the non-transparent pixels of ``img``.

    This is the fallback for Linux/X11 Tk builds that do not support
    ``-transparentcolor``. It uses the X Shape extension through ctypes, so it
    needs no extra Python dependency.
    """
    if os.name != "posix" or not os.environ.get("DISPLAY"):
        return False
    libs = _xshape_libs()
    if libs is None:
        return False

    try:
        win.update_idletasks()
        xid = int(win.winfo_id())
    except tk.TclError:
        return False

    x11, xext = libs
    display = x11.XOpenDisplay(None)
    if not display:
        return False

    pixmap = 0
    try:
        w, h = img.size
        mask = _alpha_mask_bytes(img, threshold)
        buf = ctypes.create_string_buffer(mask)
        pixmap = x11.XCreateBitmapFromData(
            display, ctypes.c_ulong(xid), ctypes.cast(buf, ctypes.c_char_p), w, h
        )
        if not pixmap:
            return False

        xext.XShapeCombineMask(
            display,
            ctypes.c_ulong(xid),
            _SHAPE_BOUNDING,
            0,
            0,
            ctypes.c_ulong(pixmap),
            _SHAPE_SET,
        )
        x11.XFlush(display)
        try:
            win.attributes("-alpha", 1.0)  # type: ignore[attr-defined]
        except tk.TclError:
            pass
        return True
    except Exception:  # noqa: BLE001
        return False
    finally:
        if pixmap:
            x11.XFreePixmap(display, pixmap)
        x11.XCloseDisplay(display)
