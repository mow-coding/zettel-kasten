# Archive Identity Reconcile

Status: implemented in v0.3.226

## Purpose

A WOM archive can repeat principal metadata in two control files:

- `archive.yml` is the archive's principal declaration.
- `archive-identity.yml` is the identity and ownership core.

The duplicated values must agree. Runtime context, AI start-here, and Doctor
report mismatches instead of silently choosing whichever file was read first.

New archives created by v0.3.226 `init` or onboarding replace template
identity id/display values with the reviewed archive and principal values, so
they begin aligned. This command exists for older or manually drifted archives;
an upgrade never rewrites them automatically.

## Read-Only Preview

```text
archive identity-reconcile <archive-root> --dry-run --format json
```

The preview reads only `archive.yml` and `archive-identity.yml`. It does not
read zets, objets, providers, or credential stores and writes nothing. Its
public result contains field names and SHA-256 digests, not display-name or
identity values.

Automatic repair is limited to these same-principal cases:

- copy `archive.yml principal.display_name` to
  `archive-identity.yml identity.display_name`, and
- derive a missing or template-like `identity.identity_id` from the archive id.

Different principal ids, archive ids, scopes, invalid documents, and any other
non-repairable finding block the automatic route for manual review.

## Approval

When the plan is `repair_ready`, use the complete `approval_command` returned
by that exact dry-run. Approval requires:

- a safe `--reviewed-by` value,
- the current `archive.yml` SHA-256,
- the current `archive-identity.yml` SHA-256,
- the proposed `archive-identity.yml` SHA-256, and
- `--affirm-principal-metadata-reviewed`.

If any current or proposed digest differs when approval starts, the write is
refused and the preview must be rerun. Approval never edits `archive.yml`.

## Receipt And Rollback

A successful approval atomically replaces `archive-identity.yml`, verifies its
expected digest, and then writes an immutable receipt under
`receipts/identity-reconciles/`. The receipt records changed field names,
sources, and before/after digests. It stores no display-name or identity value.

The YAML document is reserialized, so comments, anchors, flow style, or key
formatting may normalize even though parsed semantic changes are limited to
the listed fields. If receipt creation fails in the running process, the exact
original identity bytes are restored and a partial receipt is removed.
Forced process or machine termination remains outside that in-process rollback
guarantee; keep the normal archive backup and review discipline.

## Verification

After approval, run quick context and then a strict Doctor check:

```text
archive runtime-context <archive-root> --strict --format json
archive doctor <archive-root> --strict
```

An aligned archive reports `identity_consistency.status: aligned`. Doctor also
validates identity-reconcile receipts against their dedicated schema.
