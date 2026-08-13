"""simcapture — MP4 B-roll capture of a traffic-sim baked replay.

Thin wrapper over simcapture.mjs (node >= 22, no npm deps), which drives
headless Chrome over the DevTools protocol, screenshots the replay on a
wall-clock loop, and assembles true real-time CFR H.264 via the ffmpeg
concat demuxer with per-frame measured durations (swiftshader screenshot
latency is variable — a fixed capture rate would drift). ffmpeg resolves
the vidkit way: VIDKIT_FFMPEG env -> homebrew ffmpeg@7 -> PATH.

The replay URL must deep-link ?center=lng,lat&zoom=13+ — baked vehicles
only render at zoom >= 13 — and the bake must be served with
Content-Encoding: br (traffic-sim scripts/serve-baked.py).

CLI (args forwarded to the .mjs verbatim):
    python3 vidkit/simcapture.py --url <replay-url> --out clip.mp4 \
        [--duration 10] [--size 1080x1920] [--start-tick 3000] ...
"""
import os
import subprocess
import sys

_MJS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "simcapture.mjs")


def capture(url, out, duration=10.0, size=(1080, 1920), start_tick=None,
            speed=None, fps=30, crf=18, settle=1.5, fmt="png",
            keep_frames=False, gpu=False, timeout=120):
    """Capture `duration` seconds of the replay at `url` into mp4 `out`."""
    cmd = ["node", _MJS, "--url", url, "--out", out,
           "--duration", str(duration), "--size", f"{size[0]}x{size[1]}",
           "--fps", str(fps), "--crf", str(crf), "--settle", str(settle),
           "--format", fmt, "--timeout", str(timeout)]
    if start_tick is not None:
        cmd += ["--start-tick", str(int(start_tick))]
    if speed is not None:
        cmd += ["--speed", str(int(speed))]
    if keep_frames:
        cmd.append("--keep-frames")
    if gpu:
        cmd.append("--gpu")
    subprocess.run(cmd, check=True)
    return out


if __name__ == "__main__":
    sys.exit(subprocess.run(["node", _MJS, *sys.argv[1:]]).returncode)
