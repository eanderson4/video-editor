"""Whisper word-timing utilities.

Riverside -CFR tracks are session-time aligned (t=0 = session 0), but each
whisper run transcribed a trimmed excerpt, so every whisper JSON carries a
fixed offset back to session time. Fixes are word-level corrections keyed
(speaker, session_start) because whisper timing is stable run-to-run.
"""
import json
import os


def load_words(whisper_dir, tracks, fixes=None, subs=()):
    """Flat sorted word list [(session_start, session_end, token, speaker)].

    tracks: [(json_stem, session_offset_seconds)]; speaker = stem before '-'.
    fixes:  {(speaker, round(session_start, 2)): (wrong_token, replacement)}
            with replacement '' meaning drop the token.
    subs:   [(find, replace)] applied to every token (e.g. spelling unifies).
    """
    fixes = fixes or {}
    words = []
    for stem, off in tracks:
        p = os.path.join(whisper_dir, stem + ".json")
        if not os.path.exists(p):
            continue
        spk = stem.split("-")[0]
        d = json.load(open(p))
        for seg in d["segments"]:
            for w in seg.get("words", []):
                t = w["word"].strip()
                key = (spk, round(w["start"] + off, 2))
                if key in fixes and fixes[key][0] == t:
                    t = fixes[key][1]
                for a, b in subs:
                    t = t.replace(a, b)
                if not t:
                    continue
                words.append((w["start"] + off, w["end"] + off, t, spk))
    words.sort()
    return words


def load_words_from_srt(path, speaker, offset=0.0, subs=()):
    """Word list [(session_start, session_end, token, speaker)] from an SRT
    (e.g. Riverside's <name>.srt or a whisper -osrt slice of a -CFR track).

    SRT cues have no word timing, so words are interpolated linearly across
    their cue — keep cues short (whisper slices, not paragraph SRTs) or
    captions will smear within a cue. offset shifts cue times into session
    time (slice start). Word-level `fixes` are impractical here (timings are
    synthetic); use subs for token corrections."""
    import re
    words = []
    with open(path) as f:
        text = f.read()
    for block in re.split(r"\n\s*\n", text.strip()):
        lines = block.strip().splitlines()
        if len(lines) < 2:
            continue
        tl = next((l for l in lines if "-->" in l), None)
        if tl is None:
            continue
        a, b = [_hms(t) for t in re.split(r"\s*-->\s*", tl.strip())[:2]]
        toks = " ".join(l for l in lines[lines.index(tl) + 1:]).split()
        n = len(toks)
        for i, t in enumerate(toks):
            for x, y in subs:
                t = t.replace(x, y)
            if not t:
                continue
            words.append((offset + a + (b - a) * i / n,
                          offset + a + (b - a) * (i + 1) / n, t, speaker))
    words.sort()
    return words


def _hms(t):
    h, m, rest = t.replace(",", ".").split(":")
    return int(h) * 3600 + int(m) * 60 + float(rest)


def chunk_words(ws, max_words=4, max_gap=0.8):
    """Group [(start, end, token)] into caption chunks: break on sentence
    punctuation, max_words, or a speech gap > max_gap seconds.
    Returns [(start, end, [tokens])]."""
    chunks, cur = [], []
    for i, (s, e, t) in enumerate(ws):
        cur.append((s, e, t))
        gap_next = ws[i + 1][0] - e if i + 1 < len(ws) else 99
        if t[-1] in ".?!" or len(cur) == max_words or gap_next > max_gap:
            chunks.append((cur[0][0], cur[-1][1], [c[2] for c in cur]))
            cur = []
    if cur:
        chunks.append((cur[0][0], cur[-1][1], [c[2] for c in cur]))
    return chunks
