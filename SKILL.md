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
Editorial pipeline (research -> narrative spec -> review -> VO -> build ->
verify -> publish, with a spec template): `docs/narrative.md`.

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
  + `load_words_from_srt(srt, speaker, offset, subs)` (Riverside/whisper
  `-osrt` cues; keep cues short, timings are interpolated) + `chunk_words`.
  Whisper JSONs carry fixed offsets back to session time;
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
- `simcapture` — MP4 B-roll of a traffic-sim baked replay: headless
  Chrome over CDP (node ≥22, no npm deps; core is `simcapture.mjs`,
  `simcapture.capture()` wraps it), wall-clock screenshot loop assembled
  as true real-time CFR via concat-demuxer per-frame durations. Uses the
  viz's `?bare=1` for clean footage; `--start-tick` seeks via the hidden
  replay slider; `--speed X` sets replay speed — any value > 0 (presets
  1|2|4|8 click the panel's buttons; anything else, e.g. 0.25, POSTs the
  baked ctl stub, which validates only speed > 0 — the panel UI is the
  only quantized part); `--camera keyframes.json` flies the
  maplibre camera like a drone while recording. Preferred keyframe format
  ({t, center?, zoom?, bearing?, pitch?} in output seconds): one
  continuous monotone-cubic-Hermite spline path sampled per frame —
  C1 velocity through waypoints (no stop-start), zero overshoot, eased
  endpoints, Mercator-space centers, shortest-way bearings; repeat a
  value at two t's to hold (e.g. lock framing before a push-in). Legacy
  format ({at, duration, ..., ease}) fires discrete maplibre eases —
  each segment stops before the next; don't overlap them.
  Screenshot rate caps unique frames (~7 fps even with --gpu at
  heavy loads → choppy playback): use `--retime N` — capture N× longer
  at an N×-slower replay speed, compressed ÷N on encode (same motion,
  N× the unique fps; camera keyframes stay in output seconds; effective
  sim speed = speed × retime — so `--speed 0.25 --retime 4` gives smooth
  TRUE-1× motion; sub-1× also widens the viz's lerp buffer, which starves
  under capture load at 1×+ and stutters the vehicles). Deep-link `?center=&zoom=13+`
  (vehicle render gate) or pass
  `--min-vehicle-zoom N` to defeat the gate for zoomed-out shots (icons
  hold ~4px down to zoom 11; whole-network = ~5-6k vehicles streaming).
  Serve the bake with `traffic-sim scripts/serve-baked.py` (brotli).
  `--gpu` drops swiftshader for hardware GL (~4× faster capture). CLI:
  `python3 ~/grove/video-editor/vidkit/simcapture.py --url ... --out clip.mp4`.
- `musicgen` — original music beds + SFX via the ElevenLabs API
  (`ELEVENLABS_API_KEY`, Creator plan = commercial license for monetized
  YouTube; decision doc `docs/musicgen.md`). `music(prompt, out, seconds,
  seed)` forces instrumental; `sfx(text, out, seconds)` ≤22 s. Non-mp3
  `--out` converts via ffmpeg. CLI:
  `python3 -m vidkit.musicgen "prompt" --seconds 30 --out bed.wav`
  (or `sfx "truck horn" --out horn.wav`).

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
