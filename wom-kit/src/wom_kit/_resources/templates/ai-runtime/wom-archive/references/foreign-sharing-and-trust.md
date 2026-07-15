# Foreign Sharing And Trust

Use this reference for foreign blocks, shared ZET material, quarantine cases,
attestation review, and transport planning.

## Inspection Never Creates Trust

Inspect a foreign artifact only:

```text
archive foreign-block <archive-root> --path <artifact-path> --dry-run --format json
```

Foreign intake keeps `trust_state: untrusted_foreign`, treats claimed hashes as
unverified claims, and writes nothing. A clean parse does not mean the author,
content, signature, or provenance is trusted.

## Keep The Review Ladder Explicit

The implemented ladder separates:

1. intake inspection;
2. trust-report preview;
3. attestation-packet preview;
4. quarantine-plan preview;
5. CLI-only approved quarantine write;
6. read-only review and decision planning;
7. CLI-only recording of narrowly scoped review records.

Every stage keeps the source untrusted unless a future, separately specified
trust mechanism says otherwise. A review candidate, statement draft, decision,
or attestation-shaped record is not itself trust, import, acceptance, signing,
minting, or transport.

MCP surfaces remain inspection/check-only for these workflows. Do not expose
approve, write, apply, accept, trust, import, attest, sign, publish, provider,
or full-auto behavior through MCP.

## Transport Planning Is Not Transport

Preview the would-transport plan only:

```text
archive zet-transport-plan <archive-root> --record <archive-relative-json> --method <key-sharing|radio-frequency|mirroring> --dry-run --format json
```

The plan creates no key, radio-frequency access, mirrored payload, provider
call, queue, receipt, feed update, or delivery. Never tell the human that a ZET
was shared when only a plan or local review record exists.

## Read The Exact Contract Before Advanced Work

The foreign review ladder has intentionally narrow hashes, upstream-record
checks, replay rules, rollback rules, and output redactions. Search
[operator-contract.md](operator-contract.md) for the exact command name and
read its surrounding section before running any stage after intake.

Useful search terms include:

- `foreign-block-trust`
- `foreign-block-attestation`
- `foreign-block-quarantine`
- `quarantine-foreign-block`
- `record-quarantine-decision`
- `attestation-review-candidate`
- `attestation-statement-draft`
- `shared-update-record-review`
- `zet-transport-plan`
