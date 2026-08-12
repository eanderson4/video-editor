---
name: video-editor
description: Render video assets — episode cuts, vertical shorts, branded overlays, thumbnails, loudness — using the vidkit library in this repo. Use when building or fixing any video/promo render.
---

# Video editing (vidkit)

All video-pipeline library code lives in this repo (`~/grove/video-editor`).
Usage scripts live in the content repo (e.g. `~/grove/math-vs-vibes/promo/...`)
and hold only content (specs, cut lists, copy). Import pattern:

```python
sys.path.insert(0, os.path.expanduser("~/grove/video-editor"))
from vidkit import brand, ff, draw, captions, facetrack, loudness, shorts
```

Cross-episode pipeline lessons: `PLAYBOOK.md` (read it before any episode
render — alignment, layout, hooks, loudness, verification).

## Modules

- `brand` — brand/design systems, mirroring the design-page-bot protocol:
  a system is a directory under `systems/` with at minimum `brand.json`
  (palette, sheet/wordmark geometry, optional `assets/`, optional `fonts/`).
  Adding a system = drop in a directory, zero code changes. Active system:
  `VIDKIT_SYSTEM` env (default `math-vs-vibes`). Structured access:
  `PALETTE` / `WORDMARK` / `SHEET_W/H` / `ASSETS`; legacy constants
  (`brand.MATH_BLUE`, `brand.MATH_BOX`, ...) resolve from the active system.
  Fonts auto-resolve (system fonts/ -> macOS Arial -> Linux Liberation Sans;
  `VIDKIT_FONT_HEAVY/BOLD` overrides). List systems:
  `python3 -m vidkit.brand`. Never hardcode brand colors elsewhere.
- `ff` — ffmpeg plumbing. Binary auto-resolves: `VIDKIT_FFMPEG` env ->
  homebrew ffmpeg@7 -> PATH. ffmpeg 8 deadlocks/truncates on our many-input
  overlay graphs; Linux ffmpeg 6.1 is fine. Also
  `duration/video_size/lufs/loudnorm_measure/esc_expr`.
- `draw` — PIL primitives: shorts captions/chips/hook cards/border frames,
  the 4K designer-sheet system (`make_bg/punch/wordmark/banner/save2x`),
  thumbnail cards/cameos/stroked text.
- `captions` — `load_words(whisper_dir, [(stem, session_offset)], fixes, subs)`
  + `chunk_words`. Whisper JSONs carry fixed offsets back to session time;
  word fixes are keyed `(speaker, round(session_start, 2))`.
- `facetrack` — warm-tone centroid head tracker (`track_head_x`) +
  `knots_to_expr`/`crop_x_expr` for follow-cam crops. **Never eyeball a
  moving subject — track it, then verify by drawing on frames.** A YOLO or
  mediapipe detector plugs in via the `detector` argument.
- `loudness` — `normalize()` to -14 LUFS via measured gain + true-peak
  limiter (plain loudnorm can't reach target). CLI:
  `python3 ~/grove/video-editor/vidkit/loudness.py file.mp4 ...`.
  Run on every final.
- `shorts` — `ShortsBuilder` segmented two-pass vertical shorts engine
  (1080x1920 speaker-cut shorts from session-aligned horizontal tracks,
  PIL caption/chip/hook overlays).

## Usage entry points (in ~/grove/math-vs-vibes)

- **EP-02 shorts**: `promo/ep-02/shorts-build/build.py [--test] [--framed] [names]`
  — spec-only (SHORTS dict, FIXES, XEXPR). Finals -> `promo/ep-02/shorts/`.
  Span segs cache in `shorts-build/work/segs/` by filename; delete a short's
  `.mkv`s after editing its spans.
- **EP 2.5 episode**: `promo/ep-02/edit/build-cut.py inspect|render` —
  whisper-pinned EDL, auto speaker-switch shots, designer overlays.
  **NEVER pass `--fresh`**: the seg cache `edit/work/render/` holds three
  externally restyled, irreplaceable segs (seg000/001/002).
- **Episode overlays**: `promo/ep-02/edit/make-overlays.py` -> committed
  `edit/style/overlays/*.png`. Regeneration must be pixel-identical unless
  the script changed (verified 2026-07-18).
- **Thumbnails**: `promo/ep-02/thumbs/make-thumbs-finale.py` (1280x720,
  <2MB). Thumbnails don't index for SEO: title owns search terms, thumb owns
  CTR at 168px — ≤4 giant words, one emotion, don't repeat the title.

## Render gotchas (hard-won, do not relearn)

- Preview cold-opens = out-of-order reads of one input: single-pass ffmpeg
  silently truncates (v8) or deadlocks (v7). The engine's two-pass design
  (spans -> near-lossless .mkv -> concat+overlays) exists for this. Always
  check output duration; `ShortsBuilder.render` raises if it drifts >0.5s.
- Looped still-PNG overlay inputs need `-loop 1 -framerate 2`; at 24fps
  ffmpeg eagerly buffers duration×24 frames per input and OOMs. Overlays go
  in chunks of 32 (>40 inputs → SIGKILL).
- ffmpeg per-frame expressions: escape commas with `\\,` and do NOT quote —
  backslashes stay literal inside ffmpeg quotes (use `ff.esc_expr`).
  `t` is shot-relative after `setpts=PTS-STARTPTS`.
- Riverside `-CFR` tracks are session-time aligned (t=0 = session 0); whisper
  offsets apply to the JSONs, not the tracks.
- Loudness: render-time loudnorm lands ~-16 LUFS; finals need
  `loudness.normalize()` (gain + limiter → -14.4..-14.8). Stop within 0.3 dB;
  more gain audibly squashes speech.

## Dependencies

Python 3.10+, Pillow, ffmpeg + ffprobe on PATH. No other packages.
