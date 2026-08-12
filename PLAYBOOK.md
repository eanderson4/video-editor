# MATH vs VIBES episode pipeline playbook

Cross-episode, start-to-finish. Distilled from the ep-02 (2.5) and ep-04
renders. Library code lives in this repo (`vidkit/` package; see `SKILL.md`
for module rules); per-episode usage scripts live in the content repo
(`~/grove/math-vs-vibes/promo/...`) and hold only content. Reference
implementations: `promo/ep-02/edit/build-cut.py` (two-host) and
`promo/ep-04/edit/build-cut.py` (solo host, focus-state layout) there.

## 1. Riverside export checklist

Download per session, into `promo/ep-XX/footage/`:
- Each participant's camera track (`<name>-<uuid>-CFR.mp4`)
- Screenshare track (`screenshare-<uuid>-CFR.mp4`)
- Each participant's **raw audio** (`riverside_<name>_raw-audio_....wav`)
- Captions + transcript (`<name>.srt` / `.txt`)

Do not trust "CFR = session-aligned" blindly. Verify empirically before
cutting anything (below).

## 2. Session alignment — verify, don't assume

Camera/screenshare CFR tracks have always been session-aligned (t=0 =
session 0). The raw-audio WAV is NOT guaranteed to be:

- **ep-04 lesson**: the raw mic WAV led the session by a constant
  **+4.773s** (`session = wav_time + 4.773`), no drift. First clue: speech
  energy in the WAV appeared ~0.7s before the SRT cue while the camera
  audio matched the SRT. Envelope cross-correlation against the camera
  audio was unreliable at small search windows (kept locking onto repeated
  phrases — e.g. two different "Hey everyone" takes). What worked:
  **matched filter** — take a 3-8s envelope snippet of the *camera* audio
  and slide it over the WAV with per-position normalized correlation
  (NCC). Clean speech matches at NCC ~0.99; refines to ±2ms with parabolic
  interpolation. Check 5 points across the session to rule out drift
  (ep-04: constant to ±2ms over 23 min).
- The SRT is session-time and matches the camera audio onsets to ~0.1s.
  Sanitize with `silencedetect`/RMS profiles when in doubt.
- Once the WAV lead is measured, every WAV input seek is
  `session_t - LEAD`. Lipsync check after render: envelope-xcorr the
  final's audio against the camera track at an early and a late solo
  segment; ±50ms is fine, watch for growth (drift).

## 3. Environment adaptations (Linux box, 2026-08)

- ffmpeg versions: ffmpeg 7/8 on macOS deadlock/truncate our many-input
  overlay graphs; Linux ffmpeg 6.1 renders them fine. `ff.py` auto-resolves
  (VIDKIT_FFMPEG env -> homebrew ffmpeg@7 -> PATH). Same for fonts:
  `brand.py` resolves macOS Arial then Linux Liberation Sans
  (VIDKIT_FONT_HEAVY/BOLD env overrides).
- **ffmpeg 6.1 bug**: `apad` + `-shortest` dies mid-stream with
  `Error while filtering: No space left on device` at a reproducible byte
  count. Workaround: `aresample=48000,apad,atrim=0:<exact seg dur>` and
  drop `-shortest` (same anti-drift effect per seg).
- Overlay PNGs as single-still inputs (no `-loop`) work on 6.1 — overlay's
  default `eof_action=repeat` holds the frame. Looped stills as MAIN
  inputs (title/end cards) use `-loop 1 -framerate 2 -t <dur>`.
- libass is present: burn captions with the `subtitles` filter; fontconfig
  resolves "Liberation Sans" Bold automatically.

## 4. Layout patterns (ep-04 v2)

One composite look per episode body: same background sheet, wordmark, TOC
rail at all times; only the video windows change. Two focus states, hard
cuts between them (no animation):
- `focus-screen`: screenshare big (48,156)+1098x800, face PiP
  (1180,340)+280x497. Used for screen-driven segments.
- `focus-eric`: camera big in the same left window (crop ~1186x864,
  face-centered), screenshare demoted to (1180,340)+280x204. Used for
  talking-head segments.
- Sheets are opaque 4K INK sheets with punched rounded windows, shipped
  at 1080p via `draw.save2x`; one PNG per (state x TOC state) combo,
  selected per segment — no enable windows needed.
- Head centering: verify crops with frame grabs + image review at the
  start of every focus-eric segment; one crop per distinct posture
  (subjects lean — ep-04's punch-ins needed 1.10x, not 1.15x, because the
  host leans in during those segments).
- Captions: libass, Liberation Sans Bold 46px, white on ~56%-alpha INK
  box (BorderStyle=3), bottom-center on the free band below the big
  window (MarginV ~50) — never over the face. Re-time per segment from
  the session SRT; drop neighbour-cue slivers (<0.6s overlap) at cuts.

## 5. TOC rail pattern

Chapter list down the right edge (x~1500-1890 @1080p), one sheet variant
per state: passed = blue check disc + dim text, current = blue ring/dot +
white text, upcoming = dim hollow dot. State chosen per segment; chapter
mapping is editorial (keep it monotone — no bouncing current-highlight).
All-checked variant doubles as the end card. Hook beats that replay body
content render rail-less (pre-title), except a tease beat which may show
state 0.

## 6. Two-take hook strategy + seg cache

- Render the body ONCE (title card → end card) as cached segs + `body.ts`.
- Hook variants render as separate segs; each take = concat(hook segs,
  body.ts). Takes differ ONLY in the hook.
- Seg cache (`edit/work/render/segNNN_name.ts`, gitignored): filename-keyed;
  delete exactly the segs whose inputs changed. Ep-04 v2 reused all
  focus-screen segs and re-rendered only solo→focus-eric segs.
- Cut points: snap to SRT cue boundaries with pads, but clamp pads so
  they never pull a cut word's tail across the boundary; for hook beats,
  measure the WAV envelope and place cuts in real silence gaps with
  >=120ms margins to word edges (mark NO_SNAP after measuring).

## 7. Entry/title

~4s title card separates hook from body. Music: no asset may be lifted
(prior Content ID claim on an external bed). Placeholder = synthesized
quiet sine-pad swell (`edit/assets/entry-sting.wav`, ~-18 dBFS peak,
fade-out mixed under the first ~1.2s of the first body seg). Single
configurable input; swap for the licensed sting and re-render TITLE +
first seg.

## 8. Loudness (always last)

`vidkit.loudness.normalize()` per final (measured gain + true-peak
limiter, in place, +faststart). Iterate until gain 0 / within 0.3 dB —
ep-04's raw WAV was -31.6 LUFS and needed 3 passes to converge at -14.3.
Do not push past the limiter wall; -14.3 is fine, squashed speech is not.

## 9. Verification checklist (before declaring done)

- ffprobe every final: duration vs EDL total, 1920x1080, 24fps, aac 48k.
- Frame-grab + image review: one frame per distinct layout/state
  (both focus states, each TOC state used, montage, title, end card,
  hook beats) — framing, rail legibility, caption placement.
- Joins: 2-3 segment joins — audio envelope continuity (no gaps/doubled
  words); hook joins get the >=120ms margin check.
- Sync: envelope-xcorr final vs camera at an early and a late segment.
- LUFS report for every final.
- Montage/special segs: verify output duration matches spec ±0.5s.
