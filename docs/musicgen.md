# Music & sound generation for shorts (decision, 2026-08-14)

Need: original, license-safe music beds + SFX for a monetized YouTube
channel (MATH vs VIBES), scriptable from this toolchain, minimal new spend.

## Recommendation: ElevenLabs (already keyed)

`ELEVENLABS_API_KEY` is in the environment on an **active Creator plan**
(300k credits/mo, ~0 used — checked via `/v1/user/subscription` on
2026-08-14). Paid plans include the commercial license, so music and SFX
generated with this key are cleared for monetized YouTube. ElevenLabs
trained its music model on licensed data (deals with Merlin and Kobalt),
which is the strongest legal posture in the field — Suno and Udio have
been sued by the major labels over training data.

- **Music bed**: `POST /v1/music` — prompt, `music_length_ms` (3–600 s),
  `force_instrumental`, `seed`. Returns mp3.
- **SFX**: `POST /v1/sound-generation` — text, `duration_seconds`
  (0.5–22 s, or auto), `prompt_influence`. Returns mp3.
  Billed 20 credits/s with set duration (100 credits flat on auto).
- **Cost**: zero marginal — covered by the existing Creator subscription.
- Scaffold: `vidkit/musicgen.py` (`music` + `sfx` subcommands; shorthand
  `python3 -m vidkit.musicgen "prompt" --seconds 30 --out bed.wav`).

## Alternatives surveyed (2026-08-14)

| Provider | Scriptable | Commercial use for monetized YT | Cost | Verdict |
|---|---|---|---|---|
| **ElevenLabs Music + SFX** | Official REST API | Yes on any paid plan; licensed training data (Merlin/Kobalt) | $0 extra (existing Creator plan) | **Chosen** |
| Suno v5.5 | No sanctioned public API; third-party wrappers violate ToS | Paid plans ($10+/mo) grant commercial rights; label lawsuits over training data ongoing | New subscription | Rejected: web-UI only, legally clouded |
| Udio | Restricted API, paid tiers | Commercial rights at $30/mo Pro; post-lawsuit pivot to licensed platform, downloads restricted at times | New subscription | Rejected: worst scriptability + shifting terms |
| MiniMax Music 3.0 | Hosted API (`POST /v1/music_generation`, `Music-3.0` $0.15/song, `Music-3.0-free` 3 RPM) | Murky. "Open weights" claims conflict (pexo.ai says open-weight; minimax docs show no official weights as of Aug 2026); the MiniMax community license for open weights excludes US/EU/UK/KR from local deployment and wasn't final. Hosted API commercial terms unclear | Cheap but new account | Rejected: licensing ambiguity is disqualifying for a monetized channel |
| Google Lyria 3 Pro (Gemini API) | Yes, and `GEMINI_API_KEY` exists in env | Allowed with SynthID watermarking; terms less music-specific than ElevenLabs | ~$0.08/song | Viable fallback #2 if ElevenLabs quality disappoints |
| Video-gen audio (Hailuo/MiniMax H3 etc.) | API | Generates audio only as part of video clips; same MiniMax license murk | Per-clip | Not fit for purpose (need standalone stems) |

## Licensing bottom line

- Generate everything through the **paid Creator-plan ElevenLabs key**:
  output is commercially licensed, including YouTube monetization. Do not
  use the ElevenLabs free tier (attribution-only, no commercial rights).
- Keep prompts generic (no artist names, no "in the style of X") — Eleven
  Music's terms prohibit artist-name prompts and it's good hygiene anyway.
- Keep the generated files in the content repo as the provenance record
  (prompt + date + provider), e.g. alongside the short's build script.

## SFX shopping list for the traffic short

One-liners ready for `vidkit.musicgen sfx`:
- `diesel truck air horn, two short blasts, doppler pass`
- `CB radio squelch click and static burst`
- `city traffic ambience, distant engines and horns, light rain`
- `truck engine downshift, jake brake rumble`
