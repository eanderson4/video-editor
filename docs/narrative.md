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
   **LLM review is for facts, attack surface, and blind spots — never for
   voice.** Keep their defensibility catches (a number that invites
   comment-section attack, an apples-to-oranges comparison); treat
   structure notes as options; treat tone rewrites as noise. Convergent
   criticism (two or more models flag the same beat) is signal about
   clarity, but convergence on the same rewrite is one median opinion,
   not three — LLMs regress delivery toward announcer-speak and sand off
   the texture (escalations, rambles, confessions) that makes the host
   the host. The host's read of their own lines wins ties.
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

Practitioner-validated set: `.research/yt-narrative-style/PRINCIPLES.md`
in math-vs-vibes (12 sources, tagged [STRUCTURE]/[VOICE]/[HOOK]/[DATA]).

- Numbers are the punchlines (canon). A damage montage without the goal
  metric is spectacle; the metric without the real-world number is
  abstract. You need both, fast.
- The first frame+line is the packaging gate (viewed-vs-swiped, >=70% is
  good); obsess over second one, not over the close. Open with the most
  chaotic moment, then backfill. A gap/misconception hook ("reality has
  ~40k cars here at 8AM; the sim died at 6,500") beats a topic label.
- Escalation beats ("gridlock, total gridlock, collisions") ARE the
  information — cutting discipline targets preamble and transitions, not
  repetition-for-stakes.
- Setbacks are the retention device. "I didn't hit it" is the payoff,
  not a problem to script around. End on meaning, and consider looping
  back to the unmet goal — replays push AVD past 100%.
- Re-hook every ~15-20s inside a 52s short; beats are 10-20s, one idea
  each. 50-60s is fine when it holds (Galloway's dataset: ~4.1M avg
  views vs 1.8M for 40-50s) — never trim a working story for length
  ideology.
- Writing is where the voice lives: LLM feedback may restructure and
  fact-check, but final spoken lines are the host's phrasing. Before
  shipping, audit for AI tells (rule-of-three slogans, "not just X,
  it's Y" cadence symmetry, mirrored closes) — three reviewers
  converging on the same punchy close is itself the tell.
- VO beats the footage can't supply belong over screen visuals or a
  stats card, never over a static webcam shot.
- Canon: no em dashes on screen, no filler sincerity words, estimates
  marked as estimates.
