# Voice treatments (`vidkit.voice`)

Post effects for recorded VO. Record clean/dry; apply color at render time
so raw takes stay reusable.

## `cb_radio` — trucker CB-band voice

```python
from vidkit.voice import cb_radio
cb_radio.render("vo-dry.wav", "vo-cb.wav", squelch="cb-squelch.wav")
```

CLI: `python3 -m vidkit.voice.cb_radio in.wav out.wav [--squelch sq.wav]
[--no-squelch-start] [--no-squelch-end] [--static 0.03] [--drive 2]`

Chain (all ffmpeg filters): bandpass 300 Hz–3 kHz (the CB band), a small
1.4 kHz presence bump for consonant intelligibility, fast hot compression,
light tanh soft-clip grit, an optional band-limited pink-noise static bed,
optional squelch clicks prepended/appended for key-up/key-down, and a final
limiter at ≈ −1 dBFS (makeup gain + static + squelch can otherwise clip).
Output: 48 kHz mono wav. Use `chain()` directly if you need the filter
snippet inside a larger graph.

Squelch clicks and any world ambience (city bed, horns) are timeline
concerns — place them in the build, not in this module. First used by the
MATH vs. VIBES short "chicago-broke-it" v2 (all trucker VO, narrator stays
clean).
