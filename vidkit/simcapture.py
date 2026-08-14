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
import json
import os
import subprocess
import sys

_MJS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "simcapture.mjs")


def capture(url, out, duration=10.0, size=(1080, 1920), start_tick=None,
            speed=None, camera=None, retime=None, min_vehicle_zoom=None,
            fps=30, crf=18, settle=1.5, fmt="png", keep_frames=False,
            gpu=False, timeout=120, follow=None, follow_zoom=None,
            highlight=False):
    """Capture `duration` seconds of the replay at `url` into mp4 `out`.

    camera: drone keyframes — a JSON file path, or a list of dicts
    [{at, duration, center?, zoom?, bearing?, pitch?, ease?}, ...]
    (seconds from record start), applied to the viz's maplibre map.

    retime: smoothness — capture N× longer wall-clock, compress ÷N on
    encode (screenshot rate caps unique frames; retime multiplies it).
    Pair with a replay speed N× slower than the wanted motion; effective
    sim speed = speed × retime. Camera keyframes stay in output seconds.

    follow: lock the camera onto a real vehicle — a numeric feature id or
    "cls@lng,lat[,heading]" (cls: car|truck|any). follow_zoom sets the
    zoom; highlight rings the vehicle. camera keyframes then spline
    zoom/bearing/pitch and offset=[east_m, north_m] around it (fly-bys),
    never center. Follow shots want effective 3-4x to read as motion.
    """
    cmd = ["node", _MJS, "--url", url, "--out", out,
           "--duration", str(duration), "--size", f"{size[0]}x{size[1]}",
           "--fps", str(fps), "--crf", str(crf), "--settle", str(settle),
           "--format", fmt, "--timeout", str(timeout)]
    if start_tick is not None:
        cmd += ["--start-tick", str(int(start_tick))]
    if speed is not None:
        cmd += ["--speed", str(speed)]  # any value > 0; sub-1x (e.g. 0.25) pairs with retime
    if camera is not None:
        cmd += ["--camera",
                camera if isinstance(camera, str) else json.dumps(camera)]
    if retime is not None:
        cmd += ["--retime", str(retime)]
    if min_vehicle_zoom is not None:
        cmd += ["--min-vehicle-zoom", str(min_vehicle_zoom)]
    if keep_frames:
        cmd.append("--keep-frames")
    if gpu:
        cmd.append("--gpu")
    if follow is not None:
        cmd += ["--follow", str(follow)]
    if follow_zoom is not None:
        cmd += ["--follow-zoom", str(follow_zoom)]
    if highlight:
        cmd.append("--highlight")
    subprocess.run(cmd, check=True)
    return out


if __name__ == "__main__":
    sys.exit(subprocess.run(["node", _MJS, *sys.argv[1:]]).returncode)
