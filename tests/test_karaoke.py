"""Tests for vidkit.karaoke — fixed-geometry karaoke captions.

The contract these tests pin down:
1. Word centers are computed from PIL advances and NEVER change between
   timing states — the pop is the base word scaling about its own center.
2. No event ever overlaps the next cue (libass shifts late-starting
   events up a line and the shift sticks).
3. All words share one vertical anchor (one baseline, descender-safe).
4. The drawn box covers the whole line.
5. (integration, needs ffmpeg+libass) rendered word ink actually sits on
   the predicted centers and doesn't move when the neighbor pops.
"""
import os
import re
import shutil
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.expanduser("~/grove/video-editor"))
from vidkit import karaoke  # noqa: E402

FONT = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
ORANGE = (255, 90, 46)
BLUE = (46, 90, 255)

CUES = [
    (8.24, 10.53, [(8.24, 8.72, "Every"), (8.72, 9.66, "morning,"),
                   (9.66, 9.86, "its"), (9.86, 10.53, "creator")], BLUE),
    # this cue starts BEFORE the previous one's raw end on purpose —
    # the writer must clamp the previous cue's end to 42.29
    (42.29, 44.29, [(42.29, 44.29, "Perhaps"), (44.29, 44.63, "next"),
                    (44.63, 45.09, "time.")], ORANGE),
]
# give cue 1 a tail that overlaps cue 2, like the whisper +0.08 tail did
CUES[0] = (CUES[0][0], 42.37, CUES[0][2], CUES[0][3])


def events(ass):
    """[(layer, start, end, style, tags, text)] parsed from Dialogue lines."""
    out = []
    for line in ass.splitlines():
        if not line.startswith("Dialogue"):
            continue
        layer, start, end, style, _n, _ml, _mr, _mv, _fx, text = \
            line[len("Dialogue: "):].split(",", 9)
        m = re.match(r"(\{[^}]*\})?(.*)", text, re.S)
        out.append((int(layer), karaoke_sec(start), karaoke_sec(end),
                    style, m.group(1) or "", m.group(2)))
    return out


def karaoke_sec(t):
    h, m, s = t.split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


@pytest.fixture(scope="module")
def ass():
    return karaoke.karaoke_ass(CUES, FONT, size=58, frame=(1080, 1920),
                               margin_v=300, pop_scale=110)


# ---------------------------------------------------------------- geometry
def test_word_centers_spacing():
    from PIL import ImageFont
    f = ImageFont.truetype(FONT, 58)
    words = ["Every", "morning,", "its", "creator"]
    centers, total = karaoke.word_centers(words, f, 1080)
    # symmetric margins
    left = centers[0] - f.getlength(words[0]) / 2
    right = centers[-1] + f.getlength(words[-1]) / 2
    assert left == pytest.approx(1080 - right, abs=0.01)
    # adjacent slots are exactly one space apart
    sp = f.getlength(" ")
    for a, b, wa, wb in zip(centers, centers[1:], words, words[1:]):
        gap = (b - f.getlength(wb) / 2) - (a + f.getlength(wa) / 2)
        assert gap == pytest.approx(sp, abs=0.01)


def test_word_positions_fixed_across_states(ass):
    """A word's \\pos must be byte-identical in every timing state."""
    pos_by_word = {}
    for layer, s, e, style, tags, text in events(ass):
        if style != "CapWord":
            continue
        m = re.search(r"\\pos\(([\d.]+),([\d.]+)\)", tags)
        pos_by_word.setdefault(text, set()).add((m.group(1), m.group(2)))
    for word, poses in pos_by_word.items():
        assert len(poses) == 1, "%r moved between states: %s" % (word, poses)


def test_active_word_scales_in_place(ass):
    """Exactly the active-word event carries fscx/fscy, same \\pos."""
    for layer, s, e, style, tags, text in events(ass):
        if style != "CapWord":
            continue
        if "fscx" in tags:
            assert "fscx110" in tags and "fscy110" in tags


def test_all_words_share_one_y(ass):
    ys = set()
    for layer, s, e, style, tags, text in events(ass):
        if style == "CapWord":
            ys.add(re.search(r"\\pos\([\d.]+,([\d.]+)\)", tags).group(1))
    assert len(ys) == 1


def test_y_is_baseline_centered():
    """cy must equal baseline - (asc-desc)/2 for the requested metrics."""
    from PIL import ImageFont
    f = ImageFont.truetype(FONT, 58)
    asc, desc = f.getmetrics()
    expected = 1920 - 300 - desc - (asc - desc) / 2.0
    ass = karaoke.karaoke_ass(CUES[:1], FONT, size=58, frame=(1080, 1920),
                              margin_v=300)
    y = float(re.search(r"\\pos\([\d.]+,([\d.]+)\)",
                        [l for l in ass.splitlines()
                         if l.startswith("Dialogue")
                         and "CapWord" in l][0]).group(1))
    assert y == pytest.approx(expected, abs=0.05)


