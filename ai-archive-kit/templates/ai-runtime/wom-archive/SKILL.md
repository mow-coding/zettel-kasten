# WOM Archive Runtime Skill

Use this skill when working inside a WOM zettel-kasten archive through a terminal-capable AI runtime.

## First Step

Before creating drafts, running mint checks, or asking for mint approval, run:

```bash
archive runtime-context <archive-root> --format json
```

If `archive` is not installed on PATH, run the repository entrypoint instead:

```bash
python ai-archive-kit/cli/archive.py runtime-context <archive-root> --format json
```

If the expected archive is known, include:

```bash
--expected-archive-id <id> --expected-type <personal|company|family|project|relationship|child|business_unit>
```

Use `--strict` when the AI must stop on archive type mismatch or doctor warnings.

## Read The Result

Continue only when:

- `ok` is true,
- `blockers` is empty,
- the `archive_id` matches the intended archive,
- `paths.inbox` and `paths.zettels` are archive-relative,
- `redaction.local_paths_redacted` is true unless the human explicitly asked for local debugging.

## Safe Actions

Prefer these actions:

- create draft in inbox,
- run mint dry-run,
- run check-safe-html dry-run,
- run doctor,
- mint only through CLI approve path.

## Boundaries

Do not:

- expose private local absolute paths by default,
- set `redact_local_paths: false` or use `--no-redact-local-paths` unless the human explicitly asks for trusted local debugging,
- scan the whole disk,
- write canonical zets without explicit CLI approval,
- assume MCP has a real mint/apply tool,
- call provider APIs unless a future explicit integration and approval path exists,
- change product philosophy or naming rules.

## Naming

Use current WOM naming:

- `WOM` for the full system and worldview,
- `zet` for the unit document minted inside a zettel-kasten,
- `ZET` for the communication layer, service, or protocol.
