"""PIL drawing primitives for MATH vs VIBES graphics.

Three families, all brand-tokened via vidkit.brand:
  - shorts text: captions / speaker chips / hook cards / border frames,
    drawn as transparent PNGs and composited by ffmpeg overlay (our ffmpeg
    has no libass/drawtext)
  - sheet system: 4K (3840x2160) designer sheets downscaled 2x for AA —
    wordmark, punched rounded windows, section banners (episode overlays)
  - thumbs: face cards / circular cameos / stroked hook text
"""
from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageOps

import os

from . import brand

WHITE = (255, 255, 255, 255)
BLACK = (0, 0, 0, 255)


def font(size, path=brand.FONT_HEAVY):
    return ImageFont.truetype(path, size)


# ---------------------------------------------------------------- shorts text
def draw_words_line(pieces, fnt, stroke, pad, stroke_fill=BLACK):
    """pieces: [(text, color)]. Returns RGBA image of one rendered line
    (soft drop-shadow pass under a stroked color pass). stroke_fill sets
    both the outline and the shadow tint (shadow = same hue at alpha 110)."""
    asc, desc = fnt.getmetrics()
    total_w = sum(fnt.getlength(t) for t, _c in pieces)
    W = int(total_w) + 2 * (stroke + pad)
    H = asc + desc + 2 * (stroke + pad)
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    shadow = stroke_fill[:3] + (110,)
    x = y = stroke + pad
    for t, _c in pieces:
        d.text((x + 4, y + 6), t, font=fnt, fill=shadow,
               stroke_width=stroke, stroke_fill=shadow)
        x += fnt.getlength(t)
    x = stroke + pad
    for t, c in pieces:
        d.text((x, y), t, font=fnt, fill=c, stroke_width=stroke, stroke_fill=stroke_fill)
        x += fnt.getlength(t)
    return img


def render_caption(texts, accent, path, size=72, stroke=9, maxw=850,
                   base=WHITE, stroke_fill=BLACK):
    """texts: list of words (uppercased here); the longest word >=4 chars
    gets the accent color, the rest get base. Wraps to lines <= maxw px.
    Returns (W, H)."""
    # shorts captions read faster without commas — strip them all
    # (periods and question marks stay: they close a thought)
    texts = [t.replace(",", "") for t in texts]
    idx, best = -1, 3
    for i, t in enumerate(texts):
        L = len(t.strip(".,?!'\""))
        if L > best:
            idx, best = i, L
    words = [(t.upper(), accent if i == idx else base) for i, t in enumerate(texts)]
    fnt = font(size)
    lines, cur, curw = [], [], 0.0
    for t, c in words:
        piece = (t if not cur else " " + t)
        w = fnt.getlength(piece)
        if cur and curw + w > maxw:
            lines.append(cur)
            cur, curw = [(t, c)], fnt.getlength(t)
        else:
            cur.append((piece, c))
            curw += w
    if cur:
        lines.append(cur)
    imgs = [draw_words_line(ln, fnt, stroke, 2, stroke_fill) for ln in lines]
    W = max(im.width for im in imgs)
    gap = -10
    H = sum(im.height for im in imgs) + gap * (len(imgs) - 1)
    out = Image.new("RGBA", (W, max(H, 1)), (0, 0, 0, 0))
    y = 0
    for im in imgs:
        out.alpha_composite(im, ((W - im.width) // 2, y))
        y += im.height + gap
    out.save(path)
    return out.size


def render_chip(label, color, path, size=44):
    """Small rounded speaker chip (MATH / VIBES). Returns (W, H)."""
    fnt = font(size)
    asc, desc = fnt.getmetrics()
    tw = int(fnt.getlength(label))
    padx, pady = 26, 10
    W, H = tw + 2 * padx, asc + desc + 2 * pady
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, W - 1, H - 1], radius=16, fill=color,
                        outline=(255, 255, 255, 230), width=3)
    d.text((padx, pady), label, font=fnt, fill=WHITE)
    img.save(path)
    return img.size


# per-side hero art recipe, same as the episode overlays (make-overlays.py):
# chip label -> (bg art, flat tint, art opacity, crop anchor)
BANNER_ART = {
    "MATH": ("bg-math.jpg", brand.LAVENDER, 0.55, "top"),
    "VIBES": ("bg-vibes.jpg", brand.PEACH, 0.85, "center"),
}


def render_band(color, label, path, w=1080, h=110, strip=10):
    """Top brand band: a slice of the speaker's hero/intro textured sheet
    (BANNER_ART, drawn 2x for AA) with a speaker-colored strip along the
    bottom edge (the divider against the video). The speaker chip is
    overlaid separately, centered in the band. Returns (w, h)."""
    art, flat, opacity, anchor = BANNER_ART[label]
    ss = 2
    img = make_bg(os.path.join(brand.ASSETS, art), flat, opacity, anchor,
                  size=(w * ss, h * ss))
    ImageDraw.Draw(img).rectangle([0, (h - strip) * ss, w * ss - 1, h * ss - 1],
                                  fill=color + (255,))
    img.resize((w, h), Image.LANCZOS).save(path)
    return w, h


