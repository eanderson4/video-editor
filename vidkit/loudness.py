"""Loudness normalization to a streaming target (default -14 LUFS).

Why not plain loudnorm: single-pass undershoots (~-16), and two-pass linear
loudnorm is true-peak limited — it stops around -15.5 when peaks hit the
-1.5 dBTP ceiling. The chain that actually converges on speech content is
measured volume gain + a true-peak limiter at the ceiling. Stop within
~0.3 dB of target; pushing harder audibly squashes speech. (YouTube never
boosts quiet audio, so undershooting costs loudness relative to every
other short in the feed.)

Audio-only re-encode; the video stream is copied untouched.

CLI:  python3 loudness.py file.mp4 [more.mp4 ...]
"""
import os
import sys

if __package__:
    from . import ff
else:  # run directly as a script: python3 vidkit/loudness.py file.mp4
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from vidkit import ff


def normalize(path, target=-14.0, tp_db=-1.5, tolerance=0.3, bitrate="256k"):
    """Bring path to target LUFS (in place). Returns (before, after, gain_db);
    gain 0.0 means it was already within tolerance."""
    before = ff.lufs(path)
    gain = round(target - before, 2)
    if abs(gain) <= tolerance:
        return before, before, 0.0
    limit = round(10 ** (tp_db / 20), 3)   # -1.5 dBTP -> 0.841 linear
    root, ext = os.path.splitext(path)
    tmp = root + ".gain" + ext
    ff.run([ff.FFMPEG, "-y", "-v", "error", "-i", path, "-c:v", "copy",
            "-af", "volume=%gdB,alimiter=limit=%g:level=false,aresample=48000"
            % (gain, limit),
            "-c:a", "aac", "-b:a", bitrate, "-movflags", "+faststart", tmp])
    os.replace(tmp, path)
    return before, ff.lufs(path), gain


def loudnorm_two_pass(path, I=-14, TP=-1.5, LRA=11, bitrate="256k"):
    """Two-pass linear loudnorm (in place). Kept for material where the
    limiter chain is inappropriate; expect it to stop short of target
    whenever true peaks hit the TP ceiling."""
    m = ff.loudnorm_measure(path, I, TP, LRA)
    root, ext = os.path.splitext(path)
    tmp = root + ".norm" + ext
    ff.run([ff.FFMPEG, "-y", "-v", "error", "-i", path, "-c:v", "copy",
            "-af", "loudnorm=I=%g:TP=%g:LRA=%g:measured_I=%s:measured_TP=%s:"
            "measured_LRA=%s:measured_thresh=%s:linear=true,aresample=48000"
            % (I, TP, LRA, m["input_i"], m["input_tp"], m["input_lra"],
               m["input_thresh"]),
            "-c:a", "aac", "-b:a", bitrate, "-movflags", "+faststart", tmp])
    os.replace(tmp, path)
    return ff.lufs(path)


if __name__ == "__main__":
    files = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not files:
        sys.exit(__doc__)
    for f in files:
        before, after, gain = normalize(f)
        if gain:
            print("%s: %.1f -> %.1f LUFS (gain %+.2f dB)" % (f, before, after, gain))
        else:
            print("%s: %.1f LUFS, within tolerance, skipped" % (f, before))
