# v0.3.313 Letter 121 Source-Fidelity Implementation Minutes

Date: 2026-08-10 KST

## Chronology and user intent

- The operator forwarded Letter 121 while v0.3.312 work was still in progress
  and asked that it be handled after the active work, without unnecessarily
  stretching the batch.
- The reported interaction stopped before both draft creation and minting.
  Therefore the verified incident outcome is no written draft, no canonical
  mutation, and no actual archive data loss.
- The important defect was pre-write: the owner had explicitly requested a
  complete private personal source, while the AI proposed preserving the source
  objet but silently shortening the zet body. The operator correctly rejected
  the plan.
- Read-only reproduction against v0.3.312 showed that an AI-assisted dry-run
  with a source reference and a shortened candidate could still report success.
  The service bound the candidate body hash but did not compare it with source
  bytes.
- The operator reiterated that completeness matters more than speed, while
  unnecessary sequencing and duplicated work should be avoided. The response
  was to complete standards research once, freeze a narrow contract, and split
  non-overlapping core, CLI/MCP, and guidance work.

## Decisions

1. Add `verbatim`, `faithful_summary`, and `sanitized_derivative` as closed
   source-fidelity modes, separate from creation mode.
2. Reuse the established audience vocabulary. `verbatim` is limited to a
   personal archive with `private_self` intent.
3. Use a manifested content-addressed objet as source authority. Do not persist
   mutable source paths or excerpts in output or receipts.
4. Define `utf8_newlines_lf` as newline conversion only. Do not trim, normalize
   Unicode, remove BOM, or use the ordinary body parser's `lstrip` as fidelity
   evidence. Record that this basis is not byte-exact.
5. Let the tool append the reviewed verbatim source region and record its raw
   body byte offset and length. Re-verify that raw region during mint.
6. Require explicit human approval, expected body hash, and fidelity plan hash
   for every new AI write, regardless of profile binding.
7. Publish the draft and a content-free receipt with create-only, replayable
   semantics; never overwrite a conflicting draft.
8. Treat summary and sanitized-derivative fidelity as human-reviewed claims,
   not machine-proven semantics.
9. Preserve private personal data under explicit private verbatim intent, while
   continuing to block credential secrets. A later shared derivative never
   changes the private source and does not itself authorize sharing.
10. Do not migrate or rewrite existing zets. Existing AI drafts receive only an
    explicit attributed legacy review path; WOM must not infer a past mode.

## Standards and consequences

W3C PROV, RFC 9530, BagIt, OAIS, in-toto, and SLSA were reviewed from official
sources. WOM adopts their narrow separation, byte-fixity, and evidence-binding
principles, not their full serialization or signing stacks. A SHA-256 digest is
equality evidence, not authenticity, semantic correctness, or an ACL.

The runtime instruction that broadly rejected raw conversation text in a zet
was corrected. Keeping source and readable zet separate remains the default,
but it no longer overrides an explicit `private_self` verbatim request.
Credential secrets remain a higher-priority exclusion. Repeatable information
loss must be routed through the official feedback lifecycle when requested;
the AI may not dismiss it simply because it caused the mistake.

## Implementation surfaces

- `wom-kit/src/wom_kit/archive_services.py`
- `wom-kit/src/wom_kit/archive_cli.py`
- `wom-kit/src/wom_kit/mcp_server.py`
- source-fidelity receipt schema and focused tests
- WOM runtime Skill/reference and personal archive agent rules
- `wom-kit/docs/source-fidelity-and-private-verbatim.md`
- release, capability, version, and packaged-resource surfaces before publish

The external private archive remained read-only. No live provider call or real
personal archive write was authorized as part of implementation or tests.

## Review loop and corrections

Independent review changed the implementation before release in several
material ways:

- Full source object and region authority was removed from draft frontmatter,
  canonical metadata, CLI/MCP results, and mint receipts. It now lives only in
  the private create-only draft receipt; mint derives that receipt from the
  creation plan and validates it before re-reading the manifested objet.
- The ordinary zettel parser trims body boundaries, so it could not carry
  verbatim evidence into the canonical file. The fidelity mint path now carries
  raw body bytes through canonical publication and compares them again after
  writing. Legacy `promote` is blocked for AI/fidelity drafts so it cannot
  bypass this route.
- Old Windows CRLF AI drafts are classified through the tolerant legacy path
  before the new LF-only raw verifier. They remain mintable only after the
  attributed `legacy_source_fidelity_reviewed` affirmation.
- `verbatim` now requires fully private visibility as well as personal archive
  type and `private_self` audience. Private locators are allowed only inside the
  verified verbatim region; context outside that region remains blocked.
