"""ffmpeg plumbing: binary resolution, probing, loudness measurement.

ffmpeg 8's transcode scheduler deadlocks (sch_wait) or silently truncates
on the many-input overlay graphs our renderers build, so on macOS renders
go through ffmpeg 7 (keg-only homebrew install). Linux ffmpeg 6.1 renders
the same graphs fine. Resolution order for the render binary:
VIDKIT_FFMPEG env -> homebrew ffmpeg@7 -> system ffmpeg on PATH.
Probing and audio-only work are version-agnostic.
"""
import json
import os
import shutil
import subprocess

_HOMEBREW_FFMPEG7 = "/opt/homebrew/opt/ffmpeg@7/bin/ffmpeg"


def _resolve_ffmpeg():
    if os.environ.get("VIDKIT_FFMPEG"):
        return os.environ["VIDKIT_FFMPEG"]
    if os.path.exists(_HOMEBREW_FFMPEG7):
        return _HOMEBREW_FFMPEG7
    found = shutil.which("ffmpeg")
    if found:
        return found
    raise RuntimeError(
        "ffmpeg not found: set VIDKIT_FFMPEG or put ffmpeg on PATH")


FFMPEG = _resolve_ffmpeg()
FFPROBE = os.environ.get("VIDKIT_FFPROBE", "ffprobe")


def run(cmd, **kw):
    kw.setdefault("check", True)
    return subprocess.run(cmd, **kw)


def duration(path):
    out = subprocess.run(
        [FFPROBE, "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", path],
        check=True, capture_output=True, text=True).stdout.strip()
    return float(out)


def video_size(path):
    out = subprocess.run(
        [FFPROBE, "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height", "-of", "csv=p=0", path],
        check=True, capture_output=True, text=True).stdout.strip()
    w, h = out.split(",")[:2]
    return int(w), int(h)


def lufs(path):
    """Integrated loudness (EBU R128) of the first audio stream."""
    p = subprocess.run(
        [FFMPEG, "-i", path, "-map", "0:a", "-filter:a", "ebur128",
         "-f", "null", "-"],
        capture_output=True, text=True)
    lines = [l for l in p.stderr.splitlines() if l.strip().startswith("I:")]
    return float(lines[-1].split()[1])


def loudnorm_measure(path, I=-14, TP=-1.5, LRA=11):
    """First-pass loudnorm measurement (for linear second pass)."""
    p = subprocess.run(
        [FFMPEG, "-i", path, "-map", "0:a",
         "-af", "loudnorm=I=%g:TP=%g:LRA=%g:print_format=json" % (I, TP, LRA),
         "-f", "null", "-"],
        capture_output=True, text=True)
    txt = p.stderr
    return json.loads(txt[txt.rindex("{"):txt.rindex("}") + 1])


def esc_expr(expr):
    """Escape an ffmpeg per-frame expression for use inside a filtergraph
    (commas separate filter args; do NOT also quote — backslashes stay
    literal inside ffmpeg quotes and would reach the expression parser)."""
    return expr.replace(",", "\\,")
