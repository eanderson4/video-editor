# video-editor

Shared video-pipeline library (`vidkit`) for MATH vs VIBES and related shows:
episode cuts, vertical shorts, branded overlays, thumbnails, loudness.

- `SKILL.md` — module rules + usage entry points (start here)
- `PLAYBOOK.md` — cross-episode pipeline lessons (alignment, layout, hooks,
  loudness, verification)
- `vidkit/` — the library (brand / ff / draw / captions / facetrack / loudness / shorts / simcapture)
- `systems/` — brand/design systems, same protocol as design-page-bot:
  `systems/<name>/brand.json` (palette, sheet/wordmark geometry) +
  optional `assets/` and `fonts/`. Drop in a directory to register a
  system; select with `VIDKIT_SYSTEM` (default `math-vs-vibes`).

Usage scripts live in the content repo (`~/grove/math-vs-vibes/promo/...`)
and import the library with this repo on `sys.path`:

```python
sys.path.insert(0, os.path.expanduser("~/grove/video-editor"))
from vidkit import brand, ff, draw, captions, facetrack, loudness, shorts
```

Dependencies: Python 3.10+, Pillow, ffmpeg + ffprobe on PATH.
