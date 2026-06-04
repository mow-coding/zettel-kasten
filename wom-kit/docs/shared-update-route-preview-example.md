# Shared Update Route Preview - Usage Example

Date: 2026-06-04
Status: usage/smoke example (read-only, dry-run)

This is a worked example for the `shared-update-route-preview` command
introduced in v0.3.1. It shows how to run the read-only preview and how to read
its output. It does not add any new behavior.

See the reference doc: [shared-update-route-preview.md](shared-update-route-preview.md).

## What this command is

`shared-update-route-preview` looks at one already-reviewed shared update record
and explains the candidate next receiver-side route — `delegate`, `attest`,
`anchor`, or `none` — and which existing command would handle it. It performs
nothing and writes nothing.

## 1. Setup: a tiny public-safe record

Assume the archive already has a reviewed shared update record at an
archive-relative path (no private body, no absolute paths, no secrets):

```text
shared-updates/incoming/example-update.json
```

## 2. Run the dry-run preview

```powershell
python wom-kit\cli\archive.py shared-update-route-preview <archive-root> --record shared-updates/incoming/example-update.json --dry-run --format json
```

## 3. A representative output snippet

```json
{
  "lifecycle_action": "zet_shared_update_route_preview",
  "route_status": "route_preview_not_recorded",
  "candidate_route": "attest",
  "source_shared_update_record": {
    "record_path": "shared-updates/incoming/example-update.json",
    "sha256": "<hash>"
  },
  "trust_state": "untrusted_foreign",
  "attestation_status": "not_created",
  "anchor_status": "not_created",
  "renewal_status": "not_performed",
  "would_change": [],
  "route_eligibility": {
    "attest": {
      "applies": true,
      "defer_to": "attest-zet",
      "related_shared_update_review_command": "shared-update-attestation-review",
      "related_shared_update_review_required_flags": ["--approve", "--reviewed-by"]
    }
  }
}
```

## 4. How to read it

- `candidate_route` — the route a human could consider next (here, `attest`).
- `route_eligibility.<route>.defer_to` — the existing command that actually
  handles that route. This preview only points at it.
- `related_shared_update_review_required_flags` — a reminder that the next
  surface is itself human-gated (it needs `--approve` and `--reviewed-by`).
- `would_change: []` — nothing changed. The preview is read-only.

## 5. The four outcomes

- `delegate` — a delegate route could be considered later (`delegate-zet`).
- `attest` — an attestation/review route could be considered later
  (`attest-zet`; the review write is `shared-update-attestation-review`).
- `anchor` — an anchor route could be considered later (`anchor-zet`).
- `none` — the record is blocked or does not map to a known route. This is a
  neutral fact, not a rejection or an approval.

## What this does NOT do

In simple terms:

- It does **not** authorize a route.
- It does **not** write any file.
- It does **not** import, accept, delegate, attest, or anchor anything.
- It does **not** create trust, transport, provider sync, or a public proof.

It only explains what a later, human-gated route might be. Naming a route
command is not permission to run it.
