# Models And Reasoning Levels

Load this reference when choosing or reporting the AI model that operates WOM.

Status: recommendation, not a benchmark. It is based on beta letters 150-173
(v0.4.45 review) and on WOM's own safety design. No letter compared models or
providers directly, and none could state the reasoning level used.

## What The Letters Show

- Most rule violations were self-reported from long single sessions: hand
  edits, backgrounded or repeated approvals, reusing another conversation's
  session refs, carrying old numbering into records.
- Codex desktop sessions tended to refuse ambiguous scope (for example, a
  commit or cleanup whose session ownership was unclear). This is an
  observation from three letters, not a measured difference.
- Violations clustered after context compaction and in multi-hour sessions,
  regardless of provider.

## Recommended Setup

| Work | Model tier | Reasoning / effort |
|---|---|---|
| reading, search, summaries, previews | any current frontier model | default |
| drafting and revising notes | frontier model | default or medium |
| any `--approve`, update, recovery, cleanup, backup, credential or provider task | the provider's strongest available model | high (or the highest offered) |
| letters to the developers | frontier model | medium or higher |

- Anthropic: a Claude Opus-class or Sonnet-class current model for operations;
  keep Haiku-class models to read-only summaries. Use high effort for writes.
- OpenAI: the Codex app with its strongest available model and high reasoning
  for writes; default reasoning is fine for read-only work.
- Small or fast models should not run approval, update, recovery, or cleanup
  flows.

## Session Habits That Matter More Than The Model

- Keep one task per session and start a new session for a new task.
- After any compaction or context reset, re-run `ai-start-here` before acting.
- Before each write, re-read the core rules card in `SKILL.md`.
- In letters, name the AI and model and state the reasoning level if known.
