# v0.4.36 candidate CI correction decisions

Date: 2026-09-21. Scope: this release candidate only.

- **Implementation fact:** the candidate changed default draft creation, added archival, and finalized proven no-effects refusals. Four older test expectations did not match those changes.
- **Delegated engineering choice:** update the tests without reverting intended product behavior. Preserve negative checks and add explicit manual-mode and failed-claim coverage.
- **Verification fact:** four original failures reproduced locally; broader verification is recorded in the [correction minutes](../../meeting-minutes/2026-09-21-v0436-ci-contract-correction.md).
- **User decision retained:** full access does not gain new per-operation approval exceptions. Customer data access remains a separate permission boundary.
- **Release condition:** merge and publish only after the corrected candidate's required CI succeeds. A prior failing run cannot authorize release.
- **User scope correction:** remove fixed v0.4.37 functional promises from current release messaging; retain owed work as backlog while development-process improvements take priority. Preserve the old decision's history with a superseding note.
