"""Vertical shorts engine: 1080x1920 speaker-cut shorts from session-aligned
horizontal tracks, with PIL caption/chip/hook overlays.

A short's spec (all times are SESSION seconds):
    {
      "hook":    [[(text, color), ...], ...]        # lines of the hook card
      "preview": [(s, e, speaker, crop_cx), ...]    # optional cold-open span
      "spans":   [[(s, e, speaker, crop_cx), ...], ...]
    }
Optional follow-cam: xexpr[(speaker, round(s, 2))] = ffmpeg crop-x expression
in shot-relative t (see vidkit.facetrack.crop_x_expr); it overrides crop_cx.

Render is segmented two-pass BY DESIGN — do not collapse to one pass:
a preview cold-open makes ffmpeg read the same input at out-of-order times,
which silently truncates on ffmpeg 8 and deadlocks ffmpeg 7. So pass 1
renders each span alone (reads sequential within a span) to near-lossless
.mkv, pass 2 concats + overlays + loudnorm. Overlays are applied in chunks
of OVL_CHUNK (>40 inputs gets SIGKILLed); still-PNG inputs use
-loop 1 -framerate 2 (at 24 ffmpeg eagerly buffers duration*24 frames per
input and OOMs). Always verify output duration after a build.
"""
import os
import shutil
import sys

from PIL import Image

from . import brand, draw, ff

# layout (1080x1920)
CAP_SIZE = 60
CAP_STROKE = 9
CAP_TOP = 130          # no-banner mode only: captions hang near the top;
                       # the Shorts UI owns the bottom, so nothing goes there
CAP_MAXW = 850         # max caption width before wrapping
CHIP_TOP = 140
HOOK_TOP = 330
CROP_W = 608           # 1920x1080 -> 608x1080 crop -> scale to 1080x1920
# top brand band (hero texture): speaker chip centered in the top 90px,
# captions INSIDE the band, bottom-aligned just above the colored strip
BAND_H = 305
BAND_CHIP_H = 90
BAND_CAP_BOTTOM = 291

OVL_CHUNK = 32

DEFAULT_SPEAKERS = {
    "eric": dict(chip="MATH", color=brand.MATH_BLUE, tint=brand.LAVENDER),
    "tbone": dict(chip="VIBES", color=brand.VIBES_ORANGE, tint=brand.PEACH),
}


def all_spans(spec):
    """Concat order: optional preview span first, then content spans."""
    return ([spec["preview"]] if "preview" in spec else []) + spec["spans"]


