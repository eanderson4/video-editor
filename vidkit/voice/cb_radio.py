"""CB radio voice treatment (trucker-band post effect).

Record the VO clean and dry; this module applies the CB color at render
time so the raw takes stay reusable. The chain, on ffmpeg filters only:

  highpass 300 Hz + lowpass 3 kHz   the CB band (narrow, no air, no body)
  presence bump ~1.4 kHz            keeps consonants intelligible in-band
  acompressor (fast, hot)           the flat, always-on-radio level
  asoftclip (tanh, light drive)     mic grit / saturation
  pink-noise static bed (optional)  band-limited hiss under the voice
  squelch clicks (optional)         a recorded squelch tail prepended /
                                    appended to sell the key-up/key-down

CLI:
  python3 -m vidkit.voice.cb_radio in.wav out.wav [--squelch sq.wav]
      [--no-squelch-start] [--no-squelch-end] [--static 0.03] [--drive 2]
"""
import argparse
import os
import sys

if __package__:
    from .. import ff
else:  # run directly as a script: python3 vidkit/voice/cb_radio.py ...
    sys.path.insert(0, os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__)))))
    from vidkit import ff


def chain(static=0.0, drive=2.0, label_in="0:a", label_out="cbout"):
    """Filtergraph snippet for the CB voice band. static=0 skips the noise
    bed. Consumes [label_in], produces [label_out] (mono 48k)."""
    voice = (
        "[%s]highpass=f=300,lowpass=f=3000,"
        "equalizer=f=1400:t=q:w=1.2:g=2.5,"
        "acompressor=threshold=-18dB:ratio=6:attack=4:release=90:makeup=5,"
        "asoftclip=type=tanh:output=0.9:threshold=0.7:param=%g,"
        "aformat=sample_rates=48000:channel_layouts=mono" % (label_in, drive)
    )
    if static > 0:
        return (voice + "[cbv];"
                "anoisesrc=color=pink:amplitude=%g:sample_rate=48000[noise];"
                "[noise]highpass=f=400,lowpass=f=2800,apad[noisebed];"
                "[cbv][noisebed]amix=inputs=2:duration=first:normalize=0,"
                "atrim=0,asetpts=PTS-STARTPTS[%s]" % (static, label_out))
    return voice + "[%s]" % label_out


def render(src, dst, squelch=None, squelch_start=True, squelch_end=True,
           static=0.03, drive=2.0, squelch_trim=(0.05, 0.45)):
    """Render src through the CB chain to dst (wav 48k mono).

    squelch: path to a squelch-click wav; the first squelch_trim=(start,end)
    window of it is prepended (key-up) and/or appended (key-down).
    """
    inputs = [src]
    graph = chain(static=static, drive=drive, label_in="0:a", label_out="cb")
    last = "[cb]"
    if squelch and (squelch_start or squelch_end):
        inputs.append(squelch)
        s0, s1 = squelch_trim
        parts = []
        n = 1
        if squelch_start:
            graph += (";[1:a]atrim=%g:%g,asetpts=PTS-STARTPTS,"
                      "aformat=sample_rates=48000:channel_layouts=mono[sq0]"
                      % (s0, s1))
            parts.append("[sq0]")
            n += 1
        parts.append("[cb]")
        if squelch_end:
            graph += (";[1:a]atrim=%g:%g,asetpts=PTS-STARTPTS,"
                      "aformat=sample_rates=48000:channel_layouts=mono[sq1]"
                      % (s0, s1))
            parts.append("[sq1]")
            n += 1
        graph += ";%sconcat=n=%d:v=0:a=1[out]" % ("".join(parts), n)
        last = "[out]"
    # ceiling: compressor makeup + static bed + squelch can exceed full scale
    graph += ";%salimiter=limit=0.89:level=false[final]" % last
    last = "[final]"
    cmd = [ff.FFMPEG, "-y", "-v", "error"]
    for i in inputs:
        cmd += ["-i", i]
    cmd += ["-filter_complex", graph, "-map", last,
            "-ar", "48000", "-ac", "1", dst]
    ff.run(cmd)
    return dst


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("src")
    p.add_argument("dst")
    p.add_argument("--squelch")
    p.add_argument("--no-squelch-start", action="store_true")
    p.add_argument("--no-squelch-end", action="store_true")
    p.add_argument("--static", type=float, default=0.03)
    p.add_argument("--drive", type=float, default=2.0)
    a = p.parse_args(argv)
    render(a.src, a.dst, squelch=a.squelch,
           squelch_start=not a.no_squelch_start,
           squelch_end=not a.no_squelch_end,
           static=a.static, drive=a.drive)
    print("wrote", a.dst)


if __name__ == "__main__":
    main()
