"""Head tracking for follow-cam crops.

Measured lesson from EP-02 i-failed-math: never eyeball a moving subject's
position — track it. The default detector is a warm-tone centroid (straw
hat + skin) that proved frame-accurate on the Riverside feeds; a stronger
detector (YOLO / mediapipe face) can be plugged in via `detector` without
touching the expression plumbing.

Typical flow:
    xs = track_head_x(src, 701.05, 729.45)          # [(t_session, x, weight)]
    knots = [(6.25, 940), (7.15, 1290), ...]        # hand-smoothed, shot-relative t
    expr = crop_x_expr(knots)                       # for XEXPR in the shorts spec
"""
import os
import subprocess
import tempfile

from PIL import Image

from . import ff


def warm_centroid(img, top_frac=0.75):
    """Default detector: centroid x of warm (hat/skin) pixels in the top
    top_frac of the frame. img is a small RGB frame. Returns (x, weight)
    in img coordinates, or None if too few pixels matched."""
    w, h = img.size
    ymax = int(h * top_frac)
    px = img.load()
    sx = n = 0
    for y in range(ymax):
        for x in range(w):
            r, g, b = px[x, y][:3]
            if r > 110 and r > g > b and 45 < (r - b) < 130 and (g - b) > 10:
                sx += x
                n += 1
    if n < 200:
        return None
    return sx / n, n


def track_head_x(src, start, end, fps=4, scale_w=480, scale_h=270,
                 detector=None, workdir=None):
    """Track horizontal head position over [start, end] of a video.

    Extracts frames at `fps` downscaled to scale_w x scale_h, runs `detector`
    (default warm_centroid) on each, and maps x back to source pixels.
    Returns [(session_time, x_source_px, weight)]; frames where the detector
    returns None are skipped.
    """
    detector = detector or warm_centroid
    sw = ff.video_size(src)[0]
    own = workdir is None
    workdir = workdir or tempfile.mkdtemp(prefix="facetrack-")
    ff.run([ff.FFMPEG, "-y", "-v", "error", "-ss", "%.3f" % start,
            "-to", "%.3f" % end, "-i", src,
            "-vf", "fps=%g,scale=%d:%d" % (fps, scale_w, scale_h),
            os.path.join(workdir, "f%04d.png")])
    out = []
    i = 0
    while True:
        p = os.path.join(workdir, "f%04d.png" % (i + 1))
        if not os.path.exists(p):
            break
        hit = detector(Image.open(p).convert("RGB"))
        if hit is not None:
            cx, n = hit
            out.append((round(start + i / fps, 2), round(cx * sw / scale_w), n))
        i += 1
    if own:
        for f in os.listdir(workdir):
            os.remove(os.path.join(workdir, f))
        os.rmdir(workdir)
    return out


def knots_to_expr(knots):
    """Piecewise-linear ffmpeg expression through [(t, x), ...] knots:
    hold before the first knot, linear ramps between knots, hold after the
    last. t must be shot-relative (crop runs after setpts=PTS-STARTPTS)."""
    knots = sorted(knots)
    expr = "%g" % knots[-1][1]
    for (t0, x0), (t1, x1) in reversed(list(zip(knots, knots[1:]))):
        if x0 == x1:
            seg = "%g" % x0
        else:
            seg = "%g+%g*(t-%g)/%g" % (x0, x1 - x0, t0, t1 - t0)
        expr = "if(lt(t,%g),%s,%s)" % (t1, seg, expr)
    return "if(lt(t,%g),%g,%s)" % (knots[0][0], knots[0][1], expr)


def crop_x_expr(head_knots, crop_w=608, src_w=1920):
    """Crop-x expression that keeps a tracked head centered: head_knots are
    [(shot_relative_t, head_center_x_source_px)]. Suitable as an XEXPR value
    for vidkit.shorts (which clamps and escapes it)."""
    half = crop_w // 2
    xmax = src_w - crop_w
    return knots_to_expr([(t, min(max(x - half, 0), xmax)) for t, x in head_knots])
