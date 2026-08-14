"""Original music beds and sound effects via the ElevenLabs API.

Why ElevenLabs: the channel already holds a Creator-plan key
(ELEVENLABS_API_KEY in env), paid plans include a commercial license
covering YouTube monetization, and the training data is licensed
(Merlin/Kobalt deals) — the cleanest legal posture of the current
AI-music field. Decision doc: docs/musicgen.md.

One key, two endpoints:
  music  POST /v1/music             prompt -> song/bed (mp3), 3-600 s,
                                    force_instrumental for beds.
  sfx    POST /v1/sound-generation  text -> effect (mp3), 0.5-22 s.

Non-mp3 --out is converted with ffmpeg (vidkit.ff). Stdlib only.

CLI:
  python3 -m vidkit.musicgen music "quiet dramatic beat ..." --seconds 30 --out bed.wav
  python3 -m vidkit.musicgen sfx "CB radio squelch click" --seconds 1.5 --out squelch.wav
  python3 -m vidkit.musicgen "prompt" --seconds 30 --out bed.wav   # shorthand for music
"""
import argparse
import json
import os
import sys
import tempfile
import urllib.error
import urllib.request

if __package__:
    from . import ff
else:  # run directly as a script: python3 vidkit/musicgen.py ...
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from vidkit import ff

API = "https://api.elevenlabs.io"
KEY_ENV = "ELEVENLABS_API_KEY"

MUSIC_MIN_S, MUSIC_MAX_S = 3, 600      # music_length_ms: 3000-600000
SFX_MIN_S, SFX_MAX_S = 0.5, 22         # duration_seconds per API docs


def _key(key=None):
    key = key or os.environ.get(KEY_ENV)
    if not key:
        sys.exit("no %s in env. Get one at elevenlabs.io -> Profile -> "
                 "API Key (commercial use needs a paid plan; free tier is "
                 "attribution-only). Then: export %s=..." % (KEY_ENV, KEY_ENV))
    return key


def _post_audio(path, payload, key, timeout=300):
    """POST JSON, return response audio bytes. Raises SystemExit on HTTP errors."""
    req = urllib.request.Request(
        API + path, data=json.dumps(payload).encode(),
        headers={"xi-api-key": _key(key), "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")[:500]
        sys.exit("ElevenLabs %s -> HTTP %d: %s" % (path, e.code, body))
    except urllib.error.URLError as e:
        sys.exit("ElevenLabs %s -> network error: %s" % (path, e.reason))


def _write_audio(mp3_bytes, out):
    """Write mp3 bytes to out, converting via ffmpeg if out isn't .mp3."""
    if out.lower().endswith(".mp3"):
        with open(out, "wb") as f:
            f.write(mp3_bytes)
        return out
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as t:
        t.write(mp3_bytes)
        tmp = t.name
    try:
        ff.run([ff.FFMPEG, "-y", "-v", "error", "-i", tmp,
                "-ar", "48000", out])
    finally:
        os.unlink(tmp)
    return out


def music(prompt, out, seconds=30, seed=None, instrumental=True, key=None):
    """Generate a music track from a text prompt. Returns out path."""
    if not MUSIC_MIN_S <= seconds <= MUSIC_MAX_S:
        sys.exit("music --seconds must be %d-%d" % (MUSIC_MIN_S, MUSIC_MAX_S))
    payload = {"prompt": prompt, "music_length_ms": int(seconds * 1000),
               "model_id": "music_v1", "force_instrumental": instrumental}
    if seed is not None:
        payload["seed"] = seed
    return _write_audio(_post_audio("/v1/music", payload, key), out)


def sfx(text, out, seconds=None, prompt_influence=0.3, key=None):
    """Generate one sound effect. seconds None = model picks (billed flat)."""
    payload = {"text": text, "prompt_influence": prompt_influence}
    if seconds is not None:
        if not SFX_MIN_S <= seconds <= SFX_MAX_S:
            sys.exit("sfx --seconds must be %g-%g" % (SFX_MIN_S, SFX_MAX_S))
        payload["duration_seconds"] = seconds
    return _write_audio(_post_audio("/v1/sound-generation", payload, key), out)


def _build_parser(prog):
    p = argparse.ArgumentParser(prog=prog, description=__doc__.splitlines()[0])
    p.add_argument("prompt", help="music prompt, or effect description for sfx")
    p.add_argument("--seconds", type=float, default=None,
                   help="music: default 30 (3-600); sfx: omit to auto-duration")
    p.add_argument("--out", required=True, help=".mp3 or any ffmpeg target (.wav ...)")
    p.add_argument("--seed", type=int, default=None, help="music only")
    p.add_argument("--vocals", action="store_true",
                   help="music only: allow vocals (default forces instrumental)")
    p.add_argument("--prompt-influence", type=float, default=0.3, help="sfx only")
    return p


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    mode = "music"
    if argv and argv[0] in ("music", "sfx"):
        mode = argv.pop(0)
    args = _build_parser("musicgen " + mode).parse_args(argv)
    if mode == "music":
        out = music(args.prompt, args.out, seconds=args.seconds or 30,
                    seed=args.seed, instrumental=not args.vocals)
    else:
        out = sfx(args.prompt, args.out, seconds=args.seconds,
                  prompt_influence=args.prompt_influence)
    print("%s (%.1fs, %s)" % (out, ff.duration(out), mode))


if __name__ == "__main__":
    main()