def render_frame(color, path, w=1080, h=1920, inset=28, radius=48):
    """Speaker-colored border frame: solid color, transparent rounded-rect
    center (alpha antialiased via 4x supersample). Returns (w, h)."""
    ss = 4
    img = Image.new("RGBA", (w, h), color)
    a = Image.new("L", (w * ss, h * ss), 255)
    d = ImageDraw.Draw(a)
    d.rounded_rectangle([inset * ss, inset * ss, (w - inset) * ss - 1, (h - inset) * ss - 1],
                        radius=radius * ss, fill=0)
    img.putalpha(a.resize((w, h), Image.LANCZOS))
    img.save(path)
    return w, h


def render_hook(lines, path, start_size=78, maxw=1000):
    """Hook card: ink rounded card, multi-color heavy text, autofit from
    start_size down until the widest line fits maxw. Returns (W, H)."""
    size = start_size
    while size > 30:
        fnt = font(size)
        padx = 36
        widths = [sum(fnt.getlength(t) for t, _c in ln) for ln in lines]
        if int(max(widths)) + 2 * padx <= maxw:
            break
        size -= 2
    asc, desc = fnt.getmetrics()
    pady, lh = 26, asc + desc + 6
    W = int(max(widths)) + 2 * padx
    H = lh * len(lines) + 2 * pady
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, W - 1, H - 1], radius=24, fill=brand.INK + (242,),
                        outline=(255, 255, 255, 40), width=2)
    for i, ln in enumerate(lines):
        x = (W - widths[i]) / 2
        y = pady + i * lh
        for t, c in ln:
            d.text((x, y), t, font=fnt, fill=c)
            x += fnt.getlength(t)
    img.save(path)
    return img.size


# ---------------------------------------------------------------- 4K sheets
def render_word(text, color, box):
    """Render text in heavy sans, crop to ink, resize to exact target box.
    Returns (word_img, paste_pos)."""
    x0, y0, x1, y1 = box
    fnt = font(400)
    tmp = Image.new("RGBA", (3000, 700), (0, 0, 0, 0))
    ImageDraw.Draw(tmp).text((50, 50), text, font=fnt, fill=color + (255,))
    word = tmp.crop(tmp.getbbox()).resize((x1 - x0, y1 - y0), Image.LANCZOS)
    return word, (x0, y0)


def make_bg(art_path, flat, opacity, anchor, size=(brand.SHEET_W, brand.SHEET_H)):
    """Cover-scale/crop bg art to size, blended over flat color at opacity."""
    W, H = size
    art = Image.open(art_path).convert("RGB")
    s = max(W / art.width, H / art.height)
    art = art.resize((round(art.width * s), round(art.height * s)), Image.LANCZOS)
    x0 = (art.width - W) // 2
    y0 = 0 if anchor == "top" else (art.height - H) // 2
    art = art.crop((x0, y0, x0 + W, y0 + H))
    flat_img = Image.new("RGB", (W, H), flat)
    return Image.blend(flat_img, art, opacity).convert("RGBA")


def punch(img, boxes_radii):
    """Cut transparent rounded windows [(box, radius), ...] out of img's alpha."""
    alpha = img.getchannel("A")
    mask = Image.new("L", img.size, 0)
    md = ImageDraw.Draw(mask)
    for box, r in boxes_radii:
        md.rounded_rectangle(box, radius=r, fill=255)
    img.putalpha(ImageChops.subtract(alpha, mask))