- High-confidence AWS, OpenAI, Stripe, GitHub, Slack, Notion, Google, bearer,
  JWT, and private-key shapes are blocked without echo. Ordinary names and
  phone numbers remain preservable private personal data.
- A declared AI actor or `assisted_by` value cannot omit or relabel the AI
  creation mode to enter the human-written route.
- The private receipt schema and runtime verifier are both closed. Unknown
  fields, false privacy claims, malformed source or region structures, and
  duplicate JSON/YAML keys fail closed before canonical or mint-receipt writes.
- The receipt names the replay-bound draft timestamp `candidate_created_at`;
  it does not claim that the candidate timestamp is the actual human-review
  wall-clock time.
- Runtime-context and start-here commands were corrected to use the actual CLI
  option names and required abstract, facet, assisting runtime, source mode,
  audience, and manifested object. A temporary-archive CLI dry-run proves the
  published preview command succeeds.

## Local evidence at the implementation checkpoint

- Focused service, CLI, MCP, and documentation tests: 38 passed before the
  final strict-receipt and AI-provenance additions.
- Final core source-fidelity tests: 14 passed, including subtests for four
  credential shapes, three AI-to-human downgrade attempts, object drift,
  one-character region deletion/change, duplicate keys, and four strict
  receipt-tamper forms.
- Existing create-draft CLI regression selection: 26 passed plus 17 subtests.
- Existing MCP create-draft selection: 8 passed.
- Independent synthetic create-to-mint evidence preserved BOM, leading spaces,
  tabs, NFD text, CRLF/lone-CR conversion, trailing spaces, multiple final
  newlines, and a phone number; the canonical raw body equaled the explicitly
  newline-normalized source and ordinary projections contained no private
  objet id or separately labelled source-digest authority. For a bodyless
  verbatim candidate, its required candidate-body digest may equal the
  normalized source digest and is documented only as candidate equality.

These are temporary-archive and local source-checkout results. At this point in
the chronology they do not yet prove merge, external CI, tag, GitHub Release,
wheel publication, fresh installation, real-archive execution, external
sharing, or human acceptance.

## Late security-freeze corrections

The earlier checkpoint counts above are chronological evidence, not the final
freeze. A later complete-diff review found and closed additional authority and
privacy gaps:

- the creation plan now binds the complete non-recursive frontmatter authority
  and the complete closed source-fidelity evidence;
- an independent review-binding digest binds reviewer, archive, draft, body,
  and the approved creation plan without making reviewer identity part of the
  pre-review candidate plan;
- the redundant, unverifiable `draft_sha256` receipt claim was removed, and the
  replay-bound timestamp was named `candidate_created_at` rather than falsely
  claiming a human-review wall-clock time;
- caller metadata, post-create metadata, legacy AI drafts, and the legacy
  promotion surface now fail with value-free envelopes when credential
  secrets, private local/provider locators, or private source authority appear;
- full object ids plus raw and normalized source digests are blocked in exact
  and embedded, case-insensitive forms, including recursive metadata keys,
  while ordinary public-web citations and private personal text inside a
  verified verbatim region remain allowed;
- historical `ai:` actors and the MCP AI actor are included in legacy AI
  classification, so they cannot enter the human-written mint path without
  attributed review.
- fidelity `draft_creation` metadata is an exact closed five-key record; an
  unexpected key cannot carry private source authority into canonical
  frontmatter.

After those corrections, the focused source-fidelity suite passed 24 tests and
65 subtests. Package-resource synchronization, full regression, wheel
verification, merge, and release evidence remain later chronology and are not
claimed by this checkpoint.

## Final local verification after security freeze

After the late historical `ai:` actor correction and all directly affected
legacy fixtures were updated, the exact frozen runtime tree passed the final
local gates:

- focused source-fidelity, CLI, MCP, and documentation: 51 tests and 71
  subtests passed;
- packaged resources: 145 files synchronized for v0.3.313;
- package, capability, wheel-contract, and predecessor surfaces: 205 tests and
  4,325 subtests passed;
- complete CLI module: 1,375 tests passed with 8 skips, 0 failures, and 0
  errors;
- complete 68-module non-CLI suite: 1,323 passed with 27 skips, 0 failures,
  and 0 errors;
- public links, public privacy, Korean product language, runtime Skill, and
  release-readiness gates passed;
- independent final diff review reported P0 0, P1 0, and P2 0.

The complete CLI and non-CLI runs both recorded identical start/end source and
repository fingerprints. This meeting-minute append is a records-only change
after those runs; the exact committed tree still requires remote CI. These
results do not yet claim commit, push, pull request, merge, tag, GitHub Release,
an exact merged-commit wheel, public installation, real-archive execution,
external sharing, or human acceptance.
