# Letter 112 Completion Contract

Status: implemented for v0.3.301
Date: 2026-08-07

This release responds to the v0.3.300 integrated real-use report without
opening or modifying the beta tester's private archive. Product changes are
additive: existing command names and records remain readable, and every new
write is CLI-only, previewed first, bound to an exact plan hash, and reviewed
by a human.

## Completion Map

| Letter 112 observation | v0.3.301 response |
|---|---|
| Relative `source-intake-record --source-intake-plan` used the process CWD | Relative plan paths now resolve from the archive root. Missing, unsafe, and colliding paths have fixed distinct blocker codes. Exact existing plans return `already_recorded` plus the documented receipt path. |
| Redacted plans for different same-shape files collided | Local plans now contain a non-content `local_file_identity_sha256` derived from the archive id, resolved path identity, size, and modified time. It never reads or hashes the file body and explicitly labels itself `path_stat_fingerprint_not_content_identity`. |
| 508 files still required 1,017 source-intake commands | `source-intake-batch` accepts 1-1,000 local items, plans them together, binds approval to one complete SHA-256, writes the ordinary redacted per-item records plus one batch receipt, and converges safely on replay. It claims no transaction-wide atomicity. |
| Same external coordinate could not represent distinct occurrences | External locator v0.2 adds optional `service_ref`, `account_ref`, and `occurrence_anchor`. Identity includes these coordinates, so exact duplicates still block while reviewed distinct occurrences coexist. Recovery output reveals coordinate presence only. Legacy v0.1 records and revert receipts remain readable. |
| Simple Notion tables and layout tags blocked cleanup | Reviewed simple `table`/`tr`/`td`/`th`/`col`/`colgroup` fragments convert to GitHub Flavored Markdown tables. `columns`/`column` become paragraph boundaries and paired `mention-date` preserves visible text. Ambiguous/nested/spanned tables and every still-unknown semantic tag remain unchanged and block that whole zet. Exact-byte snapshots, recovery, and revert remain in force. |
| Relation candidates missed real archive coordinates | Candidate planning now recognizes existing `notion_event_time_start`/`end`, `thought_date`, `source_category`, `db1_category`, and `db1_subcategory` facets. Output reports only fixed signal classes, never private coordinate values; signals still create no edge. |
| `--format json` argument failures emitted usage only to stderr | Commands that request JSON now return a content-free JSON validation envelope on stdout, including fixed reason codes and missing option names, with empty stderr. |
| AI-authored zets contained tool traces, stale contradictions, invented format, and non-openable file claims | `ai-response-contract` and `zet-markdown-style-guide` add human-record integrity rules. `authoring-conventions` reads an optional strict archive-local `zettel-kasten/authoring-conventions.yml`. Mint previews warn on likely tool traces and contradictory status phrases. The bundled WOM Agent Skill requires a full re-read, openable references, and in-place unminted-draft revision. |
| A complete objet could not be added to structured zet assets | `zettel-objet-link` adds one manifested full-SHA asset using strict `{object_id, role, label?}` frontmatter. Approval revalidates under a per-zettel lock and records exact before/after evidence. `zettel-objet-link-revert` restores only unchanged post-write bytes. Mint blocks likely truncated objet hashes. |
| A never-minted draft had no safe discard lifecycle | `discard-draft` requires a safe reason, reviewer, and exact fresh plan SHA-256, then stores an exact private snapshot plus immutable receipt. It blocks minted/canonical twins. `discard-draft-restore` provides collision-safe exact restoration. Inbox audit counts intentional discard receipts separately. |

## Source Intake Batch

Request example (store privately under the archive, such as `workbench/`):

```json
{
  "schema": "wom-kit/source-intake-batch-request/v0.1",
  "batch_id": "reviewed-import-20260807",
  "items": [
    {
      "item_id": "item-001",
      "local_path": "staging/incoming/reviewed/file-001.md",
      "source_role": "primary_source"
    }
  ]
}
```

```text
archive source-intake-batch <archive-root> --manifest workbench/request.json --dry-run --format json
archive source-intake-batch <archive-root> --manifest workbench/request.json --approve --expected-plan-sha256 <sha256:...> --reviewed-by <actor> --format json
```

Relative manifest and item paths resolve from the archive root. The command
reads file metadata only. It does not read bodies, calculate content hashes,
call a provider, echo local path values, or authorize later capture.

## Human Authoring And Draft Lifecycle

Before drafting or revising:

```text
archive authoring-conventions <archive-root> --dry-run --format json
```

The optional conventions file uses
`wom-kit/authoring-conventions/v0.1`. It can declare language, title rules,
body rules, required sections, forbidden body content, and short examples.
Private locators, URLs, and secret-like values are rejected. Absence is valid
and returns an explicit conservative template.

An unminted draft is revised in place. If a human decides it should not remain:

```text
archive discard-draft <archive-root> --zettel-id <id> --reason <safe-reason> --dry-run --format json
archive discard-draft <archive-root> --zettel-id <id> --reason <same-reason> --expected-plan-sha256 <sha256:...> --approve --reviewed-by <actor> --format json
```

The output does not echo the reason or body. Restore requires the exact discard
receipt and a fresh restore plan.

## Structured zet-objet Links

```text
archive zettel-objet-link <archive-root> --zettel-id <id> --object-id sha256:<64-hex> --role source --dry-run --format json
archive zettel-objet-link <archive-root> --zettel-id <id> --object-id sha256:<64-hex> --role source --expected-plan-sha256 <sha256:...> --approve --reviewed-by <actor> --format json
```

The object must already be manifested. The writer reads no object bytes and
never guesses a truncated digest. Revert is exact-byte and refuses to overwrite
unrelated later changes.

## Deliberate Boundaries

- Unknown markup still blocks the entire affected zet. Applying only the known
  rewrites would create a mixed partially normalized document while semantic
  review is unresolved.
- `mention-date` currently preserves visible date text. It does not infer or
  write a facet automatically.
- Mint warnings for tool traces and contradictory status are prompts for human
  review, not claims that prose is semantically wrong.
- A discard receipt proves an intentional WOM discard. Historical direct file
  deletion that happened without any receipt cannot be reconstructed from
  nothing.
- Local engineering tests do not prove behavior on the beta tester's private
  archive. That remains a separate human real-use validation gate.

The human-run follow-up is documented in the
[Letter 112 beta retest protocol](letter112-beta-retest-protocol.md).
