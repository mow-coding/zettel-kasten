# Archive Infra Decision Log - v0.3.198 Reconcile Approval Status

Date: 2026-07-08
Release: v0.3.198

## Context

After v0.3.197, an integrated diagnostics batch proved that reconcile dry-run
guidance was useful, but it also exposed a confusing approval result:

```text
ok=true
writes=applied
status=needs_content_change_review
```

The approval functions copied the dry-run plan into the result and then added
write evidence. That preserved stale pre-approval guidance after the write had
already succeeded.

## Decision

Add a separate post-approval guidance block for both reconcile apply paths:

- `remint-reconcile`
- `retire-draft-reconcile`

After a successful approval, the result now reports:

- `status: reconcile_applied`
- `overall_status: reconcile_applied`
- `suggested_next_action: run_doctor_to_verify_reconcile`
- `would_write: false`
- `approval_would_write: false`
- `approval_requires_content_changed_ack: false`
- `next_safe_actions` that point back to doctor verification and a fresh dry-run
  only if new drift appears

## Consequences

- Operators can distinguish pre-approval review state from post-approval applied
  state.
- `content_change_ack` remains durable evidence that an intentional content
  change was explicitly acknowledged before approval.
- Reconcile classification and approval gates are unchanged.
- No zettel content is changed by this status-surface fix.