class ShortsBuilder:
    def __init__(self, sources, words, work_dir, xexpr=None,
                 speakers=None, from_chunks=None, use_banner=False,
                 shift_y=None, speed=1.0):
        """sources: {speaker: video_path} — insertion order fixes ffmpeg
        input indexes. words: vidkit.captions.load_words() output.
        work_dir: overlay PNGs, span segment cache, test renders.
        use_banner: render the hero-texture top brand band (speaker chip
        inside it); captions float above the Shorts UI zone either way.
        shift_y: {speaker: source_px} — crop the source from y_offset down
        and scale back WITHOUT zooming (same scale factor as unshifted
        shots); the output is shorter by the shifted amount and the freed
        bottom strip is padded with the speaker's brand tint (it sits in
        the Shorts UI zone, so keep it free of text/captions).
        speed: final-pass tempo factor (e.g. 1.1 = 10% faster); applied as
        setpts/atempo in a dedicated single-input pass after the overlays."""
        self.sources = sources
        self.order = list(sources)
        self.words = words
        self.work_dir = work_dir
        self.xexpr = xexpr or {}
        self.speakers = speakers or DEFAULT_SPEAKERS
        self.use_banner = use_banner
        self.shift_y = shift_y or {}
        self.speed = speed
        self.ovl_dir = os.path.join(work_dir, "overlays")
        self.seg_dir = os.path.join(work_dir, "segs")

    # ------------------------------------------------------------ overlays
    def build_events(self, name, spec, framed=False):
        """Returns (total_dur, events). event = (start, end, png, W, H, y)."""
        odir = os.path.join(self.ovl_dir, name)
        shutil.rmtree(odir, ignore_errors=True)
        os.makedirs(odir)
        events = []
        spans = all_spans(spec)
        segs, out_off = [], 0.0
        for span in spans:
            segs.append((span[0][0], span[-1][1], out_off))
            out_off += span[-1][1] - span[0][0]
        total = out_off
        pv_len = (spans[0][-1][1] - spans[0][0][0]) if "preview" in spec else 0.0

        def to_out(t, si):
            # span-indexed: a preview span's time range can overlap a content
            # span's, so first-match lookup would be ambiguous
            ss, se, oo = segs[si]
            if not (ss - 1e-6 <= t <= se + 1e-6):
                raise ValueError("time %s outside span %d" % (t, si))
            return oo + (t - ss)

        # border frames first so every other overlay draws on top of them
        if framed:
            border = {}
            for spk, style in self.speakers.items():
                bp = os.path.join(odir, "frame-%s.png" % spk)
                draw.render_frame(style["color"], bp)
                border[spk] = bp
            for si, span in enumerate(spans):
                for (s, e, spk, _cx) in span:
                    events.append((to_out(s, si), to_out(e, si),
                                   border[spk], 1080, 1920, 0))

        # hook card: whole preview + usual 2.4s of content open
        hp = os.path.join(odir, "hook.png")
        w, h = draw.render_hook(spec["hook"], hp)
        events.append((0.0, pv_len + 2.4, hp, w, h, HOOK_TOP))

        # chips (one png per speaker, reused; separate -i per event is fine)
        chip = {}
        for spk, style in self.speakers.items():
            cp = os.path.join(odir, "chip-%s.png" % spk)
            cw, ch = draw.render_chip(style["chip"], style["color"], cp)
            chip[spk] = (cp, cw, ch)

        # top brand band (hero-texture slice, up from t=0; chip sits inside it)
        if self.use_banner:
            band = {}
            for spk, style in self.speakers.items():
                bp = os.path.join(odir, "band-%s.png" % spk)
                bw, bh = draw.render_band(style["color"], style["chip"], bp,
                                          h=BAND_H)
                band[spk] = (bp, bw, bh)
            for si, span in enumerate(spans):
                for (s, e, spk, _cx) in span:
                    os_, oe = to_out(s, si), to_out(e, si)
                    bp, bw, bh = band[spk]
                    events.append((os_, oe, bp, bw, bh, 0))

        ci = 0
        for si, span in enumerate(spans):
            for (s, e, spk, _cx) in span:
                os_, oe = to_out(s, si), to_out(e, si)
                cp, cw, ch = chip[spk]
                # centered in the chip zone, nudged 20px off the top edge
                chip_y = ((BAND_CHIP_H - ch) // 2 + 20 if self.use_banner
                          else CHIP_TOP)
                events.append((os_, oe, cp, cw, ch, chip_y))
                ws = [(a, b, t) for (a, b, t, sp) in self.words
                      if sp == spk and s <= (a + b) / 2 < e]
                accent = self.speakers[spk]["color"]
                chunks = self._chunk(ws)
                prev_end = os_
                for i, (cs, ce, texts) in enumerate(chunks):
                    start = max(to_out(max(cs, s), si) - 0.05, os_, prev_end)
                    nxt = (to_out(max(chunks[i + 1][0], s), si) - 0.05
                           if i + 1 < len(chunks) else oe)
                    end = min(nxt, to_out(min(ce, e), si) + 0.9, oe)
                    prev_end = max(prev_end, end)
                    if end <= start:
                        continue
                    pp = os.path.join(odir, "cap%03d.png" % ci)
                    ci += 1
                    if self.use_banner:
                        # captions sit on the light band texture: dark ink
                        # text, white halo, speaker-colored accent word
                        w, h = draw.render_caption(
                            texts, accent, pp, CAP_SIZE, CAP_STROKE, CAP_MAXW,
                            base=brand.INK, stroke_fill=draw.WHITE)
                        cap_y = BAND_CAP_BOTTOM - h
                    else:
                        w, h = draw.render_caption(texts, accent, pp, CAP_SIZE,
                                                   CAP_STROKE, CAP_MAXW)
                        cap_y = CAP_TOP
                    events.append((start, end, pp, w, h, cap_y))

        # 3-frame white flash straddling the preview->content cut (added last
        # so it covers chips/captions too)
        if pv_len:
            fp = os.path.join(odir, "flash.png")
            Image.new("RGBA", (1080, 1920), draw.WHITE).save(fp)
            events.append((pv_len - 1.0 / 24, pv_len + 2.0 / 24, fp, 1080, 1920, 0))
        return total, events

    def _chunk(self, ws):
        from . import captions
        return captions.chunk_words(ws)

    # ------------------------------------------------------------ render
    def render_segment(self, name, si, span):
        """Pass 1: one span alone -> near-lossless .mkv (cached by filename)."""
        os.makedirs(self.seg_dir, exist_ok=True)
        seg = os.path.join(self.seg_dir, "%s-s%d.mkv" % (name, si))
        if os.path.exists(seg):
            return seg
        src_w = ff.video_size(next(iter(self.sources.values())))[0]
        xmax = src_w - CROP_W
        span_start, span_end = span[0][0], span[-1][1]
        fc, vlabels = [], []
        for n, (s, e, spk, cx) in enumerate(span):
            src = self.order.index(spk)
            sy = self.shift_y.get(spk, 0)
            ch = 1080 - sy
            # same scale factor as unshifted shots (no zoom); output height
            # shrinks and the remainder is padded black at the bottom,
            # which the banner hides
            oh = round(ch * 1920 / 1080) & ~1
            xe = self.xexpr.get((spk, round(s, 2)))
            if xe:
                x = "x=%s" % ff.esc_expr("clip(%s,0,%d)" % (xe, xmax))
            else:
                x = str(max(0, min(xmax, int(cx) - CROP_W // 2)))
            chain = ("[%d:v]trim=%.3f:%.3f,setpts=PTS-STARTPTS,"
                     "crop=%d:%d:%s:y=%d,scale=1080:%d:flags=lanczos,setsar=1"
                     % (src, s, e, CROP_W, ch, x, sy, oh))
            if oh != 1920:
                # the shift exposes a strip at the bottom — fill it with the
                # speaker's brand tint (sits under the Shorts UI zone)
                tint = self.speakers[spk].get("tint", (0, 0, 0))
                chain += ",pad=1080:1920:0:0:color=0x%02X%02X%02X" % tint
            fc.append(chain + "[v%d]" % n)
            vlabels.append("[v%d]" % n)
        if len(vlabels) > 1:
            fc.append("%sconcat=n=%d:v=1:a=0[vc]" % ("".join(vlabels), len(vlabels)))
        else:
            fc.append("%snull[vc]" % vlabels[0])
        fc.append("[vc]null[vout]")
        alabels = []
        for i, spk in enumerate(self.order):
            fc.append("[%d:a]atrim=%.3f:%.3f,asetpts=PTS-STARTPTS[a%d]"
                      % (i, span_start, span_end, i))
            alabels.append("[a%d]" % i)
        fc.append("%samix=inputs=%d:normalize=0,aresample=48000[aout]"
                  % ("".join(alabels), len(alabels)))
        tmp = os.path.join(self.seg_dir, "tmp-%s-s%d.mkv" % (name, si))
        cmd = [ff.FFMPEG, "-y", "-v", "error"]
        for spk in self.order:
            cmd += ["-i", self.sources[spk]]
        cmd += ["-filter_complex", ";".join(fc),
                "-map", "[vout]", "-map", "[aout]",
                "-c:v", "libx264", "-preset", "ultrafast", "-crf", "8",
                "-pix_fmt", "yuv420p", "-r", "24",
                "-c:a", "pcm_s16le", "-ar", "48000",
                "-t", "%.3f" % (span_end - span_start), tmp]
        print("  seg %d (%.1fs)" % (si, span_end - span_start))
        ff.run(cmd)
        os.replace(tmp, seg)
        return seg

    def render(self, name, spec, outdir, preset="medium", framed=False):
        """Pass 2: concat span segments, chunked overlays, loudnorm, encode.
        spec["sfx"]: optional [(t, path, volume, duration, skip)] — stinger
        slice starting skip seconds into the file, mixed at t = final-output
        seconds (post-speed)."""
        sfx = spec.get("sfx", [])
        total, events = self.build_events(name, spec, framed)
        segs = [self.render_segment(name, si, span)
                for si, span in enumerate(all_spans(spec))]

        out = os.path.join(outdir, name + ".mp4")
        chunks = ([events[i:i + OVL_CHUNK]
                   for i in range(0, len(events), OVL_CHUNK)] or [[]])
        print("rendering %s (%.1fs, %d overlays, %d passes) -> %s"
              % (name, total, len(events), len(chunks), out))
        prev = None
        for k, chunk in enumerate(chunks):
            last = k == len(chunks) - 1
            # when speeding, even the last overlay pass is an intermediate:
            # setpts after a many-input overlay chain silently no-ops on
            # ffmpeg 7, so retiming happens in a dedicated single-input pass
            encode = last and self.speed == 1.0 and not sfx
            inputs = list(segs) if k == 0 else [prev]
            nseg = len(inputs)
            fc = []
            if nseg > 1:
                pairs = "".join("[%d:v][%d:a]" % (i, i) for i in range(nseg))
                fc.append("%sconcat=n=%d:v=1:a=1[base][ac]" % (pairs, nseg))
                aout = "[ac]"
            else:
                fc.append("[0:v]null[base]")
                aout = "[0:a]"

            cur = "[base]"
            for i, (st, en, png, w, h, y) in enumerate(chunk):
                idx = len(inputs)
                inputs.append(png)
                x = (1080 - w) // 2
                nxt = "[o%d]" % i
                fc.append("%s[%d:v]overlay=x=%d:y=%d:"
                          "enable='between(t,%.3f,%.3f)'%s"
                          % (cur, idx, x, y, st, en, nxt))
                cur = nxt
            fc.append("%snull[vout]" % cur)
            if encode:
                fc.append("%saresample=48000,loudnorm=I=-14:TP=-1.5:LRA=11,"
                          "aresample=48000[aout]" % aout)
            else:
                fc.append("%sanull[aout]" % aout)

            dst = out if encode else os.path.join(self.seg_dir,
                                                  "tmp-%s-p%d.mkv" % (name, k))
            cmd = [ff.FFMPEG, "-y", "-v", "error"]
            for i, p in enumerate(inputs):
                if i >= nseg:
                    # static overlays: low fps keeps ffmpeg's eager image-loop
                    # decode from buffering duration*24 frames per input (OOM)
                    cmd += ["-loop", "1", "-framerate", "2"]
                cmd += ["-i", p]
            cmd += ["-filter_complex", ";".join(fc),
                    "-map", "[vout]", "-map", "[aout]",
                    "-pix_fmt", "yuv420p", "-r", "24", "-t", "%.3f" % total]
            if encode:
                cmd += ["-c:v", "libx264", "-preset", preset, "-crf", "18",
                        "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
                        "-movflags", "+faststart"]
            else:
                cmd += ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "8",
                        "-c:a", "pcm_s16le", "-ar", "48000"]
            cmd += [dst]
            print("  pass %d/%d (%d overlays)" % (k + 1, len(chunks), len(chunk)))
            ff.run(cmd)
            if prev and prev != out:
                os.remove(prev)
            prev = dst
        if self.speed != 1.0 or sfx:
            # final pass: retime (if speeding) + sfx stingers + delivery
            # encode. Single input for the video: setpts after a many-input
            # overlay chain silently no-ops on ffmpeg 7.
            print("  speed pass (%gx)" % self.speed)
            vc = ("[0:v]setpts=PTS/%g[vout]" % self.speed
                  if self.speed != 1.0 else "[0:v]null[vout]")
            ac = ("[0:a]aresample=48000,atempo=%g[am]" % self.speed
                  if self.speed != 1.0 else "[0:a]aresample=48000[am]")
            inputs = [prev]
            if sfx:
                mix_in = "[am]"
                for i, (t, path, vol, dur, skip) in enumerate(sfx):
                    inputs.append(path)
                    ms = round(t * 1000)
                    ac += (";[%d:a]atrim=%.3f:%.3f,asetpts=PTS-STARTPTS,"
                           "volume=%.2f,afade=t=in:st=0:d=0.15,"
                           "afade=t=out:st=%.3f:d=1.3,adelay=%d|%d[sfx%d]"
                           % (i + 1, skip, skip + dur, vol,
                              max(0.0, dur - 1.3), ms, ms, i))
                    mix_in += "[sfx%d]" % i
                ac += (";%samix=inputs=%d:duration=first:normalize=0:"
                       "dropout_transition=0[amx]"
                       % (mix_in, len(sfx) + 1))
                am_out = "[amx]"
            else:
                am_out = "[am]"
            fc = ("%s;%s;%sloudnorm=I=-14:TP=-1.5:LRA=11,"
                  "aresample=48000[aout]" % (vc, ac, am_out))
            cmd = [ff.FFMPEG, "-y", "-v", "error"]
            for p in inputs:
                cmd += ["-i", p]
            cmd += ["-filter_complex", fc,
                    "-map", "[vout]", "-map", "[aout]",
                    "-pix_fmt", "yuv420p", "-r", "24", "-t", "%.3f" % total,
                    "-c:v", "libx264", "-preset", preset, "-crf", "18",
                    "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
                    "-movflags", "+faststart", out]
            ff.run(cmd)
            os.remove(prev)
        got = ff.duration(out)
        expected = total / self.speed
        if abs(got - expected) > 0.5:
            raise RuntimeError("%s: rendered %.2fs, expected %.2fs — "
                               "truncated render?" % (out, got, expected))
        return out

    def run_cli(self, shorts, final_dir, argv=None):
        """CLI: build.py [--test] [--framed] [names...]
        --test -> preset veryfast, render into work_dir/test."""
        args = sys.argv[1:] if argv is None else argv
        test = "--test" in args
        framed = "--framed" in args
        names = [a for a in args if not a.startswith("--")] or list(shorts)
        outdir = os.path.join(self.work_dir, "test") if test else final_dir
        if framed:
            outdir = os.path.join(outdir, "framed")
        os.makedirs(outdir, exist_ok=True)
        preset = "veryfast" if test else "medium"
        for nm in names:
            self.render(nm, shorts[nm], outdir, preset, framed)
