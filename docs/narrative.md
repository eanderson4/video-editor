# Narrative pipeline for shorts (and episode promos)

How a short goes from idea to published. The render mechanics live in
`PLAYBOOK.md` and `SKILL.md`; this file is the editorial half — what you
decide before you touch ffmpeg, and in what order.

## The stages

1. **Research (facts first).** Every on-screen number comes from a
   research-bot mission with a `verify` verdict, or from a primary source
   you queried yourself (keep the query + response in the mission dir).
   Estimates are allowed but must be said as estimates ("on the order of").
   Output: a facts file in the content repo (e.g. `promo/<ep>/goal-metric.md`)
   with the numbers, the source URLs, and the arithmetic.
2. **Narrative spec.** One markdown file per short (template below). It
   owns: the hook card, the beats in order, every line of dialogue/VO,
   every on-screen number with its source, and the close. The build script
   is an implementation of this spec, nothing more.
3. **External review (optional but cheap).** Send the spec to outside
   models for adversarial feedback before rendering:
   `claude -p "$(cat brief.md)"`, `codex exec "$(cat brief.md)"`,
   `research ask -p "$(cat brief.md)"`. Keep responses in `feedback/`.
   Convergent criticism (two or more models flag the same beat) is signal;
   lone opinions are taste.
4. **VO / pickups.** If the spec needs lines the footage doesn't say,
   record them now — after review, before build. A phone recording works;
   drop it in the build dir, transcribe word-level
   (`whisper-cli -ml 1 -osrt`) for captions.
5. **Build (vidkit).** Spec-only `build.py`: spans in session seconds from
   the Riverside SRT, face-tracked crop centers, hook card from the spec.
   See `SKILL.md` entry points and `PLAYBOOK.md`.
6. **Verify.** The PLAYBOOK checklist: probe duration, frame-grab review
   of every layout, join continuity, loudness normalize to ~-14.5 LUFS.
7. **Publish.** Title/description/tags from the spec's hook (title owns
   search terms, thumb owns CTR), then a `POSTING-LOG.md` entry.

## Narrative spec template

```markdown
# Short: <slug>
Goal: <one sentence — what should the viewer feel/know at the end?>
Length target: <45-60s>

## Hook
Card: <2 lines, word-color pairs noted> | Cold open: <beat + source timecode>

## Beats
### 1. <name> (<dur>s, <source: webcam/screenshare/VO+card>)
Dialogue/VO: "<verbatim>"
On screen: <card / captions / overlay, with any numbers + their source>

### 2. ...

## Close
<the last line; ends on meaning, not apology>

## Numbers used
| claim | value | source | verified? |
```

## Editorial rules (hard-won)

- Numbers are the punchlines (canon). A damage montage without the goal
  metric is spectacle; the metric without the real-world number is
  abstract. You need both, fast.
- End on the gap or the lesson, not on the apology. "I didn't hit it" is
  a beat, not a close.
- One idea per beat; beats are 10-20s. If a beat needs a second idea,
  it's two beats.
- VO beats the footage can't supply belong over screen visuals or a
  stats card, never over a static webcam shot.
- Canon: no em dashes on screen, no filler sincerity words, estimates
  marked as estimates.
