"""ElevenLabs text-to-speech for vidkit.

CLI:
    python3 -m vidkit.voice.tts "Breaker breaker, traffic is light." \
        --voice nPczCjzI2devNBz1zQrb --out line.wav

ELEVENLABS_API_KEY must be in the environment. Commercial use is covered
by any paid plan; keep a provenance note (text, voice, model, date) next
to generated files used in published work.
"""
import argparse
import datetime
import json
import os
import subprocess
import sys
import urllib.request

API = "https://api.elevenlabs.io"
DEFAULT_MODEL = "eleven_multilingual_v2"


def _key():
    k = os.environ.get("ELEVENLABS_API_KEY")
    if not k:
        sys.exit("ELEVENLABS_API_KEY not set")
    return k


def tts(text, voice, out, model=DEFAULT_MODEL, stability=0.45,
        similarity=0.75, style=0.35):
    """Render text -> wav (pcm_44100). Lower stability = more character."""
    body = json.dumps({
        "text": text,
        "model_id": model,
        "voice_settings": {"stability": stability,
                           "similarity_boost": similarity,
                           "style": style},
    }).encode()
    req = urllib.request.Request(
        "%s/v1/text-to-speech/%s?output_format=mp3_44100_128" % (API, voice),
        data=body, headers={"xi-api-key": _key(),
                            "Content-Type": "application/json"})
    with urllib.request.urlopen(req) as r:
        mp3 = r.read()
    # pcm output formats are gated above Creator tier; decode mp3 to wav
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "mp3",
                    "-i", "pipe:0", "-ar", "48000", "-ac", "1",
                    out], input=mp3, check=True)
    return out


def provenance(path, text, voice, model):
    note = ("%s\nvoice: %s\nmodel: %s\ndate: %s\n---\n%s\n"
            % (os.path.basename(path), voice, model,
               datetime.date.today().isoformat(), text))
    with open(path + ".PROVENANCE.txt", "w") as f:
        f.write(note)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("text")
    p.add_argument("--voice", required=True, help="voice id")
    p.add_argument("--out", required=True)
    p.add_argument("--model", default=DEFAULT_MODEL)
    p.add_argument("--stability", type=float, default=0.45)
    a = p.parse_args()
    tts(a.text, a.voice, a.out, model=a.model, stability=a.stability)
    provenance(a.out, a.text, a.voice, a.model)
    print("wrote", a.out)


if __name__ == "__main__":
    main()
