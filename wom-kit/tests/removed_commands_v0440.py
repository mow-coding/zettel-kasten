"""Commands deleted in v0.4.40 (owner decision 2026-09-24: retired and replaced
writers are removed outright instead of staying fixed closed).

Legacy boundary tests iterate over historical command tables; they skip these
names because the parser no longer has them. `test_v03299_predecessor_surfaces`
pins the exact removal set.
"""

REMOVED_COMMANDS_V0440 = frozenset({
    "delegate-zet", "transfer-ownership", "quarantine-foreign-block", "record-quarantine-decision",
    "github-repo", "objet-capture-enable", "capture-enable", "object-storage-upload-evidence",
    "object-storage-external-upload-evidence", "objet-storage-upload-evidence",
    "zet-abstract-backfill-recover", "abstract-backfill-recover", "zet-abstract-backfill-revert",
    "abstract-backfill-revert", "zet-abstract-backfill-write", "abstract-backfill-write",
    "credential-keepassxc-write", "keepassxc-write", "external-locator-revert",
    "notion-ancestor-fetch-adapter-run", "notion-ancestor-fetch-run", "notion-ancestor-live-fetch",
    "notion-objet-manifest-locator-label", "notion-objet-locator-label",
    "object-storage-wom-location-reconcile", "object-storage-upload-location-reconcile",
    "object-storage-manifest-reconcile", "objet-storage-wom-location-reconcile", "scan-source",
    "tiro-lossless-recovery-capture", "tiro-recovery-capture",
})
