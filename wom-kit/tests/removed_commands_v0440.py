"""Commands deleted in v0.4.40 (owner decision 2026-09-24: retired and replaced
writers are removed outright instead of staying fixed closed).

Legacy boundary tests iterate over historical command tables; they skip these
names because the parser no longer has them. `test_v03299_predecessor_surfaces`
pins the exact removal set. Five sharing/ownership commands were restored on
2026-09-25 (owner ZET design) and are no longer listed here.
"""

REMOVED_COMMANDS_V0440 = frozenset({
    "objet-capture-enable", "capture-enable", "object-storage-upload-evidence",
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


# v0.4.44 (owner decision 2026-09-25): the IMAP chain superseded by
# imap-mailbox-message-fetch is removed with every alias.
REMOVED_COMMANDS_V0444 = frozenset({
    "imap-header-metadata-scan",
    "imap-header-scan-receipt-audit",
    "imap-mailbox-adapter-audit",
    "imap-mailbox-adapter-audit-plan",
    "imap-mailbox-adapter-audit-write",
    "imap-mailbox-adapter-execution-contract",
    "imap-mailbox-adapter-execution-plan",
    "imap-mailbox-adapter-execution-preflight",
    "imap-mailbox-adapter-manifest",
    "imap-mailbox-adapter-manifest-plan",
    "imap-mailbox-adapter-manifest-write",
    "imap-mailbox-adapter-plan",
    "imap-mailbox-adapter-preflight-plan",
    "imap-mailbox-adapter-readiness-plan",
    "imap-mailbox-header-metadata-scan",
    "imap-mailbox-header-scan-receipt-audit",
    "imap-mailbox-material-capture-approval",
    "imap-mailbox-material-capture-approval-audit",
    "imap-mailbox-material-capture-approval-plan",
    "imap-mailbox-material-capture-execution-contract",
    "imap-mailbox-material-capture-request-plan",
    "imap-mailbox-material-selection-plan",
    "imap-mailbox-material-selection-record",
    "imap-mailbox-message-selection-plan",
    "imap-mailbox-operation-request-plan",
    "imap-mailbox-plan",
    "imap-mailbox-request-plan",
    "imap-mailbox-selection-plan",
    "imap-material-capture-approval-audit",
    "imap-material-capture-approval-plan",
    "imap-material-capture-execution-contract",
    "imap-material-capture-request-plan",
    "imap-material-selection-plan",
    "imap-material-selection-record",
    "mailbox-adapter-audit-plan",
    "mailbox-adapter-audit-write",
    "mailbox-adapter-execution-contract",
    "mailbox-adapter-manifest-plan",
    "mailbox-adapter-manifest-write",
    "mailbox-adapter-preflight",
    "mailbox-adapter-readiness",
    "mailbox-header-metadata-scan",
    "mailbox-header-scan-audit",
    "mailbox-material-capture-approval-audit",
    "mailbox-material-capture-approval-plan",
    "mailbox-material-capture-execution-contract",
    "mailbox-material-capture-request-plan",
    "mailbox-material-selection-plan",
    "mailbox-material-selection-record",
    "mailbox-operation-request-plan",
    "mailbox-selection-plan",
})

REMOVED_COMMANDS = REMOVED_COMMANDS_V0440 | REMOVED_COMMANDS_V0444
