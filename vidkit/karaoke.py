"""Fixed-geometry karaoke captions (per-word ASS events).

Every word of a cue gets its own \\pos-anchored event, so a word's center
never moves when it enlarges: the active word simply scales about its own
center. Neighbors may get overlapped by the enlarged word; the inter-word
spacing itself never shifts between timing states. A vector-drawn rounded
box per cue replaces BorderStyle 3 (which requires a single-line event).

Why per-word: libass's full-line layout matches no client-side text
measurement (on this box it renders ~0.89x PIL's Liberation advances), so
a separately measured "pop overlay" never lands on its slot in the base
line. Per-word events make positions exact by construction — the only
layout libass performs is centering ONE word on the \\pos point, and the
pop IS the base word (same event, same center, just scaled).

Vertical: all words anchor an5 at the line-box center, so every word
shares one baseline regardless of descenders.

Cue ends are clamped to the next cue's start: libass assigns a shifted-up
slot the moment an event starts while another is still active, and the
shift sticks for the event's whole life (an 80ms tail overlap made every
following cue render a line high).
"""
from PIL import ImageFont


def word_centers(words, font, frame_w):
    """[(x_center_per_word)], line_total — PIL advance layout, centered."""
    widths = [font.getlength(w) for w in words]
    space = font.getlength(" ")
    total = sum(widths) + space * (len(words) - 1)
    x = (frame_w - total) / 2.0
    centers = []
    for w in widths:
        centers.append(x + w / 2.0)
        x += w + space
    return centers, total


def _ts(t):
    return "%d:%02d:%05.2f" % (t // 3600, (t % 3600) // 60, t % 60)


def ass_color(rgb):
    """(r, g, b) -> ASS &H00BBGGRR."""
    r, g, b = rgb
    return "&H00%02X%02X%02X" % (b, g, r)


def karaoke_ass(cues, font_path, size=58, frame=(1080, 1920), margin_v=300,
                spoken=(255, 255, 255), dim=(154, 154, 154),
                box_rgba=(20, 24, 32, 160), pad=14, pop_scale=110):
    """Build an ASS file of fixed-geometry karaoke captions.

    cues: sorted [(start, end, [(word_start, word_end, token), ...],
                   accent_rgb)] — accent_rgb is the active-word color.
    Returns the ASS text.
    """
    W, H = frame
    font = ImageFont.truetype(font_path, size)
    asc, desc = font.getmetrics()
    baseline = H - margin_v - desc
    cy = baseline - (asc - desc) / 2.0      # line-box center (an5 anchor)
    spoken_a, dim_a = ass_color(spoken), ass_color(dim)

    header = """[Script Info]
PlayResX: %d
PlayResY: %d
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: CapWord,Liberation Sans,%d,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,0,0,5,0,0,0,1
Style: CapBox,Liberation Sans,%d,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
""" % (W, H, size, size)

    out = [header]
    for ci, (s, e, toks, accent) in enumerate(cues):
        if ci + 1 < len(cues):
            e = min(e, cues[ci + 1][0])
        words = [tk for _, _, tk in toks]
        centers, total = word_centers(words, font, W)
        # box (vector rect; BorderStyle-3 look without a single-line event)
        bw = total + 2 * pad
        bh = asc + desc + 2 * pad
        bx, by = W / 2.0 - bw / 2.0, cy - bh / 2.0
        r, g, b, a = box_rgba
        out.append(
            "Dialogue: 0,%s,%s,CapBox,,0,0,0,,"
            r"{\pos(%.1f,%.1f)\1c&H00%02X%02X%02X&\1a&H%02X&\p1}"
            "m 0 0 l %.1f 0 %.1f %.1f 0 %.1f\n"
            % (_ts(s), _ts(e), bx, by, b, g, r, a, bw, bw, bh, bh))
        acc = ass_color(accent)
        for j in range(len(toks)):
            ev_start = s if j == 0 else toks[j][0]
            ev_end = toks[j + 1][0] if j + 1 < len(toks) else e
            for k, (_, _, tk) in enumerate(toks):
                if k < j:
                    tag = r"{\pos(%.1f,%.1f)\1c%s}" % (centers[k], cy,
                                                      spoken_a)
                elif k == j:
                    tag = (r"{\pos(%.1f,%.1f)\1c%s\fscx%d\fscy%d}"
                           % (centers[k], cy, acc, pop_scale, pop_scale))
                else:
                    tag = r"{\pos(%.1f,%.1f)\1c%s}" % (centers[k], cy, dim_a)
                out.append("Dialogue: 1,%s,%s,CapWord,,0,0,0,,%s%s\n"
                           % (_ts(ev_start), _ts(ev_end), tag, tk))
    return "".join(out)