def wordmark(img, y_shift=0, chip_fill=None):
    """MATH [vs] VIBES wordmark at the measured designer boxes (4K sheet),
    shifted vertically by y_shift."""
    for text, color, box in [("MATH", brand.MATH_BLUE, brand.MATH_BOX),
                             ("VIBES", brand.VIBES_ORANGE, brand.VIBES_BOX)]:
        b = (box[0], box[1] + y_shift, box[2], box[3] + y_shift)
        word, pos = render_word(text, color, b)
        img.alpha_composite(word, pos)
    d = ImageDraw.Draw(img)
    cb = (brand.CHIP_BOX[0], brand.CHIP_BOX[1] + y_shift,
          brand.CHIP_BOX[2], brand.CHIP_BOX[3] + y_shift)
    d.rounded_rectangle(cb, radius=18, fill=(chip_fill or brand.CHIP_DARK) + (255,))
    vs_font = font(300, brand.FONT_BOLD)
    tmp = Image.new("RGBA", (900, 600), (0, 0, 0, 0))
    ImageDraw.Draw(tmp).text((50, 50), "VS", font=vs_font, fill=WHITE)
    vs = tmp.crop(tmp.getbbox())
    vw = int((cb[2] - cb[0]) * 0.52)
    vh = int(vw * vs.height / vs.width)
    vs = vs.resize((vw, vh), Image.LANCZOS)
    img.alpha_composite(vs, (cb[0] + (cb[2] - cb[0] - vw) // 2,
                             cb[1] + (cb[3] - cb[1] - vh) // 2))


def banner(pieces, size=100, y0=200):
    """Section banner: transparent 4K sheet, centered ink lower-card with
    multi-color heavy text at y0 (100 @1080p, clear of the top wordmark).
    Returns the 4K RGBA image (save with save2x)."""
    fnt = font(size)
    asc, desc = fnt.getmetrics()
    tw = int(sum(fnt.getlength(t) for t, _c in pieces))
    padx, pady = 64, 24
    cw, ch = tw + 2 * padx, asc + desc + 2 * pady
    img = Image.new("RGBA", (brand.SHEET_W, brand.SHEET_H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    x0 = (brand.SHEET_W - cw) // 2
    d.rounded_rectangle([x0, y0, x0 + cw, y0 + ch], radius=40,
                        fill=brand.INK + (242,), outline=(255, 255, 255, 40), width=4)
    x = x0 + padx
    for t, c in pieces:
        d.text((x, y0 + pady), t, font=fnt, fill=c + (255,))
        x += fnt.getlength(t)
    return img


def save2x(img, path):
    """Save a 4K sheet at its delivery size (2x downscale for AA)."""
    img.resize((img.width // 2, img.height // 2), Image.LANCZOS).save(path)
    print("wrote", path)


# ---------------------------------------------------------------- thumbs
def card(path, w, h, border, radius=44, bw=16, focus=0.40, precrop=None):
    """Face crop -> rounded card with colored border. focus = vertical bias."""
    face = Image.open(path).convert("RGB")
    if precrop:
        face = face.crop(precrop)
    face = ImageOps.fit(face, (w, h), Image.LANCZOS, centering=(0.5, focus))
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    mask = Image.new("L", (w * 2, h * 2), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, w * 2 - 1, h * 2 - 1), radius * 2, fill=255)
    out.paste(face, (0, 0), mask.resize((w, h), Image.LANCZOS))
    ring = Image.new("RGBA", (w * 2, h * 2), (0, 0, 0, 0))
    ImageDraw.Draw(ring).rounded_rectangle((bw, bw, w * 2 - bw, h * 2 - bw),
                                           radius * 2, outline=border + (255,), width=bw * 2)
    out.alpha_composite(ring.resize((w, h), Image.LANCZOS))
    return out


def cameo(path, d, ring, bw=18, focus=0.40, precrop=None):
    """Circular face cameo with colored ring."""
    face = Image.open(path).convert("RGB")
    if precrop:
        face = face.crop(precrop)
    face = ImageOps.fit(face, (d, d), Image.LANCZOS, centering=(0.5, focus))
    out = Image.new("RGBA", (d, d), (0, 0, 0, 0))
    mask = Image.new("L", (d * 2, d * 2), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, d * 2 - 1, d * 2 - 1), fill=255)
    out.paste(face, (0, 0), mask.resize((d, d), Image.LANCZOS))
    ringim = Image.new("RGBA", (d * 2, d * 2), (0, 0, 0, 0))
    ImageDraw.Draw(ringim).ellipse((bw, bw, d * 2 - bw, d * 2 - bw),
                                   outline=ring + (255,), width=bw * 2)
    out.alpha_composite(ringim.resize((d, d), Image.LANCZOS))
    return out


def fit_font(text, max_w, size, path=brand.FONT_HEAVY, floor=60, step=8):
    """Shrink from size until text fits max_w."""
    while size > floor:
        f = ImageFont.truetype(path, size)
        if f.getlength(text) <= max_w:
            return f
        size -= step
    return ImageFont.truetype(path, size)


def stroke_text(d, xy, text, fnt, fill, stroke=28, anchor=None):
    """Ink-stroked display text (thumbnail hooks)."""
    d.text(xy, text, font=fnt, fill=fill, stroke_width=stroke,
           stroke_fill=brand.INK, anchor=anchor)


def two_tone(d, y, left, right, fnt, right_fill, width, stroke=28):
    """One centered line across `width`: left part white + right part colored."""
    total = fnt.getlength(left + right)
    x0 = (width - total) / 2
    stroke_text(d, (x0, y), left, fnt, (255, 255, 255), stroke)
    stroke_text(d, (x0 + fnt.getlength(left), y), right, fnt, right_fill, stroke)
