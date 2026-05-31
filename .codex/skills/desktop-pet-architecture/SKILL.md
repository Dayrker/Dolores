---
name: desktop-pet-architecture
description: Architecture for an autonomous, animated desktop pet/companion — sensor->personality->autonomy->brain->UI with a tkinter main thread and background inference, mood state machine, event debounce/cooldown, and a swappable image/vector sprite animation system. Use when building a desktop pet, an ambient agent that reacts to system state, or any always-on character UI that speaks on its own.
keywords: [desktop pet, mascot, autonomy, personality, mood state machine, event cooldown, debounce, sprite animation, animator, manifest, image pack, vector fallback, tkinter threading, heartbeat, borderless window, bubble, idle behavior]
---

# Desktop-pet / ambient-agent architecture

A pet that *seems* alive needs three things working together: it **senses** state, has a
**mood**, and decides **on its own when to act**. Keep these as separate, pure-logic layers
feeding a thin UI.

```
sensors → personality(mood + events) → autonomy(when to speak) → brain(what to say) → UI
```

## Layering (each layer is testable in isolation)

- **sensors** — produce a plain `SystemState` snapshot (see
  `cross-platform-system-metrics`). No IO elsewhere.
- **personality** — pure functions:
  - `derive_mood(state, pet) -> mood` (happy/comfy/excited/worried/panic/sleepy/lonely…).
  - `detect_events(state, pet) -> [Event]` with **debounce + cooldown** so the pet isn't a
    chatterbox. A high-severity event suppresses its lesser sibling (firing `cpu_very_high`
    also arms the cooldown for `cpu_high`).
- **autonomy** — `tick(state, pet) -> Intent | None` each heartbeat. Priority:
  **greeting > urgent event > randomized idle chat** (interval `uniform(min,max)`).
  Quiet-hours lower idle-chat probability but still allow urgent events. It decides
  *whether/what-kind*, never the words.
- **brain** — turns an `Intent` into text (see `pluggable-local-llm-backend`).
- **UI** — renders mood→sprite and shows speech bubbles.

```python
def tick(self, state, pet):
    if not self._greeted: self._greeted = True; return Intent("greeting", mood)
    ev = personality.top_event(state, pet)
    if ev and (not quiet_hours or ev.priority >= 50): return Intent("event", ev.mood, ev.key)
    if now >= self._next_chat_ts:
        self._next_chat_ts = now + uniform(lo, hi)
        return Intent("autonomy", derive_mood(state, pet))
    return None
```

## Threading: tkinter on the main thread, inference on a worker

tkinter requires **all UI on the main thread**. LLM inference is slow → push it to a
`BrainWorker` thread with `in_q`/`out_q` queues. Drive everything from a `root.after()`
**heartbeat**: sample sensors → update mood/sprite → (if idle) compute Intent → enqueue →
drain results → bubble. Tag each request with a **sequence number** and accept only the
latest in-flight result; let user input **preempt** autonomous requests.

## Sprite animation: swappable image packs with a vector fallback

An `Animator` unifies two frame sources so the window doesn't care which is active:

- **Image pack**: `assets/sprites/<pack>/<action>_<NN>.png` + `manifest.json`
  (`actions: {name:{frames,loop,fps}}`, `mood_map: {mood:action}`, `anchor`).
  Loader returns `None` on missing/corrupt → triggers fallback (never crash).
- **Vector fallback**: draw the character programmatically with Pillow (no art assets
  needed). Ship this so the app always renders.
- Animator advances frames by each action's own fps vs. the ~60 ms tick; **one-shot**
  actions (wave/bounce) play once then return to `idle`; **looping** actions follow mood.
- Wire body language to interactions: poke → `bounce`, greeting → `wave`,
  excited mood → `bounce`.

```python
def next_frame(self):
    if self.pack:
        self._accum += TICK_MS
        if self._accum >= 1000/fps:
            self._accum = 0; self._idx += 1
            if self._idx >= n: self._idx = 0; (oneshot and self._return_to_idle())
        return self.pack.frame(self._action, self._idx, size) or self._vector_frame()
    return self._vector_frame()   # programmatic Pillow draw + bob
```

Pre-render the default pack with a build script (squash-and-stretch bounce, blink, a swung
arm for wave, vector "zzZ" for sleep, shake for panic) so a fresh clone has art without
running anything; commit only the default pack, gitignore user packs.

## UI specifics

- Borderless (`overrideredirect(True)`), `-topmost`, draggable. Under X11/WSL only
  `-alpha` works (no per-pixel transparency) → soft rounded card look.
- Render all text (bubbles, input) via Pillow — see `tkinter-cjk-pillow-rendering`.
- Manual chat: a hidden `Entry` captures real Unicode even when its display is tofu;
  render a live Pillow preview of what's typed.

## Config-drives-everything

Dotted-path config with deep-merged defaults so a missing/garbled file still boots:
`model.backend`, `ui.sprite.{mode,pack}`, `behavior.{autonomy_*_interval_s,
idle_lonely_after_s, thresholds, quiet_hours}`.

> Reference: `dolores/{app,personality,autonomy,sensors}.py`,
> `dolores/ui/{sprite,sprite_loader,pet_window,bubble,chat_input}.py`,
> `scripts/generate_sprites.py`.
