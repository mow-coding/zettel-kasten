# Decision Log: v0.3.303 Artifact Lifecycle Inventory

Date: 2026-08-07
Status: implementation verified; exact-tag release gates pending

## Context

WOM has a useful `ai-artifact-inventory`, but it intentionally scans only four
AI scratch and staging roots. The artifact-hygiene baseline still cannot answer
one bounded question across scratch, intake, workpacks, generated indexes, and
local object bytes: what lifecycle material exists, what needs review, and was
the declared scope completely inspected?

NIST SP 800-53 CM-8 calls for an inventory that reflects the system, avoids
duplicate accounting, uses a useful reporting granularity, and is kept current.
NIST information-retention guidance also treats disposition as a policy-bound
lifecycle decision. WOM therefore needs visibility before it needs deletion.

## Decision

Add CLI-only, read-only `archive artifact-lifecycle-inventory --dry-run`.

- Scan a fixed set of archive-owned lifecycle roots, not arbitrary operator
  paths and not the whole archive or any sibling `-objets` store.
- Classify entries using the existing artifact-hygiene classes. Do not infer
  permission to delete from age, class, or an empty reference count.
- Read file metadata only, except for bounded control metadata in object
  manifests and workpack `package.yml` files.
- Hide archive-relative paths by default. Return stable content-free refs;
  reveal relative paths only with an explicit local-review flag.
- Bound every recursive root independently and report complete, truncated,
  unreadable, changed-during-scan, symlink, and Windows reparse-point coverage.
- Compare canonical local `objects/sha256/` names with a strict manifest
  authority. Report only `unmanifested_local_object_candidate`; do not call an
  item orphaned and do not hash or delete object bytes.
- Treat malformed, ambiguous, unsafe, or incomplete authority as a blocker,
  never as an empty or clean inventory.
- Call no provider, read no secret store, write no archive file, and expose no
  MCP mutation or cleanup tool.

## Consequences

An operator and AI can get one content-free lifecycle checkpoint before using
the narrower AI inventory, staged cleanup verifier, Doctor, or manual workpack
review. A green result proves only complete coverage of the declared local
roots at that moment. It does not prove semantic value, remote-provider state,
object-byte integrity, legal retention eligibility, or permission to delete.

Provider cleanup, sibling external objet-store scanning, and any automatic
cleanup remain future separately approved work.

## Verification Evidence

- Focused inventory, privacy, manifest, workpack, descriptor-change, CLI, and
  Draft 2020-12 schema tests pass. The Windows host cannot create the one
  unprivileged symlink fixture, so that case remains an explicit environment
  skip while reparse/link handling is covered elsewhere in the suite.
- All four deterministic Windows unittest shards pass: 2,293 tests, with 25
  platform-, Docker-, POSIX-, or release-artifact-only skips and zero failures.
- The three pytest-native Win32, writer-authority, and saved-view modules pass:
  129 tests and zero failures.
- Release readiness passes public links, Korean product language, public
  privacy, and runtime-skill checks. The packaged mirror is synchronized at
  144 resources.
- A clean candidate wheel install passes all four entrypoints, 121 MCP tools,
  runtime Skill lifecycle, onboarding preview/write, strict Doctor, and all
  144 manifested resources. The merge/tag-specific rebuild, tag CI, GitHub
  Release asset, and anonymous public reinstall remain separate pending gates.
