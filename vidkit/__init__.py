"""vidkit — MATH vs VIBES video pipeline library.

Modules:
  brand      palette / fonts / wordmark geometry (single source of truth)
  ff         ffmpeg plumbing: pinned ffmpeg 7, probing, LUFS, expr escaping
  draw       PIL primitives: captions/chips/hooks, 4K sheet system, thumbs
  captions   whisper word loading (offsets + fixes) and caption chunking
  facetrack  head tracking + follow-cam crop-x expressions (YOLO-pluggable)
  loudness   normalize finished files to -14 LUFS (gain + true-peak limiter)
  shorts     segmented two-pass vertical shorts render engine

Import with promo/tools on sys.path:
    sys.path.insert(0, <repo>/promo/tools)
    from vidkit import brand, shorts, ...
"""
from . import brand, captions, draw, facetrack, ff, loudness, shorts  # noqa: F401