# ---------------------------------------------------------------- timing
def test_no_cue_overlap(ass):
    """No event may cross into the next cue's start (libass line-shift)."""
    evs = events(ass)
    cue2_start = 42.29
    for layer, s, e, style, tags, text in evs:
        if s < cue2_start:
            assert e <= cue2_start + 1e-6, \
                "event %r %s-%s crosses next cue" % (text, s, e)


def test_word_states_are_sequential(ass):
    """Within a cue, state j ends when state j+1 begins (no gaps/overlaps)."""
    spans = sorted((s, e) for layer, s, e, style, tags, text in events(ass)
                   if style == "CapWord" and text == "Every")
    for (_, e), (s2, _) in zip(spans, spans[1:]):
        assert e == pytest.approx(s2, abs=1e-6)


# ---------------------------------------------------------------- box
def test_box_covers_line(ass):
    from PIL import ImageFont
    f = ImageFont.truetype(FONT, 58)
    words = ["Every", "morning,", "its", "creator"]
    centers, total = karaoke.word_centers(words, f, 1080)
    for layer, s, e, style, tags, text in events(ass):
        if style != "CapBox" or s > 9.0:
            continue
        m = re.search(r"\\pos\(([\d.]+),([\d.]+)\)", tags)
        bx = float(m.group(1))
        bw = float(re.search(r"l ([\d.]+) 0", text).group(1))
        slot_l = centers[0] - f.getlength(words[0]) / 2
        slot_r = centers[-1] + f.getlength(words[-1]) / 2
        assert bx <= slot_l and bx + bw >= slot_r


# ---------------------------------------------------------------- render
FFMPEG = shutil.which("ffmpeg")


def _ink_center(png, lo=100):
    import numpy as np
    from PIL import Image
    a = np.array(Image.open(png).convert("RGB")).max(axis=2)
    ink = a > lo
    cols = np.where(ink.any(axis=0))[0]
    rows = np.where(ink.any(axis=1))[0]
    return (cols.min() + cols.max()) / 2.0, (rows.min() + rows.max()) / 2.0


@pytest.mark.skipif(not FFMPEG, reason="ffmpeg not available")
def test_rendered_centers_match_prediction(tmp_path):
    """Burn two states of one cue; the spoken word must not move, and the
    active word's ink center must sit on its predicted slot center."""
    from PIL import ImageFont
    cues = [(0.0, 4.0, [(0.0, 2.0, "Rush"), (2.0, 4.0, "hour,")], ORANGE)]
    ass = karaoke.karaoke_ass(cues, FONT, size=58, frame=(1080, 1920),
                              margin_v=300, pop_scale=110)
    p = tmp_path / "t.ass"
    p.write_text(ass)

    def render(t, name):
        out = tmp_path / name
        subprocess.run(
            [FFMPEG, "-y", "-loglevel", "error", "-f", "lavfi",
             "-i", "color=c=black:s=1080x1920:d=4",
             "-vf", "subtitles=%s" % p, "-ss", str(t), "-frames:v", "1",
             str(out)], check=True)
        return out

    # state 1: Rush active. Crop each word's neighborhood separately.
    f = ImageFont.truetype(FONT, 58)
    centers, _ = karaoke.word_centers(["Rush", "hour,"], f, 1080)
    import numpy as np
    from PIL import Image

    def word_center(png, x0, x1):
        a = np.array(Image.open(png).convert("RGB")).max(axis=2)
        zone = a[1480:1700, x0:x1]
        ink = zone > 100
        cols = np.where(ink.any(axis=0))[0]
        rows = np.where(ink.any(axis=1))[0]
        return (cols.min() + cols.max()) / 2.0 + x0, \
               (rows.min() + rows.max()) / 2.0 + 1480

    img1 = render(1.0, "s1.png")   # Rush active
    img2 = render(3.0, "s2.png")   # hour, active
    # hour, (dim state) sits on its predicted center — crop starts right
    # of where the 110% "Rush" can reach (~533)
    cx2_dim, cy2_dim = word_center(img1, 545, 800)
    cx2_act, cy2_act = word_center(img2, 545, 800)
    assert cx2_dim == pytest.approx(centers[1], abs=12)
    # and does not drift when it pops (center fixed, just scaled)
    assert cx2_act == pytest.approx(cx2_dim, abs=6)
    assert cy2_act == pytest.approx(cy2_dim, abs=6)
    # Rush (spoken state) doesn't move between states either
    cx1_a, cy1_a = word_center(img1, 250, 530)
    cx1_b, cy1_b = word_center(img2, 250, 530)
    assert cx1_a == pytest.approx(cx1_b, abs=2)
    assert cy1_a == pytest.approx(cy1_b, abs=2)
