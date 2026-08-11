# 2026-08-11 WOM system category clarification

## Context

The user asked whether WOM should be described as a harness and requested an
exact, beginner-friendly category description.

## User correction

The user strongly corrected one point: the former proper-name product “MOW
Harness” no longer exists. It must not be presented as a current WOM component,
dependency, comparison product, or supported integration.

## Current framing

- WOM is the full system: a local-first, AI-native, Web3-oriented archive and
  communication system.
- WOM is broader than a generic AI harness. Its scope includes durable local
  artifacts, source preservation, zet lifecycle and provenance, approval and
  receipt boundaries, recovery authority, AI operation, and the future ZET
  communication layer.
- When describing the part that helps an AI operate safely, prefer “AI operation
  layer” or “AI work-control layer” in Korean rather than the ambiguous standalone
  word “harness.”
- `WOM-kit` is the current implementation/tooling layer—Python package, CLI, MCP,
  schemas, templates, and runtime skill—not the whole WOM worldview or system.
- Current implementation, documentation-only surfaces, and future roadmap must
  remain clearly separated.

## Recommended short description

> WOM은 사람과 AI가 원본, 생각, 초안, 정본 zet, 출처와 변경 이력을 로컬에
> 오래 보존하고, 검토·발행·복구·연결할 수 있게 만드는 AI-native 아카이브
> 및 커뮤니케이션 시스템이다.

## Product evaluation correction

The user rejected a generic criticism that WOM has “no UI.” In v0.3.x the
intended UI is the frontier-model host itself: a user talks naturally to Codex
or Claude Desktop, while the Runtime Skill, MCP surface, CLI, schemas, and
archive contracts constrain how the model reads and writes. A future standalone
control surface may broaden access, but its absence is not by itself a v0.3.x
defect.

The correct UX question is therefore end to end: can one natural-language
request reliably become the right WOM route, preserve sources, report progress
honestly, obtain proportionate review, complete the requested work, and leave a
recoverable state across host/model versions and interrupted sessions?

The critical evaluation concluded that WOM's strongest present distinction is
not “second brain,” local Markdown, MCP, provenance, or human-in-the-loop in
isolation. It is the combined contract of human-owned local canonical artifacts,
source-fidelity modes, reviewed publication, receipts, rollback/recovery, and
anti-silent-merge behavior. The principal risks are host routing bypass,
excessive command/tool/context surface, semantic-review limits beyond byte
integrity, incident-by-incident protocol accumulation, monolithic maintenance
cost, and insufficiently measured daily utility and independent-user retention.

## Letter 126 arrival and scope change

While that evaluation was being completed, the user supplied the new real-use
feedback letter
`<private-archive-root>/ops/feedback/letters/wom-feedback-20260811-126.md`
and asked that the evaluation be retained while implementation work proceeds.
The protected-client-archive letter and its two named diagnostic artifacts were read without
modification.

Observed field evidence:

- v0.3.310 to v0.3.313 project update preview took about 29.5 seconds; approval
  outlived a 124-second external caller timeout and completed after roughly 15
  minutes.
- the approved updater ultimately aligned source, installed-version pin, and
  receipt and released its process and locks;
- ordinary index rebuild completed in 3 minutes 4 seconds with 8,601 zettels,
  23,521 objects, 3,750 derived texts, and a current public index;
- index health then took 2 minutes 1 second and failed solely with
  `private_objet_metadata_projection_unavailable`, despite zero public
  missing/extra/changed/live-inspection findings;
- the nested private state was `blocked`, but top-level blockers were empty and
  the only next action incorrectly said the generated index matched the live
  zettels.

## Initial root-cause evidence

The current updater still calls a separate `git cat-file -s` process and a
separate `git cat-file blob` process for each tree entry. This contradicts the
existing public documentation that describes unique-object batch materialization
and explains the repeated Git child processes observed on Windows.

The ordinary `archive index` path already compiles and installs the private
objet metadata projection inside the same transaction as the public generated
index. The failure is therefore not a missing rebuild feature. The generated
SQLite database is durably in WAL header mode (`2/2`), while a clean final close
removed both `archive-index.sqlite-wal` and `archive-index.sqlite-shm`. The
private read session currently declares that normal checkpointed state
unavailable because it requires a WAL/SHM pair whenever the main database header
advertises WAL. A synthetic read confirmed that simply relaxing the check would
cause a `mode=ro` SQLite query to create new WAL/SHM files, contradicting the
health command's `writes: false` contract. The fix must therefore change the
generated-index journal/read boundary, not merely suppress the blocker.

## Implementation direction

1. replace per-entry Git blob subprocesses with one bounded persistent batch
   protocol while retaining path, type, object-id, size, total-byte, timeout,
   and output limits;
2. make a cleanly closed generated index readable without SQLite sidecar writes,
   then rebuild and validate the public and private projections together;
3. make every blocked private health state produce a top-level fixed blocker
   and command-shaped recovery actions;
4. add a generic, content-free long-operation status/checkpoint contract rather
   than one new bespoke status command per incident, while being honest about
   which cancellation or resume states are actually safe;
5. validate only with synthetic or temporary archives during development; the
   real protected client archive remains read-only until a separately reviewed client
   recovery sequence is ready.

## Palantir comparison correction

The user strongly corrected the assistant's product-evaluation wording. The
Palantir contrast was not a missing idea discovered on 2026-08-11. WOM had
already recorded it precisely on 2026-07-15: an enterprise ontology may map
stable real-world entities into an operational world model, while WOM refuses
to make a stable/global entity map the primary truth of human memory. WOM keeps
time-situated artifacts so a person's changing, conflicting perceptions of the
“same” subject remain visible and reviewable.

The error was the assistant's: it compressed that specific design into generic
“artifact-first” language and then evaluated the product as though the sharper
distinction were absent. The correction restores the existing design; it does
not invent a new 2026-08-11 philosophy or authorize an entity resolver, schema
migration, graph writer, or UI change.
