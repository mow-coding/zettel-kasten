# v0.4.36 release artifact verification decision

Date: 2026-09-21. Type: delegated operational choice for this release only.

The local supplement runtime check timed out without completing repair resume. Do not label it passed or keep extending limits. Build the exact tagged source on a Windows CI runner and run the committed complete wheel checker without modification; preserve and publish only its successfully verified wheel. Keep the local failure visible and the performance root cause unconfirmed.

The temporary workflow branch does not change main, the release tag, product behavior, or the full-access policy. After verifying the preserved artifact, continue draft comparison, publication, anonymous verification, and fresh local installations. See the [verification environment record](../../meeting-minutes/2026-09-21-v0436-release-artifact-verification.md).

Outcome: run 35539848491 passed; its exact preserved wheel was published after
source/tag/tree/hash/size checks. Anonymous download matched. See the
[release evidence](../../meeting-minutes/2026-09-21-v0436-release-evidence.md).
This does not close the failed local observation or customer acceptance items.
