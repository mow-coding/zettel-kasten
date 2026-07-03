#!/usr/bin/env python3
"""Minimal WOM-kit CLI.

Commands:
  version
          Print the running WOM-kit version and optional project pin status.
  capabilities
          Print an agent-facing manifest of executable CLI commands and release identity.
  operator-feedback-plan
          Show the operator-generated feedback storage and lifecycle contract.
  operator-feedback-record
          Preview or approve a metadata record for operator-generated feedback.
  approval-handoff-plan
          Show the AI-to-human approval handoff storage and lifecycle contract.
  approval-handoff-record
          Preview or approve a metadata record for a human approval handoff.
  approval-handoff-audit
          Audit a handoff record before a future operation uses it as approval evidence.
  operation-status-taxonomy
          Show how AI operators should classify success, partial, truncated, blocked, and failed results.
  input-provenance-taxonomy
          Show how AI operators should classify tool-discovered, receipt-verified, human-selected, and caller-supplied inputs.
  secret-signal-taxonomy
          Show how AI operators should distinguish secret concept words, safe refs, and secret-like values.
  ai-response-contract
          Show the minimum status/provenance/privacy/approval checks an AI should use when answering a human.
  doctor  Inspect an archive for structural and policy issues.
  profile-list
          List read-only WOM profile registry entries.
  profile-resolve
          Resolve a requested WOM profile before runtime-context.
  profile-wallet
          Preview wallet-ready identity metadata for a resolved WOM profile.
  runtime-context
          Print read-only AI runtime context for a mounted archive.
  operational-context
          Read or approve-update the AI-facing mission/state rehydration record.
  prompt-boundary
          Preview prompt-injection boundary risk for untrusted text.
  github-repo
          Plan GitHub repository metadata for a WOM profile.
  object-storage
          Plan object storage metadata for WOM objets.
  object-storage-recommendation
          Recommend an object storage provider path before setup planning.
  object-storage-adapter-readiness-plan
          Check readiness for a future object storage adapter without provider calls.
  imap-mailbox-adapter-readiness-plan
          Check readiness for a future IMAP mailbox adapter without connecting or reading mail.
  imap-mailbox-selection-plan
          Plan a future read-only mailbox message selection without listing messages.
  imap-mailbox-adapter-manifest-plan
          Preview a non-secret future IMAP adapter manifest without writing it.
  imap-mailbox-adapter-manifest-write
          Preview or approve writing a non-secret IMAP adapter manifest locally.
  imap-mailbox-adapter-audit-plan
          Preview a non-secret future IMAP adapter audit receipt without reading mail.
  imap-mailbox-adapter-audit-write
          Preview or approve writing a non-secret IMAP adapter audit receipt locally.
  imap-mailbox-adapter-execution-contract
          Print the read-only future execution contract before any live IMAP adapter exists.
  imap-mailbox-header-metadata-scan
          Run the first approval-gated local IMAP header metadata scan.
  imap-mailbox-header-scan-receipt-audit
          Audit a non-secret IMAP header metadata scan execution receipt.
  imap-mailbox-material-selection-plan
          Plan a human review queue from an IMAP header scan receipt without reading message material.
  imap-mailbox-material-selection-record
          Preview or approve a non-secret IMAP material selection record by candidate index.
  imap-mailbox-material-capture-request-plan
          Plan a future message-material capture request from a selection receipt without reading mail.
  imap-mailbox-material-capture-approval-plan
          Preview or approve a non-secret IMAP material capture approval receipt.
  imap-mailbox-material-capture-approval-audit
          Audit one material capture approval receipt without reading mail.
  prehashed-objet-ledger
          Preview or approve-register an already-hashed external objet ledger without reading blob bytes.
  resolve-objet-ref
          Resolve one sha256 objet reference to safe local/external candidates.
  presigned-url-plan
          Plan a future provider presigned URL request without creating URLs.
  object-storage-operation-request-plan
          Compose the read-only approval request package before any future object storage operation.
  object-storage-upload-evidence
          Record reviewed external upload evidence and update manifest locations without provider calls.
  object-storage-upload-evidence-audit
          Audit upload evidence receipts and manifest locations without provider calls.
  connection-edge-intelligence-plan
          Classify sanitized connection fixture candidates into meaning/mechanism review signals.
  notion-nested-tree-plan
          Plan Notion nested child-page recovery from a sanitized tree fixture.
  notion-ancestor-crawl-plan
          Plan missing Notion ancestor crawl requests from a sanitized nested tree fixture.
  notion-ancestor-fetch-adapter-execution-contract
          Preview the read-only execution contract for a future Notion ancestor fetch adapter.
  notion-ancestor-fetch-adapter-run
          Run the approval-gated local Notion ancestor structure fetch adapter.
  notion-recover
          Run the beginner-friendly one-command Notion missing-location recovery wrapper.
  notion-media-fetch-adapter-execution-contract
          Preview the read-only execution contract for a future Notion media byte fetch adapter.
  notion-media-result-verification-plan
          Verify a sanitized Notion media result fixture against object manifests.
  notion-block-mirror-tree-fixture-plan
          Build a sanitized nested tree fixture preview from reviewed Notion block mirror metadata.
  notion-ancestor-merge-plan
          Merge sanitized ancestor result nodes into a nested tree fixture preview and replan.
  notion-client-issue-verification-plan
          Verify a client Notion nested-tree issue from sanitized local fixtures.
  notion-client-fixture-request-plan
          Package the sanitized fixture request contract for client Notion issue verification.
  imap-mailbox-operation-request-plan
          Compose the read-only approval request package before any future IMAP mailbox operation.
  imap-mailbox-plan
          Plan a read-only IMAP mailbox source without connecting or storing secrets.
  credential-ref-plan
          Plan a local credential reference without reading or storing secret values.
  credential-ref-inventory
          List known credential refs without echoing ref values or secrets.
  credential-store-recommendation
          Recommend a secret store class for a human scenario without reading secrets.
  credential-vault-onboarding-plan
          Plan safe human vault onboarding without opening or reading a vault.
  beginner-setup-manual
          Print beginner-friendly secret vault and text-tool setup steps.
  ai-response-concept-guide
          Print beginner-friendly AI explanation cards for WOM object identity and evidence layers.
  zet-quality-check
          Check one zet for entity, document-type, source, audience, correction, and derived-artifact risks.
  status-board
          Summarize canonical, draft, retire, source metadata, and derived-artifact status without writes.
  derived-artifact-staleness
          Check whether declared derived artifacts may be stale relative to source zets.
  credential-semantic-extraction-recipe
          Print a read-only semantic recipe for splitting complex credential notes without reading secrets.
  connected-accounts
          Summarize connected provider/source accounts and credential store types without reading secrets.
  credential-plaintext-migration-plan
          Plan safe plaintext-secret migration without reading or importing secrets.
  credential-policy-check
          Check a credential request against the approval policy gate.
  credential-keepassxc-command-plan
          Plan a KeePassXC CLI command after approval receipt verification, without executing it.
  credential-keepassxc-write
          Execute a minimal KeePassXC CLI add after approval receipt verification.
  credential-access-broker-plan
          Plan a future approved credential broker request without retrieving secrets.
  credential-access-approval-plan
          Preview or record a credential access approval receipt without reading secrets.
  credential-adapter-readiness-plan
          Preview whether a future credential adapter contract is safe to implement.
  credential-adapter-manifest-plan
          Preview a non-secret future credential adapter manifest without writing it.
  credential-adapter-audit-plan
          Preview a non-secret future credential adapter audit receipt without writing it.
  derive-text-coverage
          Check textual objet derived-text coverage without reading source bodies.
  derive-text-toolchain
          Recommend an extraction route for one derived-text format.
  derive-text-doctor
          Check local derived-text toolchain readiness, with optional non-echoed tool hints.
  derive-text-agent-contract
          Print the derived-text agent operating contract.
  source-intake
          Plan safe source/objet refs before draft creation.
  source-intake-record
          Record a reviewed source-intake dry-run plan under receipts/sources/.
  objet-capture-selection
          Build a reviewed objet-capture selection manifest from a staged file and source-intake receipt.
  project-intake-plan
          Plan one staged project folder intake session without writing files.
  project-intake-staging-guide
          Show where to stage one project before a project intake session.
  project-intake-session-guide
          Show the next safe human-guided project intake step without writing files.
  project-intake-unpack-queue
          Queue top-level staged items for human-guided unpacking without exposing names.
  project-intake-unpack-choice
          Record one human-confirmed unpack choice without exposing names or paths.
  project-intake-next-question
          Return the next human-review question for a project intake session.
  project-intake-decision-template
          Build a next-question decision JSON template without writing files.
  project-intake-item-plan
          Preview the next dry-run commands for one selected intake item.
  notion-objet-link-plan
          Plan Notion provider locator to manifested objet links without echoing URLs.
  notion-objet-link-index
          Index Notion provider locator to manifested objet link candidates across zettels.
  notion-objet-link-convert
          Preview or approve converting one reviewed Notion locator match into an embed edge.
  view-recommendation-plan
          Plan saved view recommendations from navigation facets without writing views.
  block-header
          Preview the derived block header for one draft or canonical zet.
  projection-plan
          Preview a dry-run ZET publication/projection plan for one local zet.
  zet-surface-prototype
          Preview a user-selected ZET surface prototype for WordPress, Joplin, Notion, or Obsidian.
  shared-update-record-review
          Preview a local ZET shared update record before any renewal action.
  shared-update-record-review-index
          Index local ZET shared update records before any renewal action.
  shared-update-route-preview
          Preview the next receiver-side route without writes.
  shared-update-attestation-review
          Approve recording a local shared update attestation/review record and receipt.
  zet-transport-plan
          Preview a dry-run would-transport plan without real ZET transport.
  foreign-block
          Preview a foreign/shared block or zet before any trust/import action.
  foreign-block-trust
          Preview future trust/attestation eligibility from a foreign-block intake report.
  foreign-block-attestation
          Preview a human-review attestation packet from a foreign-block trust report.
  foreign-block-quarantine
          Plan future isolated holding for a foreign block without writing quarantine files.
  quarantine-foreign-block
          Preview or approve an isolated quarantine case write for a foreign block.
  quarantine-review
          List and validate existing foreign block quarantine cases.
  quarantine-decision
          Preview a future decision path for one foreign block quarantine case.
  record-quarantine-decision
          Preview or approve recording a local quarantine decision without trusting a foreign block.
  quarantine-decision-review
          List and validate recorded foreign block quarantine decisions.
  quarantine-decision-outcome
          Plan the next safe non-mutating path for one recorded quarantine decision.
  attestation-review-candidate
          Plan a human attestation review candidate from an eligible quarantine decision.
  record-attestation-review-candidate
          Preview or approve recording an untrusted attestation review candidate.
  attestation-candidate-review
          List and validate recorded foreign block attestation review candidates.
  attestation-statement-draft
          Preview a non-binding attestation statement draft for one recorded candidate.
  record-attestation-statement-draft
          Preview or approve recording that statement draft without attesting or signing.
  attestation-statement-draft-review
          List and validate recorded foreign block attestation statement drafts.
  attestation-statement-draft-decision
          Preview a safe next review route for one recorded statement draft.
  init    Create a new archive from a built-in template.
  index   Build a generated local SQLite search index.
  parcel Create a portable parcel from a view. Alias: pack.
  admit  Preview admitting a parcel/workpack without mutating the target archive. Alias: import.
  import-external
          Import Notion or Google Drive exports as governed inbox drafts.
  derive-text
          Register extracted/OCR/ASR/vision text as a provenance-aware derived text record.
  providers
          Inspect provider bindings and external account change plans.
  sources
          Inspect source bindings and mapped source items.
  scan-source
          Metadata-only scan of a registered source into source-maps/.
  add-source
          Register a source without hand-editing source-bindings.yml.
  mint-zet
          Mint an inbox draft zet into canonical private archive memory.
          Alias: mint-zettel.
  retire-draft
          Close an already minted inbox draft after evidence verification.
  delegate-zet
          Preview or write delegated zet access from a saved view.
  attest-zet
          Preview attestation of a delegated foreign zet receipt.
  anchor-zet
          Preview anchoring an attested foreign zet into local meaning.
  check-safe-html
          Dry-run check whether a Markdown-compatible zet is compatible with a
          future WOM Safe HTML Profile migration. Read-only; never writes files.
  source-mounts
          Show host-native and Docker mount guidance for registered sources.
  recovery-plan
          Show backup/restore readiness without writing files.
  upgrade-check
          Check upgrade readiness without writing files.
  migrate
          Dry-run or approve a frontmatter compatibility migration.
  restore-drill
          Plan or run a local restore drill before real data pilot.
  pilot-plan
          Plan a first real personal/team pilot without writing files.
  preflight
          Check an archive before connecting real personal or team data.
  transfer-ownership
          Preview or apply an archive ownership transfer.
  search  Search the generated local SQLite index.
"""

from __future__ import annotations

import argparse
import getpass
import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable

from . import __version__, archive_services
from .paths import (
    ArchivePathError,
    archive_relative_path,
    contains_forbidden_location_reference,
    is_path_within_root,
    resolve_archive_relative_path,
)
from .schema_validator import validate_schema

try:
    import yaml
except ImportError:  # pragma: no cover - exercised only when dependency is absent.
    yaml = None


KIT_ROOT = Path(__file__).resolve().parents[2]
TEMPLATES_ROOT = KIT_ROOT / "templates"
KIT_ZETTEL_KASTEN_ROOT = KIT_ROOT / "zettel-kasten"

REQUIRED_ARCHIVE_FILES = [
    "AGENTS.md",
    "archive.yml",
    "archive-identity.yml",
    "provider-bindings.yml",
    "source-bindings.yml",
    "views/homebase.yml",
    "objects/manifests/files.jsonl",
    "db/schema.sql",
]

REQUIRED_ARCHIVE_DIRS = [
    "inbox",
    "zettels",
    "views",
    "source-maps",
    "objects",
    "objects/manifests",
    "db",
]

RECOMMENDED_V02_FILES = [
    "zettel-kasten/types.yml",
    "zettel-kasten/actions.yml",
    "zettel-kasten/policies.yml",
    "zettel-kasten/zettel-rules.yml",
]

ZETTEL_KASTEN_SCHEMA_FILES = {
    "types.yml": "zettel-kasten-types.schema.json",
    "actions.yml": "zettel-kasten-actions.schema.json",
    "policies.yml": "zettel-kasten-policies.schema.json",
    "zettel-rules.yml": "zettel-rules.schema.json",
}

REQUIRED_ZETTEL_FIELDS = [
    "id",
    "title",
    "created_at",
    "updated_at",
    "archive_id",
    "status",
    "facets",
    "assets",
    "edges",
    "provenance",
    "visibility",
]

ALLOWED_ZETTEL_STATUS = {"draft", "canonical", "archived", "redacted"}
CANONICAL_REQUIRES_VALUES = {"human_minting", "human_promotion"}
OBJECT_ID_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
DERIVED_TEXT_ID_RE = re.compile(r"^derived-text:sha256:[0-9a-f]{64}$")
FRONTMATTER_RE = re.compile(r"\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*\r?\n", re.DOTALL)
SECRET_VALUE_RE = re.compile(
    r"(?i)(?:api[_-]?key|secret|token|password|credential|aws_secret_access_key)\s*[:=]\s*['\"]?[A-Za-z0-9_./+=:-]{12,}"
    r"|-----BEGIN (?:RSA |DSA |EC |OPENSSH )?PRIVATE KEY-----"
    r"|\bAKIA[0-9A-Z]{16}\b"
)
SECRET_ASSIGNMENT_VALUE_RE = re.compile(
    r"(?i)\A(?:api[_-]?key|secret|token|password|credential|aws_secret_access_key)\s*[:=]\s*['\"]?([A-Za-z0-9_./+=:-]{12,})['\"]?\Z"
)
SECRET_SCAN_EXTENSIONS = {
    ".conf",
    ".env",
    ".ini",
    ".json",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}


def contains_secret_value(text: str) -> bool:
    for match in SECRET_VALUE_RE.finditer(text):
        if secret_match_is_declared_credential_ref(match.group(0)):
            continue
        return True
    return False


def secret_match_is_declared_credential_ref(match_text: str) -> bool:
    text = match_text.strip().strip("'\"")
    if archive_services.safe_credential_ref(text):
        return True
    assignment = SECRET_ASSIGNMENT_VALUE_RE.match(text)
    if not assignment:
        return False
    return archive_services.safe_credential_ref(assignment.group(1).strip("'\""))
RECOMMENDED_GITIGNORE_PATTERNS = [
    ".env",
    ".env.*",
    "!.env.example",
    "secrets/",
    "profiles/local/",
    "profiles/*.local.yml",
    "keyrings/local/",
    "keyrings/*.local.yml",
    ".archive-local/",
    "*.key",
    "*.pem",
    "*.p12",
    "*.pfx",
    "*.kdbx",
    "rclone.conf",
    "credentials.json",
    "token.json",
    "tmp/",
    ".wom-scratch/",
    "workbench/ai-scratch/",
    "node_modules/",
    ".next/",
    ".vercel/",
    "/collab/",
    "/.mow-harness/",
    "**/db/archive-index.sqlite",
    "**/db/archive-index.sqlite-wal",
    "**/db/archive-index.sqlite-shm",
    "**/db/archive-index.sqlite-journal",
    "objects/sha256/",
    "objects/derived-text/sha256/",
    "/objets/",
]
SECRET_FILENAME_EXACT = {
    ".env",
    "credentials.json",
    "token.json",
    "rclone.conf",
    "id_rsa",
    "id_dsa",
    "id_ecdsa",
    "id_ed25519",
}
SECRET_FILENAME_SUFFIXES = (
    ".key",
    ".pem",
    ".p12",
    ".pfx",
    ".kdbx",
    ".secret.yml",
    ".secrets.yml",
    ".secret.yaml",
    ".secrets.yaml",
)
LOCAL_PROFILE_ROOTS = (
    "profiles/local/",
    "keyrings/local/",
    ".archive-local/",
)


@dataclass
class Diagnostic:
    severity: str
    code: str
    message: str
    path: str | None = None
    hint: str | None = None
    suggested_command: str | None = None
    compatibility_target: str | None = None

    def as_dict(self) -> dict[str, str | None]:
        data = {
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
            "path": self.path,
        }
        if self.hint is not None:
            data["hint"] = self.hint
        if self.suggested_command is not None:
            data["suggested_command"] = self.suggested_command
        if self.compatibility_target is not None:
            data["compatibility_target"] = self.compatibility_target
        return data


@dataclass
class ValidationScope:
    mode: str = "full"
    label: str = "full archive"
    since_refs: list[str] = field(default_factory=list)
    facet_filters: dict[str, str] = field(default_factory=dict)
    batch_receipt_paths: set[str] = field(default_factory=set)
    zettel_paths: set[str] = field(default_factory=set)
    mint_receipt_paths: set[str] = field(default_factory=set)
    retired_draft_receipt_paths: set[str] = field(default_factory=set)
    edge_receipt_paths: set[str] = field(default_factory=set)
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    index_cache_used: bool = False

    def active(self) -> bool:
        return self.mode != "full"

    def summary(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "label": self.label,
            "since_refs": self.since_refs,
            "facet_filters": self.facet_filters,
            "batch_receipt_count": len(self.batch_receipt_paths),
            "zettel_count": len(self.zettel_paths),
            "mint_receipt_count": len(self.mint_receipt_paths),
            "retired_draft_receipt_count": len(self.retired_draft_receipt_paths),
            "edge_receipt_count": len(self.edge_receipt_paths),
            "index_cache_used": self.index_cache_used,
        }


ProgressCallback = Callable[[str, str, int | None, int | None], None]


def parse_validate_scope_filters(raw_filters: list[str] | None) -> tuple[dict[str, str], list[str]]:
    filters: dict[str, str] = {}
    blockers: list[str] = []
    for raw in raw_filters or []:
        text = str(raw or "").strip()
        if "=" not in text:
            blockers.append("validate --scope must use facet=value syntax.")
            continue
        key, value = [item.strip() for item in text.split("=", 1)]
        if key.startswith("facets."):
            key = key.split(".", 1)[1]
        if not key or not value:
            blockers.append("validate --scope requires a non-empty facet key and value.")
            continue
        if not archive_services.safe_source_intake_plan_scalar(key) or not archive_services.safe_source_intake_plan_scalar(value):
            blockers.append("validate --scope facet key/value must be safe non-secret scalar labels.")
            continue
        filters[key] = value
    return filters, blockers


def _add_validate_scope_file(
    scope: ValidationScope,
    root: Path,
    relative: Any,
    collection: set[str],
    label: str,
    *,
    required: bool = True,
) -> Path | None:
    if not isinstance(relative, str) or not relative.strip():
        if required:
            scope.blockers.append(f"{label} path is missing.")
        return None
    try:
        path = resolve_archive_relative_path(root, relative)
        display = archive_relative_path(path, root)
    except (ArchivePathError, OSError, ValueError) as exc:
        scope.blockers.append(f"{label} path is unsafe: {relative} ({exc})")
        return None
    if required and not path.is_file():
        scope.blockers.append(f"{label} file is missing: {display}")
        return None
    if path.is_file():
        collection.add(display)
    return path


def _load_validate_scope_json(scope: ValidationScope, path: Path, label: str) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        scope.blockers.append(f"{label} is not readable JSON: {exc}")
        return None
    if not isinstance(data, dict):
        scope.blockers.append(f"{label} must contain a JSON object.")
        return None
    return data


def _collect_validate_scope_from_mint_receipt(scope: ValidationScope, root: Path, receipt_relative: str) -> None:
    receipt_path = _add_validate_scope_file(scope, root, receipt_relative, scope.mint_receipt_paths, "mint receipt")
    if receipt_path is None:
        return
    data = _load_validate_scope_json(scope, receipt_path, "mint receipt")
    if data is None:
        return
    target = data.get("target") if isinstance(data.get("target"), dict) else {}
    target_path = _add_validate_scope_file(scope, root, target.get("path"), scope.zettel_paths, "mint receipt target")
    source = data.get("source") if isinstance(data.get("source"), dict) else {}
    if isinstance(source.get("path"), str):
        _add_validate_scope_file(scope, root, source.get("path"), scope.zettel_paths, "mint receipt source", required=False)
    if target_path is None:
        return


def _collect_validate_scope_from_retired_draft_receipt(scope: ValidationScope, root: Path, receipt_relative: str) -> None:
    receipt_path = _add_validate_scope_file(
        scope,
        root,
        receipt_relative,
        scope.retired_draft_receipt_paths,
        "retired draft receipt",
    )
    if receipt_path is None:
        return
    data = _load_validate_scope_json(scope, receipt_path, "retired draft receipt")
    if data is None:
        return
    target = data.get("target") if isinstance(data.get("target"), dict) else {}
    _add_validate_scope_file(scope, root, target.get("path"), scope.zettel_paths, "retired draft target")
    mint_receipt = data.get("mint_receipt") if isinstance(data.get("mint_receipt"), dict) else {}
    if isinstance(mint_receipt.get("path"), str):
        _collect_validate_scope_from_mint_receipt(scope, root, mint_receipt["path"])


def _collect_validate_scope_from_edge_receipt(scope: ValidationScope, root: Path, receipt_relative: str) -> None:
    receipt_path = _add_validate_scope_file(scope, root, receipt_relative, scope.edge_receipt_paths, "zettel-edge receipt")
    if receipt_path is None:
        return
    data = _load_validate_scope_json(scope, receipt_path, "zettel-edge receipt")
    if data is None:
        return
    source_path = data.get("source_zettel_path")
    if isinstance(source_path, str):
        _add_validate_scope_file(scope, root, source_path, scope.zettel_paths, "zettel-edge source")


def _validate_batch_receipt_candidates(root: Path, raw_ref: str) -> list[Path]:
    text = raw_ref.strip()
    candidates: list[Path] = []
    try:
        candidates.append(archive_services.resolve_receipt_input_path(root, text))
    except Exception:
        pass

    search_roots = [
        root / archive_services.MINT_BATCH_RECEIPTS_DIR,
        root / archive_services.MINT_RETIRED_DRAFT_BATCH_RECEIPTS_DIR,
        root / archive_services.ZETTEL_EDGE_BATCH_RECEIPTS_DIR,
    ]
    for search_root in search_roots:
        if not search_root.is_dir():
            continue
        for path in sorted(search_root.glob("*.json")):
            if path in candidates:
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            batch_id = str(data.get("batch_id") or "")
            try:
                relative = archive_relative_path(path, root)
            except (ArchivePathError, OSError, ValueError):
                relative = ""
            if text in {batch_id, relative, path.name} or (batch_id and batch_id.endswith(text)):
                candidates.append(path)
    return list(dict.fromkeys(candidates))


def _collect_validate_scope_from_batch_receipt(scope: ValidationScope, root: Path, batch_path: Path) -> None:
    try:
        batch_relative = archive_relative_path(batch_path, root)
    except (ArchivePathError, OSError, ValueError):
        batch_relative = str(batch_path)
    scope.batch_receipt_paths.add(batch_relative)
    data = _load_validate_scope_json(scope, batch_path, "batch receipt")
    if data is None:
        return
    receipt_kind = data.get("receipt_kind")
    if receipt_kind == "mint_zet_batch_write":
        for receipt_relative in data.get("mint_receipts") or []:
            _collect_validate_scope_from_mint_receipt(scope, root, str(receipt_relative or ""))
    elif receipt_kind == "retire_draft_batch_write":
        for receipt_relative in data.get("retire_receipts") or []:
            _collect_validate_scope_from_retired_draft_receipt(scope, root, str(receipt_relative or ""))
    elif receipt_kind == "zettel_edge_batch_write":
        for receipt_relative in data.get("edge_receipts") or []:
            _collect_validate_scope_from_edge_receipt(scope, root, str(receipt_relative or ""))
    else:
        scope.blockers.append(f"Unsupported validate --since batch receipt kind: {receipt_kind}")


def _add_validate_scope_facet_paths(scope: ValidationScope, root: Path, filters: dict[str, str]) -> None:
    db_path = root / archive_services.INDEX_RELATIVE_PATH
    if not db_path.is_file():
        scope.blockers.append("validate --scope requires db/archive-index.sqlite. Run `archive index` first.")
        return
    try:
        conn = archive_services.connect_archive_index(db_path, row_factory=True)
        try:
            canonical_count_row = conn.execute(
                """
                SELECT COUNT(*) AS count
                FROM zettels
                WHERE coalesce(status, '') = 'canonical'
                  AND path LIKE 'zettels/%'
                """
            ).fetchone()
            canonical_count = int(canonical_count_row["count"] if isinstance(canonical_count_row, sqlite3.Row) else canonical_count_row[0])
            metadata = archive_services.read_archive_index_metadata(conn)
            stale_reasons = archive_services.archive_index_metadata_stale_reasons(metadata, indexed_canonical_count=canonical_count)
            if stale_reasons:
                scope.blockers.append(
                    "validate --scope requires a current generated index. Run `archive index` first. "
                    + "stale_reasons="
                    + ",".join(stale_reasons)
                )
                return
            sql = [
                "SELECT path FROM zettels",
                "WHERE zettel_id IS NOT NULL AND coalesce(status, '') != 'redacted'",
            ]
            params: list[Any] = []
            for key, value in filters.items():
                sql.append(
                    "AND EXISTS (SELECT 1 FROM zettel_facets f WHERE f.zettel_id = zettels.zettel_id"
                    " AND f.facet_key = ? AND f.facet_value = ?)"
                )
                params.extend([key, value])
            sql.append("ORDER BY path")
            rows = conn.execute(" ".join(sql), params).fetchall()
        finally:
            conn.close()
    except sqlite3.Error as exc:
        scope.blockers.append(f"validate --scope could not read generated index: {exc}")
        return
    for row in rows:
        relative = str(row["path"] if isinstance(row, sqlite3.Row) else row[0])
        _add_validate_scope_file(scope, root, relative, scope.zettel_paths, "scoped zettel")
    scope.index_cache_used = True
    if not scope.zettel_paths:
        scope.warnings.append("validate --scope matched zero zettels.")


def build_validation_scope(root: Path, since_refs: list[str] | None, raw_scope_filters: list[str] | None) -> ValidationScope:
    filters, filter_blockers = parse_validate_scope_filters(raw_scope_filters)
    since_values = [str(item or "").strip() for item in since_refs or [] if str(item or "").strip()]
    if not since_values and not filters:
        return ValidationScope()
    mode_parts = []
    if since_values:
        mode_parts.append("since")
    if filters:
        mode_parts.append("facet")
    scope = ValidationScope(mode="+".join(mode_parts), since_refs=since_values, facet_filters=filters)
    scope.blockers.extend(filter_blockers)
    if since_values:
        for since_ref in since_values:
            candidates = _validate_batch_receipt_candidates(root, since_ref)
            if not candidates:
                scope.blockers.append(f"validate --since could not find a matching batch receipt: {since_ref}")
                continue
            for candidate in candidates:
                _collect_validate_scope_from_batch_receipt(scope, root, candidate)
    if filters:
        _add_validate_scope_facet_paths(scope, root, filters)
    label_parts = []
    if since_values:
        label_parts.append(f"since={len(since_values)}")
    if filters:
        label_parts.append("scope=" + ",".join(f"{key}={value}" for key, value in filters.items()))
    scope.label = "; ".join(label_parts) if label_parts else "full archive"
    return scope


def make_validate_progress_callback(enabled: bool) -> ProgressCallback | None:
    if not enabled:
        return None
    started = time.monotonic()

    def progress(stage: str, message: str, current: int | None, total: int | None) -> None:
        elapsed = max(0.0, time.monotonic() - started)
        if current is not None and total:
            rate = current / elapsed if elapsed else 0.0
            remaining = max(0, total - current)
            eta = remaining / rate if rate else 0.0
            print(
                f"[validate] {stage}: {current}/{total} {message} elapsed={elapsed:.1f}s eta={eta:.1f}s",
                file=sys.stderr,
                flush=True,
            )
        else:
            print(f"[validate] {stage}: {message} elapsed={elapsed:.1f}s", file=sys.stderr, flush=True)

    return progress


class Doctor:
    def __init__(
        self,
        archive_root: Path,
        *,
        validate_scope: ValidationScope | None = None,
        progress_callback: ProgressCallback | None = None,
        use_zettel_index_cache: bool = False,
    ) -> None:
        self.archive_root = archive_root.resolve()
        self.diagnostics: list[Diagnostic] = []
        self.archive_config: dict[str, Any] = {}
        self.manifest_objects: dict[str, dict[str, Any]] = {}
        self.allowed_link_types = self._load_allowed_link_types()
        self.edge_receipts_by_source: dict[str, list[dict[str, Any]]] | None = None
        self.validate_scope = validate_scope or ValidationScope()
        self.progress_callback = progress_callback
        self.use_zettel_index_cache = use_zettel_index_cache
        self._zettel_index_cache: dict[str, dict[str, Any] | None] = {}

    def run(self) -> list[Diagnostic]:
        if not self.archive_root.exists():
            self.error("archive_root_missing", "Archive root does not exist.", self.archive_root)
            return self.diagnostics
        if not self.archive_root.is_dir():
            self.error("archive_root_not_directory", "Archive root is not a directory.", self.archive_root)
            return self.diagnostics

        self.info("archive_root", f"Inspecting archive root: {self.archive_root}", self.archive_root)
        self.info(
            "doctor_version_compatibility",
            f"release v{__version__} / schema {archive_services.FRONTMATTER_V03_TARGET} / compatible? yes",
        )
        if self.validate_scope.active():
            self.info("validate_scope", f"Scoped validation: {self.validate_scope.summary()}")
            for warning in self.validate_scope.warnings:
                self.warn("validate_scope_warning", warning)
            for blocker in self.validate_scope.blockers:
                self.error("validate_scope_blocked", blocker)
            if self.validate_scope.blockers:
                return self.diagnostics

        stages = self._scoped_stages() if self.validate_scope.active() else self._full_stages()
        for stage_name, stage_func in stages:
            self._run_stage(stage_name, stage_func)
        return self.diagnostics

    def _full_stages(self) -> list[tuple[str, Callable[[], None]]]:
        return [
            ("symlink-boundaries", self._check_symlink_boundaries),
            ("required-structure", self._check_required_structure),
            ("archive-root-boundaries", self._check_archive_root_boundaries),
            ("v0.2-recommendations", self._check_v02_recommendations),
            ("archive-yml", self._check_archive_yml),
            ("archive-identity", self._check_archive_identity_yml),
            ("provider-bindings", self._check_provider_bindings_yml),
            ("source-bindings", self._check_source_bindings_yml),
            ("sqlite-schema", self._check_sqlite_schema),
            ("object-manifest", self._check_object_manifest),
            ("derived-text-manifest", self._check_derived_text_manifest),
            ("source-maps", self._check_source_maps),
            ("zettels", self._check_zettels),
            ("views", self._check_views),
            ("workpacks", self._check_workpacks),
            ("external-import-receipts", self._check_external_import_receipts),
            ("source-scan-receipts", self._check_source_scan_receipts),
            ("recovery-receipts", self._check_recovery_receipts),
            ("lineage-receipts", self._check_lineage_receipts),
            ("mint-receipts", self._check_mint_receipts),
            ("retired-draft-receipts", self._check_retired_draft_receipts),
            ("reconcile-receipts", self._check_reconcile_receipts),
            ("delegate-receipts", self._check_delegate_receipts),
            ("capture-enablement", self._check_capture_enablement),
            ("zettel-kasten-layer", self._check_zettel_kasten_layer),
            ("local-profile-secret-safety", self._check_local_profile_and_secret_safety),
        ]

    def _scoped_stages(self) -> list[tuple[str, Callable[[], None]]]:
        return [
            ("symlink-boundaries", self._check_symlink_boundaries),
            ("required-structure", self._check_required_structure),
            ("archive-root-boundaries", self._check_archive_root_boundaries),
            ("archive-yml", self._check_archive_yml),
            ("archive-identity", self._check_archive_identity_yml),
            ("provider-bindings", self._check_provider_bindings_yml),
            ("source-bindings", self._check_source_bindings_yml),
            ("sqlite-schema", self._check_sqlite_schema),
            ("zettels", self._check_zettels),
            ("mint-receipts", self._check_mint_receipts),
            ("retired-draft-receipts", self._check_retired_draft_receipts),
            ("reconcile-receipts", self._check_reconcile_receipts),
            ("scoped-edge-receipts", self._check_scoped_edge_receipts),
            ("zettel-kasten-layer", self._check_zettel_kasten_layer),
        ]

    def _run_stage(self, stage_name: str, stage_func: Callable[[], None]) -> None:
        self._progress(stage_name, "start", None, None)
        stage_func()
        self._progress(stage_name, "done", None, None)

    def _progress(self, stage: str, message: str, current: int | None, total: int | None) -> None:
        if self.progress_callback is not None:
            self.progress_callback(stage, message, current, total)

    def error(
        self,
        code: str,
        message: str,
        path: Path | str | None = None,
        *,
        hint: str | None = None,
        suggested_command: str | None = None,
        compatibility_target: str | None = None,
    ) -> None:
        self.diagnostics.append(
            Diagnostic(
                "ERROR",
                code,
                message,
                self._display_path(path),
                hint,
                suggested_command,
                compatibility_target,
            )
        )

    def warn(self, code: str, message: str, path: Path | str | None = None) -> None:
        self.diagnostics.append(Diagnostic("WARN", code, message, self._display_path(path)))

    def info(self, code: str, message: str, path: Path | str | None = None) -> None:
        self.diagnostics.append(Diagnostic("INFO", code, message, self._display_path(path)))

    def _display_path(self, path: Path | str | None) -> str | None:
        if path is None:
            return None
        path_obj = Path(path)
        try:
            return archive_relative_path(path_obj, self.archive_root)
        except (ArchivePathError, OSError, ValueError):
            return str(path)

    def _parse_receipt_time(self, value: Any) -> datetime | None:
        if not isinstance(value, str) or not value.strip():
            return None
        try:
            return datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            return None

    def _receipt_cutoff_time(self, data: dict[str, Any]) -> datetime | None:
        for key in ["timestamp", "created_at", "reviewed_at"]:
            parsed = self._parse_receipt_time(data.get(key))
            if parsed is not None:
                return parsed
        return None

    def _text_sha256_candidates(self, text: str) -> set[str]:
        candidates = {text.encode("utf-8")}
        candidates.add(text.replace("\n", "\r\n").encode("utf-8"))
        return {hashlib.sha256(item).hexdigest() for item in candidates}

    def _candidate_zettel_texts(self, frontmatter: dict[str, Any], body: str) -> list[str]:
        dumped = dump_yaml(frontmatter)
        no_blank = "---\n" + dumped + "---\n" + body
        with_blank = "---\n" + dumped + "---\n\n" + body.rstrip() + "\n"
        return list(dict.fromkeys([no_blank, with_blank]))

    def _edge_receipts_for_source(self, source_relative: str) -> list[dict[str, Any]]:
        if self.edge_receipts_by_source is None:
            self.edge_receipts_by_source = archive_services.edge_receipts_by_source(self.archive_root)
        return self.edge_receipts_by_source.get(source_relative, [])

    def _target_sha_evolved_by_edge_receipts(
        self,
        receipt_data: dict[str, Any],
        target_path: Path,
        expected_sha: str,
    ) -> bool:
        try:
            target_relative = archive_relative_path(target_path, self.archive_root)
        except (ArchivePathError, OSError, ValueError):
            return False
        return archive_services.target_sha_evolved_by_edge_receipts(
            self.archive_root,
            receipt_data,
            target_path,
            expected_sha,
            edge_receipts=self._edge_receipts_for_source(target_relative),
        )

    def _scope_includes_relative(self, relative: str, selected: set[str]) -> bool:
        return not self.validate_scope.active() or relative in selected

    def _indexed_zettel_cache_for_path(self, path: Path) -> dict[str, Any] | None:
        if not self.use_zettel_index_cache:
            return None
        try:
            relative = archive_relative_path(path, self.archive_root)
        except (ArchivePathError, OSError, ValueError):
            return None
        if relative in self._zettel_index_cache:
            return self._zettel_index_cache[relative]
        self._zettel_index_cache[relative] = None
        db_path = self.archive_root / archive_services.INDEX_RELATIVE_PATH
        if not db_path.is_file():
            return None
        try:
            stat = path.stat()
            conn = archive_services.connect_archive_index(db_path, row_factory=True)
            try:
                row = conn.execute(
                    """
                    SELECT frontmatter_json, file_size, file_mtime_ns, body_sha256,
                           approved_body_sha256, forbidden_location_reference_found
                    FROM zettels
                    WHERE path = ?
                    """,
                    (relative,),
                ).fetchone()
            finally:
                conn.close()
        except (OSError, sqlite3.Error):
            return None
        if row is None:
            return None
        try:
            file_size = int(row["file_size"])
            file_mtime_ns = int(row["file_mtime_ns"])
        except (TypeError, ValueError):
            return None
        if file_size != stat.st_size or file_mtime_ns != stat.st_mtime_ns:
            return None
        try:
            frontmatter = json.loads(str(row["frontmatter_json"] or ""))
        except json.JSONDecodeError:
            return None
        if not isinstance(frontmatter, dict):
            return None
        cached = {
            "frontmatter": frontmatter,
            "body_sha256": row["body_sha256"],
            "approved_body_sha256": row["approved_body_sha256"],
            "forbidden_location_reference_found": bool(row["forbidden_location_reference_found"]),
        }
        self._zettel_index_cache[relative] = cached
        return cached

    def _check_required_structure(self) -> None:
        for relative in REQUIRED_ARCHIVE_DIRS:
            path = self.archive_root / relative
            if not path.is_dir():
                self.error("required_directory_missing", f"Required directory is missing: {relative}", path)

        for relative in REQUIRED_ARCHIVE_FILES:
            path = self.archive_root / relative
            if not path.is_file():
                self.error("required_file_missing", f"Required file is missing: {relative}", path)

    def _check_archive_root_boundaries(self) -> None:
        for item in archive_services.archive_development_artifact_warnings(self.archive_root):
            self.warn(item["code"], item["message"], self.archive_root / item["path"])
        for item in archive_services.archive_git_marker_warnings(self.archive_root):
            self.warn(item["code"], item["message"], self.archive_root / item["path"])
        for item in archive_services.archive_objet_store_layout_and_git_exposure_warnings(self.archive_root):
            # `path` is an archive-relative name or a bare store basename;
            # never join-and-echo an absolute path for sibling stores, and
            # bypass `_display_path` (its resolve() is CWD-dependent and would
            # mangle the bare name when doctor runs from inside the archive).
            self.diagnostics.append(Diagnostic("WARN", item["code"], item["message"], item["path"]))

    def _check_v02_recommendations(self) -> None:
        for relative in RECOMMENDED_V02_FILES:
            path = self.archive_root / relative
            if not path.is_file():
                self.warn("v02_file_missing", f"Recommended v0.2 file is missing: {relative}", path)

    def _check_archive_yml(self) -> None:
        path = self.archive_root / "archive.yml"
        data = self._load_yaml_file(path)
        if not isinstance(data, dict):
            return
        self.archive_config = data
        self._check_schema(data, "archive.schema.json", path)

        for field in [
            "archive_id",
            "name",
            "type",
            "principal",
            "root_policy",
            "ai_write_policy",
            "storage_policy",
        ]:
            if field not in data:
                self.error("archive_field_missing", f"archive.yml missing required field: {field}", path)

        root_policy = data.get("root_policy") or {}
        if isinstance(root_policy, dict):
            for key, default_relative in [
                ("canonical_zettels", "zettels/"),
                ("ai_inbox", "inbox/"),
                ("views", "views/"),
                ("object_manifest", "objects/manifests/files.jsonl"),
                ("sqlite_schema", "db/schema.sql"),
            ]:
                relative = root_policy.get(key, default_relative)
                try:
                    policy_path = resolve_archive_relative_path(self.archive_root, str(relative))
                except ArchivePathError as exc:
                    self.error("root_policy_path_unsafe", f"root_policy.{key} has an unsafe path: {relative} ({exc})", path)
                    continue
                if not policy_path.exists():
                    self.error("root_policy_path_missing", f"root_policy.{key} points to a missing path: {relative}", path)
            if "derived_text_manifest" in root_policy:
                relative = root_policy.get("derived_text_manifest")
                try:
                    policy_path = resolve_archive_relative_path(self.archive_root, str(relative))
                except ArchivePathError as exc:
                    self.error(
                        "root_policy_path_unsafe",
                        f"root_policy.derived_text_manifest has an unsafe path: {relative} ({exc})",
                        path,
                    )
                else:
                    if not policy_path.exists():
                        self.error(
                            "root_policy_path_missing",
                            f"root_policy.derived_text_manifest points to a missing path: {relative}",
                            path,
                        )

        ai_policy = data.get("ai_write_policy") or {}
        if isinstance(ai_policy, dict):
            if ai_policy.get("default") != "inbox_only":
                self.warn("unsafe_ai_write_default", "ai_write_policy.default should be inbox_only.", path)
            if ai_policy.get("canonical_requires") not in CANONICAL_REQUIRES_VALUES:
                self.warn(
                    "unsafe_minting_policy",
                    "ai_write_policy.canonical_requires should be human_minting. Legacy human_promotion is also accepted.",
                    path,
                )

        storage_policy = data.get("storage_policy") or {}
        if isinstance(storage_policy, dict):
            if storage_policy.get("object_identity") != "sha256":
                self.error("object_identity_policy", "storage_policy.object_identity must be sha256.", path)
            if storage_policy.get("provider_urls_in_zettels") != "forbidden":
                self.error("provider_url_policy", "storage_policy.provider_urls_in_zettels must be forbidden.", path)

    def _check_archive_identity_yml(self) -> None:
        path = self.archive_root / "archive-identity.yml"
        data = self._load_yaml_file(path)
        if not isinstance(data, dict):
            return
        self._check_schema(data, "archive-identity.schema.json", path)
        identity = data.get("identity") if isinstance(data.get("identity"), dict) else {}
        archive_id = identity.get("archive_id")
        if self.archive_config and archive_id != self.archive_config.get("archive_id"):
            self.error("archive_identity_mismatch", "archive-identity.yml identity.archive_id must match archive.yml archive_id.", path)
        scope = identity.get("scope")
        if scope and scope != self.archive_config.get("type"):
            self.warn("archive_identity_scope_mismatch", "archive-identity.yml identity.scope should match archive.yml type.", path)

    def _check_provider_bindings_yml(self) -> None:
        path = self.archive_root / "provider-bindings.yml"
        data = self._load_yaml_file(path)
        if not isinstance(data, dict):
            return
        self._check_schema(data, "provider-bindings.schema.json", path)
        archive_id = data.get("archive_id")
        if self.archive_config and archive_id != self.archive_config.get("archive_id"):
            self.error("provider_bindings_archive_mismatch", "provider-bindings.yml archive_id must match archive.yml archive_id.", path)
        self._check_provider_binding_secret_refs(data, path)

    def _check_provider_binding_secret_refs(self, value: Any, path: Path, field_path: str = "$") -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                child_path = f"{field_path}.{key}"
                if self._is_provider_secret_field(str(key)) and not str(key).endswith("_env"):
                    if isinstance(child, str) and child.strip():
                        self.error(
                            "provider_bindings_secret_field",
                            f"Provider binding field should reference an env var or keyring entry, not store a secret-like value: {child_path}",
                            path,
                        )
                self._check_provider_binding_secret_refs(child, path, child_path)
            return
        if isinstance(value, list):
            for index, child in enumerate(value):
                self._check_provider_binding_secret_refs(child, path, f"{field_path}[{index}]")
            return
        if isinstance(value, str) and contains_secret_value(f"value: {value}"):
            self.error(
                "provider_bindings_secret_value",
                f"Provider binding appears to contain a secret-like value at {field_path}. Use an *_env or keyring reference instead.",
                path,
            )

    def _check_source_bindings_yml(self) -> None:
        path = self.archive_root / "source-bindings.yml"
        data = self._load_yaml_file(path)
        if not isinstance(data, dict):
            return
        self._check_schema(data, "source-bindings.schema.json", path)
        archive_id = data.get("archive_id")
        if self.archive_config and archive_id != self.archive_config.get("archive_id"):
            self.error("source_bindings_archive_mismatch", "source-bindings.yml archive_id must match archive.yml archive_id.", path)
        sources = data.get("sources") if isinstance(data.get("sources"), list) else []
        seen: set[str] = set()
        for index, source in enumerate(sources):
            if not isinstance(source, dict):
                self.error("source_binding_invalid", f"source-bindings.yml sources[{index}] must be an object.", path)
                continue
            source_id = source.get("source_id")
            if not isinstance(source_id, str) or not source_id.strip():
                self.error("source_binding_id_missing", f"source-bindings.yml sources[{index}] missing source_id.", path)
            elif source_id in seen:
                self.error("source_binding_id_duplicate", f"Duplicate source_id in source-bindings.yml: {source_id}", path)
            else:
                seen.add(source_id)
            source_type = source.get("source_type")
            if source_type not in archive_services.SOURCE_TYPES:
                self.error("source_binding_type_invalid", f"Invalid source_type in source-bindings.yml: {source_type}", path)
            root_ref = source.get("root_ref")
            if not isinstance(root_ref, str) or not root_ref.strip():
                self.error("source_binding_root_ref_missing", f"Source binding missing root_ref: {source_id}", path)
            else:
                self._check_source_ref_is_portable(root_ref, path, f"sources[{index}].root_ref")
            self._check_source_binding_secret_refs(source, path, f"$.sources[{index}]")

    def _check_source_ref_is_portable(self, value: str, path: Path, field_path: str) -> None:
        if value.startswith("archive:"):
            try:
                resolve_archive_relative_path(self.archive_root, value.removeprefix("archive:"))
            except ArchivePathError as exc:
                self.error("source_binding_archive_ref_unsafe", f"{field_path} has an unsafe archive ref: {value} ({exc})", path)
            return
        if contains_forbidden_location_reference(value) or self._looks_like_absolute_path(value):
            self.error(
                "source_binding_sensitive_path",
                f"{field_path} should store an env/keyring/root ref, not an absolute path or provider URL.",
                path,
            )

    def _check_source_binding_secret_refs(self, value: Any, path: Path, field_path: str = "$") -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                child_path = f"{field_path}.{key}"
                if self._is_source_secret_field(str(key)) and not str(key).endswith("_ref") and not str(key).endswith("_env"):
                    if isinstance(child, str) and child.strip():
                        self.error(
                            "source_bindings_secret_field",
                            f"Source binding field should reference an env var or keyring entry, not store a secret-like value: {child_path}",
                            path,
                        )
                self._check_source_binding_secret_refs(child, path, child_path)
            return
        if isinstance(value, list):
            for index, child in enumerate(value):
                self._check_source_binding_secret_refs(child, path, f"{field_path}[{index}]")
            return
        if isinstance(value, str) and contains_secret_value(f"value: {value}"):
            self.error(
                "source_bindings_secret_value",
                f"Source binding appears to contain a secret-like value at {field_path}. Use an env/keyring reference instead.",
                path,
            )

    def _is_source_secret_field(self, key: str) -> bool:
        normalized = key.lower()
        return normalized in {"token", "api_token", "secret", "password", "credential", "credentials", "database_url"}

    def _looks_like_absolute_path(self, value: str) -> bool:
        normalized = value.strip().replace("\\", "/")
        return bool(re.match(r"^[A-Za-z]:/", normalized)) or normalized.startswith("/") or normalized.startswith("//")

    def _is_provider_secret_field(self, key: str) -> bool:
        normalized = key.lower()
        return normalized in {
            "token",
            "api_token",
            "secret",
            "password",
            "credential",
            "credentials",
            "access_key_id",
            "secret_access_key",
            "application_key",
            "database_url",
        }

    def _check_sqlite_schema(self) -> None:
        path = self.archive_root / "db" / "schema.sql"
        if not path.is_file():
            return
        try:
            sql = path.read_text(encoding="utf-8")
            conn = sqlite3.connect(":memory:")
            try:
                conn.executescript(sql)
            finally:
                conn.close()
        except sqlite3.Error as exc:
            self.error("sqlite_schema_invalid", f"SQLite schema failed to parse: {exc}", path)

    def _check_object_manifest(self) -> None:
        path = self.archive_root / "objects" / "manifests" / "files.jsonl"
        if not path.is_file():
            return

        for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            line = raw_line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                self.error("object_manifest_json_invalid", f"Invalid JSON on line {line_number}: {exc}", path)
                continue
            self._check_schema(record, "object-manifest-entry.schema.json", path)

            object_id = record.get("object_id")
            sha256 = record.get("sha256")
            if not isinstance(object_id, str) or not OBJECT_ID_RE.match(object_id):
                self.error("object_id_invalid", f"Invalid object_id on line {line_number}: {object_id}", path)
                continue
            if not isinstance(sha256, str) or not SHA256_RE.match(sha256):
                self.error("sha256_invalid", f"Invalid sha256 on line {line_number}: {sha256}", path)
            if isinstance(sha256, str) and object_id != f"sha256:{sha256}":
                self.error("object_id_sha_mismatch", f"object_id and sha256 mismatch on line {line_number}.", path)
            if object_id in self.manifest_objects:
                self.error("object_id_duplicate", f"Duplicate object_id in manifest: {object_id}", path)
            self.manifest_objects[object_id] = record

            if "logical_key" not in record:
                self.error("object_logical_key_missing", f"Object missing logical_key: {object_id}", path)
            if "locations" not in record or not isinstance(record.get("locations"), list):
                self.warn("object_locations_missing", f"Object has no locations list: {object_id}", path)

            self._check_local_object_locations(record, path)

    def _check_derived_text_manifest(self) -> None:
        path = self.archive_root / archive_services.DERIVED_TEXT_MANIFEST_RELATIVE_PATH
        if not path.is_file():
            return

        seen: set[str] = set()
        for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            line = raw_line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                self.error("derived_text_manifest_json_invalid", f"Invalid JSON on line {line_number}: {exc}", path)
                continue
            if not isinstance(record, dict):
                self.error("derived_text_record_invalid", f"Derived text line {line_number} must be a JSON object.", path)
                continue
            self._check_schema(record, "derived-text-record.schema.json", path)

            derived_text_id = record.get("derived_text_id")
            if not isinstance(derived_text_id, str) or not DERIVED_TEXT_ID_RE.match(derived_text_id):
                self.error("derived_text_id_invalid", f"Invalid derived_text_id on line {line_number}: {derived_text_id}", path)
            elif derived_text_id in seen:
                self.error("derived_text_id_duplicate", f"Duplicate derived_text_id: {derived_text_id}", path)
            else:
                seen.add(derived_text_id)

            source_object_id = record.get("source_object_id")
            if not isinstance(source_object_id, str) or not OBJECT_ID_RE.match(source_object_id):
                self.error("derived_text_source_object_id_invalid", f"Invalid source_object_id on line {line_number}: {source_object_id}", path)
            elif self.manifest_objects and source_object_id not in self.manifest_objects:
                self.error("derived_text_source_object_missing", f"Derived text source object is not in files.jsonl: {source_object_id}", path)

            derivation_kind = record.get("derivation_kind")
            if derivation_kind not in archive_services.DERIVED_TEXT_DERIVATION_KINDS:
                self.error("derived_text_derivation_kind_invalid", f"Invalid derivation_kind on line {line_number}: {derivation_kind}", path)
            review_status = record.get("review_status")
            if review_status not in archive_services.DERIVED_TEXT_REVIEW_STATUSES:
                self.error("derived_text_review_status_invalid", f"Invalid review_status on line {line_number}: {review_status}", path)

            text_sha256 = record.get("text_sha256")
            if not isinstance(text_sha256, str) or not SHA256_RE.match(text_sha256):
                self.error("derived_text_sha256_invalid", f"Invalid text_sha256 on line {line_number}: {text_sha256}", path)
            text_logical_key = record.get("text_logical_key")
            if not isinstance(text_logical_key, str) or not text_logical_key:
                self.error("derived_text_logical_key_missing", f"Derived text missing text_logical_key: {derived_text_id}", path)
            else:
                try:
                    text_path = resolve_archive_relative_path(self.archive_root, text_logical_key)
                except ArchivePathError as exc:
                    self.error("derived_text_path_unsafe", f"Derived text path is unsafe: {text_logical_key} ({exc})", path)
                else:
                    if text_path.is_file() and isinstance(text_sha256, str) and SHA256_RE.match(text_sha256):
                        actual_sha = sha256_file(text_path)
                        if actual_sha != text_sha256:
                            self.error("derived_text_sha_mismatch", f"Derived text SHA-256 mismatch: {text_logical_key}", text_path)
                    elif not text_path.is_file():
                        self.warn("derived_text_body_missing", f"Derived text body file is missing: {text_logical_key}", text_path)

    def _check_local_object_locations(self, record: dict[str, Any], manifest_path: Path) -> None:
        object_id = record.get("object_id")
        expected_sha = record.get("sha256")
        expected_size = record.get("size_bytes")
        locations = record.get("locations") or []
        if not isinstance(locations, list):
            return

        for location in locations:
            if not isinstance(location, dict):
                self.warn("object_location_invalid", f"Object location is not an object: {object_id}", manifest_path)
                continue
            if location.get("provider") != "local":
                continue
            relative_path = location.get("path")
            if not isinstance(relative_path, str):
                self.warn("local_object_path_missing", f"Local object location missing path: {object_id}", manifest_path)
                continue
            try:
                local_path = resolve_archive_relative_path(self.archive_root, relative_path)
            except ArchivePathError as exc:
                self.error("local_object_path_unsafe", f"Local object location has an unsafe path: {relative_path} ({exc})", manifest_path)
                continue
            if not local_path.is_file():
                self.warn("local_object_missing", f"Local object file is missing: {relative_path}", local_path)
                continue
            if isinstance(expected_size, int) and local_path.stat().st_size != expected_size:
                self.error("local_object_size_mismatch", f"Local object size mismatch: {relative_path}", local_path)
            if isinstance(expected_sha, str):
                actual_sha = sha256_file(local_path)
                if actual_sha != expected_sha:
                    self.error("local_object_sha_mismatch", f"Local object SHA-256 mismatch: {relative_path}", local_path)

    def _check_source_maps(self) -> None:
        root = self.archive_root / "source-maps"
        if not root.is_dir():
            return
        known_sources = self._known_source_ids()
        seen_items: set[str] = set()
        for path in sorted(root.glob("*.jsonl")):
            if not self._path_stays_inside_archive(path):
                continue
            for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError as exc:
                    self.error("source_map_json_invalid", f"Invalid JSON on line {line_number}: {exc}", path)
                    continue
                if not isinstance(record, dict):
                    self.error("source_map_entry_invalid", f"Source map line {line_number} must be a JSON object.", path)
                    continue
                self._check_schema(record, "source-map-entry.schema.json", path)
                source_id = record.get("source_id")
                if known_sources and source_id not in known_sources:
                    self.error("source_map_unknown_source", f"Source map references unknown source_id: {source_id}", path)
                item_id = record.get("item_id")
                if isinstance(item_id, str):
                    if item_id in seen_items:
                        self.error("source_map_item_duplicate", f"Duplicate source map item_id: {item_id}", path)
                    seen_items.add(item_id)
                relative_path = record.get("relative_path")
                if isinstance(relative_path, str) and self._relative_source_path_is_unsafe(relative_path):
                    self.error("source_map_relative_path_unsafe", f"Source map relative_path is unsafe: {relative_path}", path)
                if not relative_path and not record.get("external_url") and not record.get("object_id"):
                    self.error("source_map_location_missing", "Source map entry needs relative_path, external_url, or object_id.", path)

    def _known_source_ids(self) -> set[str]:
        path = self.archive_root / "source-bindings.yml"
        data = self._load_yaml_file(path, missing_ok=True)
        if not isinstance(data, dict):
            return set()
        sources = data.get("sources") if isinstance(data.get("sources"), list) else []
        return {item.get("source_id") for item in sources if isinstance(item, dict) and isinstance(item.get("source_id"), str)}

    def _relative_source_path_is_unsafe(self, value: str) -> bool:
        normalized = value.replace("\\", "/").strip()
        return (
            not normalized
            or normalized.startswith("/")
            or normalized.startswith("//")
            or bool(re.match(r"^[A-Za-z]:/", normalized))
            or ".." in normalized.split("/")
        )

    def _check_zettels(self) -> None:
        for folder, expected_status in [("zettels", "canonical"), ("inbox", "draft")]:
            root = self.archive_root / folder
            if not root.is_dir():
                continue
            paths = []
            for path in sorted(root.rglob("*.md")):
                if not self._path_stays_inside_archive(path):
                    continue
                try:
                    relative = archive_relative_path(path, self.archive_root)
                except (ArchivePathError, OSError, ValueError):
                    continue
                if not self._scope_includes_relative(relative, self.validate_scope.zettel_paths):
                    continue
                paths.append(path)
            total = len(paths)
            for index, path in enumerate(paths, start=1):
                if index == 1 or index == total or index % 250 == 0:
                    self._progress("zettels", self._display_path(path) or "zettel", index, total)
                self._check_zettel_file(path, expected_status)

    def _check_zettel_file(self, path: Path, expected_status: str) -> None:
        cached = self._indexed_zettel_cache_for_path(path)
        if cached is not None:
            data = cached["frontmatter"]
            if cached.get("forbidden_location_reference_found"):
                self.error("provider_url_in_zettel", "Zettel appears to contain a provider URL or local absolute path.", path)
        else:
            text = path.read_text(encoding="utf-8")
            if contains_forbidden_location_reference(text):
                self.error("provider_url_in_zettel", "Zettel appears to contain a provider URL or local absolute path.", path)

            frontmatter = parse_frontmatter(text)
            if frontmatter is None:
                self.error("zettel_frontmatter_missing", "Zettel is missing YAML frontmatter.", path)
                return

            data = self._load_yaml_text(frontmatter, path)
            if not isinstance(data, dict):
                self.error("zettel_frontmatter_invalid", "Zettel frontmatter must be a YAML object.", path)
                return
            self._warn_unquoted_yaml_timestamps(data, path)
        self._check_schema(data, "zettel-frontmatter.schema.json", path)

        for field in REQUIRED_ZETTEL_FIELDS:
            if field not in data:
                self.error("zettel_field_missing", f"Zettel missing required frontmatter field: {field}", path)

        status = data.get("status")
        if status not in ALLOWED_ZETTEL_STATUS:
            self.error("zettel_status_invalid", f"Invalid zettel status: {status}", path)
        elif status != expected_status:
            self.warn("zettel_status_path_mismatch", f"Zettel in {path.parent.name}/ has status {status}, expected {expected_status}.", path)

        minted_draft_twin = None
        displayed_path = self._display_path(path) or ""
        if expected_status == "draft" and displayed_path.startswith("inbox/"):
            minted_draft_twin = archive_services.is_minted_inbox_draft_twin(self.archive_root, path)
            if minted_draft_twin:
                self.info(
                    "minted_inbox_draft_twin_pending_retire",
                    "Inbox draft is already backed by canonical mint artifacts and can be closed with retire-draft.",
                    path,
                )

        if expected_status == "canonical" and "mint" not in data and "promotion" not in data:
            self.warn("canonical_lifecycle_metadata_missing", "Canonical zettel has no mint or v0.2 promotion metadata.", path)
        if "mint" in data and not minted_draft_twin:
            self._check_zettel_mint_metadata(data, path)
        if "kind" not in data:
            self.warn("zettel_kind_missing", "Zettel has no v0.2 kind field.", path)

        self._check_zettel_assets(data, path)
        self._check_zettel_edges(data, path)

    def _check_zettel_mint_metadata(self, data: dict[str, Any], path: Path) -> None:
        mint = data.get("mint")
        if not isinstance(mint, dict):
            self.error("mint_metadata_invalid", "Zettel mint metadata must be an object.", path)
            return
        if mint.get("stage") != "minted":
            self.error("mint_stage_invalid", "Zettel mint.stage must be minted.", path)
        if mint.get("authority_mode") != archive_services.MINT_AUTHORITY_MODE:
            self.error("mint_authority_mode_invalid", "Zettel mint.authority_mode must be basic in the current v0.2 line.", path)
        for field in ["minted_at", "reviewed_by", "receipt_path", "draft_snapshot_path", "checklist_version"]:
            if not mint.get(field):
                self.error("mint_metadata_field_missing", f"Zettel mint metadata missing field: {field}.", path)

        receipt_path = self._resolve_archive_file_ref(
            mint.get("receipt_path"),
            path,
            code_prefix="mint_receipt",
            label="Zettel mint.receipt_path",
            required=True,
        )
        if receipt_path and receipt_path.suffix != ".json":
            self.error("mint_receipt_path_invalid", "Zettel mint.receipt_path must point to a JSON receipt.", path)
        if receipt_path and receipt_path.is_file():
            receipt = self._load_json_file(receipt_path)
            if isinstance(receipt, dict):
                expected_target = self._display_path(path)
                actual_target = receipt.get("target", {}).get("path") if isinstance(receipt.get("target"), dict) else None
                if actual_target != expected_target:
                    self.error(
                        "mint_receipt_target_mismatch",
                        "Zettel mint receipt target.path does not point back to this zettel.",
                        path,
                    )
                receipt_zettel = receipt.get("zettel") if isinstance(receipt.get("zettel"), dict) else {}
                if receipt_zettel.get("id") != data.get("id"):
                    self.error("mint_receipt_zettel_mismatch", "Zettel mint receipt zettel.id does not match this zettel id.", path)

        self._resolve_archive_file_ref(
            mint.get("draft_snapshot_path"),
            path,
            code_prefix="mint_snapshot",
            label="Zettel mint.draft_snapshot_path",
            required=True,
        )

    def _check_zettel_assets(self, data: dict[str, Any], path: Path) -> None:
        assets = data.get("assets") or []
        if not isinstance(assets, list):
            self.error("zettel_assets_invalid", "Zettel assets must be a list.", path)
            return
        for asset in assets:
            if not isinstance(asset, dict):
                self.error("zettel_asset_invalid", "Zettel asset must be an object.", path)
                continue
            object_id = asset.get("object_id")
            if not isinstance(object_id, str) or not OBJECT_ID_RE.match(object_id):
                self.error("zettel_asset_object_id_invalid", f"Invalid asset object_id: {object_id}", path)
                continue
            if self.manifest_objects and object_id not in self.manifest_objects:
                self.warn("zettel_asset_missing_manifest_record", f"Asset object_id not found in manifest: {object_id}", path)

    def _check_zettel_edges(self, data: dict[str, Any], path: Path) -> None:
        edges = data.get("edges") or []
        if not isinstance(edges, list):
            self.error("zettel_edges_invalid", "Zettel edges must be a list.", path)
            return
        for edge in edges:
            if not isinstance(edge, dict):
                self.error("zettel_edge_invalid", "Zettel edge must be an object.", path)
                continue
            edge_type = edge.get("type")
            if edge_type and self.allowed_link_types and edge_type not in self.allowed_link_types:
                self.warn("zettel_edge_type_unknown", f"Edge type is not defined in zettel-kasten/types.yml: {edge_type}", path)

    def _check_views(self) -> None:
        root = self.archive_root / "views"
        if not root.is_dir():
            return
        for path in sorted(root.glob("*.yml")):
            if not self._path_stays_inside_archive(path):
                continue
            data = self._load_yaml_file(path)
            if isinstance(data, dict):
                self._check_schema(data, "view.schema.json", path)

    def _check_workpacks(self) -> None:
        root = self.archive_root / "workpacks"
        if not root.is_dir():
            return
        for path in sorted(root.glob("*/package.yml")):
            if not self._path_stays_inside_archive(path):
                continue
            data = self._load_yaml_file(path)
            if isinstance(data, dict):
                self._check_schema(data, "workpack.schema.json", path)

    def _check_external_import_receipts(self) -> None:
        root = self.archive_root / "receipts" / "import"
        if not root.is_dir():
            return
        for path in sorted(root.glob("*.external-import.json")):
            if not self._path_stays_inside_archive(path):
                continue
            data = self._load_json_file(path)
            if not isinstance(data, dict):
                continue
            self._check_schema(data, "external-import-receipt.schema.json", path)
            if data.get("action") != "import_external_archive":
                self.error(
                    "external_import_receipt_action_invalid",
                    "External import receipt action must be import_external_archive.",
                    path,
                )
            for field in ["source_export", "scope_gate", "trust_gate", "lineage"]:
                if not isinstance(data.get(field), dict):
                    self.error(
                        "external_import_receipt_field_missing",
                        f"External import receipt must contain object field: {field}.",
                        path,
                    )

    def _check_source_scan_receipts(self) -> None:
        root = self.archive_root / "receipts" / "sources"
        if not root.is_dir():
            return
        for path in sorted(root.glob("*.source-scan.json")):
            if not self._path_stays_inside_archive(path):
                continue
            data = self._load_json_file(path)
            if not isinstance(data, dict):
                continue
            self._check_schema(data, "source-scan-receipt.schema.json", path)
            if data.get("action") != "scan_archive_source":
                self.error(
                    "source_scan_receipt_action_invalid",
                    "Source scan receipt action must be scan_archive_source.",
                    path,
                )
            for field in ["scope_gate", "trust_gate", "lineage", "source_root_resolution"]:
                if not isinstance(data.get(field), dict):
                    self.error(
                        "source_scan_receipt_field_missing",
                        f"Source scan receipt must contain object field: {field}.",
                        path,
                    )

    def _check_recovery_receipts(self) -> None:
        root = self.archive_root / "receipts" / "recovery"
        if not root.is_dir():
            return
        for path in sorted(root.glob("*.restore-drill.json")):
            if not self._path_stays_inside_archive(path):
                continue
            data = self._load_json_file(path)
            if not isinstance(data, dict):
                continue
            self._check_schema(data, "restore-drill-receipt.schema.json", path)
            if data.get("action") != "restore_drill":
                self.error(
                    "restore_drill_receipt_action_invalid",
                    "Restore drill receipt action must be restore_drill.",
                    path,
                )
            for field in ["copy_plan", "validation", "result"]:
                if not isinstance(data.get(field), dict):
                    self.error(
                        "restore_drill_receipt_field_missing",
                        f"Restore drill receipt must contain object field: {field}.",
                        path,
                    )

    def _check_lineage_receipts(self) -> None:
        root = self.archive_root / "receipts" / "lineage"
        if not root.is_dir():
            return
        for path in sorted(root.glob("*.ownership-transfer.json")):
            if not self._path_stays_inside_archive(path):
                continue
            data = self._load_json_file(path)
            if not isinstance(data, dict):
                continue
            self._check_schema(data, "ownership-transfer-receipt.schema.json", path)
            if data.get("action") != "transfer_archive_ownership":
                self.error(
                    "ownership_transfer_receipt_action_invalid",
                    "Ownership transfer receipt action must be transfer_archive_ownership.",
                    path,
                )
            for field in ["scope_manifest", "trust_gate", "ownership_gate"]:
                if not isinstance(data.get(field), dict):
                    self.error(
                        "ownership_transfer_receipt_gate_missing",
                        f"Ownership transfer receipt must contain object field: {field}.",
                        path,
                    )

    def _check_mint_receipts(self) -> None:
        root = self.archive_root / "receipts" / "mint"
        if not root.is_dir():
            return
        paths = []
        for path in sorted(root.glob("*.mint.json")):
            if not self._path_stays_inside_archive(path):
                continue
            relative = self._display_path(path) or ""
            if not self._scope_includes_relative(relative, self.validate_scope.mint_receipt_paths):
                continue
            paths.append(path)
        total = len(paths)
        for index, path in enumerate(paths, start=1):
            if index == 1 or index == total or index % 250 == 0:
                self._progress("mint-receipts", self._display_path(path) or "mint receipt", index, total)
            data = self._load_json_file(path)
            if not isinstance(data, dict):
                continue
            self._check_schema(data, "mint-receipt.schema.json", path)
            if data.get("action") != "mint_zettel":
                self.error("mint_receipt_action_invalid", "Mint receipt action must be mint_zettel.", path)
            if data.get("authority_mode") != archive_services.MINT_AUTHORITY_MODE:
                self.error("mint_receipt_authority_mode_invalid", "Mint receipt authority_mode must be basic in the current v0.2 line.", path)
            if data.get("dry_run") is False and not data.get("reviewed_by"):
                self.error("mint_receipt_reviewer_missing", "Applied mint receipt must include reviewed_by.", path)
            for field in ["source", "target", "snapshot", "zettel", "result"]:
                if not isinstance(data.get(field), dict):
                    self.error("mint_receipt_field_missing", f"Mint receipt must contain object field: {field}.", path)

            self._check_mint_receipt_status(data, path, "source", "draft")
            self._check_mint_receipt_status(data, path, "target", "canonical")
            if not self._mint_receipt_source_is_retired(data, path):
                self._check_mint_receipt_file_ref(data, path, "source")
            target_path = self._check_mint_receipt_file_ref(data, path, "target")
            self._check_mint_receipt_file_ref(data, path, "snapshot")

            if target_path is not None:
                frontmatter = parse_frontmatter(target_path.read_text(encoding="utf-8-sig"))
                if frontmatter is None:
                    self.error("mint_receipt_target_frontmatter_missing", "Mint receipt target has no zettel frontmatter.", path)
                    continue
                # R7: BOM stays visible. A UTF-8 BOM is real byte drift that also
                # drifts the mint-receipt sha, so name the cause as a WARN advisory
                # (not info, which doctor filters out of --strict).
                try:
                    if target_path.read_bytes().startswith(b"\xef\xbb\xbf"):
                        self.warn(
                            "zettel_has_bom",
                            "File has a UTF-8 BOM; WOM does not write BOMs. Run archive remint-reconcile after confirming content.",
                            target_path,
                        )
                except OSError:
                    pass
                target_data = self._load_yaml_text(frontmatter, target_path)
                if not isinstance(target_data, dict):
                    continue
                mint = target_data.get("mint") if isinstance(target_data.get("mint"), dict) else {}
                receipt_relative = self._display_path(path)
                if mint.get("receipt_path") != receipt_relative:
                    self.error(
                        "mint_receipt_canonical_link_missing",
                        "Mint receipt target zettel does not link back through mint.receipt_path.",
                        path,
                    )

    def _mint_receipt_source_is_retired(self, data: dict[str, Any], path: Path) -> bool:
        zettel = data.get("zettel") if isinstance(data.get("zettel"), dict) else {}
        zettel_id = zettel.get("id")
        if not isinstance(zettel_id, str) or not zettel_id:
            return False
        retire_path = self.archive_root / archive_services.MINT_RETIRED_DRAFT_RECEIPTS_DIR / f"{zettel_id}.retire-draft.json"
        if not retire_path.is_file() or not self._path_stays_inside_archive(retire_path):
            return False
        receipt = self._load_json_file(retire_path)
        if not isinstance(receipt, dict):
            return False
        mint_receipt = receipt.get("mint_receipt") if isinstance(receipt.get("mint_receipt"), dict) else {}
        return receipt.get("action") == "retire_minted_draft" and mint_receipt.get("path") == self._display_path(path)

    def _check_retired_draft_receipts(self) -> None:
        root = self.archive_root / archive_services.MINT_RETIRED_DRAFT_RECEIPTS_DIR
        if not root.is_dir():
            return
        paths = []
        for path in sorted(root.glob("*.retire-draft.json")):
            if not self._path_stays_inside_archive(path):
                continue
            relative = self._display_path(path) or ""
            if not self._scope_includes_relative(relative, self.validate_scope.retired_draft_receipt_paths):
                continue
            paths.append(path)
        total = len(paths)
        for index, path in enumerate(paths, start=1):
            if index == 1 or index == total or index % 250 == 0:
                self._progress("retired-draft-receipts", self._display_path(path) or "retired draft receipt", index, total)
            data = self._load_json_file(path)
            if not isinstance(data, dict):
                continue
            self._check_schema(data, "mint-retired-draft-receipt.schema.json", path)
            if data.get("action") != "retire_minted_draft":
                self.error("mint_retired_draft_action_invalid", "Retired draft receipt action must be retire_minted_draft.", path)
            if data.get("authority_mode") != archive_services.MINT_AUTHORITY_MODE:
                self.error("mint_retired_draft_authority_mode_invalid", "Retired draft receipt authority_mode must be basic.", path)
            if data.get("dry_run") is False and not data.get("reviewed_by"):
                self.error("mint_retired_draft_reviewer_missing", "Applied retired draft receipt must include reviewed_by.", path)
            if data.get("receipt_path") != self._display_path(path):
                self.error("mint_retired_draft_path_mismatch", "Retired draft receipt receipt_path must match its archive-relative path.", path)
            for field in ["source", "target", "mint_receipt", "snapshot", "zettel", "result"]:
                if not isinstance(data.get(field), dict):
                    self.error("mint_retired_draft_field_missing", f"Retired draft receipt must contain object field: {field}.", path)

            source = data.get("source") if isinstance(data.get("source"), dict) else {}
            source_path_value = source.get("path")
            if isinstance(source_path_value, str) and source_path_value:
                try:
                    source_path = resolve_archive_relative_path(self.archive_root, source_path_value)
                except ArchivePathError:
                    self.error("mint_retired_draft_source_path_invalid", "Retired draft receipt source.path is unsafe.", path)
                else:
                    if source_path.exists():
                        self.error("mint_retired_draft_source_still_exists", "Retired inbox draft still exists after retirement receipt.", path)

            self._check_retired_draft_existing_ref(data, path, "target")
            self._check_retired_draft_existing_ref(data, path, "mint_receipt")
            self._check_retired_draft_existing_ref(data, path, "snapshot")

    def _check_reconcile_receipts(self) -> None:
        root = self.archive_root / archive_services.MINT_RECONCILE_RECEIPTS_DIR
        if not root.is_dir():
            return
        paths = []
        for path in sorted(root.glob("*.reconcile*.json")):
            if not self._path_stays_inside_archive(path):
                continue
            paths.append(path)
        total = len(paths)
        for index, path in enumerate(paths, start=1):
            if index == 1 or index == total or index % 250 == 0:
                self._progress("reconcile-receipts", self._display_path(path) or "reconcile receipt", index, total)
            data = self._load_json_file(path)
            if not isinstance(data, dict):
                continue
            self._check_schema(data, "mint-reconcile-receipt.schema.json", path)
            if data.get("action") != "reconcile_mint_receipt":
                self.error("mint_reconcile_action_invalid", "Reconcile receipt action must be reconcile_mint_receipt.", path)
            if data.get("authority_mode") != archive_services.MINT_AUTHORITY_MODE:
                self.error("mint_reconcile_authority_mode_invalid", "Reconcile receipt authority_mode must be basic.", path)
            if data.get("dry_run") is not False:
                self.error("mint_reconcile_dry_run_invalid", "Applied reconcile receipt must have dry_run false.", path)
            if not data.get("reviewed_by"):
                self.error("mint_reconcile_reviewer_missing", "Applied reconcile receipt must include reviewed_by.", path)
            if data.get("receipt_path") != self._display_path(path):
                self.error("mint_reconcile_path_mismatch", "Reconcile receipt receipt_path must match its archive-relative path.", path)
            for field in ["zettel", "mint_receipt", "result"]:
                if not isinstance(data.get(field), dict):
                    self.error("mint_reconcile_field_missing", f"Reconcile receipt must contain object field: {field}.", path)

    def _check_scoped_edge_receipts(self) -> None:
        if not self.validate_scope.active() or not self.validate_scope.edge_receipt_paths:
            return
        paths = []
        for relative in sorted(self.validate_scope.edge_receipt_paths):
            try:
                path = resolve_archive_relative_path(self.archive_root, relative)
            except ArchivePathError:
                self.error("zettel_edge_receipt_path_unsafe", "Scoped zettel-edge receipt path is unsafe.", relative)
                continue
            if not path.is_file():
                self.error("zettel_edge_receipt_path_missing", "Scoped zettel-edge receipt is missing.", relative)
                continue
            paths.append(path)
        total = len(paths)
        for index, path in enumerate(paths, start=1):
            if index == 1 or index == total or index % 250 == 0:
                self._progress("scoped-edge-receipts", self._display_path(path) or "edge receipt", index, total)
            data = self._load_json_file(path)
            if not isinstance(data, dict):
                continue
            if data.get("receipt_kind") != "zettel_edge_write":
                self.error("zettel_edge_receipt_kind_invalid", "Zettel-edge receipt_kind must be zettel_edge_write.", path)
            for field in ["edge_id", "source_zettel_id", "source_zettel_path", "target_ref", "edge_type", "reviewed_by"]:
                if not isinstance(data.get(field), str) or not str(data.get(field) or "").strip():
                    self.error("zettel_edge_receipt_field_missing", f"Zettel-edge receipt missing field: {field}.", path)
            source_path_value = data.get("source_zettel_path")
            if isinstance(source_path_value, str) and source_path_value.strip():
                source_path = self._resolve_archive_file_ref(
                    source_path_value,
                    path,
                    code_prefix="zettel_edge_receipt_source",
                    label="Zettel-edge receipt source_zettel_path",
                    required=True,
                )
                if source_path is not None:
                    source_frontmatter = parse_frontmatter(source_path.read_text(encoding="utf-8"))
                    if source_frontmatter is not None:
                        source_data = self._load_yaml_text(source_frontmatter, source_path)
                        edges = source_data.get("edges") if isinstance(source_data, dict) else None
                        if isinstance(edges, list):
                            edge_id = data.get("edge_id")
                            receipt_relative = self._display_path(path)
                            if not any(
                                isinstance(edge, dict)
                                and edge.get("edge_id") == edge_id
                                and edge.get("receipt") == receipt_relative
                                for edge in edges
                            ):
                                self.error(
                                    "zettel_edge_receipt_source_link_missing",
                                    "Zettel-edge receipt is not linked from the source zettel frontmatter edge.",
                                    path,
                                )

    def _check_retired_draft_existing_ref(self, data: dict[str, Any], path: Path, section: str) -> None:
        section_data = data.get(section)
        if not isinstance(section_data, dict):
            return
        resolved = self._resolve_archive_file_ref(
            section_data.get("path"),
            path,
            code_prefix=f"mint_retired_draft_{section}",
            label=f"Retired draft receipt {section}.path",
            required=True,
        )
        if resolved is None:
            return
        expected_sha = section_data.get("sha256")
        if not isinstance(expected_sha, str) or not SHA256_RE.match(expected_sha):
            self.error("mint_retired_draft_sha_invalid", f"Retired draft receipt {section}.sha256 must be a lowercase SHA-256 hex digest.", path)
            return
        actual_sha = sha256_file(resolved)
        if actual_sha != expected_sha:
            if section == "target" and self._target_sha_evolved_by_edge_receipts(data, resolved, expected_sha):
                self.info(
                    "mint_retired_draft_target_sha_evolved_by_edge_receipts",
                    "Retired draft receipt target.sha256 is historical; current target differs only by approved zettel-edge receipts.",
                    path,
                )
                return
            self.error("mint_retired_draft_sha_mismatch", f"Retired draft receipt {section}.sha256 does not match the referenced file.", path)

    def _check_mint_receipt_status(self, data: dict[str, Any], path: Path, section: str, expected_status: str) -> None:
        section_data = data.get(section)
        if not isinstance(section_data, dict):
            return
        status = section_data.get("status")
        if status != expected_status:
            self.error(
                "mint_receipt_status_invalid",
                f"Mint receipt {section}.status must be {expected_status}.",
                path,
            )

    def _check_mint_receipt_file_ref(self, data: dict[str, Any], path: Path, section: str) -> Path | None:
        section_data = data.get(section)
        if not isinstance(section_data, dict):
            return None
        resolved = self._resolve_archive_file_ref(
            section_data.get("path"),
            path,
            code_prefix=f"mint_receipt_{section}",
            label=f"Mint receipt {section}.path",
            required=True,
        )
        if resolved is None:
            return None
        expected_sha = section_data.get("sha256")
        if not isinstance(expected_sha, str) or not SHA256_RE.match(expected_sha):
            self.error("mint_receipt_sha_invalid", f"Mint receipt {section}.sha256 must be a lowercase SHA-256 hex digest.", path)
            return resolved
        actual_sha = sha256_file(resolved)
        if actual_sha != expected_sha:
            if section == "target" and self._target_sha_evolved_by_edge_receipts(data, resolved, expected_sha):
                self.info(
                    "mint_receipt_target_sha_evolved_by_edge_receipts",
                    "Mint receipt target.sha256 is historical; current target differs only by approved zettel-edge receipts.",
                    path,
                )
                return resolved
            # Format-drift route (v0.3.162): a PREVIOUSLY-reconciled receipt that
            # re-drifted by newline/BOM only. Fires ONLY when the receipt carries a
            # reconcile.normalized_content_digest that matches the current canonical's
            # newline+BOM-normalized bytes. Doctor cannot re-derive the original bytes,
            # so with no prior reconcile it must NOT assert format-only — it emits the
            # plain sha-mismatch error with a hint routing to remint-reconcile. This
            # stays an ERROR (non-clean) either way — it never softens to info/warn.
            if section == "target":
                reconcile = data.get("reconcile") if isinstance(data.get("reconcile"), dict) else {}
                recorded_digest = reconcile.get("normalized_content_digest")
                if isinstance(recorded_digest, str) and SHA256_RE.match(recorded_digest):
                    try:
                        current_digest = hashlib.sha256(
                            archive_services.bytes_normalized_for_content_compare(resolved.read_bytes())
                        ).hexdigest()
                    except OSError:
                        current_digest = None
                    if current_digest == recorded_digest:
                        zettel = data.get("zettel") if isinstance(data.get("zettel"), dict) else {}
                        zettel_id = zettel.get("id") if isinstance(zettel.get("id"), str) else "<id>"
                        self.error(
                            "mint_receipt_target_byte_drift_suspected_format",
                            "Mint receipt target.sha256 does not match, but bytes differ only by newline/BOM "
                            "(suspected format drift, UNVERIFIED). Run remint-reconcile to classify and clear.",
                            path,
                            suggested_command=f"archive remint-reconcile <archive-root> --zettel-id {zettel_id} --dry-run",
                        )
                        return resolved
                zettel = data.get("zettel") if isinstance(data.get("zettel"), dict) else {}
                zettel_id = zettel.get("id") if isinstance(zettel.get("id"), str) else "<id>"
                self.error(
                    "mint_receipt_sha_mismatch",
                    f"Mint receipt {section}.sha256 does not match the referenced file.",
                    path,
                    suggested_command=f"archive remint-reconcile <archive-root> --zettel-id {zettel_id} --dry-run",
                )
                return resolved
            self.error("mint_receipt_sha_mismatch", f"Mint receipt {section}.sha256 does not match the referenced file.", path)
        return resolved

    def _check_delegate_receipts(self) -> None:
        root = self.archive_root / "receipts" / "delegate"
        if not root.is_dir():
            return
        for path in sorted(root.glob("*.delegate.json")):
            if not self._path_stays_inside_archive(path):
                continue
            data = self._load_json_file(path)
            if not isinstance(data, dict):
                continue
            self._check_schema(data, "delegate-receipt.schema.json", path)
            if data.get("action") != "delegate_zet":
                self.error("delegate_receipt_action_invalid", "Delegate receipt action must be delegate_zet.", path)
            if data.get("lifecycle_action") != "delegate":
                self.error("delegate_receipt_lifecycle_invalid", "Delegate receipt lifecycle_action must be delegate.", path)
            if data.get("dry_run") is False and not data.get("reviewed_by"):
                self.error("delegate_receipt_reviewer_missing", "Applied delegate receipt must include reviewed_by.", path)
            if data.get("receipt_path") != self._display_path(path):
                self.error("delegate_receipt_path_mismatch", "Delegate receipt receipt_path must match its archive-relative path.", path)
            for field in ["scope_gate", "trust_gate", "ownership_gate", "delegation_capability", "settlement_condition"]:
                if not isinstance(data.get(field), dict):
                    self.error("delegate_receipt_field_missing", f"Delegate receipt must contain object field: {field}.", path)
            target_policy = data.get("target_policy")
            capability = data.get("delegation_capability") if isinstance(data.get("delegation_capability"), dict) else {}
            if target_policy not in archive_services.DELEGATE_TARGET_POLICIES:
                self.error("delegate_receipt_target_policy_invalid", f"Invalid delegate target_policy: {target_policy}.", path)
            if capability.get("target_policy") and capability.get("target_policy") != target_policy:
                self.error("delegate_receipt_capability_policy_mismatch", "Delegate capability target_policy must match receipt target_policy.", path)
            self._check_delegate_receipt_zets(data, path)

    def _check_delegate_receipt_zets(self, data: dict[str, Any], path: Path) -> None:
        delegated_zets = data.get("delegated_zets")
        if not isinstance(delegated_zets, list):
            self.error("delegate_receipt_zets_invalid", "Delegate receipt delegated_zets must be a list.", path)
            return
        local_source = bool(self.archive_config and data.get("source_archive") == self.archive_config.get("archive_id"))
        for index, item in enumerate(delegated_zets):
            if not isinstance(item, dict):
                self.error("delegate_receipt_zets_invalid", f"Delegate receipt delegated_zets[{index}] must be an object.", path)
                continue
            expected_sha = item.get("sha256")
            if not isinstance(expected_sha, str) or not SHA256_RE.match(expected_sha):
                self.error("delegate_receipt_zettel_sha_invalid", f"Delegate receipt delegated_zets[{index}].sha256 must be a lowercase SHA-256 hex digest.", path)
                continue
            if not local_source:
                continue
            resolved = self._resolve_archive_file_ref(
                item.get("path"),
                path,
                code_prefix="delegate_receipt_zettel",
                label=f"Delegate receipt delegated_zets[{index}].path",
                required=True,
            )
            if resolved is None:
                continue
            actual_sha = sha256_file(resolved)
            if actual_sha != expected_sha:
                self.error("delegate_receipt_zettel_sha_mismatch", f"Delegate receipt delegated_zets[{index}].sha256 does not match the referenced zettel.", path)

    def _resolve_archive_file_ref(
        self,
        value: Any,
        path: Path,
        *,
        code_prefix: str,
        label: str,
        required: bool,
    ) -> Path | None:
        if not isinstance(value, str) or not value.strip():
            if required:
                self.error(f"{code_prefix}_path_missing", f"{label} is missing.", path)
            return None
        try:
            resolved = resolve_archive_relative_path(self.archive_root, value)
        except ArchivePathError as exc:
            self.error(f"{code_prefix}_path_unsafe", f"{label} is unsafe: {value} ({exc})", path)
            return None
        if not resolved.is_file():
            self.error(f"{code_prefix}_path_missing", f"{label} points to a missing file: {value}", path)
            return None
        return resolved

    def _check_zettel_kasten_layer(self) -> None:
        root = self.archive_root / "zettel-kasten"
        if not root.is_dir():
            return
        for filename, schema_name in ZETTEL_KASTEN_SCHEMA_FILES.items():
            path = root / filename
            data = self._load_yaml_file(path, missing_ok=True)
            if isinstance(data, dict):
                self._check_schema(data, schema_name, path)

    def _warn_unquoted_yaml_timestamps(self, data: Any, path: Path, data_path: str = "$") -> None:
        # YAML 1.1 parses an unquoted ISO timestamp into a datetime object. Our own schema
        # validator deliberately accepts that as a string, but external JSON Schema
        # validators do not — so the hand-authored file is silently non-portable. Warn with
        # the field path so authors quote their timestamps.
        if isinstance(data, (datetime, date)):
            self.warn(
                "zettel_frontmatter_unquoted_timestamp",
                f"{data_path} is an unquoted YAML timestamp; quote it (e.g. \"2026-06-11T10:00:00+09:00\") "
                "so external schema validators read a string.",
                path,
            )
            return
        if isinstance(data, dict):
            for key, value in data.items():
                self._warn_unquoted_yaml_timestamps(value, path, f"{data_path}.{key}")
        elif isinstance(data, list):
            for index, value in enumerate(data):
                self._warn_unquoted_yaml_timestamps(value, path, f"{data_path}[{index}]")

    def _check_schema(self, data: Any, schema_name: str, path: Path) -> None:
        for issue in validate_schema(data, schema_name):
            if self._is_actionable_frontmatter_v03_issue(schema_name, issue.data_path):
                self.error(
                    issue.code,
                    f"{schema_name}: {issue.message}",
                    path,
                    hint=(
                        "This zettel looks like legacy frontmatter for the current v0.3 contract. "
                        "Run the migration dry-run before editing by hand."
                    ),
                    suggested_command=archive_services.FRONTMATTER_V03_MIGRATION_COMMAND,
                    compatibility_target=archive_services.FRONTMATTER_V03_TARGET,
                )
            else:
                self.error(issue.code, f"{schema_name}: {issue.message}", path)

    def _is_actionable_frontmatter_v03_issue(self, schema_name: str, data_path: str) -> bool:
        if schema_name != "zettel-frontmatter.schema.json":
            return False
        actionable_paths = {
            "$.facets",
            "$.assets",
            "$.edges",
            "$.provenance",
            "$.provenance.created_in",
            "$.provenance.source",
            "$.provenance.derived_from",
            "$.visibility",
            "$.visibility.allowed_archives",
            "$.visibility.source_visibility",
        }
        return data_path in actionable_paths

    def _check_capture_enablement(self) -> None:
        enablement = archive_services.read_capture_enablement(self.archive_root)
        state = enablement.get("state")
        if state == "absent":
            return
        record_path = self.archive_root / "ops" / "capture-enablement.yml"
        record = enablement.get("record") if isinstance(enablement.get("record"), dict) else {}
        if state == "enabled":
            # str() on the *_at values on purpose: YAML 1.1 parses unquoted ISO dates
            # into datetime objects and this display must never raise or gate on that.
            self.info(
                "capture_enablement_enabled",
                "Objet capture enablement is active for this archive "
                f"(reviewed_by {str(record.get('reviewed_by'))}, enabled_at {str(record.get('enabled_at'))}).",
                record_path,
            )
            receipts_dir = self.archive_root / "receipts" / "capture-enablement"
            receipts = sorted(receipts_dir.glob("*.json")) if receipts_dir.is_dir() else []
            if not receipts:
                self.warn(
                    "capture_enablement_receipts_missing",
                    "Objet capture enablement record is valid but no enablement receipts exist under "
                    "receipts/capture-enablement/; re-approve with objet-capture-enable so the audit "
                    "trail matches the record.",
                    record_path,
                )
            return
        if state == "revoked":
            self.info(
                "capture_enablement_revoked",
                "Objet capture enablement was revoked "
                f"(revoked_by {str(record.get('revoked_by'))}, revoked_at {str(record.get('revoked_at'))}).",
                record_path,
            )
            return
        reason = enablement.get("reason") or "record is present but not safe/readable"
        self.warn(
            "capture_enablement_record_invalid",
            f"ops/capture-enablement.yml is present but does not validly enable capture: {reason}; "
            "objet capture stays blocked; inspect with objet-capture-enable --dry-run.",
            record_path,
        )

    def _check_local_profile_and_secret_safety(self) -> None:
        self._check_gitignore_secret_patterns()
        for path in sorted(self.archive_root.rglob("*")):
            if not path.is_file() or not self._path_stays_inside_archive(path) or self._is_ignored_scan_path(path):
                continue
            relative = self._display_path(path) or str(path)
            name = path.name.lower()
            if self._is_secret_filename(path):
                self.error("secret_file_detected", f"Secret-like local file should not live in the archive: {relative}", path)
                continue
            if self._should_scan_secret_content(path):
                try:
                    text = path.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    continue
                if contains_secret_value(text):
                    self.error("secret_value_detected", f"Secret-like value found in archive file: {relative}", path)
            if self._is_local_profile_path(path):
                self._check_local_profile_file(path)

    def _check_gitignore_secret_patterns(self) -> None:
        path = self.archive_root / ".gitignore"
        if not path.is_file():
            self.warn("local_profile_gitignore_missing", "Archive has no .gitignore protecting local profiles and secrets.", path)
            return
        lines = {
            line.strip()
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith("#")
        }
        missing = [pattern for pattern in RECOMMENDED_GITIGNORE_PATTERNS if pattern not in lines]
        if missing:
            self.warn(
                "local_profile_gitignore_incomplete",
                "Archive .gitignore is missing local profile/secret pattern(s): " + ", ".join(missing),
                path,
            )

    def _is_ignored_scan_path(self, path: Path) -> bool:
        relative_parts = path.resolve().relative_to(self.archive_root).parts
        ignored_dirs = {".git", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".venv", "venv"}
        return any(part in ignored_dirs for part in relative_parts)

    def _is_secret_filename(self, path: Path) -> bool:
        relative = self._display_path(path) or path.name
        normalized = relative.replace("\\", "/")
        name = path.name.lower()
        if name == ".env.example":
            return False
        if name in SECRET_FILENAME_EXACT:
            return True
        if name.startswith(".env."):
            return True
        if name.endswith(SECRET_FILENAME_SUFFIXES):
            return True
        return "/secrets/" in f"/{normalized.lower()}"

    def _should_scan_secret_content(self, path: Path) -> bool:
        return path.suffix.lower() in SECRET_SCAN_EXTENSIONS or path.name.lower().startswith(".env")

    def _is_local_profile_path(self, path: Path) -> bool:
        relative = (self._display_path(path) or "").replace("\\", "/")
        return relative.endswith(".local.yml") or relative.endswith(".local.yaml") or relative.startswith(LOCAL_PROFILE_ROOTS)

    def _check_local_profile_file(self, path: Path) -> None:
        data = self._load_yaml_file(path, missing_ok=True) if path.suffix.lower() in {".yml", ".yaml"} else None
        if not isinstance(data, dict):
            return
        env = data.get("env")
        if isinstance(env, dict):
            forbidden_env_keys = [key for key in env if key not in {"required", "optional"}]
            if forbidden_env_keys:
                self.warn(
                    "local_profile_env_values",
                    "Local profiles should list required/optional env var names, not env values: " + ", ".join(forbidden_env_keys),
                    path,
                )
        if any(key in data for key in ["password", "token", "secret", "api_key", "credential"]):
            self.error("local_profile_secret_value", "Local profile appears to contain a secret value.", path)

    def _check_symlink_boundaries(self) -> None:
        for path in sorted(self.archive_root.rglob("*")):
            if path.is_symlink() and not is_path_within_root(path, self.archive_root):
                self.error(
                    "archive_symlink_escapes_root",
                    "Archive symlink resolves outside the archive root.",
                    path,
                )

    def _path_stays_inside_archive(self, path: Path) -> bool:
        if is_path_within_root(path, self.archive_root):
            return True
        self.error(
            "archive_path_escapes_root",
            "Archive file resolves outside the archive root, usually through a symlink.",
            path,
        )
        return False

    def _load_allowed_link_types(self) -> set[str]:
        candidates = [
            self.archive_root / "zettel-kasten" / "types.yml",
            KIT_ZETTEL_KASTEN_ROOT / "types.yml",
        ]
        for path in candidates:
            data = self._load_yaml_file(path, missing_ok=True)
            if not isinstance(data, dict):
                continue
            link_types = data.get("link_types") or []
            if isinstance(link_types, list):
                return {item.get("id") for item in link_types if isinstance(item, dict) and item.get("id")}
        return set()

    def _load_yaml_file(self, path: Path, missing_ok: bool = False) -> Any:
        if not path.is_file():
            if not missing_ok:
                self.error("yaml_file_missing", "YAML file is missing.", path)
            return None
        if self._path_lexically_inside_archive(path) and not self._path_stays_inside_archive(path):
            return None
        try:
            return load_yaml(path.read_text(encoding="utf-8"))
        except Exception as exc:
            self.error("yaml_parse_error", f"YAML failed to parse: {exc}", path)
            return None

    def _load_yaml_text(self, text: str, path: Path) -> Any:
        try:
            return load_yaml(text)
        except Exception as exc:
            self.error("yaml_parse_error", f"YAML failed to parse: {exc}", path)
            return None

    def _load_json_file(self, path: Path) -> Any:
        if self._path_lexically_inside_archive(path) and not self._path_stays_inside_archive(path):
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError as exc:
            self.error("json_parse_error", f"JSON failed to parse: {exc}", path)
            return None
        except OSError as exc:
            self.error("json_read_error", f"JSON file could not be read: {exc}", path)
            return None

    def _path_lexically_inside_archive(self, path: Path) -> bool:
        try:
            return path.absolute().is_relative_to(self.archive_root)
        except (OSError, RuntimeError, ValueError):
            return False


def require_yaml() -> None:
    if yaml is None:
        raise SystemExit("PyYAML is required. Install it with: python -m pip install PyYAML")


def load_yaml(text: str) -> Any:
    require_yaml()
    return yaml.safe_load(text)  # type: ignore[union-attr]


def dump_yaml(data: Any) -> str:
    require_yaml()
    return yaml.safe_dump(data, sort_keys=False, allow_unicode=True)  # type: ignore[union-attr]


def parse_frontmatter(text: str) -> str | None:
    if text.startswith("\ufeff"):
        text = text[1:]
    match = FRONTMATTER_RE.match(text)
    if not match:
        return None
    return match.group(1)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def command_doctor(args: argparse.Namespace) -> int:
    doctor = Doctor(Path(args.archive_root))
    diagnostics = doctor.run()
    errors = [item for item in diagnostics if item.severity == "ERROR"]
    warnings = [item for item in diagnostics if item.severity == "WARN"]

    if args.json or getattr(args, "format", "text") == "json":
        print_json([item.as_dict() for item in diagnostics])
    else:
        print_diagnostics(diagnostics, errors, warnings)

    if errors or (args.strict and warnings):
        return 1
    return 0


def command_version(args: argparse.Namespace) -> int:
    result = archive_services.wom_kit_version_info(
        Path(args.inspection_root) if args.inspection_root else None,
        redact_local_paths=args.redact_local_paths,
    )
    if args.format == "json":
        print_json(result)
    else:
        print(f"WOM-kit {result['version_label']}")
        print(f"CLI: {result['cli_entrypoint']}")
        print(f"Consistency: {result['consistency_state']}")
        project_pin = result.get("project_pin") if isinstance(result.get("project_pin"), dict) else {}
        if project_pin.get("checked"):
            installed = project_pin.get("installed_version") or "-"
            print(f"Project pin: {project_pin.get('status') or '-'} ({installed})")
        if result.get("warnings"):
            print("Warnings:")
            for warning in result["warnings"]:
                print(f"- {warning}")
    return 0 if result.get("ok", True) else 1


def git_version_tags() -> list[str]:
    try:
        completed = subprocess.run(
            ["git", "-C", str(KIT_ROOT.parent), "tag", "-l", "v[0-9]*"],
            check=False,
            capture_output=True,
            text=True,
            timeout=3,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    if completed.returncode != 0:
        return []
    return [line.strip() for line in completed.stdout.splitlines() if line.strip()]


def semver_key_from_tag(tag: str) -> tuple[int, int, int, str] | None:
    match = re.match(r"^v(\d+)\.(\d+)\.(\d+)(.*)$", tag)
    if not match:
        return None
    return (int(match.group(1)), int(match.group(2)), int(match.group(3)), match.group(4))


def release_identity_probe() -> dict[str, Any]:
    current_tag = f"v{__version__}"
    release_notes = KIT_ROOT / "docs" / "releases" / f"{current_tag}.md"
    tags = git_version_tags()
    tag_keys = [(tag, semver_key_from_tag(tag)) for tag in tags]
    valid_tags = [(tag, key) for tag, key in tag_keys if key is not None]
    latest_tag = max(valid_tags, key=lambda item: item[1])[0] if valid_tags else None
    local_tag_present = current_tag in tags
    release_notes_present = release_notes.is_file()
    if local_tag_present:
        state = "released_local_tag_present"
    elif release_notes_present:
        state = "documented_release_candidate"
    else:
        state = "development_snapshot"
    return {
        "version": __version__,
        "version_label": current_tag,
        "release_state": state,
        "release_notes_present": release_notes_present,
        "local_git_tag_present": local_tag_present,
        "latest_local_release_tag": latest_tag,
        "network_checked": False,
    }


def subparser_action(parser: argparse.ArgumentParser) -> argparse._SubParsersAction | None:
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return action
    return None


def parser_command_manifest(parser: argparse.ArgumentParser) -> list[dict[str, Any]]:
    action = subparser_action(parser)
    if action is None:
        return []
    help_by_name = {choice.dest: choice.help for choice in action._choices_actions}
    grouped: dict[int, dict[str, Any]] = {}
    for name, command_parser in action.choices.items():
        parser_id = id(command_parser)
        group = grouped.setdefault(
            parser_id,
            {
                "names": [],
                "help": None,
                "required_positionals": [],
                "options": [],
                "subcommands": [],
            },
        )
        group["names"].append(name)
        if group["help"] is None and name in help_by_name:
            group["help"] = help_by_name[name]
        required_positionals: list[str] = []
        options: list[str] = []
        nested_subcommands: list[str] = []
        for command_action in command_parser._actions:
            if isinstance(command_action, argparse._SubParsersAction):
                nested_subcommands.extend(sorted(command_action.choices.keys()))
                continue
            if command_action.option_strings:
                options.extend(command_action.option_strings)
            elif command_action.dest not in {"help", argparse.SUPPRESS} and getattr(command_action, "nargs", None) not in {"?", "*"}:
                required_positionals.append(command_action.dest)
        group["required_positionals"] = sorted(set(required_positionals))
        group["options"] = sorted(set(options))
        group["subcommands"] = nested_subcommands

    commands: list[dict[str, Any]] = []
    for group in grouped.values():
        names = group["names"]
        primary = names[0]
        commands.append(
            {
                "name": primary,
                "aliases": names[1:],
                "help": group["help"] or "",
                "runnable": True,
                "required_positionals": group["required_positionals"],
                "options": group["options"],
                "nested_subcommands": group["subcommands"],
            }
        )
    return sorted(commands, key=lambda item: item["name"])


def command_capabilities(args: argparse.Namespace) -> int:
    parser = build_parser()
    commands = parser_command_manifest(parser)
    release = release_identity_probe()
    data = {
        "command_count": len(commands),
        "commands": [] if args.no_commands else commands,
        "agent_operator_notes": [
            "This manifest is generated from the actual local CLI parser.",
            "release_state is local-only and does not call GitHub or any provider.",
            "Use required_positionals and options for command planning; use each command's --help for full usage.",
        ],
        "recommended_agent_checks": [
            "Confirm release_state before assuming a feature exists in the public release.",
            "Treat documented_release_candidate as usable locally but not yet proven public.",
            "Prefer JSON commands that expose ok, blockers, warnings, and privacy_guards when available.",
        ],
    }
    result = {
        "ok": True,
        "state": release["release_state"],
        "summary": {
            "version": release["version"],
            "version_label": release["version_label"],
            "command_count": len(commands),
            "release_state": release["release_state"],
            "release_notes_present": release["release_notes_present"],
            "local_git_tag_present": release["local_git_tag_present"],
            "latest_local_release_tag": release["latest_local_release_tag"],
        },
        "data": data,
        "blockers": [],
        "warnings": [],
        "privacy_guards": {
            "network_checked": False,
            "provider_called": False,
            "local_absolute_paths_echoed": False,
            "tokens_or_secrets_echoed": False,
            "writes": False,
        },
    }
    if args.machine or args.format == "json":
        print_json(result)
    else:
        summary = result["summary"]
        print("WOM-kit capabilities manifest.")
        print(f"Version: {summary['version_label']}")
        print(f"Release state: {summary['release_state']}")
        print(f"Commands: {summary['command_count']}")
        print("Machine form: archive capabilities --machine")
    return 0


def command_operator_feedback_plan(args: argparse.Namespace) -> int:
    if not args.dry_run:
        print("operator-feedback-plan is read-only and requires --dry-run.", file=sys.stderr)
        return 1
    try:
        result = archive_services.operator_feedback_plan(Path(args.archive_root), dry_run=True)
    except archive_services.ArchiveServiceError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if args.format == "json":
        print_json(result)
    else:
        summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
        print("Operator feedback lifecycle plan.")
        print(f"Archive: {result.get('archive_id') or '-'}")
        print(f"Feedback dir: {summary.get('feedback_dir') or '-'}")
        print(f"Receipt dir: {summary.get('receipt_dir') or '-'}")
        print("Statuses: " + ", ".join(summary.get("statuses") or []))
    return 0 if result.get("ok", True) else 1


def command_operator_feedback_record(args: argparse.Namespace) -> int:
    if args.dry_run == args.approve:
        print("operator-feedback-record requires exactly one of --dry-run or --approve.", file=sys.stderr)
        return 1
    if args.approve and not args.reviewed_by:
        print("operator-feedback-record requires --reviewed-by when --approve is used.", file=sys.stderr)
        return 1
    try:
        result = archive_services.operator_feedback_record(
            Path(args.archive_root),
            feedback_id=args.feedback_id,
            feedback_ref=args.feedback_ref,
            status=args.status,
            title=args.title,
            related_release=args.related_release,
            resolved_in=args.resolved_in,
            dry_run=args.dry_run,
            approve=args.approve,
            reviewed_by=args.reviewed_by,
        )
    except archive_services.ArchiveServiceError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if args.format == "json":
        print_json(result)
    else:
        summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
        print("Operator feedback record.")
        print(f"State: {result.get('state') or '-'}")
        print(f"Feedback id: {summary.get('feedback_id') or '-'}")
        print(f"Status: {summary.get('status') or '-'}")
        print(f"Record path: {summary.get('record_path') or '-'}")
        if result.get("blockers"):
            print("Blockers:")
            for blocker in result["blockers"]:
                print(f"- {blocker}")
    return 0 if result.get("ok", True) else 1


def command_objet_capture_enable(args: argparse.Namespace) -> int:
    try:
        result = archive_services.objet_capture_enable(
            Path(args.archive_root),
            dry_run=args.dry_run,
            approve=args.approve,
            reviewed_by=args.reviewed_by,
            revoke=args.revoke,
            acknowledge_never_touch_name=args.acknowledge_never_touch_name,
            reenable=args.reenable,
        )
    except archive_services.ArchiveServiceError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if args.format == "json":
        print_json(result)
    else:
        print("Objet capture enablement.")
        print(f"State: {result.get('state') or '-'}")
        print(f"Action: {result.get('action') or '-'}")
        print(f"Never-touch name match: {result.get('never_touch_name_match')}")
        if result.get("reason"):
            print(f"Reason: {result['reason']}")
        if result.get("dry_run"):
            for path in result.get("planned_writes") or []:
                print(f"Planned write: {path}")
            print("Writes: none")
        else:
            for path in result.get("files_written") or []:
                print(f"Wrote: {path}")
        if result.get("blockers"):
            print("Blockers:")
            for blocker in result["blockers"]:
                print(f"- {blocker}")
    return 0 if result.get("ok") else 1


def command_approval_handoff_plan(args: argparse.Namespace) -> int:
    if not args.dry_run:
        print("approval-handoff-plan is read-only and requires --dry-run.", file=sys.stderr)
        return 1
    try:
        result = archive_services.approval_handoff_plan(Path(args.archive_root), dry_run=True)
    except archive_services.ArchiveServiceError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if args.format == "json":
        print_json(result)
    else:
        summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
        print("Approval handoff plan.")
        print(f"Archive: {result.get('archive_id') or '-'}")
        print(f"Handoff dir: {summary.get('handoff_dir') or '-'}")
        print(f"Receipt dir: {summary.get('receipt_dir') or '-'}")
        print("Statuses: " + ", ".join(summary.get("statuses") or []))
        print("Execution performed: no")
    return 0 if result.get("ok", True) else 1


def command_approval_handoff_record(args: argparse.Namespace) -> int:
    if args.dry_run == args.approve:
        print("approval-handoff-record requires exactly one of --dry-run or --approve.", file=sys.stderr)
        return 1
    if args.approve and not args.reviewed_by:
        print("approval-handoff-record requires --reviewed-by when --approve is used.", file=sys.stderr)
        return 1
    try:
        result = archive_services.approval_handoff_record(
            Path(args.archive_root),
            handoff_id=args.handoff_id,
            operation_kind=args.operation_kind,
            target_ref=args.target_ref,
            requested_action=args.requested_action,
            status=args.status,
            requested_by=args.requested_by,
            reviewed_by=args.reviewed_by,
            related_command=args.related_command,
            related_release=args.related_release,
            supersedes=args.supersedes,
            resolved_in=args.resolved_in,
            dry_run=args.dry_run,
            approve=args.approve,
        )
    except archive_services.ArchiveServiceError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if args.format == "json":
        print_json(result)
    else:
        summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
        print("Approval handoff record.")
        print(f"State: {result.get('state') or '-'}")
        print(f"Handoff id: {summary.get('handoff_id') or '-'}")
        print(f"Operation kind: {summary.get('operation_kind') or '-'}")
        print(f"Status: {summary.get('status') or '-'}")
        print(f"Record path: {summary.get('record_path') or '-'}")
        print("Target ref echoed: no")
        print("Requested action echoed: no")
        print("Execution performed: no")
        if result.get("blockers"):
            print("Blockers:")
            for blocker in result["blockers"]:
                print(f"- {blocker}")
        if result.get("warnings"):
            print("Warnings:")
            for warning in result["warnings"]:
                print(f"- {warning}")
    return 0 if result.get("ok", True) else 1


def command_approval_handoff_audit(args: argparse.Namespace) -> int:
    if not args.dry_run:
        print("approval-handoff-audit is read-only and requires --dry-run.", file=sys.stderr)
        return 1
    try:
        result = archive_services.approval_handoff_audit(
            Path(args.archive_root),
            handoff_record=args.handoff_record,
            expected_operation_kind=args.expected_operation_kind,
            expected_status=args.expected_status,
            dry_run=True,
        )
    except archive_services.ArchiveServiceError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if args.format == "json":
        print_json(result)
    else:
        summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
        print("Approval handoff audit.")
        print(f"State: {result.get('state') or '-'}")
        print(f"Handoff id: {summary.get('handoff_id') or '-'}")
        print(f"Status: {summary.get('status') or '-'}")
        print(f"Operation kind: {summary.get('operation_kind') or '-'}")
        print(f"Future operation authorized: {'yes' if summary.get('future_operation_authorized') else 'no'}")
        print("Target ref echoed: no")
        print("Requested action echoed: no")
        print("Execution performed: no")
        if result.get("blockers"):
            print("Blockers:")
            for blocker in result["blockers"]:
                print(f"- {blocker}")
        if result.get("warnings"):
            print("Warnings:")
            for warning in result["warnings"]:
                print(f"- {warning}")
    return 0 if result.get("ok", True) else 1


def command_operation_status_taxonomy(args: argparse.Namespace) -> int:
    if not args.dry_run:
        print("operation-status-taxonomy is read-only and requires --dry-run.", file=sys.stderr)
        return 1
    try:
        result = archive_services.operation_status_taxonomy(Path(args.archive_root), dry_run=True)
    except archive_services.ArchiveServiceError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if args.format == "json":
        print_json(result)
    else:
        summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
        print("Operation status taxonomy.")
        print(f"Archive: {result.get('archive_id') or '-'}")
        print(f"Status classes: {summary.get('status_class_count') or 0}")
        print("Partial/truncated count as success: no")
        print("Writes: none")
    return 0 if result.get("ok", True) else 1


def command_input_provenance_taxonomy(args: argparse.Namespace) -> int:
    if not args.dry_run:
        print("input-provenance-taxonomy is read-only and requires --dry-run.", file=sys.stderr)
        return 1
    try:
        result = archive_services.input_provenance_taxonomy(Path(args.archive_root), dry_run=True)
    except archive_services.ArchiveServiceError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if args.format == "json":
        print_json(result)
    else:
        summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
        print("Input provenance taxonomy.")
        print(f"Archive: {result.get('archive_id') or '-'}")
        print(f"Provenance classes: {summary.get('provenance_class_count') or 0}")
        print("Caller-supplied is verified: no")
        print("Writes: none")
    return 0 if result.get("ok", True) else 1


def command_secret_signal_taxonomy(args: argparse.Namespace) -> int:
    if not args.dry_run:
        print("secret-signal-taxonomy is read-only and requires --dry-run.", file=sys.stderr)
        return 1
    try:
        result = archive_services.secret_signal_taxonomy(Path(args.archive_root), dry_run=True)
    except archive_services.ArchiveServiceError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if args.format == "json":
        print_json(result)
    else:
        summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
        print("Secret signal taxonomy.")
        print(f"Archive: {result.get('archive_id') or '-'}")
        print(f"Signal classes: {summary.get('signal_class_count') or 0}")
        print("Concept words are secret values: no")
        print("Writes: none")
    return 0 if result.get("ok", True) else 1


def command_ai_response_contract(args: argparse.Namespace) -> int:
    if not args.dry_run:
        print("ai-response-contract is read-only and requires --dry-run.", file=sys.stderr)
        return 1
    try:
        result = archive_services.ai_response_contract(Path(args.archive_root), dry_run=True)
    except archive_services.ArchiveServiceError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if args.format == "json":
        print_json(result)
    else:
        summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
        print("AI response contract.")
        print(f"Archive: {result.get('archive_id') or '-'}")
        print(f"Required sections: {summary.get('required_section_count') or 0}")
        print("Conversation status board allowed: yes")
        print("Web UI required: no")
        print("Writes: none")
    return 0 if result.get("ok", True) else 1


def command_validate(args: argparse.Namespace) -> int:
    archive_root = Path(args.archive_root)
    validate_scope = build_validation_scope(archive_root.resolve(), getattr(args, "since", None), getattr(args, "scope", None))
    progress_callback = make_validate_progress_callback(bool(getattr(args, "progress", False)))
    doctor = Doctor(
        archive_root,
        validate_scope=validate_scope,
        progress_callback=progress_callback,
        use_zettel_index_cache=validate_scope.active(),
    )
    diagnostics = doctor.run()
    errors = [item for item in diagnostics if item.severity == "ERROR"]
    warnings = [item for item in diagnostics if item.severity == "WARN"]
    ok = not errors and (args.allow_warnings or not warnings)

    if args.format == "json":
        print_json(
            {
                "ok": ok,
                "errors": len(errors),
                "warnings": len(warnings),
                "scope": validate_scope.summary(),
                "diagnostics": [item.as_dict() for item in diagnostics],
            }
        )
    else:
        print_diagnostics(diagnostics, errors, warnings)
        print("Validation passed." if ok else "Validation failed.")

    return 0 if ok else 1


def command_repair_gitignore(args: argparse.Namespace) -> int:
    if args.dry_run and args.approve:
        print("Use either --dry-run or --approve, not both.", file=sys.stderr)
        return 1
    if not args.dry_run and not args.approve:
        print("Gitignore repair requires --dry-run or --approve.", file=sys.stderr)
        return 1
    if args.approve and not args.reviewed_by:
        print("Gitignore repair requires --reviewed-by when --approve is used.", file=sys.stderr)
        return 1
    try:
        result = repair_gitignore(Path(args.archive_root), approve=args.approve, reviewed_by=args.reviewed_by)
    except (archive_services.ArchiveServiceError, OSError) as exc:
        print(f"Gitignore repair failed: {exc}", file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        print(f"Gitignore repair {result.get('action')}.")
        for pattern in result.get("missing_patterns", []):
            print(f"MISSING: {pattern}")
        for path in result.get("changed_paths", []):
            print(f"CHANGED: {path}")
        for blocker in result.get("blockers", []):
            print(f"BLOCKED: {blocker}")
    return 0 if result.get("ok") else 1


def command_migrate(args: argparse.Namespace) -> int:
    try:
        result = archive_services.migrate_archive(
            Path(args.archive_root),
            target=args.target,
            dry_run=bool(args.dry_run),
            approve=bool(args.approve),
            revert=bool(args.revert),
        )
    except archive_services.ArchiveServiceError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        if result.get("revert"):
            action = "revert dry-run" if result["dry_run"] else "approved revert"
        else:
            action = "dry-run" if result["dry_run"] else "approved write"
        print(f"Migration {action}: {result['target']}")
        print(f"Archive: {result['archive_id']}")
        print(f"Files scanned: {result['files_scanned']}")
        print(f"Files with planned changes: {result['files_with_changes']}")
        if result["blocked"]:
            print("Manual review required before migration can be approved.")
            for blocker in result["blockers"]:
                print(f"- {blocker['path']} {blocker['field']}: {blocker['message']}")
        for item in result["would_change"]:
            if not item["changes"]:
                continue
            print(f"\n{item['path']}")
            for change in item["changes"]:
                print(f"- {change['action']} {change['field']}")
        if result["files_written"]:
            print("\nFiles written:")
            for path in result["files_written"]:
                print(f"- {path}")
        if not result["would_change"]:
            print("No migration changes needed.")

    return 0 if result["ok"] else 1


def command_profile_list(args: argparse.Namespace) -> int:
    try:
        result = archive_services.profile_list(
            Path(args.registry),
            current_profile=args.current_profile,
            strict=args.strict,
            redact_local_paths=args.redact_local_paths,
        )
    except archive_services.ArchiveServiceError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print_json(result)
    return 0 if result["ok"] else 1


def command_profile_resolve(args: argparse.Namespace) -> int:
    try:
        result = archive_services.profile_resolve(
            Path(args.registry),
            target=args.target,
            current_profile=args.current_profile,
            strict=args.strict,
            redact_local_paths=args.redact_local_paths,
        )
    except archive_services.ArchiveServiceError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print_json(result)
    return 0 if result["ok"] else 1


def command_profile_wallet(args: argparse.Namespace) -> int:
    if not args.dry_run:
        print("profile-wallet is read-only and requires --dry-run.", file=sys.stderr)
        return 1
    try:
        result = archive_services.profile_wallet_preview(
            Path(args.archive_root),
            profile=args.profile,
            registry_path=Path(args.registry) if args.registry else None,
            dry_run=args.dry_run,
            redact_local_paths=args.redact_local_paths,
        )
    except archive_services.ArchiveServiceError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print_json(result)
    return 0 if result["ok"] else 1


def command_runtime_context(args: argparse.Namespace) -> int:
    try:
        diagnostics = [item.as_dict() for item in Doctor(Path(args.archive_root)).run()]
        result = archive_services.runtime_context(
            Path(args.archive_root),
            expected_archive_id=args.expected_archive_id,
            expected_type=args.expected_type,
            strict=args.strict,
            redact_local_paths=args.redact_local_paths,
            diagnostics=diagnostics,
        )
    except archive_services.ArchiveServiceError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print_json(result)
    return 0 if result["ok"] else 1


def command_operational_context(args: argparse.Namespace) -> int:
    if args.dry_run and args.approve:
        print("Use either --dry-run or --approve, not both.", file=sys.stderr)
        return 1
    if not args.dry_run and not args.approve:
        print("operational-context requires --dry-run or --approve.", file=sys.stderr)
        return 1
    if args.approve and not args.reviewed_by:
        print("operational-context requires --reviewed-by when --approve is used.", file=sys.stderr)
        return 1
    try:
        result = archive_services.operational_context(
            Path(args.archive_root),
            record_path=args.record,
            dry_run=args.dry_run,
            approve=args.approve,
            reviewed_by=args.reviewed_by,
        )
    except archive_services.ArchiveServiceError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print_json(result)
    return 0 if result["ok"] else 1


def command_ai_usage_plan(args: argparse.Namespace) -> int:
    if not args.dry_run:
        print("ai-usage-plan is read-only and requires --dry-run.", file=sys.stderr)
        return 1
    try:
        result = archive_services.ai_usage_plan(
            Path(args.archive_root),
            budget_tokens=args.budget_tokens,
            include_paths=args.include_paths,
            task_id=args.task_id,
            purpose=args.purpose,
            dry_run=args.dry_run,
        )
    except archive_services.ArchiveServiceError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print_json(result)
    return 0 if result["ok"] else 1


def command_ai_usage_record(args: argparse.Namespace) -> int:
    if args.dry_run and args.approve:
        print("Use either --dry-run or --approve, not both.", file=sys.stderr)
        return 1
    if not args.dry_run and not args.approve:
        print("ai-usage-record requires --dry-run or --approve.", file=sys.stderr)
        return 1
    if args.approve and not args.reviewed_by:
        print("ai-usage-record requires --reviewed-by when --approve is used.", file=sys.stderr)
        return 1
    try:
        result = archive_services.ai_usage_record(
            Path(args.archive_root),
            task_id=args.task_id,
            runtime=args.runtime,
            model=args.model,
            purpose=args.purpose,
            input_tokens=args.input_tokens,
            output_tokens=args.output_tokens,
            total_tokens=args.total_tokens,
            cached_input_tokens=args.cached_input_tokens,
            reasoning_tokens=args.reasoning_tokens,
            budget_tokens=args.budget_tokens,
            planned_tokens=args.planned_tokens,
            context_plan_sha256=args.context_plan_sha256,
            dry_run=args.dry_run,
            approve=args.approve,
            reviewed_by=args.reviewed_by,
        )
    except archive_services.ArchiveServiceError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print_json(result)
    return 0 if result["ok"] else 1


def command_ai_usage_report(args: argparse.Namespace) -> int:
    if not args.dry_run:
        print("ai-usage-report is read-only and requires --dry-run.", file=sys.stderr)
        return 1
    try:
        result = archive_services.ai_usage_report(
            Path(args.archive_root),
            task_id=args.task_id,
            runtime=args.runtime,
            model=args.model,
            dry_run=args.dry_run,
        )
    except archive_services.ArchiveServiceError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print_json(result)
    return 0 if result["ok"] else 1


def command_github_repo(args: argparse.Namespace) -> int:
    if args.dry_run and args.approve:
        print("Use either --dry-run or --approve, not both.", file=sys.stderr)
        return 1
    if not args.dry_run and not args.approve:
        print("GitHub repository setup requires --dry-run or --approve.", file=sys.stderr)
        return 1
    if args.approve and not args.reviewed_by:
        print("GitHub repository setup requires --reviewed-by when --approve is used.", file=sys.stderr)
        return 1

    try:
        if args.dry_run:
            result = archive_services.github_repository_setup_plan(
                Path(args.archive_root),
                profile_id=args.profile_id,
                profile_slug=args.profile_slug,
                github_owner=args.github_owner,
                github_account_ref=args.github_account_ref,
                repo_name=args.repo_name,
                visibility=args.visibility,
                remote_protocol=args.remote_protocol,
            )
        else:
            result = archive_services.approve_github_repository_setup_plan(
                Path(args.archive_root),
                reviewed_by=args.reviewed_by,
                write_local_profile=args.write_local_profile,
                profile_id=args.profile_id,
                profile_slug=args.profile_slug,
                github_owner=args.github_owner,
                github_account_ref=args.github_account_ref,
                repo_name=args.repo_name,
                visibility=args.visibility,
                remote_protocol=args.remote_protocol,
            )
    except (archive_services.ArchiveServiceError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        mode = "dry-run" if result["dry_run"] else "approved"
        state = "passed" if result["ok"] else "blocked"
        print(f"GitHub repository setup {mode} {state}.")
        print(f"Archive: {result['archive_id']}")
        print(f"Profile: {result.get('profile_id') or '-'}")
        print(f"Repository: {result.get('github_owner') or '-'}/{result.get('proposed_repo_name') or '-'}")
        if result.get("receipt_path"):
            print(f"Receipt: {result['receipt_path']}")
        elif result.get("provider_setup_receipt_preview"):
            print(f"Proposed receipt: {result['provider_setup_receipt_preview']['receipt_path']}")
        if result.get("blockers"):
            print("Blockers:")
            for blocker in result["blockers"]:
                print(f"- {blocker}")
        if result.get("warnings"):
            print("Warnings:")
            for warning in result["warnings"]:
                print(f"- {warning}")
    return 0 if result.get("ok", True) else 1


def command_object_storage(args: argparse.Namespace) -> int:
    if args.dry_run and args.approve:
        print("Use either --dry-run or --approve, not both.", file=sys.stderr)
        return 1
    if not args.dry_run and not args.approve:
        print("Object storage setup requires --dry-run or --approve.", file=sys.stderr)
        return 1
    if args.approve and not args.reviewed_by:
        print("Object storage setup requires --reviewed-by when --approve is used.", file=sys.stderr)
        return 1

    try:
        if args.dry_run:
            result = archive_services.object_storage_setup_plan(
                Path(args.archive_root),
                provider=args.provider,
                profile_id=args.profile_id,
                profile_slug=args.profile_slug,
                storage_account_ref=args.storage_account_ref,
                bucket_name=args.bucket_name,
                region=args.region,
                endpoint_ref=args.endpoint_ref,
                objet_prefix=args.objet_prefix,
                visibility=args.visibility,
            )
        else:
            result = archive_services.approve_object_storage_setup_plan(
                Path(args.archive_root),
                reviewed_by=args.reviewed_by,
                write_local_profile=args.write_local_profile,
                provider=args.provider,
                profile_id=args.profile_id,
                profile_slug=args.profile_slug,
                storage_account_ref=args.storage_account_ref,
                bucket_name=args.bucket_name,
                region=args.region,
                endpoint_ref=args.endpoint_ref,
                objet_prefix=args.objet_prefix,
                visibility=args.visibility,
            )
    except (archive_services.ArchiveServiceError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        mode = "dry-run" if result["dry_run"] else "approved"
        state = "passed" if result["ok"] else "blocked"
        print(f"Object storage setup {mode} {state}.")
        print(f"Archive: {result['archive_id']}")
        print(f"Profile: {result.get('profile_id') or '-'}")
        print(f"Provider: {result.get('provider') or '-'}")
        print(f"Bucket: {result.get('proposed_bucket_name') or '-'}")
        print(f"Objet prefix: {result.get('proposed_objet_prefix') or '-'}")
        if result.get("receipt_path"):
            print(f"Receipt: {result['receipt_path']}")
        elif result.get("provider_setup_receipt_preview"):
            print(f"Proposed receipt: {result['provider_setup_receipt_preview']['receipt_path']}")
        if result.get("blockers"):
            print("Blockers:")
            for blocker in result["blockers"]:
                print(f"- {blocker}")
        if result.get("warnings"):
            print("Warnings:")
            for warning in result["warnings"]:
                print(f"- {warning}")
    return 0 if result.get("ok", True) else 1


def command_object_storage_recommendation(args: argparse.Namespace) -> int:
    if not args.dry_run:
        print("object-storage-recommendation is read-only and requires --dry-run.", file=sys.stderr)
        return 1

    try:
        result = archive_services.object_storage_recommendation(
            Path(args.archive_root),
            scenario=args.scenario,
            profile_id=args.profile_id,
            profile_slug=args.profile_slug,
            storage_account_ref=args.storage_account_ref,
            dry_run=True,
        )
    except (archive_services.ArchiveServiceError, OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        state = "passed" if result.get("ok") else "blocked"
        primary = result.get("primary_recommendation") if isinstance(result.get("primary_recommendation"), dict) else {}
        print(f"Object storage recommendation dry-run {state}.")
        print(f"Archive: {result.get('archive_id') or '-'}")
        print(f"Scenario: {result.get('scenario') or '-'}")
        print(f"Scenario source: {result.get('scenario_source') or '-'}")
        manifest = result.get("manifest_analysis") if isinstance(result.get("manifest_analysis"), dict) else {}
        dominant = manifest.get("dominant_content_class") if isinstance(manifest.get("dominant_content_class"), dict) else {}
        print(f"Manifest size: {manifest.get('total_size_gb_decimal', 0)} GB")
        if dominant:
            print(
                "Dominant class: "
                f"{dominant.get('content_class') or '-'} "
                f"{dominant.get('share_percent', 0)}%"
            )
        print(f"Primary: {primary.get('provider') or '-'} ({primary.get('label') or '-'})")
        setup_values = result.get("recommended_setup_values") if isinstance(result.get("recommended_setup_values"), dict) else {}
        next_commands = result.get("next_exact_commands") if isinstance(result.get("next_exact_commands"), dict) else {}
        print(f"Suggested bucket: {setup_values.get('bucket_name') or '-'}")
        if next_commands.get("object_storage_setup_manual"):
            print(f"Setup manual: {next_commands['object_storage_setup_manual']}")
        if next_commands.get("object_storage_dry_run"):
            print(f"Next dry-run: {next_commands['object_storage_dry_run']}")
        print("Writes: none")
        if result.get("blockers"):
            print("Blockers:")
            for blocker in result["blockers"]:
                print(f"- {blocker}")
        if result.get("warnings"):
            print("Warnings:")
            for warning in result["warnings"]:
                print(f"- {warning}")
    return 0 if result.get("ok", True) else 1


def command_human_artifact_store(args: argparse.Namespace) -> int:
    if not args.dry_run:
        print("human-artifact-store is read-only and requires --dry-run.", file=sys.stderr)
        return 1

    try:
        result = archive_services.human_artifact_store_plan(
            Path(args.archive_root),
            surface_kind=args.surface_kind,
            surface_ref=args.surface_ref,
            role=args.role,
            dry_run=args.dry_run,
        )
    except (archive_services.ArchiveServiceError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        state = "passed" if result["ok"] else "blocked"
        surface = result["surface"]
        print(f"Human artifact store plan {state}.")
        print(f"Archive: {result['archive_id']}")
        print(f"Surface: {surface.get('surface_kind') or '-'}")
        print(f"Role: {surface.get('role') or '-'}")
        if result.get("blockers"):
            print("Blockers:")
            for blocker in result["blockers"]:
                print(f"- {blocker}")
        if result.get("warnings"):
            print("Warnings:")
            for warning in result["warnings"]:
                print(f"- {warning}")
    return 0 if result.get("ok", True) else 1


def command_external_export_plan(args: argparse.Namespace) -> int:
    if not args.dry_run:
        print("external-export-plan is read-only and requires --dry-run.", file=sys.stderr)
        return 1

    try:
        result = archive_services.external_export_plan(
            Path(args.archive_root),
            source=args.source,
            export_goal=args.export_goal,
            media_policy=args.media_policy,
            estimated_media_gb=args.estimated_media_gb,
            dry_run=args.dry_run,
        )
    except (archive_services.ArchiveServiceError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        state = "passed" if result["ok"] else "blocked"
        recommended = result.get("recommended_export_mode") if isinstance(result.get("recommended_export_mode"), dict) else {}
        print(f"External export plan {state}.")
        print(f"Archive: {result.get('archive_id') or '-'}")
        print(f"Source: {result.get('source') or '-'}")
        print(f"Risk: {result.get('risk_level') or '-'}")
        print(f"Recommended mode: {recommended.get('mode') or '-'}")
        print("Writes: none")
        if result.get("blockers"):
            print("Blockers:")
            for blocker in result["blockers"]:
                print(f"- {blocker}")
        if result.get("warnings"):
            print("Warnings:")
            for warning in result["warnings"]:
                print(f"- {warning}")
    return 0 if result.get("ok", True) else 1


def command_connection_import_plan(args: argparse.Namespace) -> int:
    if not args.dry_run:
        print("connection-import-plan is read-only and requires --dry-run.", file=sys.stderr)
        return 1

    try:
        result = archive_services.connection_import_plan(
            Path(args.archive_root),
            source=args.source,
            connection_kind=args.connection_kind,
            dry_run=args.dry_run,
        )
    except (archive_services.ArchiveServiceError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        state = "passed" if result["ok"] else "blocked"
        print(f"Connection import plan {state}.")
        print(f"Archive: {result.get('archive_id') or '-'}")
        print(f"Source: {result.get('source') or '-'}")
        print(f"Connection kind: {result.get('connection_kind') or '-'}")
        print("Mappings:")
        for item in result.get("connection_mappings", []):
            edge_types = ", ".join(item.get("candidate_edge_types") or [])
            print(f"- {item.get('connection_kind')}: {edge_types}")
        missing = result.get("archive_link_type_status", {}).get("missing_recommended_edge_types") or []
        if missing:
            print("Missing recommended edge types:")
            for edge_type in missing:
                print(f"- {edge_type}")
        if result.get("blockers"):
            print("Blockers:")
            for blocker in result["blockers"]:
                print(f"- {blocker}")
        if result.get("warnings"):
            print("Warnings:")
            for warning in result["warnings"]:
                print(f"- {warning}")
    return 0 if result.get("ok", True) else 1


def command_connection_evidence_parser_contract(args: argparse.Namespace) -> int:
    if not args.dry_run:
        print("connection-evidence-parser-contract is read-only and requires --dry-run.", file=sys.stderr)
        return 1

    try:
        result = archive_services.connection_evidence_parser_contract(
            Path(args.archive_root),
            source=args.source,
            connection_kind=args.connection_kind,
            dry_run=args.dry_run,
        )
    except (archive_services.ArchiveServiceError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        state = result.get("contract_state") or ("passed" if result.get("ok") else "blocked")
        output = result.get("output_contract") if isinstance(result.get("output_contract"), dict) else {}
        print(f"Connection evidence parser contract: {state}.")
        print(f"Archive: {result.get('archive_id') or '-'}")
        print(f"Source: {result.get('source') or '-'}")
        print(f"Connection kind: {result.get('connection_kind') or '-'}")
        print("Parser executed now: no")
        print("Writes: none")
        if output.get("candidate_record_required_fields"):
            print("Candidate fields:")
            for field in output["candidate_record_required_fields"]:
                print(f"- {field}")
        if result.get("blockers"):
            print("Blockers:")
            for blocker in result["blockers"]:
                print(f"- {blocker}")
        if result.get("warnings"):
            print("Warnings:")
            for warning in result["warnings"]:
                print(f"- {warning}")
        if result.get("next_safe_actions"):
            print("Next safe actions:")
            for action in result["next_safe_actions"]:
                print(f"- {action}")
    return 0 if result.get("ok", True) else 1


def command_connection_evidence_parse_fixture(args: argparse.Namespace) -> int:
    if not args.dry_run:
        print("connection-evidence-parse-fixture is read-only and requires --dry-run.", file=sys.stderr)
        return 1

    try:
        result = archive_services.connection_evidence_parse_fixture(
            Path(args.archive_root),
            evidence_path=args.evidence,
            source=args.source,
            connection_kind=args.connection_kind,
            dry_run=args.dry_run,
            max_items=args.max_items,
        )
    except (archive_services.ArchiveServiceError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        state = result.get("parse_state") or ("passed" if result.get("ok") else "blocked")
        summary = result.get("evidence_summary") if isinstance(result.get("evidence_summary"), dict) else {}
        print(f"Connection evidence fixture parse: {state}.")
        print(f"Archive: {result.get('archive_id') or '-'}")
        print(f"Source: {result.get('source') or '-'}")
        print(f"Connection kind: {result.get('connection_kind') or '-'}")
        print(f"Fixture records: {summary.get('declared_record_count', 0)}")
        print(f"Candidate edges: {summary.get('candidate_count', 0)}")
        print("Real export parser: no")
        print("Writes: none")
        if result.get("blockers"):
            print("Blockers:")
            for blocker in result["blockers"]:
                print(f"- {blocker}")
        if result.get("warnings"):
            print("Warnings:")
            for warning in result["warnings"]:
                print(f"- {warning}")
        if result.get("next_safe_actions"):
            print("Next safe actions:")
            for action in result["next_safe_actions"]:
                print(f"- {action}")
    return 0 if result.get("ok", True) else 1


def command_connection_edge_intelligence_plan(args: argparse.Namespace) -> int:
    if not args.dry_run:
        print("connection-edge-intelligence-plan is read-only and requires --dry-run.", file=sys.stderr)
        return 1

    try:
        result = archive_services.connection_edge_intelligence_plan(
            Path(args.archive_root),
            evidence_path=args.evidence,
            source=args.source,
            connection_kind=args.connection_kind,
            dry_run=args.dry_run,
            max_items=args.max_items,
        )
    except (archive_services.ArchiveServiceError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        state = result.get("classification_state") or ("passed" if result.get("ok") else "blocked")
        summary = result.get("classification_summary") if isinstance(result.get("classification_summary"), dict) else {}
        print(f"Connection edge intelligence plan: {state}.")
        print(f"Archive: {result.get('archive_id') or '-'}")
        print(f"Source: {result.get('source') or '-'}")
        print(f"Connection kind: {result.get('connection_kind') or '-'}")
        print(f"Candidate edges: {summary.get('candidate_count', 0)}")
        print(f"Ambiguous edges: {summary.get('ambiguous_count', 0)}")
        review_summary = result.get("review_summary") if isinstance(result.get("review_summary"), dict) else {}
        print(f"Human-review-required candidates: {review_summary.get('human_review_required_count', 0)}")
        print(f"Durable-write human approvals required: {review_summary.get('durable_write_human_approval_required_count', 0)}")
        print(f"Auto-writable candidates: {review_summary.get('auto_writable_count', 0)}")
        print("AI/LLM classifier: no")
        print("Writes: none")
        if result.get("blockers"):
            print("Blockers:")
            for blocker in result["blockers"]:
                print(f"- {blocker}")
        if result.get("warnings"):
            print("Warnings:")
            for warning in result["warnings"]:
                print(f"- {warning}")
        if result.get("next_safe_actions"):
            print("Next safe actions:")
            for action in result["next_safe_actions"]:
                print(f"- {action}")
    return 0 if result.get("ok", True) else 1


def command_notion_nested_tree_plan(args: argparse.Namespace) -> int:
    if not args.dry_run:
        print("notion-nested-tree-plan is read-only and requires --dry-run.", file=sys.stderr)
        return 1

    try:
        result = archive_services.notion_nested_tree_plan(
            Path(args.archive_root),
            tree_path=args.tree,
            source=args.source,
            dry_run=args.dry_run,
            max_items=args.max_items,
        )
    except (archive_services.ArchiveServiceError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        state = result.get("plan_state") or ("passed" if result.get("ok") else "blocked")
        summary = result.get("recovery_summary") if isinstance(result.get("recovery_summary"), dict) else {}
        print(f"Notion nested tree plan: {state}.")
        print(f"Archive: {result.get('archive_id') or '-'}")
        print(f"Source: {result.get('source') or '-'}")
        print(f"Leaf nodes: {summary.get('leaf_count', 0)}")
        print(f"Missing live content leaves: {summary.get('missing_live_content_leaf_count', 0)}")
        print(f"Untraceable leaves: {summary.get('untraceable_leaf_count', 0)}")
        print(f"Structure/template skips: {summary.get('skip_structure_or_template_leaf_count', 0)}")
        print(f"Auto-writable leaves: {summary.get('auto_writable_count', 0)}")
        print("Real export parser: no")
        print("Writes: none")
        if result.get("blockers"):
            print("Blockers:")
            for blocker in result["blockers"]:
                print(f"- {blocker}")
        if result.get("warnings"):
            print("Warnings:")
            for warning in result["warnings"]:
                print(f"- {warning}")
        if result.get("next_safe_actions"):
            print("Next safe actions:")
            for action in result["next_safe_actions"]:
                print(f"- {action}")
    return 0 if result.get("ok", True) else 1


def command_notion_ancestor_crawl_plan(args: argparse.Namespace) -> int:
    if not args.dry_run:
        print("notion-ancestor-crawl-plan is read-only and requires --dry-run.", file=sys.stderr)
        return 1

    try:
        result = archive_services.notion_ancestor_crawl_plan(
            Path(args.archive_root),
            tree_path=args.tree,
            source=args.source,
            dry_run=args.dry_run,
            max_items=args.max_items,
            max_depth=args.max_depth,
            scope_generation_ids=args.scope_generation_id,
            scope_root_refs=args.scope_root_ref,
            scope_ancestor_refs=args.scope_ancestor_ref,
            scope_leaf_refs=args.scope_leaf_ref,
        )
    except (archive_services.ArchiveServiceError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        state = result.get("plan_state") or ("passed" if result.get("ok") else "blocked")
        summary = result.get("request_summary") if isinstance(result.get("request_summary"), dict) else {}
        print(f"Notion ancestor crawl plan: {state}.")
        print(f"Archive: {result.get('archive_id') or '-'}")
        print(f"Source: {result.get('source') or '-'}")
        print(f"Crawl requests: {summary.get('crawl_request_count', 0)}")
        print(f"Missing ancestor refs: {summary.get('missing_ancestor_ref_count', 0)}")
        print(f"Rootless leaf refs: {summary.get('rootless_leaf_ref_count', 0)}")
        print(f"Affected leaves: {summary.get('affected_leaf_count', 0)}")
        print(f"Unfiltered crawl requests: {summary.get('unfiltered_crawl_request_count', 0)}")
        print(f"Excluded by scope filter: {summary.get('excluded_crawl_request_count', 0)}")
        print(f"Max depth: {summary.get('max_depth', 0)}")
        print(f"Scope filter: {'active' if summary.get('scope_filter_active') else 'inactive'}")
        print("Provider API call: no")
        print("Writes: none")
        if result.get("blockers"):
            print("Blockers:")
            for blocker in result["blockers"]:
                print(f"- {blocker}")
        if result.get("warnings"):
            print("Warnings:")
            for warning in result["warnings"]:
                print(f"- {warning}")
        if result.get("next_safe_actions"):
            print("Next safe actions:")
            for action in result["next_safe_actions"]:
                print(f"- {action}")
    return 0 if result.get("ok", True) else 1


def command_notion_ancestor_fetch_adapter_execution_contract(args: argparse.Namespace) -> int:
    if not args.dry_run:
        print("notion-ancestor-fetch-adapter-execution-contract is read-only and requires --dry-run.", file=sys.stderr)
        return 1

    try:
        result = archive_services.notion_ancestor_fetch_adapter_execution_contract(
            Path(args.archive_root),
            tree_path=args.tree,
            source=args.source,
            credential_ref=args.credential_ref,
            dry_run=args.dry_run,
            max_items=args.max_items,
            max_depth=args.max_depth,
            scope_generation_ids=args.scope_generation_id,
            scope_root_refs=args.scope_root_ref,
            scope_ancestor_refs=args.scope_ancestor_ref,
            scope_leaf_refs=args.scope_leaf_ref,
        )
    except (archive_services.ArchiveServiceError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print_notion_ancestor_fetch_adapter_execution_contract_result(result, args.format)
    return 0 if result.get("ok", True) else 1


def command_notion_ancestor_fetch_adapter_run(args: argparse.Namespace) -> int:
    if args.dry_run == args.approve:
        print("Choose exactly one mode: --dry-run or --approve.", file=sys.stderr)
        return 1

    try:
        result = archive_services.notion_ancestor_fetch_adapter_run(
            Path(args.archive_root),
            tree_path=args.tree,
            output_path=args.output,
            source=args.source,
            credential_id=args.credential_id,
            credential_ref=args.credential_ref,
            credential_kind=args.credential_kind,
            credential_provider=args.credential_provider,
            store_kind=args.store_kind,
            adapter_kind=args.adapter_kind,
            approval_decision=args.approval_decision,
            approval_receipt=args.approval_receipt,
            consumer=args.consumer,
            reviewed_by=args.reviewed_by,
            platform=args.platform,
            notion_version=args.notion_version,
            timeout_seconds=args.timeout_seconds,
            dry_run=args.dry_run,
            approve=args.approve,
            max_items=args.max_items,
            max_depth=args.max_depth,
            scope_generation_ids=args.scope_generation_id,
            scope_root_refs=args.scope_root_ref,
            scope_ancestor_refs=args.scope_ancestor_ref,
            scope_leaf_refs=args.scope_leaf_ref,
        )
    except (archive_services.ArchiveServiceError, OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        summary = result.get("fetch_summary") if isinstance(result.get("fetch_summary"), dict) else {}
        fixture = result.get("fixture") if isinstance(result.get("fixture"), dict) else {}
        receipt = result.get("receipt") if isinstance(result.get("receipt"), dict) else {}
        print(f"Notion ancestor fetch adapter run: {result.get('run_state') or '-'}")
        print(f"Archive: {result.get('archive_id') or '-'}")
        print(f"Source: {result.get('source') or '-'}")
        print(f"Requests: {summary.get('request_count', 0)}")
        print(f"Fetched nodes: {summary.get('fetched_node_count', 0)}")
        print(f"Fixture: {fixture.get('output_path') or fixture.get('proposed_output_path') or '-'}")
        print(f"Receipt: {receipt.get('receipt_path') or receipt.get('proposed_receipt_path') or '-'}")
        print("Page titles read: no")
        print("Page bodies read: no")
        print("Media bytes downloaded: no")
        writes = result.get("files_written") or []
        if writes:
            print("Files written:")
            for path in writes:
                print(f"- {path}")
        else:
            print("Writes: none")
        if result.get("blockers"):
            print("Blockers:")
            for blocker in result["blockers"]:
                print(f"- {blocker}")
        if result.get("warnings"):
            print("Warnings:")
            for warning in result["warnings"]:
                print(f"- {warning}")
    return 0 if result.get("ok", True) else 1


def command_notion_recover(args: argparse.Namespace) -> int:
    if args.dry_run and args.approve:
        print("Choose at most one mode: --dry-run or --approve.", file=sys.stderr)
        return 1

    interactive_execution = not args.dry_run and not args.approve
    try:
        plan = archive_services.notion_recover_plan(
            Path(args.archive_root),
            tree_path=args.tree,
            output_path=args.output,
            source=args.source,
            dry_run=True,
            max_items=args.max_items,
            max_depth=args.max_depth,
        )
    except (archive_services.ArchiveServiceError, OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.dry_run or not plan.get("ok") or plan.get("recover_state") == "no_missing_locations":
        print_notion_recover_result(plan, args.format)
        return 0 if plan.get("ok", True) else 1

    if interactive_execution and not sys.stdin.isatty():
        result = notion_recover_blocked_result(
            plan,
            "archive notion-recover needs an interactive terminal for local confirmation; use --dry-run to preview or --approve --yes for automation.",
        )
        print_notion_recover_result(result, args.format)
        return 1

    if not args.yes:
        print_notion_recover_confirmation(plan)
        answer = input("Proceed with this local Notion location check? (y/N): ").strip().lower()
        if answer not in {"y", "yes", "예", "네"}:
            result = notion_recover_blocked_result(plan, "Human cancelled before any secret read, provider call, or file write.")
            result["recover_state"] = "cancelled_by_human"
            print_notion_recover_result(result, args.format)
            return 1

    credential_ref = args.credential_ref or archive_services.NOTION_RECOVER_INTERACTIVE_CREDENTIAL_REF
    cleanup_env_name = None
    cleanup_env_previous_value: str | None = None
    credential_handoff_source = "environment"
    if notion_recover_is_file_ref(credential_ref):
        token_result = notion_recover_read_file_ref_token(credential_ref)
        if not token_result.get("ok"):
            result = notion_recover_blocked_result(
                plan,
                str(token_result.get("blocker") or "The local credential file could not be used."),
            )
            print_notion_recover_result(result, args.format)
            return 1
        credential_ref = archive_services.NOTION_RECOVER_INTERACTIVE_CREDENTIAL_REF
        env_name = archive_services.notion_env_ref_name(credential_ref)
        if not env_name:
            result = notion_recover_blocked_result(plan, "The internal transient credential ref was not available.")
            print_notion_recover_result(result, args.format)
            return 1
        cleanup_env_previous_value = archive_services.os.environ.get(env_name)
        archive_services.os.environ[env_name] = str(token_result.get("token") or "")
        cleanup_env_name = env_name
        credential_handoff_source = "local_file_ref"
    env_name = archive_services.notion_env_ref_name(credential_ref)
    if not env_name:
        ref_store = archive_services.credential_ref_store(credential_ref) if credential_ref else None
        if ref_store in {"keyring", "secret", "wallet"}:
            result = notion_recover_blocked_result(
                plan,
                "Vault/keyring credential refs are planned for one-click handoff, but this live wrapper currently supports env refs and file refs only.",
            )
        else:
            result = notion_recover_blocked_result(plan, "A local env or file credential ref is required for this Notion recovery wrapper.")
        print_notion_recover_result(result, args.format)
        return 1
    if cleanup_env_name is None and not archive_services.os.environ.get(env_name):
        if args.credential_ref and not sys.stdin.isatty():
            result = notion_recover_blocked_result(plan, "The local token value was not available in this process environment.")
            print_notion_recover_result(result, args.format)
            return 1
        if not sys.stdin.isatty():
            result = notion_recover_blocked_result(
                plan,
                "A hidden local token prompt needs an interactive terminal; no token was read.",
            )
            print_notion_recover_result(result, args.format)
            return 1
        token = getpass.getpass("Paste Notion integration token (hidden; not echoed): ")
        if not token.strip():
            result = notion_recover_blocked_result(plan, "No token was entered; no provider call was made.")
            print_notion_recover_result(result, args.format)
            return 1
        archive_services.os.environ[env_name] = token.strip()
        cleanup_env_name = env_name
        credential_handoff_source = "hidden_local_prompt"
    elif cleanup_env_name is None:
        credential_handoff_source = "environment"

    try:
        result = run_approved_notion_recover(args, plan, credential_ref, credential_handoff_source=credential_handoff_source)
    finally:
        if cleanup_env_name:
            if cleanup_env_previous_value is None:
                archive_services.os.environ.pop(cleanup_env_name, None)
            else:
                archive_services.os.environ[cleanup_env_name] = cleanup_env_previous_value

    print_notion_recover_result(result, args.format)
    return 0 if result.get("ok", True) else 1


def notion_recover_is_file_ref(credential_ref: str) -> bool:
    return str(credential_ref or "").strip().lower().startswith("file:")


def notion_recover_read_file_ref_token(credential_ref: str) -> dict[str, Any]:
    raw_path = str(credential_ref or "").strip()[5:].strip()
    if not raw_path:
        return {"ok": False, "blocker": "The file credential ref did not include a local file path."}
    if any(char in raw_path for char in ["\n", "\r", "\x00"]):
        return {"ok": False, "blocker": "The file credential ref path was not a single local path."}
    try:
        path = Path(raw_path).expanduser()
        if not path.is_file():
            return {"ok": False, "blocker": "The local credential file was not found or was not a regular file."}
        if path.stat().st_size > 65536:
            return {"ok": False, "blocker": "The local credential file was too large for a token handoff."}
        text = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError):
        return {"ok": False, "blocker": "The local credential file could not be read as UTF-8 text."}

    token = notion_recover_extract_notion_token(text)
    if not token:
        return {"ok": False, "blocker": "No Notion integration token was found in the local credential file."}
    return {"ok": True, "token": token}


def notion_recover_extract_notion_token(text: str) -> str | None:
    for pattern in (r"\bntn_[A-Za-z0-9_-]{20,}\b", r"\bsecret_[A-Za-z0-9_-]{20,}\b"):
        match = re.search(pattern, text or "")
        if match:
            return match.group(0)
    stripped = (text or "").strip()
    if re.fullmatch(r"[A-Za-z0-9_-]{20,}", stripped):
        return stripped
    return None


def run_approved_notion_recover(
    args: argparse.Namespace,
    plan: dict[str, Any],
    credential_ref: str,
    *,
    credential_handoff_source: str = "environment",
) -> dict[str, Any]:
    archive_root = Path(args.archive_root)
    selected_tree_path = str(plan.get("selected_tree_path") or "")
    request_count = int(plan.get("auto_scope_summary", {}).get("location_request_count", 0) or 0)
    if not selected_tree_path:
        return notion_recover_blocked_result(plan, "No selected Notion tree fixture was available.")
    if request_count <= 0:
        result = dict(plan)
        result["recover_state"] = "no_missing_locations"
        return result

    approval_preview = archive_services.credential_access_approval_plan(
        archive_root,
        credential_id="cred:notion-readonly",
        credential_ref=credential_ref,
        credential_kind="provider_api_key",
        provider="notion",
        action_kind="cli_token_auth",
        decision="approve_once",
        store_kind="environment",
        consumer="wom:adapter:notion-ancestor-fetch",
        reviewed_by=args.reviewed_by,
        dry_run=True,
        approve=False,
    )
    if not approval_preview.get("ok"):
        return notion_recover_blocked_result(
            plan,
            "The one-time local approval preview was blocked.",
            nested_blockers=approval_preview.get("blockers", []),
        )

    approval_receipt = str(approval_preview.get("proposed_receipt_path") or "")
    approval_written = False
    approval_reused = bool(approval_preview.get("receipt_exists"))
    if not approval_reused:
        approval_result = archive_services.credential_access_approval_plan(
            archive_root,
            credential_id="cred:notion-readonly",
            credential_ref=credential_ref,
            credential_kind="provider_api_key",
            provider="notion",
            action_kind="cli_token_auth",
            decision="approve_once",
            store_kind="environment",
            consumer="wom:adapter:notion-ancestor-fetch",
            reviewed_by=args.reviewed_by,
            dry_run=False,
            approve=True,
        )
        if not approval_result.get("ok"):
            return notion_recover_blocked_result(
                plan,
                "The one-time local approval receipt could not be written.",
                nested_blockers=approval_result.get("blockers", []),
            )
        approval_receipt = str(approval_result.get("receipt_path") or approval_receipt)
        approval_written = True

    fetch_result = archive_services.notion_ancestor_fetch_adapter_run(
        archive_root,
        tree_path=selected_tree_path,
        output_path=args.output,
        source=args.source,
        credential_id="cred:notion-readonly",
        credential_ref=credential_ref,
        credential_kind="provider_api_key",
        credential_provider="notion",
        store_kind="environment",
        adapter_kind="environment_injection",
        approval_decision="approve_once",
        approval_receipt=approval_receipt,
        consumer="wom:adapter:notion-ancestor-fetch",
        reviewed_by=args.reviewed_by,
        platform=args.platform,
        notion_version=args.notion_version,
        timeout_seconds=args.timeout_seconds,
        dry_run=False,
        approve=True,
        max_items=args.max_items,
        max_depth=args.max_depth,
    )
    if not fetch_result.get("ok"):
        return notion_recover_execution_result(
            plan,
            approval_written=approval_written,
            approval_reused=approval_reused,
            fetch_result=fetch_result,
            merge_result={},
        )

    fixture = fetch_result.get("fixture") if isinstance(fetch_result.get("fixture"), dict) else {}
    output_path = str(fixture.get("output_path") or args.output)
    merge_result: dict[str, Any] = {}
    if output_path:
        merge_result = archive_services.notion_ancestor_merge_plan(
            archive_root,
            tree_path=selected_tree_path,
            ancestors_path=output_path,
            source=args.source,
            dry_run=True,
            max_items=100000,
        )

    return notion_recover_execution_result(
        plan,
        approval_written=approval_written,
        approval_reused=approval_reused,
        fetch_result=fetch_result,
        merge_result=merge_result,
        credential_handoff_source=credential_handoff_source,
    )


def notion_recover_blocked_result(
    plan: dict[str, Any],
    blocker: str,
    *,
    nested_blockers: list[Any] | None = None,
) -> dict[str, Any]:
    result = dict(plan)
    blockers = list(result.get("blockers") or [])
    blockers.append(blocker)
    blockers.extend(str(item) for item in (nested_blockers or []))
    result["ok"] = False
    result["recover_state"] = "blocked"
    result["blockers"] = archive_services.unique_preserve_order(blockers)
    closed = dict(result.get("closed_actions") or {})
    closed.update(
        {
            "provider_api_called": False,
            "notion_location_fetch_executed": False,
            "notion_ancestor_result_fixture_written": False,
            "files_written": False,
        }
    )
    result["closed_actions"] = closed
    return result


def notion_recover_execution_result(
    plan: dict[str, Any],
    *,
    approval_written: bool,
    approval_reused: bool,
    fetch_result: dict[str, Any],
    merge_result: dict[str, Any],
    credential_handoff_source: str = "environment",
) -> dict[str, Any]:
    fetch_summary = fetch_result.get("fetch_summary") if isinstance(fetch_result.get("fetch_summary"), dict) else {}
    fixture = fetch_result.get("fixture") if isinstance(fetch_result.get("fixture"), dict) else {}
    merge_summary = merge_result.get("merge_summary") if isinstance(merge_result.get("merge_summary"), dict) else {}
    after_merge = merge_result.get("nested_tree_plan_after_merge") if isinstance(merge_result.get("nested_tree_plan_after_merge"), dict) else {}
    after_recovery = after_merge.get("recovery_summary") if isinstance(after_merge.get("recovery_summary"), dict) else {}
    fetch_ok = bool(fetch_result.get("ok"))
    merge_ok = bool(merge_result.get("ok", True)) if merge_result else True
    files_written_count = len(fetch_result.get("files_written") or []) + (1 if approval_written else 0)
    result = {
        "ok": fetch_ok and merge_ok,
        "dry_run": False,
        "approved": True,
        "lifecycle_action": "notion_recover",
        "mode": "single_command_interactive_wrapper",
        "archive_id": plan.get("archive_id"),
        "recover_state": "succeeded" if fetch_ok and merge_ok else "blocked_after_partial_execution",
        "source": plan.get("source"),
        "selected_tree_path": plan.get("selected_tree_path"),
        "selected_tree_path_kind": plan.get("selected_tree_path_kind"),
        "auto_scope_summary": plan.get("auto_scope_summary", {}),
        "approval_summary": {
            "approval_required_before_provider_call": True,
            "approval_receipt_written": approval_written,
            "approval_receipt_reused": approval_reused,
            "approval_receipt_path_echoed": False,
            "approval_receipt_path_copy_required": False,
            "decision": "approve_once",
        },
        "credential_handoff": {
            "source": credential_handoff_source,
            "file_ref_supported_now": True,
            "vault_or_keyring_click_handoff_supported_now": False,
            "secret_value_returned_to_ai": False,
            "credential_file_path_echoed": False,
            "credential_value_echoed": False,
            "transient_local_injection_only": credential_handoff_source in {"local_file_ref", "hidden_local_prompt"},
        },
        "fetch_summary": {
            "request_count": int(fetch_summary.get("request_count", 0) or 0),
            "fetched_location_count": int(fetch_summary.get("fetched_node_count", 0) or 0),
            "partial_request_count": int(fetch_summary.get("partial_request_count", 0) or 0),
            "failed_request_count": int(fetch_summary.get("failed_request_count", 0) or 0),
            "failure_categories": fetch_summary.get("failure_categories", []),
            "primary_failure_category": fetch_summary.get("primary_failure_category"),
            "safe_action_hints": fetch_summary.get("safe_action_hints", []),
            "permission_or_connection_issue_detected": fetch_summary.get("primary_failure_category")
            in {"notion_connection_not_shared_or_permission_denied", "notion_object_missing_or_not_shared"},
            "raw_provider_errors_echoed": False,
            "page_titles_returned": False,
            "page_bodies_returned": False,
            "media_bytes_returned": False,
        },
        "result_handoff": {
            "sanitized_output_path": fixture.get("output_path"),
            "sanitized_output_path_kind": fixture.get("output_path_kind"),
            "merge_plan_previewed": bool(merge_result),
            "merge_plan_state": merge_result.get("plan_state") if merge_result else None,
            "merged_added_location_count": int(merge_summary.get("added_node_count", 0) or 0),
            "remaining_missing_location_count_after_merge_preview": int(after_recovery.get("hold_leaf_count", 0) or 0)
            if after_recovery
            else None,
            "merge_writer_implemented": False,
            "say_to_ai_after_success": "Please tidy and merge the recovered Notion locations into the reviewed list.",
        },
        "current_capability": plan.get("current_capability", {}),
        "closed_actions": {
            "provider_api_called": bool(fetch_result.get("closed_actions", {}).get("provider_api_called")),
            "notion_connection_opened": bool(fetch_result.get("closed_actions", {}).get("notion_connection_opened")),
            "secret_value_read": bool(fetch_result.get("closed_actions", {}).get("secret_value_read")),
            "environment_read": bool(fetch_result.get("closed_actions", {}).get("environment_read")),
            "approval_receipt_written": approval_written,
            "notion_location_fetch_executed": bool(fetch_result.get("closed_actions", {}).get("live_adapter_executed")),
            "notion_ancestor_result_fixture_written": bool(
                fetch_result.get("closed_actions", {}).get("ancestor_result_fixture_written")
            ),
            "merge_plan_executed": bool(merge_result),
            "zettels_written": False,
            "edges_written": False,
            "media_downloaded": False,
            "files_written": files_written_count > 0,
        },
        "privacy_guards": {
            "credential_ref_echoed": False,
            "credential_values_echoed": False,
            "env_var_names_echoed": False,
            "approval_receipt_path_echoed": False,
            "raw_provider_refs_echoed": False,
            "provider_urls_echoed": False,
            "workspace_urls_echoed": False,
            "local_absolute_paths_echoed": False,
            "credential_file_paths_echoed": False,
            "page_titles_echoed": False,
            "page_bodies_echoed": False,
            "comment_bodies_echoed": False,
            "media_bytes_echoed": False,
            "account_ids_echoed": False,
            "emails_echoed": False,
            "tokens_echoed": False,
            "secret_values_echoed": False,
            "writes": files_written_count > 0,
        },
        "files_written_count": files_written_count,
        "receipt_paths_echoed": False,
        "next_safe_actions": [
            "Ask AI to tidy and merge the recovered Notion locations into the reviewed list.",
            "Rerun archive notion-recover only if the merge preview still shows missing locations.",
            "Keep page body and media byte recovery behind their separate approval gates.",
        ],
        "warnings": archive_services.unique_preserve_order(
            [*list(plan.get("warnings") or []), *list(fetch_result.get("warnings") or []), *list(merge_result.get("warnings") or [])]
        ),
        "blockers": archive_services.unique_preserve_order(
            [*list(fetch_result.get("blockers") or []), *list(merge_result.get("blockers") or [])]
        ),
    }
    if result["blockers"]:
        result["ok"] = False
        result["recover_state"] = "blocked_after_partial_execution" if files_written_count else "blocked"
    return result


def print_notion_recover_confirmation(result: dict[str, Any]) -> None:
    scope = result.get("auto_scope_summary") if isinstance(result.get("auto_scope_summary"), dict) else {}
    print("Notion recovery is ready.")
    print(f"Location checks: {scope.get('location_request_count', 0)}")
    print(f"Items affected: {scope.get('affected_item_count', 0)}")
    print("Reads: folder/shelf/location links only.")
    print("Does not read: page titles, page bodies, comments, or media.")
    print("Your token stays in the local terminal. The AI does not receive it.")


def print_notion_recover_result(result: dict[str, Any], output_format: str) -> None:
    if output_format == "json":
        print_json(result)
        return
    scope = result.get("auto_scope_summary") if isinstance(result.get("auto_scope_summary"), dict) else {}
    fetch = result.get("fetch_summary") if isinstance(result.get("fetch_summary"), dict) else {}
    handoff = result.get("result_handoff") if isinstance(result.get("result_handoff"), dict) else {}
    print(f"Notion recovery: {result.get('recover_state') or '-'}")
    print(f"Archive: {result.get('archive_id') or '-'}")
    print(f"Tree: {result.get('selected_tree_path') or '-'}")
    print(f"Location checks: {scope.get('location_request_count', 0)}")
    print(f"Items affected: {scope.get('affected_item_count', 0)}")
    if fetch:
        print(f"Recovered locations: {fetch.get('fetched_location_count', 0)}")
        print(f"Failed checks: {fetch.get('failed_request_count', 0)}")
        if fetch.get("primary_failure_category"):
            print(f"Likely failure category: {fetch.get('primary_failure_category')}")
        hints = fetch.get("safe_action_hints") if isinstance(fetch.get("safe_action_hints"), list) else []
        if hints:
            print(f"Suggested next action: {hints[0]}")
    print("Reads: folder/shelf/location links only")
    print("Does not read: page titles, page bodies, comments, or media")
    if handoff.get("sanitized_output_path"):
        print(f"Sanitized result: {handoff.get('sanitized_output_path')}")
    print("Next: ask AI to tidy and merge the recovered Notion locations.")
    if result.get("blockers"):
        print("Blockers:")
        for blocker in result["blockers"]:
            print(f"- {blocker}")
    if result.get("warnings"):
        print("Warnings:")
        for warning in result["warnings"]:
            print(f"- {warning}")


def command_notion_connection_plan(args: argparse.Namespace) -> int:
    if not args.dry_run:
        print("notion-connection-plan is read-only and requires --dry-run.", file=sys.stderr)
        return 1
    try:
        result = archive_services.notion_connection_plan(
            Path(args.archive_root),
            dry_run=args.dry_run,
        )
    except (archive_services.ArchiveServiceError, OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if args.format == "json":
        print_json(result)
    else:
        print(f"Notion connection plan: {result.get('connection_state') or '-'}")
        print(f"Archive: {result.get('archive_id') or '-'}")
        recommended = result.get("recommended_product_path") if isinstance(result.get("recommended_product_path"), dict) else {}
        print(f"Recommended path: {recommended.get('path') or '-'}")
        print(f"First click: {recommended.get('first_click') or '-'}")
        implemented = result.get("implemented_now") if isinstance(result.get("implemented_now"), dict) else {}
        print(f"One-click OAuth implemented: {implemented.get('one_click_oauth_connection')}")
        print(f"Actionable failure classification: {implemented.get('actionable_provider_failure_classification')}")
    return 0 if result.get("ok", True) else 1


def command_notion_oauth_connection_preflight(args: argparse.Namespace) -> int:
    if not args.dry_run:
        print("notion-oauth-connection-preflight is read-only and requires --dry-run.", file=sys.stderr)
        return 1
    try:
        result = archive_services.notion_oauth_connection_preflight(
            Path(args.archive_root),
            client_id_ref=args.client_id_ref,
            client_secret_ref=args.client_secret_ref,
            redirect_uri=args.redirect_uri,
            state_ref=args.state_ref,
            token_store_ref=args.token_store_ref,
            dry_run=args.dry_run,
        )
    except (archive_services.ArchiveServiceError, OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if args.format == "json":
        print_json(result)
    else:
        print(f"Notion OAuth preflight: {result.get('preflight_state') or '-'}")
        print(f"Archive: {result.get('archive_id') or '-'}")
        callback = result.get("callback_validation") if isinstance(result.get("callback_validation"), dict) else {}
        print(f"Callback host: {callback.get('host_class') or '-'}")
        print(f"Callback valid: {callback.get('redirect_uri_valid')}")
        security = result.get("security_contract") if isinstance(result.get("security_contract"), dict) else {}
        print(f"AI secret-blind: {security.get('ai_secret_blind')}")
        print(f"Token exchange actor: {security.get('token_exchange_actor') or '-'}")
        if result.get("blockers"):
            print("Blockers:")
            for blocker in result["blockers"]:
                print(f"- {blocker}")
        if result.get("warnings"):
            print("Warnings:")
            for warning in result["warnings"]:
                print(f"- {warning}")
    return 0 if result.get("ok", True) else 1


def command_notion_media_fetch_adapter_execution_contract(args: argparse.Namespace) -> int:
    if not args.dry_run:
        print("notion-media-fetch-adapter-execution-contract is read-only and requires --dry-run.", file=sys.stderr)
        return 1

    try:
        result = archive_services.notion_media_fetch_adapter_execution_contract(
            Path(args.archive_root),
            tree_path=args.tree,
            source=args.source,
            credential_ref=args.credential_ref,
            dry_run=args.dry_run,
            max_items=args.max_items,
            scope_generation_ids=args.scope_generation_id,
            scope_root_refs=args.scope_root_ref,
            scope_leaf_refs=args.scope_leaf_ref,
        )
    except (archive_services.ArchiveServiceError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print_notion_media_fetch_adapter_execution_contract_result(result, args.format)
    return 0 if result.get("ok", True) else 1


def command_notion_media_result_verification_plan(args: argparse.Namespace) -> int:
    if not args.dry_run:
        print("notion-media-result-verification-plan is read-only and requires --dry-run.", file=sys.stderr)
        return 1

    try:
        result = archive_services.notion_media_result_verification_plan(
            Path(args.archive_root),
            media_result_path=args.media_result,
            source=args.source,
            dry_run=args.dry_run,
            max_items=args.max_items,
        )
    except (archive_services.ArchiveServiceError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print_notion_media_result_verification_plan_result(result, args.format)
    return 0 if result.get("ok", True) else 1


def command_notion_block_mirror_tree_fixture_plan(args: argparse.Namespace) -> int:
    if not args.dry_run:
        print("notion-block-mirror-tree-fixture-plan is read-only and requires --dry-run.", file=sys.stderr)
        return 1

    try:
        result = archive_services.notion_block_mirror_tree_fixture_plan(
            Path(args.archive_root),
            mirror_path=args.mirror,
            source=args.source,
            dry_run=args.dry_run,
            max_items=args.max_items,
        )
    except (archive_services.ArchiveServiceError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        state = result.get("plan_state") or ("passed" if result.get("ok") else "blocked")
        mirror = result.get("mirror_summary") if isinstance(result.get("mirror_summary"), dict) else {}
        preview = result.get("nested_tree_plan_preview") if isinstance(result.get("nested_tree_plan_preview"), dict) else {}
        summary = preview.get("recovery_summary") if isinstance(preview.get("recovery_summary"), dict) else {}
        print(f"Notion block mirror tree fixture plan: {state}.")
        print(f"Archive: {result.get('archive_id') or '-'}")
        print(f"Source: {result.get('source') or '-'}")
        print(f"Mirror records: {mirror.get('processed_record_count', 0)}/{mirror.get('declared_record_count', 0)}")
        print(f"Preview leaf nodes: {summary.get('leaf_count', 0)}")
        print(f"Preview recovery leaves: {summary.get('missing_live_content_leaf_count', 0)}")
        print(f"Preview hold leaves: {summary.get('hold_leaf_count', 0)}")
        print("Provider API call: no")
        print("Writes: none")
        if result.get("blockers"):
            print("Blockers:")
            for blocker in result["blockers"]:
                print(f"- {blocker}")
        if result.get("warnings"):
            print("Warnings:")
            for warning in result["warnings"]:
                print(f"- {warning}")
    return 0 if result.get("ok", True) else 1


def print_notion_ancestor_fetch_adapter_execution_contract_result(result: dict[str, Any], output_format: str) -> None:
    if output_format == "json":
        print_json(result)
        return
    summary = result.get("crawl_request_summary") if isinstance(result.get("crawl_request_summary"), dict) else {}
    credential = result.get("credential_summary") if isinstance(result.get("credential_summary"), dict) else {}
    actor = result.get("execution_actor_contract") if isinstance(result.get("execution_actor_contract"), dict) else {}
    print(f"Notion ancestor fetch adapter execution contract: {result.get('contract_state') or '-'}")
    print(f"Archive: {result.get('archive_id') or '-'}")
    print(f"Source: {result.get('source') or '-'}")
    print(f"Crawl requests: {summary.get('crawl_request_count', 0)}")
    print(f"Unfiltered crawl requests: {summary.get('unfiltered_crawl_request_count', 0)}")
    print(f"Excluded by scope filter: {summary.get('excluded_crawl_request_count', 0)}")
    print(f"Scope filter: {'active' if summary.get('scope_filter_active') else 'inactive'}")
    print(f"Credential ref supplied: {credential.get('credential_ref_supplied', False)}")
    print("Live execution allowed now: no")
    print(f"Current execution subject: {actor.get('current_live_fetch_execution_subject') or 'none_contract_preview_only'}")
    print(f"Intended future execution subject: {actor.get('intended_live_fetch_execution_subject') or 'future_wom_local_credential_bounded_adapter_process'}")
    print("Client hand-rolled provider crawl required: no")
    print("AI hand-rolled provider crawl allowed: no")
    print("Provider API called: no")
    print("Writes: none")
    if result.get("blockers"):
        print("Blockers:")
        for blocker in result["blockers"]:
            print(f"- {blocker}")
    if result.get("warnings"):
        print("Warnings:")
        for warning in result["warnings"]:
            print(f"- {warning}")
    if result.get("next_safe_actions"):
        print("Next safe actions:")
        for action in result["next_safe_actions"]:
            print(f"- {action}")


def print_notion_media_fetch_adapter_execution_contract_result(result: dict[str, Any], output_format: str) -> None:
    if output_format == "json":
        print_json(result)
        return
    summary = result.get("media_request_summary") if isinstance(result.get("media_request_summary"), dict) else {}
    credential = result.get("credential_summary") if isinstance(result.get("credential_summary"), dict) else {}
    actor = result.get("execution_actor_contract") if isinstance(result.get("execution_actor_contract"), dict) else {}
    print(f"Notion media fetch adapter execution contract: {result.get('contract_state') or '-'}")
    print(f"Archive: {result.get('archive_id') or '-'}")
    print(f"Source: {result.get('source') or '-'}")
    print(f"Candidate pages: {summary.get('candidate_page_count', 0)}")
    print(f"Unfiltered candidate pages: {summary.get('unfiltered_candidate_page_count', 0)}")
    print(f"Excluded by scope filter: {summary.get('excluded_by_scope_filter_count', 0)}")
    print(f"Media block count known now: {summary.get('media_block_count_known_now', False)}")
    print(f"Credential ref supplied: {credential.get('credential_ref_supplied', False)}")
    print("Live execution allowed now: no")
    print(f"Current execution subject: {actor.get('current_live_fetch_execution_subject') or 'none_contract_preview_only'}")
    print(f"Intended future execution subject: {actor.get('intended_live_fetch_execution_subject') or 'future_wom_local_credential_bounded_adapter_process'}")
    print("Client hand-rolled provider crawl required: no")
    print("AI hand-rolled provider crawl allowed: no")
    print("Provider API called: no")
    print("Media bytes downloaded: no")
    print("Writes: none")
    if result.get("blockers"):
        print("Blockers:")
        for blocker in result["blockers"]:
            print(f"- {blocker}")
    if result.get("warnings"):
        print("Warnings:")
        for warning in result["warnings"]:
            print(f"- {warning}")
    if result.get("next_safe_actions"):
        print("Next safe actions:")
        for action in result["next_safe_actions"]:
            print(f"- {action}")


def print_notion_media_result_verification_plan_result(result: dict[str, Any], output_format: str) -> None:
    if output_format == "json":
        print_json(result)
        return
    summary = result.get("verification_summary") if isinstance(result.get("verification_summary"), dict) else {}
    print(f"Notion media result verification plan: {result.get('plan_state') or '-'}")
    print(f"Archive: {result.get('archive_id') or '-'}")
    print(f"Source: {result.get('source') or '-'}")
    print(f"Media results: {summary.get('media_result_count', 0)}")
    print(f"Manifest matches: {summary.get('manifest_match_count', 0)}")
    print(f"Manifest missing: {summary.get('manifest_missing_count', 0)}")
    print(f"Already preserved: {summary.get('already_preserved_count', 0)}")
    print(f"Newly preserved: {summary.get('newly_preserved_count', 0)}")
    print(f"Fetch failed: {summary.get('fetch_failed_count', 0)}")
    print(f"Item blockers: {summary.get('item_blocker_count', 0)}")
    print("Provider API called: no")
    print("Media bytes downloaded: no")
    print("Media bytes hashed: no")
    print("Writes: none")
    if result.get("blockers"):
        print("Blockers:")
        for blocker in result["blockers"]:
            print(f"- {blocker}")
    if result.get("warnings"):
        print("Warnings:")
        for warning in result["warnings"]:
            print(f"- {warning}")
    if result.get("next_safe_actions"):
        print("Next safe actions:")
        for action in result["next_safe_actions"]:
            print(f"- {action}")


def command_notion_ancestor_merge_plan(args: argparse.Namespace) -> int:
    if not args.dry_run:
        print("notion-ancestor-merge-plan is read-only and requires --dry-run.", file=sys.stderr)
        return 1

    try:
        result = archive_services.notion_ancestor_merge_plan(
            Path(args.archive_root),
            tree_path=args.tree,
            ancestors_path=args.ancestors,
            source=args.source,
            dry_run=args.dry_run,
            max_items=args.max_items,
        )
    except (archive_services.ArchiveServiceError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        state = result.get("plan_state") or ("passed" if result.get("ok") else "blocked")
        merge = result.get("merge_summary") if isinstance(result.get("merge_summary"), dict) else {}
        preview = result.get("nested_tree_plan_after_merge") if isinstance(result.get("nested_tree_plan_after_merge"), dict) else {}
        summary = preview.get("recovery_summary") if isinstance(preview.get("recovery_summary"), dict) else {}
        print(f"Notion ancestor merge plan: {state}.")
        print(f"Archive: {result.get('archive_id') or '-'}")
        print(f"Source: {result.get('source') or '-'}")
        print(f"Added ancestors: {merge.get('added_node_count', 0)}")
        print(f"Conflicts: {merge.get('conflict_count', 0)}")
        print(f"After-merge recovery leaves: {summary.get('missing_live_content_leaf_count', 0)}")
        print(f"After-merge hold leaves: {summary.get('hold_leaf_count', 0)}")
        print("Provider API call: no")
        print("Writes: none")
        if result.get("blockers"):
            print("Blockers:")
            for blocker in result["blockers"]:
                print(f"- {blocker}")
        if result.get("warnings"):
            print("Warnings:")
            for warning in result["warnings"]:
                print(f"- {warning}")
    return 0 if result.get("ok", True) else 1


def command_notion_client_issue_verification_plan(args: argparse.Namespace) -> int:
    if not args.dry_run:
        print("notion-client-issue-verification-plan is read-only and requires --dry-run.", file=sys.stderr)
        return 1

    try:
        result = archive_services.notion_client_issue_verification_plan(
            Path(args.archive_root),
            tree_path=args.tree,
            mirror_path=args.mirror,
            ancestors_path=args.ancestors,
            source=args.source,
            dry_run=args.dry_run,
            max_items=args.max_items,
            max_depth=args.max_depth,
        )
    except (archive_services.ArchiveServiceError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        state = result.get("plan_state") or ("passed" if result.get("ok") else "blocked")
        summary = result.get("verification_summary") if isinstance(result.get("verification_summary"), dict) else {}
        print(f"Notion client issue verification plan: {state}.")
        print(f"Archive: {result.get('archive_id') or '-'}")
        print(f"Source: {result.get('source') or '-'}")
        print(f"Verdict: {summary.get('verdict') or '-'}")
        print(f"Initial hold leaves: {summary.get('initial_hold_leaf_count', 0)}")
        print(f"Initial untraceable leaves: {summary.get('initial_untraceable_leaf_count', 0)}")
        print(f"Crawl requests: {summary.get('crawl_request_count', 0)}")
        print(f"Added ancestors: {summary.get('added_ancestor_count', 0)}")
        print(f"After-merge hold leaves: {summary.get('after_merge_hold_leaf_count', 0)}")
        print(f"Ready for reviewed recovery: {'yes' if summary.get('ready_for_reviewed_recovery') else 'no'}")
        print("Provider API call: no")
        print("Writes: none")
        if result.get("blockers"):
            print("Blockers:")
            for blocker in result["blockers"]:
                print(f"- {blocker}")
        if result.get("warnings"):
            print("Warnings:")
            for warning in result["warnings"]:
                print(f"- {warning}")
        if result.get("next_safe_actions"):
            print("Next safe actions:")
            for action in result["next_safe_actions"]:
                print(f"- {action}")
    return 0 if result.get("ok", True) else 1


def command_notion_client_fixture_request_plan(args: argparse.Namespace) -> int:
    if not args.dry_run:
        print("notion-client-fixture-request-plan is read-only and requires --dry-run.", file=sys.stderr)
        return 1

    try:
        result = archive_services.notion_client_fixture_request_plan(
            Path(args.archive_root),
            tree_path=args.tree,
            mirror_path=args.mirror,
            ancestors_path=args.ancestors,
            source=args.source,
            scenario=args.scenario,
            dry_run=args.dry_run,
            max_items=args.max_items,
            max_depth=args.max_depth,
        )
    except (archive_services.ArchiveServiceError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        state = result.get("plan_state") or ("passed" if result.get("ok") else "blocked")
        package = result.get("request_package") if isinstance(result.get("request_package"), dict) else {}
        print(f"Notion client fixture request plan: {state}.")
        print(f"Archive: {result.get('archive_id') or '-'}")
        print(f"Source: {result.get('source') or '-'}")
        print(f"Scenario: {result.get('scenario') or '-'}")
        print(f"Requested next fixture: {package.get('requested_next_fixture') or '-'}")
        print(f"Current verification state: {package.get('current_verification_state') or '-'}")
        print("Provider API call: no")
        print("Writes: none")
        if result.get("blockers"):
            print("Blockers:")
            for blocker in result["blockers"]:
                print(f"- {blocker}")
        if result.get("warnings"):
            print("Warnings:")
            for warning in result["warnings"]:
                print(f"- {warning}")
        if result.get("next_safe_actions"):
            print("Next safe actions:")
            for action in result["next_safe_actions"]:
                print(f"- {action}")
    return 0 if result.get("ok", True) else 1


def command_zettel_edge(args: argparse.Namespace) -> int:
    try:
        result = archive_services.zettel_edge_write(
            Path(args.archive_root),
            from_zettel=args.from_zettel,
            from_path=args.from_path,
            target_ref=args.target,
            edge_type=args.edge_type,
            visibility=args.visibility,
            dry_run=args.dry_run,
            approve=args.approve,
            reviewed_by=args.reviewed_by,
        )
    except (archive_services.ArchiveServiceError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        state = result.get("write_status") or ("passed" if result.get("ok") else "blocked")
        print(f"Zettel edge: {state}.")
        print(f"Archive: {result.get('archive_id') or '-'}")
        source = result.get("source") if isinstance(result.get("source"), dict) else {}
        target = result.get("target") if isinstance(result.get("target"), dict) else {}
        print(f"Source: {source.get('zettel_id') or '-'}")
        print(f"Target: {target.get('ref') or '-'}")
        print(f"Edge type: {result.get('edge_type') or '-'}")
        print(f"Visibility: {result.get('visibility') or '-'}")
        print(f"Receipt: {result.get('receipt_path') or '-'}")
        if result.get("files_written"):
            print("Files written:")
            for path in result["files_written"]:
                print(f"- {path}")
        elif result.get("would_change"):
            print("Would change:")
            for path in result["would_change"]:
                print(f"- {path}")
        if result.get("blockers"):
            print("Blockers:")
            for blocker in result["blockers"]:
                print(f"- {blocker}")
        if result.get("warnings"):
            print("Warnings:")
            for warning in result["warnings"]:
                print(f"- {warning}")
    return 0 if result.get("ok", True) else 1


def command_zettel_edge_batch(args: argparse.Namespace) -> int:
    try:
        result = archive_services.zettel_edge_batch_write(
            Path(args.archive_root),
            plan_path=Path(args.plan),
            dry_run=args.dry_run,
            approve=args.approve,
            reviewed_by=args.reviewed_by,
            max_edges=args.max_edges,
            skip_existing=args.skip_existing,
        )
    except (archive_services.ArchiveServiceError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        state = result.get("write_status") or ("passed" if result.get("ok") else "blocked")
        summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
        policy = result.get("policy") if isinstance(result.get("policy"), dict) else {}
        print(f"Zettel edge batch: {state}.")
        print(f"Archive: {result.get('archive_id') or '-'}")
        print(f"Policy: {policy.get('policy_id') or '-'}")
        print(f"Policy-writable edges: {summary.get('policy_writable_edge_count', 0)}")
        print(f"Human review queue: {summary.get('review_queue_count', 0)}")
        print(f"Skipped existing edges: {summary.get('skipped_existing_edge_count', 0)}")
        print(f"Written edges: {summary.get('written_edge_count', 0)}")
        print(f"Receipt: {result.get('receipt_path') or '-'}")
        if result.get("files_written"):
            print("Files written:")
            for path in result["files_written"]:
                print(f"- {path}")
        elif result.get("would_change"):
            print("Would change:")
            for path in result["would_change"]:
                print(f"- {path}")
        if result.get("blockers"):
            print("Blockers:")
            for blocker in result["blockers"]:
                print(f"- {blocker}")
        if result.get("warnings"):
            print("Warnings:")
            for warning in result["warnings"]:
                print(f"- {warning}")
    return 0 if result.get("ok", True) else 1


def command_revert_edge(args: argparse.Namespace) -> int:
    try:
        result = archive_services.zettel_edge_revert(
            Path(args.archive_root),
            receipt=args.receipt,
            dry_run=args.dry_run,
            approve=args.approve,
            reviewed_by=args.reviewed_by,
        )
    except (archive_services.ArchiveServiceError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        state = result.get("write_status") or ("passed" if result.get("ok") else "blocked")
        source = result.get("source") if isinstance(result.get("source"), dict) else {}
        edge = result.get("edge") if isinstance(result.get("edge"), dict) else {}
        print(f"Zettel edge revert: {state}.")
        print(f"Archive: {result.get('archive_id') or '-'}")
        print(f"Source: {source.get('zettel_id') or '-'}")
        print(f"Edge: {edge.get('edge_id') or '-'}")
        print(f"Receipt: {result.get('edge_receipt_path') or '-'}")
        print(f"Revert receipt: {result.get('revert_receipt_path') or '-'}")
        if result.get("files_written"):
            print("Files written:")
            for path in result["files_written"]:
                print(f"- {path}")
        elif result.get("would_change"):
            print("Would change:")
            for path in result["would_change"]:
                print(f"- {path}")
        if result.get("blockers"):
            print("Blockers:")
            for blocker in result["blockers"]:
                print(f"- {blocker}")
        if result.get("warnings"):
            print("Warnings:")
            for warning in result["warnings"]:
                print(f"- {warning}")
    return 0 if result.get("ok", True) else 1


def command_revert_batch(args: argparse.Namespace) -> int:
    try:
        result = archive_services.zettel_edge_batch_revert(
            Path(args.archive_root),
            receipt=args.receipt,
            dry_run=args.dry_run,
            approve=args.approve,
            reviewed_by=args.reviewed_by,
        )
    except (archive_services.ArchiveServiceError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        state = result.get("write_status") or ("passed" if result.get("ok") else "blocked")
        summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
        print(f"Zettel edge batch revert: {state}.")
        print(f"Archive: {result.get('archive_id') or '-'}")
        print(f"Edges to revert: {summary.get('edge_revert_count', 0)}")
        print(f"Receipt: {result.get('batch_receipt_path') or '-'}")
        print(f"Batch revert receipt: {result.get('batch_revert_receipt_path') or '-'}")
        if result.get("files_written"):
            print("Files written:")
            for path in result["files_written"]:
                print(f"- {path}")
        elif result.get("would_change"):
            print("Would change:")
            for path in result["would_change"]:
                print(f"- {path}")
        if result.get("blockers"):
            print("Blockers:")
            for blocker in result["blockers"]:
                print(f"- {blocker}")
        if result.get("warnings"):
            print("Warnings:")
            for warning in result["warnings"]:
                print(f"- {warning}")
    return 0 if result.get("ok", True) else 1


def command_prehashed_objet_ledger(args: argparse.Namespace) -> int:
    if args.dry_run == args.approve:
        print("prehashed-objet-ledger requires exactly one of --dry-run or --approve.", file=sys.stderr)
        return 1
    if args.approve and not args.reviewed_by:
        print("prehashed-objet-ledger requires --reviewed-by when --approve is used.", file=sys.stderr)
        return 1

    try:
        result = archive_services.prehashed_objet_ledger_register(
            Path(args.archive_root),
            [Path(item) for item in args.ledger],
            store_kind=args.store_kind,
            store_ref=args.store_ref,
            sha256_field=args.sha256_field,
            size_field=args.size_field,
            mime_field=args.mime_field,
            dry_run=args.dry_run,
            approve=args.approve,
            reviewed_by=args.reviewed_by,
            max_rows=args.max_rows,
        )
    except (archive_services.ArchiveServiceError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print_prehashed_objet_ledger_result(result, args.format)
    return 0 if result.get("ok", True) else 1


def command_object_storage_upload_evidence(args: argparse.Namespace) -> int:
    if args.dry_run == args.approve:
        print("object-storage-upload-evidence requires exactly one of --dry-run or --approve.", file=sys.stderr)
        return 1
    if args.approve and not args.reviewed_by:
        print("object-storage-upload-evidence requires --reviewed-by when --approve is used.", file=sys.stderr)
        return 1
    try:
        result = archive_services.object_storage_upload_evidence_register(
            Path(args.archive_root),
            [Path(item) for item in args.ledger],
            provider_kind=args.provider_kind,
            store_ref=args.store_ref,
            sha256_field=args.sha256_field,
            size_field=args.size_field,
            status_field=args.status_field,
            dry_run=args.dry_run,
            approve=args.approve,
            reviewed_by=args.reviewed_by,
            max_rows=args.max_rows,
        )
    except (archive_services.ArchiveServiceError, OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print_object_storage_upload_evidence_result(result, args.format)
    return 0 if result.get("ok", True) else 1


def command_object_storage_upload_evidence_audit(args: argparse.Namespace) -> int:
    if not args.dry_run:
        print("object-storage-upload-evidence-audit is read-only and requires --dry-run.", file=sys.stderr)
        return 1
    try:
        result = archive_services.object_storage_upload_evidence_audit(
            Path(args.archive_root),
            receipt=args.receipt,
            dry_run=True,
        )
    except (archive_services.ArchiveServiceError, OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print_object_storage_upload_evidence_audit_result(result, args.format)
    return 0 if result.get("ok", True) else 1


def command_resolve_objet_ref(args: argparse.Namespace) -> int:
    if not args.dry_run:
        print("resolve-objet-ref is read-only and requires --dry-run.", file=sys.stderr)
        return 1
    try:
        result = archive_services.resolve_objet_ref(
            Path(args.archive_root),
            object_id=args.object_id,
            dry_run=True,
        )
    except (archive_services.ArchiveServiceError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print_resolve_objet_ref_result(result, args.format)
    return 0 if result.get("ok", True) else 1


def command_presigned_url_plan(args: argparse.Namespace) -> int:
    if not args.dry_run:
        print("presigned-url-plan is read-only and requires --dry-run.", file=sys.stderr)
        return 1
    try:
        result = archive_services.presigned_url_plan(
            Path(args.archive_root),
            object_id=args.object_id,
            store_ref=args.store_ref,
            operation=args.operation,
            ttl_seconds=args.ttl_seconds,
            dry_run=True,
        )
    except (archive_services.ArchiveServiceError, OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print_presigned_url_plan_result(result, args.format)
    return 0 if result.get("ok", True) else 1


def command_object_storage_operation_request_plan(args: argparse.Namespace) -> int:
    if not args.dry_run:
        print("object-storage-operation-request-plan is read-only and requires --dry-run.", file=sys.stderr)
        return 1
    try:
        result = archive_services.object_storage_operation_request_plan(
            Path(args.archive_root),
            operation=args.operation,
            object_id=args.object_id,
            store_ref=args.store_ref,
            ttl_seconds=args.ttl_seconds,
            provider_ref=args.provider_ref,
            credential_id=args.credential_id,
            credential_ref=args.credential_ref,
            credential_kind=args.credential_kind,
            provider=args.provider,
            store_kind=args.store_kind,
            adapter_kind=args.adapter_kind,
            approval_decision=args.approval_decision,
            approval_receipt=args.approval_receipt,
            consumer=args.consumer,
            reviewed_by=args.reviewed_by,
            platform=args.platform,
            dry_run=True,
        )
    except (archive_services.ArchiveServiceError, OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print_object_storage_operation_request_plan_result(result, args.format)
    return 0 if result.get("ok", True) else 1


def command_object_storage_adapter_execution_contract(args: argparse.Namespace) -> int:
    if not args.dry_run:
        print("object-storage-adapter-execution-contract is read-only and requires --dry-run.", file=sys.stderr)
        return 1
    try:
        result = archive_services.object_storage_adapter_execution_contract(
            Path(args.archive_root),
            operation=args.operation,
            object_id=args.object_id,
            store_ref=args.store_ref,
            provider_ref=args.provider_ref,
            dry_run=True,
        )
    except (archive_services.ArchiveServiceError, OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print_object_storage_adapter_execution_contract_result(result, args.format)
    return 0 if result.get("ok", True) else 1


def command_imap_mailbox_operation_request_plan(args: argparse.Namespace) -> int:
    if not args.dry_run:
        print("imap-mailbox-operation-request-plan is read-only and requires --dry-run.", file=sys.stderr)
        return 1
    try:
        result = archive_services.imap_mailbox_operation_request_plan(
            Path(args.archive_root),
            source_id=args.source_id,
            provider=args.provider,
            imap_host=args.imap_host,
            imap_port=args.imap_port,
            account_ref=args.account_ref,
            username_ref=args.username_ref,
            auth_mode=args.auth_mode,
            app_password_ref=args.app_password_ref,
            oauth_token_ref=args.oauth_token_ref,
            mailbox_ref=args.mailbox_ref,
            operation=args.operation,
            max_messages=args.max_messages,
            since_days=args.since_days,
            credential_id=args.credential_id,
            credential_ref=args.credential_ref,
            credential_kind=args.credential_kind,
            credential_provider=args.credential_provider,
            store_kind=args.store_kind,
            adapter_kind=args.adapter_kind,
            approval_decision=args.approval_decision,
            approval_receipt=args.approval_receipt,
            consumer=args.consumer,
            reviewed_by=args.reviewed_by,
            platform=args.platform,
            dry_run=True,
        )
    except (archive_services.ArchiveServiceError, OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print_imap_mailbox_operation_request_plan_result(result, args.format)
    return 0 if result.get("ok", True) else 1


def command_imap_mailbox_plan(args: argparse.Namespace) -> int:
    if not args.dry_run:
        print("imap-mailbox-plan is dry-run only and requires --dry-run.", file=sys.stderr)
        return 1
    try:
        result = archive_services.imap_mailbox_plan(
            Path(args.archive_root),
            source_id=args.source_id,
            provider=args.provider,
            imap_host=args.imap_host,
            imap_port=args.imap_port,
            account_ref=args.account_ref,
            username_ref=args.username_ref,
            auth_mode=args.auth_mode,
            app_password_ref=args.app_password_ref,
            oauth_token_ref=args.oauth_token_ref,
            mailbox_ref=args.mailbox_ref,
            dry_run=True,
        )
    except (archive_services.ArchiveServiceError, OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        state = "passed" if result.get("ok") else "blocked"
        print(f"IMAP mailbox plan {state}.")
        print(f"Archive: {result.get('archive_id') or '-'}")
        print(f"Source: {result.get('source_id') or '-'} ({result.get('source_type') or '-'})")
        print(f"Provider: {result.get('provider') or '-'}")
        server = result.get("server") if isinstance(result.get("server"), dict) else {}
        print(f"Server: {server.get('imap_host') or '-'}:{server.get('imap_port') or '-'}")
        print("Writes: none")
        if result.get("blockers"):
            print("Blockers:")
            for blocker in result["blockers"]:
                print(f"- {blocker}")
        if result.get("warnings"):
            print("Warnings:")
            for warning in result["warnings"]:
                print(f"- {warning}")
    return 0 if result.get("ok", True) else 1


def command_credential_ref_plan(args: argparse.Namespace) -> int:
    if not args.dry_run:
        print("credential-ref-plan is dry-run only and requires --dry-run.", file=sys.stderr)
        return 1
    try:
        result = archive_services.credential_ref_plan(
            Path(args.archive_root),
            credential_id=args.credential_id,
            credential_ref=args.credential_ref,
            credential_kind=args.credential_kind,
            purpose=args.purpose,
            provider=args.provider,
            dry_run=True,
        )
    except (archive_services.ArchiveServiceError, OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        state = "passed" if result.get("ok") else "blocked"
        print(f"Credential ref plan {state}.")
        print(f"Archive: {result.get('archive_id') or '-'}")
        print(f"Credential: {result.get('credential_id') or '-'} ({result.get('credential_kind') or '-'})")
        print(f"Provider: {result.get('provider') or '-'}")
        print(f"Store: {result.get('credential_store') or '-'}")
        print("Writes: none")
        if result.get("blockers"):
            print("Blockers:")
            for blocker in result["blockers"]:
                print(f"- {blocker}")
        if result.get("warnings"):
            print("Warnings:")
            for warning in result["warnings"]:
                print(f"- {warning}")
    return 0 if result.get("ok", True) else 1


def command_credential_ref_inventory(args: argparse.Namespace) -> int:
    if not args.dry_run:
        print("credential-ref-inventory is read-only and requires --dry-run.", file=sys.stderr)
        return 1
    try:
        result = archive_services.credential_ref_inventory(
            Path(args.archive_root),
            dry_run=True,
        )
    except (archive_services.ArchiveServiceError, OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        state = "passed" if result.get("ok") else "blocked"
        print(f"Credential ref inventory {state}.")
        print(f"Archive: {result.get('archive_id') or '-'}")
        print(f"Credentials: {result.get('credential_count', 0)}")
        for item in result.get("credentials") or []:
            if not isinstance(item, dict):
                continue
            print(
                "- "
                f"{item.get('credential_id') or '-'} "
                f"{item.get('credential_kind') or '-'} "
                f"{item.get('provider') or '-'} "
                f"{item.get('ref_prefix') or '-'}"
            )
        if result.get("blockers"):
            print("Blockers:")
            for blocker in result["blockers"]:
                print(f"- {blocker}")
        if result.get("warnings"):
            print("Warnings:")
            for warning in result["warnings"]:
                print(f"- {warning}")
    return 0 if result.get("ok", True) else 1


def command_connected_accounts(args: argparse.Namespace) -> int:
    if not args.dry_run:
        print("connected-accounts is read-only and requires --dry-run.", file=sys.stderr)
        return 1
    try:
        result = archive_services.connected_accounts_overview(
            Path(args.archive_root),
            include_disabled=args.include_disabled,
            dry_run=True,
        )
    except (archive_services.ArchiveServiceError, OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        state = "passed" if result.get("ok") else "blocked"
        print(f"Connected accounts dry-run {state}.")
        print(f"Archive: {result.get('archive_id') or '-'}")
        print(f"Accounts: {result.get('account_count', 0)}")
        print("Writes: none")
        for account in result.get("accounts") or []:
            if not isinstance(account, dict):
                continue
            stores = account.get("credential_store_summary") if isinstance(account.get("credential_store_summary"), dict) else {}
            store_text = ", ".join(f"{key}:{value}" for key, value in stores.items()) if stores else "none"
            print(
                "- "
                f"{account.get('account_label') or '-'} "
                f"{account.get('account_kind') or '-'} "
                f"{account.get('provider') or '-'} "
                f"stores={store_text}"
            )
        catalog = result.get("credential_catalog") if isinstance(result.get("credential_catalog"), dict) else {}
        print(f"Credential catalog refs: {catalog.get('credential_count', 0)}")
        print(f"Credential catalog status: {catalog.get('status') or '-'}")
        if catalog.get("blockers"):
            print("Credential catalog blockers:")
            for blocker in catalog["blockers"]:
                print(f"- {blocker}")
        if result.get("blockers"):
            print("Blockers:")
            for blocker in result["blockers"]:
                print(f"- {blocker}")
        if result.get("warnings"):
            print("Warnings:")
            for warning in result["warnings"]:
                print(f"- {warning}")
    return 0 if result.get("ok", True) else 1


def command_credential_store_recommendation(args: argparse.Namespace) -> int:
    if not args.dry_run:
        print("credential-store-recommendation is read-only and requires --dry-run.", file=sys.stderr)
        return 1
    try:
        result = archive_services.credential_store_recommendation(
            Path(args.archive_root),
            scenario=args.scenario,
            platform=args.platform,
            dry_run=True,
        )
    except (archive_services.ArchiveServiceError, OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        state = "passed" if result.get("ok") else "blocked"
        primary = result.get("primary_recommendation") if isinstance(result.get("primary_recommendation"), dict) else {}
        print(f"Credential store recommendation {state}.")
        print(f"Archive: {result.get('archive_id') or '-'}")
        print(f"Scenario: {result.get('scenario') or '-'}")
        print(f"Platform: {result.get('platform') or '-'}")
        print(f"Primary: {primary.get('store_id') or '-'} ({primary.get('store_class') or '-'})")
        print(f"WOM ref prefix: {primary.get('wom_ref_prefix') or '-'}")
        print("Writes: none")
        if result.get("blockers"):
            print("Blockers:")
            for blocker in result["blockers"]:
                print(f"- {blocker}")
        if result.get("warnings"):
            print("Warnings:")
            for warning in result["warnings"]:
                print(f"- {warning}")
    return 0 if result.get("ok", True) else 1


def command_credential_vault_onboarding_plan(args: argparse.Namespace) -> int:
    if not args.dry_run:
        print("credential-vault-onboarding-plan is read-only and requires --dry-run.", file=sys.stderr)
        return 1
    try:
        result = archive_services.credential_vault_onboarding_plan(
            Path(args.archive_root),
            scenario=args.scenario,
            store_id=args.store_id,
            credential_id=args.credential_id,
            credential_kind=args.credential_kind,
            provider=args.provider,
            action_kind=args.action_kind,
            platform=args.platform,
            dry_run=True,
        )
    except (archive_services.ArchiveServiceError, OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        state = "passed" if result.get("ok") else "blocked"
        store = result.get("selected_store") if isinstance(result.get("selected_store"), dict) else {}
        credential = result.get("credential_plan") if isinstance(result.get("credential_plan"), dict) else {}
        print(f"Credential vault onboarding plan {state}.")
        print(f"Archive: {result.get('archive_id') or '-'}")
        print(f"Scenario: {result.get('scenario') or '-'}")
        print(f"Store: {store.get('store_id') or '-'} ({store.get('store_class') or '-'})")
        print(f"WOM ref prefix: {credential.get('safe_ref_prefix_to_record') or '-'}")
        print("Writes: none")
        if result.get("blockers"):
            print("Blockers:")
            for blocker in result["blockers"]:
                print(f"- {blocker}")
        if result.get("warnings"):
            print("Warnings:")
            for warning in result["warnings"]:
                print(f"- {warning}")
    return 0 if result.get("ok", True) else 1


def command_beginner_setup_manual(args: argparse.Namespace) -> int:
    if not args.dry_run:
        print("beginner-setup-manual is read-only and requires --dry-run.", file=sys.stderr)
        return 1
    try:
        result = archive_services.beginner_setup_manual(
            Path(args.archive_root),
            topic=args.topic,
            scenario=args.scenario,
            store_id=args.store_id,
            platform=args.platform,
            dry_run=True,
        )
    except (archive_services.ArchiveServiceError, OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        state = "passed" if result.get("ok") else "blocked"
        print(f"Beginner setup manual {state}.")
        print(f"Archive: {result.get('archive_id') or '-'}")
        print(f"Topic: {result.get('topic') or '-'}")
        print(f"Scenario: {result.get('scenario') or '-'}")
        print(f"Store: {result.get('selected_store_id') or '-'}")
        for section in result.get("sections", []):
            if not isinstance(section, dict):
                continue
            print(f"\n{section.get('title') or section.get('section_id') or 'Section'}")
            if section.get("beginner_explanation"):
                print(str(section["beginner_explanation"]))
            for step in section.get("steps") or []:
                print(f"- {step}")
        if result.get("command_checklist"):
            print("\nCommands to dry-run:")
            for command in result["command_checklist"]:
                print(f"- {command}")
        if result.get("blockers"):
            print("\nBlockers:")
            for blocker in result["blockers"]:
                print(f"- {blocker}")
        if result.get("warnings"):
            print("\nWarnings:")
            for warning in result["warnings"]:
                print(f"- {warning}")
    return 0 if result.get("ok", True) else 1


def command_ai_response_concept_guide(args: argparse.Namespace) -> int:
    if not args.dry_run:
        print("ai-response-concept-guide is read-only and requires --dry-run.", file=sys.stderr)
        return 1
    try:
        result = archive_services.ai_response_concept_guide(
            Path(args.archive_root),
            topic=args.topic,
            locale=args.locale,
            dry_run=True,
        )
    except (archive_services.ArchiveServiceError, OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        state = "passed" if result.get("ok") else "blocked"
        print(f"AI response concept guide {state}.")
        print(f"Archive: {result.get('archive_id') or '-'}")
        print(f"Topic: {result.get('topic') or '-'}")
        print(f"Locale: {result.get('locale') or '-'}")
        for section in result.get("sections", []):
            if not isinstance(section, dict):
                continue
            print(f"\n{section.get('title') or section.get('section_id') or 'Section'}")
            if section.get("beginner_explanation"):
                print(str(section["beginner_explanation"]))
            if section.get("short_script"):
                print(f"Script: {section['short_script']}")
            if section.get("korean_script"):
                print(f"Korean script: {section['korean_script']}")
            if section.get("safe_warning"):
                print(f"Warning: {section['safe_warning']}")
            if section.get("edge_type_terms"):
                print("Edge type terms:")
                for term in section["edge_type_terms"]:
                    if isinstance(term, dict):
                        print(f"- {term.get('term') or '-'}: {term.get('selected_user_phrase') or '-'}")
        if result.get("next_safe_question"):
            print("\nNext safe question:")
            print(str(result["next_safe_question"]))
        if result.get("safe_routing"):
            print("\nSafe routing:")
            for route in result["safe_routing"]:
                if not isinstance(route, dict):
                    continue
                print(f"- {route.get('human_intent') or '-'}: {route.get('command') or '-'}")
        if result.get("blockers"):
            print("\nBlockers:")
            for blocker in result["blockers"]:
                print(f"- {blocker}")
        if result.get("warnings"):
            print("\nWarnings:")
            for warning in result["warnings"]:
                print(f"- {warning}")
    return 0 if result.get("ok", True) else 1


def command_credential_plaintext_migration_plan(args: argparse.Namespace) -> int:
    if not args.dry_run:
        print("credential-plaintext-migration-plan is read-only and requires --dry-run.", file=sys.stderr)
        return 1
    try:
        result = archive_services.credential_plaintext_migration_plan(
            Path(args.archive_root),
            source_label=args.source_label,
            credential_id=args.credential_id,
            target_store_id=args.target_store_id,
            scenario=args.scenario,
            credential_kind=args.credential_kind,
            provider=args.provider,
            platform=args.platform,
            dry_run=True,
        )
    except (archive_services.ArchiveServiceError, OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        state = "passed" if result.get("ok") else "blocked"
        target = result.get("target") if isinstance(result.get("target"), dict) else {}
        print(f"Credential plaintext migration plan {state}.")
        print(f"Archive: {result.get('archive_id') or '-'}")
        print(f"Source label: {(result.get('source') or {}).get('source_label') if isinstance(result.get('source'), dict) else '-'}")
        print(f"Target store: {target.get('selected_store_id') or '-'} ({target.get('store_kind') or '-'})")
        print(f"WOM ref prefix: {target.get('wom_ref_prefix') or '-'}")
        print("Writes: none")
        if result.get("blockers"):
            print("Blockers:")
            for blocker in result["blockers"]:
                print(f"- {blocker}")
        if result.get("warnings"):
            print("Warnings:")
            for warning in result["warnings"]:
                print(f"- {warning}")
    return 0 if result.get("ok", True) else 1


def command_credential_semantic_extraction_recipe(args: argparse.Namespace) -> int:
    if not args.dry_run:
        print("credential-semantic-extraction-recipe is read-only and requires --dry-run.", file=sys.stderr)
        return 1
    try:
        result = archive_services.credential_semantic_extraction_recipe(
            Path(args.archive_root),
            source_label=args.source_label,
            source_kind=args.source_kind,
            context=args.context,
            target_store_id=args.target_store_id,
            platform=args.platform,
            dry_run=True,
        )
    except (archive_services.ArchiveServiceError, OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        state = "passed" if result.get("ok") else "blocked"
        source = result.get("source") if isinstance(result.get("source"), dict) else {}
        recipe_context = result.get("recipe_context") if isinstance(result.get("recipe_context"), dict) else {}
        print(f"Credential semantic extraction recipe {state}.")
        print(f"Archive: {result.get('archive_id') or '-'}")
        print(f"Source label: {source.get('source_label') or '-'}")
        print(f"Context: {recipe_context.get('context') or '-'}")
        print(f"Target store: {recipe_context.get('target_store_id') or '-'}")
        print("Writes: none")
        if result.get("entry_classes"):
            print("Entry classes:")
            for entry_class in result["entry_classes"]:
                if isinstance(entry_class, dict):
                    print(f"- {entry_class.get('class_id') or '-'}")
        if result.get("blockers"):
            print("Blockers:")
            for blocker in result["blockers"]:
                print(f"- {blocker}")
        if result.get("warnings"):
            print("Warnings:")
            for warning in result["warnings"]:
                print(f"- {warning}")
    return 0 if result.get("ok", True) else 1


def command_credential_policy_check(args: argparse.Namespace) -> int:
    if not args.dry_run:
        print("credential-policy-check is read-only and requires --dry-run.", file=sys.stderr)
        return 1
    try:
        result = archive_services.credential_policy_check(
            Path(args.archive_root),
            credential_id=args.credential_id,
            credential_ref=args.credential_ref,
            credential_kind=args.credential_kind,
            provider=args.provider,
            action_kind=args.action_kind,
            approval_decision=args.approval_decision,
            store_kind=args.store_kind,
            adapter_kind=args.adapter_kind,
            operation=args.operation,
            consumer=args.consumer,
            reviewed_by=args.reviewed_by,
            platform=args.platform,
            approval_receipt=args.approval_receipt,
            dry_run=True,
        )
    except (archive_services.ArchiveServiceError, OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        request = result.get("request") if isinstance(result.get("request"), dict) else {}
        evaluation = result.get("policy_evaluation") if isinstance(result.get("policy_evaluation"), dict) else {}
        print(f"Credential policy check: {result.get('policy_result') or '-'}")
        print(f"Archive: {result.get('archive_id') or '-'}")
        print(f"Credential: {request.get('credential_id') or '-'} ({request.get('credential_kind') or '-'})")
        print(f"Action: {request.get('action_kind') or '-'}")
        print(f"Adapter: {request.get('adapter_kind') or '-'} / {request.get('operation') or '-'}")
        print(f"Future adapter allowed after approval receipt: {evaluation.get('would_allow_future_adapter_after_receipt')}")
        print("Writes: none")
        if result.get("blockers"):
            print("Blockers:")
            for blocker in result["blockers"]:
                print(f"- {blocker}")
        if evaluation.get("denied_rules"):
            print("Denied rules:")
            for rule in evaluation["denied_rules"]:
                print(f"- {rule}")
        if result.get("warnings"):
            print("Warnings:")
            for warning in result["warnings"]:
                print(f"- {warning}")
    return 0 if result.get("ok", True) else 1


def command_credential_keepassxc_command_plan(args: argparse.Namespace) -> int:
    if not args.dry_run:
        print("credential-keepassxc-command-plan is read-only and requires --dry-run.", file=sys.stderr)
        return 1
    try:
        result = archive_services.credential_keepassxc_command_plan(
            Path(args.archive_root),
            credential_id=args.credential_id,
            credential_ref=args.credential_ref,
            credential_kind=args.credential_kind,
            provider=args.provider,
            action_kind=args.action_kind,
            operation=args.operation,
            approval_receipt=args.approval_receipt,
            entry_label=args.entry_label,
            group_label=args.group_label,
            database_ref=args.database_ref,
            consumer=args.consumer,
            reviewed_by=args.reviewed_by,
            platform=args.platform,
            dry_run=True,
        )
    except (archive_services.ArchiveServiceError, OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        state = "passed" if result.get("ok") else "blocked"
        adapter = result.get("adapter") if isinstance(result.get("adapter"), dict) else {}
        command_plan = result.get("command_plan") if isinstance(result.get("command_plan"), dict) else {}
        print(f"Credential KeePassXC command plan {state}.")
        print(f"Archive: {result.get('archive_id') or '-'}")
        print(f"Adapter: {adapter.get('adapter_kind') or '-'} / {adapter.get('operation') or '-'}")
        print(f"Approval receipt verified: {adapter.get('approval_receipt_verified')}")
        print("Command preview:")
        print("  " + " ".join(str(item) for item in command_plan.get("argv_preview") or []))
        print("Writes: none")
        if result.get("blockers"):
            print("Blockers:")
            for blocker in result["blockers"]:
                print(f"- {blocker}")
        if result.get("warnings"):
            print("Warnings:")
            for warning in result["warnings"]:
                print(f"- {warning}")
    return 0 if result.get("ok", True) else 1


def command_credential_access_broker_plan(args: argparse.Namespace) -> int:
    if not args.dry_run:
        print("credential-access-broker-plan is read-only and requires --dry-run.", file=sys.stderr)
        return 1
    try:
        result = archive_services.credential_access_broker_plan(
            Path(args.archive_root),
            credential_id=args.credential_id,
            credential_ref=args.credential_ref,
            credential_kind=args.credential_kind,
            provider=args.provider,
            action_kind=args.action_kind,
            store_kind=args.store_kind,
            consumer=args.consumer,
            platform=args.platform,
            dry_run=True,
        )
    except (archive_services.ArchiveServiceError, OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        state = "passed" if result.get("ok") else "blocked"
        credential = result.get("credential") if isinstance(result.get("credential"), dict) else {}
        request = result.get("broker_request") if isinstance(result.get("broker_request"), dict) else {}
        print(f"Credential access broker plan {state}.")
        print(f"Archive: {result.get('archive_id') or '-'}")
        print(f"Credential: {credential.get('credential_id') or '-'} ({credential.get('credential_kind') or '-'})")
        print(f"Action: {request.get('action_kind') or '-'}")
        print(f"Store: {request.get('store_kind') or '-'}")
        print(f"Secret returned to AI: {request.get('secret_value_return_to_ai')}")
        print("Writes: none")
        if result.get("blockers"):
            print("Blockers:")
            for blocker in result["blockers"]:
                print(f"- {blocker}")
        if result.get("warnings"):
            print("Warnings:")
            for warning in result["warnings"]:
                print(f"- {warning}")
    return 0 if result.get("ok", True) else 1


def command_credential_access_approval_plan(args: argparse.Namespace) -> int:
    if args.dry_run == args.approve:
        print("Choose exactly one mode: --dry-run or --approve.", file=sys.stderr)
        return 1
    try:
        result = archive_services.credential_access_approval_plan(
            Path(args.archive_root),
            credential_id=args.credential_id,
            credential_ref=args.credential_ref,
            credential_kind=args.credential_kind,
            provider=args.provider,
            action_kind=args.action_kind,
            decision=args.decision,
            store_kind=args.store_kind,
            consumer=args.consumer,
            reviewed_by=args.reviewed_by,
            platform=args.platform,
            dry_run=args.dry_run,
            approve=args.approve,
        )
    except (archive_services.ArchiveServiceError, OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        state = "passed" if result.get("ok") else "blocked"
        summary = result.get("broker_plan_summary") if isinstance(result.get("broker_plan_summary"), dict) else {}
        print(f"Credential access approval plan {state}.")
        print(f"Archive: {result.get('archive_id') or '-'}")
        print(f"Decision: {result.get('decision') or '-'}")
        print(f"Action: {summary.get('action_kind') or '-'}")
        print(f"Credential: {summary.get('credential_id') or '-'}")
        print(f"Receipt: {result.get('receipt_path') or result.get('proposed_receipt_path') or '-'}")
        print(f"Writes: {'receipt' if result.get('files_written') else 'none'}")
        if result.get("blockers"):
            print("Blockers:")
            for blocker in result["blockers"]:
                print(f"- {blocker}")
        if result.get("warnings"):
            print("Warnings:")
            for warning in result["warnings"]:
                print(f"- {warning}")
    return 0 if result.get("ok", True) else 1


def command_credential_adapter_readiness_plan(args: argparse.Namespace) -> int:
    if not args.dry_run:
        print("credential-adapter-readiness-plan is read-only and requires --dry-run.", file=sys.stderr)
        return 1
    try:
        result = archive_services.credential_adapter_readiness_plan(
            Path(args.archive_root),
            adapter_kind=args.adapter_kind,
            operation=args.operation,
            credential_id=args.credential_id,
            credential_ref=args.credential_ref,
            credential_kind=args.credential_kind,
            provider=args.provider,
            action_kind=args.action_kind,
            store_kind=args.store_kind,
            consumer=args.consumer,
            platform=args.platform,
            dry_run=True,
        )
    except (archive_services.ArchiveServiceError, OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        state = "passed" if result.get("ok") else "blocked"
        adapter = result.get("adapter") if isinstance(result.get("adapter"), dict) else {}
        operation = result.get("operation") if isinstance(result.get("operation"), dict) else {}
        print(f"Credential adapter readiness plan {state}.")
        print(f"Archive: {result.get('archive_id') or '-'}")
        print(f"Adapter: {adapter.get('adapter_kind') or '-'} ({adapter.get('store_kind') or '-'})")
        print(f"Operation: {operation.get('operation') or '-'} / {operation.get('action_kind') or '-'}")
        print("Writes: none")
        if result.get("blockers"):
            print("Blockers:")
            for blocker in result["blockers"]:
                print(f"- {blocker}")
        if result.get("warnings"):
            print("Warnings:")
            for warning in result["warnings"]:
                print(f"- {warning}")
    return 0 if result.get("ok", True) else 1


def command_credential_adapter_manifest_plan(args: argparse.Namespace) -> int:
    if not args.dry_run:
        print("credential-adapter-manifest-plan is read-only and requires --dry-run.", file=sys.stderr)
        return 1
    try:
        result = archive_services.credential_adapter_manifest_plan(
            Path(args.archive_root),
            adapter_id=args.adapter_id,
            adapter_kind=args.adapter_kind,
            operations=args.operation,
            store_kind=args.store_kind,
            consumer=args.consumer,
            platform=args.platform,
            dry_run=True,
        )
    except (archive_services.ArchiveServiceError, OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        state = "passed" if result.get("ok") else "blocked"
        manifest = result.get("manifest_preview") if isinstance(result.get("manifest_preview"), dict) else {}
        schema = result.get("schema_validation") if isinstance(result.get("schema_validation"), dict) else {}
        print(f"Credential adapter manifest plan {state}.")
        print(f"Archive: {result.get('archive_id') or '-'}")
        print(f"Adapter: {manifest.get('adapter_id') or '-'} ({manifest.get('adapter_kind') or '-'})")
        print(f"Manifest: {result.get('proposed_manifest_path') or '-'}")
        print(f"Schema valid: {schema.get('ok')}")
        print("Writes: none")
        if result.get("blockers"):
            print("Blockers:")
            for blocker in result["blockers"]:
                print(f"- {blocker}")
        if result.get("warnings"):
            print("Warnings:")
            for warning in result["warnings"]:
                print(f"- {warning}")
    return 0 if result.get("ok", True) else 1


def command_credential_adapter_audit_plan(args: argparse.Namespace) -> int:
    if not args.dry_run:
        print("credential-adapter-audit-plan is read-only and requires --dry-run.", file=sys.stderr)
        return 1
    try:
        result = archive_services.credential_adapter_audit_plan(
            Path(args.archive_root),
            adapter_id=args.adapter_id,
            adapter_kind=args.adapter_kind,
            operation=args.operation,
            credential_id=args.credential_id,
            credential_kind=args.credential_kind,
            provider=args.provider,
            action_kind=args.action_kind,
            result_status=args.result_status,
            store_kind=args.store_kind,
            consumer=args.consumer,
            platform=args.platform,
            dry_run=True,
        )
    except (archive_services.ArchiveServiceError, OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        state = "passed" if result.get("ok") else "blocked"
        receipt = result.get("receipt_preview") if isinstance(result.get("receipt_preview"), dict) else {}
        adapter = receipt.get("adapter") if isinstance(receipt.get("adapter"), dict) else {}
        print(f"Credential adapter audit plan {state}.")
        print(f"Archive: {result.get('archive_id') or '-'}")
        print(f"Adapter: {adapter.get('adapter_id') or '-'} ({adapter.get('adapter_kind') or '-'})")
        print(f"Receipt: {result.get('proposed_receipt_path') or '-'}")
        print(f"Result status: {receipt.get('result_status') or '-'}")
        print("Writes: none")
        if result.get("blockers"):
            print("Blockers:")
            for blocker in result["blockers"]:
                print(f"- {blocker}")
        if result.get("warnings"):
            print("Warnings:")
            for warning in result["warnings"]:
                print(f"- {warning}")
    return 0 if result.get("ok", True) else 1


def command_credential_keepassxc_write(args: argparse.Namespace) -> int:
    if args.dry_run == args.approve:
        print("Choose exactly one mode: --dry-run or --approve.", file=sys.stderr)
        return 1
    try:
        result = archive_services.credential_keepassxc_write(
            Path(args.archive_root),
            credential_id=args.credential_id,
            credential_ref=args.credential_ref,
            credential_kind=args.credential_kind,
            provider=args.provider,
            action_kind=args.action_kind,
            operation=args.operation,
            approval_receipt=args.approval_receipt,
            entry_label=args.entry_label,
            group_label=args.group_label,
            database_ref=args.database_ref,
            database_path=args.database_path,
            consumer=args.consumer,
            reviewed_by=args.reviewed_by,
            platform=args.platform,
            dry_run=args.dry_run,
            approve=args.approve,
        )
    except (archive_services.ArchiveServiceError, OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        state = result.get("execution_status") or ("passed" if result.get("ok") else "blocked")
        print(f"Credential KeePassXC write {state}.")
        print(f"Archive: {result.get('archive_id') or '-'}")
        print(f"Receipt: {result.get('receipt_path') or result.get('proposed_receipt_path') or '-'}")
        target = result.get("target") if isinstance(result.get("target"), dict) else {}
        print(f"Entry: {target.get('entry_target') or '-'}")
        print(f"Database path echoed: {target.get('database_path_included')}")
        print(f"Secret returned to AI: {result.get('execution_boundary', {}).get('secret_value_return_to_ai')}")
        writes = result.get("files_written") or []
        if writes:
            print("Files written:")
            for path in writes:
                print(f"- {path}")
        else:
            print("Writes: none")
        if result.get("blockers"):
            print("Blockers:")
            for blocker in result["blockers"]:
                print(f"- {blocker}")
        if result.get("warnings"):
            print("Warnings:")
            for warning in result["warnings"]:
                print(f"- {warning}")
    return 0 if result.get("ok", True) else 1


def command_project_intake_unpack_queue(args: argparse.Namespace) -> int:
    if not args.dry_run:
        print("project-intake-unpack-queue is read-only and requires --dry-run.", file=sys.stderr)
        return 1
    try:
        result = archive_services.project_intake_unpack_queue(
            Path(args.archive_root),
            Path(args.staged_folder),
            receipt=args.receipt,
            max_items=args.max_items,
            dry_run=True,
        )
    except (archive_services.ArchiveServiceError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print_project_intake_unpack_queue_result(result, args.format)
    return 0 if result.get("ok", True) else 1


def print_project_intake_unpack_queue_result(result: dict[str, Any], output_format: str) -> None:
    if output_format == "json":
        print_json(result)
        return
    state = str(result.get("state") or ("passed" if result.get("ok") else "blocked"))
    queue = result.get("unpack_queue") if isinstance(result.get("unpack_queue"), dict) else {}
    turn = result.get("next_human_turn") if isinstance(result.get("next_human_turn"), dict) else {}
    print(f"Project intake unpack queue {state}.")
    print(f"Archive: {result.get('archive_id') or '-'}")
    print(f"Items: {queue.get('returned_item_count', 0)} of {queue.get('total_item_count', 0)}")
    print(f"Names included: {queue.get('entry_names_included', False)}")
    for item in queue.get("items", []):
        if isinstance(item, dict):
            print(
                f"- {item.get('item_ref')}: {item.get('kind')}"
                f" ext={item.get('extension') or '-'} size={item.get('size_bucket') or '-'}"
            )
    if turn.get("ask_user"):
        print(f"Ask: {turn['ask_user']}")
    if result.get("blockers"):
        print("Blockers:")
        for blocker in result["blockers"]:
            print(f"- {blocker}")
    if result.get("warnings"):
        print("Warnings:")
        for warning in result["warnings"]:
            print(f"- {warning}")


def command_project_intake_unpack_choice(args: argparse.Namespace) -> int:
    try:
        result = archive_services.project_intake_unpack_choice(
            Path(args.archive_root),
            Path(args.choice),
            receipt=args.receipt,
            staged_folder=Path(args.staged_folder),
            dry_run=args.dry_run,
            approve=args.approve,
            reviewed_by=args.reviewed_by,
        )
    except (archive_services.ArchiveServiceError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print_project_intake_unpack_choice_result(result, args.format)
    return 0 if result.get("ok", True) else 1


def print_project_intake_unpack_choice_result(result: dict[str, Any], output_format: str) -> None:
    if output_format == "json":
        print_json(result)
        return
    mode = "dry-run ready" if result.get("dry_run") else "recorded"
    if not result.get("ok", True):
        mode = "blocked"
    choice = result.get("choice_summary") if isinstance(result.get("choice_summary"), dict) else {}
    queue = result.get("queue_context") if isinstance(result.get("queue_context"), dict) else {}
    selected = queue.get("selected_item") if isinstance(queue.get("selected_item"), dict) else {}
    print(f"Project intake unpack choice {mode}.")
    print(f"Archive: {result.get('archive_id') or '-'}")
    print(f"Session: {result.get('session_id') or '-'}")
    print(f"Project intake receipt: {result.get('project_intake_receipt') or '-'}")
    print(f"Selected item ref: {choice.get('item_ref') or '-'}")
    print(f"Intended action: {choice.get('intended_action') or '-'}")
    print(f"Selected kind: {selected.get('kind') or '-'}")
    print(f"Queue digest: {queue.get('queue_sha256') or '-'}")
    if result.get("receipt_path"):
        print(f"Receipt: {result['receipt_path']}")
    else:
        print(f"Proposed receipt: {result.get('proposed_receipt_path') or '-'}")
    writes = result.get("files_written") or []
    if writes:
        print("Files written:")
        for path in writes:
            print(f"- {path}")
    else:
        print("Writes: none")
    if result.get("blockers"):
        print("Blockers:")
        for blocker in result["blockers"]:
            print(f"- {blocker}")
    if result.get("warnings"):
        print("Warnings:")
        for warning in result["warnings"]:
            print(f"- {warning}")
    if result.get("next_safe_actions"):
        print("Next safe actions:")
        for action in result["next_safe_actions"]:
            print(f"- {action}")


def print_prehashed_objet_ledger_result(result: dict[str, Any], output_format: str) -> None:
    if output_format == "json":
        print_json(result)
        return
    state = "passed" if result.get("ok") else "blocked"
    ledger = result.get("ledger") if isinstance(result.get("ledger"), dict) else {}
    print(f"Prehashed objet ledger preview {state}.")
    print(f"Archive: {result.get('archive_id') or '-'}")
    print(f"Store kind: {result.get('store_kind') or '-'}")
    print(f"Ledger files: {ledger.get('ledger_file_count', 0)}")
    print(f"Rows: {ledger.get('row_count', 0)}")
    print(f"Valid objects: {ledger.get('valid_object_count', 0)}")
    print(f"Skipped rows: {ledger.get('skipped_row_count', 0)}")
    print(f"Invalid rows: {ledger.get('invalid_row_count', 0)}")
    print(f"Duplicate sha256 rows: {ledger.get('duplicate_sha256_count', 0)}")
    registration = result.get("registration") if isinstance(result.get("registration"), dict) else {}
    if result.get("dry_run"):
        print(f"Would append manifest records: {registration.get('would_append_manifest_records', 0)}")
        print("Writes: none")
    else:
        print(f"Appended manifest records: {registration.get('appended_manifest_records', 0)}")
        print(f"Receipt: {registration.get('receipt_path') or '-'}")
    if result.get("blockers"):
        print("Blockers:")
        for blocker in result["blockers"]:
            print(f"- {blocker}")
    if result.get("warnings"):
        print("Warnings:")
        for warning in result["warnings"]:
            print(f"- {warning}")


def print_object_storage_upload_evidence_result(result: dict[str, Any], output_format: str) -> None:
    if output_format == "json":
        print_json(result)
        return
    state = "passed" if result.get("ok") else "blocked"
    evidence = result.get("evidence") if isinstance(result.get("evidence"), dict) else {}
    update = result.get("manifest_update") if isinstance(result.get("manifest_update"), dict) else {}
    receipt = result.get("receipt") if isinstance(result.get("receipt"), dict) else {}
    print(f"Object-storage upload evidence {state}.")
    print(f"Archive: {result.get('archive_id') or '-'}")
    print(f"Provider: {result.get('provider_kind') or '-'}")
    print(f"Store ref: {result.get('store_ref') or '-'}")
    print(f"Ledger files: {evidence.get('ledger_file_count', 0)}")
    print(f"Rows: {evidence.get('row_count', 0)}")
    print(f"Successful evidence rows: {evidence.get('successful_upload_count', 0)}")
    print(f"Matched manifest records: {update.get('matched_manifest_records', 0)}")
    if result.get("dry_run"):
        print(f"Would add locations: {update.get('would_add_locations', 0)}")
        print("Writes: none")
    else:
        print(f"Added locations: {update.get('added_locations', 0)}")
        print(f"Receipt: {receipt.get('receipt_path') or '-'}")
    if result.get("blockers"):
        print("Blockers:")
        for blocker in result["blockers"]:
            print(f"- {blocker}")
    if result.get("warnings"):
        print("Warnings:")
        for warning in result["warnings"]:
            print(f"- {warning}")


def print_object_storage_upload_evidence_audit_result(result: dict[str, Any], output_format: str) -> None:
    if output_format == "json":
        print_json(result)
        return
    state = "passed" if result.get("ok") else "blocked"
    receipt = result.get("receipt_summary") if isinstance(result.get("receipt_summary"), dict) else {}
    manifest = result.get("manifest_check") if isinstance(result.get("manifest_check"), dict) else {}
    print(f"Object-storage upload evidence audit {state}.")
    print(f"Archive: {result.get('archive_id') or '-'}")
    print(f"Provider: {receipt.get('provider_kind') or '-'}")
    print(f"Store ref: {receipt.get('store_ref') or '-'}")
    print(f"Receipt loaded: {receipt.get('receipt_loaded', False)}")
    print(f"Manifest locations: {manifest.get('matching_locations', 0)}")
    print(f"Invalid locations: {manifest.get('invalid_location_count', 0)}")
    print("Writes: none")
    if result.get("blockers"):
        print("Blockers:")
        for blocker in result["blockers"]:
            print(f"- {blocker}")
    if result.get("warnings"):
        print("Warnings:")
        for warning in result["warnings"]:
            print(f"- {warning}")


def print_resolve_objet_ref_result(result: dict[str, Any], output_format: str) -> None:
    if output_format == "json":
        print_json(result)
        return
    state = result.get("resolution_state") or ("passed" if result.get("ok") else "blocked")
    print(f"Objet ref resolution {state}.")
    print(f"Archive: {result.get('archive_id') or '-'}")
    print(f"Object id: {result.get('object_id') or '-'}")
    print(f"Manifest records: {result.get('manifest_record_count', 0)}")
    local_candidates = result.get("local_candidates") if isinstance(result.get("local_candidates"), list) else []
    if local_candidates:
        print("Local candidates:")
        for candidate in local_candidates:
            if not isinstance(candidate, dict):
                continue
            state_label = "exists" if candidate.get("exists") else "missing"
            print(f"- {candidate.get('archive_relative_path') or '-'} ({state_label})")
    external_candidates = result.get("external_candidates") if isinstance(result.get("external_candidates"), list) else []
    if external_candidates:
        print("External candidates:")
        for candidate in external_candidates:
            if not isinstance(candidate, dict):
                continue
            store_kind = candidate.get("store_kind") or "-"
            store_ref = candidate.get("store_ref") or "-"
            availability = candidate.get("availability") or "-"
            print(f"- {candidate.get('provider') or '-'} {store_kind} {store_ref} ({availability})")
    print("Writes: none")
    if result.get("blockers"):
        print("Blockers:")
        for blocker in result["blockers"]:
            print(f"- {blocker}")
    if result.get("warnings"):
        print("Warnings:")
        for warning in result["warnings"]:
            print(f"- {warning}")
    if result.get("next_safe_actions"):
        print("Next safe actions:")
        for action in result["next_safe_actions"]:
            print(f"- {action}")


def print_presigned_url_plan_result(result: dict[str, Any], output_format: str) -> None:
    if output_format == "json":
        print_json(result)
        return
    state = result.get("plan_state") or ("passed" if result.get("ok") else "blocked")
    request = result.get("presigned_url_request") if isinstance(result.get("presigned_url_request"), dict) else {}
    summary = result.get("resolution_summary") if isinstance(result.get("resolution_summary"), dict) else {}
    print(f"Presigned URL plan {state}.")
    print(f"Archive: {result.get('archive_id') or '-'}")
    print(f"Object id: {result.get('object_id') or '-'}")
    print(f"Operation: {request.get('operation') or '-'}")
    print(f"TTL seconds: {request.get('ttl_seconds') or '-'}")
    print(f"Store ref: {request.get('store_ref') or '-'}")
    print(f"Resolution: {summary.get('resolution_state') or '-'}")
    print(f"External candidates: {summary.get('external_candidate_count', 0)}")
    print("Presigned URL created: no")
    print("Provider API called: no")
    print("Writes: none")
    if result.get("blockers"):
        print("Blockers:")
        for blocker in result["blockers"]:
            print(f"- {blocker}")
    if result.get("warnings"):
        print("Warnings:")
        for warning in result["warnings"]:
            print(f"- {warning}")
    if result.get("next_safe_actions"):
        print("Next safe actions:")
        for action in result["next_safe_actions"]:
            print(f"- {action}")


def print_object_storage_operation_request_plan_result(result: dict[str, Any], output_format: str) -> None:
    if output_format == "json":
        print_json(result)
        return
    policy = result.get("credential_policy_summary") if isinstance(result.get("credential_policy_summary"), dict) else {}
    target = result.get("target_summary") if isinstance(result.get("target_summary"), dict) else {}
    print(f"Object storage operation request plan: {result.get('request_state') or '-'}")
    print(f"Archive: {result.get('archive_id') or '-'}")
    print(f"Operation: {result.get('operation') or '-'}")
    print(f"Object id: {result.get('object_id') or '-'}")
    print(f"Target: {target.get('target_kind') or '-'}")
    print(f"Credential policy: {policy.get('policy_result') or '-'}")
    print(f"Approval receipt verified: {policy.get('approval_receipt_verified')}")
    print("Live execution allowed now: no")
    print("Provider API called: no")
    print("Writes: none")
    if result.get("blockers"):
        print("Blockers:")
        for blocker in result["blockers"]:
            print(f"- {blocker}")
    if result.get("warnings"):
        print("Warnings:")
        for warning in result["warnings"]:
            print(f"- {warning}")
    if result.get("next_safe_actions"):
        print("Next safe actions:")
        for action in result["next_safe_actions"]:
            print(f"- {action}")


def print_object_storage_adapter_execution_contract_result(result: dict[str, Any], output_format: str) -> None:
    if output_format == "json":
        print_json(result)
        return
    gates = result.get("prerequisite_gate_summary") if isinstance(result.get("prerequisite_gate_summary"), dict) else {}
    key_contract = result.get("key_contract") if isinstance(result.get("key_contract"), dict) else {}
    integrity = result.get("integrity_contract") if isinstance(result.get("integrity_contract"), dict) else {}
    transfer = result.get("transfer_contract") if isinstance(result.get("transfer_contract"), dict) else {}
    print(f"Object storage adapter execution contract: {result.get('contract_state') or '-'}")
    print(f"Archive: {result.get('archive_id') or '-'}")
    print(f"Operation: {result.get('operation') or '-'}")
    print(f"Object id: {result.get('object_id') or '-'}")
    print(f"Store ref: {result.get('store_ref') or '-'}")
    print(f"Readiness: {gates.get('readiness_state') or '-'}")
    print(f"Key strategy: {key_contract.get('strategy') or '-'}")
    print(f"SHA-256 required: {integrity.get('sha256_required')}")
    print(f"Resume ledger required: {transfer.get('resume_ledger_required')}")
    print("Live execution allowed now: no")
    print("Provider API called: no")
    print("Writes: none")
    if result.get("blockers"):
        print("Blockers:")
        for blocker in result["blockers"]:
            print(f"- {blocker}")
    if result.get("warnings"):
        print("Warnings:")
        for warning in result["warnings"]:
            print(f"- {warning}")
    if result.get("next_safe_actions"):
        print("Next safe actions:")
        for action in result["next_safe_actions"]:
            print(f"- {action}")


def print_imap_mailbox_operation_request_plan_result(result: dict[str, Any], output_format: str) -> None:
    if output_format == "json":
        print_json(result)
        return
    policy = result.get("credential_policy_summary") if isinstance(result.get("credential_policy_summary"), dict) else {}
    scope = result.get("operation_scope") if isinstance(result.get("operation_scope"), dict) else {}
    print(f"IMAP mailbox operation request plan: {result.get('request_state') or '-'}")
    print(f"Archive: {result.get('archive_id') or '-'}")
    print(f"Source: {result.get('source_id') or '-'}")
    print(f"Provider: {result.get('provider') or '-'}")
    print(f"Operation: {result.get('operation') or '-'}")
    print(f"Max messages: {scope.get('max_messages') or '-'}")
    print(f"Credential policy: {policy.get('policy_result') or '-'}")
    print(f"Approval receipt verified: {policy.get('approval_receipt_verified')}")
    print("Live execution allowed now: no")
    print("IMAP connection opened: no")
    print("Writes: none")
    if result.get("blockers"):
        print("Blockers:")
        for blocker in result["blockers"]:
            print(f"- {blocker}")
    if result.get("warnings"):
        print("Warnings:")
        for warning in result["warnings"]:
            print(f"- {warning}")
    if result.get("next_safe_actions"):
        print("Next safe actions:")
        for action in result["next_safe_actions"]:
            print(f"- {action}")


def command_source_intake(args: argparse.Namespace) -> int:
    if not args.dry_run:
        print("Source intake is dry-run only in v0.2.22. Use --dry-run.", file=sys.stderr)
        return 1
    try:
        result = archive_services.source_intake_plan(
            Path(args.archive_root),
            local_path=args.local_path,
            source_id=args.source,
            item_id=args.item_id,
            relative_path=args.relative_path,
            objet_ref=args.objet_ref,
            object_id=args.object_id,
            provider=args.provider,
            provider_object_id=args.provider_object_id,
            provider_kind=args.provider_kind,
            ai_artifact_ref=args.ai_artifact_ref,
            runtime=args.runtime,
            artifact_kind=args.artifact_kind,
            expected_archive_id=args.expected_archive_id,
            expected_type=args.expected_type,
            profile_id=args.profile_id,
            source_role=args.source_role,
            title=args.title,
            mime=args.mime,
            redact_local_paths=args.redact_local_paths,
            project_intake_receipt=args.project_intake_receipt,
        )
    except (archive_services.ArchiveServiceError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        state = "passed" if result.get("ok") else "blocked"
        print(f"Source intake dry-run {state}.")
        print(f"Archive: {result.get('archive_id') or '-'}")
        print(f"Input kind: {result.get('input_kind') or '-'}")
        print(f"Objet status: {result.get('objet_status') or '-'}")
        if result.get("source_refs_for_draft"):
            print("Source refs for draft:")
            for ref in result["source_refs_for_draft"]:
                print(f"- {ref.get('type')}:{ref.get('value')}")
        if result.get("blockers"):
            print("Blockers:")
            for blocker in result["blockers"]:
                print(f"- {blocker}")
        if result.get("warnings"):
            print("Warnings:")
            for warning in result["warnings"]:
                print(f"- {warning}")
    return 0 if result.get("ok", True) else 1


def command_tiro_import_plan(args: argparse.Namespace) -> int:
    if not args.dry_run:
        print("Tiro import planning is dry-run only. Use --dry-run.", file=sys.stderr)
        return 1
    try:
        result = archive_services.tiro_import_plan(
            Path(args.archive_root),
            manifest_path=args.manifest,
            source=args.source,
            max_segments=args.max_segments,
        )
    except (archive_services.ArchiveServiceError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        state = result.get("state") or ("ready" if result.get("ok") else "blocked")
        print(f"Tiro import plan {state}.")
        print(f"Archive: {result.get('archive_id') or '-'}")
        print(f"Manifest: {result.get('manifest_path') or '-'}")
        transcript = result.get("transcript_mapping") if isinstance(result.get("transcript_mapping"), dict) else {}
        segments = transcript.get("segments_preserved") if isinstance(transcript.get("segments_preserved"), dict) else {}
        print(f"Transcript segments: {segments.get('segment_count', 0)}")
        print(f"Speakers: {segments.get('speaker_count_in_segments', 0)}")
        audio = result.get("audio_source_ref") if isinstance(result.get("audio_source_ref"), dict) else {}
        print(f"Audio objet visible: {bool(audio.get('manifest_record_found'))}")
        if result.get("blockers"):
            print("Blockers:")
            for blocker in result["blockers"]:
                print(f"- {blocker}")
        if result.get("warnings"):
            print("Warnings:")
            for warning in result["warnings"]:
                print(f"- {warning}")
    return 0 if result.get("ok", True) else 1


def command_tiro_lossless_recovery_plan(args: argparse.Namespace) -> int:
    if not args.dry_run:
        print("tiro-lossless-recovery-plan is read-only and requires --dry-run.", file=sys.stderr)
        return 1
    try:
        result = archive_services.tiro_lossless_recovery_plan(
            Path(args.archive_root),
            credential_ref=args.credential_ref,
            workspace_guid=args.workspace_guid,
            note_guid=args.note_guid,
            max_notes=args.max_notes,
            dry_run=True,
        )
    except (archive_services.ArchiveServiceError, OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        print(f"Tiro lossless recovery plan {result.get('plan_state') or '-'}.")
        print(f"Archive: {result.get('archive_id') or '-'}")
        print(f"Endpoint categories: {len(result.get('endpoint_inventory') or [])}")
        credential = result.get("credential_summary") if isinstance(result.get("credential_summary"), dict) else {}
        print(f"Credential ref supplied: {bool(credential.get('credential_ref_supplied'))}")
        if result.get("blockers"):
            print("Blockers:")
            for blocker in result["blockers"]:
                print(f"- {blocker}")
        if result.get("warnings"):
            print("Warnings:")
            for warning in result["warnings"]:
                print(f"- {warning}")
    return 0 if result.get("ok", True) else 1


def command_tiro_lossless_recovery_capture(args: argparse.Namespace) -> int:
    try:
        result = archive_services.tiro_lossless_recovery_capture(
            Path(args.archive_root),
            bundle_path=args.bundle,
            dry_run=args.dry_run,
            approve=args.approve,
            reviewed_by=args.reviewed_by,
        )
    except (archive_services.ArchiveServiceError, OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        print(f"Tiro lossless recovery capture {result.get('capture_state') or '-'}.")
        print(f"Archive: {result.get('archive_id') or '-'}")
        obj = result.get("object") if isinstance(result.get("object"), dict) else {}
        print(f"Object: {obj.get('object_id') or '-'}")
        receipt = result.get("receipt") if isinstance(result.get("receipt"), dict) else {}
        print(f"Receipt: {receipt.get('receipt_path') or receipt.get('proposed_receipt_path') or '-'}")
        if result.get("files_written"):
            print("Files written:")
            for path in result["files_written"]:
                print(f"- {path}")
        elif result.get("would_change"):
            print("Would change:")
            for path in result["would_change"]:
                print(f"- {path}")
        if result.get("blockers"):
            print("Blockers:")
            for blocker in result["blockers"]:
                print(f"- {blocker}")
        if result.get("warnings"):
            print("Warnings:")
            for warning in result["warnings"]:
                print(f"- {warning}")
    return 0 if result.get("ok", True) else 1


def command_tiro_lossless_recovery_fetch_run(args: argparse.Namespace) -> int:
    try:
        result = archive_services.tiro_lossless_recovery_fetch_run(
            Path(args.archive_root),
            credential_ref=args.credential_ref,
            workspace_guid=args.workspace_guid,
            note_guid=args.note_guid,
            output_path=args.output,
            max_notes=args.max_notes,
            timeout_seconds=args.timeout_seconds,
            dry_run=args.dry_run,
            approve=args.approve,
            reviewed_by=args.reviewed_by,
        )
    except (archive_services.ArchiveServiceError, OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        print(f"Tiro lossless recovery fetch {result.get('fetch_state') or '-'}.")
        print(f"Archive: {result.get('archive_id') or '-'}")
        bundle = result.get("bundle") if isinstance(result.get("bundle"), dict) else {}
        print(f"Bundle: {bundle.get('output_path') or bundle.get('proposed_output_path') or '-'}")
        receipt = result.get("receipt") if isinstance(result.get("receipt"), dict) else {}
        print(f"Receipt: {receipt.get('receipt_path') or receipt.get('proposed_receipt_path') or '-'}")
        if result.get("files_written"):
            print("Files written:")
            for path in result["files_written"]:
                print(f"- {path}")
        elif result.get("would_change"):
            print("Would change:")
            for path in result["would_change"]:
                print(f"- {path}")
        if result.get("blockers"):
            print("Blockers:")
            for blocker in result["blockers"]:
                print(f"- {blocker}")
        if result.get("warnings"):
            print("Warnings:")
            for warning in result["warnings"]:
                print(f"- {warning}")
    return 0 if result.get("ok", True) else 1


def command_zet_markdown_style_guide(args: argparse.Namespace) -> int:
    if not args.dry_run:
        print("zet-markdown-style-guide is read-only and requires --dry-run.", file=sys.stderr)
        return 1
    try:
        result = archive_services.zet_markdown_style_guide(
            Path(args.archive_root),
            topic=args.topic,
            dry_run=True,
        )
    except (archive_services.ArchiveServiceError, OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        print("zet Markdown style guide passed." if result.get("ok") else "zet Markdown style guide blocked.")
        print(f"Archive: {result.get('archive_id') or '-'}")
        for section in result.get("sections", []):
            if not isinstance(section, dict):
                continue
            print(f"\n{section.get('title') or section.get('section_id') or 'Section'}")
            if section.get("beginner_explanation"):
                print(str(section["beginner_explanation"]))
            rule = section.get("range_tilde_rule") if isinstance(section.get("range_tilde_rule"), dict) else {}
            if rule:
                print(f"Rule: {rule.get('required_form') or '-'}")
        if result.get("blockers"):
            print("Blockers:")
            for blocker in result["blockers"]:
                print(f"- {blocker}")
        if result.get("warnings"):
            print("Warnings:")
            for warning in result["warnings"]:
                print(f"- {warning}")
    return 0 if result.get("ok", True) else 1


def command_source_intake_record(args: argparse.Namespace) -> int:
    try:
        result = archive_services.source_intake_record(
            Path(args.archive_root),
            Path(args.source_intake_plan),
            dry_run=args.dry_run,
            approve=args.approve,
            reviewed_by=args.reviewed_by,
        )
    except (archive_services.ArchiveServiceError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print_source_intake_record_result(result, args.format)
    return 0 if result.get("ok", True) else 1


def print_source_intake_record_result(result: dict[str, Any], output_format: str) -> None:
    if output_format == "json":
        print_json(result)
        return
    mode = "dry-run ready" if result.get("dry_run") else "recorded"
    if not result.get("ok", True):
        mode = "blocked"
    print(f"Source intake record {mode}.")
    print(f"Archive: {result.get('archive_id') or '-'}")
    print(f"Plan SHA-256: {result.get('source_intake_plan_sha256') or '-'}")
    if result.get("plan_path"):
        print(f"Plan path: {result['plan_path']}")
    else:
        print(f"Proposed plan path: {result.get('proposed_plan_path') or '-'}")
    writes = result.get("files_written") or []
    if writes:
        print("Files written:")
        for path in writes:
            print(f"- {path}")
    else:
        print("Writes: none")
    if result.get("blockers"):
        print("Blockers:")
        for blocker in result["blockers"]:
            print(f"- {blocker}")
    if result.get("warnings"):
        print("Warnings:")
        for warning in result["warnings"]:
            print(f"- {warning}")


def command_list_zettels(args: argparse.Namespace) -> int:
    try:
        result = archive_services.list_zettels(Path(args.archive_root), status=args.status, limit=args.limit)
    except archive_services.ArchiveServiceError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        print(f"Found {result['count']} zettel(s).")
        for zettel in result["zettels"]:
            print(
                "\t".join(
                    [
                        str(zettel.get("status") or "-"),
                        str(zettel.get("id") or "-"),
                        str(zettel.get("title") or "(untitled)"),
                        str(zettel.get("path") or "-"),
                    ]
                )
            )
    return 0


def command_status_board(args: argparse.Namespace) -> int:
    if not args.dry_run:
        print("status-board is read-only and requires --dry-run.", file=sys.stderr)
        return 1
    try:
        result = archive_services.archive_status_board(
            Path(args.archive_root),
            dry_run=True,
            max_items=args.max_items,
            include_quality=args.include_quality,
        )
    except archive_services.ArchiveServiceError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        counts = result.get("counts") if isinstance(result.get("counts"), dict) else {}
        print("Archive status board.")
        print(f"Archive: {result.get('archive_id') or '-'}")
        print(f"Canonical zets: {counts.get('canonical', 0)}")
        print(f"Draft zets: {counts.get('draft', 0)}")
        print(f"Minted drafts pending retire: {counts.get('minted_draft_pending_retire', 0)}")
        print(f"Document type missing: {counts.get('document_type_missing', 0)}")
        print(f"Audience missing: {counts.get('audience_missing', 0)}")
        print(f"Source metadata gaps: {counts.get('source_metadata_gap', 0)}")
        print(f"Derived artifact gaps: {counts.get('derived_artifact_gap', 0)}")
        if args.include_quality:
            print(f"Quality blocker candidates: {counts.get('quality_blocker_candidate', 0)}")
            print(f"Quality warning candidates: {counts.get('quality_warning_candidate', 0)}")
        if result.get("next_actions"):
            print("Next actions:")
            for action in result["next_actions"]:
                print(f"- {action}")
    return 0 if result.get("ok", True) else 1


def command_derived_artifact_staleness(args: argparse.Namespace) -> int:
    if not args.dry_run:
        print("derived-artifact-staleness is read-only and requires --dry-run.", file=sys.stderr)
        return 1
    try:
        result = archive_services.derived_artifact_staleness_check(
            Path(args.archive_root),
            dry_run=True,
            max_items=args.max_items,
        )
    except archive_services.ArchiveServiceError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        counts = result.get("counts") if isinstance(result.get("counts"), dict) else {}
        print("Derived artifact staleness check.")
        print(f"Archive: {result.get('archive_id') or '-'}")
        print(f"Derived artifacts: {counts.get('artifact_count', 0)}")
        print(f"Current: {counts.get('current_artifact', 0)}")
        print(f"Stale: {counts.get('stale_artifact', 0)}")
        print(f"Unknown sync time: {counts.get('unknown_sync_time', 0)}")
        print(f"Missing source zettels: {counts.get('missing_source_zettels', 0)}")
        print(f"Unresolved source zettels: {counts.get('unresolved_source_zettels', 0)}")
        if result.get("next_actions"):
            print("Next actions:")
            for action in result["next_actions"]:
                print(f"- {action}")
    return 0 if result.get("ok", True) else 1


def command_read_zettel(args: argparse.Namespace) -> int:
    try:
        result = archive_services.read_zettel(
            Path(args.archive_root),
            zettel_id=args.zettel_id,
            relative_path=args.path,
            section=args.section,
        )
    except archive_services.ArchiveServiceError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        frontmatter = result["frontmatter"]
        print(f"Path: {result['path']}")
        if isinstance(frontmatter, dict):
            print(f"ID: {frontmatter.get('id', '-')}")
            print(f"Title: {frontmatter.get('title', '-')}")
            print(f"Status: {frontmatter.get('status', '-')}")
        overview = result.get("overview") if isinstance(result.get("overview"), dict) else {}
        if overview:
            print(f"Section: {result.get('section', 'body')}")
            print(f"Kind: {overview.get('kind') or '-'}")
            print(f"Gist: {overview.get('gist') or '-'}")
            tie_summary = overview.get("tie_summary") if isinstance(overview.get("tie_summary"), dict) else {}
            if tie_summary:
                print(
                    "Ties: "
                    f"{tie_summary.get('edge_count', 0)} edge(s), "
                    f"{tie_summary.get('referenced_zets_count', 0)} zet ref(s), "
                    f"{tie_summary.get('referenced_objets_count', 0)} objet ref(s)"
                )
        print()
        if result.get("body_omitted"):
            print("(body omitted)")
        else:
            print(result["body"].rstrip())
    return 0


def command_zettel_objet_links(args: argparse.Namespace) -> int:
    if not args.dry_run:
        print("zettel-objet-links is read-only and requires --dry-run.", file=sys.stderr)
        return 1
    try:
        result = archive_services.zettel_objet_links(
            Path(args.archive_root),
            zettel_id=args.zettel_id,
            relative_path=args.path,
            dry_run=True,
            max_refs=args.max_refs,
        )
    except (archive_services.ArchiveServiceError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        zettel = result.get("zettel") if isinstance(result.get("zettel"), dict) else {}
        print(f"Zettel objet links: {result.get('count', 0)}")
        print(f"Zettel: {zettel.get('id') or zettel.get('path') or '-'}")
        for link in result.get("links", []):
            if not isinstance(link, dict):
                continue
            print(f"- {link.get('object_id')}: {link.get('resolution_state')}")
            for candidate in link.get("link_candidates", []):
                if not isinstance(candidate, dict):
                    continue
                if candidate.get("kind") == "archive_relative_path":
                    state = "exists" if candidate.get("exists") else "missing"
                    print(f"  local: {candidate.get('archive_relative_path') or '-'} ({state})")
                elif candidate.get("kind") == "external_store_label":
                    print(
                        "  external: "
                        f"{candidate.get('provider') or '-'} "
                        f"{candidate.get('store_kind') or '-'} "
                        f"{candidate.get('store_ref') or '-'}"
                    )
        if result.get("blockers"):
            print("Blockers:")
            for blocker in result["blockers"]:
                print(f"- {blocker}")
        if result.get("warnings"):
            print("Warnings:")
            for warning in result["warnings"]:
                print(f"- {warning}")
        if result.get("next_safe_actions"):
            print("Next safe actions:")
            for action in result["next_safe_actions"]:
                print(f"- {action}")
        print("Writes: none")
    return 0 if result.get("ok", True) else 1


def command_notion_objet_link_plan(args: argparse.Namespace) -> int:
    if not args.dry_run:
        print("notion-objet-link-plan is read-only and requires --dry-run.", file=sys.stderr)
        return 1
    try:
        result = archive_services.notion_objet_link_plan(
            Path(args.archive_root),
            zettel_id=args.zettel_id,
            relative_path=args.path,
            dry_run=True,
            max_locators=args.max_locators,
            max_candidates=args.max_candidates,
        )
    except (archive_services.ArchiveServiceError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        zettel = result.get("zettel") if isinstance(result.get("zettel"), dict) else {}
        print(f"Notion objet link plan: {result.get('locator_count', 0)} locator(s)")
        print(f"Zettel: {zettel.get('id') or zettel.get('path') or '-'}")
        manifest_summary = result.get("manifest_summary") if isinstance(result.get("manifest_summary"), dict) else {}
        print(f"Manifest records: {manifest_summary.get('record_count', 0)}")
        print(f"Notion-labeled records: {manifest_summary.get('notion_labeled_record_count', 0)}")
        for locator in result.get("locators", []):
            if not isinstance(locator, dict):
                continue
            print(
                f"- {locator.get('locator_fingerprint')}: "
                f"{locator.get('candidate_state')} "
                f"({locator.get('candidate_count', 0)} candidate(s))"
            )
            for candidate in locator.get("candidates", []):
                if not isinstance(candidate, dict):
                    continue
                print(f"  object: {candidate.get('object_id') or '-'} ({candidate.get('resolution_state') or '-'})")
        if result.get("blockers"):
            print("Blockers:")
            for blocker in result["blockers"]:
                print(f"- {blocker}")
        if result.get("warnings"):
            print("Warnings:")
            for warning in result["warnings"]:
                print(f"- {warning}")
        if result.get("next_safe_actions"):
            print("Next safe actions:")
            for action in result["next_safe_actions"]:
                print(f"- {action}")
        print("Writes: none")
    return 0 if result.get("ok", True) else 1


def command_notion_objet_link_index(args: argparse.Namespace) -> int:
    if not args.dry_run:
        print("notion-objet-link-index is read-only and requires --dry-run.", file=sys.stderr)
        return 1
    try:
        result = archive_services.notion_objet_link_index(
            Path(args.archive_root),
            dry_run=True,
            max_zettels=args.max_zettels,
            max_locators_per_zettel=args.max_locators_per_zettel,
            max_candidates=args.max_candidates,
        )
    except (archive_services.ArchiveServiceError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
        manifest_summary = result.get("manifest_summary") if isinstance(result.get("manifest_summary"), dict) else {}
        print("Notion objet link index:")
        print(f"- zettels scanned: {summary.get('scanned_non_redacted_zettel_count', 0)}")
        print(f"- zettels with locators: {summary.get('zettels_with_locator_count', 0)}")
        print(f"- distinct locators: {summary.get('distinct_locator_count', 0)}")
        print(f"- matched locator rows: {summary.get('zettel_locator_rows_with_manifest_candidate_count', 0)}")
        print(f"- unmatched locator rows: {summary.get('zettel_locator_rows_without_manifest_candidate_count', 0)}")
        print(f"- manifest records: {manifest_summary.get('record_count', 0)}")
        print(f"- Notion-labeled records: {manifest_summary.get('notion_labeled_record_count', 0)}")
        for zettel in result.get("zettels", []):
            if not isinstance(zettel, dict):
                continue
            print(
                f"* {zettel.get('id') or zettel.get('path') or '-'}: "
                f"{zettel.get('locator_count', 0)} locator(s), "
                f"{zettel.get('matched_locator_count', 0)} matched"
            )
        if result.get("blockers"):
            print("Blockers:")
            for blocker in result["blockers"]:
                print(f"- {blocker}")
        if result.get("warnings"):
            print("Warnings:")
            for warning in result["warnings"]:
                print(f"- {warning}")
        if result.get("next_safe_actions"):
            print("Next safe actions:")
            for action in result["next_safe_actions"]:
                print(f"- {action}")
        print("Writes: none")
    return 0 if result.get("ok", True) else 1


def command_notion_objet_source_map_link_plan(args: argparse.Namespace) -> int:
    if not args.dry_run:
        print("notion-objet-source-map-link-plan is read-only and requires --dry-run.", file=sys.stderr)
        return 1
    try:
        result = archive_services.notion_objet_source_map_link_plan(
            Path(args.archive_root),
            source_maps=args.source_map,
            ledgers=args.ledger,
            dry_run=True,
            max_rows=args.max_rows,
            max_candidates=args.max_candidates,
        )
    except (archive_services.ArchiveServiceError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
        print("Notion objet source-map link plan:")
        print(f"- source-map records: {summary.get('source_map_record_count', 0)}")
        print(f"- ledger records: {summary.get('ledger_record_count', 0)}")
        print(f"- zettel sources: {summary.get('zettel_source_count', 0)}")
        print(f"- object ref sources: {summary.get('object_ref_source_count', 0)}")
        print(f"- candidates: {summary.get('candidate_count', 0)}")
        for candidate in result.get("candidates", []):
            if not isinstance(candidate, dict):
                continue
            zettel = candidate.get("from_zettel") if isinstance(candidate.get("from_zettel"), dict) else {}
            print(
                f"* {candidate.get('candidate_id')}: "
                f"{zettel.get('id') or zettel.get('path') or '-'} -> "
                f"{candidate.get('target_object_id') or '-'} "
                f"({candidate.get('confidence') or '-'}, {candidate.get('write_status') or '-'})"
            )
        if result.get("blockers"):
            print("Blockers:")
            for blocker in result["blockers"]:
                print(f"- {blocker}")
        if result.get("warnings"):
            print("Warnings:")
            for warning in result["warnings"]:
                print(f"- {warning}")
        if result.get("next_safe_actions"):
            print("Next safe actions:")
            for action in result["next_safe_actions"]:
                print(f"- {action}")
        print("Writes: none")
    return 0 if result.get("ok", True) else 1


def command_notion_objet_import_clue_audit(args: argparse.Namespace) -> int:
    if not args.dry_run:
        print("notion-objet-import-clue-audit is read-only and requires --dry-run.", file=sys.stderr)
        return 1
    try:
        result = archive_services.notion_objet_import_clue_audit(
            Path(args.archive_root),
            source_maps=args.source_map,
            ledgers=args.ledger,
            dry_run=True,
            max_rows=args.max_rows,
            max_zettels=args.max_zettels,
            max_candidates=args.max_candidates,
        )
    except (archive_services.ArchiveServiceError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
        print("Notion objet import clue audit:")
        print(f"- Notion import zettels: {summary.get('notion_import_zettel_count', 0)}")
        print(f"- preserved object refs/edges: {summary.get('preserved_object_ref_or_edge_count', 0)}")
        print(f"- source-map join available: {summary.get('source_map_join_available_count', 0)}")
        print(f"- missing after locator omission: {summary.get('missing_material_clue_after_locator_omission_count', 0)}")
        for item in result.get("zettels", []):
            if not isinstance(item, dict):
                continue
            zettel = item.get("zettel") if isinstance(item.get("zettel"), dict) else {}
            print(
                f"* {zettel.get('id') or zettel.get('path') or '-'}: "
                f"{item.get('material_clue_state') or '-'}"
            )
        if result.get("blockers"):
            print("Blockers:")
            for blocker in result["blockers"]:
                print(f"- {blocker}")
        if result.get("warnings"):
            print("Warnings:")
            for warning in result["warnings"]:
                print(f"- {warning}")
        if result.get("next_safe_actions"):
            print("Next safe actions:")
            for action in result["next_safe_actions"]:
                print(f"- {action}")
        print("Writes: none")
    return 0 if result.get("ok", True) else 1


def command_notion_objet_link_rewrite_plan(args: argparse.Namespace) -> int:
    if not args.dry_run:
        print("notion-objet-link-rewrite-plan is read-only and requires --dry-run.", file=sys.stderr)
        return 1
    try:
        result = archive_services.notion_objet_link_rewrite_plan(
            Path(args.archive_root),
            zettel_id=args.zettel_id,
            relative_path=args.path,
            locator_fingerprint=args.locator_fingerprint,
            object_id=args.object_id,
            target_mode=args.target_mode,
            expected_occurrence_count=args.expected_occurrence_count,
            dry_run=True,
        )
    except (archive_services.ArchiveServiceError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        zettel = result.get("zettel") if isinstance(result.get("zettel"), dict) else {}
        locator = result.get("selected_locator") if isinstance(result.get("selected_locator"), dict) else {}
        candidate = result.get("selected_candidate") if isinstance(result.get("selected_candidate"), dict) else {}
        print("Notion objet link rewrite plan:")
        print(f"- target mode: {result.get('target_mode') or '-'}")
        print(f"- zettel: {zettel.get('id') or zettel.get('path') or '-'}")
        print(f"- locator: {result.get('locator_fingerprint') or '-'}")
        print(f"- occurrence count: {locator.get('occurrence_count', 0)}")
        print(f"- object: {result.get('selected_object_id') or '-'} ({candidate.get('resolution_state') or '-'})")
        for change in result.get("would_change", []):
            if not isinstance(change, dict):
                continue
            print(f"* would {change.get('change_kind')}: {change.get('target_objet_ref') or change.get('replacement_objet_ref') or '-'}")
        if result.get("blockers"):
            print("Blockers:")
            for blocker in result["blockers"]:
                print(f"- {blocker}")
        if result.get("warnings"):
            print("Warnings:")
            for warning in result["warnings"]:
                print(f"- {warning}")
        if result.get("next_safe_actions"):
            print("Next safe actions:")
            for action in result["next_safe_actions"]:
                print(f"- {action}")
        print("Writes: none")
    return 0 if result.get("ok", True) else 1


def command_notion_objet_link_convert(args: argparse.Namespace) -> int:
    try:
        result = archive_services.notion_objet_link_convert(
            Path(args.archive_root),
            zettel_id=args.zettel_id,
            relative_path=args.path,
            locator_fingerprint=args.locator_fingerprint,
            object_id=args.object_id,
            target_mode=args.target_mode,
            expected_occurrence_count=args.expected_occurrence_count,
            visibility=args.visibility,
            dry_run=args.dry_run,
            approve=args.approve,
            reviewed_by=args.reviewed_by,
        )
    except (archive_services.ArchiveServiceError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        zettel = result.get("zettel") if isinstance(result.get("zettel"), dict) else {}
        edge_write = result.get("edge_write") if isinstance(result.get("edge_write"), dict) else {}
        receipt = result.get("receipt") if isinstance(result.get("receipt"), dict) else {}
        print(f"Notion objet link convert: {result.get('write_status') or '-'}")
        print(f"- target mode: {result.get('target_mode') or '-'}")
        print(f"- zettel: {zettel.get('id') or zettel.get('path') or '-'}")
        print(f"- locator: {result.get('locator_fingerprint') or '-'}")
        print(f"- object: {result.get('selected_object_id') or '-'}")
        print(f"- edge: {edge_write.get('edge_id') or '-'}")
        print(f"- edge receipt: {edge_write.get('receipt_path') or '-'}")
        print(f"- conversion receipt: {receipt.get('receipt_path') or '-'}")
        if result.get("files_written"):
            print("Files written:")
            for path in result["files_written"]:
                print(f"- {path}")
        elif result.get("would_change"):
            print("Would change:")
            for path in result["would_change"]:
                print(f"- {path}")
        if result.get("blockers"):
            print("Blockers:")
            for blocker in result["blockers"]:
                print(f"- {blocker}")
        if result.get("warnings"):
            print("Warnings:")
            for warning in result["warnings"]:
                print(f"- {warning}")
        if result.get("next_safe_actions"):
            print("Next safe actions:")
            for action in result["next_safe_actions"]:
                print(f"- {action}")
    return 0 if result.get("ok", True) else 1


def command_notion_objet_manifest_locator_label(args: argparse.Namespace) -> int:
    try:
        result = archive_services.notion_objet_manifest_locator_label(
            Path(args.archive_root),
            object_id=args.object_id,
            locator_fingerprint=args.locator_fingerprint,
            dry_run=args.dry_run,
            approve=args.approve,
            reviewed_by=args.reviewed_by,
        )
    except (archive_services.ArchiveServiceError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        update = result.get("manifest_update") if isinstance(result.get("manifest_update"), dict) else {}
        receipt = result.get("receipt") if isinstance(result.get("receipt"), dict) else {}
        print(f"Notion objet manifest locator label: {result.get('write_status') or '-'}")
        print(f"Archive: {result.get('archive_id') or '-'}")
        print(f"Object: {result.get('object_id') or '-'}")
        print(f"Locator fingerprint: {result.get('locator_fingerprint') or '-'}")
        print(f"Label field: {update.get('label_field') or '-'}")
        print(f"Already labeled: {update.get('already_labeled')}")
        print(f"Receipt: {receipt.get('receipt_path') or '-'}")
        if result.get("files_written"):
            print("Files written:")
            for path in result["files_written"]:
                print(f"- {path}")
        elif result.get("would_change"):
            print("Would change:")
            for path in result["would_change"]:
                print(f"- {path}")
        if result.get("blockers"):
            print("Blockers:")
            for blocker in result["blockers"]:
                print(f"- {blocker}")
        if result.get("warnings"):
            print("Warnings:")
            for warning in result["warnings"]:
                print(f"- {warning}")
        if result.get("next_safe_actions"):
            print("Next safe actions:")
            for action in result["next_safe_actions"]:
                print(f"- {action}")
    return 0 if result.get("ok", True) else 1


def command_create_draft(args: argparse.Namespace) -> int:
    try:
        body = read_body_arg(args)
        created_by = args.created_by or "cli:archive"
        source = args.source or "cli_command"
        result = archive_services.create_draft_zettel(
            Path(args.archive_root),
            title=args.title,
            body=body,
            archive_id=args.archive_id,
            kind=args.kind,
            facets=parse_key_value_pairs(args.facet or []),
            created_by=created_by,
            source=source,
            dry_run=args.dry_run,
            expected_archive_id=args.expected_archive_id,
            expected_type=args.expected_type,
            profile_id=args.profile_id,
            profile_operator_id=args.profile_operator_id,
            profile_authority_mode=args.profile_authority_mode,
            creation_mode=args.creation_mode,
            assisted_by=args.assisted_by,
            supervised_by=args.supervised_by,
            derived_from=args.derived_from,
            source_refs=parse_source_ref_pairs(args.source_ref or []),
            source_intake_plan=load_source_intake_plan_file(args.source_intake_plan),
            prompt_boundary_report=load_prompt_boundary_report_file(args.prompt_boundary_report),
            local_ai_sessions=build_local_ai_session_refs(args),
            draft_id=args.draft_id,
            created_at=args.created_at,
            expected_body_sha256=args.expected_body_sha256,
            draft_approved_by=args.draft_approved_by,
        )
    except (archive_services.ArchiveServiceError, ValueError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        if result.get("dry_run"):
            print(f"Draft dry-run for {result['frontmatter_preview']['id']}")
            print(f"Proposed path: {result['proposed_path']}")
            if result["blockers"]:
                print("Blockers:")
                for blocker in result["blockers"]:
                    print(f"- {blocker}")
            if result["warnings"]:
                print("Warnings:")
                for warning in result["warnings"]:
                    print(f"- {warning}")
            print("Draft dry-run passed." if result["ok"] else "Draft dry-run blocked.")
        else:
            print(f"Created draft zettel {result['zettel_id']} at {result['path']}")
    return 0 if result.get("ok", True) else 1


def command_block_header(args: argparse.Namespace) -> int:
    try:
        result = archive_services.block_header_preview(
            Path(args.archive_root),
            zettel_id=args.zettel_id,
            relative_path=args.path,
            dry_run=args.dry_run,
        )
    except archive_services.ArchiveServiceError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        print(f"Block header dry-run for {result.get('zettel_id') or result.get('source_path') or '-'}")
        if result.get("source_path"):
            print(f"Source path: {result['source_path']}")
        if result.get("header_sha256"):
            print(f"Header SHA-256: {result['header_sha256']}")
        if result.get("block_hash_preview"):
            print(f"Block hash preview: {result['block_hash_preview']}")
        if result.get("blockers"):
            print("Blockers:")
            for blocker in result["blockers"]:
                print(f"- {blocker}")
        if result.get("warnings"):
            print("Warnings:")
            for warning in result["warnings"]:
                print(f"- {warning}")
        print("Block header dry-run passed." if result["ok"] else "Block header dry-run blocked.")
    return 0 if result.get("ok") else 1


def command_projection_plan(args: argparse.Namespace) -> int:
    if not args.dry_run:
        print("Projection plan is dry-run only in v0.2.46. Use --dry-run.", file=sys.stderr)
        return 1
    try:
        result = archive_services.zet_projection_plan_preview(
            Path(args.archive_root),
            zet_ref=args.zet,
            surface=args.surface,
            dry_run=args.dry_run,
            visibility=args.visibility,
            projection_format=args.projection_format,
        )
    except archive_services.ArchiveServiceError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        state = "passed" if result.get("ok") else "blocked"
        zet = result.get("zet") if isinstance(result.get("zet"), dict) else {}
        surface = result.get("surface") if isinstance(result.get("surface"), dict) else {}
        print(f"Projection plan dry-run {state}.")
        print(f"Archive: {result.get('archive_id') or '-'}")
        print(f"zet: {zet.get('zettel_id') or zet.get('source_path') or '-'}")
        print(f"Surface: {surface.get('surface_kind') or '-'}")
        contract = result.get("projection_contract") if isinstance(result.get("projection_contract"), dict) else {}
        if result.get("blockers") and contract.get("supported_surface_kinds"):
            print("Supported surfaces: " + ", ".join(contract.get("supported_surface_kinds") or []))
        if result.get("blockers"):
            print("Blockers:")
            for blocker in result["blockers"]:
                print(f"- {blocker}")
        if result.get("warnings"):
            print("Warnings:")
            for warning in result["warnings"]:
                print(f"- {warning}")
    return 0 if result.get("ok", True) else 1


def command_zet_surface_prototype(args: argparse.Namespace) -> int:
    if not args.dry_run:
        print("zet-surface-prototype is dry-run only; pass --dry-run.", file=sys.stderr)
        return 1
    try:
        result = archive_services.zet_surface_prototype_plan(
            Path(args.archive_root),
            surface_kind=args.surface_kind,
            surface_ref=args.surface_ref,
            dry_run=args.dry_run,
        )
    except (archive_services.ArchiveServiceError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        state = "passed" if result.get("ok") else "blocked"
        surface = result.get("surface") if isinstance(result.get("surface"), dict) else {}
        prototype = result.get("prototype") if isinstance(result.get("prototype"), dict) else {}
        print(f"ZET surface prototype {state}.")
        print(f"Archive: {result.get('archive_id') or '-'}")
        print(f"Surface: {surface.get('surface_kind') or '-'}")
        print(f"Role: {surface.get('role') or '-'}")
        print(f"Integration family: {prototype.get('integration_family') or '-'}")
        if result.get("blockers"):
            print("Blockers:")
            for blocker in result["blockers"]:
                print(f"- {blocker}")
        if result.get("warnings"):
            print("Warnings:")
            for warning in result["warnings"]:
                print(f"- {warning}")
    return 0 if result.get("ok", True) else 1


def command_shared_update_record_review(args: argparse.Namespace) -> int:
    try:
        result = archive_services.zet_shared_update_record_review_preview(
            Path(args.archive_root),
            record=args.record,
            dry_run=args.dry_run,
        )
    except archive_services.ArchiveServiceError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        state = "passed" if result.get("ok") else "blocked"
        print(f"Shared update record review preview {state}.")
        print(f"Archive: {result.get('archive_id') or '-'}")
        print(f"Record: {result.get('record_path') or '-'}")
        print(f"Preview status: {result.get('preview_status') or '-'}")
        if result.get("blockers"):
            print("Blockers:")
            for blocker in result["blockers"]:
                print(f"- {blocker}")
        if result.get("warnings"):
            print("Warnings:")
            for warning in result["warnings"]:
                print(f"- {warning}")
    return 0 if result.get("ok", True) else 1


def command_shared_update_record_review_index(args: argparse.Namespace) -> int:
    try:
        result = archive_services.zet_shared_update_record_review_index(
            Path(args.archive_root),
            records_dir=args.records_dir,
            dry_run=args.dry_run,
            limit=args.limit,
        )
    except archive_services.ArchiveServiceError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        state = "passed" if result.get("ok") else "blocked"
        print(f"Shared update record review index {state}.")
        print(f"Archive: {result.get('archive_id') or '-'}")
        print(f"Records dir: {result.get('records_dir') or '-'}")
        print(f"Index status: {result.get('index_status') or '-'}")
        print(f"Reviewable: {result.get('reviewable_count', 0)}")
        print(f"Blocked: {result.get('blocked_count', 0)}")
        if result.get("blockers"):
            print("Blockers:")
            for blocker in result["blockers"]:
                print(f"- {blocker}")
        if result.get("warnings"):
            print("Warnings:")
            for warning in result["warnings"]:
                print(f"- {warning}")
    return 0 if result.get("ok", True) else 1


def command_shared_update_route_preview(args: argparse.Namespace) -> int:
    try:
        result = archive_services.shared_update_route_preview(
            Path(args.archive_root),
            record=args.record,
            dry_run=args.dry_run,
        )
    except archive_services.ArchiveServiceError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        state = "passed" if result.get("ok") else "blocked"
        print(f"Shared update route preview {state}.")
        print(f"Archive: {result.get('archive_id') or '-'}")
        print(f"Record: {result.get('record_path') or '-'}")
        print(f"Candidate route: {result.get('candidate_route') or '-'}")
        print(f"Route status: {result.get('route_status') or '-'}")
        if result.get("blockers"):
            print("Blockers:")
            for blocker in result["blockers"]:
                print(f"- {blocker}")
        if result.get("warnings"):
            print("Warnings:")
            for warning in result["warnings"]:
                print(f"- {warning}")
    return 0 if result.get("ok", True) else 1


def command_shared_update_attestation_review(args: argparse.Namespace) -> int:
    try:
        result = archive_services.record_shared_update_attestation_review(
            Path(args.archive_root),
            record=args.record,
            decision=args.decision,
            reviewed_by=args.reviewed_by,
            approve=args.approve,
        )
    except archive_services.ArchiveServiceError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        state = "recorded" if result.get("ok") else "blocked"
        print(f"Shared update attestation/review write {state}.")
        print(f"Archive: {result.get('archive_id') or '-'}")
        print(f"Decision: {result.get('decision') or '-'}")
        print(f"Record: {result.get('review_record_path') or result.get('proposed_paths', {}).get('review_record') or '-'}")
        print(f"Receipt: {result.get('receipt_path') or result.get('proposed_paths', {}).get('receipt') or '-'}")
        if result.get("blockers"):
            print("Blockers:")
            for blocker in result["blockers"]:
                print(f"- {blocker}")
        if result.get("warnings"):
            print("Warnings:")
            for warning in result["warnings"]:
                print(f"- {warning}")
    return 0 if result.get("ok", True) else 1


def command_zet_transport_plan(args: argparse.Namespace) -> int:
    try:
        result = archive_services.zet_transport_would_plan(
            Path(args.archive_root),
            record=args.record,
            method=args.method,
            dry_run=args.dry_run,
        )
    except archive_services.ArchiveServiceError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        state = "passed" if result.get("ok") else "blocked"
        print(f"ZET transport would-plan {state}.")
        print(f"Archive: {result.get('archive_id') or '-'}")
        print(f"Record: {result.get('record_path') or '-'}")
        print(f"Method: {result.get('method') or '-'}")
        print(f"Plan status: {result.get('plan_status') or '-'}")
        if result.get("blockers"):
            print("Blockers:")
            for blocker in result["blockers"]:
                print(f"- {blocker}")
        if result.get("warnings"):
            print("Warnings:")
            for warning in result["warnings"]:
                print(f"- {warning}")
    return 0 if result.get("ok", True) else 1


def command_foreign_block(args: argparse.Namespace) -> int:
    try:
        stdin_text = sys.stdin.read() if args.stdin else None
        result = archive_services.foreign_block_intake_check(
            Path(args.archive_root),
            relative_path=args.path,
            text=stdin_text,
            dry_run=args.dry_run,
        )
    except archive_services.ArchiveServiceError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        print(f"Foreign block intake: {result.get('detected_input_kind') or '-'}")
        print(f"Trust state: {result.get('trust_state') or '-'}")
        if result.get("blockers"):
            print("Blockers:")
            for blocker in result["blockers"]:
                print(f"- {blocker}")
        if result.get("warnings"):
            print("Warnings:")
            for warning in result["warnings"]:
                print(f"- {warning}")
        print("Foreign block intake passed." if result.get("ok") else "Foreign block intake blocked.")
    return 0 if result.get("ok") else 1


def command_foreign_block_trust(args: argparse.Namespace) -> int:
    try:
        stdin_text = sys.stdin.read() if args.stdin else None
        result = archive_services.foreign_block_trust_preview(
            Path(args.archive_root),
            intake_report_path=args.intake_report,
            text=stdin_text,
            dry_run=args.dry_run,
        )
    except archive_services.ArchiveServiceError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        print(f"Foreign block trust preview: {result.get('proposed_trust_action') or '-'}")
        print(f"Trust state: {result.get('trust_state') or '-'}")
        if result.get("blockers"):
            print("Blockers:")
            for blocker in result["blockers"]:
                print(f"- {blocker}")
        if result.get("warnings"):
            print("Warnings:")
            for warning in result["warnings"]:
                print(f"- {warning}")
        print("Foreign block trust preview passed." if result.get("ok") else "Foreign block trust preview blocked.")
    return 0 if result.get("ok") else 1


def command_foreign_block_attestation(args: argparse.Namespace) -> int:
    try:
        stdin_text = sys.stdin.read() if args.stdin else None
        result = archive_services.foreign_block_attestation_packet_preview(
            Path(args.archive_root),
            trust_report_path=args.trust_report,
            text=stdin_text,
            dry_run=args.dry_run,
            prospective_attestor=args.prospective_attestor,
            review_scope=args.review_scope,
        )
    except archive_services.ArchiveServiceError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        print(f"Foreign block attestation packet: {result.get('packet_status') or '-'}")
        print(f"Trust state: {result.get('trust_state') or '-'}")
        if result.get("blockers"):
            print("Blockers:")
            for blocker in result["blockers"]:
                print(f"- {blocker}")
        if result.get("warnings"):
            print("Warnings:")
            for warning in result["warnings"]:
                print(f"- {warning}")
        print("Foreign block attestation packet preview passed." if result.get("ok") else "Foreign block attestation packet preview blocked.")
    return 0 if result.get("ok") else 1


def command_foreign_block_quarantine(args: argparse.Namespace) -> int:
    try:
        stdin_text = sys.stdin.read() if args.stdin else None
        result = archive_services.foreign_block_quarantine_plan(
            Path(args.archive_root),
            attestation_packet_path=args.attestation_packet,
            text=stdin_text,
            dry_run=args.dry_run,
            quarantine_case_id=args.quarantine_case_id,
            reviewer=args.reviewer,
            quarantine_policy=args.quarantine_policy,
        )
    except archive_services.ArchiveServiceError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        print(f"Foreign block quarantine plan: {result.get('proposed_quarantine_action') or '-'}")
        print(f"Trust state: {result.get('trust_state') or '-'}")
        if result.get("blockers"):
            print("Blockers:")
            for blocker in result["blockers"]:
                print(f"- {blocker}")
        if result.get("warnings"):
            print("Warnings:")
            for warning in result["warnings"]:
                print(f"- {warning}")
        print("Foreign block quarantine plan passed." if result.get("ok") else "Foreign block quarantine plan blocked.")
    return 0 if result.get("ok") else 1


def command_quarantine_foreign_block(args: argparse.Namespace) -> int:
    try:
        result = archive_services.quarantine_foreign_block(
            Path(args.archive_root),
            plan_path=args.plan,
            dry_run=args.dry_run,
            approve=args.approve,
            reviewed_by=args.reviewed_by,
            expected_case_id=args.expected_case_id,
            review_note=args.review_note,
        )
    except archive_services.ArchiveServiceError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        print(f"Foreign block quarantine write: {result.get('quarantine_write_status') or '-'}")
        print(f"Trust state: {result.get('trust_state') or '-'}")
        if result.get("proposed_paths"):
            print("Proposed paths:")
            for key, value in result["proposed_paths"].items():
                print(f"- {key}: {value}")
        if result.get("files_written"):
            print("Files written:")
            for value in result["files_written"]:
                print(f"- {value}")
        if result.get("blockers"):
            print("Blockers:")
            for blocker in result["blockers"]:
                print(f"- {blocker}")
        if result.get("warnings"):
            print("Warnings:")
            for warning in result["warnings"]:
                print(f"- {warning}")
        print("Foreign block quarantine write passed." if result.get("ok") else "Foreign block quarantine write blocked.")
    return 0 if result.get("ok") else 1


def command_quarantine_review(args: argparse.Namespace) -> int:
    try:
        result = archive_services.foreign_block_quarantine_review_index(
            Path(args.archive_root),
            case_id=args.case_id,
            status=args.status,
            include_receipts=args.include_receipts,
        )
    except archive_services.ArchiveServiceError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        print(f"Foreign block quarantine review index: {result.get('case_count', 0)} case(s)")
        print(f"Trust state: {result.get('trust_state') or '-'}")
        for item in result.get("cases", []):
            print(f"- {item.get('case_id')}: {item.get('quarantine_status')} ({item.get('receipt_consistency', {}).get('status')})")
        if result.get("blockers"):
            print("Blockers:")
            for blocker in result["blockers"]:
                print(f"- {blocker}")
        if result.get("warnings"):
            print("Warnings:")
            for warning in result["warnings"]:
                print(f"- {warning}")
    return 0 if result.get("ok") else 1


def command_quarantine_decision(args: argparse.Namespace) -> int:
    try:
        result = archive_services.foreign_block_quarantine_decision_preview(
            Path(args.archive_root),
            case_id=args.case_id,
            decision_intent=args.decision_intent,
            reviewer=args.reviewer,
            review_note=args.review_note,
            dry_run=args.dry_run,
        )
    except archive_services.ArchiveServiceError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        print(f"Foreign block quarantine decision preview: {result.get('proposed_decision') or '-'}")
        print(f"Trust state: {result.get('trust_state') or '-'}")
        print(f"Decision status: {result.get('decision_status') or '-'}")
        if result.get("blockers"):
            print("Blockers:")
            for blocker in result["blockers"]:
                print(f"- {blocker}")
        if result.get("warnings"):
            print("Warnings:")
            for warning in result["warnings"]:
                print(f"- {warning}")
    return 0 if result.get("ok") else 1


def command_record_quarantine_decision(args: argparse.Namespace) -> int:
    try:
        result = archive_services.record_quarantine_decision(
            Path(args.archive_root),
            decision_preview_path=args.decision_preview,
            dry_run=args.dry_run,
            approve=args.approve,
            reviewed_by=args.reviewed_by,
            expected_case_id=args.expected_case_id,
            expected_decision=args.expected_decision,
            review_note=args.review_note,
        )
    except archive_services.ArchiveServiceError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        print(f"Foreign block quarantine decision record: {result.get('decision') or '-'}")
        print(f"Trust state: {result.get('trust_state') or '-'}")
        print(f"Decision status: {result.get('decision_status') or '-'}")
        if result.get("proposed_paths"):
            print("Proposed paths:")
            for key, value in result["proposed_paths"].items():
                print(f"- {key}: {value}")
        if result.get("files_written"):
            print("Files written:")
            for value in result["files_written"]:
                print(f"- {value}")
        if result.get("blockers"):
            print("Blockers:")
            for blocker in result["blockers"]:
                print(f"- {blocker}")
        if result.get("warnings"):
            print("Warnings:")
            for warning in result["warnings"]:
                print(f"- {warning}")
    return 0 if result.get("ok") else 1


def command_quarantine_decision_review(args: argparse.Namespace) -> int:
    try:
        result = archive_services.foreign_block_quarantine_decision_review_index(
            Path(args.archive_root),
            case_id=args.case_id,
            decision=args.decision,
            include_receipts=args.include_receipts,
        )
    except archive_services.ArchiveServiceError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        print(f"Foreign block quarantine decision review index: {result.get('decision_count', 0)} decision(s)")
        print(f"Trust state: {result.get('trust_state') or '-'}")
        for item in result.get("decisions", []):
            print(f"- {item.get('case_id')}: {item.get('decision')} ({item.get('receipt_consistency', {}).get('status')})")
        if result.get("blockers"):
            print("Blockers:")
            for blocker in result["blockers"]:
                print(f"- {blocker}")
        if result.get("warnings"):
            print("Warnings:")
            for warning in result["warnings"]:
                print(f"- {warning}")
    return 0 if result.get("ok") else 1


def command_quarantine_decision_outcome(args: argparse.Namespace) -> int:
    try:
        result = archive_services.foreign_block_decision_outcome_plan(
            Path(args.archive_root),
            case_id=args.case_id,
            dry_run=args.dry_run,
            expected_decision=args.expected_decision,
            reviewer=args.reviewer,
            review_note=args.review_note,
        )
    except archive_services.ArchiveServiceError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        print(f"Foreign block decision outcome plan: {result.get('proposed_outcome') or '-'}")
        print(f"Trust state: {result.get('trust_state') or '-'}")
        print(f"Outcome status: {result.get('outcome_status') or '-'}")
        if result.get("next_safe_actions"):
            print("Next safe actions:")
            for action in result["next_safe_actions"]:
                print(f"- {action}")
        if result.get("blockers"):
            print("Blockers:")
            for blocker in result["blockers"]:
                print(f"- {blocker}")
        if result.get("warnings"):
            print("Warnings:")
            for warning in result["warnings"]:
                print(f"- {warning}")
    return 0 if result.get("ok") else 1


def command_attestation_review_candidate(args: argparse.Namespace) -> int:
    try:
        result = archive_services.foreign_block_attestation_review_candidate_plan(
            Path(args.archive_root),
            case_id=args.case_id,
            dry_run=args.dry_run,
            expected_decision=args.expected_decision,
            expected_outcome=args.expected_outcome,
            prospective_attestor=args.prospective_attestor,
            review_scope=args.review_scope,
            review_note=args.review_note,
        )
    except archive_services.ArchiveServiceError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        print(f"Foreign block attestation review candidate: {result.get('candidate_status') or '-'}")
        print(f"Trust state: {result.get('trust_state') or '-'}")
        print(f"Attestation status: {result.get('attestation_status') or '-'}")
        candidate = result.get("attestation_review_candidate") if isinstance(result.get("attestation_review_candidate"), dict) else {}
        if candidate.get("next_safe_actions"):
            print("Next safe actions:")
            for action in candidate["next_safe_actions"]:
                print(f"- {action}")
        if result.get("blockers"):
            print("Blockers:")
            for blocker in result["blockers"]:
                print(f"- {blocker}")
        if result.get("warnings"):
            print("Warnings:")
            for warning in result["warnings"]:
                print(f"- {warning}")
    return 0 if result.get("ok") else 1


def command_record_attestation_review_candidate(args: argparse.Namespace) -> int:
    try:
        result = archive_services.record_attestation_review_candidate(
            Path(args.archive_root),
            candidate_plan_path=args.candidate_plan,
            dry_run=args.dry_run,
            approve=args.approve,
            reviewed_by=args.reviewed_by,
            expected_case_id=args.expected_case_id,
            expected_review_scope=args.expected_review_scope,
            expected_attestor=args.expected_attestor,
            review_note=args.review_note,
        )
    except archive_services.ArchiveServiceError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        print(f"Foreign block attestation review candidate record: {result.get('candidate_status') or '-'}")
        print(f"Trust state: {result.get('trust_state') or '-'}")
        print(f"Attestation status: {result.get('attestation_status') or '-'}")
        if result.get("proposed_paths"):
            print("Proposed paths:")
            for key, value in result["proposed_paths"].items():
                print(f"- {key}: {value}")
        if result.get("files_written"):
            print("Files written:")
            for value in result["files_written"]:
                print(f"- {value}")
        if result.get("blockers"):
            print("Blockers:")
            for blocker in result["blockers"]:
                print(f"- {blocker}")
        if result.get("warnings"):
            print("Warnings:")
            for warning in result["warnings"]:
                print(f"- {warning}")
    return 0 if result.get("ok") else 1


def command_attestation_candidate_review(args: argparse.Namespace) -> int:
    try:
        result = archive_services.foreign_block_attestation_review_candidate_index(
            Path(args.archive_root),
            case_id=args.case_id,
            review_scope=args.review_scope,
            include_receipts=args.include_receipts,
        )
    except archive_services.ArchiveServiceError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        print(f"Foreign block attestation review candidate index: {result.get('candidate_count', 0)} candidate(s)")
        print(f"Trust state: {result.get('trust_state') or '-'}")
        for item in result.get("candidates", []):
            print(f"- {item.get('case_id')}: {item.get('review_scope')} ({item.get('candidate_receipt_consistency', {}).get('status')})")
        if result.get("blockers"):
            print("Blockers:")
            for blocker in result["blockers"]:
                print(f"- {blocker}")
        if result.get("warnings"):
            print("Warnings:")
            for warning in result["warnings"]:
                print(f"- {warning}")
    return 0 if result.get("ok") else 1


def command_attestation_statement_draft(args: argparse.Namespace) -> int:
    try:
        result = archive_services.foreign_block_attestation_statement_draft_preview(
            Path(args.archive_root),
            case_id=args.case_id,
            dry_run=args.dry_run,
            expected_review_scope=args.expected_review_scope,
            prospective_attestor=args.prospective_attestor,
            statement_style=args.statement_style,
            review_note=args.review_note,
        )
    except archive_services.ArchiveServiceError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        print(f"Foreign block attestation statement draft: {result.get('draft_status') or '-'}")
        print(f"Trust state: {result.get('trust_state') or '-'}")
        print(f"Attestation status: {result.get('attestation_status') or '-'}")
        print(f"Signature status: {result.get('signature_status') or '-'}")
        draft = result.get("attestation_statement_draft") if isinstance(result.get("attestation_statement_draft"), dict) else {}
        if draft.get("statement_lines"):
            print("Statement draft lines:")
            for line in draft["statement_lines"]:
                print(f"- {line}")
        if result.get("blockers"):
            print("Blockers:")
            for blocker in result["blockers"]:
                print(f"- {blocker}")
        if result.get("warnings"):
            print("Warnings:")
            for warning in result["warnings"]:
                print(f"- {warning}")
    return 0 if result.get("ok") else 1


def command_record_attestation_statement_draft(args: argparse.Namespace) -> int:
    try:
        result = archive_services.record_attestation_statement_draft(
            Path(args.archive_root),
            draft_preview_path=args.draft_preview,
            dry_run=args.dry_run,
            approve=args.approve,
            reviewed_by=args.reviewed_by,
        )
    except archive_services.ArchiveServiceError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        print(f"Foreign block attestation statement draft record: {result.get('draft_record_status') or '-'}")
        print(f"Trust state: {result.get('trust_state') or '-'}")
        print(f"Attestation status: {result.get('attestation_status') or '-'}")
        print(f"Signature status: {result.get('signature_status') or '-'}")
        if result.get("proposed_paths"):
            print("Proposed paths:")
            for key, value in result["proposed_paths"].items():
                print(f"- {key}: {value}")
        if result.get("files_written"):
            print("Files written:")
            for value in result["files_written"]:
                print(f"- {value}")
        if result.get("blockers"):
            print("Blockers:")
            for blocker in result["blockers"]:
                print(f"- {blocker}")
        if result.get("warnings"):
            print("Warnings:")
            for warning in result["warnings"]:
                print(f"- {warning}")
    return 0 if result.get("ok") else 1


def command_attestation_statement_draft_review(args: argparse.Namespace) -> int:
    try:
        result = archive_services.foreign_block_attestation_statement_draft_review_index(
            Path(args.archive_root),
            case_id=args.case_id,
            statement_style=args.statement_style,
            review_scope=args.review_scope,
            include_receipts=args.include_receipts,
        )
    except archive_services.ArchiveServiceError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        print(f"Foreign block attestation statement draft review index: {result.get('displayed_draft_count', 0)} draft(s)")
        print(f"Trust state: {result.get('trust_state') or '-'}")
        for item in result.get("statement_drafts", []):
            print(f"- {item.get('case_id')}: {item.get('review_scope')} / {item.get('statement_style')} ({item.get('receipt_consistency', {}).get('status')})")
        if result.get("blockers"):
            print("Blockers:")
            for blocker in result["blockers"]:
                print(f"- {blocker}")
        if result.get("warnings"):
            print("Warnings:")
            for warning in result["warnings"]:
                print(f"- {warning}")
    return 0 if result.get("ok") else 1


def command_attestation_statement_draft_decision(args: argparse.Namespace) -> int:
    try:
        result = archive_services.foreign_block_attestation_statement_draft_decision_preview(
            Path(args.archive_root),
            case_id=args.case_id,
            dry_run=args.dry_run,
            decision_intent=args.decision_intent,
            reviewer=args.reviewer,
            expected_review_scope=args.expected_review_scope,
            expected_statement_style=args.expected_statement_style,
            review_note=args.review_note,
        )
    except archive_services.ArchiveServiceError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        print(f"Foreign block attestation statement draft decision preview: {result.get('proposed_route') or '-'}")
        print(f"Trust state: {result.get('trust_state') or '-'}")
        print(f"Decision status: {result.get('decision_status') or '-'}")
        print(f"Attestation status: {result.get('attestation_status') or '-'}")
        print(f"Signature status: {result.get('signature_status') or '-'}")
        if result.get("blockers"):
            print("Blockers:")
            for blocker in result["blockers"]:
                print(f"- {blocker}")
        if result.get("warnings"):
            print("Warnings:")
            for warning in result["warnings"]:
                print(f"- {warning}")
    return 0 if result.get("ok") else 1


def command_promote(args: argparse.Namespace) -> int:
    if args.dry_run:
        try:
            result = archive_services.promote_zettel_dry_run(
                Path(args.archive_root),
                zettel_id=args.zettel_id,
                relative_path=args.path,
            )
        except archive_services.ArchiveServiceError as exc:
            print(str(exc), file=sys.stderr)
            return 1

        if args.format == "json":
            print_json(result)
        else:
            print(f"Dry-run promotion for {result.get('zettel_id') or result['draft_path']}")
            print(f"Draft path: {result['draft_path']}")
            print(f"Proposed canonical path: {result['proposed_canonical_path']}")
            print(f"Proposed receipt path: {result['proposed_receipt_path']}")
            if result.get("checklist"):
                print("Checklist:")
                for item in result["checklist"]:
                    print(f"- {item['id']}: {item['status']} ({item['source']})")
            guidance = result.get("mint_checklist_guidance") if isinstance(result.get("mint_checklist_guidance"), dict) else {}
            if guidance.get("missing_required_item_ids"):
                print("Checklist guidance:")
                print(f"- Preferred frontmatter path: {guidance.get('preferred_frontmatter_path')}")
                print("- Missing required item ids: " + ", ".join(guidance.get("missing_required_item_ids") or []))
                print("- Rerun mint-zet --dry-run after human review marks those items true.")
            if result.get("near_duplicates"):
                print("Near duplicates:")
                for item in result["near_duplicates"]:
                    print(f"- {item['path']}: {item['reason']}")
            if result["blockers"]:
                print("Blockers:")
                for blocker in result["blockers"]:
                    print(f"- {blocker}")
            if result["warnings"]:
                print("Warnings:")
                for warning in result["warnings"]:
                    print(f"- {warning}")
            print("Promotion dry-run passed." if result["ok"] else "Promotion dry-run blocked.")
        return 0 if result["ok"] else 1

    if not args.approve:
        print("Real promotion requires --approve.", file=sys.stderr)
        return 1
    if not args.reviewed_by:
        print("Real promotion requires --reviewed-by.", file=sys.stderr)
        return 1

    try:
        result = archive_services.promote_zettel(
            Path(args.archive_root),
            zettel_id=args.zettel_id,
            relative_path=args.path,
            reviewed_by=args.reviewed_by,
            allow_warnings=args.allow_warnings,
        )
    except (archive_services.ArchiveServiceError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        print(f"Promoted {result['zettel_id']} to canonical memory.")
        print(f"Canonical path: {result['canonical_path']}")
        print(f"Receipt path: {result['receipt_path']}")
        if result["warnings"]:
            print("Warnings approved:")
            for warning in result["warnings"]:
                print(f"- {warning}")
    return 0


def command_mint_zettel(args: argparse.Namespace) -> int:
    if args.dry_run:
        try:
            result = archive_services.mint_zettel_dry_run(
                Path(args.archive_root),
                zettel_id=args.zettel_id,
                relative_path=args.path,
            )
        except archive_services.ArchiveServiceError as exc:
            print(str(exc), file=sys.stderr)
            return 1

        if args.format == "json":
            print_json(result)
        else:
            print(f"Dry-run mint for {result.get('zettel_id') or result['draft_path']}")
            print(f"Draft path: {result['draft_path']}")
            print(f"Proposed canonical path: {result['proposed_canonical_path']}")
            print(f"Proposed mint receipt path: {result['proposed_mint_receipt_path']}")
            print(f"Proposed draft snapshot path: {result['proposed_draft_snapshot_path']}")
            if result.get("checklist"):
                print("Checklist:")
                for item in result["checklist"]:
                    print(f"- {item['id']}: {item['status']} ({item['source']})")
            if result.get("near_duplicates"):
                print("Near duplicates:")
                for item in result["near_duplicates"]:
                    print(f"- {item['path']}: {item['reason']}")
            if result["blockers"]:
                print("Blockers:")
                for blocker in result["blockers"]:
                    print(f"- {blocker}")
            if result["warnings"]:
                print("Warnings:")
                for warning in result["warnings"]:
                    print(f"- {warning}")
            print("Mint dry-run passed." if result["ok"] else "Mint dry-run blocked.")
        return 0 if result["ok"] else 1

    if not args.approve:
        print("Real minting requires --approve.", file=sys.stderr)
        return 1
    if not args.reviewed_by:
        print("Real minting requires --reviewed-by.", file=sys.stderr)
        return 1

    try:
        result = archive_services.mint_zettel(
            Path(args.archive_root),
            zettel_id=args.zettel_id,
            relative_path=args.path,
            reviewed_by=args.reviewed_by,
            allow_warnings=args.allow_warnings,
        )
    except (archive_services.ArchiveServiceError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        print(f"Minted {result['zettel_id']} into canonical private archive memory.")
        print(f"Canonical path: {result['canonical_path']}")
        print(f"Mint receipt path: {result['mint_receipt_path']}")
        print(f"Draft snapshot path: {result['draft_snapshot_path']}")
        if result["warnings"]:
            print("Warnings approved:")
            for warning in result["warnings"]:
                print(f"- {warning}")
    return 0


def command_zet_self_contained_check(args: argparse.Namespace) -> int:
    if not args.dry_run:
        print("zet-self-contained-check is read-only and requires --dry-run.", file=sys.stderr)
        return 1
    try:
        result = archive_services.zet_self_contained_check(
            Path(args.archive_root),
            zettel_id=args.zettel_id,
            relative_path=args.path,
            dry_run=True,
        )
    except (archive_services.ArchiveServiceError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        state = "self-contained" if result.get("self_contained") else "needs revision"
        print(f"Zet self-contained check {state}.")
        print(f"Archive: {result.get('archive_id') or '-'}")
        print(f"Zet: {result.get('zettel_id') or result.get('zettel_path') or '-'}")
        check = result.get("self_contained_check") if isinstance(result.get("self_contained_check"), dict) else {}
        print(f"Scratch refs: {check.get('scratch_reference_count', 0)}")
        print(f"External citation URLs: {check.get('external_citation_url_count', 0)}")
        if result.get("warnings"):
            print("Warnings:")
            for warning in result["warnings"]:
                print(f"- {warning}")
    return 0 if result.get("ok", True) else 1


def command_zet_quality_check(args: argparse.Namespace) -> int:
    if not args.dry_run:
        print("zet-quality-check is read-only and requires --dry-run.", file=sys.stderr)
        return 1
    try:
        result = archive_services.zet_quality_check(
            Path(args.archive_root),
            zettel_id=args.zettel_id,
            relative_path=args.path,
            dry_run=True,
        )
    except (archive_services.ArchiveServiceError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        print(f"Zet quality check {result.get('quality_state') or 'unknown'}.")
        print(f"Archive: {result.get('archive_id') or '-'}")
        print(f"Zet: {result.get('zettel_id') or result.get('zettel_path') or '-'}")
        print(f"Issues: {result.get('issue_count', 0)}")
        if result.get("issues"):
            print("Issues:")
            for issue in result["issues"]:
                print(f"- {issue.get('code')}: {issue.get('severity')}")
    return 0 if result.get("ok", True) else 1


def command_ai_scratch_gc(args: argparse.Namespace) -> int:
    if args.dry_run and args.approve:
        print("Use either --dry-run or --approve, not both.", file=sys.stderr)
        return 1
    if not args.dry_run and not args.approve:
        print("ai-scratch-gc requires --dry-run or --approve.", file=sys.stderr)
        return 1
    if args.approve and not args.reviewed_by:
        print("ai-scratch-gc requires --reviewed-by when --approve is used.", file=sys.stderr)
        return 1
    try:
        result = archive_services.ai_scratch_gc_for_zettel(
            Path(args.archive_root),
            zettel_id=args.zettel_id,
            relative_path=args.path,
            dry_run=args.dry_run,
            approve=args.approve,
            reviewed_by=args.reviewed_by,
        )
    except (archive_services.ArchiveServiceError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        state = "cleaned" if args.approve else "planned"
        if not result.get("ok", True):
            state = "blocked"
        print(f"AI scratch GC {state}.")
        print(f"Archive: {result.get('archive_id') or '-'}")
        print(f"Zet: {result.get('zettel_id') or result.get('zettel_path') or '-'}")
        plan = result.get("cleanup_plan") if isinstance(result.get("cleanup_plan"), dict) else {}
        print(f"Candidates: {plan.get('candidate_count', 0)}")
        if result.get("receipt_path"):
            print(f"Receipt: {result['receipt_path']}")
        if result.get("deleted"):
            print("Deleted:")
            for item in result["deleted"]:
                print(f"- {item.get('path')}")
        elif result.get("would_change"):
            print("Would change:")
            for path in result["would_change"]:
                print(f"- {path}")
        if result.get("blockers"):
            print("Blockers:")
            for blocker in result["blockers"]:
                print(f"- {blocker}")
        if result.get("warnings"):
            print("Warnings:")
            for warning in result["warnings"]:
                print(f"- {warning}")
    return 0 if result.get("ok", True) else 1


def command_retire_draft(args: argparse.Namespace) -> int:
    if args.dry_run and args.approve:
        print("Use either --dry-run or --approve, not both.", file=sys.stderr)
        return 1
    if not args.dry_run and not args.approve:
        print("retire-draft requires --dry-run or --approve.", file=sys.stderr)
        return 1
    if args.approve and not args.reviewed_by:
        print("retire-draft requires --reviewed-by when --approve is used.", file=sys.stderr)
        return 1

    try:
        result = archive_services.retire_minted_draft(
            Path(args.archive_root),
            zettel_id=args.zettel_id,
            relative_path=args.path,
            reviewed_by=args.reviewed_by,
            approve=args.approve,
        )
    except (archive_services.ArchiveServiceError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        state = "passed" if result.get("ok") else "blocked"
        print(f"Retire draft {state} for {result.get('zettel_id') or result.get('draft_path')}.")
        print(f"Draft path: {result.get('draft_path') or '-'}")
        print(f"Canonical path: {result.get('canonical_path') or '-'}")
        print(f"Mint receipt path: {result.get('mint_receipt_path') or '-'}")
        print(f"Draft snapshot path: {result.get('draft_snapshot_path') or '-'}")
        print(f"Retire receipt path: {result.get('retire_receipt_path') or '-'}")
        if result.get("blockers"):
            print("Blockers:")
            for blocker in result["blockers"]:
                print(f"- {blocker}")
        if result.get("warnings"):
            print("Warnings:")
            for warning in result["warnings"]:
                print(f"- {warning}")
        if result.get("next_safe_actions"):
            print("Next safe actions:")
            for action in result["next_safe_actions"]:
                print(f"- {action}")
        if result.get("dry_run"):
            print("Writes: none")
        else:
            print("Retired inbox draft.")
    return 0 if result.get("ok") else 1


def command_remint_reconcile(args: argparse.Namespace) -> int:
    if args.dry_run and args.approve:
        print("Use either --dry-run or --approve, not both.", file=sys.stderr)
        return 1
    approve = bool(args.approve)
    if approve and not (args.reviewed_by or "").strip():
        print("remint-reconcile requires --reviewed-by when --approve is used.", file=sys.stderr)
        return 1

    try:
        if approve:
            result = archive_services.remint_reconcile_apply(
                Path(args.archive_root),
                zettel_id=args.zettel_id,
                relative_path=args.path,
                reviewed_by=args.reviewed_by,
                content_changed_ack=bool(args.content_changed_ack),
            )
        else:
            result = archive_services.remint_reconcile_plan(
                Path(args.archive_root),
                zettel_id=args.zettel_id,
                relative_path=args.path,
            )
    except (archive_services.ArchiveServiceError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        state = "passed" if result.get("ok") else "blocked"
        print(f"Reconcile {state} for {result.get('zettel_id') or result.get('canonical_path')}.")
        print(f"Canonical path: {result.get('canonical_path') or '-'}")
        print(f"Mint receipt path: {result.get('mint_receipt_path') or '-'}")
        print(f"Draft snapshot path: {result.get('draft_snapshot_path') or '-'}")
        print(f"Drift class: {result.get('drift_class') or 'unclassified'}")
        drift_class = result.get("drift_class")
        show_content = drift_class == "content_change" or approve
        if show_content:
            print("Current on-disk content:")
            field_changes = result.get("frontmatter_field_changes") or []
            if field_changes:
                for change in field_changes:
                    print(
                        f"- {change.get('field')}: receipt={change.get('receipt_value')!r} "
                        f"current={change.get('current_value')!r}"
                    )
            else:
                print("- no content change detected (newline/BOM only)")
            print(f"- body_changed: {result.get('body_changed')}")
            text = result.get("current_canonical_text")
            if isinstance(text, str):
                print("--- canonical text (begin) ---")
                print(text.rstrip("\n"))
                print("--- canonical text (end) ---")
        if result.get("content_change_ack_required"):
            print("Content change acknowledgment required: rerun --approve with --content-changed-ack.")
        if result.get("blockers"):
            print("Blockers:")
            for blocker in result["blockers"]:
                print(f"- {blocker}")
        if result.get("warnings"):
            print("Warnings:")
            for warning in result["warnings"]:
                print(f"- {warning}")
        if result.get("next_safe_actions"):
            print("Next safe actions:")
            for action in result["next_safe_actions"]:
                print(f"- {action}")
        if result.get("dry_run"):
            print("Writes: none")
        else:
            print(f"Reconciled mint receipt: {result.get('mint_receipt_path')}")
            print(f"Wrote reconcile receipt: {result.get('reconcile_receipt_path')}")
    return 0 if result.get("ok") else 1


def command_mint_zettel_batch(args: argparse.Namespace) -> int:
    try:
        result = archive_services.mint_zet_batch(
            Path(args.archive_root),
            plan_path=args.plan,
            dry_run=args.dry_run,
            approve=args.approve,
            reviewed_by=args.reviewed_by,
            allow_warnings=args.allow_warnings,
            max_items=args.max_items,
            skip_existing=args.skip_existing,
        )
    except (archive_services.ArchiveServiceError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        print(f"Mint batch {result.get('write_status')} ({result['summary']['candidate_item_count']} item(s)).")
        print(f"Receipt path: {result.get('receipt_path') or '-'}")
        print(f"Would/write count: {result['summary']['would_write_count'] or result['summary']['written_item_count']}")
        print(f"Skipped existing: {result['summary']['skipped_existing_item_count']}")
        print(f"Failed: {result['summary']['failed_item_count']}")
    return 0 if result.get("ok") else 1


def command_retire_draft_batch(args: argparse.Namespace) -> int:
    try:
        result = archive_services.retire_draft_batch(
            Path(args.archive_root),
            plan_path=args.plan,
            dry_run=args.dry_run,
            approve=args.approve,
            reviewed_by=args.reviewed_by,
            max_items=args.max_items,
            skip_existing=args.skip_existing,
        )
    except (archive_services.ArchiveServiceError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        print(f"Retire draft batch {result.get('write_status')} ({result['summary']['candidate_item_count']} item(s)).")
        print(f"Receipt path: {result.get('receipt_path') or '-'}")
        print(f"Would/write count: {result['summary']['would_write_count'] or result['summary']['written_item_count']}")
        print(f"Skipped existing: {result['summary']['skipped_existing_item_count']}")
        print(f"Failed: {result['summary']['failed_item_count']}")
        if result.get("next_safe_actions"):
            print("Next safe actions:")
            for action in result["next_safe_actions"]:
                print(f"- {action}")
    return 0 if result.get("ok") else 1


def command_index(args: argparse.Namespace) -> int:
    try:
        result = archive_services.index_archive(Path(args.archive_root))
    except archive_services.ArchiveServiceError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        print(
            "Indexed "
            f"{result['zettels']} zettel(s), "
            f"{result['objects']} object(s), "
            f"{result['derived_texts']} derived text record(s), "
            f"{result['views']} view(s), "
            f"{result['source_map_entries']} source map item(s) "
            f"at {result['index_path']}"
        )
    return 0


def command_view_zets(args: argparse.Namespace) -> int:
    facets: dict[str, str] = {}
    for raw in args.facet or []:
        if "=" not in raw:
            print(f"--facet expects key=value, got: {raw}", file=sys.stderr)
            return 1
        key, value = raw.split("=", 1)
        facets[key.strip()] = value.strip()
    if bool(args.view_id) == bool(facets):
        print("Provide exactly one of --view-id or --facet.", file=sys.stderr)
        return 1
    try:
        result = archive_services.view_zets(
            Path(args.archive_root),
            view_id=args.view_id,
            facets=facets or None,
            limit=args.limit,
        )
    except archive_services.ArchiveServiceError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if args.format == "json":
        print_json(result)
    else:
        label = result.get("view_name") or result.get("view_id") or "facet query"
        print(f"{label}: {result['count']} zet(s)")
        for item in result["zettels"]:
            print(f"  {item['id']}\t{item['status']}\t{item['title'] or ''}")
        for blocker in result.get("blockers", []):
            print(f"BLOCKED: {blocker}")
    return 0 if result.get("ok") else 1


def command_view_health(args: argparse.Namespace) -> int:
    if not args.dry_run:
        print("view-health is read-only and requires --dry-run.", file=sys.stderr)
        return 1
    try:
        result = archive_services.view_health(
            Path(args.archive_root),
            dry_run=True,
            max_values=args.max_values,
        )
    except archive_services.ArchiveServiceError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if args.format == "json":
        print_json(result)
    else:
        summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
        print(
            "View health: "
            f"{summary.get('active_view_count', 0)} active, "
            f"{summary.get('empty_view_count', 0)} empty, "
            f"{summary.get('blocked_view_count', 0)} blocked"
        )
        role_summary = result.get("facet_role_summary") if isinstance(result.get("facet_role_summary"), dict) else {}
        print(
            "Facet roles: "
            f"{role_summary.get('navigation_key_count', 0)} navigation, "
            f"{role_summary.get('internal_key_count', 0)} internal, "
            f"{role_summary.get('unknown_key_count', 0)} unknown"
        )
        for view in result.get("views", []):
            if not isinstance(view, dict):
                continue
            print(f"- {view.get('id')}: {view.get('state')} ({view.get('count', 0)} zet(s))")
        for blocker in result.get("blockers", []):
            print(f"BLOCKED: {blocker}")
        for warning in result.get("warnings", []):
            print(f"WARNING: {warning}")
        for action in result.get("next_safe_actions", []):
            print(f"NEXT: {action}")
        print("Writes: none")
    return 0 if result.get("ok") else 1


def command_view_recommendation_plan(args: argparse.Namespace) -> int:
    if not args.dry_run:
        print("view-recommendation-plan is read-only and requires --dry-run.", file=sys.stderr)
        return 1
    try:
        result = archive_services.view_recommendation_plan(
            Path(args.archive_root),
            dry_run=True,
            max_values=args.max_values,
            max_recommendations=args.max_recommendations,
        )
    except archive_services.ArchiveServiceError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if args.format == "json":
        print_json(result)
    else:
        summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
        print("View recommendation plan:")
        print(f"- recommendations: {summary.get('recommendation_count', 0)}")
        print(f"- navigation facet keys: {summary.get('navigation_key_count', 0)}")
        print(f"- empty saved views: {summary.get('empty_view_count', 0)}")
        for recommendation in result.get("recommendations", []):
            if not isinstance(recommendation, dict):
                continue
            print(
                f"* {recommendation.get('view_id_suggestion')}: "
                f"{recommendation.get('facet_key')}={recommendation.get('facet_value')} "
                f"({recommendation.get('match_count', 0)} zet(s))"
            )
        for blocker in result.get("blockers", []):
            print(f"BLOCKED: {blocker}")
        for warning in result.get("warnings", []):
            print(f"WARNING: {warning}")
        for action in result.get("next_safe_actions", []):
            print(f"NEXT: {action}")
        print("Writes: none")
    return 0 if result.get("ok") else 1


def command_index_health(args: argparse.Namespace) -> int:
    if not args.dry_run:
        print("index-health is read-only and requires --dry-run.", file=sys.stderr)
        return 1
    try:
        result = archive_services.index_health(
            Path(args.archive_root),
            dry_run=True,
            max_items=args.max_items,
        )
    except archive_services.ArchiveServiceError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if args.format == "json":
        print_json(result)
    else:
        summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
        print(f"Index health: {result.get('index_state')}")
        print(
            "Zettels: "
            f"{summary.get('live_zettel_count', 0)} live, "
            f"{summary.get('indexed_zettel_count', 0)} indexed"
        )
        for reason in result.get("stale_reasons", []):
            print(f"STALE: {reason}")
        for blocker in result.get("blockers", []):
            print(f"BLOCKED: {blocker}")
        for action in result.get("next_safe_actions", []):
            print(f"NEXT: {action}")
        print("Writes: none")
    return 0 if result.get("ok") else 1


def command_related_zets(args: argparse.Namespace) -> int:
    try:
        result = archive_services.get_related_zets(
            Path(args.archive_root),
            args.zettel_id,
            depth=args.depth,
            edge_types=args.edge_type or None,
            limit=args.limit,
        )
    except archive_services.ArchiveServiceError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if args.format == "json":
        print_json(result)
    else:
        print(f"Related zets for {result['zettel_id']}: {result['count']}")
        for item in result["related"]:
            arrow = "->" if item["direction"] == "out" else "<-"
            print(f"  {arrow} {item['id']} ({item['edge_type'] or 'untyped'}, hop {item['hop']}) {item['title'] or ''}")
    return 0


def command_search(args: argparse.Namespace) -> int:
    try:
        result = archive_services.search_archive(Path(args.archive_root), args.query, limit=args.limit)
    except archive_services.ArchiveServiceError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        print(f"Found {result['count']} result(s).")
        for item in result["results"]:
            print(
                "\t".join(
                    [
                        str(item.get("type") or "-"),
                        str(item.get("id") or "-"),
                        str(item.get("title") or "(untitled)"),
                        str(item.get("path") or "-"),
                        str(item.get("snippet") or ""),
                    ]
                )
            )
    return 0


def command_pack(args: argparse.Namespace) -> int:
    try:
        result = archive_services.pack_work_context(
            Path(args.archive_root),
            view_id=args.view,
            purpose=args.purpose,
            mode=args.mode,
            target_archive=args.target_archive,
        )
    except (archive_services.ArchiveServiceError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        print(f"Created parcel {result['package_id']} at {result['package_path']}")
        print(f"View: {result['view_id']}")
        print(f"Mode: {result['mode']}")
        print(f"zets: {result['zettels']}")
        print(f"Objects: {result['objects']} metadata record(s)")
    return 0


def command_import_workpack(args: argparse.Namespace) -> int:
    if not args.dry_run:
        print("Only --dry-run parcel admit/import is implemented. Real admit/import is intentionally unavailable.", file=sys.stderr)
        return 1
    try:
        result = archive_services.import_workpack_dry_run_with_trust(
            Path(args.archive_root),
            Path(args.workpack),
            counterparty_id=args.counterparty_id,
            counterparty_fingerprint=args.counterparty_fingerprint,
        )
    except (archive_services.ArchiveServiceError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        state = "passed" if result["ok"] else "blocked"
        print(f"Parcel admit dry-run {state}: {result['package_id']}")
        print(f"Target archive: {result['target_archive']}")
        print(f"Proposed receipt path: {result['proposed_receipt_path']}")
        print(f"zets: {len(result['zettels'])}")
        print(f"Objects: {len(result['objects'])}")
        print(f"Scope gate included zettels: {len(result['scope_gate']['included_zettels'])}")
        print(f"Trust gate: {result['trust_gate']['status']}")
        if result["blockers"]:
            print("Blockers:")
            for blocker in result["blockers"]:
                print(f"- {blocker}")
        if result["warnings"]:
            print("Warnings:")
        for warning in result["warnings"]:
            print(f"- {warning}")
    return 0 if result["ok"] else 1


def command_staged_cleanup_check(args: argparse.Namespace) -> int:
    if not args.dry_run:
        print("staged-cleanup-check is report-only; pass --dry-run.", file=sys.stderr)
        return 1
    try:
        result = archive_services.staged_cleanup_check(
            Path(args.archive_root),
            args.staged,
            deferred_path=Path(args.deferred) if args.deferred else None,
        )
    except (archive_services.ArchiveServiceError, OSError, json.JSONDecodeError, yaml.YAMLError) as exc:
        print(f"Staged cleanup check failed: {exc}", file=sys.stderr)
        return 1
    if args.format == "json":
        print_json(result)
    else:
        for entry in result.get("files", []):
            print(f"{entry['path']}: {entry['status']}")
        print(f"safe_to_cleanup: {result.get('safe_to_cleanup')}")
        for action in result.get("next_safe_actions", []):
            print(f"- {action}")
        for blocker in result.get("blockers", []):
            print(f"BLOCKED: {blocker}")
    return 0 if result.get("ok") and result.get("safe_to_cleanup") else 1


def command_objet_capture_selection(args: argparse.Namespace) -> int:
    if args.dry_run == args.approve:
        print("objet-capture-selection requires exactly one of --dry-run or --approve.", file=sys.stderr)
        return 1
    if args.approve and not args.reviewed_by:
        print("objet-capture-selection requires --reviewed-by when --approve is used.", file=sys.stderr)
        return 1
    pairing_values = [
        args.derivation_kind,
        args.tool_name,
        args.tool_version,
        args.review_status,
        args.model_name,
        args.model_version,
        args.confidence,
        args.language,
        True if args.born_digital else None,
    ]
    if args.derived_text_staged_path is None and any(value is not None for value in pairing_values):
        print(
            "Derived-text pairing flags require --derived-text-staged-path.",
            file=sys.stderr,
        )
        return 1
    if args.derived_text_staged_path is not None and any(
        value is None for value in [args.derivation_kind, args.tool_name, args.tool_version, args.review_status]
    ):
        print(
            "--derived-text-staged-path requires --derivation-kind, --tool-name, --tool-version, and --review-status.",
            file=sys.stderr,
        )
        return 1

    try:
        result = archive_services.objet_capture_selection_manifest(
            Path(args.archive_root),
            staged_path=args.staged_path,
            source_intake_receipt=args.source_intake_receipt,
            item_id=args.item_id,
            manifest_id=args.manifest_id,
            project_intake_receipt=args.project_intake_receipt,
            dry_run=args.dry_run,
            approve=args.approve,
            reviewed_by=args.reviewed_by,
            derived_text_staged_path=args.derived_text_staged_path,
            derivation_kind=args.derivation_kind,
            tool_name=args.tool_name,
            tool_version=args.tool_version,
            review_status=args.review_status,
            model_name=args.model_name,
            model_version=args.model_version,
            confidence=args.confidence,
            language=args.language,
            born_digital=args.born_digital,
        )
    except (archive_services.ArchiveServiceError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print_objet_capture_selection_result(result, args.format)
    return 0 if result.get("ok", True) else 1


def print_objet_capture_selection_result(result: dict[str, Any], output_format: str) -> None:
    if output_format == "json":
        print_json(result)
        return
    state = "passed" if result.get("ok") else "blocked"
    item = result.get("item") if isinstance(result.get("item"), dict) else {}
    print(f"Objet capture selection {state}.")
    print(f"Archive: {result.get('archive_id') or '-'}")
    print(f"Manifest id: {result.get('selection_manifest_id') or '-'}")
    print(f"Object id: {item.get('approved_object_id') or '-'}")
    if result.get("dry_run"):
        print(f"Proposed selection: {result.get('proposed_selection_path') or '-'}")
        print("Writes: none")
    else:
        print(f"Selection: {result.get('selection_path') or '-'}")
    if result.get("blockers"):
        print("Blockers:")
        for blocker in result["blockers"]:
            print(f"- {blocker}")
    if result.get("warnings"):
        print("Warnings:")
        for warning in result["warnings"]:
            print(f"- {warning}")


def command_objet_capture(args: argparse.Namespace) -> int:
    if args.dry_run and args.approve:
        print("Use either --dry-run or --approve, not both.", file=sys.stderr)
        return 1
    if not args.dry_run and not args.approve:
        print("Objet capture requires --dry-run or --approve.", file=sys.stderr)
        return 1
    if args.approve and not args.reviewed_by:
        print("Objet capture requires --reviewed-by when --approve is used.", file=sys.stderr)
        return 1

    try:
        if args.dry_run:
            result = archive_services.objet_capture_dry_run(
                Path(args.archive_root),
                Path(args.selection),
                project_intake_receipt=args.project_intake_receipt,
            )
        else:
            result = archive_services.objet_capture_apply(
                Path(args.archive_root),
                Path(args.selection),
                reviewed_by=args.reviewed_by,
                project_intake_receipt=args.project_intake_receipt,
            )
    except (archive_services.ArchiveServiceError, OSError, json.JSONDecodeError) as exc:
        print(f"Objet capture failed: {exc}", file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        for entry in result.get("items", []):
            print(f"{entry.get('item_id')}: {entry.get('action') or entry.get('planned_action')}")
        summary = result.get("summary") or {}
        print("Summary: " + ", ".join(f"{key}={value}" for key, value in summary.items()))
        for blocker in result.get("blockers", []):
            print(f"BLOCKED: {blocker}")
    return 0 if result.get("ok") else 1


def command_derive_text_capture(args: argparse.Namespace) -> int:
    if args.dry_run and args.approve:
        print("Use either --dry-run or --approve, not both.", file=sys.stderr)
        return 1
    if not args.dry_run and not args.approve:
        print("Derived text capture requires --dry-run or --approve.", file=sys.stderr)
        return 1
    if args.approve and not args.reviewed_by:
        print("Derived text capture requires --reviewed-by when --approve is used.", file=sys.stderr)
        return 1
    single_fields = [
        args.text_file,
        args.source_object_id,
        args.derivation_kind,
        args.tool_name,
        args.tool_version,
        args.review_status,
    ]
    single_optional_fields = [
        args.model_name,
        args.model_version,
        args.confidence,
        args.language,
        True if args.born_digital else None,
    ]
    if args.from_manifest and any(value is not None for value in single_fields + single_optional_fields):
        print("Use --from-manifest or single-file capture arguments, not both.", file=sys.stderr)
        return 1
    if not args.from_manifest and any(value is None for value in single_fields):
        print(
            "Derived text capture requires --text-file, --source-object-id, --derivation-kind, --tool-name, --tool-version, and --review-status unless --from-manifest is used.",
            file=sys.stderr,
        )
        return 1

    try:
        if args.from_manifest:
            if args.dry_run:
                result = archive_services.derived_text_capture_manifest_dry_run(
                    Path(args.archive_root),
                    Path(args.from_manifest),
                )
            else:
                result = archive_services.derived_text_capture_manifest_apply(
                    Path(args.archive_root),
                    Path(args.from_manifest),
                    reviewed_by=args.reviewed_by,
                )
        else:
            kwargs = {
                "text_file": Path(args.text_file),
                "source_object_id": args.source_object_id,
                "derivation_kind": args.derivation_kind,
                "tool_name": args.tool_name,
                "tool_version": args.tool_version,
                "review_status": args.review_status,
                "model_name": args.model_name,
                "model_version": args.model_version,
                "confidence": args.confidence,
                "language": args.language,
                "born_digital": args.born_digital,
            }
            if args.dry_run:
                result = archive_services.derived_text_capture_dry_run(Path(args.archive_root), **kwargs)
            else:
                result = archive_services.derived_text_capture_apply(
                    Path(args.archive_root),
                    reviewed_by=args.reviewed_by,
                    **kwargs,
                )
    except (archive_services.ArchiveServiceError, OSError, json.JSONDecodeError) as exc:
        print(f"Derived text capture failed: {exc}", file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    elif args.from_manifest:
        for entry in result.get("items", []):
            state = entry.get("action") or entry.get("planned_action")
            print(f"{entry.get('item_id') or entry.get('manifest_line')}: {state}")
        summary = result.get("summary") or {}
        print("Summary: " + ", ".join(f"{key}={value}" for key, value in summary.items()))
        for blocker in result.get("blockers", []):
            print(f"BLOCKED: {blocker}")
        for warning in result.get("warnings", []):
            print(f"WARNING: {warning}")
    else:
        state = result.get("action") or result.get("planned_action")
        print(f"{result.get('derived_text_id') or '-'}: {state}")
        print(f"Source object: {result.get('source_object_id') or '-'}")
        print(f"Text path: {result.get('text_logical_key') or '-'}")
        for blocker in result.get("blockers", []):
            print(f"BLOCKED: {blocker}")
        for warning in result.get("warnings", []):
            print(f"WARNING: {warning}")
    return 0 if result.get("ok") else 1


def command_derive_text_coverage(args: argparse.Namespace) -> int:
    if not args.dry_run:
        print("Derived text coverage is read-only and requires --dry-run.", file=sys.stderr)
        return 1
    try:
        result = archive_services.derived_text_coverage(
            Path(args.archive_root),
            dry_run=True,
            max_items=args.max_items,
        )
    except (archive_services.ArchiveServiceError, OSError, json.JSONDecodeError) as exc:
        print(f"Derived text coverage failed: {exc}", file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        gate = result.get("coverage_gate") if isinstance(result.get("coverage_gate"), dict) else {}
        counts = result.get("manifest_counts") if isinstance(result.get("manifest_counts"), dict) else {}
        quality = result.get("manifest_quality") if isinstance(result.get("manifest_quality"), dict) else {}
        print(f"Derived text coverage {gate.get('status') or ('passed' if result.get('ok') else 'blocked')}.")
        print(f"Archive: {result.get('archive_id') or '-'}")
        print(f"Textual candidates: {gate.get('textual_candidate_count', 0)}")
        print(f"Covered: {gate.get('covered_textual_count', 0)}")
        print(f"Missing: {gate.get('missing_derived_text_count', 0)}")
        print(f"Encrypted/password required: {gate.get('needs_password_or_encrypted_count', 0)}")
        print(f"Manifest quality: {quality.get('status') or '-'} ({quality.get('records_with_issues_count', 0)} issue record(s))")
        print(f"By family: {counts.get('by_toolchain_family') or {}}")
        for item in result.get("missing_items", []):
            print(
                f"- missing {item.get('object_id')}: "
                f"{item.get('extension') or item.get('mime') or '-'} "
                f"via {item.get('suggested_route') or '-'}"
            )
        for blocker in result.get("blockers", []):
            print(f"BLOCKED: {blocker}")
        for warning in result.get("warnings", []):
            print(f"WARNING: {warning}")
    return 0 if result.get("ok") else 1


def command_derive_text_toolchain(args: argparse.Namespace) -> int:
    if not args.dry_run:
        print("Derived text toolchain is read-only and requires --dry-run.", file=sys.stderr)
        return 1
    try:
        result = archive_services.derived_text_toolchain(
            Path(args.archive_root),
            extension=args.extension,
            mime=args.mime,
            dry_run=True,
        )
    except (archive_services.ArchiveServiceError, OSError, json.JSONDecodeError) as exc:
        print(f"Derived text toolchain failed: {exc}", file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        toolchain = result.get("toolchain") if isinstance(result.get("toolchain"), dict) else {}
        print(f"Derived text toolchain: {toolchain.get('format_family') or '-'}")
        print(f"Route: {toolchain.get('extraction_route') or '-'}")
        print(f"Derivation kind: {toolchain.get('recommended_derivation_kind') or '-'}")
        print(f"Primary tools: {', '.join(toolchain.get('primary_tools') or []) or '-'}")
        print(f"Fallback tools: {', '.join(toolchain.get('fallback_tools') or []) or '-'}")
        for blocker in result.get("blockers", []):
            print(f"BLOCKED: {blocker}")
        for warning in result.get("warnings", []):
            print(f"WARNING: {warning}")
    return 0 if result.get("ok") else 1


def command_derive_text_agent_contract(args: argparse.Namespace) -> int:
    if not args.dry_run:
        print("Derived text agent contract is read-only and requires --dry-run.", file=sys.stderr)
        return 1
    try:
        result = archive_services.derived_text_agent_contract(
            Path(args.archive_root),
            dry_run=True,
        )
    except (archive_services.ArchiveServiceError, OSError, json.JSONDecodeError) as exc:
        print(f"Derived text agent contract failed: {exc}", file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        contract = result.get("agent_operating_contract") if isinstance(result.get("agent_operating_contract"), dict) else {}
        print(f"Derived text agent contract: {contract.get('default_posture') or '-'}")
        for rule in contract.get("rules", []):
            print(f"- {rule}")
        for blocker in result.get("blockers", []):
            print(f"BLOCKED: {blocker}")
    return 0 if result.get("ok") else 1


def command_derive_text_doctor(args: argparse.Namespace) -> int:
    if not args.dry_run:
        print("Derived text doctor is read-only and requires --dry-run.", file=sys.stderr)
        return 1
    try:
        result = archive_services.derived_text_toolchain_doctor(
            Path(args.archive_root),
            dry_run=True,
            tool_hints=Path(args.tool_hints) if args.tool_hints else None,
        )
    except (archive_services.ArchiveServiceError, OSError, json.JSONDecodeError) as exc:
        print(f"Derived text doctor failed: {exc}", file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        summary = result.get("readiness_summary") if isinstance(result.get("readiness_summary"), dict) else {}
        print("Derived text toolchain doctor.")
        print(f"Archive: {result.get('archive_id') or '-'}")
        print(f"Tools available: {summary.get('available_tool_count', 0)} / {summary.get('checked_tool_count', 0)}")
        print(f"Families ready: {summary.get('ready_family_count', 0)} / {summary.get('total_family_count', 0)}")
        for family in result.get("family_readiness", []):
            state = "ready" if family.get("ready") else "needs-tool"
            print(f"- {family.get('format_family')}: {state}")
        for blocker in result.get("blockers", []):
            print(f"BLOCKED: {blocker}")
        for warning in result.get("warnings", []):
            print(f"WARNING: {warning}")
    return 0 if result.get("ok") else 1


def command_import_external(args: argparse.Namespace) -> int:
    if args.dry_run and args.approve:
        print("Use either --dry-run or --approve, not both.", file=sys.stderr)
        return 1
    if not args.dry_run and not args.approve:
        print("External import requires --dry-run or --approve.", file=sys.stderr)
        return 1
    if args.approve and not args.reviewed_by:
        print("External import requires --reviewed-by when --approve is used.", file=sys.stderr)
        return 1

    try:
        if args.dry_run:
            result = archive_services.external_import_dry_run(
                Path(args.archive_root),
                Path(args.export),
                source_system=args.source,
                limit=args.limit,
                provider_locator_policy=args.provider_locator_policy,
            )
        else:
            result = archive_services.import_external_archive(
                Path(args.archive_root),
                Path(args.export),
                source_system=args.source,
                reviewed_by=args.reviewed_by,
                limit=args.limit,
                provider_locator_policy=args.provider_locator_policy,
            )
    except (archive_services.ArchiveServiceError, OSError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
        return 0 if result["ok"] else 1

    mode = "dry-run" if result["dry_run"] else "applied"
    state = "passed" if result["ok"] else "blocked"
    print(f"External import {mode} {state}.")
    print(f"Source: {result['source_system']}")
    print(f"Target archive: {result['target_archive']}")
    if result["dry_run"]:
        print(f"Items: {result['item_count']}")
        print(f"Proposed receipt path: {result['proposed_receipt_path']}")
    else:
        print(f"Imported: {result['imported_count']}")
        print(f"Receipt path: {result['receipt_path']}")
    if result.get("blockers"):
        print("Blockers:")
        for blocker in result["blockers"]:
            print(f"- {blocker}")
    if result.get("warnings"):
        print("Warnings:")
        for warning in result["warnings"]:
            print(f"- {warning}")
    return 0 if result["ok"] else 1


def command_share(args: argparse.Namespace) -> int:
    if not args.dry_run:
        print("Only --dry-run archive sharing is implemented. Real share/merge/fork is intentionally unavailable.", file=sys.stderr)
        return 1
    try:
        result = archive_services.share_archive_scope_dry_run(
            Path(args.archive_root),
            view_id=args.view,
            target_archive=args.target_archive,
            counterparty_id=args.counterparty_id,
            counterparty_fingerprint=args.counterparty_fingerprint,
            allow_sensitive=args.allow_sensitive,
        )
    except (archive_services.ArchiveServiceError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        state = "passed" if result["ok"] else "blocked"
        print(f"Archive share dry-run {state}.")
        print(f"Source archive: {result['source_archive']}")
        print(f"Target archive: {result['target_archive']}")
        print(f"View: {result['view_id']}")
        print(f"Included zettels: {len(result['scope_gate']['included'])}")
        print(f"Excluded zettels: {len(result['scope_gate']['excluded'])}")
        print(f"Trust gate: {result['trust_gate']['status']}")
        print(f"Proposed receipt path: {result['proposed_receipt_path']}")
        if result["blockers"]:
            print("Blockers:")
            for blocker in result["blockers"]:
                print(f"- {blocker}")
        if result["warnings"]:
            print("Warnings:")
            for warning in result["warnings"]:
                print(f"- {warning}")
    return 0 if result["ok"] else 1


def command_delegate_zet(args: argparse.Namespace) -> int:
    if args.dry_run and args.approve:
        print("Use either --dry-run or --approve, not both.", file=sys.stderr)
        return 1
    if not args.dry_run and not args.approve:
        print("zet delegation requires --dry-run or --approve. Use --dry-run to preview.", file=sys.stderr)
        return 1
    if args.approve and not args.reviewed_by:
        print("Real zet delegation requires --reviewed-by.", file=sys.stderr)
        return 1
    try:
        if args.dry_run:
            result = archive_services.delegate_zets_dry_run(
                Path(args.archive_root),
                view_id=args.view,
                target_archive=args.target_archive,
                counterparty_id=args.counterparty_id,
                counterparty_fingerprint=args.counterparty_fingerprint,
                allow_sensitive=args.allow_sensitive,
                target_policy=args.target_policy,
            )
        else:
            result = archive_services.delegate_zets(
                Path(args.archive_root),
                view_id=args.view,
                target_archive=args.target_archive,
                counterparty_id=args.counterparty_id,
                counterparty_fingerprint=args.counterparty_fingerprint,
                allow_sensitive=args.allow_sensitive,
                target_policy=args.target_policy,
                reviewed_by=args.reviewed_by,
            )
    except (archive_services.ArchiveServiceError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        if result["dry_run"]:
            state = "passed" if result["ok"] else "blocked"
            print(f"zet delegate dry-run {state}.")
        else:
            print("zet delegate receipt written.")
        print(f"Source archive: {result['source_archive']}")
        print(f"Target policy: {result['target_policy']}")
        print(f"Target archive: {result['target_archive'] or '<deferred until attestation>'}")
        print(f"View: {result['view_id']}")
        print(f"Delegated zets: {len(result['delegated_zets'])}")
        if result["dry_run"]:
            print(f"Trust gate: {result['trust_gate']['status']}")
            print(f"Proposed delegate receipt path: {result['proposed_delegate_receipt_path']}")
        else:
            print(f"Delegate receipt path: {result['delegate_receipt_path']}")
            print(f"Reviewed by: {result['reviewed_by']}")
        if result["blockers"]:
            print("Blockers:")
            for blocker in result["blockers"]:
                print(f"- {blocker}")
        if result["warnings"]:
            print("Warnings:")
            for warning in result["warnings"]:
                print(f"- {warning}")
    return 0 if result["ok"] else 1


def command_attest_zet(args: argparse.Namespace) -> int:
    if not args.dry_run:
        print("Only --dry-run zet attestation is implemented. Real attestation writes are intentionally unavailable.", file=sys.stderr)
        return 1
    try:
        result = archive_services.attest_zets_dry_run(
            Path(args.archive_root),
            delegate_receipt_path=args.delegate_receipt,
            counterparty_id=args.counterparty_id,
            counterparty_fingerprint=args.counterparty_fingerprint,
        )
    except (archive_services.ArchiveServiceError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        state = "passed" if result["ok"] else "blocked"
        print(f"zet attest dry-run {state}.")
        print(f"Archive: {result['archive_id']}")
        print(f"Source archive: {result['source_archive']}")
        print(f"Delegated zets: {len(result['delegated_zets'])}")
        print(f"Trust gate: {result['trust_gate']['status']}")
        print(f"Proposed attestation receipt path: {result['proposed_attestation_receipt_path']}")
        if result["blockers"]:
            print("Blockers:")
            for blocker in result["blockers"]:
                print(f"- {blocker}")
        if result["warnings"]:
            print("Warnings:")
            for warning in result["warnings"]:
                print(f"- {warning}")
    return 0 if result["ok"] else 1


def command_anchor_zet(args: argparse.Namespace) -> int:
    if not args.dry_run:
        print("Only --dry-run zet anchoring is implemented. Real anchor writes are intentionally unavailable.", file=sys.stderr)
        return 1
    try:
        result = archive_services.anchor_zets_dry_run(
            Path(args.archive_root),
            attestation_receipt_path=args.attestation_receipt,
        )
    except (archive_services.ArchiveServiceError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        state = "passed" if result["ok"] else "blocked"
        print(f"zet anchor dry-run {state}.")
        print(f"Archive: {result['archive_id']}")
        print(f"Source archive: {result['source_archive']}")
        print(f"Anchored zets: {len(result['anchored_zets'])}")
        print(f"Proposed anchor metadata path: {result['proposed_anchor_metadata_path']}")
        if result["blockers"]:
            print("Blockers:")
            for blocker in result["blockers"]:
                print(f"- {blocker}")
        if result["warnings"]:
            print("Warnings:")
            for warning in result["warnings"]:
                print(f"- {warning}")
    return 0 if result["ok"] else 1


def command_check_safe_html(args: argparse.Namespace) -> int:
    if not args.dry_run:
        print(
            "check-safe-html is a read-only dry-run validator and requires --dry-run. "
            "It never writes files.",
            file=sys.stderr,
        )
        return 1
    try:
        result = archive_services.check_safe_html_dry_run(
            Path(args.archive_root),
            relative_path=args.path,
        )
    except (archive_services.ArchiveServiceError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        state = "passed" if result["ok"] else "blocked"
        print(f"WOM Safe HTML check dry-run {state}.")
        print(f"Archive: {result['archive_id']}")
        print(f"Source path: {result['source_path']}")
        print(f"Detected format: {result['detected_format']}")
        print(f"Proposed profile: {result['proposed_profile']}")
        if result["blockers"]:
            print("Blockers:")
            for blocker in result["blockers"]:
                print(f"- {blocker}")
        if result["warnings"]:
            print("Warnings:")
            for warning in result["warnings"]:
                print(f"- {warning}")
    return 0 if result["ok"] else 1


def command_prompt_boundary(args: argparse.Namespace) -> int:
    if not args.dry_run:
        print("prompt-boundary is read-only and requires --dry-run.", file=sys.stderr)
        return 1
    try:
        result = archive_services.prompt_boundary_check(
            Path(args.archive_root),
            text=args.text,
            relative_path=args.path,
            dry_run=args.dry_run,
        )
    except (archive_services.ArchiveServiceError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print_json(result)
    return 0 if result["ok"] else 1


def command_providers(args: argparse.Namespace) -> int:
    try:
        result = archive_services.provider_bindings_summary(Path(args.archive_root))
    except (archive_services.ArchiveServiceError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        print(f"Provider bindings for {result['archive_id']}: {result['binding_count']} configured.")
        print(f"Path: {result['provider_bindings_path']}")
        print(f"External changes: {result['provider_change_plan']['status']}")
        for provider in result["providers"]:
            state = "enabled" if provider["enabled"] else "disabled"
            print(f"- {provider['provider']} ({state}): {provider['binding_id']}")
    return 0


def command_provider_status(args: argparse.Namespace) -> int:
    if not args.dry_run:
        print("provider-status is read-only and requires --dry-run.", file=sys.stderr)
        return 1

    try:
        result = archive_services.provider_setup_status(Path(args.archive_root))
    except (archive_services.ArchiveServiceError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        state = "passed" if result["ok"] else "blocked"
        print(f"Provider setup status dry-run {state}.")
        print(f"Archive: {result['archive_id']}")
        print(f"Status: {result['status']}")
        print(f"Bindings checked: {result['checked_binding_count']} of {result['binding_count']}")
        print(f"Receipts: {result['receipt_count']} in {result['receipt_dir']}")
        for provider in result["providers"]:
            marker = provider.get("receipt_path") or provider.get("expected_receipt_path") or "-"
            print(f"- {provider['provider']}: {provider['status']} ({marker})")
        for orphan in result["orphan_receipts"]:
            print(f"- receipt: {orphan['status']} ({orphan['receipt_path']})")
        if result.get("blockers"):
            print("Blockers:")
            for blocker in result["blockers"]:
                print(f"- {blocker}")
        if result.get("warnings"):
            print("Warnings:")
            for warning in result["warnings"]:
                print(f"- {warning}")
    return 0 if result["ok"] else 1


def command_object_storage_adapter_readiness_plan(args: argparse.Namespace) -> int:
    if not args.dry_run:
        print("object-storage-adapter-readiness-plan is read-only and requires --dry-run.", file=sys.stderr)
        return 1
    try:
        result = archive_services.object_storage_adapter_readiness_plan(
            Path(args.archive_root),
            operation=args.operation,
            provider_ref=args.provider_ref,
            dry_run=True,
        )
    except (archive_services.ArchiveServiceError, OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        state = "passed" if result.get("ok") else "blocked"
        summary = result.get("provider_summary") if isinstance(result.get("provider_summary"), dict) else {}
        print(f"Object storage adapter readiness dry-run {state}.")
        print(f"Archive: {result.get('archive_id') or '-'}")
        print(f"Readiness: {result.get('readiness_state') or '-'}")
        print(f"Operation: {result.get('operation') or '-'}")
        print(f"Object-storage bindings: {summary.get('setup_managed_object_storage_count', 0)}")
        print(f"Selected provider kind: {summary.get('selected_provider_kind') or '-'}")
        print(f"Selected provider setup ready: {summary.get('selected_provider_setup_ready')}")
        print("Provider API called: no")
        print("Writes: none")
        if result.get("blockers"):
            print("Blockers:")
            for blocker in result["blockers"]:
                print(f"- {blocker}")
        if result.get("warnings"):
            print("Warnings:")
            for warning in result["warnings"]:
                print(f"- {warning}")
    return 0 if result.get("ok", True) else 1


def command_imap_mailbox_adapter_readiness_plan(args: argparse.Namespace) -> int:
    if not args.dry_run:
        print("imap-mailbox-adapter-readiness-plan is read-only and requires --dry-run.", file=sys.stderr)
        return 1
    try:
        result = archive_services.imap_mailbox_adapter_readiness_plan(
            Path(args.archive_root),
            source_id=args.source_id,
            adapter_id=args.adapter_id,
            provider=args.provider,
            imap_host=args.imap_host,
            imap_port=args.imap_port,
            account_ref=args.account_ref,
            username_ref=args.username_ref,
            auth_mode=args.auth_mode,
            app_password_ref=args.app_password_ref,
            oauth_token_ref=args.oauth_token_ref,
            mailbox_ref=args.mailbox_ref,
            operation=args.operation,
            max_messages=args.max_messages,
            since_days=args.since_days,
            credential_id=args.credential_id,
            credential_ref=args.credential_ref,
            credential_kind=args.credential_kind,
            credential_provider=args.credential_provider,
            store_kind=args.store_kind,
            adapter_kind=args.adapter_kind,
            approval_decision=args.approval_decision,
            approval_receipt=args.approval_receipt,
            consumer=args.consumer,
            reviewed_by=args.reviewed_by,
            platform=args.platform,
            dry_run=True,
        )
    except (archive_services.ArchiveServiceError, OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        state = "passed" if result.get("ok") else "blocked"
        request = result.get("request_package_summary") if isinstance(result.get("request_package_summary"), dict) else {}
        runtime = result.get("runtime_summary") if isinstance(result.get("runtime_summary"), dict) else {}
        print(f"IMAP mailbox adapter readiness dry-run {state}.")
        print(f"Archive: {result.get('archive_id') or '-'}")
        print(f"Readiness: {result.get('readiness_state') or '-'}")
        print(f"Source: {result.get('source_id') or '-'}")
        print(f"Provider: {result.get('provider') or '-'}")
        print(f"Operation: {result.get('operation') or '-'}")
        print(f"Request package: {request.get('request_state') or '-'}")
        manifest = result.get("adapter_manifest_summary") if isinstance(result.get("adapter_manifest_summary"), dict) else {}
        print(f"Adapter manifest: {manifest.get('status') or '-'}")
        print(f"Missing runtime modules: {runtime.get('missing_module_count', 0)}")
        print("IMAP connection opened: no")
        print("Writes: none")
        if result.get("blockers"):
            print("Blockers:")
            for blocker in result["blockers"]:
                print(f"- {blocker}")
        if result.get("warnings"):
            print("Warnings:")
            for warning in result["warnings"]:
                print(f"- {warning}")
    return 0 if result.get("ok", True) else 1


def command_imap_mailbox_selection_plan(args: argparse.Namespace) -> int:
    if not args.dry_run:
        print("imap-mailbox-selection-plan is read-only and requires --dry-run.", file=sys.stderr)
        return 1
    try:
        result = archive_services.imap_mailbox_selection_plan(
            Path(args.archive_root),
            source_id=args.source_id,
            provider=args.provider,
            imap_host=args.imap_host,
            imap_port=args.imap_port,
            account_ref=args.account_ref,
            username_ref=args.username_ref,
            auth_mode=args.auth_mode,
            app_password_ref=args.app_password_ref,
            oauth_token_ref=args.oauth_token_ref,
            mailbox_ref=args.mailbox_ref,
            operation=args.operation,
            selection_rule=args.selection_rule,
            selector_id=args.selector_id,
            max_messages=args.max_messages,
            since_days=args.since_days,
            credential_id=args.credential_id,
            credential_ref=args.credential_ref,
            credential_kind=args.credential_kind,
            credential_provider=args.credential_provider,
            store_kind=args.store_kind,
            adapter_kind=args.adapter_kind,
            approval_decision=args.approval_decision,
            approval_receipt=args.approval_receipt,
            consumer=args.consumer,
            reviewed_by=args.reviewed_by,
            platform=args.platform,
            dry_run=True,
        )
    except (archive_services.ArchiveServiceError, OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        state = "passed" if result.get("ok") else "blocked"
        request = result.get("request_package_summary") if isinstance(result.get("request_package_summary"), dict) else {}
        selector = result.get("selector_plan") if isinstance(result.get("selector_plan"), dict) else {}
        print(f"IMAP mailbox selection dry-run {state}.")
        print(f"Archive: {result.get('archive_id') or '-'}")
        print(f"Selection: {result.get('selection_state') or '-'}")
        print(f"Source: {result.get('source_id') or '-'}")
        print(f"Provider: {result.get('provider') or '-'}")
        print(f"Operation: {result.get('operation') or '-'}")
        print(f"Request package: {request.get('request_state') or '-'}")
        print(f"Selection rule: {selector.get('selection_rule') or '-'}")
        print("Mailbox selected: no")
        print("Messages listed: no")
        print("Writes: none")
        if result.get("blockers"):
            print("Blockers:")
            for blocker in result["blockers"]:
                print(f"- {blocker}")
        if result.get("warnings"):
            print("Warnings:")
            for warning in result["warnings"]:
                print(f"- {warning}")
    return 0 if result.get("ok", True) else 1


def command_imap_mailbox_adapter_audit_plan(args: argparse.Namespace) -> int:
    if not args.dry_run:
        print("imap-mailbox-adapter-audit-plan is read-only and requires --dry-run.", file=sys.stderr)
        return 1
    try:
        result = archive_services.imap_mailbox_adapter_audit_plan(
            Path(args.archive_root),
            adapter_id=args.adapter_id,
            source_id=args.source_id,
            provider=args.provider,
            imap_host=args.imap_host,
            imap_port=args.imap_port,
            account_ref=args.account_ref,
            username_ref=args.username_ref,
            auth_mode=args.auth_mode,
            app_password_ref=args.app_password_ref,
            oauth_token_ref=args.oauth_token_ref,
            mailbox_ref=args.mailbox_ref,
            operation=args.operation,
            selection_rule=args.selection_rule,
            selector_id=args.selector_id,
            max_messages=args.max_messages,
            since_days=args.since_days,
            credential_id=args.credential_id,
            credential_ref=args.credential_ref,
            credential_kind=args.credential_kind,
            credential_provider=args.credential_provider,
            store_kind=args.store_kind,
            adapter_kind=args.adapter_kind,
            approval_decision=args.approval_decision,
            approval_receipt=args.approval_receipt,
            consumer=args.consumer,
            reviewed_by=args.reviewed_by,
            platform=args.platform,
            result_status=args.result_status,
            dry_run=True,
        )
    except (archive_services.ArchiveServiceError, OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        state = result.get("audit_state") or ("passed" if result.get("ok") else "blocked")
        receipt = result.get("receipt_preview") if isinstance(result.get("receipt_preview"), dict) else {}
        adapter = receipt.get("adapter") if isinstance(receipt.get("adapter"), dict) else {}
        operation = receipt.get("operation") if isinstance(receipt.get("operation"), dict) else {}
        print(f"IMAP mailbox adapter audit plan {state}.")
        print(f"Archive: {result.get('archive_id') or '-'}")
        print(f"Adapter: {adapter.get('adapter_id') or '-'} ({adapter.get('adapter_kind') or '-'})")
        print(f"Receipt: {result.get('proposed_receipt_path') or '-'}")
        print(f"Result status: {receipt.get('result_status') or '-'}")
        print(f"Operation: {operation.get('operation') or '-'}")
        print("Live adapter executed: no")
        print("Messages listed: no")
        print("Writes: none")
        if result.get("blockers"):
            print("Blockers:")
            for blocker in result["blockers"]:
                print(f"- {blocker}")
        if result.get("warnings"):
            print("Warnings:")
            for warning in result["warnings"]:
                print(f"- {warning}")
    return 0 if result.get("ok", True) else 1


def command_imap_mailbox_adapter_audit_write(args: argparse.Namespace) -> int:
    if args.dry_run == args.approve:
        print("Choose exactly one mode: --dry-run or --approve.", file=sys.stderr)
        return 1
    try:
        result = archive_services.imap_mailbox_adapter_audit_write(
            Path(args.archive_root),
            adapter_id=args.adapter_id,
            source_id=args.source_id,
            provider=args.provider,
            imap_host=args.imap_host,
            imap_port=args.imap_port,
            account_ref=args.account_ref,
            username_ref=args.username_ref,
            auth_mode=args.auth_mode,
            app_password_ref=args.app_password_ref,
            oauth_token_ref=args.oauth_token_ref,
            mailbox_ref=args.mailbox_ref,
            operation=args.operation,
            selection_rule=args.selection_rule,
            selector_id=args.selector_id,
            max_messages=args.max_messages,
            since_days=args.since_days,
            credential_id=args.credential_id,
            credential_ref=args.credential_ref,
            credential_kind=args.credential_kind,
            credential_provider=args.credential_provider,
            store_kind=args.store_kind,
            adapter_kind=args.adapter_kind,
            approval_decision=args.approval_decision,
            approval_receipt=args.approval_receipt,
            result_status=args.result_status,
            consumer=args.consumer,
            reviewed_by=args.reviewed_by,
            platform=args.platform,
            dry_run=args.dry_run,
            approve=args.approve,
        )
    except (archive_services.ArchiveServiceError, OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        state = "written" if result.get("approved") else ("passed" if result.get("ok") else "blocked")
        receipt = result.get("receipt_preview") if isinstance(result.get("receipt_preview"), dict) else {}
        print(f"IMAP mailbox adapter audit write {state}.")
        print(f"Archive: {result.get('archive_id') or '-'}")
        print(f"Adapter: {(receipt.get('adapter') or {}).get('adapter_id') or '-'}")
        print(f"Result: {receipt.get('result_status') or '-'}")
        print(f"Receipt: {result.get('receipt_path') or result.get('proposed_receipt_path') or '-'}")
        print("IMAP connection opened: no")
        print("Mail read: no")
        writes = result.get("files_written") or []
        if writes:
            print("Files written:")
            for path in writes:
                print(f"- {path}")
        else:
            print("Writes: none")
        if result.get("blockers"):
            print("Blockers:")
            for blocker in result["blockers"]:
                print(f"- {blocker}")
        if result.get("warnings"):
            print("Warnings:")
            for warning in result["warnings"]:
                print(f"- {warning}")
    return 0 if result.get("ok", True) else 1


def command_imap_mailbox_adapter_preflight_plan(args: argparse.Namespace) -> int:
    if not args.dry_run:
        print("imap-mailbox-adapter-preflight-plan is read-only and requires --dry-run.", file=sys.stderr)
        return 1
    try:
        result = archive_services.imap_mailbox_adapter_preflight_plan(
            Path(args.archive_root),
            adapter_id=args.adapter_id,
            source_id=args.source_id,
            provider=args.provider,
            imap_host=args.imap_host,
            imap_port=args.imap_port,
            account_ref=args.account_ref,
            username_ref=args.username_ref,
            auth_mode=args.auth_mode,
            app_password_ref=args.app_password_ref,
            oauth_token_ref=args.oauth_token_ref,
            mailbox_ref=args.mailbox_ref,
            operation=args.operation,
            selection_rule=args.selection_rule,
            selector_id=args.selector_id,
            max_messages=args.max_messages,
            since_days=args.since_days,
            credential_id=args.credential_id,
            credential_ref=args.credential_ref,
            credential_kind=args.credential_kind,
            credential_provider=args.credential_provider,
            store_kind=args.store_kind,
            adapter_kind=args.adapter_kind,
            approval_decision=args.approval_decision,
            approval_receipt=args.approval_receipt,
            consumer=args.consumer,
            reviewed_by=args.reviewed_by,
            platform=args.platform,
            dry_run=True,
        )
    except (archive_services.ArchiveServiceError, OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        gate = result.get("gate_summary") if isinstance(result.get("gate_summary"), dict) else {}
        manifest = result.get("adapter_manifest_summary") if isinstance(result.get("adapter_manifest_summary"), dict) else {}
        print(f"IMAP mailbox adapter preflight {result.get('preflight_state') or '-'}.")
        print(f"Archive: {result.get('archive_id') or '-'}")
        print(f"Source: {result.get('source_id') or '-'}")
        print(f"Provider: {result.get('provider') or '-'}")
        print(f"Operation: {result.get('operation') or '-'}")
        print(f"Request package: {gate.get('request_state') or '-'}")
        print(f"Selection: {gate.get('selection_state') or '-'}")
        print(f"Adapter manifest: {manifest.get('status') or '-'}")
        print(f"Audit preview: {gate.get('audit_state') or '-'}")
        print("Live adapter executed: no")
        print("Mail read: no")
        print("Writes: none")
        if result.get("blockers"):
            print("Blockers:")
            for blocker in result["blockers"]:
                print(f"- {blocker}")
        if result.get("warnings"):
            print("Warnings:")
            for warning in result["warnings"]:
                print(f"- {warning}")
    return 0 if result.get("ok", True) else 1


def command_imap_mailbox_adapter_execution_contract(args: argparse.Namespace) -> int:
    if not args.dry_run:
        print("imap-mailbox-adapter-execution-contract is read-only and requires --dry-run.", file=sys.stderr)
        return 1
    try:
        result = archive_services.imap_mailbox_adapter_execution_contract(
            Path(args.archive_root),
            adapter_id=args.adapter_id,
            source_id=args.source_id,
            provider=args.provider,
            imap_host=args.imap_host,
            imap_port=args.imap_port,
            account_ref=args.account_ref,
            username_ref=args.username_ref,
            auth_mode=args.auth_mode,
            app_password_ref=args.app_password_ref,
            oauth_token_ref=args.oauth_token_ref,
            mailbox_ref=args.mailbox_ref,
            operation=args.operation,
            selection_rule=args.selection_rule,
            selector_id=args.selector_id,
            max_messages=args.max_messages,
            since_days=args.since_days,
            credential_id=args.credential_id,
            credential_ref=args.credential_ref,
            credential_kind=args.credential_kind,
            credential_provider=args.credential_provider,
            store_kind=args.store_kind,
            adapter_kind=args.adapter_kind,
            approval_decision=args.approval_decision,
            approval_receipt=args.approval_receipt,
            consumer=args.consumer,
            reviewed_by=args.reviewed_by,
            platform=args.platform,
            execution_mode=args.execution_mode,
            dry_run=True,
        )
    except (archive_services.ArchiveServiceError, OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        preflight = result.get("preflight_summary") if isinstance(result.get("preflight_summary"), dict) else {}
        receipt = result.get("receipt_contract") if isinstance(result.get("receipt_contract"), dict) else {}
        print(f"IMAP mailbox adapter execution contract {result.get('contract_state') or '-'}.")
        print(f"Archive: {result.get('archive_id') or '-'}")
        print(f"Source: {result.get('source_id') or '-'}")
        print(f"Provider: {result.get('provider') or '-'}")
        print(f"Operation: {result.get('operation') or '-'}")
        print(f"Preflight: {preflight.get('preflight_state') or '-'}")
        print(f"Receipt: {receipt.get('proposed_receipt_path') or '-'}")
        print("Live adapter executed: no")
        print("Mail read: no")
        print("Writes: none")
        if result.get("blockers"):
            print("Blockers:")
            for blocker in result["blockers"]:
                print(f"- {blocker}")
        if result.get("warnings"):
            print("Warnings:")
            for warning in result["warnings"]:
                print(f"- {warning}")
    return 0 if result.get("ok", True) else 1


def command_imap_mailbox_header_metadata_scan(args: argparse.Namespace) -> int:
    if args.dry_run == args.approve:
        print("Choose exactly one mode: --dry-run or --approve.", file=sys.stderr)
        return 1
    try:
        result = archive_services.imap_mailbox_header_metadata_scan(
            Path(args.archive_root),
            adapter_id=args.adapter_id,
            source_id=args.source_id,
            provider=args.provider,
            imap_host=args.imap_host,
            imap_port=args.imap_port,
            account_ref=args.account_ref,
            username_ref=args.username_ref,
            auth_mode=args.auth_mode,
            app_password_ref=args.app_password_ref,
            oauth_token_ref=args.oauth_token_ref,
            mailbox_ref=args.mailbox_ref,
            operation=args.operation,
            selection_rule=args.selection_rule,
            selector_id=args.selector_id,
            max_messages=args.max_messages,
            since_days=args.since_days,
            credential_id=args.credential_id,
            credential_ref=args.credential_ref,
            credential_kind=args.credential_kind,
            credential_provider=args.credential_provider,
            store_kind=args.store_kind,
            adapter_kind=args.adapter_kind,
            approval_decision=args.approval_decision,
            approval_receipt=args.approval_receipt,
            consumer=args.consumer,
            reviewed_by=args.reviewed_by,
            platform=args.platform,
            timeout_seconds=args.timeout_seconds,
            dry_run=args.dry_run,
            approve=args.approve,
        )
    except (archive_services.ArchiveServiceError, OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        scan = result.get("scan_summary") if isinstance(result.get("scan_summary"), dict) else {}
        receipt = result.get("receipt") if isinstance(result.get("receipt"), dict) else {}
        print(f"IMAP mailbox header metadata scan {result.get('execution_status') or '-'}.")
        print(f"Archive: {result.get('archive_id') or '-'}")
        print(f"Source: {result.get('source_id') or '-'}")
        print(f"Provider: {result.get('provider') or '-'}")
        print(f"Candidates: {scan.get('candidate_count') or 0}")
        print(f"Headers fetched: {scan.get('headers_fetched_count') or 0}")
        print(f"Receipt: {receipt.get('receipt_path') or receipt.get('proposed_receipt_path') or '-'}")
        print("Message bodies read: no")
        print("Attachments read: no")
        writes = result.get("files_written") or []
        if writes:
            print("Files written:")
            for path in writes:
                print(f"- {path}")
        else:
            print("Writes: none")
        if result.get("blockers"):
            print("Blockers:")
            for blocker in result["blockers"]:
                print(f"- {blocker}")
        if result.get("warnings"):
            print("Warnings:")
            for warning in result["warnings"]:
                print(f"- {warning}")
    return 0 if result.get("ok", True) else 1


def command_imap_mailbox_header_scan_receipt_audit(args: argparse.Namespace) -> int:
    if args.dry_run == args.approve:
        print("Choose exactly one mode: --dry-run or --approve.", file=sys.stderr)
        return 1
    try:
        result = archive_services.imap_mailbox_header_scan_receipt_audit(
            Path(args.archive_root),
            execution_receipt=args.execution_receipt,
            reviewed_by=args.reviewed_by,
            dry_run=args.dry_run,
            approve=args.approve,
        )
    except (archive_services.ArchiveServiceError, OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        summary = result.get("execution_receipt_summary") if isinstance(result.get("execution_receipt_summary"), dict) else {}
        print(f"IMAP header scan receipt audit {result.get('audit_state') or '-'}.")
        print(f"Archive: {result.get('archive_id') or '-'}")
        print(f"Execution status: {summary.get('execution_status') or '-'}")
        print(f"Candidates: {summary.get('candidate_count') or 0}")
        print(f"Headers fetched: {summary.get('headers_fetched_count') or 0}")
        print(f"Audit receipt: {result.get('audit_receipt_path') or result.get('proposed_audit_receipt_path') or '-'}")
        print("IMAP connection opened: no")
        print("Secrets read: no")
        writes = result.get("files_written") or []
        if writes:
            print("Files written:")
            for path in writes:
                print(f"- {path}")
        else:
            print("Writes: none")
        if result.get("blockers"):
            print("Blockers:")
            for blocker in result["blockers"]:
                print(f"- {blocker}")
        if result.get("warnings"):
            print("Warnings:")
            for warning in result["warnings"]:
                print(f"- {warning}")
    return 0 if result.get("ok", True) else 1


def command_imap_mailbox_material_selection_plan(args: argparse.Namespace) -> int:
    if not args.dry_run:
        print("imap-mailbox-material-selection-plan is read-only and requires --dry-run.", file=sys.stderr)
        return 1
    try:
        result = archive_services.imap_mailbox_material_selection_plan(
            Path(args.archive_root),
            execution_receipt=args.execution_receipt,
            selection_mode=args.selection_mode,
            dry_run=True,
        )
    except (archive_services.ArchiveServiceError, OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        summary = result.get("execution_receipt_summary") if isinstance(result.get("execution_receipt_summary"), dict) else {}
        queue = result.get("selection_queue") if isinstance(result.get("selection_queue"), dict) else {}
        scope = result.get("future_material_scope") if isinstance(result.get("future_material_scope"), dict) else {}
        print(f"IMAP mailbox material selection plan {result.get('plan_state') or '-'}.")
        print(f"Archive: {result.get('archive_id') or '-'}")
        print(f"Selection mode: {result.get('selection_mode') or '-'}")
        print(f"Execution status: {summary.get('execution_status') or '-'}")
        print(f"Candidate pool: {queue.get('candidate_pool_count') or 0}")
        print("Execution receipt path echoed: no")
        print("Candidate refs echoed: no")
        print(f"Future body capture requested: {'yes' if scope.get('body_capture_requested') else 'no'}")
        print(f"Future attachment capture requested: {'yes' if scope.get('attachment_capture_requested') else 'no'}")
        print(f"Future derived text requested: {'yes' if scope.get('derived_text_capture_requested') else 'no'}")
        print("Message bodies read now: no")
        print("Attachments read now: no")
        print("Writes: none")
        if result.get("blockers"):
            print("Blockers:")
            for blocker in result["blockers"]:
                print(f"- {blocker}")
        if result.get("warnings"):
            print("Warnings:")
            for warning in result["warnings"]:
                print(f"- {warning}")
    return 0 if result.get("ok", True) else 1


def command_imap_mailbox_material_selection_record(args: argparse.Namespace) -> int:
    if args.dry_run == args.approve:
        print("Choose exactly one mode: --dry-run or --approve.", file=sys.stderr)
        return 1
    try:
        result = archive_services.imap_mailbox_material_selection_record(
            Path(args.archive_root),
            execution_receipt=args.execution_receipt,
            selection_mode=args.selection_mode,
            selected_indexes=args.selected_index,
            reviewed_by=args.reviewed_by,
            dry_run=args.dry_run,
            approve=args.approve,
        )
    except (archive_services.ArchiveServiceError, OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        summary = result.get("selection_summary") if isinstance(result.get("selection_summary"), dict) else {}
        material_record = (
            result.get("material_selection_record")
            if isinstance(result.get("material_selection_record"), dict)
            else {}
        )
        scope = result.get("future_material_scope") if isinstance(result.get("future_material_scope"), dict) else {}
        print(f"IMAP mailbox material selection record {result.get('record_state') or '-'}.")
        print(f"Archive: {result.get('archive_id') or '-'}")
        print(f"Selection mode: {result.get('selection_mode') or '-'}")
        print(f"Selected count: {summary.get('selected_count') or 0}")
        print(f"Candidate pool: {summary.get('candidate_pool_count') or 0}")
        print(f"Receipt: {material_record.get('receipt_path') or material_record.get('proposed_receipt_path') or '-'}")
        print("Execution receipt path echoed: no")
        print("Candidate refs echoed: no")
        print(f"Future body capture requested: {'yes' if scope.get('body_capture_requested') else 'no'}")
        print(f"Future attachment capture requested: {'yes' if scope.get('attachment_capture_requested') else 'no'}")
        print(f"Future derived text requested: {'yes' if scope.get('derived_text_capture_requested') else 'no'}")
        print("Message bodies read now: no")
        print("Attachments read now: no")
        writes = result.get("files_written") or []
        if writes:
            print("Files written:")
            for path in writes:
                print(f"- {path}")
        else:
            print("Writes: none")
        if result.get("blockers"):
            print("Blockers:")
            for blocker in result["blockers"]:
                print(f"- {blocker}")
        if result.get("warnings"):
            print("Warnings:")
            for warning in result["warnings"]:
                print(f"- {warning}")
    return 0 if result.get("ok", True) else 1


def command_imap_mailbox_material_capture_request_plan(args: argparse.Namespace) -> int:
    if not args.dry_run:
        print("imap-mailbox-material-capture-request-plan is read-only and requires --dry-run.", file=sys.stderr)
        return 1
    try:
        result = archive_services.imap_mailbox_material_capture_request_plan(
            Path(args.archive_root),
            material_selection_receipt=args.material_selection_receipt,
            capture_action=args.capture_action,
            dry_run=True,
        )
    except (archive_services.ArchiveServiceError, OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        summary = (
            result.get("material_selection_summary")
            if isinstance(result.get("material_selection_summary"), dict)
            else {}
        )
        request = result.get("capture_request") if isinstance(result.get("capture_request"), dict) else {}
        print(f"IMAP mailbox material capture request plan {result.get('request_state') or '-'}.")
        print(f"Archive: {result.get('archive_id') or '-'}")
        print(f"Capture action: {result.get('capture_action') or '-'}")
        print(f"Selection mode: {summary.get('selection_mode') or '-'}")
        print(f"Selected count: {summary.get('selected_count') or 0}")
        print(f"Candidate pool: {summary.get('candidate_pool_count') or 0}")
        print("Material selection receipt path echoed: no")
        print("Execution receipt path echoed: no")
        print("Candidate refs echoed: no")
        print(f"Requires future approval: {'yes' if request.get('requires_separate_execution_approval') else 'no'}")
        print("Message material read now: no")
        print("Writes: none")
        if result.get("blockers"):
            print("Blockers:")
            for blocker in result["blockers"]:
                print(f"- {blocker}")
        if result.get("warnings"):
            print("Warnings:")
            for warning in result["warnings"]:
                print(f"- {warning}")
    return 0 if result.get("ok", True) else 1


def command_imap_mailbox_material_capture_execution_contract(args: argparse.Namespace) -> int:
    if not args.dry_run:
        print("imap-mailbox-material-capture-execution-contract is read-only and requires --dry-run.", file=sys.stderr)
        return 1
    try:
        result = archive_services.imap_mailbox_material_capture_execution_contract(
            Path(args.archive_root),
            material_selection_receipt=args.material_selection_receipt,
            capture_action=args.capture_action,
            dry_run=True,
        )
    except (archive_services.ArchiveServiceError, OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        summary = (
            result.get("material_selection_summary")
            if isinstance(result.get("material_selection_summary"), dict)
            else {}
        )
        request = result.get("request_summary") if isinstance(result.get("request_summary"), dict) else {}
        contract = (
            result.get("future_adapter_contract")
            if isinstance(result.get("future_adapter_contract"), dict)
            else {}
        )
        allowed = (
            contract.get("allowed_actions_after_implementation_and_approval")
            if isinstance(contract.get("allowed_actions_after_implementation_and_approval"), dict)
            else {}
        )
        print(f"IMAP mailbox material capture execution contract {result.get('contract_state') or '-'}.")
        print(f"Archive: {result.get('archive_id') or '-'}")
        print(f"Capture action: {result.get('capture_action') or '-'}")
        print(f"Selection mode: {summary.get('selection_mode') or '-'}")
        print(f"Selected count: {request.get('selected_count') or 0}")
        print(f"Future execution mode: {contract.get('execution_mode') or '-'}")
        print("Material selection receipt path echoed: no")
        print("Execution receipt path echoed: no")
        print("Candidate refs echoed: no")
        print(f"Future body read allowed after approval: {'yes' if allowed.get('read_selected_message_bodies') else 'no'}")
        print(f"Future attachment read allowed after approval: {'yes' if allowed.get('read_selected_attachments') else 'no'}")
        print(f"Future derived text allowed after approval: {'yes' if allowed.get('create_mail_derived_text') else 'no'}")
        print("Message material read now: no")
        print("Writes: none")
        if result.get("blockers"):
            print("Blockers:")
            for blocker in result["blockers"]:
                print(f"- {blocker}")
        if result.get("warnings"):
            print("Warnings:")
            for warning in result["warnings"]:
                print(f"- {warning}")
    return 0 if result.get("ok", True) else 1


def command_imap_mailbox_material_capture_approval_plan(args: argparse.Namespace) -> int:
    if args.dry_run == args.approve:
        print("Choose exactly one mode: --dry-run or --approve.", file=sys.stderr)
        return 1
    try:
        result = archive_services.imap_mailbox_material_capture_approval_plan(
            Path(args.archive_root),
            material_selection_receipt=args.material_selection_receipt,
            capture_action=args.capture_action,
            decision=args.decision,
            reviewed_by=args.reviewed_by,
            dry_run=args.dry_run,
            approve=args.approve,
        )
    except (archive_services.ArchiveServiceError, OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        summary = (
            result.get("material_selection_summary")
            if isinstance(result.get("material_selection_summary"), dict)
            else {}
        )
        approval = result.get("approval_summary") if isinstance(result.get("approval_summary"), dict) else {}
        record = result.get("approval_record") if isinstance(result.get("approval_record"), dict) else {}
        print(f"IMAP mailbox material capture approval {result.get('record_state') or '-'}.")
        print(f"Archive: {result.get('archive_id') or '-'}")
        print(f"Capture action: {result.get('capture_action') or '-'}")
        print(f"Decision: {result.get('decision') or '-'}")
        print(f"Selection mode: {summary.get('selection_mode') or '-'}")
        print(f"Selected count: {approval.get('selected_count') or 0}")
        print(f"Receipt: {record.get('receipt_path') or record.get('proposed_receipt_path') or '-'}")
        print("Material selection receipt path echoed: no")
        print("Execution receipt path echoed: no")
        print("Candidate refs echoed: no")
        print("Message material read now: no")
        writes = result.get("files_written") or []
        if writes:
            print("Files written:")
            for path in writes:
                print(f"- {path}")
        else:
            print("Writes: none")
        if result.get("blockers"):
            print("Blockers:")
            for blocker in result["blockers"]:
                print(f"- {blocker}")
        if result.get("warnings"):
            print("Warnings:")
            for warning in result["warnings"]:
                print(f"- {warning}")
    return 0 if result.get("ok", True) else 1


def command_imap_mailbox_material_capture_approval_audit(args: argparse.Namespace) -> int:
    if not args.dry_run:
        print("imap-mailbox-material-capture-approval-audit is read-only and requires --dry-run.", file=sys.stderr)
        return 1
    try:
        result = archive_services.imap_mailbox_material_capture_approval_audit(
            Path(args.archive_root),
            material_selection_receipt=args.material_selection_receipt,
            approval_receipt=args.approval_receipt,
            capture_action=args.capture_action,
            expected_decision=args.expected_decision,
            dry_run=True,
        )
    except (archive_services.ArchiveServiceError, OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        approval = (
            result.get("approval_receipt_summary")
            if isinstance(result.get("approval_receipt_summary"), dict)
            else {}
        )
        validation = (
            result.get("validation_summary")
            if isinstance(result.get("validation_summary"), dict)
            else {}
        )
        print(f"IMAP mailbox material capture approval audit {result.get('audit_state') or '-'}.")
        print(f"Archive: {result.get('archive_id') or '-'}")
        print(f"Capture action: {result.get('capture_action') or '-'}")
        print(f"Decision: {approval.get('decision') or '-'}")
        print(f"Expected decision: {result.get('expected_decision') or '-'}")
        print(f"Future capture authorized: {'yes' if result.get('future_capture_authorized') else 'no'}")
        print(f"Selection SHA matches: {'yes' if validation.get('material_selection_sha256_matches') else 'no'}")
        print(f"Selected indexes match: {'yes' if validation.get('selected_indexes_match') else 'no'}")
        print("Approval receipt path echoed: no")
        print("Material selection receipt path echoed: no")
        print("Execution receipt path echoed: no")
        print("Candidate refs echoed: no")
        print("Message material read now: no")
        print("Writes: none")
        if result.get("blockers"):
            print("Blockers:")
            for blocker in result["blockers"]:
                print(f"- {blocker}")
        if result.get("warnings"):
            print("Warnings:")
            for warning in result["warnings"]:
                print(f"- {warning}")
    return 0 if result.get("ok", True) else 1


def command_imap_mailbox_adapter_manifest_plan(args: argparse.Namespace) -> int:
    if not args.dry_run:
        print("imap-mailbox-adapter-manifest-plan is read-only and requires --dry-run.", file=sys.stderr)
        return 1
    try:
        result = archive_services.imap_mailbox_adapter_manifest_plan(
            Path(args.archive_root),
            adapter_id=args.adapter_id,
            providers=args.provider,
            operations=args.operation,
            selection_rules=args.selection_rule,
            consumer=args.consumer,
            platform=args.platform,
            dry_run=True,
        )
    except (archive_services.ArchiveServiceError, OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        state = "passed" if result.get("ok") else "blocked"
        manifest = result.get("manifest_preview") if isinstance(result.get("manifest_preview"), dict) else {}
        print(f"IMAP mailbox adapter manifest plan {state}.")
        print(f"Archive: {result.get('archive_id') or '-'}")
        print(f"Adapter: {manifest.get('adapter_id') or '-'} ({manifest.get('adapter_kind') or '-'})")
        print(f"Manifest: {result.get('proposed_manifest_path') or '-'}")
        print("Writes: none")
        if result.get("blockers"):
            print("Blockers:")
            for blocker in result["blockers"]:
                print(f"- {blocker}")
        if result.get("warnings"):
            print("Warnings:")
            for warning in result["warnings"]:
                print(f"- {warning}")
    return 0 if result.get("ok", True) else 1


def command_imap_mailbox_adapter_manifest_write(args: argparse.Namespace) -> int:
    if args.dry_run == args.approve:
        print("Choose exactly one mode: --dry-run or --approve.", file=sys.stderr)
        return 1
    try:
        result = archive_services.imap_mailbox_adapter_manifest_write(
            Path(args.archive_root),
            adapter_id=args.adapter_id,
            providers=args.provider,
            operations=args.operation,
            selection_rules=args.selection_rule,
            consumer=args.consumer,
            platform=args.platform,
            reviewed_by=args.reviewed_by,
            dry_run=args.dry_run,
            approve=args.approve,
        )
    except (archive_services.ArchiveServiceError, OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        state = "written" if result.get("approved") else ("passed" if result.get("ok") else "blocked")
        manifest = result.get("manifest_preview") if isinstance(result.get("manifest_preview"), dict) else {}
        print(f"IMAP mailbox adapter manifest write {state}.")
        print(f"Archive: {result.get('archive_id') or '-'}")
        print(f"Adapter: {manifest.get('adapter_id') or '-'} ({manifest.get('adapter_kind') or '-'})")
        print(f"Manifest: {result.get('manifest_path') or result.get('proposed_manifest_path') or '-'}")
        print(f"Receipt: {result.get('receipt_path') or result.get('proposed_receipt_path') or '-'}")
        print("IMAP connection opened: no")
        print("Mail read: no")
        writes = result.get("files_written") or []
        if writes:
            print("Files written:")
            for path in writes:
                print(f"- {path}")
        else:
            print("Writes: none")
        if result.get("blockers"):
            print("Blockers:")
            for blocker in result["blockers"]:
                print(f"- {blocker}")
        if result.get("warnings"):
            print("Warnings:")
            for warning in result["warnings"]:
                print(f"- {warning}")
    return 0 if result.get("ok", True) else 1


def command_sources(args: argparse.Namespace) -> int:
    try:
        result = archive_services.list_sources(Path(args.archive_root))
    except (archive_services.ArchiveServiceError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        print(f"Sources for {result['archive_id']}: {result['source_count']} configured.")
        print(f"Path: {result['source_bindings_path']}")
        for source in result["sources"]:
            state = "enabled" if source["enabled"] else "disabled"
            mapped = source["mapped_items"]
            print(f"- {source['source_id']} ({source['source_type']}, {state}): {mapped} mapped item(s)")
    return 0


def command_scan_source(args: argparse.Namespace) -> int:
    if args.dry_run and args.approve:
        print("Use either --dry-run or --approve, not both.", file=sys.stderr)
        return 1
    if not args.dry_run and not args.approve:
        print("Source scan requires --dry-run or --approve.", file=sys.stderr)
        return 1
    if args.approve and not args.reviewed_by:
        print("Source scan requires --reviewed-by when --approve is used.", file=sys.stderr)
        return 1

    try:
        if args.dry_run:
            result = archive_services.source_scan_dry_run(
                Path(args.archive_root),
                source_id=args.source,
                source_root=args.source_root,
                limit=args.limit,
            )
        else:
            result = archive_services.scan_source(
                Path(args.archive_root),
                source_id=args.source,
                source_root=args.source_root,
                reviewed_by=args.reviewed_by,
                limit=args.limit,
            )
    except (archive_services.ArchiveServiceError, OSError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
        return 0 if result["ok"] else 1

    mode = "dry-run" if result["dry_run"] else "applied"
    state = "passed" if result["ok"] else "blocked"
    print(f"Source scan {mode} {state}.")
    print(f"Archive: {result['source_archive']}")
    print(f"Source: {result['source_id']} ({result['source_type']})")
    print(f"Scan mode: {result['scan_mode']}")
    print(f"Items: {result['item_count']}")
    if result["dry_run"]:
        print(f"Proposed source map path: {result['proposed_source_map_path']}")
        print(f"Proposed receipt path: {result['proposed_receipt_path']}")
    else:
        print(f"Source map path: {result['source_map_path']}")
        print(f"Receipt path: {result['receipt_path']}")
    if result.get("blockers"):
        print("Blockers:")
        for blocker in result["blockers"]:
            print(f"- {blocker}")
    if result.get("warnings"):
        print("Warnings:")
        for warning in result["warnings"]:
            print(f"- {warning}")
    return 0 if result["ok"] else 1


def command_add_source(args: argparse.Namespace) -> int:
    if args.dry_run and args.approve:
        print("Use either --dry-run or --approve, not both.", file=sys.stderr)
        return 1
    if not args.dry_run and not args.approve:
        print("Source registration requires --dry-run or --approve.", file=sys.stderr)
        return 1
    if args.approve and not args.reviewed_by:
        print("Source registration requires --reviewed-by when --approve is used.", file=sys.stderr)
        return 1

    try:
        if args.dry_run:
            result = archive_services.add_source_dry_run(
                Path(args.archive_root),
                source_id=args.source_id,
                source_type=args.source_type,
                description=args.description,
                root_ref=args.root_ref,
                local_root=args.local_root,
                write_local_profile=args.write_local_profile,
                include=args.include,
                exclude=args.exclude,
                max_items=args.max_items,
                visibility_scope=args.visibility_scope,
                source_visibility=args.source_visibility,
                replace=args.replace,
            )
        else:
            result = archive_services.add_source_binding(
                Path(args.archive_root),
                source_id=args.source_id,
                source_type=args.source_type,
                description=args.description,
                root_ref=args.root_ref,
                local_root=args.local_root,
                write_local_profile=args.write_local_profile,
                include=args.include,
                exclude=args.exclude,
                max_items=args.max_items,
                visibility_scope=args.visibility_scope,
                source_visibility=args.source_visibility,
                replace=args.replace,
                reviewed_by=args.reviewed_by,
            )
    except (archive_services.ArchiveServiceError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
        return 0 if result["ok"] else 1

    mode = "dry-run" if result["dry_run"] else "applied"
    state = "passed" if result["ok"] else "blocked"
    print(f"Source registration {mode} {state}.")
    print(f"Archive: {result['archive_id']}")
    print(f"Source: {result['source_id']} ({result['source_type']})")
    print(f"Root ref: {result['source_binding']['root_ref']}")
    if result["dry_run"]:
        print("Would change: " + ", ".join(result["would_change"]))
    else:
        print("Changed: " + ", ".join(result["changed_paths"]))
    if result.get("blockers"):
        print("Blockers:")
        for blocker in result["blockers"]:
            print(f"- {blocker}")
    if result.get("warnings"):
        print("Warnings:")
        for warning in result["warnings"]:
            print(f"- {warning}")
    return 0 if result["ok"] else 1


def command_source_mounts(args: argparse.Namespace) -> int:
    try:
        result = archive_services.source_mount_plan(Path(args.archive_root))
    except (archive_services.ArchiveServiceError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        print(f"Source mount plan for {result['archive_id']}.")
        print(f"Strategy: {result['strategy']}")
        for source in result["sources"]:
            if source["needs_host_mount"]:
                print(f"- {source['source_id']}: mount {source['compose_volume_hint']}")
                print(f"  Docker scan: {source['docker_scan_command']}")
            else:
                print(f"- {source['source_id']}: no extra host mount needed")
    return 0


def command_recovery_plan(args: argparse.Namespace) -> int:
    try:
        result = archive_services.recovery_plan(Path(args.archive_root))
    except (archive_services.ArchiveServiceError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        print(f"Recovery plan for {result['archive_id']}.")
        print("Mode: local control-plane recovery; external originals are not copied.")
        print(f"Sources: {result['source_summary']['source_count']} configured")
        print(f"Providers: {result['provider_summary']['binding_count']} configured, manual verification required")
        if result["latest_successful_restore_drill"]:
            latest = result["latest_successful_restore_drill"]
            print(f"Latest restore drill: {latest['receipt_path']}")
        else:
            print("Latest restore drill: none")
    return 0


def command_upgrade_check(args: argparse.Namespace) -> int:
    if not args.dry_run:
        print("Upgrade check is read-only and requires --dry-run.", file=sys.stderr)
        return 1
    try:
        archive_root = Path(args.archive_root)
        diagnostics = [item.as_dict() for item in Doctor(archive_root).run()]
        result = archive_services.upgrade_check(
            archive_root,
            diagnostics=diagnostics,
            require_restore_drill=args.require_restore_drill,
        )
    except (archive_services.ArchiveServiceError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print_upgrade_check_result(result, args.format)
    return 0 if result["upgrade_readiness"]["status"] != "blocked" else 1


def print_upgrade_check_result(result: dict[str, Any], output_format: str) -> None:
    if output_format == "json":
        print_json(result)
        return
    state = result["upgrade_readiness"]["status"]
    print(f"Upgrade check dry-run {state}.")
    print(f"Archive: {result['archive_id']}")
    print(f"Doctor: {result['doctor']['errors']} error(s), {result['doctor']['warnings']} warning(s)")
    latest_restore = result["restore_drill"]["latest_successful"]
    if latest_restore:
        print(f"Latest restore drill: {latest_restore['receipt_path']}")
    else:
        print("Latest restore drill: none")
    print("Safety model: read-only advisor; no migration engine, provider calls, or object-store operations.")
    print(f"Ready for manual upgrade review: {str(result['upgrade_readiness']['ready_for_manual_upgrade_review']).lower()}")
    if result["blockers"]:
        print("Blockers:")
        for blocker in result["blockers"]:
            print(f"- {blocker}")
    if result["warnings"]:
        print("Warnings:")
        for warning in result["warnings"]:
            print(f"- {warning}")
    print("Next safe actions:")
    for action in result["next_safe_actions"]:
        print(f"- {action}")


def command_project_intake_plan(args: argparse.Namespace) -> int:
    if not args.dry_run:
        print("Project intake planning is read-only and requires --dry-run.", file=sys.stderr)
        return 1
    try:
        result = archive_services.project_intake_plan(Path(args.archive_root), Path(args.staged_folder))
    except (archive_services.ArchiveServiceError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print_project_intake_plan_result(result, args.format)
    return 0


def print_project_intake_plan_result(result: dict[str, Any], output_format: str) -> None:
    if output_format == "json":
        print_json(result)
        return
    summary = result["folder_summary"]
    print("Project intake plan dry-run ready.")
    print(f"Archive: {result['archive_id']}")
    print(f"Staged folder: {result['staged_folder']}")
    print(
        "Top-level summary: "
        f"{summary['top_level_file_count']} file(s), "
        f"{summary['top_level_dir_count']} folder(s), "
        f"{summary['top_level_other_count']} other item(s)."
    )
    convention = "yes" if result["follows_staging_convention"] else "no"
    print(f"Follows staging convention: {convention}")
    print("Writes: none (would_change: [])")
    if result["warnings"]:
        print("Warnings:")
        for warning in result["warnings"]:
            print(f"- {warning}")
    print("Human review checklist:")
    for item in result.get("human_review_checklist", []):
        print(f"- {item.get('id')}: {item.get('question')}")
    print("Next session questions:")
    for question in result["next_session_questions"]:
        print(f"- {question}")
    print("Next safe actions:")
    for action in result["next_safe_actions"]:
        print(f"- {action}")


def command_project_intake_staging_guide(args: argparse.Namespace) -> int:
    try:
        result = archive_services.project_intake_staging_guide(
            Path(args.archive_root),
            project_slug=args.project_slug,
            dry_run=args.dry_run,
        )
    except (archive_services.ArchiveServiceError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print_project_intake_staging_guide_result(result, args.format)
    return 0 if result.get("ok", True) else 1


def print_project_intake_staging_guide_result(result: dict[str, Any], output_format: str) -> None:
    if output_format == "json":
        print_json(result)
        return
    print("Project intake staging guide dry-run.")
    print(f"Archive: {result.get('archive_id') or '-'}")
    paths = result.get("recommended_paths") if isinstance(result.get("recommended_paths"), dict) else {}
    print(f"Objet store: {paths.get('objet_store_root') or '-'}")
    print(f"Intake root: {paths.get('intake_root') or '-'}")
    print(f"Staged project folder: {paths.get('staged_project_folder') or '-'}")
    print("Writes: none")
    if result.get("blockers"):
        print("Blockers:")
        for blocker in result["blockers"]:
            print(f"- {blocker}")
    if result.get("next_safe_actions"):
        print("Next safe actions:")
        for action in result["next_safe_actions"]:
            print(f"- {action}")


def command_project_intake_session_guide(args: argparse.Namespace) -> int:
    try:
        result = archive_services.project_intake_session_guide(
            Path(args.archive_root),
            project_slug=args.project_slug,
            staged_folder=Path(args.staged_folder) if args.staged_folder else None,
            receipt=args.receipt,
            session_id=args.session_id,
            staged_folder_ref=args.staged_folder_ref,
            dry_run=args.dry_run,
        )
    except (archive_services.ArchiveServiceError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print_project_intake_session_guide_result(result, args.format)
    return 0 if result.get("ok", True) else 1


def print_project_intake_session_guide_result(result: dict[str, Any], output_format: str) -> None:
    if output_format == "json":
        print_json(result)
        return
    print(f"Project intake session guide dry-run {result.get('state') or 'unknown'}.")
    print(f"Archive: {result.get('archive_id') or '-'}")
    print(f"Mode: {result.get('mode') or '-'}")
    turn = result.get("next_human_turn") if isinstance(result.get("next_human_turn"), dict) else None
    if turn is None:
        print("Next human turn: none")
    else:
        if turn.get("checklist_id"):
            print(f"Checklist id: {turn.get('checklist_id')}")
        print(f"Ask: {turn.get('ask_user') or '-'}")
        print(f"Answer type: {turn.get('answer_type') or '-'}")
    guidance = result.get("command_guidance") if isinstance(result.get("command_guidance"), dict) else {}
    if guidance:
        print("Command guidance:")
        for key, value in guidance.items():
            print(f"- {key}: {value}")
    print("Writes: none")
    if result.get("blockers"):
        print("Blockers:")
        for blocker in result["blockers"]:
            print(f"- {blocker}")
    if result.get("warnings"):
        print("Warnings:")
        for warning in result["warnings"]:
            print(f"- {warning}")
    if result.get("next_safe_actions"):
        print("Next safe actions:")
        for action in result["next_safe_actions"]:
            print(f"- {action}")


def command_project_intake_decisions(args: argparse.Namespace) -> int:
    try:
        result = archive_services.project_intake_decisions(
            Path(args.archive_root),
            Path(args.decisions),
            dry_run=args.dry_run,
            approve=args.approve,
            reviewed_by=args.reviewed_by,
        )
    except (archive_services.ArchiveServiceError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print_project_intake_decisions_result(result, args.format)
    return 0 if result.get("ok", True) else 1


def print_project_intake_decisions_result(result: dict[str, Any], output_format: str) -> None:
    if output_format == "json":
        print_json(result)
        return
    mode = "dry-run ready" if result.get("dry_run") else "recorded"
    if not result.get("ok", True):
        mode = "blocked"
    print(f"Project intake decisions {mode}.")
    print(f"Archive: {result.get('archive_id') or '-'}")
    print(f"Session: {result.get('session_id') or '-'}")
    print(f"Answer count: {result.get('answer_count', 0)}")
    print(f"Decision SHA-256: {result.get('decision_sha256') or '-'}")
    if result.get("checklist_ids"):
        print("Checklist ids:")
        for checklist_id in result["checklist_ids"]:
            print(f"- {checklist_id}")
    if result.get("receipt_path"):
        print(f"Receipt: {result['receipt_path']}")
    else:
        print(f"Proposed receipt: {result.get('proposed_receipt_path') or '-'}")
    writes = result.get("files_written") or []
    if writes:
        print("Files written:")
        for path in writes:
            print(f"- {path}")
    else:
        print("Writes: none")
    if result.get("blockers"):
        print("Blockers:")
        for blocker in result["blockers"]:
            print(f"- {blocker}")
    if result.get("warnings"):
        print("Warnings:")
        for warning in result["warnings"]:
            print(f"- {warning}")


def command_project_intake_record_answer(args: argparse.Namespace) -> int:
    try:
        result = archive_services.project_intake_record_answer(
            Path(args.archive_root),
            Path(args.answer),
            receipt=args.receipt,
            session_id=args.session_id,
            staged_folder_ref=args.staged_folder_ref,
            dry_run=args.dry_run,
            approve=args.approve,
            reviewed_by=args.reviewed_by,
        )
    except (archive_services.ArchiveServiceError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print_project_intake_record_answer_result(result, args.format)
    return 0 if result.get("ok", True) else 1


def print_project_intake_record_answer_result(result: dict[str, Any], output_format: str) -> None:
    if output_format == "json":
        print_json(result)
        return
    mode = "dry-run ready" if result.get("dry_run") else "recorded"
    if not result.get("ok", True):
        mode = "blocked"
    print(f"Project intake answer {mode}.")
    print(f"Archive: {result.get('archive_id') or '-'}")
    print(f"Session: {result.get('session_id') or '-'}")
    print(f"Previous answers: {result.get('previous_answer_count', 0)}")
    print(f"New checklist id: {result.get('new_answer_checklist_id') or '-'}")
    print(f"Expected next checklist id: {result.get('expected_next_checklist_id') or '-'}")
    print(f"Answer count: {result.get('answer_count', 0)}")
    print(f"Decision SHA-256: {result.get('decision_sha256') or '-'}")
    if result.get("checklist_ids"):
        print("Checklist ids:")
        for checklist_id in result["checklist_ids"]:
            print(f"- {checklist_id}")
    if result.get("receipt_path"):
        print(f"Receipt: {result['receipt_path']}")
    else:
        print(f"Proposed receipt: {result.get('proposed_receipt_path') or '-'}")
    writes = result.get("files_written") or []
    if writes:
        print("Files written:")
        for path in writes:
            print(f"- {path}")
    else:
        print("Writes: none")
    print("Answer values echoed: no")
    if result.get("blockers"):
        print("Blockers:")
        for blocker in result["blockers"]:
            print(f"- {blocker}")
    if result.get("warnings"):
        print("Warnings:")
        for warning in result["warnings"]:
            print(f"- {warning}")
    if result.get("next_safe_actions"):
        print("Next safe actions:")
        for action in result["next_safe_actions"]:
            print(f"- {action}")


def command_project_intake_status(args: argparse.Namespace) -> int:
    try:
        result = archive_services.project_intake_status(
            Path(args.archive_root),
            args.receipt,
            dry_run=args.dry_run,
        )
    except (archive_services.ArchiveServiceError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print_project_intake_status_result(result, args.format)
    return 0 if result.get("ok", True) else 1


def print_project_intake_status_result(result: dict[str, Any], output_format: str) -> None:
    if output_format == "json":
        print_json(result)
        return
    state = result.get("readiness", {}).get("status") or "unknown"
    print(f"Project intake status dry-run {state}.")
    print(f"Archive: {result.get('archive_id') or '-'}")
    print(f"Session: {result.get('session_id') or '-'}")
    print(f"Receipt: {result.get('receipt_path') or '-'}")
    coverage = result.get("checklist_coverage") if isinstance(result.get("checklist_coverage"), dict) else {}
    print(f"Answered checklist ids: {coverage.get('answered_count', 0)} / {coverage.get('required_count', 0)}")
    if coverage.get("answered_checklist_ids"):
        print("Answered:")
        for checklist_id in coverage["answered_checklist_ids"]:
            print(f"- {checklist_id}")
    if coverage.get("missing_checklist_ids"):
        print("Missing:")
        for checklist_id in coverage["missing_checklist_ids"]:
            print(f"- {checklist_id}")
    if result.get("next_review_prompts"):
        print("Next review prompts:")
        for prompt in result["next_review_prompts"]:
            print(f"- {prompt.get('checklist_id')}: {prompt.get('question')}")
    print("Writes: none")
    if result.get("blockers"):
        print("Blockers:")
        for blocker in result["blockers"]:
            print(f"- {blocker}")
    if result.get("warnings"):
        print("Warnings:")
        for warning in result["warnings"]:
            print(f"- {warning}")
    if result.get("next_safe_actions"):
        print("Next safe actions:")
        for action in result["next_safe_actions"]:
            print(f"- {action}")


def command_project_intake_next_question(args: argparse.Namespace) -> int:
    try:
        result = archive_services.project_intake_next_question(
            Path(args.archive_root),
            staged_folder=Path(args.staged_folder) if args.staged_folder else None,
            receipt=args.receipt,
            dry_run=args.dry_run,
        )
    except (archive_services.ArchiveServiceError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print_project_intake_next_question_result(result, args.format)
    return 0 if result.get("ok", True) else 1


def print_project_intake_next_question_result(result: dict[str, Any], output_format: str) -> None:
    if output_format == "json":
        print_json(result)
        return
    print(f"Project intake next question dry-run {result.get('state') or 'unknown'}.")
    print(f"Archive: {result.get('archive_id') or '-'}")
    if result.get("session_id"):
        print(f"Session: {result['session_id']}")
    question = result.get("next_question") if isinstance(result.get("next_question"), dict) else None
    if question is None:
        print("Next question: none")
    else:
        print(f"Checklist id: {question.get('checklist_id')}")
        print(f"Question: {question.get('ask_user')}")
        print(f"Answer type: {question.get('answer_type')}")
        if question.get("allowed_labels"):
            print("Allowed labels:")
            for label in question["allowed_labels"]:
                print(f"- {label}")
    print(f"Remaining prompts: {result.get('remaining_prompt_count', 0)}")
    print("Writes: none")
    if result.get("blockers"):
        print("Blockers:")
        for blocker in result["blockers"]:
            print(f"- {blocker}")
    if result.get("warnings"):
        print("Warnings:")
        for warning in result["warnings"]:
            print(f"- {warning}")
    if result.get("next_safe_actions"):
        print("Next safe actions:")
        for action in result["next_safe_actions"]:
            print(f"- {action}")


def command_project_intake_decision_template(args: argparse.Namespace) -> int:
    try:
        result = archive_services.project_intake_decision_template(
            Path(args.archive_root),
            staged_folder=Path(args.staged_folder) if args.staged_folder else None,
            receipt=args.receipt,
            session_id=args.session_id,
            staged_folder_ref=args.staged_folder_ref,
            dry_run=args.dry_run,
        )
    except (archive_services.ArchiveServiceError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print_project_intake_decision_template_result(result, args.format)
    return 0 if result.get("ok", True) else 1


def print_project_intake_decision_template_result(result: dict[str, Any], output_format: str) -> None:
    if output_format == "json":
        print_json(result)
        return
    print(f"Project intake decision template dry-run {result.get('state') or 'unknown'}.")
    print(f"Archive: {result.get('archive_id') or '-'}")
    question = result.get("next_question") if isinstance(result.get("next_question"), dict) else None
    if question is None:
        print("Next question: none")
    else:
        print(f"Checklist id: {question.get('checklist_id')}")
        print(f"Question: {question.get('ask_user')}")
    print("Decision values included: no")
    print("Writes: none")
    if result.get("blockers"):
        print("Blockers:")
        for blocker in result["blockers"]:
            print(f"- {blocker}")
    if result.get("warnings"):
        print("Warnings:")
        for warning in result["warnings"]:
            print(f"- {warning}")
    if result.get("next_safe_actions"):
        print("Next safe actions:")
        for action in result["next_safe_actions"]:
            print(f"- {action}")


def command_project_intake_item_plan(args: argparse.Namespace) -> int:
    try:
        result = archive_services.project_intake_item_plan(
            Path(args.archive_root),
            receipt=args.receipt,
            local_path=Path(args.local_path),
            source_role=args.source_role,
            title=args.title,
            mime=args.mime,
            dry_run=args.dry_run,
        )
    except (archive_services.ArchiveServiceError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print_project_intake_item_plan_result(result, args.format)
    return 0 if result.get("ok", True) else 1


def print_project_intake_item_plan_result(result: dict[str, Any], output_format: str) -> None:
    if output_format == "json":
        print_json(result)
        return
    print(f"Project intake item plan dry-run {result.get('state') or 'unknown'}.")
    print(f"Archive: {result.get('archive_id') or '-'}")
    print(f"Receipt: {result.get('receipt_path') or '-'}")
    selected = result.get("selected_item_plan") if isinstance(result.get("selected_item_plan"), dict) else {}
    print(f"Input kind: {selected.get('input_kind') or '-'}")
    print(f"Source kind: {selected.get('source_kind') or '-'}")
    print(f"Objet status: {selected.get('objet_status') or '-'}")
    guidance = result.get("command_guidance") if isinstance(result.get("command_guidance"), dict) else {}
    if guidance.get("source_intake_dry_run"):
        print("Next dry-run command:")
        print(guidance["source_intake_dry_run"])
    print("Writes: none")
    if result.get("blockers"):
        print("Blockers:")
        for blocker in result["blockers"]:
            print(f"- {blocker}")
    if result.get("warnings"):
        print("Warnings:")
        for warning in result["warnings"]:
            print(f"- {warning}")
    if result.get("next_safe_actions"):
        print("Next safe actions:")
        for action in result["next_safe_actions"]:
            print(f"- {action}")


def command_restore_drill(args: argparse.Namespace) -> int:
    if args.dry_run and args.approve:
        print("Use either --dry-run or --approve, not both.", file=sys.stderr)
        return 1
    if not args.dry_run and not args.approve:
        print("Restore drill requires --dry-run or --approve.", file=sys.stderr)
        return 1
    if args.approve and not args.reviewed_by:
        print("Restore drill requires --reviewed-by when --approve is used.", file=sys.stderr)
        return 1

    try:
        plan = archive_services.restore_drill_dry_run(Path(args.archive_root), Path(args.target))
    except (archive_services.ArchiveServiceError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.dry_run or not plan["ok"]:
        print_restore_drill_result(plan, args.format)
        return 0 if plan["ok"] else 1

    archive_root = Path(args.archive_root).resolve()
    target = Path(args.target).expanduser().resolve()
    reviewed_at = datetime.now().astimezone().replace(microsecond=0).isoformat()
    timestamp_slug = reviewed_at.replace(":", "").replace("+", "_").replace("-", "").replace("T", "_")
    receipt_relative = f"{archive_services.RESTORE_DRILL_RECEIPTS_DIR}/{timestamp_slug}.restore-drill.json"

    try:
        changed_archive_paths = archive_services.copy_restore_drill_tree(archive_root, target)
        diagnostics = Doctor(target).run()
        errors = [item for item in diagnostics if item.severity == "ERROR"]
        warnings = [item for item in diagnostics if item.severity == "WARN"]
        index_result = archive_services.index_archive(target)
        search_result = archive_services.search_archive(target, "archive", limit=3)
    except (archive_services.ArchiveServiceError, OSError, sqlite3.Error) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    validation_ok = not errors and not warnings
    result_status = "passed" if validation_ok else "failed"
    blockers = [] if validation_ok else [f"Restored copy doctor reported {len(errors)} error(s), {len(warnings)} warning(s)."]
    receipt = dict(plan["receipt_preview"])
    receipt.update(
        {
            "receipt_id": f"receipt:restore-drill:{archive_services.safe_slug(plan['archive_id'])}:{timestamp_slug}",
            "dry_run": False,
            "timestamp": reviewed_at,
            "reviewed_by": args.reviewed_by,
            "reviewed_at": reviewed_at,
            "validation": {
                "doctor_strict": {
                    "ok": validation_ok,
                    "errors": len(errors),
                    "warnings": len(warnings),
                    "diagnostics": [item.as_dict() for item in diagnostics],
                },
                "index": index_result,
                "search_smoke": {
                    "ok": True,
                    "query": search_result["query"],
                    "count": search_result["count"],
                },
            },
            "result": {
                "status": result_status,
                "changed_paths": [str(target), receipt_relative],
                "restored_archive_file_count": len(changed_archive_paths),
            },
            "blockers": blockers,
            "warnings": [],
        }
    )
    receipt_path = archive_services.archive_internal_path(archive_root, receipt_relative)
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    final = {
        "ok": validation_ok,
        "dry_run": False,
        "action": "restore_drill",
        "archive_id": plan["archive_id"],
        "archive_root": str(archive_root),
        "target_root": str(target),
        "receipt_path": receipt_relative,
        "copy_plan": plan["copy_plan"],
        "validation": receipt["validation"],
        "result": receipt["result"],
        "blockers": blockers,
        "warnings": [],
    }
    print_restore_drill_result(final, args.format)
    return 0 if validation_ok else 1


def print_restore_drill_result(result: dict[str, Any], output_format: str) -> None:
    if output_format == "json":
        print_json(result)
        return
    mode = "dry-run" if result["dry_run"] else "applied"
    state = "passed" if result["ok"] else "blocked"
    print(f"Restore drill {mode} {state}.")
    print(f"Archive: {result['archive_id']}")
    print(f"Target: {result['target_root']}")
    print(f"Files planned: {result['copy_plan']['included_files']}")
    if result.get("receipt_path"):
        print(f"Receipt: {result['receipt_path']}")
    elif result.get("proposed_receipt_path"):
        print(f"Proposed receipt: {result['proposed_receipt_path']}")
    if result.get("blockers"):
        print("Blockers:")
        for blocker in result["blockers"]:
            print(f"- {blocker}")
    if result.get("warnings"):
        print("Warnings:")
        for warning in result["warnings"]:
            print(f"- {warning}")


def command_pilot_plan(args: argparse.Namespace) -> int:
    try:
        result = archive_services.real_pilot_plan(
            personal_root=Path(args.personal_root),
            team_root=Path(args.team_root),
            personal_archive_id=args.personal_archive_id,
            personal_principal_id=args.personal_principal_id,
            personal_principal_name=args.personal_principal_name,
            team_archive_id=args.team_archive_id,
            team_principal_id=args.team_principal_id,
            team_principal_name=args.team_principal_name,
            personal_provider_profile=args.personal_provider_profile,
            team_provider_profile=args.team_provider_profile,
        )
    except (archive_services.ArchiveServiceError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
        return 0 if result["ok"] else 1

    state = "passed" if result["ok"] else "blocked"
    print(f"Real archive pilot plan {state}.")
    print("Safety model: metadata-first, no content reads, no live provider API calls.")
    for archive in result["archives"]:
        print(f"- {archive['label']}: {archive['target_root']}")
        print(f"  Archive id: {archive['archive_id']}")
        print(f"  Provider profile: {archive['provider_profile']}")
        print(f"  Suggested sources: {len(archive['suggested_sources'])}")
    if result["blockers"]:
        print("Blockers:")
        for blocker in result["blockers"]:
            print(f"- {blocker}")
    if result["warnings"]:
        print("Warnings:")
        for warning in result["warnings"]:
            print(f"- {warning}")
    return 0 if result["ok"] else 1


def command_preflight(args: argparse.Namespace) -> int:
    try:
        archive_root = Path(args.archive_root)
        diagnostics = [item.as_dict() for item in Doctor(archive_root).run()]
        docker_runtime = docker_runtime_check() if args.check_docker else {"checked": False, "ok": None, "status": "not_checked"}
        result = archive_services.preflight_check(
            archive_root,
            diagnostics=diagnostics,
            peer_archive_root=Path(args.peer_archive) if args.peer_archive else None,
            require_source_maps=args.require_source_maps,
            require_restore_drill=args.require_restore_drill,
            strict=args.strict,
            docker_runtime=docker_runtime,
        )
    except (archive_services.ArchiveServiceError, OSError, subprocess.SubprocessError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
        return 0 if result["ok"] else 1

    state = "passed" if result["ok"] else "blocked"
    print(f"Archive preflight {state}.")
    print(f"Archive: {result['archive_id']}")
    print(f"Doctor: {result['doctor']['errors']} error(s), {result['doctor']['warnings']} warning(s)")
    print(f"Sources: {result['sources']['source_count']} configured")
    print(f"Docker: {result['docker_runtime']['status']}")
    if result["blockers"]:
        print("Blockers:")
        for blocker in result["blockers"]:
            print(f"- {blocker}")
    if result["warnings"]:
        print("Warnings:")
        for warning in result["warnings"]:
            print(f"- {warning}")
    print("Next safe actions:")
    for action in result["next_safe_actions"]:
        print(f"- {action}")
    return 0 if result["ok"] else 1


def docker_runtime_check() -> dict[str, Any]:
    override = os.environ.get("AI_ARCHIVE_TEST_DOCKER_STATE")
    if override:
        return docker_runtime_check_from_state(override)

    docker = shutil.which("docker")
    if docker is None:
        return {
            "checked": True,
            "ok": False,
            "status": "missing",
            "message": "Docker CLI is not installed or not on PATH.",
        }

    compose = subprocess.run(
        [docker, "compose", "version"],
        cwd=KIT_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )
    if compose.returncode != 0:
        return {
            "checked": True,
            "ok": False,
            "status": "compose_missing",
            "message": "Docker Compose is not available through docker compose.",
        }

    info = subprocess.run(
        [docker, "info", "--format", "{{.ServerVersion}}"],
        cwd=KIT_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )
    if info.returncode != 0:
        return {
            "checked": True,
            "ok": False,
            "status": "daemon_down",
            "message": "Docker daemon is not reachable. Start Docker Desktop and rerun preflight.",
        }

    config = subprocess.run(
        [docker, "compose", "config"],
        cwd=KIT_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
    )
    if config.returncode != 0:
        return {
            "checked": True,
            "ok": False,
            "status": "compose_config_failed",
            "message": "docker compose config failed for the WOM-kit runtime.",
        }

    return {
        "checked": True,
        "ok": True,
        "status": "ready",
        "server_version": info.stdout.strip(),
        "message": "Docker CLI, Compose, daemon, and compose config are available.",
    }


def docker_runtime_check_from_state(state: str) -> dict[str, Any]:
    mapping = {
        "missing": ("missing", False, "Docker CLI is not installed or not on PATH."),
        "compose_missing": ("compose_missing", False, "Docker Compose is not available through docker compose."),
        "daemon_down": ("daemon_down", False, "Docker daemon is not reachable. Start Docker Desktop and rerun preflight."),
        "ready": ("ready", True, "Docker CLI, Compose, daemon, and compose config are available."),
    }
    status, ok, message = mapping.get(state, ("unknown", False, f"Unknown Docker test state: {state}."))
    return {"checked": True, "ok": ok, "status": status, "message": message}


def command_onboard(args: argparse.Namespace) -> int:
    require_yaml()
    if args.guided:
        fill_guided_onboarding_args(args)
    missing = [
        name
        for name in ["target_root", "archive_type", "archive_id", "principal_id"]
        if not getattr(args, name, None)
    ]
    if missing:
        print("Missing onboarding argument(s): " + ", ".join(f"--{name.replace('_', '-')}" for name in missing), file=sys.stderr)
        return 2
    if args.dry_run and args.approve:
        print("Use either --dry-run or --approve, not both.", file=sys.stderr)
        return 1

    principal_kind = args.principal_kind or archive_services.default_principal_kind_for_archive_type(args.archive_type)
    try:
        plan = archive_services.onboarding_plan(
            Path(args.target_root),
            archive_type=args.archive_type,
            archive_id=args.archive_id,
            principal_id=args.principal_id,
            principal_name=args.principal_name,
            principal_kind=principal_kind,
            name=args.name,
            provider_profile=args.provider_profile,
        )
    except (archive_services.ArchiveServiceError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if not args.approve:
        print_onboarding_result(plan, args.format)
        return 0 if plan["ok"] else 1
    if not plan["ok"]:
        print_onboarding_result(plan, args.format)
        return 1

    target = Path(args.target_root).resolve()
    if target.exists() and not target.is_dir():
        print(f"Target archive root must be a folder or absent: {target}.", file=sys.stderr)
        return 1
    if target.exists() and any(target.iterdir()):
        print(f"Target archive folder must be empty or absent: {target}.", file=sys.stderr)
        return 1
    template = TEMPLATES_ROOT / args.archive_type
    if not template.is_dir():
        print(f"Unknown archive type: {args.archive_type}", file=sys.stderr)
        return 2

    namespace = argparse.Namespace(
        archive_root=str(target),
        type=args.archive_type,
        archive_id=args.archive_id,
        principal_id=args.principal_id,
        principal_name=args.principal_name,
        principal_kind=principal_kind,
        name=args.name or plan["name"],
        dry_run=False,
    )
    target.mkdir(parents=True, exist_ok=True)
    copy_template(template, target)
    copy_zettel_kasten_layer(target)
    create_recommended_dirs(target)
    write_safe_gitignore(target)
    update_archive_yml(target, namespace)
    update_archive_identity_yml(target, namespace)
    update_provider_bindings_yml(target, namespace)
    update_source_bindings_yml(target, namespace)
    apply_provider_profile(target, args.provider_profile)

    doctor = Doctor(target)
    diagnostics = doctor.run()
    errors = [item for item in diagnostics if item.severity == "ERROR"]
    warnings = [item for item in diagnostics if item.severity == "WARN"]
    result = dict(plan)
    result.update(
        {
            "ok": not errors and not warnings,
            "dry_run": False,
            "created_paths": plan["would_create"],
            "doctor": {
                "strict": True,
                "errors": len(errors),
                "warnings": len(warnings),
                "diagnostics": [item.as_dict() for item in diagnostics],
            },
        }
    )
    print_onboarding_result(result, args.format)
    return 0 if result["ok"] else 1


def fill_guided_onboarding_args(args: argparse.Namespace) -> None:
    def ask(attr: str, prompt: str, default: str | None = None) -> None:
        if getattr(args, attr, None):
            return
        suffix = f" [{default}]" if default else ""
        answer = input(f"{prompt}{suffix}: ").strip()
        setattr(args, attr, answer or default)

    ask("archive_type", "Archive type (personal, family, company)", "personal")
    ask("target_root", "Archive folder to create", "archives/personal")
    ask("principal_id", "Owner/principal id", "person:me")
    ask("archive_id", "Archive id", "archive:personal:me")
    ask("principal_name", "Display name", "Me")


def print_onboarding_result(result: dict[str, Any], output_format: str) -> None:
    if output_format == "json":
        print_json(result)
        return
    state = "passed" if result["ok"] else "blocked"
    mode = "dry-run" if result["dry_run"] else "applied"
    print(f"Archive onboarding {mode} {state}.")
    print(f"Target: {result['target_root']}")
    print(f"Archive: {result['archive_id']} ({result['archive_type']})")
    print(f"Principal: {result['principal_id']}")
    print(f"Provider profile: {result['provider_profile']}")
    print("Enabled providers: " + ", ".join(result["provider_bindings"]["enabled_providers"]))
    if not result["dry_run"] and "doctor" in result:
        doctor = result["doctor"]
        print(f"Doctor: {doctor['errors']} error(s), {doctor['warnings']} warning(s)")
    if result["blockers"]:
        print("Blockers:")
        for blocker in result["blockers"]:
            print(f"- {blocker}")
    if result["warnings"]:
        print("Warnings:")
        for warning in result["warnings"]:
            print(f"- {warning}")


def command_transfer_ownership(args: argparse.Namespace) -> int:
    if args.dry_run and args.approve:
        print("Use either --dry-run or --approve, not both.", file=sys.stderr)
        return 1
    if args.dry_run:
        try:
            result = archive_services.ownership_transfer_dry_run(
                Path(args.archive_root),
                new_owner=args.new_owner,
                new_owner_kind=args.new_owner_kind,
                new_owner_archive=args.new_owner_archive,
                operators_after=args.operator_after,
                approved_by=args.approved_by,
                subject=args.subject,
                counterparty_id=args.counterparty_id,
                counterparty_fingerprint=args.counterparty_fingerprint,
                reason=args.reason,
            )
        except (archive_services.ArchiveServiceError, OSError) as exc:
            print(str(exc), file=sys.stderr)
            return 1

        if args.format == "json":
            print_json(result)
        else:
            state = "passed" if result["ok"] else "blocked"
            print(f"Ownership transfer dry-run {state}.")
            print(f"Archive: {result['source_archive']}")
            print(f"Previous owner: {result['previous_owner']}")
            print(f"New owner: {result['new_owner']}")
            print(f"Operators after: {', '.join(result['ownership_gate']['operators_after']) or '(none)'}")
            print(f"Trust gate: {result['trust_gate']['status']}")
            print(f"Provider changes: {result['provider_change_plan']['status']}")
            print(f"Proposed receipt path: {result['proposed_receipt_path']}")
            if result["blockers"]:
                print("Blockers:")
                for blocker in result["blockers"]:
                    print(f"- {blocker}")
            if result["warnings"]:
                print("Warnings:")
                for warning in result["warnings"]:
                    print(f"- {warning}")
        return 0 if result["ok"] else 1

    if not args.approve:
        print("Real ownership transfer requires --approve. Use --dry-run to preview.", file=sys.stderr)
        return 1
    if not args.reviewed_by:
        print("Real ownership transfer requires --reviewed-by.", file=sys.stderr)
        return 1

    try:
        result = archive_services.transfer_archive_ownership(
            Path(args.archive_root),
            new_owner=args.new_owner,
            new_owner_kind=args.new_owner_kind,
            new_owner_archive=args.new_owner_archive,
            operators_after=args.operator_after,
            approved_by=args.approved_by,
            subject=args.subject,
            counterparty_id=args.counterparty_id,
            counterparty_fingerprint=args.counterparty_fingerprint,
            reason=args.reason,
            reviewed_by=args.reviewed_by,
        )
    except (archive_services.ArchiveServiceError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        print("Ownership transfer applied.")
        print(f"Archive: {result['source_archive']}")
        print(f"Previous owner: {result['previous_owner']}")
        print(f"New owner: {result['new_owner']}")
        print(f"Reviewed by: {result['reviewed_by']}")
        print(f"Receipt path: {result['receipt_path']}")
        print(f"Provider changes: {result['provider_change_plan']['status']} (manual)")
    return 0


def command_init(args: argparse.Namespace) -> int:
    require_yaml()

    target = Path(args.archive_root).resolve()
    template = TEMPLATES_ROOT / args.type
    if not template.is_dir():
        print(f"Unknown archive type: {args.type}", file=sys.stderr)
        return 2

    if target.exists() and any(target.iterdir()):
        print(f"Target must be empty or absent: {target}", file=sys.stderr)
        return 1

    if args.dry_run:
        print(f"Would initialize {args.type} archive at {target}")
        return 0

    target.mkdir(parents=True, exist_ok=True)
    copy_template(template, target)
    copy_zettel_kasten_layer(target)
    create_recommended_dirs(target)
    write_safe_gitignore(target)
    update_archive_yml(target, args)
    update_archive_identity_yml(target, args)
    update_provider_bindings_yml(target, args)
    update_source_bindings_yml(target, args)

    print(f"Initialized {args.type} archive at {target}")
    print(f"archive_id: {args.archive_id}")
    print(f"principal_id: {args.principal_id}")
    return 0


def copy_template(template: Path, target: Path) -> None:
    for child in template.iterdir():
        destination = target / child.name
        if child.is_dir():
            shutil.copytree(child, destination, dirs_exist_ok=True)
        else:
            shutil.copy2(child, destination)


def copy_zettel_kasten_layer(target: Path) -> None:
    destination = target / "zettel-kasten"
    shutil.copytree(KIT_ZETTEL_KASTEN_ROOT, destination, dirs_exist_ok=True)


def create_recommended_dirs(target: Path) -> None:
    for relative in [
        "inbox",
        "zettels",
        "views",
        "source-maps",
        "objects/manifests",
        "objects/derived-text/sha256",
        "db",
        "workbench",
        "receipts",
        "receipts/derived-text-capture",
        "receipts/delegate",
        "receipts/edges",
        "receipts/import",
        "receipts/lineage",
        "receipts/mint",
        "receipts/mint/drafts",
        "receipts/recovery",
        "receipts/share",
        "receipts/sources",
    ]:
        (target / relative).mkdir(parents=True, exist_ok=True)


def write_safe_gitignore(target: Path) -> None:
    gitignore = target / ".gitignore"
    if gitignore.exists():
        return
    gitignore.write_text(
        "\n".join(
            [
                "# WOM-kit safe defaults",
                ".env",
                ".env.*",
                "!.env.example",
                "*.key",
                "*.pem",
                "*.p12",
                "*.pfx",
                "*.kdbx",
                "secrets/",
                "profiles/local/",
                "profiles/*.local.yml",
                "keyrings/local/",
                "keyrings/*.local.yml",
                ".archive-local/",
                "rclone.conf",
                "credentials.json",
                "token.json",
                "tmp/",
                ".wom-scratch/",
                "workbench/ai-scratch/",
                "node_modules/",
                ".next/",
                ".vercel/",
                "",
                "# Local-only collaboration and harness state",
                "/collab/",
                "/.mow-harness/",
                "",
                "# Generated archive search indexes",
                "**/db/archive-index.sqlite",
                "**/db/archive-index.sqlite-wal",
                "**/db/archive-index.sqlite-shm",
                "**/db/archive-index.sqlite-journal",
                "",
                "# Local content-addressed objet byte store (manifests/receipts stay tracked)",
                "objects/sha256/",
                "objects/derived-text/sha256/",
                "",
                "# Raw in-root objet store must never be tracked (non-canonical layout; see artifact-hygiene migration guide)",
                "/objets/",
                "",
            ]
        ),
        encoding="utf-8",
    )


def gitignore_missing_patterns(gitignore: Path) -> list[str]:
    if not gitignore.is_file():
        return list(RECOMMENDED_GITIGNORE_PATTERNS)
    lines = {
        line.strip()
        for line in gitignore.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    }
    return [pattern for pattern in RECOMMENDED_GITIGNORE_PATTERNS if pattern not in lines]


def append_gitignore_patterns(gitignore: Path, missing: list[str]) -> None:
    if not gitignore.is_file():
        gitignore.write_text(
            "\n".join(["# WOM-kit safe defaults", *RECOMMENDED_GITIGNORE_PATTERNS, ""]),
            encoding="utf-8",
        )
        return
    existing = gitignore.read_text(encoding="utf-8")
    prefix = "" if not existing or existing.endswith("\n") else "\n"
    addition = "\n".join(["", "# WOM-kit repaired safe defaults", *missing, ""])
    gitignore.write_text(existing + prefix + addition, encoding="utf-8")


def repair_gitignore(root: Path, *, approve: bool, reviewed_by: str | None) -> dict[str, Any]:
    archive_root = archive_services.require_existing_archive_root(root)
    archive_id = archive_services.read_archive_id(archive_root)
    gitignore = archive_root / ".gitignore"
    missing = gitignore_missing_patterns(gitignore)
    if not gitignore.is_file() and missing:
        action = "create_gitignore"
    elif missing:
        action = "append_patterns"
    else:
        action = "up_to_date"
    result = {
        "ok": True,
        "dry_run": not approve,
        "lifecycle_action": "repair_gitignore_plan" if not approve else "repair_gitignore",
        "archive_id": archive_id,
        "action": action if approve else f"would_{action}" if action != "up_to_date" else "up_to_date",
        "missing_patterns": missing,
        "planned_writes": [".gitignore"] if missing else [],
        "changed_paths": [],
        "reviewed_by": reviewed_by if approve else None,
        "blockers": [],
        "warnings": [],
    }
    if not approve or not missing:
        return result
    if not reviewed_by or not str(reviewed_by).strip():
        return {**result, "ok": False, "action": "blocked", "blockers": ["reviewed_by_required"]}
    append_gitignore_patterns(gitignore, missing)
    return {**result, "action": action, "changed_paths": [".gitignore"]}


def update_archive_yml(target: Path, args: argparse.Namespace) -> None:
    path = target / "archive.yml"
    data = load_yaml(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"archive.yml is not a YAML object: {path}")

    data["archive_id"] = args.archive_id
    data["name"] = args.name or f"{args.type.title()} Archive"
    data["type"] = args.type
    data["principal"] = {
        "principal_id": args.principal_id,
        "display_name": args.principal_name or args.principal_id,
        "kind": args.principal_kind,
    }
    data.setdefault("root_policy", {})
    data["root_policy"].setdefault("canonical_zettels", "zettels/")
    data["root_policy"].setdefault("ai_inbox", "inbox/")
    data["root_policy"].setdefault("views", "views/")
    data["root_policy"].setdefault("object_manifest", "objects/manifests/files.jsonl")
    data["root_policy"].setdefault("derived_text_manifest", archive_services.DERIVED_TEXT_MANIFEST_RELATIVE_PATH)
    data["root_policy"].setdefault("source_bindings", "source-bindings.yml")
    data["root_policy"].setdefault("source_maps", "source-maps/")
    data["root_policy"].setdefault("sqlite_schema", "db/schema.sql")
    data.setdefault("ai_write_policy", {})
    data["ai_write_policy"]["default"] = "inbox_only"
    data["ai_write_policy"]["canonical_requires"] = "human_minting"
    data.setdefault("storage_policy", {})
    data["storage_policy"]["object_identity"] = "sha256"
    data["storage_policy"]["provider_urls_in_zettels"] = "forbidden"
    data["storage_policy"]["locations_live_in_manifest"] = True
    data.setdefault("mounted_archives", [])

    path.write_text(dump_yaml(data), encoding="utf-8")


def update_archive_identity_yml(target: Path, args: argparse.Namespace) -> None:
    path = target / "archive-identity.yml"
    data: dict[str, Any] = {}
    if path.is_file():
        loaded = load_yaml(path.read_text(encoding="utf-8"))
        data = loaded if isinstance(loaded, dict) else {}

    identity = data.get("identity") if isinstance(data.get("identity"), dict) else {}
    identity["archive_id"] = args.archive_id
    identity.setdefault("identity_id", f"identity:{args.archive_id}")
    identity["scope"] = args.type
    identity["principal_id"] = args.principal_id
    identity.setdefault("display_name", args.principal_name or args.principal_id)
    identity.setdefault("public_keys", [])
    data["identity"] = identity

    ownership = data.get("ownership") if isinstance(data.get("ownership"), dict) else {}
    ownership["owner_id"] = args.principal_id
    ownership["owner_kind"] = args.principal_kind
    ownership["owner_display_name"] = args.principal_name or args.principal_id
    ownership["owner_archive_id"] = args.archive_id
    default_operator = {
        "operator_id": args.principal_id,
        "role": "owner_operator",
        "permissions": ["capture", "curate", "approve", "transfer_request"],
    }
    if args.type == "personal" or not isinstance(ownership.get("operators"), list) or not ownership.get("operators"):
        ownership["operators"] = [default_operator]
    ownership.setdefault("subjects", [])
    ownership.setdefault(
        "transfer_policy",
        {
            "ownership_transfer_allowed": True,
            "requires_human_approval": True,
            "requires_receipt": True,
            "receipt_action": "transfer_archive_ownership",
            "default_transfer_target": None,
        },
    )
    data["ownership"] = ownership
    data.setdefault("trusted_counterparties", [])
    data.setdefault(
        "lineage",
        {
            "parents": [],
            "children": [],
            "forked_from": None,
            "merged_from": [],
            "exited_from": None,
        },
    )

    path.write_text(dump_yaml(data), encoding="utf-8")


def update_provider_bindings_yml(target: Path, args: argparse.Namespace) -> None:
    path = target / "provider-bindings.yml"
    if not path.is_file():
        return
    data = load_yaml(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"provider-bindings.yml is not a YAML object: {path}")
    data["archive_id"] = args.archive_id
    path.write_text(dump_yaml(data), encoding="utf-8")


def update_source_bindings_yml(target: Path, args: argparse.Namespace) -> None:
    path = target / "source-bindings.yml"
    if not path.is_file():
        return
    data = load_yaml(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"source-bindings.yml is not a YAML object: {path}")
    data["archive_id"] = args.archive_id
    path.write_text(dump_yaml(data), encoding="utf-8")


def apply_provider_profile(target: Path, provider_profile: str | None) -> None:
    path = target / "provider-bindings.yml"
    if not path.is_file():
        return
    data = load_yaml(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"provider-bindings.yml is not a YAML object: {path}")
    enabled = set(archive_services.provider_profile_enabled_providers(provider_profile))
    bindings = data.get("bindings") if isinstance(data.get("bindings"), list) else []
    for binding in bindings:
        if not isinstance(binding, dict):
            continue
        binding["enabled"] = binding.get("provider") in enabled
    data["onboarding"] = {
        "provider_profile": provider_profile or "local_only",
        "secret_values_allowed": False,
        "external_provider_mutation": "manual_required",
    }
    path.write_text(dump_yaml(data), encoding="utf-8")


def print_json(data: Any) -> None:
    print(json.dumps(data, indent=2, ensure_ascii=False, default=str))


def print_diagnostics(diagnostics: list[Diagnostic], errors: list[Diagnostic], warnings: list[Diagnostic]) -> None:
    for item in diagnostics:
        location = f" [{item.path}]" if item.path else ""
        print(f"{item.severity}: {item.code}: {item.message}{location}")
        if item.hint:
            print(f"  hint: {item.hint}")
        if item.suggested_command:
            print(f"  suggested_command: {item.suggested_command}")
        if item.compatibility_target:
            print(f"  compatibility_target: {item.compatibility_target}")
    print(f"\nSummary: {len(errors)} error(s), {len(warnings)} warning(s).")


def parse_key_value_pairs(items: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for item in items:
        if "=" not in item:
            raise ValueError(f"Facet must be KEY=VALUE: {item}")
        key, value = item.split("=", 1)
        key = key.strip()
        if not key:
            raise ValueError(f"Facet key must not be empty: {item}")
        result[key] = value.strip()
    return result


def parse_source_ref_pairs(items: list[str]) -> list[dict[str, str]]:
    refs: list[dict[str, str]] = []
    for item in items:
        if ":" not in item:
            raise ValueError(f"Source ref must be TYPE:VALUE: {item}")
        ref_type, value = item.split(":", 1)
        ref_type = ref_type.strip()
        value = value.strip()
        if not ref_type or not value:
            raise ValueError(f"Source ref must be TYPE:VALUE: {item}")
        ref = {"type": ref_type, "value": value}
        if ref_type == "local_ai_session":
            ref["role"] = "prompt_context"
        refs.append(ref)
    return refs


def load_source_intake_plan_file(path: str | None) -> dict[str, Any] | None:
    if not path:
        return None
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"source-intake plan must be valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("source-intake plan JSON must be an object.")
    return data


def load_prompt_boundary_report_file(path: str | None) -> dict[str, Any] | None:
    if not path:
        return None
    report_path = Path(path)
    if "\x00" in path or ".." in report_path.parts:
        raise ValueError("prompt-boundary report path must not contain path traversal.")
    try:
        data = json.loads(report_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"prompt-boundary report must be valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("prompt-boundary report JSON must be an object.")
    return data


def infer_runtime_name(actor: str | None) -> str | None:
    if not actor:
        return None
    if actor.startswith("ai_runtime:"):
        return actor.split(":", 1)[1] or None
    if actor.startswith("mcp:"):
        return "mcp"
    if actor.startswith("cli:"):
        return "cli"
    return None


def build_local_ai_session_refs(args: argparse.Namespace) -> list[dict[str, str]]:
    sessions: list[dict[str, str]] = []
    runtime = infer_runtime_name(args.created_by)
    archive_id = args.expected_archive_id or args.archive_id
    for item in args.local_ai_session or []:
        session_ref = item.strip()
        if not session_ref:
            continue
        session = {"session_ref": session_ref}
        if runtime:
            session["runtime"] = runtime
        if args.profile_id:
            session["profile_id"] = args.profile_id
        if archive_id:
            session["archive_id"] = archive_id
        if args.profile_authority_mode:
            session["authority_mode"] = args.profile_authority_mode
        sessions.append(session)
    return sessions


def read_body_arg(args: argparse.Namespace) -> str:
    if args.body_file:
        return Path(args.body_file).read_text(encoding="utf-8")
    return args.body


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="archive",
        description="Minimal CLI for WOM archive nodes.",
    )
    parser.add_argument("--version", action="version", version=f"archive {__version__}")
    subcommands = parser.add_subparsers(dest="command", required=True)

    version = subcommands.add_parser("version", help="Print the running WOM-kit version and optional project pin status.")
    version.add_argument(
        "inspection_root",
        nargs="?",
        help="Optional project/archive root to inspect for .zettel-kasten/source/installed-version.txt.",
    )
    version.add_argument(
        "--no-redact-local-paths",
        dest="redact_local_paths",
        action="store_false",
        default=True,
        help="Include local module and inspection paths in JSON output.",
    )
    version.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    version.set_defaults(func=command_version)

    capabilities = subcommands.add_parser(
        "capabilities",
        help="Print an agent-facing manifest of executable CLI commands and local release identity.",
    )
    capabilities.add_argument(
        "--machine",
        action="store_true",
        help="Print the stable JSON envelope intended for AI operators.",
    )
    capabilities.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    capabilities.add_argument(
        "--no-commands",
        action="store_true",
        help="Omit the full command list and print only summary/release identity.",
    )
    capabilities.set_defaults(func=command_capabilities)

    operator_feedback_plan = subcommands.add_parser(
        "operator-feedback-plan",
        aliases=["feedback-plan", "ops-feedback-plan"],
        help="Read-only plan for operator-generated feedback storage and lifecycle status.",
    )
    operator_feedback_plan.add_argument("archive_root", help="Archive root to inspect.")
    operator_feedback_plan.add_argument("--dry-run", action="store_true", help="Required. Preview only; write nothing.")
    operator_feedback_plan.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    operator_feedback_plan.set_defaults(func=command_operator_feedback_plan)

    operator_feedback_record = subcommands.add_parser(
        "operator-feedback-record",
        aliases=["feedback-record", "feedback-register"],
        help="Preview or approve a metadata record for operator-generated feedback.",
    )
    operator_feedback_record.add_argument("archive_root", help="Archive root receiving the feedback metadata record.")
    operator_feedback_record.add_argument("--feedback-id", required=True, help="Safe feedback id for ops/feedback/<id>.yml.")
    operator_feedback_record.add_argument("--feedback-ref", required=True, help="Safe non-secret feedback ref; no URLs, emails, tokens, or local paths.")
    operator_feedback_record.add_argument("--status", required=True, choices=archive_services.OPERATOR_FEEDBACK_STATUSES, help="Feedback lifecycle status.")
    operator_feedback_record.add_argument("--title", help="Optional safe single-line label stored in the record but not echoed.")
    operator_feedback_record.add_argument("--related-release", action="append", help="Safe related release label. May be repeated.")
    operator_feedback_record.add_argument("--resolved-in", help="Safe release/decision label required when --status resolved.")
    operator_feedback_record.add_argument("--dry-run", action="store_true", help="Preview the metadata record without writing files.")
    operator_feedback_record.add_argument("--approve", action="store_true", help="Write ops/feedback metadata and a receipt.")
    operator_feedback_record.add_argument("--reviewed-by", help="Reviewer id required for approved writes.")
    operator_feedback_record.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    operator_feedback_record.set_defaults(func=command_operator_feedback_record)

    objet_capture_enable = subcommands.add_parser(
        "objet-capture-enable",
        aliases=["capture-enable"],
        help="Inspect, approve, or revoke the owner capture-enablement record that lets a real (non-sandbox) archive run objet-capture.",
    )
    objet_capture_enable.add_argument("archive_root", help="Archive root to inspect, enable, or revoke.")
    objet_capture_enable.add_argument("--dry-run", action="store_true", help="Read-only eligibility report; writes nothing.")
    objet_capture_enable.add_argument("--approve", action="store_true", help="Write ops/capture-enablement.yml plus a receipt after owner review.")
    objet_capture_enable.add_argument("--reviewed-by", help="Reviewer id required when --approve is used.")
    objet_capture_enable.add_argument("--revoke", action="store_true", help="Revoke the existing enablement record (with --approve; --dry-run previews the revoke).")
    objet_capture_enable.add_argument(
        "--acknowledge-never-touch-name",
        action="store_true",
        help="Required at approve time when the root or a parent name matches the never-touch pattern (zettel-kasten-* / *-objets).",
    )
    objet_capture_enable.add_argument("--reenable", action="store_true", help="Required to approve enablement over a previously revoked record.")
    objet_capture_enable.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    objet_capture_enable.set_defaults(func=command_objet_capture_enable)

    approval_handoff_plan = subcommands.add_parser(
        "approval-handoff-plan",
        aliases=["handoff-plan", "human-approval-handoff-plan"],
        help="Read-only plan for AI-to-human approval handoff records.",
    )
    approval_handoff_plan.add_argument("archive_root", help="Archive root to inspect.")
    approval_handoff_plan.add_argument("--dry-run", action="store_true", help="Required. Preview only; write nothing.")
    approval_handoff_plan.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    approval_handoff_plan.set_defaults(func=command_approval_handoff_plan)

    approval_handoff_record = subcommands.add_parser(
        "approval-handoff-record",
        aliases=["handoff-record", "human-approval-handoff-record"],
        help="Preview or approve a safe metadata record for a human approval handoff.",
    )
    approval_handoff_record.add_argument("archive_root", help="Archive root receiving the handoff metadata record.")
    approval_handoff_record.add_argument("--handoff-id", required=True, help="Safe handoff id for ops/approval-handoffs/<id>.yml.")
    approval_handoff_record.add_argument(
        "--operation-kind",
        required=True,
        choices=archive_services.APPROVAL_HANDOFF_OPERATION_KINDS,
        help="Operation category that needs human review.",
    )
    approval_handoff_record.add_argument("--target-ref", required=True, help="Safe non-secret target ref; no URLs, emails, tokens, or local paths.")
    approval_handoff_record.add_argument("--requested-action", required=True, help="Safe non-secret action label stored in the record but not echoed.")
    approval_handoff_record.add_argument("--status", required=True, choices=archive_services.APPROVAL_HANDOFF_STATUSES, help="Approval handoff lifecycle status.")
    approval_handoff_record.add_argument("--requested-by", help="Optional safe non-secret actor id for the AI/operator requesting approval.")
    approval_handoff_record.add_argument("--reviewed-by", help="Reviewer id required for approved writes.")
    approval_handoff_record.add_argument("--related-command", action="append", help="Safe related CLI command label. May be repeated.")
    approval_handoff_record.add_argument("--related-release", action="append", help="Safe related release label. May be repeated.")
    approval_handoff_record.add_argument("--supersedes", help="Safe prior handoff id required when --status superseded.")
    approval_handoff_record.add_argument("--resolved-in", help="Safe release/receipt/decision label required when --status resolved.")
    approval_handoff_record.add_argument("--dry-run", action="store_true", help="Preview the metadata record without writing files.")
    approval_handoff_record.add_argument("--approve", action="store_true", help="Write ops/approval-handoffs metadata and a receipt.")
    approval_handoff_record.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    approval_handoff_record.set_defaults(func=command_approval_handoff_record)

    approval_handoff_audit = subcommands.add_parser(
        "approval-handoff-audit",
        aliases=["handoff-audit", "human-approval-handoff-audit"],
        help="Audit an approval handoff metadata record without executing the underlying operation.",
    )
    approval_handoff_audit.add_argument("archive_root", help="Archive root to inspect.")
    approval_handoff_audit.add_argument(
        "--handoff-record",
        required=True,
        help="Archive-relative ops/approval-handoffs/<id>.yml path. Target/action values are not echoed.",
    )
    approval_handoff_audit.add_argument(
        "--expected-operation-kind",
        choices=archive_services.APPROVAL_HANDOFF_OPERATION_KINDS,
        help="Optional operation kind expected by the future operation.",
    )
    approval_handoff_audit.add_argument(
        "--expected-status",
        choices=archive_services.APPROVAL_HANDOFF_STATUSES,
        default="approved_once",
        help="Expected handoff status. Defaults to approved_once.",
    )
    approval_handoff_audit.add_argument("--dry-run", action="store_true", help="Required. Audit only; write nothing.")
    approval_handoff_audit.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    approval_handoff_audit.set_defaults(func=command_approval_handoff_audit)

    operation_status_taxonomy = subcommands.add_parser(
        "operation-status-taxonomy",
        aliases=["status-taxonomy", "partial-success-taxonomy"],
        help="Read-only taxonomy for AI-visible operation status and partial/truncated result handling.",
    )
    operation_status_taxonomy.add_argument("archive_root", help="Archive root to inspect.")
    operation_status_taxonomy.add_argument("--dry-run", action="store_true", help="Required. Preview only; write nothing.")
    operation_status_taxonomy.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    operation_status_taxonomy.set_defaults(func=command_operation_status_taxonomy)

    input_provenance_taxonomy = subcommands.add_parser(
        "input-provenance-taxonomy",
        aliases=["provenance-taxonomy", "caller-input-taxonomy"],
        help="Read-only taxonomy for tool-discovered, receipt-verified, human-selected, caller-supplied, and AI-generated inputs.",
    )
    input_provenance_taxonomy.add_argument("archive_root", help="Archive root to inspect.")
    input_provenance_taxonomy.add_argument("--dry-run", action="store_true", help="Required. Preview only; write nothing.")
    input_provenance_taxonomy.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    input_provenance_taxonomy.set_defaults(func=command_input_provenance_taxonomy)

    secret_signal_taxonomy = subcommands.add_parser(
        "secret-signal-taxonomy",
        aliases=["secret-taxonomy", "sensitive-signal-taxonomy"],
        help="Read-only taxonomy for secret concept words, safe references, private locators, and secret-like values.",
    )
    secret_signal_taxonomy.add_argument("archive_root", help="Archive root to inspect.")
    secret_signal_taxonomy.add_argument("--dry-run", action="store_true", help="Required. Preview only; write nothing.")
    secret_signal_taxonomy.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    secret_signal_taxonomy.set_defaults(func=command_secret_signal_taxonomy)

    ai_response_contract = subcommands.add_parser(
        "ai-response-contract",
        aliases=["response-contract", "operator-response-contract"],
        help="Read-only contract for AI answers that report status, provenance, privacy, approval, and remaining work.",
    )
    ai_response_contract.add_argument("archive_root", help="Archive root to inspect.")
    ai_response_contract.add_argument("--dry-run", action="store_true", help="Required. Preview only; write nothing.")
    ai_response_contract.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    ai_response_contract.set_defaults(func=command_ai_response_contract)

    doctor = subcommands.add_parser("doctor", help="Inspect an archive for structural and policy issues.")
    doctor.add_argument("archive_root", nargs="?", default=".", help="Archive root to inspect.")
    doctor.add_argument("--strict", action="store_true", help="Treat warnings as a failing result.")
    doctor.add_argument("--json", action="store_true", help="Print diagnostics as JSON.")
    doctor.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    doctor.set_defaults(func=command_doctor)

    validate = subcommands.add_parser("validate", help="Run strict archive validation.")
    validate.add_argument("archive_root", nargs="?", default=".", help="Archive root to validate.")
    validate.add_argument("--allow-warnings", action="store_true", help="Do not fail when only warnings are present.")
    validate.add_argument(
        "--strict",
        action="store_true",
        help="Accepted for parity with doctor: validate already treats warnings as failing unless --allow-warnings.",
    )
    validate.add_argument(
        "--since",
        action="append",
        help="Validate artifacts touched by a mint/retire/edge batch id or batch receipt path. May be repeated.",
    )
    validate.add_argument(
        "--scope",
        action="append",
        help="Validate zettels matching an indexed facet filter, for example source_database=database_2_0. May be repeated.",
    )
    validate.add_argument("--progress", action="store_true", help="Stream stage and item progress to stderr.")
    validate.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    validate.set_defaults(func=command_validate)

    repair_gitignore = subcommands.add_parser(
        "repair-gitignore",
        help="Dry-run or approve adding missing WOM-kit safe .gitignore patterns.",
    )
    repair_gitignore.add_argument("archive_root", help="Archive root whose .gitignore should be repaired.")
    repair_gitignore.add_argument("--dry-run", action="store_true", help="Preview missing .gitignore patterns without writing.")
    repair_gitignore.add_argument("--approve", action="store_true", help="Append missing safe .gitignore patterns.")
    repair_gitignore.add_argument("--reviewed-by", help="Reviewer id required with --approve.")
    repair_gitignore.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    repair_gitignore.set_defaults(func=command_repair_gitignore)

    migrate = subcommands.add_parser("migrate", help="Dry-run or approve a compatibility migration.")
    migrate.add_argument("archive_root", help="Archive root to migrate.")
    migrate.add_argument(
        "--target",
        required=True,
        choices=[archive_services.FRONTMATTER_V03_TARGET, archive_services.LINK_TYPES_V03_TARGET],
        help="Migration target.",
    )
    migrate.add_argument("--dry-run", action="store_true", help="Preview migration changes without writing files.")
    migrate.add_argument("--approve", action="store_true", help="Apply the reviewed migration changes.")
    migrate.add_argument("--revert", action="store_true", help="Preview or apply a safe migration rollback where the target supports it.")
    migrate.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    migrate.set_defaults(func=command_migrate)

    profile_list_parser = subcommands.add_parser(
        "profile-list",
        help="List read-only WOM profile registry entries.",
    )
    profile_list_parser.add_argument("--registry", required=True, help="Path to the local WOM profile registry YAML file.")
    profile_list_parser.add_argument("--current-profile", help="Optional current profile id for caller context.")
    profile_list_parser.add_argument("--strict", action="store_true", help="Treat registry warnings as blocking.")
    profile_list_parser.add_argument(
        "--redact-local-paths",
        dest="redact_local_paths",
        action="store_true",
        default=True,
        help="Redact registry and archive local paths. This is the default.",
    )
    profile_list_parser.add_argument(
        "--no-redact-local-paths",
        dest="redact_local_paths",
        action="store_false",
        help="Include local paths for trusted local debugging.",
    )
    profile_list_parser.add_argument("--format", choices=["json"], default="json", help="Output format.")
    profile_list_parser.set_defaults(func=command_profile_list)

    profile_resolve_parser = subcommands.add_parser(
        "profile-resolve",
        help="Resolve a requested WOM profile before runtime-context.",
    )
    profile_resolve_parser.add_argument("--registry", required=True, help="Path to the local WOM profile registry YAML file.")
    profile_resolve_parser.add_argument("--target", required=True, help="Requested profile id, label, or alias.")
    profile_resolve_parser.add_argument("--current-profile", help="Optional current profile id for caller context.")
    profile_resolve_parser.add_argument("--strict", action="store_true", help="Treat registry warnings as blocking when safe.")
    profile_resolve_parser.add_argument(
        "--redact-local-paths",
        dest="redact_local_paths",
        action="store_true",
        default=True,
        help="Redact registry and archive local paths. This is the default.",
    )
    profile_resolve_parser.add_argument(
        "--no-redact-local-paths",
        dest="redact_local_paths",
        action="store_false",
        help="Include local paths for trusted local debugging.",
    )
    profile_resolve_parser.add_argument("--format", choices=["json"], default="json", help="Output format.")
    profile_resolve_parser.set_defaults(func=command_profile_resolve)

    profile_wallet_parser = subcommands.add_parser(
        "profile-wallet",
        help="Preview wallet-ready identity metadata for a resolved WOM profile.",
    )
    profile_wallet_parser.add_argument("archive_root", help="Archive root used for context.")
    profile_wallet_parser.add_argument("--profile", required=True, help="Requested profile id, label, or alias.")
    profile_wallet_parser.add_argument("--registry", help="Optional path to the local WOM profile registry YAML file.")
    profile_wallet_parser.add_argument("--dry-run", action="store_true", help="Preview only; never write files or generate keys.")
    profile_wallet_parser.add_argument(
        "--redact-local-paths",
        dest="redact_local_paths",
        action="store_true",
        default=True,
        help="Redact registry and archive local paths. This is the default.",
    )
    profile_wallet_parser.add_argument(
        "--no-redact-local-paths",
        dest="redact_local_paths",
        action="store_false",
        help="Include local paths for trusted local debugging.",
    )
    profile_wallet_parser.add_argument("--format", choices=["json"], default="json", help="Output format.")
    profile_wallet_parser.set_defaults(func=command_profile_wallet)

    runtime_context = subcommands.add_parser(
        "runtime-context",
        help="Print read-only AI runtime context for a mounted archive.",
    )
    runtime_context.add_argument("archive_root", help="Archive root to inspect.")
    runtime_context.add_argument("--expected-archive-id", help="Expected archive id; mismatch blocks.")
    runtime_context.add_argument(
        "--expected-type",
        choices=sorted(archive_services.RUNTIME_CONTEXT_ARCHIVE_TYPES),
        help="Expected archive type. Mismatch warns by default and blocks with --strict.",
    )
    runtime_context.add_argument("--strict", action="store_true", help="Treat runtime context warnings as blocking.")
    runtime_context.add_argument(
        "--redact-local-paths",
        dest="redact_local_paths",
        action="store_true",
        default=True,
        help="Use archive-relative paths and suppress local absolute paths. This is the default.",
    )
    runtime_context.add_argument(
        "--no-redact-local-paths",
        dest="redact_local_paths",
        action="store_false",
        help="Include local absolute path context for trusted local debugging.",
    )
    runtime_context.add_argument("--format", choices=["json"], default="json", help="Output format.")
    runtime_context.set_defaults(func=command_runtime_context)

    operational_context = subcommands.add_parser(
        "operational-context",
        help="Read or approve-update the AI-facing mission/state rehydration record.",
    )
    operational_context.add_argument("archive_root", help="Archive root to inspect or update.")
    operational_context.add_argument(
        "--record",
        help="Archive-relative staged YAML candidate to validate or approve into ops/operational-context.yml.",
    )
    operational_context.add_argument("--dry-run", action="store_true", help="Read or preview only; never write files.")
    operational_context.add_argument("--approve", action="store_true", help="Approve writing the staged operational context record.")
    operational_context.add_argument("--reviewed-by", help="Safe non-secret actor id required when --approve is used.")
    operational_context.add_argument("--format", choices=["json"], default="json", help="Output format.")
    operational_context.set_defaults(func=command_operational_context)

    ai_usage_plan = subcommands.add_parser(
        "ai-usage-plan",
        help="Estimate an explicit AI context pack against a token budget without echoing content.",
    )
    ai_usage_plan.add_argument("archive_root", help="Archive root to inspect.")
    ai_usage_plan.add_argument("--budget-tokens", type=int, required=True, help="Token budget for the planned AI context pack.")
    ai_usage_plan.add_argument(
        "--include",
        dest="include_paths",
        action="append",
        default=[],
        help="Archive-relative UTF-8 text file to include in the token estimate. May be repeated.",
    )
    ai_usage_plan.add_argument("--task-id", help="Safe non-secret task id for the planned AI call.")
    ai_usage_plan.add_argument("--purpose", help="Safe non-secret purpose label for the planned AI call.")
    ai_usage_plan.add_argument("--dry-run", action="store_true", help="Estimate only; never write files.")
    ai_usage_plan.add_argument("--format", choices=["json"], default="json", help="Output format.")
    ai_usage_plan.set_defaults(func=command_ai_usage_plan)

    ai_usage_record = subcommands.add_parser(
        "ai-usage-record",
        help="Record a reviewed non-secret AI token usage receipt.",
    )
    ai_usage_record.add_argument("archive_root", help="Archive root to write the usage receipt into.")
    ai_usage_record.add_argument("--task-id", required=True, help="Safe non-secret task/session id.")
    ai_usage_record.add_argument("--runtime", required=True, help="Safe non-secret AI runtime label.")
    ai_usage_record.add_argument("--model", required=True, help="Safe non-secret model label.")
    ai_usage_record.add_argument("--purpose", required=True, help="Safe non-secret purpose label.")
    ai_usage_record.add_argument("--input-tokens", type=int, required=True, help="Reported prompt/input token count.")
    ai_usage_record.add_argument("--output-tokens", type=int, required=True, help="Reported completion/output token count.")
    ai_usage_record.add_argument("--total-tokens", type=int, help="Reported total token count. Defaults to input + output.")
    ai_usage_record.add_argument("--cached-input-tokens", type=int, help="Reported cached input token count, if available.")
    ai_usage_record.add_argument("--reasoning-tokens", type=int, help="Reported reasoning token count, if available.")
    ai_usage_record.add_argument("--budget-tokens", type=int, help="Optional budget used for the call.")
    ai_usage_record.add_argument("--planned-tokens", type=int, help="Optional estimated context tokens from ai-usage-plan.")
    ai_usage_record.add_argument("--context-plan-sha256", help="Optional sha256:<hex> hash for an external context plan record.")
    ai_usage_record.add_argument("--dry-run", action="store_true", help="Preview the receipt only; never write files.")
    ai_usage_record.add_argument("--approve", action="store_true", help="Approve writing the usage receipt.")
    ai_usage_record.add_argument("--reviewed-by", help="Safe non-secret actor id required when --approve is used.")
    ai_usage_record.add_argument("--format", choices=["json"], default="json", help="Output format.")
    ai_usage_record.set_defaults(func=command_ai_usage_record)

    ai_usage_report = subcommands.add_parser(
        "ai-usage-report",
        help="Aggregate local AI usage receipts without reading prompts or responses.",
    )
    ai_usage_report.add_argument("archive_root", help="Archive root to inspect.")
    ai_usage_report.add_argument("--task-id", help="Optional safe task id filter.")
    ai_usage_report.add_argument("--runtime", help="Optional safe runtime filter.")
    ai_usage_report.add_argument("--model", help="Optional safe model filter.")
    ai_usage_report.add_argument("--dry-run", action="store_true", help="Read receipts only; never write files.")
    ai_usage_report.add_argument("--format", choices=["json"], default="json", help="Output format.")
    ai_usage_report.set_defaults(func=command_ai_usage_report)

    prompt_boundary = subcommands.add_parser(
        "prompt-boundary",
        help="Dry-run prompt-injection boundary check for untrusted text.",
    )
    prompt_boundary.add_argument("archive_root", help="Archive root used for context.")
    prompt_boundary.add_argument("--text", help="Inline untrusted text to inspect.")
    prompt_boundary.add_argument("--path", help="Archive-relative zet or text path to inspect.")
    prompt_boundary.add_argument("--dry-run", action="store_true", help="Preview only; never execute inspected text.")
    prompt_boundary.add_argument("--format", choices=["json"], default="json", help="Output format.")
    prompt_boundary.set_defaults(func=command_prompt_boundary)

    github_repo = subcommands.add_parser(
        "github-repo",
        help="Plan GitHub repository setup for a WOM profile without creating the repository.",
    )
    github_repo.add_argument("archive_root", help="Archive root to plan for.")
    github_repo.add_argument("--dry-run", action="store_true", help="Preview local metadata and manual GitHub steps without writing files.")
    github_repo.add_argument("--profile-id", help="Resolved WOM profile id.")
    github_repo.add_argument("--profile-slug", help="ASCII profile slug used in the proposed repository name.")
    github_repo.add_argument("--github-owner", help="GitHub user or organization name.")
    github_repo.add_argument("--github-account-ref", help="Safe GitHub account reference such as github:account:example.")
    github_repo.add_argument("--repo-name", help="Override repository name. Must keep the zettel-kasten- prefix.")
    github_repo.add_argument(
        "--visibility",
        choices=sorted(archive_services.GITHUB_REPOSITORY_ALLOWED_VISIBILITIES),
        default=archive_services.GITHUB_REPOSITORY_DEFAULT_VISIBILITY,
        help="Proposed repository visibility. Defaults to private.",
    )
    github_repo.add_argument(
        "--remote-protocol",
        choices=sorted(archive_services.GITHUB_REPOSITORY_REMOTE_PROTOCOLS),
        default=archive_services.GITHUB_REPOSITORY_DEFAULT_REMOTE_PROTOCOL,
        help="Planned local remote protocol. Defaults to ssh.",
    )
    github_repo.add_argument(
        "--approve",
        action="store_true",
        help="Write versioned provider metadata and a setup receipt only; never create or connect a GitHub repository.",
    )
    github_repo.add_argument("--reviewed-by", help="Reviewer id required with --approve.")
    github_repo.add_argument(
        "--write-local-profile",
        action="store_true",
        help="Write ignored local GitHub account hints under profiles/local/ when approving.",
    )
    github_repo.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    github_repo.set_defaults(func=command_github_repo)

    object_storage = subcommands.add_parser(
        "object-storage",
        help="Plan object storage setup for WOM objets without creating buckets or uploading files.",
    )
    object_storage.add_argument("archive_root", help="Archive root to plan for.")
    object_storage.add_argument("--dry-run", action="store_true", help="Preview local metadata and manual object storage steps without writing files.")
    object_storage.add_argument("--provider", help="Provider kind: cloudflare-r2, aws-s3, backblaze-b2, google-cloud-storage, or generic-s3.")
    object_storage.add_argument("--profile-id", help="Resolved WOM profile id.")
    object_storage.add_argument("--profile-slug", help="ASCII profile slug used in the proposed bucket/container name.")
    object_storage.add_argument("--storage-account-ref", help="Safe storage account reference such as storage:account:example.")
    object_storage.add_argument("--bucket-name", help="Override bucket/container name. Must pass conservative lowercase safety rules.")
    object_storage.add_argument("--region", help="Safe provider region label. Defaults to auto.")
    object_storage.add_argument("--endpoint-ref", help="Safe endpoint reference. Do not pass raw provider URLs.")
    object_storage.add_argument("--objet-prefix", help="Provider-relative prefix for WOM objets. Defaults to archives/<archive_id>/objets/.")
    object_storage.add_argument(
        "--visibility",
        choices=sorted(archive_services.OBJECT_STORAGE_ALLOWED_VISIBILITIES),
        default=archive_services.OBJECT_STORAGE_DEFAULT_VISIBILITY,
        help="Proposed bucket/container visibility. Defaults to private.",
    )
    object_storage.add_argument(
        "--approve",
        action="store_true",
        help="Write versioned provider metadata and a setup receipt only; never create buckets, upload, sync, copy, or hash files.",
    )
    object_storage.add_argument("--reviewed-by", help="Reviewer id required with --approve.")
    object_storage.add_argument(
        "--write-local-profile",
        action="store_true",
        help="Write ignored local object storage account hints under profiles/local/ when approving.",
    )
    object_storage.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    object_storage.set_defaults(func=command_object_storage)

    object_storage_recommendation = subcommands.add_parser(
        "object-storage-recommendation",
        aliases=["object-storage-match", "objet-storage-recommendation"],
        help="Recommend an object storage provider path before setup planning.",
    )
    object_storage_recommendation.add_argument("archive_root", help="Archive root to inspect.")
    object_storage_recommendation.add_argument(
        "--scenario",
        choices=sorted(archive_services.OBJECT_STORAGE_RECOMMENDATION_SCENARIOS),
        default="personal_low_ops",
        help="Human object-storage usage scenario.",
    )
    object_storage_recommendation.add_argument("--profile-id", help="Optional safe profile id for the next object-storage dry-run command.")
    object_storage_recommendation.add_argument("--profile-slug", help="Optional safe ASCII profile slug for the next object-storage dry-run command.")
    object_storage_recommendation.add_argument("--storage-account-ref", help="Optional safe storage account ref for the next object-storage dry-run command.")
    object_storage_recommendation.add_argument("--dry-run", action="store_true", help="Required; recommendation only.")
    object_storage_recommendation.add_argument("--format", choices=["text", "json"], default="json", help="Output format.")
    object_storage_recommendation.set_defaults(func=command_object_storage_recommendation)

    human_artifact_store = subcommands.add_parser(
        "human-artifact-store",
        help="Plan a user-facing note/workspace/publication surface without calling providers.",
    )
    human_artifact_store.add_argument("archive_root", help="Archive root to plan for.")
    human_artifact_store.add_argument("--dry-run", action="store_true", help="Preview the surface contract without writing files.")
    human_artifact_store.add_argument(
        "--surface-kind",
        choices=sorted(archive_services.HUMAN_ARTIFACT_SURFACE_KINDS),
        required=True,
        help="User-facing app/surface kind to plan for.",
    )
    human_artifact_store.add_argument("--surface-ref", help="Optional safe app-level label/ref; never pass a URL, email, path, or token.")
    human_artifact_store.add_argument(
        "--role",
        choices=sorted(archive_services.HUMAN_ARTIFACT_ROLES),
        default=archive_services.HUMAN_ARTIFACT_DEFAULT_ROLE,
        help="Role this app should play in the archive model.",
    )
    human_artifact_store.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    human_artifact_store.set_defaults(func=command_human_artifact_store)

    prehashed_objet_ledger = subcommands.add_parser(
        "prehashed-objet-ledger",
        help="Preview an already-hashed external objet ledger without reading blob bytes.",
    )
    prehashed_objet_ledger.add_argument("archive_root", help="Archive root to plan for.")
    prehashed_objet_ledger.add_argument(
        "--ledger",
        action="append",
        required=True,
        help="UTF-8 JSONL ledger with sha256 and byte-size fields. May be repeated.",
    )
    prehashed_objet_ledger.add_argument(
        "--store-kind",
        choices=sorted(archive_services.PREHASHED_OBJET_LEDGER_STORE_KINDS),
        default="generic_content_addressed_store",
        help="External store context for the preview.",
    )
    prehashed_objet_ledger.add_argument("--store-ref", help="Safe external store label/ref required when --approve is used.")
    prehashed_objet_ledger.add_argument("--sha256-field", default="sha256", help="JSONL field containing sha256 or sha256:<hex>.")
    prehashed_objet_ledger.add_argument("--size-field", default="bytes", help="JSONL field containing byte size.")
    prehashed_objet_ledger.add_argument("--mime-field", default="mime", help="Optional JSONL field containing a safe MIME type.")
    prehashed_objet_ledger.add_argument("--max-rows", type=int, default=100000, help="Maximum rows to inspect.")
    prehashed_objet_ledger.add_argument("--dry-run", action="store_true", help="Preview ledger registration without writing.")
    prehashed_objet_ledger.add_argument("--approve", action="store_true", help="Append reviewed external manifest records and write a receipt.")
    prehashed_objet_ledger.add_argument("--reviewed-by", help="Reviewer id required when --approve is used.")
    prehashed_objet_ledger.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    prehashed_objet_ledger.set_defaults(func=command_prehashed_objet_ledger)

    object_storage_upload_evidence = subcommands.add_parser(
        "object-storage-upload-evidence",
        aliases=["object-storage-external-upload-evidence", "objet-storage-upload-evidence"],
        help="Record reviewed external object-storage upload evidence without calling providers.",
    )
    object_storage_upload_evidence.add_argument("archive_root", help="Archive root to update.")
    object_storage_upload_evidence.add_argument(
        "--ledger",
        action="append",
        required=True,
        help="UTF-8 JSONL upload evidence ledger. May be repeated. Paths are not echoed.",
    )
    object_storage_upload_evidence.add_argument(
        "--provider-kind",
        choices=sorted(archive_services.OBJECT_STORAGE_ALLOWED_PROVIDERS),
        default="cloudflare-r2",
        help="Object-storage provider kind label.",
    )
    object_storage_upload_evidence.add_argument(
        "--store-ref",
        help="Safe store label/ref. Required with --approve. Do not pass URLs, bucket names, paths, tokens, or secrets.",
    )
    object_storage_upload_evidence.add_argument("--sha256-field", default="sha256", help="JSONL field containing sha256 or sha256:<hex>.")
    object_storage_upload_evidence.add_argument("--size-field", default="bytes", help="Optional JSONL field containing byte size.")
    object_storage_upload_evidence.add_argument(
        "--status-field",
        default="status",
        help="JSONL field whose value must be uploaded, verified, succeeded, already_present, or ok.",
    )
    object_storage_upload_evidence.add_argument("--max-rows", type=int, default=100000, help="Maximum rows to inspect.")
    object_storage_upload_evidence.add_argument("--dry-run", action="store_true", help="Preview manifest location updates without writing.")
    object_storage_upload_evidence.add_argument("--approve", action="store_true", help="Write reviewed upload evidence receipt and manifest locations.")
    object_storage_upload_evidence.add_argument("--reviewed-by", help="Reviewer id required when --approve is used.")
    object_storage_upload_evidence.add_argument("--format", choices=["text", "json"], default="json", help="Output format.")
    object_storage_upload_evidence.set_defaults(func=command_object_storage_upload_evidence)

    object_storage_upload_evidence_audit = subcommands.add_parser(
        "object-storage-upload-evidence-audit",
        aliases=["object-storage-external-upload-evidence-audit", "objet-storage-upload-evidence-audit"],
        help="Audit an object-storage upload evidence receipt without calling providers.",
    )
    object_storage_upload_evidence_audit.add_argument("archive_root", help="Archive root to inspect.")
    object_storage_upload_evidence_audit.add_argument(
        "--receipt",
        required=True,
        help="Archive-relative receipts/providers/object-storage-upload-evidence/*.json path. The exact path is not echoed.",
    )
    object_storage_upload_evidence_audit.add_argument(
        "--dry-run",
        action="store_true",
        help="Required. Audit only; never calls providers, reads object bytes, retrieves secrets, or writes files.",
    )
    object_storage_upload_evidence_audit.add_argument("--format", choices=["text", "json"], default="json", help="Output format.")
    object_storage_upload_evidence_audit.set_defaults(func=command_object_storage_upload_evidence_audit)

    resolve_objet_ref = subcommands.add_parser(
        "resolve-objet-ref",
        help="Resolve one sha256 objet reference to safe local/external candidates without opening providers.",
    )
    resolve_objet_ref.add_argument("archive_root", help="Archive root to inspect.")
    resolve_objet_ref.add_argument("--object-id", required=True, help="Object id formatted as sha256:<64 hex> or bare 64 hex.")
    resolve_objet_ref.add_argument("--dry-run", action="store_true", help="Required. Read manifests only; never writes, downloads, or calls providers.")
    resolve_objet_ref.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    resolve_objet_ref.set_defaults(func=command_resolve_objet_ref)

    presigned_url_plan = subcommands.add_parser(
        "presigned-url-plan",
        aliases=["object-presigned-url-plan", "objet-presigned-url-plan"],
        help="Plan a future provider presigned URL request without creating URLs.",
    )
    presigned_url_plan.add_argument("archive_root", help="Archive root to inspect.")
    presigned_url_plan.add_argument("--object-id", required=True, help="Object id formatted as sha256:<64 hex> or bare 64 hex.")
    presigned_url_plan.add_argument("--store-ref", help="Safe external store label/ref. Do not pass a URL, path, token, or secret.")
    presigned_url_plan.add_argument(
        "--operation",
        choices=sorted(archive_services.PRESIGNED_URL_OPERATIONS),
        default="download",
        help="Future presigned URL operation to plan.",
    )
    presigned_url_plan.add_argument(
        "--ttl-seconds",
        type=int,
        default=archive_services.PRESIGNED_URL_DEFAULT_TTL_SECONDS,
        help="Future URL TTL to plan. Must be between 60 and 86400 seconds.",
    )
    presigned_url_plan.add_argument("--dry-run", action="store_true", help="Required. Plan only; never creates URLs or calls providers.")
    presigned_url_plan.add_argument("--format", choices=["text", "json"], default="json", help="Output format.")
    presigned_url_plan.set_defaults(func=command_presigned_url_plan)

    object_storage_operation_request = subcommands.add_parser(
        "object-storage-operation-request-plan",
        aliases=["object-storage-request-plan", "objet-storage-operation-request"],
        help="Compose a read-only approval request package before a future object-storage operation.",
    )
    object_storage_operation_request.add_argument("archive_root", help="Archive root to inspect.")
    object_storage_operation_request.add_argument(
        "--operation",
        choices=sorted(archive_services.OBJECT_STORAGE_ADAPTER_OPERATIONS),
        default="presigned_download",
        help="Future object-storage operation to request.",
    )
    object_storage_operation_request.add_argument("--object-id", help="Object id formatted as sha256:<64 hex> or bare 64 hex.")
    object_storage_operation_request.add_argument("--store-ref", help="Safe external store label/ref. Do not pass a URL, path, token, or secret.")
    object_storage_operation_request.add_argument(
        "--ttl-seconds",
        type=int,
        default=archive_services.PRESIGNED_URL_DEFAULT_TTL_SECONDS,
        help="Future presigned URL TTL to plan. Must be between 60 and 86400 seconds.",
    )
    object_storage_operation_request.add_argument(
        "--provider-ref",
        help="Optional safe provider binding label/ref. Do not pass a URL, path, token, or secret.",
    )
    object_storage_operation_request.add_argument(
        "--credential-id",
        default="cred:object-storage",
        help="Safe credential label for the future object-storage token.",
    )
    object_storage_operation_request.add_argument("--credential-ref", help="Optional env/keyring/secret/wallet ref; exact value is not echoed.")
    object_storage_operation_request.add_argument(
        "--credential-kind",
        choices=sorted(archive_services.CREDENTIAL_REF_ALLOWED_KINDS),
        help="Credential kind. Defaults to object_storage_token.",
    )
    object_storage_operation_request.add_argument(
        "--provider",
        choices=sorted(archive_services.CREDENTIAL_REF_ALLOWED_PROVIDERS),
        help="Credential provider label. Defaults from credential kind.",
    )
    object_storage_operation_request.add_argument(
        "--store-kind",
        choices=sorted(archive_services.CREDENTIAL_ACCESS_BROKER_STORE_KINDS),
        default="password_manager",
        help="Credential store class for the future token retrieval.",
    )
    object_storage_operation_request.add_argument(
        "--adapter-kind",
        choices=sorted(archive_services.CREDENTIAL_ADAPTER_KINDS),
        help="Future credential adapter kind. Defaults from store kind and platform.",
    )
    object_storage_operation_request.add_argument(
        "--approval-decision",
        choices=sorted(archive_services.CREDENTIAL_ACCESS_APPROVAL_DECISIONS),
        default="needs_review",
        help="Human decision state to evaluate.",
    )
    object_storage_operation_request.add_argument(
        "--approval-receipt",
        help="Archive-relative approval receipt path to verify. The path is not echoed in output.",
    )
    object_storage_operation_request.add_argument("--consumer", default="wom:adapter:object-storage", help="Safe label for the future adapter.")
    object_storage_operation_request.add_argument("--reviewed-by", default="human:pending-review", help="Safe non-secret reviewer label.")
    object_storage_operation_request.add_argument(
        "--platform",
        choices=sorted(archive_services.CREDENTIAL_STORE_RECOMMENDATION_PLATFORMS),
        default="windows",
        help="Local platform for default credential adapter selection.",
    )
    object_storage_operation_request.add_argument("--dry-run", action="store_true", help="Required. Plan only; never calls providers or reads secrets.")
    object_storage_operation_request.add_argument("--format", choices=["text", "json"], default="json", help="Output format.")
    object_storage_operation_request.set_defaults(func=command_object_storage_operation_request_plan)

    object_storage_adapter_execution_contract = subcommands.add_parser(
        "object-storage-adapter-execution-contract",
        aliases=["object-storage-upload-execution-contract", "objet-storage-adapter-execution-contract"],
        help="Preview the read-only execution contract a future object-storage upload adapter must satisfy.",
    )
    object_storage_adapter_execution_contract.add_argument("archive_root", help="Archive root to inspect.")
    object_storage_adapter_execution_contract.add_argument(
        "--operation",
        choices=sorted(archive_services.OBJECT_STORAGE_ADAPTER_EXECUTION_CONTRACT_OPERATIONS),
        default="upload_object",
        help="Future object-storage adapter operation to contract. v0.3.78 covers upload_object.",
    )
    object_storage_adapter_execution_contract.add_argument("--object-id", help="Optional object id formatted as sha256:<64 hex> or bare 64 hex.")
    object_storage_adapter_execution_contract.add_argument("--store-ref", help="Optional safe external store label/ref. Do not pass a URL, path, token, or secret.")
    object_storage_adapter_execution_contract.add_argument(
        "--provider-ref",
        help="Optional safe provider binding label/ref. Do not pass a URL, path, token, or secret.",
    )
    object_storage_adapter_execution_contract.add_argument(
        "--dry-run",
        action="store_true",
        help="Required. Contract only; never uploads, reads object bytes, calls providers, retrieves secrets, or writes files.",
    )
    object_storage_adapter_execution_contract.add_argument("--format", choices=["text", "json"], default="json", help="Output format.")
    object_storage_adapter_execution_contract.set_defaults(func=command_object_storage_adapter_execution_contract)

    imap_mailbox_operation_request = subcommands.add_parser(
        "imap-mailbox-operation-request-plan",
        aliases=["imap-mailbox-request-plan", "mailbox-operation-request-plan"],
        help="Compose a read-only approval request package before a future IMAP mailbox operation.",
    )
    imap_mailbox_operation_request.add_argument("archive_root", help="Archive root to inspect.")
    imap_mailbox_operation_request.add_argument("--source-id", required=True, help="Stable source id, e.g. imap:gmail-personal.")
    imap_mailbox_operation_request.add_argument(
        "--provider",
        choices=sorted(archive_services.IMAP_MAILBOX_ALLOWED_PROVIDERS),
        default="generic_imap",
        help="Provider preset. generic_imap requires --imap-host.",
    )
    imap_mailbox_operation_request.add_argument("--imap-host", help="Safe IMAP host label. Required for generic_imap.")
    imap_mailbox_operation_request.add_argument("--imap-port", type=int, default=993, help="IMAP SSL port. Defaults to 993.")
    imap_mailbox_operation_request.add_argument(
        "--account-ref",
        required=True,
        help="Safe account reference, e.g. imap:account:personal-mail. Do not pass an email address.",
    )
    imap_mailbox_operation_request.add_argument(
        "--username-ref",
        required=True,
        help="env/keyring/secret/wallet reference for the username. Do not pass the username value.",
    )
    imap_mailbox_operation_request.add_argument(
        "--auth-mode",
        choices=sorted(archive_services.IMAP_MAILBOX_ALLOWED_AUTH_MODES),
        default="app_password_ref",
        help="Credential reference kind.",
    )
    imap_mailbox_operation_request.add_argument(
        "--app-password-ref",
        help="env/keyring/secret/wallet reference for an app password. Do not pass the password value.",
    )
    imap_mailbox_operation_request.add_argument(
        "--oauth-token-ref",
        help="env/keyring/secret/wallet reference for an OAuth token. Do not pass the token value.",
    )
    imap_mailbox_operation_request.add_argument(
        "--mailbox-ref",
        default="imap:mailbox:inbox",
        help="Safe mailbox reference. Do not pass private mailbox names.",
    )
    imap_mailbox_operation_request.add_argument(
        "--operation",
        choices=sorted(archive_services.IMAP_MAILBOX_OPERATION_REQUEST_OPERATIONS),
        default="header_metadata_scan",
        help="Future IMAP mailbox operation to request.",
    )
    imap_mailbox_operation_request.add_argument(
        "--max-messages",
        type=int,
        default=archive_services.IMAP_MAILBOX_OPERATION_MAX_MESSAGES_DEFAULT,
        help="Future message limit to request. Must be between 1 and 2000.",
    )
    imap_mailbox_operation_request.add_argument(
        "--since-days",
        type=int,
        help="Optional future recency window. Must be between 1 and 3650 days.",
    )
    imap_mailbox_operation_request.add_argument(
        "--credential-id",
        default="cred:mail-source-access",
        help="Safe credential label for the future mail credential.",
    )
    imap_mailbox_operation_request.add_argument("--credential-ref", help="Optional env/keyring/secret/wallet ref; exact value is not echoed.")
    imap_mailbox_operation_request.add_argument(
        "--credential-kind",
        choices=sorted(archive_services.CREDENTIAL_REF_ALLOWED_KINDS),
        help="Credential kind. Defaults from IMAP auth mode.",
    )
    imap_mailbox_operation_request.add_argument(
        "--credential-provider",
        choices=sorted(archive_services.CREDENTIAL_REF_ALLOWED_PROVIDERS),
        help="Credential provider label. Defaults from IMAP provider.",
    )
    imap_mailbox_operation_request.add_argument(
        "--store-kind",
        choices=sorted(archive_services.CREDENTIAL_ACCESS_BROKER_STORE_KINDS),
        default="password_manager",
        help="Credential store class for the future mail credential retrieval.",
    )
    imap_mailbox_operation_request.add_argument(
        "--adapter-kind",
        choices=sorted(archive_services.CREDENTIAL_ADAPTER_KINDS),
        help="Future credential adapter kind. Defaults from store kind and platform.",
    )
    imap_mailbox_operation_request.add_argument(
        "--approval-decision",
        choices=sorted(archive_services.CREDENTIAL_ACCESS_APPROVAL_DECISIONS),
        default="needs_review",
        help="Human decision state to evaluate.",
    )
    imap_mailbox_operation_request.add_argument(
        "--approval-receipt",
        help="Archive-relative approval receipt path to verify. The path is not echoed in output.",
    )
    imap_mailbox_operation_request.add_argument("--consumer", default="wom:adapter:imap-mailbox", help="Safe label for the future adapter.")
    imap_mailbox_operation_request.add_argument("--reviewed-by", default="human:pending-review", help="Safe non-secret reviewer label.")
    imap_mailbox_operation_request.add_argument(
        "--platform",
        choices=sorted(archive_services.CREDENTIAL_STORE_RECOMMENDATION_PLATFORMS),
        default="windows",
        help="Local platform for default credential adapter selection.",
    )
    imap_mailbox_operation_request.add_argument("--dry-run", action="store_true", help="Required. Plan only; never connects to IMAP or reads secrets.")
    imap_mailbox_operation_request.add_argument("--format", choices=["text", "json"], default="json", help="Output format.")
    imap_mailbox_operation_request.set_defaults(func=command_imap_mailbox_operation_request_plan)

    imap_mailbox_plan = subcommands.add_parser(
        "imap-mailbox-plan",
        help="Plan a read-only IMAP mailbox source without connecting or storing secrets.",
    )
    imap_mailbox_plan.add_argument("archive_root", help="Archive root to inspect.")
    imap_mailbox_plan.add_argument("--source-id", required=True, help="Stable source id, e.g. imap:gmail-personal.")
    imap_mailbox_plan.add_argument(
        "--provider",
        choices=sorted(archive_services.IMAP_MAILBOX_ALLOWED_PROVIDERS),
        default="generic_imap",
        help="Provider preset. generic_imap requires --imap-host.",
    )
    imap_mailbox_plan.add_argument("--imap-host", help="Safe IMAP host label. Required for generic_imap.")
    imap_mailbox_plan.add_argument("--imap-port", type=int, default=993, help="IMAP SSL port. Defaults to 993.")
    imap_mailbox_plan.add_argument(
        "--account-ref",
        required=True,
        help="Safe account reference, e.g. imap:account:personal-mail. Do not pass an email address.",
    )
    imap_mailbox_plan.add_argument(
        "--username-ref",
        required=True,
        help="env/keyring/secret/wallet reference for the username. Do not pass the username value.",
    )
    imap_mailbox_plan.add_argument(
        "--auth-mode",
        choices=sorted(archive_services.IMAP_MAILBOX_ALLOWED_AUTH_MODES),
        default="app_password_ref",
        help="Credential reference kind.",
    )
    imap_mailbox_plan.add_argument(
        "--app-password-ref",
        help="env/keyring/secret/wallet reference for an app password. Do not pass the password value.",
    )
    imap_mailbox_plan.add_argument(
        "--oauth-token-ref",
        help="env/keyring/secret/wallet reference for an OAuth token. Do not pass the token value.",
    )
    imap_mailbox_plan.add_argument(
        "--mailbox-ref",
        default="imap:mailbox:inbox",
        help="Safe mailbox reference. Do not pass private mailbox names.",
    )
    imap_mailbox_plan.add_argument("--dry-run", action="store_true", help="Required; plan only.")
    imap_mailbox_plan.add_argument("--format", choices=["text", "json"], default="json", help="Output format.")
    imap_mailbox_plan.set_defaults(func=command_imap_mailbox_plan)

    credential_ref_plan = subcommands.add_parser(
        "credential-ref-plan",
        help="Plan a local credential reference without reading or storing secret values.",
    )
    credential_ref_plan.add_argument("archive_root", help="Archive root to inspect.")
    credential_ref_plan.add_argument("--credential-id", required=True, help="Safe label, e.g. cred:openai-api.")
    credential_ref_plan.add_argument(
        "--credential-ref",
        required=True,
        help="env/keyring/secret/wallet reference. Do not pass the actual secret value.",
    )
    credential_ref_plan.add_argument(
        "--credential-kind",
        choices=sorted(archive_services.CREDENTIAL_REF_ALLOWED_KINDS),
        default="generic_secret",
        help="Kind of credential this ref points to.",
    )
    credential_ref_plan.add_argument(
        "--purpose",
        choices=sorted(archive_services.CREDENTIAL_REF_ALLOWED_PURPOSES),
        help="Optional intended use; defaults from credential kind.",
    )
    credential_ref_plan.add_argument(
        "--provider",
        choices=sorted(archive_services.CREDENTIAL_REF_ALLOWED_PROVIDERS),
        help="Optional provider context; defaults from credential kind.",
    )
    credential_ref_plan.add_argument("--dry-run", action="store_true", help="Required; plan only.")
    credential_ref_plan.add_argument("--format", choices=["text", "json"], default="json", help="Output format.")
    credential_ref_plan.set_defaults(func=command_credential_ref_plan)

    credential_ref_inventory = subcommands.add_parser(
        "credential-ref-inventory",
        aliases=["credentials", "credential-status"],
        help="List known credential refs without echoing ref values or secrets.",
    )
    credential_ref_inventory.add_argument("archive_root", help="Archive root to inspect.")
    credential_ref_inventory.add_argument("--dry-run", action="store_true", help="Required; read-only inventory.")
    credential_ref_inventory.add_argument("--format", choices=["text", "json"], default="json", help="Output format.")
    credential_ref_inventory.set_defaults(func=command_credential_ref_inventory)

    connected_accounts = subcommands.add_parser(
        "connected-accounts",
        aliases=["accounts", "account-status"],
        help="Summarize connected provider/source accounts and credential store types without reading secrets.",
    )
    connected_accounts.add_argument("archive_root", help="Archive root to inspect.")
    connected_accounts.add_argument("--include-disabled", action="store_true", help="Include disabled bindings in the metadata-only overview.")
    connected_accounts.add_argument("--dry-run", action="store_true", help="Required; read-only account bridge.")
    connected_accounts.add_argument("--format", choices=["text", "json"], default="json", help="Output format.")
    connected_accounts.set_defaults(func=command_connected_accounts)

    credential_store_recommendation = subcommands.add_parser(
        "credential-store-recommendation",
        aliases=["credential-store-plan", "secret-store-recommendation"],
        help="Recommend a secret store class for a human scenario without reading secrets.",
    )
    credential_store_recommendation.add_argument("archive_root", help="Archive root to inspect.")
    credential_store_recommendation.add_argument(
        "--scenario",
        choices=sorted(archive_services.CREDENTIAL_STORE_RECOMMENDATION_SCENARIOS),
        required=True,
        help="Human secret-vault usage scenario.",
    )
    credential_store_recommendation.add_argument(
        "--platform",
        choices=sorted(archive_services.CREDENTIAL_STORE_RECOMMENDATION_PLATFORMS),
        default="windows",
        help="Host platform for OS keyring wording.",
    )
    credential_store_recommendation.add_argument("--dry-run", action="store_true", help="Required; read-only recommendation.")
    credential_store_recommendation.add_argument("--format", choices=["text", "json"], default="json", help="Output format.")
    credential_store_recommendation.set_defaults(func=command_credential_store_recommendation)

    credential_vault_onboarding_plan = subcommands.add_parser(
        "credential-vault-onboarding-plan",
        aliases=["credential-vault-onboarding", "secret-vault-onboarding-plan"],
        help="Plan safe human vault onboarding without opening or reading a vault.",
    )
    credential_vault_onboarding_plan.add_argument("archive_root", help="Archive root to inspect.")
    credential_vault_onboarding_plan.add_argument(
        "--scenario",
        choices=sorted(archive_services.CREDENTIAL_STORE_RECOMMENDATION_SCENARIOS),
        required=True,
        help="Human secret-vault usage scenario.",
    )
    credential_vault_onboarding_plan.add_argument(
        "--store-id",
        choices=sorted(archive_services.CREDENTIAL_VAULT_ONBOARDING_STORE_IDS),
        default="recommended",
        help="Selected external vault/store family. Defaults to the scenario recommendation.",
    )
    credential_vault_onboarding_plan.add_argument("--credential-id", help="Optional safe credential label, e.g. cred:openai-api.")
    credential_vault_onboarding_plan.add_argument(
        "--credential-kind",
        choices=sorted(archive_services.CREDENTIAL_REF_ALLOWED_KINDS),
        help="Optional credential kind; defaults from action kind.",
    )
    credential_vault_onboarding_plan.add_argument(
        "--provider",
        choices=sorted(archive_services.CREDENTIAL_REF_ALLOWED_PROVIDERS),
        help="Optional provider context.",
    )
    credential_vault_onboarding_plan.add_argument(
        "--action-kind",
        choices=sorted(archive_services.CREDENTIAL_ACCESS_BROKER_ACTIONS),
        help="Optional future action; defaults from scenario.",
    )
    credential_vault_onboarding_plan.add_argument(
        "--platform",
        choices=sorted(archive_services.CREDENTIAL_STORE_RECOMMENDATION_PLATFORMS),
        default="windows",
        help="Host platform for OS keyring wording.",
    )
    credential_vault_onboarding_plan.add_argument("--dry-run", action="store_true", help="Required; read-only onboarding plan.")
    credential_vault_onboarding_plan.add_argument("--format", choices=["text", "json"], default="json", help="Output format.")
    credential_vault_onboarding_plan.set_defaults(func=command_credential_vault_onboarding_plan)

    beginner_setup_manual = subcommands.add_parser(
        "beginner-setup-manual",
        aliases=["first-use-setup-manual", "setup-manual"],
        help="Print beginner-friendly secret vault and text-tool setup steps without reading secrets.",
    )
    beginner_setup_manual.add_argument("archive_root", help="Archive root to inspect.")
    beginner_setup_manual.add_argument(
        "--topic",
        choices=sorted(archive_services.BEGINNER_SETUP_MANUAL_TOPICS),
        default="first_secret_and_text_tools",
        help="Setup manual topic.",
    )
    beginner_setup_manual.add_argument(
        "--scenario",
        choices=sorted(archive_services.CREDENTIAL_STORE_RECOMMENDATION_SCENARIOS),
        default="personal_local_first",
        help="Human secret-vault usage scenario.",
    )
    beginner_setup_manual.add_argument(
        "--store-id",
        choices=sorted(archive_services.CREDENTIAL_VAULT_ONBOARDING_STORE_IDS),
        default="recommended",
        help="Selected external vault/store family. Defaults to the scenario recommendation.",
    )
    beginner_setup_manual.add_argument(
        "--platform",
        choices=sorted(archive_services.CREDENTIAL_STORE_RECOMMENDATION_PLATFORMS),
        default="windows",
        help="Host platform for OS keyring wording.",
    )
    beginner_setup_manual.add_argument("--dry-run", action="store_true", help="Required; read-only manual.")
    beginner_setup_manual.add_argument("--format", choices=["text", "json"], default="json", help="Output format.")
    beginner_setup_manual.set_defaults(func=command_beginner_setup_manual)

    ai_response_concept_guide = subcommands.add_parser(
        "ai-response-concept-guide",
        aliases=["ai-concept-guide", "wom-concept-guide"],
        help="Print beginner-friendly AI explanation cards for WOM object identity and evidence layers.",
    )
    ai_response_concept_guide.add_argument("archive_root", help="Archive root to inspect.")
    ai_response_concept_guide.add_argument(
        "--topic",
        choices=sorted(archive_services.AI_RESPONSE_CONCEPT_GUIDE_TOPICS),
        default="all",
        help="Explanation topic.",
    )
    ai_response_concept_guide.add_argument(
        "--locale",
        default="ko-KR",
        help="Human-facing language for operational term translations. Supports ko-KR and en-US.",
    )
    ai_response_concept_guide.add_argument("--dry-run", action="store_true", help="Required; read-only guide.")
    ai_response_concept_guide.add_argument("--format", choices=["text", "json"], default="json", help="Output format.")
    ai_response_concept_guide.set_defaults(func=command_ai_response_concept_guide)

    credential_semantic_extraction_recipe = subcommands.add_parser(
        "credential-semantic-extraction-recipe",
        aliases=["credential-extraction-recipe", "secret-semantic-extraction-recipe"],
        help="Print a read-only semantic recipe for splitting complex credential notes without reading secrets.",
    )
    credential_semantic_extraction_recipe.add_argument("archive_root", help="Archive root to inspect.")
    credential_semantic_extraction_recipe.add_argument(
        "--source-label",
        required=True,
        help="Safe label for the human-selected source. Do not pass a path, email, URL, token, or secret.",
    )
    credential_semantic_extraction_recipe.add_argument(
        "--source-kind",
        choices=sorted(archive_services.CREDENTIAL_SEMANTIC_SOURCE_KINDS),
        default="plaintext_note",
        help="Human-declared source kind; the command still reads no source file.",
    )
    credential_semantic_extraction_recipe.add_argument(
        "--context",
        choices=sorted(archive_services.CREDENTIAL_SEMANTIC_CONTEXTS),
        default="mixed",
        help="Human-declared review context.",
    )
    credential_semantic_extraction_recipe.add_argument(
        "--target-store-id",
        choices=sorted(archive_services.CREDENTIAL_VAULT_ONBOARDING_STORE_IDS),
        default="recommended",
        help="Selected target vault/store family. Defaults to the scenario recommendation.",
    )
    credential_semantic_extraction_recipe.add_argument(
        "--platform",
        choices=sorted(archive_services.CREDENTIAL_STORE_RECOMMENDATION_PLATFORMS),
        default="windows",
        help="Host platform for OS keyring wording.",
    )
    credential_semantic_extraction_recipe.add_argument("--dry-run", action="store_true", help="Required; read-only recipe.")
    credential_semantic_extraction_recipe.add_argument("--format", choices=["text", "json"], default="json", help="Output format.")
    credential_semantic_extraction_recipe.set_defaults(func=command_credential_semantic_extraction_recipe)

    credential_plaintext_migration_plan = subcommands.add_parser(
        "credential-plaintext-migration-plan",
        aliases=["secret-migration-plan", "credential-import-plan"],
        help="Plan safe plaintext-secret migration without reading or importing secrets.",
    )
    credential_plaintext_migration_plan.add_argument("archive_root", help="Archive root to inspect.")
    credential_plaintext_migration_plan.add_argument(
        "--source-label",
        required=True,
        help="Safe label for the human-selected plaintext source. Do not pass a path, email, URL, token, or secret.",
    )
    credential_plaintext_migration_plan.add_argument("--credential-id", required=True, help="Safe credential label, e.g. cred:openai-api.")
    credential_plaintext_migration_plan.add_argument(
        "--target-store-id",
        choices=sorted(archive_services.CREDENTIAL_VAULT_ONBOARDING_STORE_IDS),
        default="recommended",
        help="Selected target vault/store family. Defaults to the scenario recommendation.",
    )
    credential_plaintext_migration_plan.add_argument(
        "--scenario",
        choices=sorted(archive_services.CREDENTIAL_STORE_RECOMMENDATION_SCENARIOS),
        default="personal_local_first",
        help="Human secret-vault usage scenario.",
    )
    credential_plaintext_migration_plan.add_argument(
        "--credential-kind",
        choices=sorted(archive_services.CREDENTIAL_REF_ALLOWED_KINDS),
        help="Optional credential kind; defaults from plaintext migration.",
    )
    credential_plaintext_migration_plan.add_argument(
        "--provider",
        choices=sorted(archive_services.CREDENTIAL_REF_ALLOWED_PROVIDERS),
        help="Optional provider context.",
    )
    credential_plaintext_migration_plan.add_argument(
        "--platform",
        choices=sorted(archive_services.CREDENTIAL_STORE_RECOMMENDATION_PLATFORMS),
        default="windows",
        help="Host platform for OS keyring wording.",
    )
    credential_plaintext_migration_plan.add_argument("--dry-run", action="store_true", help="Required; read-only migration plan.")
    credential_plaintext_migration_plan.add_argument("--format", choices=["text", "json"], default="json", help="Output format.")
    credential_plaintext_migration_plan.set_defaults(func=command_credential_plaintext_migration_plan)

    credential_policy_check = subcommands.add_parser(
        "credential-policy-check",
        aliases=["credential-access-policy-check", "secret-policy-check"],
        help="Check a credential request against the approval policy gate.",
    )
    credential_policy_check.add_argument("archive_root", help="Archive root to inspect.")
    credential_policy_check.add_argument("--credential-id", required=True, help="Safe credential label, e.g. cred:openai-api.")
    credential_policy_check.add_argument("--credential-ref", help="Optional env/keyring/secret/wallet ref; exact value is not echoed.")
    credential_policy_check.add_argument(
        "--credential-kind",
        choices=sorted(archive_services.CREDENTIAL_REF_ALLOWED_KINDS),
        help="Credential kind; defaults from action kind.",
    )
    credential_policy_check.add_argument(
        "--provider",
        choices=sorted(archive_services.CREDENTIAL_REF_ALLOWED_PROVIDERS),
        help="Optional provider context.",
    )
    credential_policy_check.add_argument(
        "--action-kind",
        choices=sorted(archive_services.CREDENTIAL_ACCESS_BROKER_ACTIONS),
        required=True,
        help="Requested action that would need a credential capability.",
    )
    credential_policy_check.add_argument(
        "--approval-decision",
        choices=sorted(archive_services.CREDENTIAL_ACCESS_APPROVAL_DECISIONS),
        default="needs_review",
        help="Human approval decision currently available to the policy gate.",
    )
    credential_policy_check.add_argument(
        "--store-kind",
        choices=sorted(archive_services.CREDENTIAL_ACCESS_BROKER_STORE_KINDS),
        default="password_manager",
        help="External store class that would hold the real secret.",
    )
    credential_policy_check.add_argument(
        "--adapter-kind",
        choices=sorted(archive_services.CREDENTIAL_ADAPTER_KINDS),
        help="Future local adapter class. Defaults from store/platform.",
    )
    credential_policy_check.add_argument(
        "--operation",
        choices=sorted(archive_services.CREDENTIAL_ADAPTER_OPERATIONS),
        help="Future adapter operation. Defaults from action kind.",
    )
    credential_policy_check.add_argument("--consumer", default="wom_local_adapter", help="Safe label for the tool/adapter asking to use the credential.")
    credential_policy_check.add_argument("--reviewed-by", default="human:pending-review", help="Safe non-secret reviewer label.")
    credential_policy_check.add_argument(
        "--platform",
        choices=sorted(archive_services.CREDENTIAL_STORE_RECOMMENDATION_PLATFORMS),
        default="windows",
        help="Host platform for OS keyring wording.",
    )
    credential_policy_check.add_argument(
        "--approval-receipt",
        help="Optional archive-relative credential access approval receipt to verify.",
    )
    credential_policy_check.add_argument("--dry-run", action="store_true", help="Required; read-only policy check.")
    credential_policy_check.add_argument("--format", choices=["text", "json"], default="json", help="Output format.")
    credential_policy_check.set_defaults(func=command_credential_policy_check)

    credential_keepassxc_command_plan = subcommands.add_parser(
        "credential-keepassxc-command-plan",
        aliases=["keepassxc-command-plan", "credential-keepassxc-write-plan"],
        help="Plan a KeePassXC CLI add command after verifying an approval receipt, without executing it.",
    )
    credential_keepassxc_command_plan.add_argument("archive_root", help="Archive root to inspect.")
    credential_keepassxc_command_plan.add_argument("--credential-id", required=True, help="Safe credential label, e.g. cred:openai-api.")
    credential_keepassxc_command_plan.add_argument("--credential-ref", help="Optional secret: ref; exact value is not echoed.")
    credential_keepassxc_command_plan.add_argument(
        "--credential-kind",
        choices=sorted(archive_services.CREDENTIAL_REF_ALLOWED_KINDS),
        help="Credential kind; defaults from action kind.",
    )
    credential_keepassxc_command_plan.add_argument(
        "--provider",
        choices=sorted(archive_services.CREDENTIAL_REF_ALLOWED_PROVIDERS),
        help="Optional provider context.",
    )
    credential_keepassxc_command_plan.add_argument(
        "--action-kind",
        choices=sorted(archive_services.CREDENTIAL_ACCESS_BROKER_ACTIONS),
        default="plaintext_secret_migration",
        help="Credential action to policy-check before planning the command.",
    )
    credential_keepassxc_command_plan.add_argument(
        "--operation",
        choices=["plaintext_secret_migration", "write_new_secret"],
        default="plaintext_secret_migration",
        help="KeePassXC write-like operation to preflight.",
    )
    credential_keepassxc_command_plan.add_argument(
        "--approval-receipt",
        required=True,
        help="Archive-relative credential access approval receipt to verify before planning.",
    )
    credential_keepassxc_command_plan.add_argument(
        "--entry-label",
        required=True,
        help="Safe non-secret KeePassXC entry label. Do not pass an email, URL, token, password, or path.",
    )
    credential_keepassxc_command_plan.add_argument(
        "--group-label",
        help="Optional safe non-secret KeePassXC group label. Do not pass a path.",
    )
    credential_keepassxc_command_plan.add_argument(
        "--database-ref",
        default="keepassxc:human-selected-database",
        help="Safe label for the human-selected database; never pass a .kdbx path.",
    )
    credential_keepassxc_command_plan.add_argument("--consumer", default="wom:adapter:keepassxc", help="Safe label for the future local adapter.")
    credential_keepassxc_command_plan.add_argument("--reviewed-by", default="human:pending-review", help="Safe non-secret reviewer label.")
    credential_keepassxc_command_plan.add_argument(
        "--platform",
        choices=sorted(archive_services.CREDENTIAL_STORE_RECOMMENDATION_PLATFORMS),
        default="windows",
        help="Host platform context.",
    )
    credential_keepassxc_command_plan.add_argument("--dry-run", action="store_true", help="Required; read-only command preflight.")
    credential_keepassxc_command_plan.add_argument("--format", choices=["text", "json"], default="json", help="Output format.")
    credential_keepassxc_command_plan.set_defaults(func=command_credential_keepassxc_command_plan)

    credential_keepassxc_write = subcommands.add_parser(
        "credential-keepassxc-write",
        aliases=["keepassxc-write"],
        help="Execute a minimal KeePassXC CLI add after verifying an approval receipt.",
    )
    credential_keepassxc_write.add_argument("archive_root", help="Archive root to inspect.")
    credential_keepassxc_write.add_argument("--credential-id", required=True, help="Safe credential label, e.g. cred:openai-api.")
    credential_keepassxc_write.add_argument("--credential-ref", help="Optional secret: ref; exact value is not echoed.")
    credential_keepassxc_write.add_argument(
        "--credential-kind",
        choices=sorted(archive_services.CREDENTIAL_REF_ALLOWED_KINDS),
        help="Credential kind; defaults from action kind.",
    )
    credential_keepassxc_write.add_argument(
        "--provider",
        choices=sorted(archive_services.CREDENTIAL_REF_ALLOWED_PROVIDERS),
        help="Optional provider context.",
    )
    credential_keepassxc_write.add_argument(
        "--action-kind",
        choices=sorted(archive_services.CREDENTIAL_ACCESS_BROKER_ACTIONS),
        default="plaintext_secret_migration",
        help="Credential action to policy-check before the write.",
    )
    credential_keepassxc_write.add_argument(
        "--operation",
        choices=["plaintext_secret_migration", "write_new_secret"],
        default="plaintext_secret_migration",
        help="KeePassXC write-like operation to execute.",
    )
    credential_keepassxc_write.add_argument(
        "--approval-receipt",
        required=True,
        help="Archive-relative credential access approval receipt to verify before execution.",
    )
    credential_keepassxc_write.add_argument(
        "--entry-label",
        required=True,
        help="Safe non-secret KeePassXC entry label. Do not pass an email, URL, token, password, or path.",
    )
    credential_keepassxc_write.add_argument(
        "--group-label",
        help="Optional safe non-secret KeePassXC group label. Do not pass a path.",
    )
    credential_keepassxc_write.add_argument(
        "--database-ref",
        default="keepassxc:human-selected-database",
        help="Safe label for the human-selected database; never pass a .kdbx path here.",
    )
    credential_keepassxc_write.add_argument(
        "--database-path",
        help="Local .kdbx path used only for --approve execution. It is not echoed in JSON or receipts.",
    )
    credential_keepassxc_write.add_argument("--consumer", default="wom:adapter:keepassxc", help="Safe label for the local adapter.")
    credential_keepassxc_write.add_argument("--reviewed-by", default="human:pending-review", help="Safe non-secret reviewer label.")
    credential_keepassxc_write.add_argument(
        "--platform",
        choices=sorted(archive_services.CREDENTIAL_STORE_RECOMMENDATION_PLATFORMS),
        default="windows",
        help="Host platform context.",
    )
    credential_keepassxc_write.add_argument("--dry-run", action="store_true", help="Preview the write without executing keepassxc-cli.")
    credential_keepassxc_write.add_argument("--approve", action="store_true", help="Execute keepassxc-cli add after local human approval.")
    credential_keepassxc_write.add_argument("--format", choices=["text", "json"], default="json", help="Output format.")
    credential_keepassxc_write.set_defaults(func=command_credential_keepassxc_write)

    credential_access_broker_plan = subcommands.add_parser(
        "credential-access-broker-plan",
        aliases=["credential-broker-plan", "secret-access-broker-plan"],
        help="Plan a future approved credential broker request without retrieving secrets.",
    )
    credential_access_broker_plan.add_argument("archive_root", help="Archive root to inspect.")
    credential_access_broker_plan.add_argument("--credential-id", required=True, help="Safe credential label, e.g. cred:openai-api.")
    credential_access_broker_plan.add_argument("--credential-ref", help="Optional env/keyring/secret/wallet ref; exact value is not echoed.")
    credential_access_broker_plan.add_argument(
        "--credential-kind",
        choices=sorted(archive_services.CREDENTIAL_REF_ALLOWED_KINDS),
        help="Credential kind; defaults from action kind.",
    )
    credential_access_broker_plan.add_argument(
        "--provider",
        choices=sorted(archive_services.CREDENTIAL_REF_ALLOWED_PROVIDERS),
        help="Optional provider context.",
    )
    credential_access_broker_plan.add_argument(
        "--action-kind",
        choices=sorted(archive_services.CREDENTIAL_ACCESS_BROKER_ACTIONS),
        required=True,
        help="Future action that would need a credential capability.",
    )
    credential_access_broker_plan.add_argument(
        "--store-kind",
        choices=sorted(archive_services.CREDENTIAL_ACCESS_BROKER_STORE_KINDS),
        default="password_manager",
        help="External store class that would hold the real secret.",
    )
    credential_access_broker_plan.add_argument("--consumer", default="wom_local_adapter", help="Safe label for the tool/adapter asking to use the credential.")
    credential_access_broker_plan.add_argument(
        "--platform",
        choices=sorted(archive_services.CREDENTIAL_STORE_RECOMMENDATION_PLATFORMS),
        default="windows",
        help="Host platform for OS keyring wording.",
    )
    credential_access_broker_plan.add_argument("--dry-run", action="store_true", help="Required; read-only broker plan.")
    credential_access_broker_plan.add_argument("--format", choices=["text", "json"], default="json", help="Output format.")
    credential_access_broker_plan.set_defaults(func=command_credential_access_broker_plan)

    credential_access_approval_plan = subcommands.add_parser(
        "credential-access-approval-plan",
        aliases=["credential-access-approval", "secret-access-approval-plan"],
        help="Preview or record a credential access approval receipt without reading secrets.",
    )
    credential_access_approval_plan.add_argument("archive_root", help="Archive root to inspect.")
    credential_access_approval_plan.add_argument("--credential-id", required=True, help="Safe credential label, e.g. cred:openai-api.")
    credential_access_approval_plan.add_argument("--credential-ref", help="Optional env/keyring/secret/wallet ref; exact value is not echoed.")
    credential_access_approval_plan.add_argument(
        "--credential-kind",
        choices=sorted(archive_services.CREDENTIAL_REF_ALLOWED_KINDS),
        help="Credential kind; defaults from action kind.",
    )
    credential_access_approval_plan.add_argument(
        "--provider",
        choices=sorted(archive_services.CREDENTIAL_REF_ALLOWED_PROVIDERS),
        help="Optional provider context.",
    )
    credential_access_approval_plan.add_argument(
        "--action-kind",
        choices=sorted(archive_services.CREDENTIAL_ACCESS_BROKER_ACTIONS),
        required=True,
        help="Future action that would need a credential capability.",
    )
    credential_access_approval_plan.add_argument(
        "--decision",
        choices=sorted(archive_services.CREDENTIAL_ACCESS_APPROVAL_DECISIONS),
        default="needs_review",
        help="Human decision to preview in the future approval receipt.",
    )
    credential_access_approval_plan.add_argument(
        "--store-kind",
        choices=sorted(archive_services.CREDENTIAL_ACCESS_BROKER_STORE_KINDS),
        default="password_manager",
        help="External store class that would hold the real secret.",
    )
    credential_access_approval_plan.add_argument("--consumer", default="wom_local_adapter", help="Safe label for the tool/adapter asking to use the credential.")
    credential_access_approval_plan.add_argument("--reviewed-by", help="Safe non-secret reviewer label. Required with --approve.")
    credential_access_approval_plan.add_argument(
        "--platform",
        choices=sorted(archive_services.CREDENTIAL_STORE_RECOMMENDATION_PLATFORMS),
        default="windows",
        help="Host platform for OS keyring wording.",
    )
    credential_access_approval_plan.add_argument("--dry-run", action="store_true", help="Preview approval receipt without writing files.")
    credential_access_approval_plan.add_argument("--approve", action="store_true", help="Write the reviewed approval receipt without reading secrets.")
    credential_access_approval_plan.add_argument("--format", choices=["text", "json"], default="json", help="Output format.")
    credential_access_approval_plan.set_defaults(func=command_credential_access_approval_plan)

    credential_adapter_readiness_plan = subcommands.add_parser(
        "credential-adapter-readiness-plan",
        aliases=["credential-adapter-plan", "secret-adapter-readiness"],
        help="Preview a future credential adapter contract without opening keyrings or vaults.",
    )
    credential_adapter_readiness_plan.add_argument("archive_root", help="Archive root to inspect.")
    credential_adapter_readiness_plan.add_argument(
        "--adapter-kind",
        choices=sorted(archive_services.CREDENTIAL_ADAPTER_KINDS),
        required=True,
        help="Future local adapter class to evaluate.",
    )
    credential_adapter_readiness_plan.add_argument(
        "--operation",
        choices=sorted(archive_services.CREDENTIAL_ADAPTER_OPERATIONS),
        required=True,
        help="Future adapter operation to evaluate.",
    )
    credential_adapter_readiness_plan.add_argument("--credential-id", required=True, help="Safe credential label, e.g. cred:openai-api.")
    credential_adapter_readiness_plan.add_argument("--credential-ref", help="Optional env/keyring/secret/wallet ref; exact value is not echoed.")
    credential_adapter_readiness_plan.add_argument(
        "--credential-kind",
        choices=sorted(archive_services.CREDENTIAL_REF_ALLOWED_KINDS),
        help="Credential kind; defaults from action kind.",
    )
    credential_adapter_readiness_plan.add_argument(
        "--provider",
        choices=sorted(archive_services.CREDENTIAL_REF_ALLOWED_PROVIDERS),
        help="Optional provider context.",
    )
    credential_adapter_readiness_plan.add_argument(
        "--action-kind",
        choices=sorted(archive_services.CREDENTIAL_ACCESS_BROKER_ACTIONS),
        required=True,
        help="Future action that would need a credential capability.",
    )
    credential_adapter_readiness_plan.add_argument(
        "--store-kind",
        choices=sorted(archive_services.CREDENTIAL_ACCESS_BROKER_STORE_KINDS),
        help="External store class; defaults from adapter kind.",
    )
    credential_adapter_readiness_plan.add_argument("--consumer", help="Safe label for the future local adapter.")
    credential_adapter_readiness_plan.add_argument(
        "--platform",
        choices=sorted(archive_services.CREDENTIAL_STORE_RECOMMENDATION_PLATFORMS),
        default="windows",
        help="Host platform for OS keyring wording.",
    )
    credential_adapter_readiness_plan.add_argument("--dry-run", action="store_true", help="Required; read-only adapter readiness preview.")
    credential_adapter_readiness_plan.add_argument("--format", choices=["text", "json"], default="json", help="Output format.")
    credential_adapter_readiness_plan.set_defaults(func=command_credential_adapter_readiness_plan)

    credential_adapter_manifest_plan = subcommands.add_parser(
        "credential-adapter-manifest-plan",
        aliases=["credential-adapter-manifest", "secret-adapter-manifest-plan"],
        help="Preview a non-secret future credential adapter manifest without writing it.",
    )
    credential_adapter_manifest_plan.add_argument("archive_root", help="Archive root to inspect.")
    credential_adapter_manifest_plan.add_argument("--adapter-id", required=True, help="Safe adapter id path segment, e.g. win-keyring.")
    credential_adapter_manifest_plan.add_argument(
        "--adapter-kind",
        choices=sorted(archive_services.CREDENTIAL_ADAPTER_KINDS),
        required=True,
        help="Future local adapter class to describe.",
    )
    credential_adapter_manifest_plan.add_argument(
        "--operation",
        action="append",
        choices=sorted(archive_services.CREDENTIAL_ADAPTER_OPERATIONS),
        help="Supported future adapter operation; may be repeated. Defaults from adapter kind.",
    )
    credential_adapter_manifest_plan.add_argument(
        "--store-kind",
        choices=sorted(archive_services.CREDENTIAL_ACCESS_BROKER_STORE_KINDS),
        help="External store class; defaults from adapter kind.",
    )
    credential_adapter_manifest_plan.add_argument("--consumer", help="Safe label for the future local adapter.")
    credential_adapter_manifest_plan.add_argument(
        "--platform",
        choices=sorted(archive_services.CREDENTIAL_STORE_RECOMMENDATION_PLATFORMS),
        default="windows",
        help="Host platform for OS keyring wording.",
    )
    credential_adapter_manifest_plan.add_argument("--dry-run", action="store_true", help="Required; read-only manifest preview.")
    credential_adapter_manifest_plan.add_argument("--format", choices=["text", "json"], default="json", help="Output format.")
    credential_adapter_manifest_plan.set_defaults(func=command_credential_adapter_manifest_plan)

    credential_adapter_audit_plan = subcommands.add_parser(
        "credential-adapter-audit-plan",
        aliases=["credential-adapter-audit", "secret-adapter-audit-plan"],
        help="Preview a non-secret future credential adapter audit receipt without writing it.",
    )
    credential_adapter_audit_plan.add_argument("archive_root", help="Archive root to inspect.")
    credential_adapter_audit_plan.add_argument("--adapter-id", required=True, help="Safe adapter id path segment, e.g. win-keyring.")
    credential_adapter_audit_plan.add_argument(
        "--adapter-kind",
        choices=sorted(archive_services.CREDENTIAL_ADAPTER_KINDS),
        required=True,
        help="Future local adapter class to audit.",
    )
    credential_adapter_audit_plan.add_argument(
        "--operation",
        choices=sorted(archive_services.CREDENTIAL_ADAPTER_OPERATIONS),
        required=True,
        help="Future adapter operation to audit.",
    )
    credential_adapter_audit_plan.add_argument("--credential-id", required=True, help="Safe credential label, e.g. cred:openai-api.")
    credential_adapter_audit_plan.add_argument(
        "--credential-kind",
        choices=sorted(archive_services.CREDENTIAL_REF_ALLOWED_KINDS),
        help="Credential kind; defaults from action kind.",
    )
    credential_adapter_audit_plan.add_argument(
        "--provider",
        choices=sorted(archive_services.CREDENTIAL_REF_ALLOWED_PROVIDERS),
        help="Optional provider context.",
    )
    credential_adapter_audit_plan.add_argument(
        "--action-kind",
        choices=sorted(archive_services.CREDENTIAL_ACCESS_BROKER_ACTIONS),
        required=True,
        help="Future action that would need a credential capability.",
    )
    credential_adapter_audit_plan.add_argument(
        "--result-status",
        choices=sorted(archive_services.CREDENTIAL_ADAPTER_AUDIT_RESULT_STATUSES),
        default="not_run",
        help="Non-secret future adapter outcome status to preview.",
    )
    credential_adapter_audit_plan.add_argument(
        "--store-kind",
        choices=sorted(archive_services.CREDENTIAL_ACCESS_BROKER_STORE_KINDS),
        help="External store class; defaults from adapter kind.",
    )
    credential_adapter_audit_plan.add_argument("--consumer", help="Safe label for the future local adapter.")
    credential_adapter_audit_plan.add_argument(
        "--platform",
        choices=sorted(archive_services.CREDENTIAL_STORE_RECOMMENDATION_PLATFORMS),
        default="windows",
        help="Host platform for OS keyring wording.",
    )
    credential_adapter_audit_plan.add_argument("--dry-run", action="store_true", help="Required; read-only audit receipt preview.")
    credential_adapter_audit_plan.add_argument("--format", choices=["text", "json"], default="json", help="Output format.")
    credential_adapter_audit_plan.set_defaults(func=command_credential_adapter_audit_plan)

    source_intake = subcommands.add_parser(
        "source-intake",
        help="Dry-run source/objet intake planning before draft creation.",
    )
    source_intake.add_argument("archive_root", help="Archive root to inspect.")
    source_intake.add_argument("--dry-run", action="store_true", help="Preview source/objet classification without writing files.")
    source_intake.add_argument("--local-path", help="Single local file path to classify by metadata only.")
    source_intake.add_argument("--source", help="Registered source id for source map item lookup.")
    source_intake.add_argument("--item-id", help="Source map item id to classify.")
    source_intake.add_argument("--relative-path", help="Source-relative item path to classify.")
    source_intake.add_argument("--objet-ref", help="WOM objet ref such as objet:sha256:<hash>.")
    source_intake.add_argument("--object-id", help="Technical object_id such as sha256:<hash>.")
    source_intake.add_argument("--provider", help="Provider name for metadata-only provider reference.")
    source_intake.add_argument("--provider-object-id", help="Safe provider object id. Do not pass URLs.")
    source_intake.add_argument("--provider-kind", help="Safe provider item kind.")
    source_intake.add_argument("--ai-artifact-ref", help="Safe local AI artifact reference.")
    source_intake.add_argument(
        "--runtime",
        choices=sorted(archive_services.SOURCE_INTAKE_RUNTIMES),
        help="AI runtime for --ai-artifact-ref.",
    )
    source_intake.add_argument("--artifact-kind", help="Safe AI artifact kind label.")
    source_intake.add_argument("--expected-archive-id", help="Expected archive id; mismatch blocks.")
    source_intake.add_argument(
        "--expected-type",
        choices=sorted(archive_services.RUNTIME_CONTEXT_ARCHIVE_TYPES),
        help="Expected archive type; mismatch blocks.",
    )
    source_intake.add_argument("--profile-id", help="Resolved WOM profile id for downstream draft context.")
    source_intake.add_argument(
        "--source-role",
        choices=sorted(archive_services.SOURCE_INTAKE_ROLES),
        default=archive_services.SOURCE_INTAKE_DEFAULT_ROLE,
        help="Role this source should play in the draft.",
    )
    source_intake.add_argument("--title", help="Non-secret label for the source.")
    source_intake.add_argument("--mime", help="Optional MIME label; no content sniffing is performed.")
    source_intake.add_argument(
        "--project-intake-receipt",
        help="Optional project-intake decisions receipt to validate as session context only.",
    )
    source_intake.add_argument(
        "--redact-local-paths",
        dest="redact_local_paths",
        action="store_true",
        default=True,
        help="Redact local absolute paths. This is the default.",
    )
    source_intake.add_argument(
        "--no-redact-local-paths",
        dest="redact_local_paths",
        action="store_false",
        help="Include local paths for trusted local debugging.",
    )
    source_intake.add_argument("--format", choices=["text", "json"], default="json", help="Output format.")
    source_intake.set_defaults(func=command_source_intake)

    tiro_import_plan = subcommands.add_parser(
        "tiro-import-plan",
        help="Dry-run Tiro meeting transcript/objet import planning from an archive-internal manifest.",
    )
    tiro_import_plan.add_argument("archive_root", help="Archive root to inspect.")
    tiro_import_plan.add_argument(
        "--manifest",
        required=True,
        help="Archive-relative Tiro manifest JSON, e.g. workbench/tiro-meeting.sample.json.",
    )
    tiro_import_plan.add_argument(
        "--source",
        default=archive_services.TIRO_IMPORT_SOURCE,
        choices=[archive_services.TIRO_IMPORT_SOURCE],
        help="Transcript source label.",
    )
    tiro_import_plan.add_argument(
        "--max-segments",
        type=int,
        default=1000,
        help=f"Maximum transcript segments to inspect, up to {archive_services.TIRO_IMPORT_MAX_SEGMENTS}.",
    )
    tiro_import_plan.add_argument("--dry-run", action="store_true", help="Required; write nothing.")
    tiro_import_plan.add_argument("--format", choices=["text", "json"], default="json", help="Output format.")
    tiro_import_plan.set_defaults(func=command_tiro_import_plan)

    tiro_lossless_recovery_plan = subcommands.add_parser(
        "tiro-lossless-recovery-plan",
        aliases=["tiro-recovery-plan"],
        help="Dry-run the Tiro full-data lossless recovery endpoint and bundle contract.",
    )
    tiro_lossless_recovery_plan.add_argument("archive_root", help="Archive root to inspect.")
    tiro_lossless_recovery_plan.add_argument("--credential-ref", help="Optional env/keyring/secret/wallet ref; exact value is not echoed.")
    tiro_lossless_recovery_plan.add_argument("--workspace-guid", help="Optional safe Tiro workspace id; exact value is not echoed.")
    tiro_lossless_recovery_plan.add_argument("--note-guid", help="Optional safe Tiro note id; exact value is not echoed.")
    tiro_lossless_recovery_plan.add_argument(
        "--max-notes",
        type=int,
        default=200,
        help=f"Maximum notes for a future adapter run, up to {archive_services.TIRO_LOSSLESS_RECOVERY_MAX_NOTES}.",
    )
    tiro_lossless_recovery_plan.add_argument("--dry-run", action="store_true", help="Required; write nothing.")
    tiro_lossless_recovery_plan.add_argument("--format", choices=["text", "json"], default="json", help="Output format.")
    tiro_lossless_recovery_plan.set_defaults(func=command_tiro_lossless_recovery_plan)

    tiro_lossless_recovery_capture = subcommands.add_parser(
        "tiro-lossless-recovery-capture",
        aliases=["tiro-recovery-capture"],
        help="Preview or approve preserving a private raw Tiro recovery bundle as a WOM objet.",
    )
    tiro_lossless_recovery_capture.add_argument("archive_root", help="Archive root to update.")
    tiro_lossless_recovery_capture.add_argument(
        "--bundle",
        required=True,
        help="Archive-relative raw Tiro recovery bundle JSON under workbench/.",
    )
    tiro_lossless_recovery_capture.add_argument("--dry-run", action="store_true", help="Preview object/receipt writes.")
    tiro_lossless_recovery_capture.add_argument("--approve", action="store_true", help="Write the reviewed raw bundle as a WOM objet.")
    tiro_lossless_recovery_capture.add_argument("--reviewed-by", help="Safe reviewer id required with --approve.")
    tiro_lossless_recovery_capture.add_argument("--format", choices=["text", "json"], default="json", help="Output format.")
    tiro_lossless_recovery_capture.set_defaults(func=command_tiro_lossless_recovery_capture)

    tiro_lossless_recovery_fetch_run = subcommands.add_parser(
        "tiro-lossless-recovery-fetch-run",
        aliases=["tiro-recovery-fetch-run"],
        help="Preview or approve a credential-bounded Tiro REST fetch into a private raw recovery bundle.",
    )
    tiro_lossless_recovery_fetch_run.add_argument("archive_root", help="Archive root to update.")
    tiro_lossless_recovery_fetch_run.add_argument(
        "--credential-ref",
        help="env:/keyring:/credential-manager: credential ref for approved live fetch; exact value is not echoed.",
    )
    tiro_lossless_recovery_fetch_run.add_argument("--workspace-guid", help="Optional safe Tiro workspace id; exact value is not echoed.")
    tiro_lossless_recovery_fetch_run.add_argument("--note-guid", help="Optional safe Tiro note id; exact value is not echoed.")
    tiro_lossless_recovery_fetch_run.add_argument(
        "--output",
        default=archive_services.TIRO_LOSSLESS_RECOVERY_DEFAULT_OUTPUT_PATH,
        help="Archive-relative raw bundle output path under workbench/.",
    )
    tiro_lossless_recovery_fetch_run.add_argument(
        "--max-notes",
        type=int,
        default=200,
        help=f"Maximum notes to fetch, up to {archive_services.TIRO_LOSSLESS_RECOVERY_MAX_NOTES}.",
    )
    tiro_lossless_recovery_fetch_run.add_argument("--timeout-seconds", type=int, default=30, help="Provider request timeout, 1-120 seconds.")
    tiro_lossless_recovery_fetch_run.add_argument("--dry-run", action="store_true", help="Preview provider/bundle writes without reading credentials.")
    tiro_lossless_recovery_fetch_run.add_argument("--approve", action="store_true", help="Run the approved live fetch and write the raw bundle.")
    tiro_lossless_recovery_fetch_run.add_argument("--reviewed-by", help="Safe reviewer id required with --approve.")
    tiro_lossless_recovery_fetch_run.add_argument("--format", choices=["text", "json"], default="json", help="Output format.")
    tiro_lossless_recovery_fetch_run.set_defaults(func=command_tiro_lossless_recovery_fetch_run)

    zet_markdown_style_guide = subcommands.add_parser(
        "zet-markdown-style-guide",
        aliases=["zet-style-guide", "zettel-markdown-style-guide"],
        help="Print read-only WOM zet Markdown authoring rules such as safe range tilde usage.",
    )
    zet_markdown_style_guide.add_argument("archive_root", help="Archive root to inspect.")
    zet_markdown_style_guide.add_argument(
        "--topic",
        choices=sorted(archive_services.ZET_MARKDOWN_STYLE_GUIDE_TOPICS),
        default="all",
        help="Style topic.",
    )
    zet_markdown_style_guide.add_argument("--dry-run", action="store_true", help="Required; read-only guide.")
    zet_markdown_style_guide.add_argument("--format", choices=["text", "json"], default="json", help="Output format.")
    zet_markdown_style_guide.set_defaults(func=command_zet_markdown_style_guide)

    source_intake_record = subcommands.add_parser(
        "source-intake-record",
        help="Record a reviewed source-intake dry-run plan under receipts/sources/.",
    )
    source_intake_record.add_argument("archive_root", help="Archive root to update.")
    source_intake_record.add_argument("--source-intake-plan", required=True, help="JSON file from source-intake --dry-run.")
    source_intake_record.add_argument("--dry-run", action="store_true", help="Preview validation without writing files.")
    source_intake_record.add_argument("--approve", action="store_true", help="Write the reviewed source-intake plan record.")
    source_intake_record.add_argument("--reviewed-by", help="Reviewer id required when --approve is used.")
    source_intake_record.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    source_intake_record.set_defaults(func=command_source_intake_record)

    list_zettels = subcommands.add_parser("list-zettels", help="List draft and/or canonical zettels.")
    list_zettels.add_argument("archive_root", help="Archive root to inspect.")
    list_zettels.add_argument("--status", choices=["all", "draft", "canonical"], default="canonical", help="Zettel status to list.")
    list_zettels.add_argument("--limit", type=int, default=100, help="Maximum number of zettels to return.")
    list_zettels.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    list_zettels.set_defaults(func=command_list_zettels)

    status_board = subcommands.add_parser(
        "status-board",
        aliases=["archive-status-board", "zet-status-board"],
        help="Read-only archive status board for canonical, draft, retire, source metadata, and derived-artifact gaps.",
    )
    status_board.add_argument("archive_root", help="Archive root to inspect.")
    status_board.add_argument("--dry-run", action="store_true", help="Required. Preview only; write nothing.")
    status_board.add_argument("--max-items", type=int, default=20, help="Maximum example items per board.")
    status_board.add_argument(
        "--include-quality",
        action="store_true",
        help="Also run body-inspecting zet quality checks for counts and candidate paths.",
    )
    status_board.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    status_board.set_defaults(func=command_status_board)

    derived_artifact_staleness = subcommands.add_parser(
        "derived-artifact-staleness",
        aliases=["report-staleness", "artifact-staleness"],
        help="Read-only freshness check for derived_artifacts against their source zets.",
    )
    derived_artifact_staleness.add_argument("archive_root", help="Archive root to inspect.")
    derived_artifact_staleness.add_argument(
        "--dry-run",
        action="store_true",
        help="Required. Preview only; write nothing.",
    )
    derived_artifact_staleness.add_argument("--max-items", type=int, default=20, help="Maximum example items per board.")
    derived_artifact_staleness.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    derived_artifact_staleness.set_defaults(func=command_derived_artifact_staleness)

    read_zettel = subcommands.add_parser("read-zettel", help="Read one zettel by id or archive-relative path.")
    read_zettel.add_argument("archive_root", help="Archive root to inspect.")
    read_target = read_zettel.add_mutually_exclusive_group(required=True)
    read_target.add_argument("--zettel-id", help="Zettel id to read.")
    read_target.add_argument("--path", help="Archive-relative zettel path to read.")
    read_zettel.add_argument(
        "--section",
        choices=["overview", "body", "details", "all"],
        default="body",
        help="Read only the cheap first-read overview, the body, frontmatter details, or all sections.",
    )
    read_zettel.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    read_zettel.set_defaults(func=command_read_zettel)

    zettel_objet_links = subcommands.add_parser(
        "zettel-objet-links",
        help="Preview safe objet link candidates referenced by one zettel.",
    )
    zettel_objet_links.add_argument("archive_root", help="Archive root to inspect.")
    zettel_objet_target = zettel_objet_links.add_mutually_exclusive_group(required=True)
    zettel_objet_target.add_argument("--zettel-id", help="Zettel id to inspect.")
    zettel_objet_target.add_argument("--path", help="Archive-relative zettel path to inspect.")
    zettel_objet_links.add_argument("--dry-run", action="store_true", help="Required. Preview only; write nothing and open nothing.")
    zettel_objet_links.add_argument("--max-refs", type=int, default=100, help="Maximum distinct object refs to resolve.")
    zettel_objet_links.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    zettel_objet_links.set_defaults(func=command_zettel_objet_links)

    notion_objet_link_plan = subcommands.add_parser(
        "notion-objet-link-plan",
        help="Plan Notion provider locator to manifested objet links without echoing URLs.",
    )
    notion_objet_link_plan.add_argument("archive_root", help="Archive root to inspect.")
    notion_objet_link_target = notion_objet_link_plan.add_mutually_exclusive_group(required=True)
    notion_objet_link_target.add_argument("--zettel-id", help="Zettel id to inspect.")
    notion_objet_link_target.add_argument("--path", help="Archive-relative zettel path to inspect.")
    notion_objet_link_plan.add_argument("--dry-run", action="store_true", help="Required. Preview only; write nothing and open nothing.")
    notion_objet_link_plan.add_argument("--max-locators", type=int, default=100, help="Maximum distinct Notion locators to inspect.")
    notion_objet_link_plan.add_argument("--max-candidates", type=int, default=20, help="Maximum manifest candidates per locator.")
    notion_objet_link_plan.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    notion_objet_link_plan.set_defaults(func=command_notion_objet_link_plan)

    notion_objet_link_index = subcommands.add_parser(
        "notion-objet-link-index",
        help="Index Notion provider locator to manifested objet link candidates across zettels without echoing URLs.",
    )
    notion_objet_link_index.add_argument("archive_root", help="Archive root to inspect.")
    notion_objet_link_index.add_argument("--dry-run", action="store_true", help="Required. Preview only; write nothing and open nothing.")
    notion_objet_link_index.add_argument("--max-zettels", type=int, default=50, help="Maximum zettel summaries to include.")
    notion_objet_link_index.add_argument("--max-locators-per-zettel", type=int, default=20, help="Maximum locator summaries per zettel.")
    notion_objet_link_index.add_argument("--max-candidates", type=int, default=5, help="Maximum manifest candidates per locator.")
    notion_objet_link_index.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    notion_objet_link_index.set_defaults(func=command_notion_objet_link_index)

    notion_objet_source_map_link_plan = subcommands.add_parser(
        "notion-objet-source-map-link-plan",
        help="Plan zettel to objet material-link candidates from source maps and ledgers without body locators.",
    )
    notion_objet_source_map_link_plan.add_argument("archive_root", help="Archive root to inspect.")
    notion_objet_source_map_link_plan.add_argument(
        "--source-map",
        action="append",
        help="Archive-relative source-map JSON/JSONL/YAML file. Defaults to source-maps/*.jsonl.",
    )
    notion_objet_source_map_link_plan.add_argument(
        "--ledger",
        action="append",
        help="Archive-relative download/retrieval ledger JSON/JSONL/YAML file with sha256/object_id metadata.",
    )
    notion_objet_source_map_link_plan.add_argument("--dry-run", action="store_true", help="Required. Preview only; write nothing.")
    notion_objet_source_map_link_plan.add_argument("--max-rows", type=int, default=10000, help="Maximum source-map rows to read.")
    notion_objet_source_map_link_plan.add_argument("--max-candidates", type=int, default=200, help="Maximum candidate links to return.")
    notion_objet_source_map_link_plan.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    notion_objet_source_map_link_plan.set_defaults(func=command_notion_objet_source_map_link_plan)

    notion_objet_import_clue_audit = subcommands.add_parser(
        "notion-objet-import-clue-audit",
        help="Audit imported Notion zettels for preserved material clues after provider locator omission.",
    )
    notion_objet_import_clue_audit.add_argument("archive_root", help="Archive root to inspect.")
    notion_objet_import_clue_audit.add_argument(
        "--source-map",
        action="append",
        help="Archive-relative source-map JSON/JSONL/YAML file. Defaults to source-maps/*.jsonl.",
    )
    notion_objet_import_clue_audit.add_argument(
        "--ledger",
        action="append",
        help="Archive-relative download/retrieval ledger JSON/JSONL/YAML file with sha256/object_id metadata.",
    )
    notion_objet_import_clue_audit.add_argument("--dry-run", action="store_true", help="Required. Preview only; write nothing.")
    notion_objet_import_clue_audit.add_argument("--max-rows", type=int, default=10000, help="Maximum source-map or ledger rows to read.")
    notion_objet_import_clue_audit.add_argument("--max-zettels", type=int, default=500, help="Maximum imported zettels to report.")
    notion_objet_import_clue_audit.add_argument("--max-candidates", type=int, default=1000, help="Maximum source-map candidates to consider.")
    notion_objet_import_clue_audit.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    notion_objet_import_clue_audit.set_defaults(func=command_notion_objet_import_clue_audit)

    notion_objet_link_rewrite_plan = subcommands.add_parser(
        "notion-objet-link-rewrite-plan",
        help="Validate one reviewed Notion locator to objet conversion plan without writing.",
    )
    notion_objet_link_rewrite_plan.add_argument("archive_root", help="Archive root to inspect.")
    notion_objet_link_rewrite_target = notion_objet_link_rewrite_plan.add_mutually_exclusive_group(required=True)
    notion_objet_link_rewrite_target.add_argument("--zettel-id", help="Zettel id to inspect.")
    notion_objet_link_rewrite_target.add_argument("--path", help="Archive-relative zettel path to inspect.")
    notion_objet_link_rewrite_plan.add_argument("--locator-fingerprint", required=True, help="Selected sha256 locator fingerprint from notion-objet-link-plan.")
    notion_objet_link_rewrite_plan.add_argument("--object-id", required=True, help="Selected manifested object id, sha256:<64 hex>.")
    notion_objet_link_rewrite_plan.add_argument(
        "--target-mode",
        choices=["objet_ref_rewrite", "embed_edge"],
        default="objet_ref_rewrite",
        help="Future approved conversion mode to validate.",
    )
    notion_objet_link_rewrite_plan.add_argument(
        "--expected-occurrence-count",
        type=int,
        help="Optional drift guard copied from the reviewed one-zettel plan.",
    )
    notion_objet_link_rewrite_plan.add_argument("--dry-run", action="store_true", help="Required. Preview only; write nothing and open nothing.")
    notion_objet_link_rewrite_plan.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    notion_objet_link_rewrite_plan.set_defaults(func=command_notion_objet_link_rewrite_plan)

    notion_objet_link_convert = subcommands.add_parser(
        "notion-objet-link-convert",
        help="Preview or approve converting one reviewed Notion locator/object match into an embed edge.",
    )
    notion_objet_link_convert.add_argument("archive_root", help="Archive root to update.")
    notion_objet_link_convert_target = notion_objet_link_convert.add_mutually_exclusive_group(required=True)
    notion_objet_link_convert_target.add_argument("--zettel-id", help="Zettel id to update.")
    notion_objet_link_convert_target.add_argument("--path", help="Archive-relative zettel path to update.")
    notion_objet_link_convert.add_argument("--locator-fingerprint", required=True, help="Selected sha256 locator fingerprint from the reviewed rewrite plan.")
    notion_objet_link_convert.add_argument("--object-id", required=True, help="Selected manifested object id, sha256:<64 hex>.")
    notion_objet_link_convert.add_argument(
        "--target-mode",
        choices=["embed_edge", "objet_ref_rewrite"],
        default="embed_edge",
        help="Approved conversion mode. v0.3.101 writes embed_edge only; body rewrite stays blocked.",
    )
    notion_objet_link_convert.add_argument(
        "--expected-occurrence-count",
        type=int,
        help="Drift guard copied from the reviewed rewrite plan. Required with --approve.",
    )
    notion_objet_link_convert.add_argument("--visibility", default="private", help="Safe edge visibility label. Default: private.")
    notion_objet_link_convert.add_argument("--dry-run", action="store_true", help="Preview the embed edge and conversion receipt without writing files.")
    notion_objet_link_convert.add_argument("--approve", action="store_true", help="Write the reviewed embed edge and conversion receipt.")
    notion_objet_link_convert.add_argument("--reviewed-by", help="Safe reviewer id required with --approve.")
    notion_objet_link_convert.add_argument("--format", choices=["text", "json"], default="json", help="Output format.")
    notion_objet_link_convert.set_defaults(func=command_notion_objet_link_convert)

    notion_objet_manifest_locator_label = subcommands.add_parser(
        "notion-objet-manifest-locator-label",
        aliases=["notion-objet-locator-label"],
        help="Preview or approve adding a reviewed Notion locator fingerprint label to one object manifest record.",
    )
    notion_objet_manifest_locator_label.add_argument("archive_root", help="Archive root to update.")
    notion_objet_manifest_locator_label.add_argument("--object-id", required=True, help="Manifested object id, sha256:<64 hex>.")
    notion_objet_manifest_locator_label.add_argument(
        "--locator-fingerprint",
        required=True,
        help="Reviewed sha256 locator fingerprint from notion-objet-link-plan or notion-objet-link-index.",
    )
    notion_objet_manifest_locator_label.add_argument("--dry-run", action="store_true", help="Preview manifest label update without writing files.")
    notion_objet_manifest_locator_label.add_argument("--approve", action="store_true", help="Write the reviewed non-secret locator label and receipt.")
    notion_objet_manifest_locator_label.add_argument("--reviewed-by", help="Safe reviewer id required with --approve.")
    notion_objet_manifest_locator_label.add_argument("--format", choices=["text", "json"], default="json", help="Output format.")
    notion_objet_manifest_locator_label.set_defaults(func=command_notion_objet_manifest_locator_label)

    block_header = subcommands.add_parser("block-header", help="Preview the derived block header for one zet.")
    block_header.add_argument("archive_root", help="Archive root to inspect.")
    block_header.add_argument("--path", help="Archive-relative zet path inside inbox/ or zettels/.")
    block_header.add_argument("--zettel-id", help="zet id to inspect.")
    block_header.add_argument("--dry-run", action="store_true", help="Preview the block header without writing files.")
    block_header.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    block_header.set_defaults(func=command_block_header)

    projection_plan = subcommands.add_parser(
        "projection-plan",
        help="Preview a dry-run publication/projection plan for one local zet.",
    )
    projection_plan.add_argument("archive_root", help="Archive root to inspect.")
    projection_plan.add_argument("--zet", required=True, help="zet id or archive-relative path under inbox/ or zettels/.")
    projection_plan.add_argument(
        "--surface",
        required=True,
        help="Operator-declared target surface kind. Supported: "
        + ", ".join(sorted(archive_services.ZET_PROJECTION_SURFACE_KINDS)),
    )
    projection_plan.add_argument(
        "--visibility",
        default="unknown",
        help="Operator-declared visibility intent; not verified provider state.",
    )
    projection_plan.add_argument(
        "--projection-format",
        default="metadata_only",
        help="Future projection format intent; v0.2.46 renders no body output. Supported: "
        + ", ".join(sorted(archive_services.ZET_PROJECTION_FORMATS)),
    )
    projection_plan.add_argument("--dry-run", action="store_true", help="Preview only; write nothing.")
    projection_plan.add_argument("--format", choices=["text", "json"], default="json", help="Output format.")
    projection_plan.set_defaults(func=command_projection_plan)

    zet_surface_prototype = subcommands.add_parser(
        "zet-surface-prototype",
        help="Preview a user-selected ZET surface prototype without provider calls or writes.",
    )
    zet_surface_prototype.add_argument("archive_root", help="Archive root to inspect.")
    zet_surface_prototype.add_argument(
        "--surface-kind",
        choices=sorted(archive_services.ZET_SURFACE_PROTOTYPE_KINDS),
        required=True,
        help="Surface prototype kind.",
    )
    zet_surface_prototype.add_argument("--surface-ref", help="Optional safe label/ref; never pass a URL, email, token, or local path.")
    zet_surface_prototype.add_argument("--dry-run", action="store_true", help="Required; preview only.")
    zet_surface_prototype.add_argument("--format", choices=["text", "json"], default="json", help="Output format.")
    zet_surface_prototype.set_defaults(func=command_zet_surface_prototype)

    shared_update_record_review = subcommands.add_parser(
        "shared-update-record-review",
        help="Preview a local ZET shared update record before any renewal action.",
    )
    shared_update_record_review.add_argument("archive_root", help="Archive root used for path safety and local context.")
    shared_update_record_review.add_argument(
        "--record",
        required=True,
        help="Archive-relative JSON shared update record path.",
    )
    shared_update_record_review.add_argument("--dry-run", action="store_true", help="Preview only; write nothing.")
    shared_update_record_review.add_argument("--format", choices=["text", "json"], default="json", help="Output format.")
    shared_update_record_review.set_defaults(func=command_shared_update_record_review)

    shared_update_record_review_index = subcommands.add_parser(
        "shared-update-record-review-index",
        help="Index local ZET shared update records before any renewal action.",
    )
    shared_update_record_review_index.add_argument("archive_root", help="Archive root used for path safety and local context.")
    shared_update_record_review_index.add_argument(
        "--records-dir",
        required=True,
        help="Archive-relative directory containing JSON shared update records.",
    )
    shared_update_record_review_index.add_argument(
        "--limit",
        type=int,
        default=archive_services.ZET_SHARED_UPDATE_REVIEW_INDEX_MAX_LIMIT,
        help="Maximum direct-child JSON records to scan. Defaults to 100.",
    )
    shared_update_record_review_index.add_argument("--dry-run", action="store_true", help="Required. Preview only; write nothing.")
    shared_update_record_review_index.add_argument("--format", choices=["text", "json"], default="json", help="Output format.")
    shared_update_record_review_index.set_defaults(func=command_shared_update_record_review_index)

    shared_update_route_preview_parser = subcommands.add_parser(
        "shared-update-route-preview",
        help="Preview the next receiver-side route without writing files.",
    )
    shared_update_route_preview_parser.add_argument(
        "archive_root",
        help="Archive root used for path safety and local context.",
    )
    shared_update_route_preview_parser.add_argument(
        "--record",
        required=True,
        help="Archive-relative JSON shared update record path.",
    )
    shared_update_route_preview_parser.add_argument("--dry-run", action="store_true", help="Required. Preview only; write nothing.")
    shared_update_route_preview_parser.add_argument("--format", choices=["text", "json"], default="json", help="Output format.")
    shared_update_route_preview_parser.set_defaults(func=command_shared_update_route_preview)

    shared_update_attestation_review = subcommands.add_parser(
        "shared-update-attestation-review",
        help="Approve recording a local shared update attestation/review record and receipt.",
    )
    shared_update_attestation_review.add_argument("archive_root", help="Archive root used for path safety and local context.")
    shared_update_attestation_review.add_argument(
        "--record",
        required=True,
        help="Archive-relative JSON shared update record path already accepted by shared-update-record-review.",
    )
    shared_update_attestation_review.add_argument(
        "--decision",
        required=True,
        choices=sorted(archive_services.ZET_SHARED_UPDATE_ATTESTATION_REVIEW_DECISIONS),
        help="Human receiver-side review decision to record locally.",
    )
    shared_update_attestation_review.add_argument(
        "--reviewed-by",
        required=False,
        help="Safe reviewer actor id. Required with --approve.",
    )
    shared_update_attestation_review.add_argument("--approve", action="store_true", help="Required. Record the local review and receipt.")
    shared_update_attestation_review.add_argument("--format", choices=["text", "json"], default="json", help="Output format.")
    shared_update_attestation_review.set_defaults(func=command_shared_update_attestation_review)

    zet_transport_plan = subcommands.add_parser(
        "zet-transport-plan",
        help="Preview a dry-run ZET would-transport plan without real transport.",
    )
    zet_transport_plan.add_argument("archive_root", help="Archive root used for path safety and local context.")
    zet_transport_plan.add_argument(
        "--record",
        required=True,
        help="Archive-relative JSON shared update record path.",
    )
    zet_transport_plan.add_argument(
        "--method",
        required=True,
        help="Planning method: key-sharing, radio-frequency, or mirroring.",
    )
    zet_transport_plan.add_argument("--dry-run", action="store_true", help="Required. Preview only; write nothing.")
    zet_transport_plan.add_argument("--format", choices=["text", "json"], default="json", help="Output format.")
    zet_transport_plan.set_defaults(func=command_zet_transport_plan)

    foreign_block = subcommands.add_parser("foreign-block", help="Preview a foreign/shared block or zet before trust/import.")
    foreign_block.add_argument("archive_root", help="Archive root used for path safety and local context.")
    foreign_source = foreign_block.add_mutually_exclusive_group(required=True)
    foreign_source.add_argument("--path", help="Archive-relative foreign artifact path to inspect.")
    foreign_source.add_argument("--stdin", action="store_true", help="Read the foreign artifact from stdin.")
    foreign_block.add_argument("--dry-run", action="store_true", help="Preview foreign block intake without writing files.")
    foreign_block.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    foreign_block.set_defaults(func=command_foreign_block)

    foreign_block_trust = subcommands.add_parser(
        "foreign-block-trust",
        help="Preview future trust/attestation eligibility from a foreign-block intake report.",
    )
    foreign_block_trust.add_argument("archive_root", help="Archive root used for path safety and local context.")
    trust_source = foreign_block_trust.add_mutually_exclusive_group(required=True)
    trust_source.add_argument("--intake-report", help="Archive-relative JSON report from foreign-block --dry-run.")
    trust_source.add_argument("--stdin", action="store_true", help="Read the foreign-block intake report JSON from stdin.")
    foreign_block_trust.add_argument("--dry-run", action="store_true", help="Preview trust/attestation eligibility without writing files.")
    foreign_block_trust.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    foreign_block_trust.set_defaults(func=command_foreign_block_trust)

    foreign_block_attestation = subcommands.add_parser(
        "foreign-block-attestation",
        help="Preview a human-review attestation packet from a foreign-block trust report.",
    )
    foreign_block_attestation.add_argument("archive_root", help="Archive root used for path safety and local context.")
    attestation_source = foreign_block_attestation.add_mutually_exclusive_group(required=True)
    attestation_source.add_argument("--trust-report", help="Archive-relative JSON report from foreign-block-trust --dry-run.")
    attestation_source.add_argument("--stdin", action="store_true", help="Read the foreign-block trust report JSON from stdin.")
    foreign_block_attestation.add_argument("--prospective-attestor", help="Optional safe actor id for a future attestor. This is not approval.")
    foreign_block_attestation.add_argument(
        "--review-scope",
        choices=["human_review", "policy_review", "operator_review"],
        default="human_review",
        help="Review scope for the preview packet. This is not approval.",
    )
    foreign_block_attestation.add_argument("--dry-run", action="store_true", help="Preview the attestation review packet without writing files.")
    foreign_block_attestation.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    foreign_block_attestation.set_defaults(func=command_foreign_block_attestation)

    foreign_block_quarantine = subcommands.add_parser(
        "foreign-block-quarantine",
        help="Plan future isolated holding for a foreign block without writing quarantine files.",
    )
    foreign_block_quarantine.add_argument("archive_root", help="Archive root used for path safety and local context.")
    quarantine_source = foreign_block_quarantine.add_mutually_exclusive_group(required=True)
    quarantine_source.add_argument("--attestation-packet", help="Archive-relative JSON report from foreign-block-attestation --dry-run.")
    quarantine_source.add_argument("--stdin", action="store_true", help="Read the foreign-block attestation packet JSON from stdin.")
    foreign_block_quarantine.add_argument("--quarantine-case-id", help="Optional safe case id for preview paths. This is not approval.")
    foreign_block_quarantine.add_argument("--reviewer", help="Optional safe actor id for a future reviewer. This is not approval.")
    foreign_block_quarantine.add_argument(
        "--quarantine-policy",
        choices=sorted(archive_services.FOREIGN_BLOCK_QUARANTINE_POLICIES),
        default=archive_services.FOREIGN_BLOCK_QUARANTINE_DEFAULT_POLICY,
        help="Quarantine planning policy. This is not approval.",
    )
    foreign_block_quarantine.add_argument("--dry-run", action="store_true", help="Preview the quarantine plan without writing files.")
    foreign_block_quarantine.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    foreign_block_quarantine.set_defaults(func=command_foreign_block_quarantine)

    quarantine_foreign_block = subcommands.add_parser(
        "quarantine-foreign-block",
        help="Preview or approve a local isolated quarantine case write for a foreign block.",
    )
    quarantine_foreign_block.add_argument("archive_root", help="Archive root used for path safety and local context.")
    quarantine_foreign_block.add_argument("--plan", required=True, help="Archive-relative JSON report from foreign-block-quarantine --dry-run.")
    quarantine_foreign_block.add_argument("--dry-run", action="store_true", help="Preview the approved quarantine write without writing files.")
    quarantine_foreign_block.add_argument("--approve", action="store_true", help="Approve the local quarantine case write.")
    quarantine_foreign_block.add_argument("--reviewed-by", help="Safe actor id approving the quarantine write.")
    quarantine_foreign_block.add_argument("--expected-case-id", help="Optional safe case id expected from the plan.")
    quarantine_foreign_block.add_argument("--review-note", help="Optional short non-secret operator note. This is not trust or attestation.")
    quarantine_foreign_block.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    quarantine_foreign_block.set_defaults(func=command_quarantine_foreign_block)

    quarantine_review = subcommands.add_parser(
        "quarantine-review",
        help="List and validate existing foreign block quarantine cases without writing files.",
    )
    quarantine_review.add_argument("archive_root", help="Archive root used for path safety and local context.")
    quarantine_review.add_argument("--case-id", help="Optional safe quarantine case id filter.")
    quarantine_review.add_argument(
        "--status",
        choices=["written_untrusted", "all"],
        default="written_untrusted",
        help="Filter by quarantine status.",
    )
    quarantine_review.add_argument("--include-receipts", action="store_true", help="Include a safe receipt summary for each matching case.")
    quarantine_review.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    quarantine_review.set_defaults(func=command_quarantine_review)

    quarantine_decision = subcommands.add_parser(
        "quarantine-decision",
        help="Preview a future decision path for one foreign block quarantine case without writing files.",
    )
    quarantine_decision.add_argument("archive_root", help="Archive root used for path safety and local context.")
    quarantine_decision.add_argument("--case-id", required=True, help="Safe quarantine case id to inspect.")
    quarantine_decision.add_argument("--dry-run", action="store_true", help="Preview only. Required; writes nothing.")
    quarantine_decision.add_argument(
        "--decision-intent",
        default="auto",
        help="auto, keep_quarantined, reject_and_keep_record, eligible_for_attestation_review, or needs_more_review.",
    )
    quarantine_decision.add_argument("--reviewer", help="Optional safe actor id. Preview context only, not approval.")
    quarantine_decision.add_argument("--review-note", help="Optional short safe note. Preview context only, not approval.")
    quarantine_decision.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    quarantine_decision.set_defaults(func=command_quarantine_decision)

    record_quarantine_decision = subcommands.add_parser(
        "record-quarantine-decision",
        help="Preview or approve recording a local quarantine decision for a foreign block.",
    )
    record_quarantine_decision.add_argument("archive_root", help="Archive root used for path safety and local context.")
    record_quarantine_decision.add_argument(
        "--decision-preview",
        required=True,
        help="JSON file from quarantine-decision --dry-run --format json.",
    )
    record_quarantine_decision.add_argument("--dry-run", action="store_true", help="Preview the decision record write without writing files.")
    record_quarantine_decision.add_argument("--approve", action="store_true", help="Approve writing the local quarantine decision record.")
    record_quarantine_decision.add_argument("--reviewed-by", help="Safe actor id approving the decision record.")
    record_quarantine_decision.add_argument("--expected-case-id", help="Optional safe case id expected from the decision preview.")
    record_quarantine_decision.add_argument(
        "--expected-decision",
        choices=sorted(archive_services.FOREIGN_BLOCK_QUARANTINE_DECISIONS),
        help="Optional quarantine decision expected from the decision preview.",
    )
    record_quarantine_decision.add_argument("--review-note", help="Optional short non-secret operator note. Only summary metadata is stored.")
    record_quarantine_decision.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    record_quarantine_decision.set_defaults(func=command_record_quarantine_decision)

    quarantine_decision_review = subcommands.add_parser(
        "quarantine-decision-review",
        help="List and validate recorded foreign block quarantine decisions without writing files.",
    )
    quarantine_decision_review.add_argument("archive_root", help="Archive root used for path safety and local context.")
    quarantine_decision_review.add_argument("--case-id", help="Optional safe quarantine case id filter.")
    quarantine_decision_review.add_argument(
        "--decision",
        choices=sorted(archive_services.FOREIGN_BLOCK_QUARANTINE_DECISIONS | {"all"}),
        default="all",
        help="Filter by recorded quarantine decision.",
    )
    quarantine_decision_review.add_argument("--include-receipts", action="store_true", help="Include sanitized decision receipt summaries.")
    quarantine_decision_review.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    quarantine_decision_review.set_defaults(func=command_quarantine_decision_review)

    quarantine_decision_outcome = subcommands.add_parser(
        "quarantine-decision-outcome",
        help="Plan the next safe non-mutating path for one recorded foreign block quarantine decision.",
    )
    quarantine_decision_outcome.add_argument("archive_root", help="Archive root used for path safety and local context.")
    quarantine_decision_outcome.add_argument("--case-id", required=True, help="Safe quarantine case id with a recorded decision.")
    quarantine_decision_outcome.add_argument("--dry-run", action="store_true", help="Required. Preview the outcome plan without writing files.")
    quarantine_decision_outcome.add_argument(
        "--expected-decision",
        choices=sorted(archive_services.FOREIGN_BLOCK_QUARANTINE_DECISIONS),
        help="Optional recorded decision expected for replay safety.",
    )
    quarantine_decision_outcome.add_argument("--reviewer", help="Optional safe actor id for local operator preview context.")
    quarantine_decision_outcome.add_argument("--review-note", help="Optional short non-secret operator note. Only summary metadata is returned.")
    quarantine_decision_outcome.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    quarantine_decision_outcome.set_defaults(func=command_quarantine_decision_outcome)

    attestation_review_candidate = subcommands.add_parser(
        "attestation-review-candidate",
        help="Plan a human attestation review candidate from an eligible recorded quarantine decision.",
    )
    attestation_review_candidate.add_argument("archive_root", help="Archive root used for path safety and local context.")
    attestation_review_candidate.add_argument("--case-id", required=True, help="Safe quarantine case id with a recorded eligible decision.")
    attestation_review_candidate.add_argument("--dry-run", action="store_true", help="Required. Preview the candidate plan without writing files.")
    attestation_review_candidate.add_argument(
        "--expected-decision",
        help="Optional replay guard. Must be eligible_for_attestation_review.",
    )
    attestation_review_candidate.add_argument(
        "--expected-outcome",
        help="Optional replay guard. Must be prepare_attestation_review_candidate.",
    )
    attestation_review_candidate.add_argument("--prospective-attestor", help="Optional safe actor id for the future human attestor.")
    attestation_review_candidate.add_argument(
        "--review-scope",
        choices=sorted(archive_services.FOREIGN_BLOCK_ATTESTATION_REVIEW_CANDIDATE_SCOPES),
        default="full_human_review",
        help="Human review focus for the candidate plan.",
    )
    attestation_review_candidate.add_argument("--review-note", help="Optional short non-secret operator note. Only summary metadata is returned.")
    attestation_review_candidate.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    attestation_review_candidate.set_defaults(func=command_attestation_review_candidate)

    record_attestation_review_candidate = subcommands.add_parser(
        "record-attestation-review-candidate",
        help="Preview or approve recording an untrusted foreign block attestation review candidate.",
    )
    record_attestation_review_candidate.add_argument("archive_root", help="Archive root used for path safety and local context.")
    record_attestation_review_candidate.add_argument(
        "--candidate-plan",
        required=True,
        help="JSON file from attestation-review-candidate --dry-run --format json.",
    )
    record_attestation_review_candidate.add_argument("--dry-run", action="store_true", help="Preview the candidate record write without writing files.")
    record_attestation_review_candidate.add_argument("--approve", action="store_true", help="Approve writing the local untrusted candidate record.")
    record_attestation_review_candidate.add_argument("--reviewed-by", help="Safe actor id approving the candidate record.")
    record_attestation_review_candidate.add_argument("--expected-case-id", help="Optional safe case id expected from the candidate plan.")
    record_attestation_review_candidate.add_argument(
        "--expected-review-scope",
        choices=sorted(archive_services.FOREIGN_BLOCK_ATTESTATION_REVIEW_CANDIDATE_SCOPES),
        help="Optional review scope expected from the candidate plan.",
    )
    record_attestation_review_candidate.add_argument("--expected-attestor", help="Optional safe prospective attestor expected from the candidate plan.")
    record_attestation_review_candidate.add_argument("--review-note", help="Optional short non-secret operator note. Only summary metadata is stored.")
    record_attestation_review_candidate.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    record_attestation_review_candidate.set_defaults(func=command_record_attestation_review_candidate)

    attestation_candidate_review = subcommands.add_parser(
        "attestation-candidate-review",
        help="List and validate recorded foreign block attestation review candidates without writing files.",
    )
    attestation_candidate_review.add_argument("archive_root", help="Archive root used for path safety and local context.")
    attestation_candidate_review.add_argument("--case-id", help="Optional safe quarantine case id filter.")
    attestation_candidate_review.add_argument(
        "--review-scope",
        choices=sorted(archive_services.FOREIGN_BLOCK_ATTESTATION_REVIEW_CANDIDATE_SCOPES | {"all"}),
        default="all",
        help="Filter displayed candidates by review scope.",
    )
    attestation_candidate_review.add_argument("--include-receipts", action="store_true", help="Include sanitized candidate receipt summaries.")
    attestation_candidate_review.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    attestation_candidate_review.set_defaults(func=command_attestation_candidate_review)

    attestation_statement_draft = subcommands.add_parser(
        "attestation-statement-draft",
        help="Preview a non-binding foreign block attestation statement draft without writing files.",
    )
    attestation_statement_draft.add_argument("archive_root", help="Archive root used for path safety and local context.")
    attestation_statement_draft.add_argument("--case-id", required=True, help="Safe quarantine case id with a recorded candidate.")
    attestation_statement_draft.add_argument("--dry-run", action="store_true", help="Required. Preview the statement draft without writing files.")
    attestation_statement_draft.add_argument(
        "--expected-review-scope",
        choices=sorted(archive_services.FOREIGN_BLOCK_ATTESTATION_REVIEW_CANDIDATE_SCOPES),
        help="Optional review scope expected from the recorded candidate.",
    )
    attestation_statement_draft.add_argument("--prospective-attestor", help="Optional safe actor id expected or proposed for the future attestor.")
    attestation_statement_draft.add_argument(
        "--statement-style",
        default="minimal",
        help="minimal, review_checklist, or human_readable.",
    )
    attestation_statement_draft.add_argument("--review-note", help="Optional short non-secret operator note. Only summary metadata is returned.")
    attestation_statement_draft.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    attestation_statement_draft.set_defaults(func=command_attestation_statement_draft)

    record_attestation_statement_draft = subcommands.add_parser(
        "record-attestation-statement-draft",
        help="Preview or approve recording a local attestation statement draft without attesting.",
    )
    record_attestation_statement_draft.add_argument("archive_root", help="Archive root used for path safety and local context.")
    record_attestation_statement_draft.add_argument(
        "--draft-preview",
        required=True,
        help="Archive-relative JSON output from attestation-statement-draft --dry-run --format json.",
    )
    record_attestation_statement_draft.add_argument("--dry-run", action="store_true", help="Preview the two-file statement draft record write.")
    record_attestation_statement_draft.add_argument("--approve", action="store_true", help="Approve writing the local statement draft record and receipt.")
    record_attestation_statement_draft.add_argument("--reviewed-by", help="Safe actor id approving the statement draft record.")
    record_attestation_statement_draft.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    record_attestation_statement_draft.set_defaults(func=command_record_attestation_statement_draft)

    attestation_statement_draft_review = subcommands.add_parser(
        "attestation-statement-draft-review",
        help="List and validate recorded foreign block attestation statement drafts.",
    )
    attestation_statement_draft_review.add_argument("archive_root", help="Archive root used for path safety and local context.")
    attestation_statement_draft_review.add_argument("--case-id", help="Optional safe quarantine case id filter.")
    attestation_statement_draft_review.add_argument(
        "--statement-style",
        choices=sorted(archive_services.FOREIGN_BLOCK_ATTESTATION_STATEMENT_STYLES | {"all"}),
        default="all",
        help="Display only drafts with this statement style, or all.",
    )
    attestation_statement_draft_review.add_argument(
        "--review-scope",
        choices=sorted(archive_services.FOREIGN_BLOCK_ATTESTATION_REVIEW_CANDIDATE_SCOPES | {"all"}),
        default="all",
        help="Display only drafts with this review scope, or all.",
    )
    attestation_statement_draft_review.add_argument("--include-receipts", action="store_true", help="Include sanitized statement draft receipt summaries.")
    attestation_statement_draft_review.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    attestation_statement_draft_review.set_defaults(func=command_attestation_statement_draft_review)

    attestation_statement_draft_decision = subcommands.add_parser(
        "attestation-statement-draft-decision",
        help="Preview a safe next review route for one recorded attestation statement draft.",
    )
    attestation_statement_draft_decision.add_argument("archive_root", help="Archive root used for path safety and local context.")
    attestation_statement_draft_decision.add_argument("--case-id", required=True, help="Safe quarantine case id with a recorded statement draft.")
    attestation_statement_draft_decision.add_argument("--dry-run", action="store_true", help="Required. Preview the decision route without writing files.")
    attestation_statement_draft_decision.add_argument(
        "--decision-intent",
        default="needs_more_review",
        help="keep_under_review, revise_statement_draft, reject_statement_draft, prepare_future_attestation_statement_review, or needs_more_review.",
    )
    attestation_statement_draft_decision.add_argument("--reviewer", help="Optional safe actor id for preview context only.")
    attestation_statement_draft_decision.add_argument(
        "--expected-review-scope",
        help="Optional review scope expected from the recorded statement draft.",
    )
    attestation_statement_draft_decision.add_argument(
        "--expected-statement-style",
        help="Optional statement style expected from the recorded statement draft.",
    )
    attestation_statement_draft_decision.add_argument("--review-note", help="Optional short non-secret operator note. Only summary metadata is returned.")
    attestation_statement_draft_decision.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    attestation_statement_draft_decision.set_defaults(func=command_attestation_statement_draft_decision)

    create_draft = subcommands.add_parser("create-draft", help="Create a draft zettel in inbox/.")
    create_draft.add_argument("archive_root", help="Archive root to write to.")
    create_draft.add_argument("--title", required=True, help="Draft title.")
    body = create_draft.add_mutually_exclusive_group(required=True)
    body.add_argument("--body", help="Draft body text.")
    body.add_argument("--body-file", help="Path to a UTF-8 text file containing the draft body.")
    create_draft.add_argument("--archive-id", help="Archive id. Defaults to archive.yml archive_id.")
    create_draft.add_argument("--kind", default="fleeting_capture", help="Zettel kind.")
    create_draft.add_argument("--facet", action="append", help="Facet in KEY=VALUE form. May be repeated.")
    create_draft.add_argument("--dry-run", action="store_true", help="Preview draft creation without writing files.")
    create_draft.add_argument("--expected-archive-id", help="Expected archive id; mismatch blocks.")
    create_draft.add_argument(
        "--expected-type",
        choices=sorted(archive_services.RUNTIME_CONTEXT_ARCHIVE_TYPES),
        help="Expected archive type; mismatch blocks.",
    )
    create_draft.add_argument("--profile-id", help="Resolved WOM profile id for profile-bound draft replay.")
    create_draft.add_argument("--profile-operator-id", help="Actor operating under the resolved profile.")
    create_draft.add_argument("--profile-authority-mode", help="Authority mode from the resolved profile.")
    create_draft.add_argument(
        "--creation-mode",
        choices=sorted(archive_services.DRAFT_CREATION_MODES),
        help="How the draft body was created.",
    )
    create_draft.add_argument("--created-by", help="Actor that created the draft frontmatter.")
    create_draft.add_argument("--source", help="Non-secret source label for provenance.")
    create_draft.add_argument("--assisted-by", action="append", help="Assisting actor id. May be repeated.")
    create_draft.add_argument("--supervised-by", action="append", help="Supervising actor id. May be repeated.")
    create_draft.add_argument("--derived-from", action="append", help="Safe source ref the draft derives from. May be repeated.")
    create_draft.add_argument("--source-ref", action="append", help="Safe source ref in TYPE:VALUE form. May be repeated.")
    create_draft.add_argument("--source-intake-plan", help="JSON file from source-intake --dry-run to merge into draft refs.")
    create_draft.add_argument("--prompt-boundary-report", help="JSON file from prompt-boundary --dry-run to preserve untrusted-text handling metadata.")
    create_draft.add_argument("--local-ai-session", action="append", help="Safe local AI session ref. May be repeated.")
    create_draft.add_argument("--draft-id", help="Deterministic draft zet id for dry-run replay.")
    create_draft.add_argument("--created-at", help="Deterministic ISO timestamp for dry-run replay.")
    create_draft.add_argument("--expected-body-sha256", help="Expected SHA-256 of the normalized draft body.")
    create_draft.add_argument("--draft-approved-by", help="Human actor approving inbox draft creation.")
    create_draft.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    create_draft.set_defaults(func=command_create_draft)

    promote = subcommands.add_parser("promote", help="Legacy: check whether a draft zettel can be promoted.")
    promote.add_argument("archive_root", help="Archive root to inspect.")
    promote_target = promote.add_mutually_exclusive_group(required=True)
    promote_target.add_argument("--zettel-id", help="Draft zettel id to check.")
    promote_target.add_argument("--path", help="Archive-relative draft path to check.")
    promote.add_argument("--dry-run", action="store_true", help="Preview promotion without writing canonical memory.")
    promote.add_argument("--approve", action="store_true", help="Actually write canonical memory after dry-run gates pass.")
    promote.add_argument("--reviewed-by", help="Reviewer id required for real promotion, e.g. person:me.")
    promote.add_argument(
        "--allow-warnings",
        action="store_true",
        help="Allow real promotion when dry-run warnings are present.",
    )
    promote.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    promote.set_defaults(func=command_promote)

    mint = subcommands.add_parser(
        "mint-zet",
        aliases=["mint-zettel"],
        help="Mint an inbox draft zet into canonical private archive memory. Alias: mint-zettel.",
    )
    mint.add_argument("archive_root", help="Archive root to inspect.")
    mint_target = mint.add_mutually_exclusive_group(required=True)
    mint_target.add_argument("--zettel-id", help="Draft zettel id to mint.")
    mint_target.add_argument("--path", help="Archive-relative draft path to mint.")
    mint.add_argument("--dry-run", action="store_true", help="Preview minting without writing canonical memory.")
    mint.add_argument("--approve", action="store_true", help="Actually mint after dry-run gates pass.")
    mint.add_argument("--reviewed-by", help="Reviewer id required for real minting, e.g. person:me.")
    mint.add_argument(
        "--allow-warnings",
        action="store_true",
        help="Allow real minting when dry-run warnings are present.",
    )
    mint.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    mint.set_defaults(func=command_mint_zettel)

    self_contained = subcommands.add_parser(
        "zet-self-contained-check",
        aliases=["zettel-self-contained-check"],
        help="Read-only check that a zet does not depend on AI scratch files or private provider locators.",
    )
    self_contained.add_argument("archive_root", help="Archive root to inspect.")
    self_contained_target = self_contained.add_mutually_exclusive_group(required=True)
    self_contained_target.add_argument("--zettel-id", help="Zet id to inspect.")
    self_contained_target.add_argument("--path", help="Archive-relative zet path to inspect.")
    self_contained.add_argument("--dry-run", action="store_true", help="Required; read-only check.")
    self_contained.add_argument("--format", choices=["text", "json"], default="json", help="Output format.")
    self_contained.set_defaults(func=command_zet_self_contained_check)

    quality_check = subcommands.add_parser(
        "zet-quality-check",
        aliases=["zettel-quality-check"],
        help="Read-only check for entity, document-type, source, audience, correction, and derived-artifact quality risks.",
    )
    quality_check.add_argument("archive_root", help="Archive root to inspect.")
    quality_target = quality_check.add_mutually_exclusive_group(required=True)
    quality_target.add_argument("--zettel-id", help="Zet id to inspect.")
    quality_target.add_argument("--path", help="Archive-relative zet path to inspect.")
    quality_check.add_argument("--dry-run", action="store_true", help="Required; read-only check.")
    quality_check.add_argument("--format", choices=["text", "json"], default="json", help="Output format.")
    quality_check.set_defaults(func=command_zet_quality_check)

    ai_scratch_gc = subcommands.add_parser(
        "ai-scratch-gc",
        aliases=["ai-residue-cleanup", "scratch-gc"],
        help="Preview or approve deleting explicit AI scratch files used by one zet.",
    )
    ai_scratch_gc.add_argument("archive_root", help="Archive root to inspect.")
    ai_scratch_gc_target = ai_scratch_gc.add_mutually_exclusive_group(required=True)
    ai_scratch_gc_target.add_argument("--zettel-id", help="Zet id whose explicit scratch refs should be cleaned.")
    ai_scratch_gc_target.add_argument("--path", help="Archive-relative zet path whose explicit scratch refs should be cleaned.")
    ai_scratch_gc.add_argument("--dry-run", action="store_true", help="Preview cleanup without deleting scratch files.")
    ai_scratch_gc.add_argument("--approve", action="store_true", help="Delete explicit scratch files and write a cleanup receipt.")
    ai_scratch_gc.add_argument("--reviewed-by", help="Reviewer id required when --approve is used, e.g. person:me.")
    ai_scratch_gc.add_argument("--format", choices=["text", "json"], default="json", help="Output format.")
    ai_scratch_gc.set_defaults(func=command_ai_scratch_gc)

    mint_batch = subcommands.add_parser(
        "mint-zet-batch",
        aliases=["mint-zettel-batch", "bulk-mint", "bulk-mint-zet"],
        help="Preview or approve minting many inbox draft zets from one JSON plan in one process.",
    )
    mint_batch.add_argument("archive_root", help="Archive root to update.")
    mint_batch.add_argument("--plan", required=True, help="JSON plan file with items containing zettel_id or path.")
    mint_batch.add_argument("--dry-run", action="store_true", help="Preview the batch without writing canonical memory.")
    mint_batch.add_argument("--approve", action="store_true", help="Mint approved batch items after gates pass.")
    mint_batch.add_argument("--reviewed-by", help="Reviewer id required when --approve is used, e.g. person:me.")
    mint_batch.add_argument("--allow-warnings", action="store_true", help="Allow approved item mints when warnings are present.")
    mint_batch.add_argument("--skip-existing", action="store_true", help="Skip items whose canonical, mint receipt, and draft snapshot already exist.")
    mint_batch.add_argument("--max-items", type=int, default=500, help="Maximum item count accepted from the plan.")
    mint_batch.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    mint_batch.set_defaults(func=command_mint_zettel_batch)

    retire_draft = subcommands.add_parser(
        "retire-draft",
        aliases=["retire-minted-draft"],
        help="Close an already minted inbox draft after canonical, receipt, and snapshot evidence is verified.",
    )
    retire_draft.add_argument("archive_root", help="Archive root to inspect.")
    retire_target = retire_draft.add_mutually_exclusive_group(required=True)
    retire_target.add_argument("--zettel-id", help="Inbox draft zettel id to retire.")
    retire_target.add_argument("--path", help="Archive-relative inbox draft path to retire.")
    retire_draft.add_argument("--dry-run", action="store_true", help="Verify retirement evidence without writing or deleting.")
    retire_draft.add_argument("--approve", action="store_true", help="Remove the verified inbox draft and write a retire receipt.")
    retire_draft.add_argument("--reviewed-by", help="Reviewer id required when --approve is used, e.g. person:me.")
    retire_draft.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    retire_draft.set_defaults(func=command_retire_draft)

    retire_draft_batch = subcommands.add_parser(
        "retire-draft-batch",
        aliases=["retire-minted-draft-batch", "bulk-retire", "bulk-retire-draft"],
        help="Preview or approve retiring many already minted inbox drafts from one JSON plan in one process.",
    )
    retire_draft_batch.add_argument("archive_root", help="Archive root to update.")
    retire_draft_batch.add_argument("--plan", required=True, help="JSON plan file with items containing zettel_id or path.")
    retire_draft_batch.add_argument("--dry-run", action="store_true", help="Verify batch retirement evidence without writing or deleting.")
    retire_draft_batch.add_argument("--approve", action="store_true", help="Remove verified inbox drafts and write retire receipts.")
    retire_draft_batch.add_argument("--reviewed-by", help="Reviewer id required when --approve is used, e.g. person:me.")
    retire_draft_batch.add_argument("--skip-existing", action="store_true", help="Skip items whose draft is already gone and retire receipt exists.")
    retire_draft_batch.add_argument("--max-items", type=int, default=500, help="Maximum item count accepted from the plan.")
    retire_draft_batch.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    retire_draft_batch.set_defaults(func=command_retire_draft_batch)

    remint_reconcile = subcommands.add_parser(
        "remint-reconcile",
        help="Honestly reconcile a canonical zettel with its mint receipt after newline/BOM or content drift.",
    )
    remint_reconcile.add_argument("archive_root", help="Archive root to inspect.")
    reconcile_target = remint_reconcile.add_mutually_exclusive_group(required=True)
    reconcile_target.add_argument("--zettel-id", help="Canonical zettel id to reconcile.")
    reconcile_target.add_argument("--path", help="Archive-relative canonical zettel path to reconcile.")
    reconcile_mode = remint_reconcile.add_mutually_exclusive_group()
    reconcile_mode.add_argument("--dry-run", action="store_true", help="Classify and preview without writing (default).")
    reconcile_mode.add_argument("--approve", action="store_true", help="Re-issue the mint receipt after human review; requires --reviewed-by.")
    remint_reconcile.add_argument("--reviewed-by", help="Reviewer id required when --approve is used, e.g. person:me.")
    remint_reconcile.add_argument(
        "--content-changed-ack",
        action="store_true",
        help="Human acknowledgment required to approve a content_change reconcile.",
    )
    remint_reconcile.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    remint_reconcile.set_defaults(func=command_remint_reconcile)

    index = subcommands.add_parser("index", help="Build a generated local SQLite search index.")
    index.add_argument("archive_root", help="Archive root to index.")
    index.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    index.set_defaults(func=command_index)

    index_health_parser = subcommands.add_parser(
        "index-health",
        help="Check whether the generated local SQLite index matches live zettel files.",
    )
    index_health_parser.add_argument("archive_root", help="Archive root to inspect.")
    index_health_parser.add_argument("--dry-run", action="store_true", help="Required. Preview only; write nothing.")
    index_health_parser.add_argument("--max-items", type=int, default=50, help="Maximum sample paths to return per drift bucket.")
    index_health_parser.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    index_health_parser.set_defaults(func=command_index_health)

    view_zets_parser = subcommands.add_parser(
        "view-zets",
        help="Execute a saved view's facet filters (views/*.yml) or ad-hoc --facet filters against the index.",
    )
    view_zets_parser.add_argument("archive_root", help="Archive root to inspect.")
    view_zets_parser.add_argument("--view-id", help="Saved view id from views/*.yml (top-level or saved_views).")
    view_zets_parser.add_argument("--facet", action="append", help="Ad-hoc facet filter key=value (repeatable, ANDed).")
    view_zets_parser.add_argument("--limit", type=int, default=50, help="Maximum zets to return.")
    view_zets_parser.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    view_zets_parser.set_defaults(func=command_view_zets)

    view_health_parser = subcommands.add_parser(
        "view-health",
        help="Diagnose saved view hit counts and facet distributions without reading zettel bodies.",
    )
    view_health_parser.add_argument("archive_root", help="Archive root to inspect.")
    view_health_parser.add_argument("--dry-run", action="store_true", help="Required. Preview only; write nothing.")
    view_health_parser.add_argument("--max-values", type=int, default=10, help="Maximum observed values to show per facet key.")
    view_health_parser.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    view_health_parser.set_defaults(func=command_view_health)

    view_recommendation_parser = subcommands.add_parser(
        "view-recommendation-plan",
        help="Plan saved view recommendations from navigation facets without writing views.",
    )
    view_recommendation_parser.add_argument("archive_root", help="Archive root to inspect.")
    view_recommendation_parser.add_argument("--dry-run", action="store_true", help="Required. Preview only; write nothing.")
    view_recommendation_parser.add_argument("--max-values", type=int, default=5, help="Maximum top values to consider per navigation facet key.")
    view_recommendation_parser.add_argument("--max-recommendations", type=int, default=12, help="Maximum recommendations to return.")
    view_recommendation_parser.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    view_recommendation_parser.set_defaults(func=command_view_recommendation_plan)

    related = subcommands.add_parser(
        "related-zets",
        help="List zets related to one zet via typed edges, both directions (backlinks included).",
    )
    related.add_argument("archive_root", help="Archive root to inspect.")
    related.add_argument("--zettel-id", required=True, help="The zet id to find related zets for.")
    related.add_argument("--depth", type=int, default=1, help="Traversal depth (1-3, default 1).")
    related.add_argument("--edge-type", action="append", help="Filter to specific edge types (repeatable).")
    related.add_argument("--limit", type=int, default=100, help="Maximum related zets to return.")
    related.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    related.set_defaults(func=command_related_zets)

    search = subcommands.add_parser("search", help="Search the generated local SQLite search index.")
    search.add_argument("archive_root", help="Archive root to search.")
    search.add_argument("query", help="Search query.")
    search.add_argument("--limit", type=int, default=20, help="Maximum number of results to return.")
    search.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    search.set_defaults(func=command_search)

    pack = subcommands.add_parser(
        "parcel",
        aliases=["pack"],
        help="Create a portable parcel from a saved view. Alias: pack.",
    )
    pack.add_argument("archive_root", help="Source archive root.")
    pack.add_argument("--view", required=True, help="View id to pack.")
    pack.add_argument("--purpose", required=True, help="Reason this workpack exists.")
    pack.add_argument(
        "--mode",
        choices=["reference", "copy", "mount", "derive", "handover", "return"],
        default="reference",
        help="Parcel/workpack mode.",
    )
    pack.add_argument("--target-archive", help="Optional target archive id.")
    pack.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    pack.set_defaults(func=command_pack)

    import_workpack = subcommands.add_parser(
        "admit",
        aliases=["import"],
        help="Preview admitting a parcel/workpack without mutating the target archive. Alias: import.",
    )
    import_workpack.add_argument("archive_root", help="Target archive root.")
    import_workpack.add_argument("workpack", help="Parcel/workpack directory or package.yml file.")
    import_workpack.add_argument("--dry-run", action="store_true", help="Preview admit/import without writing target archive files.")
    import_workpack.add_argument("--counterparty-id", help="Expected sender identity/archive/principal id for trust-gated workpacks.")
    import_workpack.add_argument("--counterparty-fingerprint", help="Expected sender public key fingerprint for trust-gated workpacks.")
    import_workpack.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    import_workpack.set_defaults(func=command_import_workpack)

    staged_cleanup = subcommands.add_parser(
        "staged-cleanup-check",
        help="Report-only G2 verifier: is every staged file preserved as an objet (or deferred) so cleanup would be safe?",
    )
    staged_cleanup.add_argument("archive_root", help="Archive root containing the staged folder.")
    staged_cleanup.add_argument("--staged", required=True, help="Archive-relative staged folder to verify.")
    staged_cleanup.add_argument("--deferred", help="Optional JSON file: {\"deferred\": [staged-relative paths]} explicitly deferred from capture.")
    staged_cleanup.add_argument("--dry-run", action="store_true", help="Required: report-only and never deletes; exits 0 only when safe_to_cleanup is true.")
    staged_cleanup.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    staged_cleanup.set_defaults(func=command_staged_cleanup_check)

    objet_capture_selection = subcommands.add_parser(
        "objet-capture-selection",
        help="Build a reviewed objet-capture selection manifest from one staged file and source-intake receipt.",
    )
    objet_capture_selection.add_argument("archive_root", help="Archive root containing the staged file.")
    objet_capture_selection.add_argument("--staged-path", required=True, help="Archive-relative staged file path.")
    objet_capture_selection.add_argument("--source-intake-receipt", required=True, help="Archive-relative source-intake plan record under receipts/sources/.")
    objet_capture_selection.add_argument("--item-id", default="item", help="Safe item id for the selection manifest.")
    objet_capture_selection.add_argument("--manifest-id", help="Optional safe manifest id; defaults from the object hash.")
    objet_capture_selection.add_argument("--project-intake-receipt", help="Optional archive-relative project-intake decisions receipt.")
    objet_capture_selection.add_argument(
        "--derived-text-staged-path",
        help="Optional archive-relative staged transcript/text file to pair with the staged original in ONE approval.",
    )
    objet_capture_selection.add_argument(
        "--derivation-kind",
        choices=sorted(archive_services.DERIVED_TEXT_DERIVATION_KINDS),
        help="How the paired text was derived from the staged original (required with --derived-text-staged-path).",
    )
    objet_capture_selection.add_argument("--tool-name", help="Extractor/OCR/ASR/vision tool name for the paired text (required with --derived-text-staged-path).")
    objet_capture_selection.add_argument("--tool-version", help="Extractor/OCR/ASR/vision tool version for the paired text (required with --derived-text-staged-path).")
    objet_capture_selection.add_argument(
        "--review-status",
        choices=sorted(archive_services.DERIVED_TEXT_REVIEW_STATUSES),
        help="Review status for the paired text (required with --derived-text-staged-path).",
    )
    objet_capture_selection.add_argument("--model-name", help="Optional model name for model-dependent paired-text derivations.")
    objet_capture_selection.add_argument("--model-version", help="Optional model version for model-dependent paired-text derivations.")
    objet_capture_selection.add_argument("--confidence", type=float, help="Optional paired-text confidence from 0.0 to 1.0.")
    objet_capture_selection.add_argument("--language", help="Optional BCP-47-ish language tag for the paired text, e.g. ko or en.")
    objet_capture_selection.add_argument("--born-digital", action="store_true", help="Mark the paired text as extracted from born-digital content.")
    objet_capture_selection.add_argument("--dry-run", action="store_true", help="Preview the selection manifest without writing.")
    objet_capture_selection.add_argument("--approve", action="store_true", help="Write the reviewed selection manifest only; does not run capture.")
    objet_capture_selection.add_argument("--reviewed-by", help="Reviewer id required when --approve is used.")
    objet_capture_selection.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    objet_capture_selection.set_defaults(func=command_objet_capture_selection)

    objet_capture = subcommands.add_parser(
        "objet-capture",
        help="Dry-run or approve capturing selected staged files into the local content-addressed objet store.",
    )
    objet_capture.add_argument("archive_root", help="Archive root (sandbox-marked, or enabled via objet-capture-enable).")
    objet_capture.add_argument("--selection", required=True, help="B4 selection manifest JSON path.")
    objet_capture.add_argument("--dry-run", action="store_true", help="Preview the capture plan without writing files.")
    objet_capture.add_argument("--approve", action="store_true", help="Capture bytes, append manifest records, write a receipt.")
    objet_capture.add_argument("--reviewed-by", help="Reviewer id required for approved capture.")
    objet_capture.add_argument(
        "--project-intake-receipt",
        help="Optional project-intake decisions receipt to validate as capture-session context only.",
    )
    objet_capture.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    objet_capture.set_defaults(func=command_objet_capture)

    derive_text = subcommands.add_parser(
        "derive-text",
        help="Register extracted text as provenance-aware derived text records.",
    )
    derive_text_subcommands = derive_text.add_subparsers(dest="derive_text_command", required=True)
    derive_text_capture = derive_text_subcommands.add_parser(
        "capture",
        help="Dry-run or approve registering extracted/OCR/ASR/vision text.",
    )
    derive_text_capture.add_argument("archive_root", help="Archive root receiving the derived text record.")
    derive_text_capture.add_argument("--from-manifest", help="JSONL batch manifest of derived text capture items.")
    derive_text_capture.add_argument("--text-file", help="UTF-8 extracted text file to capture.")
    derive_text_capture.add_argument("--source-object-id", help="Source object_id from objects/manifests/files.jsonl.")
    derive_text_capture.add_argument(
        "--derivation-kind",
        choices=sorted(archive_services.DERIVED_TEXT_DERIVATION_KINDS),
        help="How this text was derived from the source object.",
    )
    derive_text_capture.add_argument("--tool-name", help="Extractor/OCR/ASR/vision tool name.")
    derive_text_capture.add_argument("--tool-version", help="Extractor/OCR/ASR/vision tool version.")
    derive_text_capture.add_argument("--model-name", help="Optional model name for model-dependent derivations.")
    derive_text_capture.add_argument("--model-version", help="Optional model version for model-dependent derivations.")
    derive_text_capture.add_argument("--confidence", type=float, help="Optional confidence from 0.0 to 1.0.")
    derive_text_capture.add_argument("--language", help="Optional BCP-47-ish language tag, e.g. ko or en.")
    derive_text_capture.add_argument(
        "--review-status",
        choices=sorted(archive_services.DERIVED_TEXT_REVIEW_STATUSES),
        help="Review status for this derived text.",
    )
    derive_text_capture.add_argument("--born-digital", action="store_true", help="Mark text as extracted from born-digital content.")
    derive_text_capture.add_argument("--dry-run", action="store_true", help="Preview derived text capture without writing files.")
    derive_text_capture.add_argument("--approve", action="store_true", help="Store derived text, append manifest record, and write receipt.")
    derive_text_capture.add_argument("--reviewed-by", help="Reviewer id required for approved capture.")
    derive_text_capture.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    derive_text_capture.set_defaults(func=command_derive_text_capture)

    derive_text_coverage = derive_text_subcommands.add_parser(
        "coverage",
        help="Check textual objet derived-text coverage without reading source bodies.",
    )
    derive_text_coverage.add_argument("archive_root", help="Archive root to inspect.")
    derive_text_coverage.add_argument("--max-items", type=int, default=25, help="Maximum missing/blocked object ids to include.")
    derive_text_coverage.add_argument("--dry-run", action="store_true", help="Required; read-only coverage gate.")
    derive_text_coverage.add_argument("--format", choices=["text", "json"], default="json", help="Output format.")
    derive_text_coverage.set_defaults(func=command_derive_text_coverage)

    derive_text_toolchain = derive_text_subcommands.add_parser(
        "toolchain",
        help="Recommend a derived-text extraction route for one format without running tools.",
    )
    derive_text_toolchain.add_argument("archive_root", help="Archive root to inspect.")
    derive_text_toolchain.add_argument("--extension", help="File extension such as .pdf, .docx, .hwp, or .ppt.")
    derive_text_toolchain.add_argument("--mime", help="Optional MIME type hint.")
    derive_text_toolchain.add_argument("--dry-run", action="store_true", help="Required; read-only toolchain recommendation.")
    derive_text_toolchain.add_argument("--format", choices=["text", "json"], default="json", help="Output format.")
    derive_text_toolchain.set_defaults(func=command_derive_text_toolchain)

    derive_text_doctor = derive_text_subcommands.add_parser(
        "doctor",
        help="Check local derived-text toolchain readiness without echoing tool paths.",
    )
    derive_text_doctor.add_argument("archive_root", help="Archive root to inspect.")
    derive_text_doctor.add_argument("--tool-hints", help="Optional JSON file with executable path hints; paths are never echoed.")
    derive_text_doctor.add_argument("--dry-run", action="store_true", help="Required; read-only toolchain readiness check.")
    derive_text_doctor.add_argument("--format", choices=["text", "json"], default="json", help="Output format.")
    derive_text_doctor.set_defaults(func=command_derive_text_doctor)

    derive_text_agent_contract = derive_text_subcommands.add_parser(
        "agent-contract",
        help="Print the derived-text agent operating contract.",
    )
    derive_text_agent_contract.add_argument("archive_root", help="Archive root to inspect.")
    derive_text_agent_contract.add_argument("--dry-run", action="store_true", help="Required; read-only agent contract.")
    derive_text_agent_contract.add_argument("--format", choices=["text", "json"], default="json", help="Output format.")
    derive_text_agent_contract.set_defaults(func=command_derive_text_agent_contract)

    derive_text_coverage_alias = subcommands.add_parser(
        "derive-text-coverage",
        help="Alias for derive-text coverage.",
    )
    derive_text_coverage_alias.add_argument("archive_root", help="Archive root to inspect.")
    derive_text_coverage_alias.add_argument("--max-items", type=int, default=25, help="Maximum missing/blocked object ids to include.")
    derive_text_coverage_alias.add_argument("--dry-run", action="store_true", help="Required; read-only coverage gate.")
    derive_text_coverage_alias.add_argument("--format", choices=["text", "json"], default="json", help="Output format.")
    derive_text_coverage_alias.set_defaults(func=command_derive_text_coverage)

    derive_text_toolchain_alias = subcommands.add_parser(
        "derive-text-toolchain",
        help="Alias for derive-text toolchain.",
    )
    derive_text_toolchain_alias.add_argument("archive_root", help="Archive root to inspect.")
    derive_text_toolchain_alias.add_argument("--extension", help="File extension such as .pdf, .docx, .hwp, or .ppt.")
    derive_text_toolchain_alias.add_argument("--mime", help="Optional MIME type hint.")
    derive_text_toolchain_alias.add_argument("--dry-run", action="store_true", help="Required; read-only toolchain recommendation.")
    derive_text_toolchain_alias.add_argument("--format", choices=["text", "json"], default="json", help="Output format.")
    derive_text_toolchain_alias.set_defaults(func=command_derive_text_toolchain)

    derive_text_doctor_alias = subcommands.add_parser(
        "derive-text-doctor",
        help="Alias for derive-text doctor.",
    )
    derive_text_doctor_alias.add_argument("archive_root", help="Archive root to inspect.")
    derive_text_doctor_alias.add_argument("--tool-hints", help="Optional JSON file with executable path hints; paths are never echoed.")
    derive_text_doctor_alias.add_argument("--dry-run", action="store_true", help="Required; read-only toolchain readiness check.")
    derive_text_doctor_alias.add_argument("--format", choices=["text", "json"], default="json", help="Output format.")
    derive_text_doctor_alias.set_defaults(func=command_derive_text_doctor)

    derive_text_agent_contract_alias = subcommands.add_parser(
        "derive-text-agent-contract",
        help="Alias for derive-text agent-contract.",
    )
    derive_text_agent_contract_alias.add_argument("archive_root", help="Archive root to inspect.")
    derive_text_agent_contract_alias.add_argument("--dry-run", action="store_true", help="Required; read-only agent contract.")
    derive_text_agent_contract_alias.add_argument("--format", choices=["text", "json"], default="json", help="Output format.")
    derive_text_agent_contract_alias.set_defaults(func=command_derive_text_agent_contract)

    external_export_plan = subcommands.add_parser(
        "external-export-plan",
        help="Plan a text-first external export before large media downloads.",
    )
    external_export_plan.add_argument("archive_root", help="Archive root to inspect.")
    external_export_plan.add_argument(
        "--source",
        required=True,
        choices=sorted(archive_services.EXTERNAL_EXPORT_PLAN_SOURCES),
        help="External source/export surface to plan.",
    )
    external_export_plan.add_argument(
        "--export-goal",
        default="text_only",
        choices=sorted(archive_services.EXTERNAL_EXPORT_GOALS),
        help="Human-reviewed export goal.",
    )
    external_export_plan.add_argument(
        "--media-policy",
        default="avoid_bulk_media",
        choices=sorted(archive_services.EXTERNAL_EXPORT_MEDIA_POLICIES),
        help="How to treat uploaded files and large media before export.",
    )
    external_export_plan.add_argument(
        "--estimated-media-gb",
        type=float,
        help="Optional rough media-size estimate for risk classification.",
    )
    external_export_plan.add_argument("--dry-run", action="store_true", help="Required; read-only export preflight.")
    external_export_plan.add_argument("--format", choices=["text", "json"], default="json", help="Output format.")
    external_export_plan.set_defaults(func=command_external_export_plan)

    connection_import_plan = subcommands.add_parser(
        "connection-import-plan",
        help="Plan Notion connection evidence import into WOM typed-edge candidates, including containment.",
    )
    connection_import_plan.add_argument("archive_root", help="Archive root to inspect.")
    connection_import_plan.add_argument(
        "--source",
        required=True,
        choices=sorted(archive_services.CONNECTION_IMPORT_SOURCES),
        help="External connection evidence source.",
    )
    connection_import_plan.add_argument(
        "--connection-kind",
        default="all",
        choices=["all"] + sorted(archive_services.CONNECTION_IMPORT_KINDS),
        help="Specific connection evidence kind to plan.",
    )
    connection_import_plan.add_argument("--dry-run", action="store_true", help="Required; read-only connection import plan.")
    connection_import_plan.add_argument("--format", choices=["text", "json"], default="json", help="Output format.")
    connection_import_plan.set_defaults(func=command_connection_import_plan)

    connection_evidence_parser_contract = subcommands.add_parser(
        "connection-evidence-parser-contract",
        aliases=["connection-parser-contract", "notion-connection-parser-contract"],
        help="Preview the read-only contract a future Notion connection evidence parser must satisfy.",
    )
    connection_evidence_parser_contract.add_argument("archive_root", help="Archive root to inspect.")
    connection_evidence_parser_contract.add_argument(
        "--source",
        required=True,
        choices=sorted(archive_services.CONNECTION_IMPORT_SOURCES),
        help="External connection evidence source.",
    )
    connection_evidence_parser_contract.add_argument(
        "--connection-kind",
        default="all",
        choices=["all"] + sorted(archive_services.CONNECTION_IMPORT_KINDS),
        help="Specific connection evidence kind to contract.",
    )
    connection_evidence_parser_contract.add_argument(
        "--dry-run",
        action="store_true",
        help="Required. Contract only; never reads exports, parses files, writes candidates, or writes edges.",
    )
    connection_evidence_parser_contract.add_argument("--format", choices=["text", "json"], default="json", help="Output format.")
    connection_evidence_parser_contract.set_defaults(func=command_connection_evidence_parser_contract)

    connection_evidence_parse_fixture = subcommands.add_parser(
        "connection-evidence-parse-fixture",
        aliases=["connection-evidence-parser-fixture", "notion-connection-evidence-parser-fixture"],
        help="Parse a sanitized archive-internal connection evidence fixture into read-only candidate edge previews.",
    )
    connection_evidence_parse_fixture.add_argument("archive_root", help="Archive root to inspect.")
    connection_evidence_parse_fixture.add_argument(
        "--evidence",
        required=True,
        help="Archive-relative sanitized fixture JSON path. Absolute paths and provider URLs are rejected.",
    )
    connection_evidence_parse_fixture.add_argument(
        "--source",
        required=True,
        choices=sorted(archive_services.CONNECTION_IMPORT_SOURCES),
        help="External connection evidence source declared by the fixture.",
    )
    connection_evidence_parse_fixture.add_argument(
        "--connection-kind",
        default="all",
        choices=["all"] + sorted(archive_services.CONNECTION_IMPORT_KINDS),
        help="Specific connection evidence kind to parse from the fixture.",
    )
    connection_evidence_parse_fixture.add_argument("--max-items", type=int, default=100, help="Maximum fixture records to parse.")
    connection_evidence_parse_fixture.add_argument(
        "--dry-run",
        action="store_true",
        help="Required. Parses sanitized fixture metadata only; never writes candidates, zets, edges, receipts, or manifests.",
    )
    connection_evidence_parse_fixture.add_argument("--format", choices=["text", "json"], default="json", help="Output format.")
    connection_evidence_parse_fixture.set_defaults(func=command_connection_evidence_parse_fixture)

    connection_edge_intelligence_plan = subcommands.add_parser(
        "connection-edge-intelligence-plan",
        aliases=["connection-edge-classification-plan"],
        help="Plan meaning/mechanism classification for sanitized connection fixture candidates.",
    )
    connection_edge_intelligence_plan.add_argument("archive_root", help="Archive root to inspect.")
    connection_edge_intelligence_plan.add_argument(
        "--evidence",
        required=True,
        help="Archive-relative sanitized fixture JSON path. Absolute paths and provider URLs are rejected.",
    )
    connection_edge_intelligence_plan.add_argument(
        "--source",
        required=True,
        choices=sorted(archive_services.CONNECTION_IMPORT_SOURCES),
        help="External connection evidence source declared by the fixture.",
    )
    connection_edge_intelligence_plan.add_argument(
        "--connection-kind",
        default="all",
        choices=["all"] + sorted(archive_services.CONNECTION_IMPORT_KINDS),
        help="Specific connection evidence kind to classify from the fixture.",
    )
    connection_edge_intelligence_plan.add_argument("--max-items", type=int, default=100, help="Maximum fixture records to parse.")
    connection_edge_intelligence_plan.add_argument(
        "--dry-run",
        action="store_true",
        help="Required. Classifies sanitized fixture candidates only; never calls AI/LLMs, reads bodies, writes candidates, zets, edges, receipts, or manifests.",
    )
    connection_edge_intelligence_plan.add_argument("--format", choices=["text", "json"], default="json", help="Output format.")
    connection_edge_intelligence_plan.set_defaults(func=command_connection_edge_intelligence_plan)

    notion_nested_tree_plan = subcommands.add_parser(
        "notion-nested-tree-plan",
        aliases=["notion-nested-page-tree-plan", "notion-child-page-recovery-plan"],
        help="Plan nested Notion child-page recovery from a sanitized tree fixture.",
    )
    notion_nested_tree_plan.add_argument("archive_root", help="Archive root to inspect.")
    notion_nested_tree_plan.add_argument(
        "--tree",
        required=True,
        help="Archive-relative sanitized nested-tree fixture JSON path. Absolute paths and provider URLs are rejected.",
    )
    notion_nested_tree_plan.add_argument(
        "--source",
        required=True,
        choices=sorted(archive_services.NOTION_NESTED_TREE_SOURCES),
        help="External nested tree source declared by the fixture.",
    )
    notion_nested_tree_plan.add_argument(
        "--max-items",
        type=int,
        default=1000,
        help=(
            "Maximum fixture nodes to parse. Range 1-100000. "
            "If the fixture is larger, the command blocks instead of returning a partial success."
        ),
    )
    notion_nested_tree_plan.add_argument(
        "--dry-run",
        action="store_true",
        help="Required. Parses sanitized tree metadata only; never reads real exports, writes zets, writes edges, or mints pages.",
    )
    notion_nested_tree_plan.add_argument("--format", choices=["text", "json"], default="json", help="Output format.")
    notion_nested_tree_plan.set_defaults(func=command_notion_nested_tree_plan)

    notion_ancestor_crawl_plan = subcommands.add_parser(
        "notion-ancestor-crawl-plan",
        aliases=["notion-nested-ancestor-crawl-plan", "notion-parent-chain-crawl-plan"],
        help="Plan missing Notion ancestor crawl requests from a sanitized nested tree fixture.",
    )
    notion_ancestor_crawl_plan.add_argument("archive_root", help="Archive root to inspect.")
    notion_ancestor_crawl_plan.add_argument(
        "--tree",
        required=True,
        help="Archive-relative sanitized nested-tree fixture JSON path. Absolute paths and provider URLs are rejected.",
    )
    notion_ancestor_crawl_plan.add_argument(
        "--source",
        required=True,
        choices=sorted(archive_services.NOTION_NESTED_TREE_SOURCES),
        help="External nested tree source declared by the fixture.",
    )
    notion_ancestor_crawl_plan.add_argument(
        "--max-items",
        type=int,
        default=1000,
        help=(
            "Maximum fixture nodes to parse while deriving missing ancestor requests. Range 1-100000. "
            "Oversized fixtures block instead of returning partial crawl queues."
        ),
    )
    notion_ancestor_crawl_plan.add_argument(
        "--max-depth",
        type=int,
        default=16,
        help="Maximum future parent-chain crawl depth to request per missing ancestor. Range 1-64.",
    )
    notion_ancestor_crawl_plan.add_argument(
        "--scope-generation-id",
        action="append",
        help="Optional generation id filter for broad workspace fixtures. Repeat to include more than one generation.",
    )
    notion_ancestor_crawl_plan.add_argument(
        "--scope-root-ref",
        action="append",
        help="Optional safe root/ref filter matched against request refs before a future adapter receives the queue. Repeatable.",
    )
    notion_ancestor_crawl_plan.add_argument(
        "--scope-ancestor-ref",
        action="append",
        help="Optional exact ancestor_ref filter. Repeatable.",
    )
    notion_ancestor_crawl_plan.add_argument(
        "--scope-leaf-ref",
        action="append",
        help="Optional exact affected leaf ref filter. Repeatable.",
    )
    notion_ancestor_crawl_plan.add_argument(
        "--dry-run",
        action="store_true",
        help="Required. Packages missing ancestor crawl requests only; never calls providers, reads titles or bodies, or writes fixtures.",
    )
    notion_ancestor_crawl_plan.add_argument("--format", choices=["text", "json"], default="json", help="Output format.")
    notion_ancestor_crawl_plan.set_defaults(func=command_notion_ancestor_crawl_plan)

    notion_ancestor_fetch_contract = subcommands.add_parser(
        "notion-ancestor-fetch-adapter-execution-contract",
        aliases=["notion-ancestor-fetch-execution-contract", "notion-ancestor-crawl-adapter-execution-contract"],
        help="Preview the read-only execution contract a future Notion ancestor fetch adapter must satisfy.",
    )
    notion_ancestor_fetch_contract.add_argument("archive_root", help="Archive root to inspect.")
    notion_ancestor_fetch_contract.add_argument(
        "--tree",
        required=True,
        help="Archive-relative sanitized nested-tree fixture JSON path. Absolute paths and provider URLs are rejected.",
    )
    notion_ancestor_fetch_contract.add_argument(
        "--source",
        required=True,
        choices=sorted(archive_services.NOTION_NESTED_TREE_SOURCES),
        help="External nested tree source declared by the fixture.",
    )
    notion_ancestor_fetch_contract.add_argument(
        "--credential-ref",
        help="Optional safe env/keyring/secret/wallet ref label. Exact value is validated but never echoed.",
    )
    notion_ancestor_fetch_contract.add_argument(
        "--max-items",
        type=int,
        default=1000,
        help="Maximum fixture nodes to parse while deriving missing ancestor requests. Oversized fixtures block.",
    )
    notion_ancestor_fetch_contract.add_argument(
        "--max-depth",
        type=int,
        default=16,
        help="Maximum future parent-chain crawl depth to request per missing ancestor. Range 1-64.",
    )
    notion_ancestor_fetch_contract.add_argument(
        "--scope-generation-id",
        action="append",
        help="Optional generation id filter for broad workspace fixtures. Repeat to include more than one generation.",
    )
    notion_ancestor_fetch_contract.add_argument(
        "--scope-root-ref",
        action="append",
        help="Optional safe root/ref filter matched against request refs before a future adapter receives the queue. Repeatable.",
    )
    notion_ancestor_fetch_contract.add_argument(
        "--scope-ancestor-ref",
        action="append",
        help="Optional exact ancestor_ref filter. Repeatable.",
    )
    notion_ancestor_fetch_contract.add_argument(
        "--scope-leaf-ref",
        action="append",
        help="Optional exact affected leaf ref filter. Repeatable.",
    )
    notion_ancestor_fetch_contract.add_argument(
        "--dry-run",
        action="store_true",
        help="Required. Contract only; never calls Notion, retrieves secrets, reads titles or bodies, or writes files.",
    )
    notion_ancestor_fetch_contract.add_argument("--format", choices=["text", "json"], default="json", help="Output format.")
    notion_ancestor_fetch_contract.set_defaults(func=command_notion_ancestor_fetch_adapter_execution_contract)

    notion_ancestor_fetch_run = subcommands.add_parser(
        "notion-ancestor-fetch-adapter-run",
        aliases=["notion-ancestor-fetch-run", "notion-ancestor-live-fetch"],
        help="Run the approval-gated local Notion ancestor structure fetch adapter.",
    )
    notion_ancestor_fetch_run.add_argument("archive_root", help="Archive root to update.")
    notion_ancestor_fetch_run.add_argument(
        "--tree",
        required=True,
        help="Archive-relative sanitized nested-tree fixture JSON path. Absolute paths and provider URLs are rejected.",
    )
    notion_ancestor_fetch_run.add_argument(
        "--output",
        default="workbench/notion-ancestor-result.live.json",
        help="Archive-relative sanitized ancestor result fixture path under workbench/. Existing files are not overwritten.",
    )
    notion_ancestor_fetch_run.add_argument(
        "--source",
        required=True,
        choices=sorted(archive_services.NOTION_NESTED_TREE_SOURCES),
        help="External nested tree source declared by the fixture.",
    )
    notion_ancestor_fetch_run.add_argument(
        "--credential-id",
        default="cred:notion-readonly",
        help="Safe non-secret credential label for the approval receipt.",
    )
    notion_ancestor_fetch_run.add_argument(
        "--credential-ref",
        help="Required with --approve. Must be an env: ref for the first live Notion ancestor fetch; exact value is never echoed.",
    )
    notion_ancestor_fetch_run.add_argument("--credential-kind", default="provider_api_key", help="Credential kind label.")
    notion_ancestor_fetch_run.add_argument("--credential-provider", default="notion", help="Credential provider label.")
    notion_ancestor_fetch_run.add_argument(
        "--store-kind",
        default="environment",
        choices=sorted(archive_services.CREDENTIAL_ACCESS_BROKER_STORE_KINDS),
        help="Credential store kind. First live run supports environment only.",
    )
    notion_ancestor_fetch_run.add_argument(
        "--adapter-kind",
        default="environment_injection",
        choices=sorted(archive_services.CREDENTIAL_ADAPTER_KINDS),
        help="Credential adapter kind. First live run supports environment_injection only.",
    )
    notion_ancestor_fetch_run.add_argument(
        "--approval-decision",
        default="needs_review",
        choices=sorted(archive_services.CREDENTIAL_ACCESS_APPROVAL_DECISIONS),
        help="Use approve_once with --approve after writing a matching credential-access-approval receipt.",
    )
    notion_ancestor_fetch_run.add_argument(
        "--approval-receipt",
        help="Archive-relative credential access approval receipt path. Required with --approve; not echoed in result details.",
    )
    notion_ancestor_fetch_run.add_argument(
        "--consumer",
        default="wom:adapter:notion-ancestor-fetch",
        help="Safe consumer label that must match the approval receipt.",
    )
    notion_ancestor_fetch_run.add_argument("--reviewed-by", default="human:pending-review", help="Safe reviewer label.")
    notion_ancestor_fetch_run.add_argument(
        "--platform",
        default="windows",
        choices=sorted(archive_services.CREDENTIAL_STORE_RECOMMENDATION_PLATFORMS),
        help="Credential platform policy label.",
    )
    notion_ancestor_fetch_run.add_argument(
        "--notion-version",
        default=archive_services.NOTION_API_DEFAULT_VERSION,
        help="Notion API version header. Defaults to the conservative stable version.",
    )
    notion_ancestor_fetch_run.add_argument("--timeout-seconds", type=int, default=30, help="Provider request timeout, 1-120 seconds.")
    notion_ancestor_fetch_run.add_argument(
        "--max-items",
        type=int,
        default=1000,
        help="Maximum fixture nodes to parse while deriving missing ancestor requests. Oversized fixtures block.",
    )
    notion_ancestor_fetch_run.add_argument(
        "--max-depth",
        type=int,
        default=16,
        help="Maximum parent-chain crawl depth per missing ancestor. Range 1-64.",
    )
    notion_ancestor_fetch_run.add_argument(
        "--scope-generation-id",
        action="append",
        help="Optional generation id filter for broad workspace fixtures. Repeat to include more than one generation.",
    )
    notion_ancestor_fetch_run.add_argument(
        "--scope-root-ref",
        action="append",
        help="Optional safe root/ref filter matched against request refs before the live adapter receives the queue. Repeatable.",
    )
    notion_ancestor_fetch_run.add_argument(
        "--scope-ancestor-ref",
        action="append",
        help="Optional exact ancestor_ref filter. Repeatable.",
    )
    notion_ancestor_fetch_run.add_argument(
        "--scope-leaf-ref",
        action="append",
        help="Optional exact affected leaf ref filter. Repeatable.",
    )
    notion_ancestor_fetch_run.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview without reading environment variables, calling Notion, or writing files.",
    )
    notion_ancestor_fetch_run.add_argument(
        "--approve",
        action="store_true",
        help="Run the local Notion ancestor structure fetch and write sanitized fixture plus non-secret receipt.",
    )
    notion_ancestor_fetch_run.add_argument("--format", choices=["text", "json"], default="json", help="Output format.")
    notion_ancestor_fetch_run.set_defaults(func=command_notion_ancestor_fetch_adapter_run)

    notion_recover = subcommands.add_parser(
        "notion-recover",
        aliases=["notion-location-recover", "notion-recovery"],
        help="Beginner-friendly one-command Notion missing-location recovery wrapper.",
    )
    notion_recover.add_argument(
        "archive_root",
        nargs="?",
        default=".",
        help="Archive root to update. Defaults to the current directory so `archive notion-recover` works from an archive root.",
    )
    notion_recover.add_argument(
        "--tree",
        help="Optional archive-relative sanitized nested-tree fixture. Usually omitted; WOM auto-selects the one missing-location fixture.",
    )
    notion_recover.add_argument(
        "--output",
        default=archive_services.NOTION_RECOVER_DEFAULT_OUTPUT_PATH,
        help="Archive-relative sanitized ancestor result fixture path under workbench/. Existing files are not overwritten.",
    )
    notion_recover.add_argument(
        "--source",
        default="notion",
        choices=sorted(archive_services.NOTION_NESTED_TREE_SOURCES),
        help="External nested tree source declared by the fixture.",
    )
    notion_recover.add_argument(
        "--credential-ref",
        help="Optional local credential handoff. Supports env refs and CLI-only file:<path> fallback; exact refs, paths, and values are not echoed.",
    )
    notion_recover.add_argument("--reviewed-by", default="human:local-operator", help="Safe reviewer label for the local approval receipt.")
    notion_recover.add_argument(
        "--platform",
        default="windows",
        choices=sorted(archive_services.CREDENTIAL_STORE_RECOMMENDATION_PLATFORMS),
        help="Credential platform policy label.",
    )
    notion_recover.add_argument(
        "--notion-version",
        default=archive_services.NOTION_API_DEFAULT_VERSION,
        help="Notion API version header. Defaults to the conservative stable version.",
    )
    notion_recover.add_argument("--timeout-seconds", type=int, default=30, help="Provider request timeout, 1-120 seconds.")
    notion_recover.add_argument(
        "--max-items",
        type=int,
        default=1000,
        help="Maximum fixture nodes to parse while deriving missing ancestor requests. Oversized fixtures block.",
    )
    notion_recover.add_argument(
        "--max-depth",
        type=int,
        default=16,
        help="Maximum parent-chain crawl depth per missing ancestor. Range 1-64.",
    )
    notion_recover.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview the one-command recovery without reading environment variables, calling Notion, or writing files.",
    )
    notion_recover.add_argument(
        "--approve",
        action="store_true",
        help="Run the one-command local recovery wrapper. Without --yes, an interactive terminal confirmation is required.",
    )
    notion_recover.add_argument(
        "--yes",
        action="store_true",
        help="Skip the confirmation prompt for local automation. Secrets are still never echoed.",
    )
    notion_recover.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    notion_recover.set_defaults(func=command_notion_recover)

    notion_connection_plan = subcommands.add_parser(
        "notion-connection-plan",
        aliases=["notion-connect-plan", "notion-one-click-connection-plan"],
        help="Preview the product contract for one-click Notion connection and actionable recovery failures.",
    )
    notion_connection_plan.add_argument(
        "archive_root",
        nargs="?",
        default=".",
        help="Archive root to inspect. Defaults to the current directory.",
    )
    notion_connection_plan.add_argument("--dry-run", action="store_true", help="Required; writes nothing and calls no provider.")
    notion_connection_plan.add_argument("--format", choices=["text", "json"], default="json", help="Output format.")
    notion_connection_plan.set_defaults(func=command_notion_connection_plan)

    notion_oauth_preflight = subcommands.add_parser(
        "notion-oauth-connection-preflight",
        aliases=["notion-oauth-preflight", "notion-connect-oauth-preflight"],
        help="Validate the secret-blind local OAuth connection contract before a future live Notion browser flow.",
    )
    notion_oauth_preflight.add_argument(
        "archive_root",
        nargs="?",
        default=".",
        help="Archive root to inspect. Defaults to the current directory.",
    )
    notion_oauth_preflight.add_argument(
        "--client-id-ref",
        help="Safe env/keyring/secret/wallet ref for the Notion OAuth client id. The exact ref is validated but never echoed.",
    )
    notion_oauth_preflight.add_argument(
        "--client-secret-ref",
        help="Safe env/keyring/secret/wallet ref for the Notion OAuth client secret. The exact ref is validated but never echoed.",
    )
    notion_oauth_preflight.add_argument(
        "--redirect-uri",
        help="Local loopback callback URI to validate. The exact URI is never echoed.",
    )
    notion_oauth_preflight.add_argument(
        "--state-ref",
        help="Optional safe ref where a live runtime would store a one-time OAuth state. The exact ref is never echoed.",
    )
    notion_oauth_preflight.add_argument(
        "--token-store-ref",
        help="Safe keyring/secret/wallet ref for future access and refresh tokens. Env refs are rejected for token storage.",
    )
    notion_oauth_preflight.add_argument("--dry-run", action="store_true", help="Required; writes nothing and calls no provider.")
    notion_oauth_preflight.add_argument("--format", choices=["text", "json"], default="json", help="Output format.")
    notion_oauth_preflight.set_defaults(func=command_notion_oauth_connection_preflight)

    notion_media_fetch_contract = subcommands.add_parser(
        "notion-media-fetch-adapter-execution-contract",
        aliases=["notion-media-fetch-execution-contract", "notion-nested-leaf-media-fetch-contract"],
        help="Preview the read-only execution contract a future Notion media byte fetch adapter must satisfy.",
    )
    notion_media_fetch_contract.add_argument("archive_root", help="Archive root to inspect.")
    notion_media_fetch_contract.add_argument(
        "--tree",
        required=True,
        help="Archive-relative sanitized nested-tree fixture JSON path. Absolute paths and provider URLs are rejected.",
    )
    notion_media_fetch_contract.add_argument(
        "--source",
        required=True,
        choices=sorted(archive_services.NOTION_NESTED_TREE_SOURCES),
        help="External nested tree source declared by the fixture.",
    )
    notion_media_fetch_contract.add_argument(
        "--credential-ref",
        help="Optional safe env/keyring/secret/wallet ref label. Exact value is validated but never echoed.",
    )
    notion_media_fetch_contract.add_argument(
        "--max-items",
        type=int,
        default=1000,
        help="Maximum fixture nodes to parse while deriving media fetch candidate pages. Oversized fixtures block.",
    )
    notion_media_fetch_contract.add_argument(
        "--scope-generation-id",
        action="append",
        help="Optional generation id filter for broad workspace fixtures. Repeat to include more than one generation.",
    )
    notion_media_fetch_contract.add_argument(
        "--scope-root-ref",
        action="append",
        help="Optional safe root/ref filter matched before a future media adapter receives the queue. Repeatable.",
    )
    notion_media_fetch_contract.add_argument(
        "--scope-leaf-ref",
        action="append",
        help="Optional exact nested leaf page ref filter. Repeatable.",
    )
    notion_media_fetch_contract.add_argument(
        "--dry-run",
        action="store_true",
        help="Required. Contract only; never calls Notion, retrieves secrets, downloads media bytes, hashes bytes, or writes files.",
    )
    notion_media_fetch_contract.add_argument("--format", choices=["text", "json"], default="json", help="Output format.")
    notion_media_fetch_contract.set_defaults(func=command_notion_media_fetch_adapter_execution_contract)

    notion_media_result_verification = subcommands.add_parser(
        "notion-media-result-verification-plan",
        aliases=["notion-media-result-verify-plan", "notion-media-preservation-verification-plan"],
        help="Verify a sanitized Notion media result fixture against object manifests without reading bytes.",
    )
    notion_media_result_verification.add_argument("archive_root", help="Archive root to inspect.")
    notion_media_result_verification.add_argument(
        "--media-result",
        required=True,
        help="Archive-relative sanitized notion_media_result_fixture JSON path.",
    )
    notion_media_result_verification.add_argument(
        "--source",
        required=True,
        choices=sorted(archive_services.NOTION_NESTED_TREE_SOURCES),
        help="External source declared by the fixture.",
    )
    notion_media_result_verification.add_argument(
        "--max-items",
        type=int,
        default=1000,
        help="Maximum media result rows to verify. Oversized fixtures block.",
    )
    notion_media_result_verification.add_argument(
        "--dry-run",
        action="store_true",
        help="Required. Reads only sanitized fixture metadata and object manifests; never reads or hashes media bytes.",
    )
    notion_media_result_verification.add_argument("--format", choices=["text", "json"], default="json", help="Output format.")
    notion_media_result_verification.set_defaults(func=command_notion_media_result_verification_plan)

    notion_block_mirror_tree_fixture_plan = subcommands.add_parser(
        "notion-block-mirror-tree-fixture-plan",
        aliases=["notion-nested-tree-fixture-plan", "notion-mirror-tree-fixture-plan"],
        help="Build a sanitized nested tree fixture preview from reviewed Notion block mirror metadata.",
    )
    notion_block_mirror_tree_fixture_plan.add_argument("archive_root", help="Archive root to inspect.")
    notion_block_mirror_tree_fixture_plan.add_argument(
        "--mirror",
        required=True,
        help="Archive-relative reviewed Notion block mirror fixture JSON path. Absolute paths and provider URLs are rejected.",
    )
    notion_block_mirror_tree_fixture_plan.add_argument(
        "--source",
        required=True,
        choices=sorted(archive_services.NOTION_NESTED_TREE_SOURCES),
        help="External block mirror source declared by the fixture.",
    )
    notion_block_mirror_tree_fixture_plan.add_argument(
        "--max-items",
        type=int,
        default=100000,
        help="Maximum mirror records to parse. Range 1-100000. Oversized mirrors block instead of returning partial fixtures.",
    )
    notion_block_mirror_tree_fixture_plan.add_argument(
        "--dry-run",
        action="store_true",
        help="Required. Builds a sanitized fixture preview only; never calls providers, reads titles or bodies, or writes fixtures.",
    )
    notion_block_mirror_tree_fixture_plan.add_argument("--format", choices=["text", "json"], default="json", help="Output format.")
    notion_block_mirror_tree_fixture_plan.set_defaults(func=command_notion_block_mirror_tree_fixture_plan)

    notion_ancestor_merge_plan = subcommands.add_parser(
        "notion-ancestor-merge-plan",
        aliases=["notion-nested-tree-merge-plan", "notion-ancestor-result-merge-plan"],
        help="Merge sanitized ancestor result nodes into a nested tree fixture preview and replan.",
    )
    notion_ancestor_merge_plan.add_argument("archive_root", help="Archive root to inspect.")
    notion_ancestor_merge_plan.add_argument(
        "--tree",
        required=True,
        help="Archive-relative sanitized nested-tree fixture JSON path. Absolute paths and provider URLs are rejected.",
    )
    notion_ancestor_merge_plan.add_argument(
        "--ancestors",
        required=True,
        help="Archive-relative sanitized ancestor result fixture JSON path. Absolute paths and provider URLs are rejected.",
    )
    notion_ancestor_merge_plan.add_argument(
        "--source",
        required=True,
        choices=sorted(archive_services.NOTION_NESTED_TREE_SOURCES),
        help="External source declared by both fixtures.",
    )
    notion_ancestor_merge_plan.add_argument(
        "--max-items",
        type=int,
        default=100000,
        help="Maximum merged fixture nodes to replan. Range 1-100000.",
    )
    notion_ancestor_merge_plan.add_argument(
        "--dry-run",
        action="store_true",
        help="Required. Merges sanitized metadata in memory only; never calls providers, reads titles or bodies, or writes fixtures.",
    )
    notion_ancestor_merge_plan.add_argument("--format", choices=["text", "json"], default="json", help="Output format.")
    notion_ancestor_merge_plan.set_defaults(func=command_notion_ancestor_merge_plan)

    notion_client_issue_verification_plan = subcommands.add_parser(
        "notion-client-issue-verification-plan",
        aliases=["notion-tree-verification-plan", "notion-nested-tree-verification-plan"],
        help="Verify a client Notion nested-tree issue from sanitized local fixtures.",
    )
    notion_client_issue_verification_plan.add_argument("archive_root", help="Archive root to inspect.")
    notion_client_issue_verification_plan.add_argument(
        "--tree",
        help="Optional archive-relative sanitized nested-tree fixture JSON path. Absolute paths and provider URLs are rejected.",
    )
    notion_client_issue_verification_plan.add_argument(
        "--mirror",
        help="Optional archive-relative reviewed Notion block mirror fixture JSON path. Absolute paths and provider URLs are rejected.",
    )
    notion_client_issue_verification_plan.add_argument(
        "--ancestors",
        help=(
            "Optional archive-relative sanitized ancestor result fixture JSON path. "
            "Requires --tree in this release; no fixture files are written."
        ),
    )
    notion_client_issue_verification_plan.add_argument(
        "--source",
        required=True,
        choices=sorted(archive_services.NOTION_NESTED_TREE_SOURCES),
        help="External source declared by the sanitized fixtures.",
    )
    notion_client_issue_verification_plan.add_argument(
        "--max-items",
        type=int,
        default=100000,
        help="Maximum fixture nodes or mirror records to parse. Range 1-100000.",
    )
    notion_client_issue_verification_plan.add_argument(
        "--max-depth",
        type=int,
        default=16,
        help="Maximum future parent-chain crawl depth to request per missing ancestor. Range 1-64.",
    )
    notion_client_issue_verification_plan.add_argument(
        "--dry-run",
        action="store_true",
        help="Required. Verifies sanitized fixtures only; never calls providers, reads titles or bodies, or writes fixtures.",
    )
    notion_client_issue_verification_plan.add_argument(
        "--format", choices=["text", "json"], default="json", help="Output format."
    )
    notion_client_issue_verification_plan.set_defaults(func=command_notion_client_issue_verification_plan)

    notion_client_fixture_request_plan = subcommands.add_parser(
        "notion-client-fixture-request-plan",
        aliases=["notion-fixture-request-plan", "notion-client-verification-request-plan"],
        help="Package the sanitized fixture request contract for client Notion issue verification.",
    )
    notion_client_fixture_request_plan.add_argument("archive_root", help="Archive root to inspect.")
    notion_client_fixture_request_plan.add_argument(
        "--tree",
        help="Optional archive-relative sanitized nested-tree fixture JSON path for current-state preview.",
    )
    notion_client_fixture_request_plan.add_argument(
        "--mirror",
        help="Optional archive-relative reviewed block mirror fixture JSON path for current-state preview.",
    )
    notion_client_fixture_request_plan.add_argument(
        "--ancestors",
        help="Optional archive-relative sanitized ancestor result fixture JSON path for current-state preview.",
    )
    notion_client_fixture_request_plan.add_argument(
        "--source",
        required=True,
        choices=sorted(archive_services.NOTION_NESTED_TREE_SOURCES),
        help="External source declared by the future sanitized fixtures.",
    )
    notion_client_fixture_request_plan.add_argument(
        "--scenario",
        default="missing_ancestor",
        choices=["missing_ancestor", "nested_tree", "block_mirror", "ancestor_merge"],
        help="Client fixture request scenario.",
    )
    notion_client_fixture_request_plan.add_argument(
        "--max-items",
        type=int,
        default=100000,
        help="Maximum fixture nodes or mirror records to parse when preview inputs are supplied. Range 1-100000.",
    )
    notion_client_fixture_request_plan.add_argument(
        "--max-depth",
        type=int,
        default=16,
        help="Maximum future parent-chain crawl depth to request per missing ancestor. Range 1-64.",
    )
    notion_client_fixture_request_plan.add_argument(
        "--dry-run",
        action="store_true",
        help="Required. Builds a non-secret request package only; never sends messages, calls providers, or writes fixtures.",
    )
    notion_client_fixture_request_plan.add_argument("--format", choices=["text", "json"], default="json", help="Output format.")
    notion_client_fixture_request_plan.set_defaults(func=command_notion_client_fixture_request_plan)

    zettel_edge = subcommands.add_parser(
        "zettel-edge",
        aliases=["link-zettel-edge", "write-zettel-edge"],
        help="Preview or approve one typed edge from a zettel to another zettel or manifested objet.",
    )
    zettel_edge.add_argument("archive_root", help="Archive root to update.")
    zettel_edge.add_argument("--from-zettel", help="Source zettel id. Mutually exclusive with --from-path.")
    zettel_edge.add_argument("--from-path", help="Source archive-relative zettel path. Mutually exclusive with --from-zettel.")
    zettel_edge.add_argument("--target", required=True, help="Target zet_<id>, sha256:<64hex>, or objet:sha256:<64hex> ref.")
    zettel_edge.add_argument("--edge-type", required=True, help="Typed edge id from zettel-kasten/types.yml.")
    zettel_edge.add_argument("--visibility", default="private", help="Safe edge visibility label. Default: private.")
    zettel_edge.add_argument("--dry-run", action="store_true", help="Preview the edge and receipt path without writing files.")
    zettel_edge.add_argument("--approve", action="store_true", help="Write the reviewed edge and receipt.")
    zettel_edge.add_argument("--reviewed-by", help="Safe reviewer id required with --approve.")
    zettel_edge.add_argument("--format", choices=["text", "json"], default="json", help="Output format.")
    zettel_edge.set_defaults(func=command_zettel_edge)

    zettel_edge_batch = subcommands.add_parser(
        "zettel-edge-batch",
        aliases=["bulk-zettel-edge", "batch-zettel-edge"],
        help="Preview or approve policy-gated bulk typed edge writes from a reviewed JSON plan.",
    )
    zettel_edge_batch.add_argument("archive_root", help="Archive root to update.")
    zettel_edge_batch.add_argument("--plan", required=True, help="JSON batch plan with policy and edges.")
    zettel_edge_batch.add_argument("--dry-run", action="store_true", help="Preview all policy-writable edges without writing files.")
    zettel_edge_batch.add_argument("--approve", action="store_true", help="Write policy-writable edges and a batch receipt.")
    zettel_edge_batch.add_argument("--reviewed-by", help="Safe reviewer id required with --approve.")
    zettel_edge_batch.add_argument("--max-edges", type=int, default=200, help="Maximum edge rows accepted from the batch plan.")
    zettel_edge_batch.add_argument("--skip-existing", action="store_true", help="Skip already-written edges or receipts instead of blocking the whole batch.")
    zettel_edge_batch.add_argument("--format", choices=["text", "json"], default="json", help="Output format.")
    zettel_edge_batch.set_defaults(func=command_zettel_edge_batch)

    revert_edge = subcommands.add_parser(
        "revert-edge",
        aliases=["rollback-edge"],
        help="Preview or approve removing one edge using its zettel-edge write receipt.",
    )
    revert_edge.add_argument("archive_root", help="Archive root to update.")
    revert_edge.add_argument("--receipt", required=True, help="Archive-relative receipts/edges/*.zettel-edge.json path.")
    revert_edge.add_argument("--dry-run", action="store_true", help="Preview the edge removal and revert receipt path without writing files.")
    revert_edge.add_argument("--approve", action="store_true", help="Remove the reviewed edge and write a revert receipt.")
    revert_edge.add_argument("--reviewed-by", help="Safe reviewer id required with --approve.")
    revert_edge.add_argument("--format", choices=["text", "json"], default="json", help="Output format.")
    revert_edge.set_defaults(func=command_revert_edge)

    revert_batch = subcommands.add_parser(
        "revert-batch",
        aliases=["rollback-batch"],
        help="Preview or approve removing all edges listed in a zettel-edge-batch receipt.",
    )
    revert_batch.add_argument("archive_root", help="Archive root to update.")
    revert_batch.add_argument("--receipt", required=True, help="Archive-relative receipts/edges/batches/*.zettel-edge-batch.json path.")
    revert_batch.add_argument("--dry-run", action="store_true", help="Preview all edge removals and the batch revert receipt without writing files.")
    revert_batch.add_argument("--approve", action="store_true", help="Remove all reviewed batch edges and write revert receipts.")
    revert_batch.add_argument("--reviewed-by", help="Safe reviewer id required with --approve.")
    revert_batch.add_argument("--format", choices=["text", "json"], default="json", help="Output format.")
    revert_batch.set_defaults(func=command_revert_batch)

    import_external = subcommands.add_parser("import-external", help="Import Notion or Google Drive exports as inbox drafts.")
    import_external.add_argument("archive_root", help="Target archive root.")
    import_external.add_argument("--source", required=True, choices=sorted(archive_services.EXTERNAL_IMPORT_SOURCES), help="External source system.")
    import_external.add_argument("--export", required=True, help="Export folder or JSON/YAML manifest to import.")
    import_external.add_argument("--dry-run", action="store_true", help="Preview import without writing archive files.")
    import_external.add_argument("--approve", action="store_true", help="Write imported items to inbox and record a receipt.")
    import_external.add_argument("--reviewed-by", help="Reviewer id required for approved import.")
    import_external.add_argument("--limit", type=int, default=200, help="Maximum number of external items to import.")
    import_external.add_argument(
        "--provider-locator-policy",
        choices=sorted(archive_services.EXTERNAL_IMPORT_PROVIDER_LOCATOR_POLICIES),
        default="preserve",
        help="How to handle provider locators found in imported bodies. object-ref converts supported Notion locators to an objet ref when exactly one object source ref is present.",
    )
    import_external.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    import_external.set_defaults(func=command_import_external)

    share = subcommands.add_parser("share", help="Legacy: dry-run a governed archive share from a saved view.")
    share.add_argument("archive_root", help="Source archive root.")
    share.add_argument("--view", required=True, help="View id to share.")
    share.add_argument("--target-archive", required=True, help="Target archive id.")
    share.add_argument("--counterparty-id", help="Expected counterparty identity/archive/principal id.")
    share.add_argument("--counterparty-fingerprint", help="Expected counterparty public key fingerprint.")
    share.add_argument("--allow-sensitive", action="store_true", help="Allow sensitive categories in the dry-run manifest.")
    share.add_argument("--dry-run", action="store_true", help="Preview sharing without writing or sending files.")
    share.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    share.set_defaults(func=command_share)

    delegate = subcommands.add_parser("delegate-zet", help="Preview or write delegated access to zets from a saved view.")
    delegate.add_argument("archive_root", help="Source archive root.")
    delegate.add_argument("--view", required=True, help="View id to delegate.")
    delegate.add_argument("--target-archive", help="Target archive id. Required for counterparty_bound delegation.")
    delegate.add_argument(
        "--target-policy",
        choices=sorted(archive_services.DELEGATE_TARGET_POLICIES),
        default=archive_services.DELEGATE_DEFAULT_TARGET_POLICY,
        help="Delegation target policy. claimable_once can defer the recipient until attestation.",
    )
    delegate.add_argument("--counterparty-id", help="Expected counterparty identity/archive/principal id.")
    delegate.add_argument("--counterparty-fingerprint", help="Expected counterparty public key fingerprint.")
    delegate.add_argument("--allow-sensitive", action="store_true", help="Allow sensitive categories in the delegation gate.")
    delegate.add_argument("--dry-run", action="store_true", help="Preview delegation without writing or sending files.")
    delegate.add_argument("--approve", action="store_true", help="Write a delegate receipt after dry-run gates pass.")
    delegate.add_argument("--reviewed-by", help="Reviewer id required for real delegation, e.g. person:me.")
    delegate.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    delegate.set_defaults(func=command_delegate_zet)

    attest = subcommands.add_parser("attest-zet", help="Dry-run attestation of a delegated foreign zet receipt.")
    attest.add_argument("archive_root", help="Attesting archive root.")
    attest.add_argument("--delegate-receipt", required=True, help="Archive-relative or absolute delegate receipt JSON path.")
    attest.add_argument("--counterparty-id", help="Expected source archive/principal id. Defaults to receipt source_archive.")
    attest.add_argument("--counterparty-fingerprint", help="Expected source public key fingerprint.")
    attest.add_argument("--dry-run", action="store_true", help="Preview attestation without writing files.")
    attest.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    attest.set_defaults(func=command_attest_zet)

    anchor = subcommands.add_parser("anchor-zet", help="Dry-run anchoring of an attested foreign zet into local meaning.")
    anchor.add_argument("archive_root", help="Anchoring archive root.")
    anchor.add_argument("--attestation-receipt", required=True, help="Archive-relative or absolute attestation receipt JSON path.")
    anchor.add_argument("--dry-run", action="store_true", help="Preview anchoring without writing files.")
    anchor.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    anchor.set_defaults(func=command_anchor_zet)

    check_safe_html = subcommands.add_parser(
        "check-safe-html",
        help="Dry-run check whether a Markdown-compatible zet is compatible with a future WOM Safe HTML Profile migration.",
    )
    check_safe_html.add_argument("archive_root", help="Archive root containing the zet.")
    check_safe_html.add_argument(
        "--path",
        required=True,
        help="Archive-relative zet path inside inbox/ or zettels/.",
    )
    check_safe_html.add_argument(
        "--dry-run",
        action="store_true",
        help="Required. Preview Safe HTML compatibility without writing files.",
    )
    check_safe_html.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format.",
    )
    check_safe_html.set_defaults(func=command_check_safe_html)

    providers = subcommands.add_parser("providers", help="Inspect external provider bindings and manual change plans.")
    providers.add_argument("archive_root", help="Archive root to inspect.")
    providers.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    providers.set_defaults(func=command_providers)

    provider_status = subcommands.add_parser(
        "provider-status",
        help="Dry-run check local provider setup metadata and receipts without calling providers.",
    )
    provider_status.add_argument("archive_root", help="Archive root to inspect.")
    provider_status.add_argument("--dry-run", action="store_true", help="Required. Read provider metadata and receipts only.")
    provider_status.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    provider_status.set_defaults(func=command_provider_status)

    object_storage_adapter_readiness = subcommands.add_parser(
        "object-storage-adapter-readiness-plan",
        aliases=["object-storage-adapter-plan", "objet-storage-adapter-readiness"],
        help="Check readiness for a future object-storage adapter without provider calls.",
    )
    object_storage_adapter_readiness.add_argument("archive_root", help="Archive root to inspect.")
    object_storage_adapter_readiness.add_argument(
        "--operation",
        choices=sorted(archive_services.OBJECT_STORAGE_ADAPTER_OPERATIONS),
        default="presigned_download",
        help="Future object-storage adapter operation to evaluate.",
    )
    object_storage_adapter_readiness.add_argument(
        "--provider-ref",
        help="Optional safe provider binding label/ref. Do not pass a URL, path, token, or secret.",
    )
    object_storage_adapter_readiness.add_argument("--dry-run", action="store_true", help="Required. Plan only; never calls providers.")
    object_storage_adapter_readiness.add_argument("--format", choices=["text", "json"], default="json", help="Output format.")
    object_storage_adapter_readiness.set_defaults(func=command_object_storage_adapter_readiness_plan)

    imap_mailbox_adapter_readiness = subcommands.add_parser(
        "imap-mailbox-adapter-readiness-plan",
        aliases=["imap-mailbox-adapter-plan", "mailbox-adapter-readiness"],
        help="Check readiness for a future IMAP mailbox adapter without connecting or reading mail.",
    )
    imap_mailbox_adapter_readiness.add_argument("archive_root", help="Archive root to inspect.")
    imap_mailbox_adapter_readiness.add_argument("--source-id", required=True, help="Stable source id, e.g. imap:gmail-personal.")
    imap_mailbox_adapter_readiness.add_argument(
        "--adapter-id",
        help="Optional safe adapter manifest id to check under config/imap-adapters/.",
    )
    imap_mailbox_adapter_readiness.add_argument(
        "--provider",
        choices=sorted(archive_services.IMAP_MAILBOX_ALLOWED_PROVIDERS),
        default="generic_imap",
        help="Provider preset. generic_imap requires --imap-host.",
    )
    imap_mailbox_adapter_readiness.add_argument("--imap-host", help="Safe IMAP host label. Required for generic_imap.")
    imap_mailbox_adapter_readiness.add_argument("--imap-port", type=int, default=993, help="IMAP SSL port. Defaults to 993.")
    imap_mailbox_adapter_readiness.add_argument(
        "--account-ref",
        required=True,
        help="Safe account reference, e.g. imap:account:personal-mail. Do not pass an email address.",
    )
    imap_mailbox_adapter_readiness.add_argument(
        "--username-ref",
        required=True,
        help="env/keyring/secret/wallet reference for the username. Do not pass the username value.",
    )
    imap_mailbox_adapter_readiness.add_argument(
        "--auth-mode",
        choices=sorted(archive_services.IMAP_MAILBOX_ALLOWED_AUTH_MODES),
        default="app_password_ref",
        help="Credential reference kind.",
    )
    imap_mailbox_adapter_readiness.add_argument(
        "--app-password-ref",
        help="env/keyring/secret/wallet reference for an app password. Do not pass the password value.",
    )
    imap_mailbox_adapter_readiness.add_argument(
        "--oauth-token-ref",
        help="env/keyring/secret/wallet reference for an OAuth token. Do not pass the token value.",
    )
    imap_mailbox_adapter_readiness.add_argument(
        "--mailbox-ref",
        default="imap:mailbox:inbox",
        help="Safe mailbox reference. Do not pass private mailbox names.",
    )
    imap_mailbox_adapter_readiness.add_argument(
        "--operation",
        choices=sorted(archive_services.IMAP_MAILBOX_OPERATION_REQUEST_OPERATIONS),
        default="header_metadata_scan",
        help="Future IMAP mailbox operation to evaluate.",
    )
    imap_mailbox_adapter_readiness.add_argument(
        "--max-messages",
        type=int,
        default=archive_services.IMAP_MAILBOX_OPERATION_MAX_MESSAGES_DEFAULT,
        help="Future message limit to request. Must be between 1 and 2000.",
    )
    imap_mailbox_adapter_readiness.add_argument(
        "--since-days",
        type=int,
        help="Optional future recency window. Must be between 1 and 3650 days.",
    )
    imap_mailbox_adapter_readiness.add_argument(
        "--credential-id",
        default="cred:mail-source-access",
        help="Safe credential label for the future mail credential.",
    )
    imap_mailbox_adapter_readiness.add_argument("--credential-ref", help="Optional env/keyring/secret/wallet ref; exact value is not echoed.")
    imap_mailbox_adapter_readiness.add_argument(
        "--credential-kind",
        choices=sorted(archive_services.CREDENTIAL_REF_ALLOWED_KINDS),
        help="Credential kind. Defaults from IMAP auth mode.",
    )
    imap_mailbox_adapter_readiness.add_argument(
        "--credential-provider",
        choices=sorted(archive_services.CREDENTIAL_REF_ALLOWED_PROVIDERS),
        help="Credential provider label. Defaults from IMAP provider.",
    )
    imap_mailbox_adapter_readiness.add_argument(
        "--store-kind",
        choices=sorted(archive_services.CREDENTIAL_ACCESS_BROKER_STORE_KINDS),
        default="password_manager",
        help="Credential store class for the future mail credential retrieval.",
    )
    imap_mailbox_adapter_readiness.add_argument(
        "--adapter-kind",
        choices=sorted(archive_services.CREDENTIAL_ADAPTER_KINDS),
        help="Future credential adapter kind. Defaults from store kind and platform.",
    )
    imap_mailbox_adapter_readiness.add_argument(
        "--approval-decision",
        choices=sorted(archive_services.CREDENTIAL_ACCESS_APPROVAL_DECISIONS),
        default="needs_review",
        help="Human decision state to evaluate.",
    )
    imap_mailbox_adapter_readiness.add_argument(
        "--approval-receipt",
        help="Archive-relative approval receipt path to verify. The path is not echoed in output.",
    )
    imap_mailbox_adapter_readiness.add_argument("--consumer", default="wom:adapter:imap-mailbox", help="Safe label for the future adapter.")
    imap_mailbox_adapter_readiness.add_argument("--reviewed-by", default="human:pending-review", help="Safe non-secret reviewer label.")
    imap_mailbox_adapter_readiness.add_argument(
        "--platform",
        choices=sorted(archive_services.CREDENTIAL_STORE_RECOMMENDATION_PLATFORMS),
        default="windows",
        help="Local platform for default credential adapter selection.",
    )
    imap_mailbox_adapter_readiness.add_argument("--dry-run", action="store_true", help="Required. Plan only; never connects to IMAP or reads secrets.")
    imap_mailbox_adapter_readiness.add_argument("--format", choices=["text", "json"], default="json", help="Output format.")
    imap_mailbox_adapter_readiness.set_defaults(func=command_imap_mailbox_adapter_readiness_plan)

    imap_mailbox_selection = subcommands.add_parser(
        "imap-mailbox-selection-plan",
        aliases=["imap-mailbox-message-selection-plan", "mailbox-selection-plan"],
        help="Plan future read-only mailbox message selection without connecting, listing messages, or reading mail.",
    )
    imap_mailbox_selection.add_argument("archive_root", help="Archive root to inspect.")
    imap_mailbox_selection.add_argument("--source-id", required=True, help="Stable source id, e.g. imap:gmail-personal.")
    imap_mailbox_selection.add_argument(
        "--provider",
        choices=sorted(archive_services.IMAP_MAILBOX_ALLOWED_PROVIDERS),
        default="generic_imap",
        help="Provider preset. generic_imap requires --imap-host.",
    )
    imap_mailbox_selection.add_argument("--imap-host", help="Safe IMAP host label. Required for generic_imap.")
    imap_mailbox_selection.add_argument("--imap-port", type=int, default=993, help="IMAP SSL port. Defaults to 993.")
    imap_mailbox_selection.add_argument(
        "--account-ref",
        required=True,
        help="Safe account reference, e.g. imap:account:personal-mail. Do not pass an email address.",
    )
    imap_mailbox_selection.add_argument(
        "--username-ref",
        required=True,
        help="env/keyring/secret/wallet reference for the username. Do not pass the username value.",
    )
    imap_mailbox_selection.add_argument(
        "--auth-mode",
        choices=sorted(archive_services.IMAP_MAILBOX_ALLOWED_AUTH_MODES),
        default="app_password_ref",
        help="Credential reference kind.",
    )
    imap_mailbox_selection.add_argument(
        "--app-password-ref",
        help="env/keyring/secret/wallet reference for an app password. Do not pass the password value.",
    )
    imap_mailbox_selection.add_argument(
        "--oauth-token-ref",
        help="env/keyring/secret/wallet reference for an OAuth token. Do not pass the token value.",
    )
    imap_mailbox_selection.add_argument(
        "--mailbox-ref",
        default="imap:mailbox:inbox",
        help="Safe mailbox reference. Do not pass private mailbox names.",
    )
    imap_mailbox_selection.add_argument(
        "--operation",
        choices=sorted(archive_services.IMAP_MAILBOX_OPERATION_REQUEST_OPERATIONS),
        default="header_metadata_scan",
        help="Future IMAP mailbox operation to evaluate.",
    )
    imap_mailbox_selection.add_argument(
        "--selection-rule",
        choices=sorted(archive_services.IMAP_MAILBOX_SELECTION_RULES),
        default="newest_first",
        help="Future non-secret mailbox selection rule.",
    )
    imap_mailbox_selection.add_argument(
        "--selector-id",
        default="mail-selection:recent-inbox",
        help="Safe non-secret selector label. Do not pass subjects, senders, emails, mailbox names, URLs, or paths.",
    )
    imap_mailbox_selection.add_argument(
        "--max-messages",
        type=int,
        default=archive_services.IMAP_MAILBOX_OPERATION_MAX_MESSAGES_DEFAULT,
        help="Future message candidate limit to request. Must be between 1 and 2000.",
    )
    imap_mailbox_selection.add_argument(
        "--since-days",
        type=int,
        help="Optional future recency window. Must be between 1 and 3650 days.",
    )
    imap_mailbox_selection.add_argument(
        "--credential-id",
        default="cred:mail-source-access",
        help="Safe credential label for the future mail credential.",
    )
    imap_mailbox_selection.add_argument("--credential-ref", help="Optional env/keyring/secret/wallet ref; exact value is not echoed.")
    imap_mailbox_selection.add_argument(
        "--credential-kind",
        choices=sorted(archive_services.CREDENTIAL_REF_ALLOWED_KINDS),
        help="Credential kind. Defaults from IMAP auth mode.",
    )
    imap_mailbox_selection.add_argument(
        "--credential-provider",
        choices=sorted(archive_services.CREDENTIAL_REF_ALLOWED_PROVIDERS),
        help="Credential provider label. Defaults from IMAP provider.",
    )
    imap_mailbox_selection.add_argument(
        "--store-kind",
        choices=sorted(archive_services.CREDENTIAL_ACCESS_BROKER_STORE_KINDS),
        default="password_manager",
        help="Credential store class for the future mail credential retrieval.",
    )
    imap_mailbox_selection.add_argument(
        "--adapter-kind",
        choices=sorted(archive_services.CREDENTIAL_ADAPTER_KINDS),
        help="Future credential adapter kind. Defaults from store kind and platform.",
    )
    imap_mailbox_selection.add_argument(
        "--approval-decision",
        choices=sorted(archive_services.CREDENTIAL_ACCESS_APPROVAL_DECISIONS),
        default="needs_review",
        help="Human decision state to evaluate.",
    )
    imap_mailbox_selection.add_argument(
        "--approval-receipt",
        help="Archive-relative approval receipt path to verify. The path is not echoed in output.",
    )
    imap_mailbox_selection.add_argument("--consumer", default="wom:adapter:imap-mailbox", help="Safe label for the future adapter.")
    imap_mailbox_selection.add_argument("--reviewed-by", default="human:pending-review", help="Safe non-secret reviewer label.")
    imap_mailbox_selection.add_argument(
        "--platform",
        choices=sorted(archive_services.CREDENTIAL_STORE_RECOMMENDATION_PLATFORMS),
        default="windows",
        help="Local platform for default credential adapter selection.",
    )
    imap_mailbox_selection.add_argument("--dry-run", action="store_true", help="Required. Plan only; never connects, selects, searches, lists, or reads mail.")
    imap_mailbox_selection.add_argument("--format", choices=["text", "json"], default="json", help="Output format.")
    imap_mailbox_selection.set_defaults(func=command_imap_mailbox_selection_plan)

    imap_mailbox_adapter_manifest = subcommands.add_parser(
        "imap-mailbox-adapter-manifest-plan",
        aliases=["imap-mailbox-adapter-manifest", "mailbox-adapter-manifest-plan"],
        help="Preview a non-secret future IMAP adapter manifest without connecting or reading mail.",
    )
    imap_mailbox_adapter_manifest.add_argument("archive_root", help="Archive root to inspect.")
    imap_mailbox_adapter_manifest.add_argument(
        "--adapter-id",
        required=True,
        help="Safe local adapter id, e.g. local-imap. Do not pass paths, URLs, emails, or secrets.",
    )
    imap_mailbox_adapter_manifest.add_argument(
        "--provider",
        action="append",
        choices=sorted(archive_services.IMAP_MAILBOX_ALLOWED_PROVIDERS),
        help="Supported provider label. May be repeated; defaults to all current IMAP providers.",
    )
    imap_mailbox_adapter_manifest.add_argument(
        "--operation",
        action="append",
        choices=sorted(archive_services.IMAP_MAILBOX_OPERATION_REQUEST_OPERATIONS),
        help="Supported future operation. May be repeated; defaults to all current IMAP operation labels.",
    )
    imap_mailbox_adapter_manifest.add_argument(
        "--selection-rule",
        action="append",
        choices=sorted(archive_services.IMAP_MAILBOX_SELECTION_RULES),
        help="Supported future selection rule. May be repeated; defaults to all current selection rules.",
    )
    imap_mailbox_adapter_manifest.add_argument("--consumer", default="wom:adapter:imap-mailbox", help="Safe label for the future adapter.")
    imap_mailbox_adapter_manifest.add_argument(
        "--platform",
        choices=sorted(archive_services.CREDENTIAL_STORE_RECOMMENDATION_PLATFORMS),
        default="windows",
        help="Local platform context.",
    )
    imap_mailbox_adapter_manifest.add_argument("--dry-run", action="store_true", help="Required. Preview only; never writes manifests, connects, lists, or reads mail.")
    imap_mailbox_adapter_manifest.add_argument("--format", choices=["text", "json"], default="json", help="Output format.")
    imap_mailbox_adapter_manifest.set_defaults(func=command_imap_mailbox_adapter_manifest_plan)

    imap_mailbox_adapter_manifest_write = subcommands.add_parser(
        "imap-mailbox-adapter-manifest-write",
        aliases=["mailbox-adapter-manifest-write"],
        help="Preview or approve writing a non-secret IMAP adapter manifest without connecting or reading mail.",
    )
    imap_mailbox_adapter_manifest_write.add_argument("archive_root", help="Archive root to inspect.")
    imap_mailbox_adapter_manifest_write.add_argument(
        "--adapter-id",
        required=True,
        help="Safe local adapter id, e.g. local-imap. Do not pass paths, URLs, emails, or secrets.",
    )
    imap_mailbox_adapter_manifest_write.add_argument(
        "--provider",
        action="append",
        choices=sorted(archive_services.IMAP_MAILBOX_ALLOWED_PROVIDERS),
        help="Supported provider label. May be repeated; defaults to all current IMAP providers.",
    )
    imap_mailbox_adapter_manifest_write.add_argument(
        "--operation",
        action="append",
        choices=sorted(archive_services.IMAP_MAILBOX_OPERATION_REQUEST_OPERATIONS),
        help="Supported future operation. May be repeated; defaults to all current IMAP operation labels.",
    )
    imap_mailbox_adapter_manifest_write.add_argument(
        "--selection-rule",
        action="append",
        choices=sorted(archive_services.IMAP_MAILBOX_SELECTION_RULES),
        help="Supported future selection rule. May be repeated; defaults to all current selection rules.",
    )
    imap_mailbox_adapter_manifest_write.add_argument("--consumer", default="wom:adapter:imap-mailbox", help="Safe label for the future adapter.")
    imap_mailbox_adapter_manifest_write.add_argument("--reviewed-by", help="Safe non-secret reviewer label. Required with --approve.")
    imap_mailbox_adapter_manifest_write.add_argument(
        "--platform",
        choices=sorted(archive_services.CREDENTIAL_STORE_RECOMMENDATION_PLATFORMS),
        default="windows",
        help="Local platform context.",
    )
    imap_mailbox_adapter_manifest_write.add_argument("--dry-run", action="store_true", help="Preview the manifest and write receipt without writing files.")
    imap_mailbox_adapter_manifest_write.add_argument("--approve", action="store_true", help="Write the non-secret manifest and write receipt after local human review.")
    imap_mailbox_adapter_manifest_write.add_argument("--format", choices=["text", "json"], default="json", help="Output format.")
    imap_mailbox_adapter_manifest_write.set_defaults(func=command_imap_mailbox_adapter_manifest_write)

    imap_mailbox_adapter_audit = subcommands.add_parser(
        "imap-mailbox-adapter-audit-plan",
        aliases=["imap-mailbox-adapter-audit", "mailbox-adapter-audit-plan"],
        help="Preview a non-secret future IMAP adapter audit receipt without connecting, listing messages, or reading mail.",
    )
    imap_mailbox_adapter_audit.add_argument("archive_root", help="Archive root to inspect.")
    imap_mailbox_adapter_audit.add_argument(
        "--adapter-id",
        required=True,
        help="Safe local adapter id, e.g. local-imap. Do not pass paths, URLs, emails, or secrets.",
    )
    imap_mailbox_adapter_audit.add_argument("--source-id", required=True, help="Stable source id, e.g. imap:gmail-personal.")
    imap_mailbox_adapter_audit.add_argument(
        "--provider",
        choices=sorted(archive_services.IMAP_MAILBOX_ALLOWED_PROVIDERS),
        default="generic_imap",
        help="Provider preset. generic_imap requires --imap-host.",
    )
    imap_mailbox_adapter_audit.add_argument("--imap-host", help="Safe IMAP host label. Required for generic_imap.")
    imap_mailbox_adapter_audit.add_argument("--imap-port", type=int, default=993, help="IMAP SSL port. Defaults to 993.")
    imap_mailbox_adapter_audit.add_argument(
        "--account-ref",
        required=True,
        help="Safe account reference, e.g. imap:account:personal-mail. Do not pass an email address.",
    )
    imap_mailbox_adapter_audit.add_argument(
        "--username-ref",
        required=True,
        help="env/keyring/secret/wallet reference for the username. Do not pass the username value.",
    )
    imap_mailbox_adapter_audit.add_argument(
        "--auth-mode",
        choices=sorted(archive_services.IMAP_MAILBOX_ALLOWED_AUTH_MODES),
        default="app_password_ref",
        help="Credential reference kind.",
    )
    imap_mailbox_adapter_audit.add_argument(
        "--app-password-ref",
        help="env/keyring/secret/wallet reference for an app password. Do not pass the password value.",
    )
    imap_mailbox_adapter_audit.add_argument(
        "--oauth-token-ref",
        help="env/keyring/secret/wallet reference for an OAuth token. Do not pass the token value.",
    )
    imap_mailbox_adapter_audit.add_argument(
        "--mailbox-ref",
        default="imap:mailbox:inbox",
        help="Safe mailbox reference. Do not pass private mailbox names.",
    )
    imap_mailbox_adapter_audit.add_argument(
        "--operation",
        choices=sorted(archive_services.IMAP_MAILBOX_OPERATION_REQUEST_OPERATIONS),
        default="header_metadata_scan",
        help="Future IMAP mailbox operation to audit.",
    )
    imap_mailbox_adapter_audit.add_argument(
        "--selection-rule",
        choices=sorted(archive_services.IMAP_MAILBOX_SELECTION_RULES),
        default="newest_first",
        help="Future non-secret mailbox selection rule.",
    )
    imap_mailbox_adapter_audit.add_argument(
        "--selector-id",
        default="mail-selection:recent-inbox",
        help="Safe non-secret selector label. Do not pass subjects, senders, emails, mailbox names, URLs, or paths.",
    )
    imap_mailbox_adapter_audit.add_argument(
        "--max-messages",
        type=int,
        default=archive_services.IMAP_MAILBOX_OPERATION_MAX_MESSAGES_DEFAULT,
        help="Future message candidate limit to request. Must be between 1 and 2000.",
    )
    imap_mailbox_adapter_audit.add_argument(
        "--since-days",
        type=int,
        help="Optional future recency window. Must be between 1 and 3650 days.",
    )
    imap_mailbox_adapter_audit.add_argument(
        "--credential-id",
        default="cred:mail-source-access",
        help="Safe credential label for the future mail credential.",
    )
    imap_mailbox_adapter_audit.add_argument("--credential-ref", help="Optional env/keyring/secret/wallet ref; exact value is not echoed.")
    imap_mailbox_adapter_audit.add_argument(
        "--credential-kind",
        choices=sorted(archive_services.CREDENTIAL_REF_ALLOWED_KINDS),
        help="Credential kind. Defaults from IMAP auth mode.",
    )
    imap_mailbox_adapter_audit.add_argument(
        "--credential-provider",
        choices=sorted(archive_services.CREDENTIAL_REF_ALLOWED_PROVIDERS),
        help="Credential provider label. Defaults from IMAP provider.",
    )
    imap_mailbox_adapter_audit.add_argument(
        "--store-kind",
        choices=sorted(archive_services.CREDENTIAL_ACCESS_BROKER_STORE_KINDS),
        default="password_manager",
        help="Credential store class for the future mail credential retrieval.",
    )
    imap_mailbox_adapter_audit.add_argument(
        "--adapter-kind",
        choices=sorted(archive_services.CREDENTIAL_ADAPTER_KINDS),
        help="Future credential adapter kind. Defaults from store kind and platform.",
    )
    imap_mailbox_adapter_audit.add_argument(
        "--approval-decision",
        choices=sorted(archive_services.CREDENTIAL_ACCESS_APPROVAL_DECISIONS),
        default="needs_review",
        help="Human decision state to evaluate.",
    )
    imap_mailbox_adapter_audit.add_argument(
        "--approval-receipt",
        help="Archive-relative approval receipt path to verify. The path is not echoed in output.",
    )
    imap_mailbox_adapter_audit.add_argument(
        "--result-status",
        choices=sorted(archive_services.IMAP_MAILBOX_ADAPTER_AUDIT_RESULT_STATUSES),
        default="not_run",
        help="Non-secret future adapter outcome status to preview.",
    )
    imap_mailbox_adapter_audit.add_argument("--consumer", default="wom:adapter:imap-mailbox", help="Safe label for the future adapter.")
    imap_mailbox_adapter_audit.add_argument("--reviewed-by", default="human:pending-review", help="Safe non-secret reviewer label.")
    imap_mailbox_adapter_audit.add_argument(
        "--platform",
        choices=sorted(archive_services.CREDENTIAL_STORE_RECOMMENDATION_PLATFORMS),
        default="windows",
        help="Local platform for default credential adapter selection.",
    )
    imap_mailbox_adapter_audit.add_argument("--dry-run", action="store_true", help="Required. Preview only; never connects, selects, searches, lists, or reads mail.")
    imap_mailbox_adapter_audit.add_argument("--format", choices=["text", "json"], default="json", help="Output format.")
    imap_mailbox_adapter_audit.set_defaults(func=command_imap_mailbox_adapter_audit_plan)

    imap_mailbox_adapter_audit_write = subcommands.add_parser(
        "imap-mailbox-adapter-audit-write",
        aliases=["mailbox-adapter-audit-write"],
        help="Preview or approve writing a non-secret IMAP adapter audit receipt without connecting or reading mail.",
    )
    imap_mailbox_adapter_audit_write.add_argument("archive_root", help="Archive root to inspect.")
    imap_mailbox_adapter_audit_write.add_argument(
        "--adapter-id",
        required=True,
        help="Safe local adapter id, e.g. local-imap. Do not pass paths, URLs, emails, or secrets.",
    )
    imap_mailbox_adapter_audit_write.add_argument("--source-id", required=True, help="Stable source id, e.g. imap:gmail-personal.")
    imap_mailbox_adapter_audit_write.add_argument(
        "--provider",
        choices=sorted(archive_services.IMAP_MAILBOX_ALLOWED_PROVIDERS),
        default="generic_imap",
        help="Provider preset. generic_imap requires --imap-host.",
    )
    imap_mailbox_adapter_audit_write.add_argument("--imap-host", help="Safe IMAP host label. Required for generic_imap.")
    imap_mailbox_adapter_audit_write.add_argument("--imap-port", type=int, default=993, help="IMAP SSL port. Defaults to 993.")
    imap_mailbox_adapter_audit_write.add_argument(
        "--account-ref",
        required=True,
        help="Safe account reference, e.g. imap:account:personal-mail. Do not pass an email address.",
    )
    imap_mailbox_adapter_audit_write.add_argument(
        "--username-ref",
        required=True,
        help="env/keyring/secret/wallet reference for the username. Do not pass the username value.",
    )
    imap_mailbox_adapter_audit_write.add_argument(
        "--auth-mode",
        choices=sorted(archive_services.IMAP_MAILBOX_ALLOWED_AUTH_MODES),
        default="app_password_ref",
        help="Credential reference kind.",
    )
    imap_mailbox_adapter_audit_write.add_argument(
        "--app-password-ref",
        help="env/keyring/secret/wallet reference for an app password. Do not pass the password value.",
    )
    imap_mailbox_adapter_audit_write.add_argument(
        "--oauth-token-ref",
        help="env/keyring/secret/wallet reference for an OAuth token. Do not pass the token value.",
    )
    imap_mailbox_adapter_audit_write.add_argument(
        "--mailbox-ref",
        default="imap:mailbox:inbox",
        help="Safe mailbox reference. Do not pass private mailbox names.",
    )
    imap_mailbox_adapter_audit_write.add_argument(
        "--operation",
        choices=sorted(archive_services.IMAP_MAILBOX_OPERATION_REQUEST_OPERATIONS),
        default="header_metadata_scan",
        help="Future IMAP mailbox operation to audit.",
    )
    imap_mailbox_adapter_audit_write.add_argument(
        "--selection-rule",
        choices=sorted(archive_services.IMAP_MAILBOX_SELECTION_RULES),
        default="newest_first",
        help="Future non-secret mailbox selection rule.",
    )
    imap_mailbox_adapter_audit_write.add_argument(
        "--selector-id",
        default="mail-selection:recent-inbox",
        help="Safe non-secret selector label. Do not pass subjects, senders, emails, mailbox names, URLs, or paths.",
    )
    imap_mailbox_adapter_audit_write.add_argument(
        "--max-messages",
        type=int,
        default=archive_services.IMAP_MAILBOX_OPERATION_MAX_MESSAGES_DEFAULT,
        help="Future message candidate limit to request. Must be between 1 and 2000.",
    )
    imap_mailbox_adapter_audit_write.add_argument(
        "--since-days",
        type=int,
        help="Optional future recency window. Must be between 1 and 3650 days.",
    )
    imap_mailbox_adapter_audit_write.add_argument(
        "--credential-id",
        default="cred:mail-source-access",
        help="Safe credential label for the future mail credential.",
    )
    imap_mailbox_adapter_audit_write.add_argument("--credential-ref", help="Optional env/keyring/secret/wallet ref; exact value is not echoed.")
    imap_mailbox_adapter_audit_write.add_argument(
        "--credential-kind",
        choices=sorted(archive_services.CREDENTIAL_REF_ALLOWED_KINDS),
        help="Credential kind. Defaults from IMAP auth mode.",
    )
    imap_mailbox_adapter_audit_write.add_argument(
        "--credential-provider",
        choices=sorted(archive_services.CREDENTIAL_REF_ALLOWED_PROVIDERS),
        help="Credential provider label. Defaults from IMAP provider.",
    )
    imap_mailbox_adapter_audit_write.add_argument(
        "--store-kind",
        choices=sorted(archive_services.CREDENTIAL_ACCESS_BROKER_STORE_KINDS),
        default="password_manager",
        help="Credential store class for the future mail credential retrieval.",
    )
    imap_mailbox_adapter_audit_write.add_argument(
        "--adapter-kind",
        choices=sorted(archive_services.CREDENTIAL_ADAPTER_KINDS),
        help="Future credential adapter kind. Defaults from store kind and platform.",
    )
    imap_mailbox_adapter_audit_write.add_argument(
        "--approval-decision",
        choices=sorted(archive_services.CREDENTIAL_ACCESS_APPROVAL_DECISIONS),
        default="needs_review",
        help="Human decision state to evaluate.",
    )
    imap_mailbox_adapter_audit_write.add_argument(
        "--approval-receipt",
        help="Archive-relative approval receipt path to verify. The path is not echoed in output.",
    )
    imap_mailbox_adapter_audit_write.add_argument(
        "--result-status",
        choices=sorted(archive_services.IMAP_MAILBOX_ADAPTER_AUDIT_RESULT_STATUSES),
        default="not_run",
        help="Non-secret future adapter outcome status to record.",
    )
    imap_mailbox_adapter_audit_write.add_argument("--consumer", default="wom:adapter:imap-mailbox", help="Safe label for the future adapter.")
    imap_mailbox_adapter_audit_write.add_argument("--reviewed-by", help="Safe non-secret reviewer label. Required with --approve.")
    imap_mailbox_adapter_audit_write.add_argument(
        "--platform",
        choices=sorted(archive_services.CREDENTIAL_STORE_RECOMMENDATION_PLATFORMS),
        default="windows",
        help="Local platform for default credential adapter selection.",
    )
    imap_mailbox_adapter_audit_write.add_argument("--dry-run", action="store_true", help="Preview the audit receipt without writing files.")
    imap_mailbox_adapter_audit_write.add_argument("--approve", action="store_true", help="Write the non-secret audit receipt after local human review.")
    imap_mailbox_adapter_audit_write.add_argument("--format", choices=["text", "json"], default="json", help="Output format.")
    imap_mailbox_adapter_audit_write.set_defaults(func=command_imap_mailbox_adapter_audit_write)

    imap_mailbox_adapter_preflight = subcommands.add_parser(
        "imap-mailbox-adapter-preflight-plan",
        aliases=["imap-mailbox-adapter-execution-preflight", "mailbox-adapter-preflight"],
        help="Run a read-only preflight before any future IMAP adapter execution.",
    )
    imap_mailbox_adapter_preflight.add_argument("archive_root", help="Archive root to inspect.")
    imap_mailbox_adapter_preflight.add_argument(
        "--adapter-id",
        required=True,
        help="Safe local adapter id, e.g. local-imap. Do not pass paths, URLs, emails, or secrets.",
    )
    imap_mailbox_adapter_preflight.add_argument("--source-id", required=True, help="Stable source id, e.g. imap:gmail-personal.")
    imap_mailbox_adapter_preflight.add_argument(
        "--provider",
        choices=sorted(archive_services.IMAP_MAILBOX_ALLOWED_PROVIDERS),
        default="generic_imap",
        help="Provider preset. generic_imap requires --imap-host.",
    )
    imap_mailbox_adapter_preflight.add_argument("--imap-host", help="Safe IMAP host label. Required for generic_imap.")
    imap_mailbox_adapter_preflight.add_argument("--imap-port", type=int, default=993, help="IMAP SSL port. Defaults to 993.")
    imap_mailbox_adapter_preflight.add_argument(
        "--account-ref",
        required=True,
        help="Safe account reference, e.g. imap:account:personal-mail. Do not pass an email address.",
    )
    imap_mailbox_adapter_preflight.add_argument(
        "--username-ref",
        required=True,
        help="env/keyring/secret/wallet reference for the username. Do not pass the username value.",
    )
    imap_mailbox_adapter_preflight.add_argument(
        "--auth-mode",
        choices=sorted(archive_services.IMAP_MAILBOX_ALLOWED_AUTH_MODES),
        default="app_password_ref",
        help="Credential reference kind.",
    )
    imap_mailbox_adapter_preflight.add_argument(
        "--app-password-ref",
        help="env/keyring/secret/wallet reference for an app password. Do not pass the password value.",
    )
    imap_mailbox_adapter_preflight.add_argument(
        "--oauth-token-ref",
        help="env/keyring/secret/wallet reference for an OAuth token. Do not pass the token value.",
    )
    imap_mailbox_adapter_preflight.add_argument(
        "--mailbox-ref",
        default="imap:mailbox:inbox",
        help="Safe mailbox reference. Do not pass private mailbox names.",
    )
    imap_mailbox_adapter_preflight.add_argument(
        "--operation",
        choices=sorted(archive_services.IMAP_MAILBOX_OPERATION_REQUEST_OPERATIONS),
        default="header_metadata_scan",
        help="Future IMAP mailbox operation to preflight.",
    )
    imap_mailbox_adapter_preflight.add_argument(
        "--selection-rule",
        choices=sorted(archive_services.IMAP_MAILBOX_SELECTION_RULES),
        default="newest_first",
        help="Future non-secret mailbox selection rule.",
    )
    imap_mailbox_adapter_preflight.add_argument(
        "--selector-id",
        default="mail-selection:recent-inbox",
        help="Safe non-secret selector label. Do not pass subjects, senders, emails, mailbox names, URLs, or paths.",
    )
    imap_mailbox_adapter_preflight.add_argument(
        "--max-messages",
        type=int,
        default=archive_services.IMAP_MAILBOX_OPERATION_MAX_MESSAGES_DEFAULT,
        help="Future message candidate limit to request. Must be between 1 and 2000.",
    )
    imap_mailbox_adapter_preflight.add_argument(
        "--since-days",
        type=int,
        help="Optional future recency window. Must be between 1 and 3650 days.",
    )
    imap_mailbox_adapter_preflight.add_argument(
        "--credential-id",
        default="cred:mail-source-access",
        help="Safe credential label for the future mail credential.",
    )
    imap_mailbox_adapter_preflight.add_argument("--credential-ref", help="Optional env/keyring/secret/wallet ref; exact value is not echoed.")
    imap_mailbox_adapter_preflight.add_argument(
        "--credential-kind",
        choices=sorted(archive_services.CREDENTIAL_REF_ALLOWED_KINDS),
        help="Credential kind. Defaults from IMAP auth mode.",
    )
    imap_mailbox_adapter_preflight.add_argument(
        "--credential-provider",
        choices=sorted(archive_services.CREDENTIAL_REF_ALLOWED_PROVIDERS),
        help="Credential provider label. Defaults from IMAP provider.",
    )
    imap_mailbox_adapter_preflight.add_argument(
        "--store-kind",
        choices=sorted(archive_services.CREDENTIAL_ACCESS_BROKER_STORE_KINDS),
        default="password_manager",
        help="Credential store class for the future mail credential retrieval.",
    )
    imap_mailbox_adapter_preflight.add_argument(
        "--adapter-kind",
        choices=sorted(archive_services.CREDENTIAL_ADAPTER_KINDS),
        help="Future credential adapter kind. Defaults from store kind and platform.",
    )
    imap_mailbox_adapter_preflight.add_argument(
        "--approval-decision",
        choices=sorted(archive_services.CREDENTIAL_ACCESS_APPROVAL_DECISIONS),
        default="needs_review",
        help="Human decision state to evaluate.",
    )
    imap_mailbox_adapter_preflight.add_argument(
        "--approval-receipt",
        help="Archive-relative approval receipt path to verify. The path is not echoed in output.",
    )
    imap_mailbox_adapter_preflight.add_argument("--consumer", default="wom:adapter:imap-mailbox", help="Safe label for the future adapter.")
    imap_mailbox_adapter_preflight.add_argument("--reviewed-by", default="human:pending-review", help="Safe non-secret reviewer label.")
    imap_mailbox_adapter_preflight.add_argument(
        "--platform",
        choices=sorted(archive_services.CREDENTIAL_STORE_RECOMMENDATION_PLATFORMS),
        default="windows",
        help="Local platform for default credential adapter selection.",
    )
    imap_mailbox_adapter_preflight.add_argument("--dry-run", action="store_true", help="Required. Preflight only; never connects, selects, searches, lists, reads mail, or writes files.")
    imap_mailbox_adapter_preflight.add_argument("--format", choices=["text", "json"], default="json", help="Output format.")
    imap_mailbox_adapter_preflight.set_defaults(func=command_imap_mailbox_adapter_preflight_plan)

    imap_mailbox_adapter_execution_contract = subcommands.add_parser(
        "imap-mailbox-adapter-execution-contract",
        aliases=["imap-mailbox-adapter-execution-plan", "mailbox-adapter-execution-contract"],
        help="Print the read-only future execution contract before any live IMAP adapter exists.",
    )
    imap_mailbox_adapter_execution_contract.add_argument("archive_root", help="Archive root to inspect.")
    imap_mailbox_adapter_execution_contract.add_argument(
        "--adapter-id",
        required=True,
        help="Safe local adapter id, e.g. local-imap. Do not pass paths, URLs, emails, or secrets.",
    )
    imap_mailbox_adapter_execution_contract.add_argument("--source-id", required=True, help="Stable source id, e.g. imap:gmail-personal.")
    imap_mailbox_adapter_execution_contract.add_argument(
        "--provider",
        choices=sorted(archive_services.IMAP_MAILBOX_ALLOWED_PROVIDERS),
        default="generic_imap",
        help="Provider preset. generic_imap requires --imap-host.",
    )
    imap_mailbox_adapter_execution_contract.add_argument("--imap-host", help="Safe IMAP host label. Required for generic_imap.")
    imap_mailbox_adapter_execution_contract.add_argument("--imap-port", type=int, default=993, help="IMAP SSL port. Defaults to 993.")
    imap_mailbox_adapter_execution_contract.add_argument(
        "--account-ref",
        required=True,
        help="Safe account reference, e.g. imap:account:personal-mail. Do not pass an email address.",
    )
    imap_mailbox_adapter_execution_contract.add_argument(
        "--username-ref",
        required=True,
        help="env/keyring/secret/wallet reference for the username. Do not pass the username value.",
    )
    imap_mailbox_adapter_execution_contract.add_argument(
        "--auth-mode",
        choices=sorted(archive_services.IMAP_MAILBOX_ALLOWED_AUTH_MODES),
        default="app_password_ref",
        help="Credential reference kind.",
    )
    imap_mailbox_adapter_execution_contract.add_argument(
        "--app-password-ref",
        help="env/keyring/secret/wallet reference for an app password. Do not pass the password value.",
    )
    imap_mailbox_adapter_execution_contract.add_argument(
        "--oauth-token-ref",
        help="env/keyring/secret/wallet reference for an OAuth token. Do not pass the token value.",
    )
    imap_mailbox_adapter_execution_contract.add_argument(
        "--mailbox-ref",
        default="imap:mailbox:inbox",
        help="Safe mailbox reference. Do not pass private mailbox names.",
    )
    imap_mailbox_adapter_execution_contract.add_argument(
        "--operation",
        choices=sorted(archive_services.IMAP_MAILBOX_OPERATION_REQUEST_OPERATIONS),
        default="header_metadata_scan",
        help="Future IMAP mailbox operation to contract.",
    )
    imap_mailbox_adapter_execution_contract.add_argument(
        "--selection-rule",
        choices=sorted(archive_services.IMAP_MAILBOX_SELECTION_RULES),
        default="newest_first",
        help="Future non-secret mailbox selection rule.",
    )
    imap_mailbox_adapter_execution_contract.add_argument(
        "--selector-id",
        default="mail-selection:recent-inbox",
        help="Safe non-secret selector label. Do not pass subjects, senders, emails, mailbox names, URLs, or paths.",
    )
    imap_mailbox_adapter_execution_contract.add_argument(
        "--max-messages",
        type=int,
        default=archive_services.IMAP_MAILBOX_OPERATION_MAX_MESSAGES_DEFAULT,
        help="Future message candidate limit to request. Must be between 1 and 2000.",
    )
    imap_mailbox_adapter_execution_contract.add_argument(
        "--since-days",
        type=int,
        help="Optional future recency window. Must be between 1 and 3650 days.",
    )
    imap_mailbox_adapter_execution_contract.add_argument(
        "--credential-id",
        default="cred:mail-source-access",
        help="Safe credential label for the future mail credential.",
    )
    imap_mailbox_adapter_execution_contract.add_argument("--credential-ref", help="Optional env/keyring/secret/wallet ref; exact value is not echoed.")
    imap_mailbox_adapter_execution_contract.add_argument(
        "--credential-kind",
        choices=sorted(archive_services.CREDENTIAL_REF_ALLOWED_KINDS),
        help="Credential kind. Defaults from IMAP auth mode.",
    )
    imap_mailbox_adapter_execution_contract.add_argument(
        "--credential-provider",
        choices=sorted(archive_services.CREDENTIAL_REF_ALLOWED_PROVIDERS),
        help="Credential provider label. Defaults from IMAP provider.",
    )
    imap_mailbox_adapter_execution_contract.add_argument(
        "--store-kind",
        choices=sorted(archive_services.CREDENTIAL_ACCESS_BROKER_STORE_KINDS),
        default="password_manager",
        help="Credential store class for the future mail credential retrieval.",
    )
    imap_mailbox_adapter_execution_contract.add_argument(
        "--adapter-kind",
        choices=sorted(archive_services.CREDENTIAL_ADAPTER_KINDS),
        help="Future credential adapter kind. Defaults from store kind and platform.",
    )
    imap_mailbox_adapter_execution_contract.add_argument(
        "--approval-decision",
        choices=sorted(archive_services.CREDENTIAL_ACCESS_APPROVAL_DECISIONS),
        default="needs_review",
        help="Human decision state to evaluate.",
    )
    imap_mailbox_adapter_execution_contract.add_argument(
        "--approval-receipt",
        help="Archive-relative approval receipt path to verify. The path is not echoed in output.",
    )
    imap_mailbox_adapter_execution_contract.add_argument("--consumer", default="wom:adapter:imap-mailbox", help="Safe label for the future adapter.")
    imap_mailbox_adapter_execution_contract.add_argument("--reviewed-by", default="human:pending-review", help="Safe non-secret reviewer label.")
    imap_mailbox_adapter_execution_contract.add_argument(
        "--platform",
        choices=sorted(archive_services.CREDENTIAL_STORE_RECOMMENDATION_PLATFORMS),
        default="windows",
        help="Local platform for default credential adapter selection.",
    )
    imap_mailbox_adapter_execution_contract.add_argument(
        "--execution-mode",
        choices=sorted(archive_services.IMAP_MAILBOX_ADAPTER_EXECUTION_MODES),
        default="local_cli_dry_run_contract",
        help="Future execution mode to describe. The command still does not execute it.",
    )
    imap_mailbox_adapter_execution_contract.add_argument("--dry-run", action="store_true", help="Required. Contract only; never connects, selects, searches, lists, reads mail, or writes files.")
    imap_mailbox_adapter_execution_contract.add_argument("--format", choices=["text", "json"], default="json", help="Output format.")
    imap_mailbox_adapter_execution_contract.set_defaults(func=command_imap_mailbox_adapter_execution_contract)

    imap_mailbox_header_metadata_scan = subcommands.add_parser(
        "imap-mailbox-header-metadata-scan",
        aliases=["imap-header-metadata-scan", "mailbox-header-metadata-scan"],
        help="Run the first approval-gated local IMAP header metadata scan.",
    )
    imap_mailbox_header_metadata_scan.add_argument("archive_root", help="Archive root to inspect.")
    imap_mailbox_header_metadata_scan.add_argument(
        "--adapter-id",
        required=True,
        help="Safe local adapter id, e.g. local-imap. Do not pass paths, URLs, emails, or secrets.",
    )
    imap_mailbox_header_metadata_scan.add_argument("--source-id", required=True, help="Stable source id, e.g. imap:gmail-personal.")
    imap_mailbox_header_metadata_scan.add_argument(
        "--provider",
        choices=sorted(archive_services.IMAP_MAILBOX_ALLOWED_PROVIDERS),
        default="generic_imap",
        help="Provider preset. generic_imap requires --imap-host.",
    )
    imap_mailbox_header_metadata_scan.add_argument("--imap-host", help="Safe IMAP host label. Required for generic_imap.")
    imap_mailbox_header_metadata_scan.add_argument("--imap-port", type=int, default=993, help="IMAP SSL port. Defaults to 993.")
    imap_mailbox_header_metadata_scan.add_argument(
        "--account-ref",
        required=True,
        help="Safe account reference, e.g. imap:account:personal-mail. Do not pass an email address.",
    )
    imap_mailbox_header_metadata_scan.add_argument(
        "--username-ref",
        required=True,
        help="env: reference for the username. Do not pass the username value.",
    )
    imap_mailbox_header_metadata_scan.add_argument(
        "--auth-mode",
        choices=["app_password_ref"],
        default="app_password_ref",
        help="Credential reference kind. v0.3.62 supports app_password_ref only.",
    )
    imap_mailbox_header_metadata_scan.add_argument(
        "--app-password-ref",
        required=True,
        help="env: reference for an app password. Do not pass the password value.",
    )
    imap_mailbox_header_metadata_scan.add_argument(
        "--oauth-token-ref",
        help="Reserved for future OAuth support; v0.3.62 blocks this value.",
    )
    imap_mailbox_header_metadata_scan.add_argument(
        "--mailbox-ref",
        default="imap:mailbox:inbox",
        help="Safe mailbox reference. v0.3.62 supports only imap:mailbox:inbox.",
    )
    imap_mailbox_header_metadata_scan.add_argument(
        "--operation",
        choices=["header_metadata_scan"],
        default="header_metadata_scan",
        help="Only header_metadata_scan is executable in this release.",
    )
    imap_mailbox_header_metadata_scan.add_argument(
        "--selection-rule",
        choices=sorted(archive_services.IMAP_MAILBOX_SELECTION_RULES),
        default="newest_first",
        help="Non-secret mailbox selection rule.",
    )
    imap_mailbox_header_metadata_scan.add_argument(
        "--selector-id",
        default="mail-selection:recent-inbox",
        help="Safe non-secret selector label. Do not pass subjects, senders, emails, mailbox names, URLs, or paths.",
    )
    imap_mailbox_header_metadata_scan.add_argument(
        "--max-messages",
        type=int,
        default=archive_services.IMAP_MAILBOX_OPERATION_MAX_MESSAGES_DEFAULT,
        help="Message candidate limit to request. Must be between 1 and 2000.",
    )
    imap_mailbox_header_metadata_scan.add_argument(
        "--since-days",
        type=int,
        help="Optional future recency window. Must be between 1 and 3650 days.",
    )
    imap_mailbox_header_metadata_scan.add_argument(
        "--credential-id",
        default="cred:mail-source-access",
        help="Safe credential label for the mail credential.",
    )
    imap_mailbox_header_metadata_scan.add_argument("--credential-ref", help="Optional env: ref; exact value is not echoed.")
    imap_mailbox_header_metadata_scan.add_argument(
        "--credential-kind",
        choices=sorted(archive_services.CREDENTIAL_REF_ALLOWED_KINDS),
        default="mail_app_password",
        help="Credential kind. v0.3.62 supports mail_app_password for app-password auth.",
    )
    imap_mailbox_header_metadata_scan.add_argument(
        "--credential-provider",
        choices=sorted(archive_services.CREDENTIAL_REF_ALLOWED_PROVIDERS),
        help="Credential provider label. Defaults from IMAP provider.",
    )
    imap_mailbox_header_metadata_scan.add_argument(
        "--store-kind",
        choices=sorted(archive_services.CREDENTIAL_ACCESS_BROKER_STORE_KINDS),
        default="environment",
        help="Credential store class. v0.3.62 live scan supports environment refs only.",
    )
    imap_mailbox_header_metadata_scan.add_argument(
        "--adapter-kind",
        choices=sorted(archive_services.CREDENTIAL_ADAPTER_KINDS),
        default="environment_injection",
        help="Credential adapter kind. v0.3.62 live scan supports environment_injection only.",
    )
    imap_mailbox_header_metadata_scan.add_argument(
        "--approval-decision",
        choices=sorted(archive_services.CREDENTIAL_ACCESS_APPROVAL_DECISIONS),
        default="needs_review",
        help="Human decision state to evaluate.",
    )
    imap_mailbox_header_metadata_scan.add_argument(
        "--approval-receipt",
        help="Archive-relative approval receipt path to verify. The path is not echoed in output.",
    )
    imap_mailbox_header_metadata_scan.add_argument("--consumer", default="wom:adapter:imap-mailbox", help="Safe label for the adapter.")
    imap_mailbox_header_metadata_scan.add_argument("--reviewed-by", default="human:pending-review", help="Safe non-secret reviewer label.")
    imap_mailbox_header_metadata_scan.add_argument(
        "--platform",
        choices=sorted(archive_services.CREDENTIAL_STORE_RECOMMENDATION_PLATFORMS),
        default="windows",
        help="Local platform for default credential adapter selection.",
    )
    imap_mailbox_header_metadata_scan.add_argument(
        "--timeout-seconds",
        type=int,
        default=30,
        help="IMAP connection timeout for approved mode. Must be between 1 and 120.",
    )
    imap_mailbox_header_metadata_scan.add_argument("--dry-run", action="store_true", help="Preview the scan without reading environment variables or opening IMAP.")
    imap_mailbox_header_metadata_scan.add_argument("--approve", action="store_true", help="Run the local header metadata scan and write a non-secret receipt.")
    imap_mailbox_header_metadata_scan.add_argument("--format", choices=["text", "json"], default="json", help="Output format.")
    imap_mailbox_header_metadata_scan.set_defaults(func=command_imap_mailbox_header_metadata_scan)

    imap_mailbox_header_scan_receipt_audit = subcommands.add_parser(
        "imap-mailbox-header-scan-receipt-audit",
        aliases=["imap-header-scan-receipt-audit", "mailbox-header-scan-audit"],
        help="Audit a non-secret IMAP header metadata scan execution receipt.",
    )
    imap_mailbox_header_scan_receipt_audit.add_argument("archive_root", help="Archive root to inspect.")
    imap_mailbox_header_scan_receipt_audit.add_argument(
        "--execution-receipt",
        required=True,
        help="Archive-relative receipts/imap/adapter-executions/*.json path. The exact path is not echoed in JSON output.",
    )
    imap_mailbox_header_scan_receipt_audit.add_argument(
        "--reviewed-by",
        default="human:pending-review",
        help="Safe non-secret reviewer label. Required to be non-empty with --approve.",
    )
    imap_mailbox_header_scan_receipt_audit.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate the receipt and preview the audit receipt without writing files.",
    )
    imap_mailbox_header_scan_receipt_audit.add_argument(
        "--approve",
        action="store_true",
        help="Write a non-secret audit receipt after validation passes.",
    )
    imap_mailbox_header_scan_receipt_audit.add_argument("--format", choices=["text", "json"], default="json", help="Output format.")
    imap_mailbox_header_scan_receipt_audit.set_defaults(func=command_imap_mailbox_header_scan_receipt_audit)

    imap_mailbox_material_selection_plan = subcommands.add_parser(
        "imap-mailbox-material-selection-plan",
        aliases=["imap-material-selection-plan", "mailbox-material-selection-plan"],
        help="Plan a human review queue from an IMAP header scan receipt without reading message material.",
    )
    imap_mailbox_material_selection_plan.add_argument("archive_root", help="Archive root to inspect.")
    imap_mailbox_material_selection_plan.add_argument(
        "--execution-receipt",
        required=True,
        help="Archive-relative receipts/imap/adapter-executions/*.json path. The exact path is not echoed in JSON output.",
    )
    imap_mailbox_material_selection_plan.add_argument(
        "--selection-mode",
        choices=sorted(archive_services.IMAP_MAILBOX_MATERIAL_SELECTION_MODES),
        default="human_review_queue",
        help="Future message material review lane to plan. The command still reads no bodies or attachments.",
    )
    imap_mailbox_material_selection_plan.add_argument(
        "--dry-run",
        action="store_true",
        help="Required. Plan only; never connects to IMAP, reads secrets, reads bodies, reads attachments, or writes files.",
    )
    imap_mailbox_material_selection_plan.add_argument("--format", choices=["text", "json"], default="json", help="Output format.")
    imap_mailbox_material_selection_plan.set_defaults(func=command_imap_mailbox_material_selection_plan)

    imap_mailbox_material_selection_record = subcommands.add_parser(
        "imap-mailbox-material-selection-record",
        aliases=["imap-material-selection-record", "mailbox-material-selection-record"],
        help="Preview or approve a non-secret IMAP material selection record by candidate index.",
    )
    imap_mailbox_material_selection_record.add_argument("archive_root", help="Archive root to inspect.")
    imap_mailbox_material_selection_record.add_argument(
        "--execution-receipt",
        required=True,
        help="Archive-relative receipts/imap/adapter-executions/*.json path. The exact path is not echoed in JSON output.",
    )
    imap_mailbox_material_selection_record.add_argument(
        "--selection-mode",
        choices=sorted(archive_services.IMAP_MAILBOX_MATERIAL_SELECTION_MODES),
        default="human_review_queue",
        help="Future message material review lane to record. The command still reads no bodies or attachments.",
    )
    imap_mailbox_material_selection_record.add_argument(
        "--selected-index",
        type=int,
        action="append",
        default=[],
        help="One-based candidate position from the execution receipt. Repeat for multiple candidates.",
    )
    imap_mailbox_material_selection_record.add_argument(
        "--reviewed-by",
        default="human:pending-review",
        help="Safe non-secret reviewer label. Required to be non-empty with --approve.",
    )
    imap_mailbox_material_selection_record.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and preview the material selection receipt without writing files.",
    )
    imap_mailbox_material_selection_record.add_argument(
        "--approve",
        action="store_true",
        help="Write a non-secret material selection receipt after validation passes.",
    )
    imap_mailbox_material_selection_record.add_argument("--format", choices=["text", "json"], default="json", help="Output format.")
    imap_mailbox_material_selection_record.set_defaults(func=command_imap_mailbox_material_selection_record)

    imap_mailbox_material_capture_request_plan = subcommands.add_parser(
        "imap-mailbox-material-capture-request-plan",
        aliases=["imap-material-capture-request-plan", "mailbox-material-capture-request-plan"],
        help="Plan a future message-material capture request from a selection receipt without reading mail.",
    )
    imap_mailbox_material_capture_request_plan.add_argument("archive_root", help="Archive root to inspect.")
    imap_mailbox_material_capture_request_plan.add_argument(
        "--material-selection-receipt",
        required=True,
        help="Archive-relative receipts/imap/material-selections/*.json path. The exact path is not echoed in JSON output.",
    )
    imap_mailbox_material_capture_request_plan.add_argument(
        "--capture-action",
        choices=sorted(archive_services.IMAP_MAILBOX_MATERIAL_CAPTURE_ACTIONS),
        default="message_body_capture",
        help="Future capture action to request. The command still reads no bodies or attachments.",
    )
    imap_mailbox_material_capture_request_plan.add_argument(
        "--dry-run",
        action="store_true",
        help="Required. Plan only; never connects to IMAP, reads secrets, reads bodies, reads attachments, or writes files.",
    )
    imap_mailbox_material_capture_request_plan.add_argument("--format", choices=["text", "json"], default="json", help="Output format.")
    imap_mailbox_material_capture_request_plan.set_defaults(func=command_imap_mailbox_material_capture_request_plan)

    imap_mailbox_material_capture_execution_contract = subcommands.add_parser(
        "imap-mailbox-material-capture-execution-contract",
        aliases=["imap-material-capture-execution-contract", "mailbox-material-capture-execution-contract"],
        help="Print the future IMAP material capture execution contract without reading mail.",
    )
    imap_mailbox_material_capture_execution_contract.add_argument("archive_root", help="Archive root to inspect.")
    imap_mailbox_material_capture_execution_contract.add_argument(
        "--material-selection-receipt",
        required=True,
        help="Archive-relative receipts/imap/material-selections/*.json path. The exact path is not echoed in JSON output.",
    )
    imap_mailbox_material_capture_execution_contract.add_argument(
        "--capture-action",
        choices=sorted(archive_services.IMAP_MAILBOX_MATERIAL_CAPTURE_ACTIONS),
        default="message_body_capture",
        help="Future capture action to describe. The command still reads no bodies or attachments.",
    )
    imap_mailbox_material_capture_execution_contract.add_argument(
        "--dry-run",
        action="store_true",
        help="Required. Contract only; never connects to IMAP, reads secrets, reads bodies, reads attachments, or writes files.",
    )
    imap_mailbox_material_capture_execution_contract.add_argument("--format", choices=["text", "json"], default="json", help="Output format.")
    imap_mailbox_material_capture_execution_contract.set_defaults(func=command_imap_mailbox_material_capture_execution_contract)

    imap_mailbox_material_capture_approval_plan = subcommands.add_parser(
        "imap-mailbox-material-capture-approval-plan",
        aliases=["imap-material-capture-approval-plan", "mailbox-material-capture-approval-plan", "imap-mailbox-material-capture-approval"],
        help="Preview or approve a non-secret IMAP material capture approval receipt.",
    )
    imap_mailbox_material_capture_approval_plan.add_argument("archive_root", help="Archive root to inspect.")
    imap_mailbox_material_capture_approval_plan.add_argument(
        "--material-selection-receipt",
        required=True,
        help="Archive-relative receipts/imap/material-selections/*.json path. The exact path is not echoed in JSON output.",
    )
    imap_mailbox_material_capture_approval_plan.add_argument(
        "--capture-action",
        choices=sorted(archive_services.IMAP_MAILBOX_MATERIAL_CAPTURE_ACTIONS),
        default="message_body_capture",
        help="Future capture action to approve or deny. The command still reads no bodies or attachments.",
    )
    imap_mailbox_material_capture_approval_plan.add_argument(
        "--decision",
        choices=sorted(archive_services.IMAP_MAILBOX_MATERIAL_CAPTURE_APPROVAL_DECISIONS),
        default="needs_review",
        help="Human decision to preview or record for the future material capture action.",
    )
    imap_mailbox_material_capture_approval_plan.add_argument(
        "--reviewed-by",
        default="human:pending-review",
        help="Safe non-secret reviewer label. Required to be non-empty with --approve.",
    )
    imap_mailbox_material_capture_approval_plan.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and preview the material capture approval receipt without writing files.",
    )
    imap_mailbox_material_capture_approval_plan.add_argument(
        "--approve",
        action="store_true",
        help="Write a non-secret material capture approval receipt after validation passes.",
    )
    imap_mailbox_material_capture_approval_plan.add_argument("--format", choices=["text", "json"], default="json", help="Output format.")
    imap_mailbox_material_capture_approval_plan.set_defaults(func=command_imap_mailbox_material_capture_approval_plan)

    imap_mailbox_material_capture_approval_audit = subcommands.add_parser(
        "imap-mailbox-material-capture-approval-audit",
        aliases=["imap-material-capture-approval-audit", "mailbox-material-capture-approval-audit"],
        help="Audit one IMAP material capture approval receipt without reading mail.",
    )
    imap_mailbox_material_capture_approval_audit.add_argument("archive_root", help="Archive root to inspect.")
    imap_mailbox_material_capture_approval_audit.add_argument(
        "--material-selection-receipt",
        required=True,
        help="Archive-relative receipts/imap/material-selections/*.json path. The exact path is not echoed in JSON output.",
    )
    imap_mailbox_material_capture_approval_audit.add_argument(
        "--approval-receipt",
        required=True,
        help="Archive-relative receipts/imap/material-capture-approvals/*.json path. The exact path is not echoed in JSON output.",
    )
    imap_mailbox_material_capture_approval_audit.add_argument(
        "--capture-action",
        choices=sorted(archive_services.IMAP_MAILBOX_MATERIAL_CAPTURE_ACTIONS),
        default="message_body_capture",
        help="Future capture action expected by the approval receipt. The command still reads no bodies or attachments.",
    )
    imap_mailbox_material_capture_approval_audit.add_argument(
        "--expected-decision",
        choices=sorted(archive_services.IMAP_MAILBOX_MATERIAL_CAPTURE_APPROVAL_DECISIONS),
        default="approve_once",
        help="Human decision expected in the approval receipt.",
    )
    imap_mailbox_material_capture_approval_audit.add_argument(
        "--dry-run",
        action="store_true",
        help="Required. Audit only; never connects to IMAP, reads secrets, reads bodies, reads attachments, or writes files.",
    )
    imap_mailbox_material_capture_approval_audit.add_argument("--format", choices=["text", "json"], default="json", help="Output format.")
    imap_mailbox_material_capture_approval_audit.set_defaults(func=command_imap_mailbox_material_capture_approval_audit)

    sources = subcommands.add_parser("sources", help="Inspect source bindings and source map status.")
    sources.add_argument("archive_root", help="Archive root to inspect.")
    sources.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    sources.set_defaults(func=command_sources)

    scan_source = subcommands.add_parser("scan-source", help="Metadata-only scan of a registered source into a source map.")
    scan_source.add_argument("archive_root", help="Archive root to inspect.")
    scan_source.add_argument("--source", required=True, help="source_id from source-bindings.yml.")
    scan_source.add_argument(
        "--source-root",
        help="Real local/export folder or manifest path for this run. It is used at runtime and not written to source maps.",
    )
    scan_source.add_argument("--dry-run", action="store_true", help="Preview source scan without writing archive files.")
    scan_source.add_argument("--approve", action="store_true", help="Write source map and receipt after dry-run gates pass.")
    scan_source.add_argument("--reviewed-by", help="Reviewer id required for approved source scan.")
    scan_source.add_argument("--limit", type=int, default=2000, help="Maximum metadata items to map.")
    scan_source.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    scan_source.set_defaults(func=command_scan_source)

    add_source = subcommands.add_parser("add-source", help="Register a source without hand-editing source-bindings.yml.")
    add_source.add_argument("archive_root", help="Archive root to update.")
    add_source.add_argument("--source-id", required=True, help="Stable source id, e.g. local:documents or ssd:archive-drive.")
    add_source.add_argument(
        "--type",
        dest="source_type",
        required=True,
        choices=sorted(archive_services.SOURCE_TYPES),
        help="Source type.",
    )
    add_source.add_argument("--description", help="Human-readable source description.")
    add_source.add_argument(
        "--root-ref",
        help="Safe root ref to store, e.g. ARCHIVE_SOURCE_DOCUMENTS_ROOT or archive:objects/manifests/files.jsonl.",
    )
    add_source.add_argument(
        "--local-root",
        help="Actual local path used only for ignored local profile guidance when --write-local-profile is set.",
    )
    add_source.add_argument(
        "--write-local-profile",
        action="store_true",
        help="Write the actual local root to ignored profiles/local/source-roots.local.yml.",
    )
    add_source.add_argument("--include", action="append", help="Include glob. Repeatable. Defaults to **/*.")
    add_source.add_argument("--exclude", action="append", help="Exclude glob. Repeatable.")
    add_source.add_argument("--max-items", type=int, default=2000, help="Maximum metadata items for default scans.")
    add_source.add_argument("--visibility-scope", default="private", help="Visibility scope recorded for mapped items.")
    add_source.add_argument("--source-visibility", default="private", help="Source visibility recorded for mapped items.")
    add_source.add_argument("--replace", action="store_true", help="Replace an existing source with the same source id.")
    add_source.add_argument("--dry-run", action="store_true", help="Preview source registration without writing files.")
    add_source.add_argument("--approve", action="store_true", help="Write source-bindings.yml after review.")
    add_source.add_argument("--reviewed-by", help="Reviewer id required for approved registration.")
    add_source.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    add_source.set_defaults(func=command_add_source)

    source_mounts = subcommands.add_parser("source-mounts", help="Show host-native and Docker mount guidance for registered sources.")
    source_mounts.add_argument("archive_root", help="Archive root to inspect.")
    source_mounts.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    source_mounts.set_defaults(func=command_source_mounts)

    project_intake_staging_guide = subcommands.add_parser(
        "project-intake-staging-guide",
        help="Show where to stage one project folder before a project intake session.",
    )
    project_intake_staging_guide.add_argument("archive_root", help="Archive root to inspect.")
    project_intake_staging_guide.add_argument("--project-slug", required=True, help="Lowercase ASCII project slug for the staged folder.")
    project_intake_staging_guide.add_argument("--dry-run", action="store_true", help="Required; path guidance only.")
    project_intake_staging_guide.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    project_intake_staging_guide.set_defaults(func=command_project_intake_staging_guide)

    project_intake_session_guide = subcommands.add_parser(
        "project-intake-session-guide",
        help="Show the next safe human-guided project intake step without writing files.",
    )
    project_intake_session_guide.add_argument("archive_root", help="Archive root to inspect.")
    project_intake_session_guide_source = project_intake_session_guide.add_mutually_exclusive_group(required=True)
    project_intake_session_guide_source.add_argument("--project-slug", help="Lowercase ASCII project slug for staging guidance.")
    project_intake_session_guide_source.add_argument("--staged-folder", help="One staged project folder for a new intake session.")
    project_intake_session_guide_source.add_argument("--receipt", help="Archive-relative project intake decisions receipt for a continuing session.")
    project_intake_session_guide.add_argument("--session-id", help="Optional safe session id for a new decision template.")
    project_intake_session_guide.add_argument("--staged-folder-ref", help="Optional non-secret staged folder reference for a new decision template.")
    project_intake_session_guide.add_argument("--dry-run", action="store_true", help="Required; guide only.")
    project_intake_session_guide.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    project_intake_session_guide.set_defaults(func=command_project_intake_session_guide)

    project_intake_plan = subcommands.add_parser(
        "project-intake-plan",
        help="Plan one staged project folder intake session without writing files.",
    )
    project_intake_plan.add_argument("archive_root", help="Archive root to inspect.")
    project_intake_plan.add_argument("--staged-folder", required=True, help="One staged project folder to plan.")
    project_intake_plan.add_argument("--dry-run", action="store_true", help="Required; plan without writing files.")
    project_intake_plan.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    project_intake_plan.set_defaults(func=command_project_intake_plan)

    project_intake_unpack_queue = subcommands.add_parser(
        "project-intake-unpack-queue",
        help="Queue top-level staged items for human-guided unpacking without exposing entry names.",
    )
    project_intake_unpack_queue.add_argument("archive_root", help="Archive root to inspect.")
    project_intake_unpack_queue.add_argument("--staged-folder", required=True, help="One staged project folder to queue.")
    project_intake_unpack_queue.add_argument("--receipt", help="Optional archive-relative project intake decisions receipt.")
    project_intake_unpack_queue.add_argument("--max-items", type=int, default=25, help="Maximum top-level items to return, capped at 100.")
    project_intake_unpack_queue.add_argument("--dry-run", action="store_true", help="Required; queue without writing files.")
    project_intake_unpack_queue.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    project_intake_unpack_queue.set_defaults(func=command_project_intake_unpack_queue)

    project_intake_unpack_choice = subcommands.add_parser(
        "project-intake-unpack-choice",
        help="Record one human-confirmed unpack choice without exposing staged entry names.",
    )
    project_intake_unpack_choice.add_argument("archive_root", help="Archive root to update.")
    project_intake_unpack_choice.add_argument("--choice", required=True, help="Reviewed unpack-choice JSON file.")
    project_intake_unpack_choice.add_argument("--receipt", required=True, help="Archive-relative project intake decisions receipt.")
    project_intake_unpack_choice.add_argument("--staged-folder", required=True, help="One staged project folder whose queue contains item_ref.")
    project_intake_unpack_choice.add_argument("--dry-run", action="store_true", help="Preview validation without writing files.")
    project_intake_unpack_choice.add_argument("--approve", action="store_true", help="Write the reviewed unpack-choice receipt.")
    project_intake_unpack_choice.add_argument("--reviewed-by", help="Reviewer id required when --approve is used.")
    project_intake_unpack_choice.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    project_intake_unpack_choice.set_defaults(func=command_project_intake_unpack_choice)

    project_intake_decisions = subcommands.add_parser(
        "project-intake-decisions",
        help="Record reviewed project intake checklist decisions after a planner session.",
    )
    project_intake_decisions.add_argument("archive_root", help="Archive root to update.")
    project_intake_decisions.add_argument("--decisions", required=True, help="Reviewed project intake decisions JSON file.")
    project_intake_decisions.add_argument("--dry-run", action="store_true", help="Preview validation without writing files.")
    project_intake_decisions.add_argument("--approve", action="store_true", help="Write the reviewed decisions receipt.")
    project_intake_decisions.add_argument("--reviewed-by", help="Reviewer id required when --approve is used.")
    project_intake_decisions.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    project_intake_decisions.set_defaults(func=command_project_intake_decisions)

    project_intake_record_answer = subcommands.add_parser(
        "project-intake-record-answer",
        help="Append one reviewed project intake answer to a decisions receipt.",
    )
    project_intake_record_answer.add_argument("archive_root", help="Archive root to update.")
    project_intake_record_answer.add_argument("--answer", required=True, help="Reviewed single-answer JSON file.")
    project_intake_record_answer_source = project_intake_record_answer.add_mutually_exclusive_group(required=True)
    project_intake_record_answer_source.add_argument("--receipt", help="Existing project-intake decisions receipt to continue.")
    project_intake_record_answer_source.add_argument("--session-id", help="Safe session id when recording the first answer.")
    project_intake_record_answer.add_argument("--staged-folder-ref", help="Optional non-secret staged folder reference for a new session.")
    project_intake_record_answer.add_argument("--dry-run", action="store_true", help="Preview validation without writing files.")
    project_intake_record_answer.add_argument("--approve", action="store_true", help="Write the updated decisions receipt.")
    project_intake_record_answer.add_argument("--reviewed-by", help="Reviewer id required when --approve is used.")
    project_intake_record_answer.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    project_intake_record_answer.set_defaults(func=command_project_intake_record_answer)

    project_intake_status = subcommands.add_parser(
        "project-intake-status",
        help="Review a recorded project intake decisions receipt without echoing answer text.",
    )
    project_intake_status.add_argument("archive_root", help="Archive root to inspect.")
    project_intake_status.add_argument("--receipt", required=True, help="Archive-relative project intake decisions receipt.")
    project_intake_status.add_argument("--dry-run", action="store_true", help="Required; inspect without writing files.")
    project_intake_status.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    project_intake_status.set_defaults(func=command_project_intake_status)

    project_intake_next_question = subcommands.add_parser(
        "project-intake-next-question",
        help="Return the next human-review question for a project intake session without writing files.",
    )
    project_intake_next_question.add_argument("archive_root", help="Archive root to inspect.")
    project_intake_next_question_source = project_intake_next_question.add_mutually_exclusive_group(required=True)
    project_intake_next_question_source.add_argument("--staged-folder", help="One staged project folder for a new intake session.")
    project_intake_next_question_source.add_argument("--receipt", help="Archive-relative project intake decisions receipt for a continuing session.")
    project_intake_next_question.add_argument("--dry-run", action="store_true", help="Required; ask-planning only.")
    project_intake_next_question.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    project_intake_next_question.set_defaults(func=command_project_intake_next_question)

    project_intake_decision_template = subcommands.add_parser(
        "project-intake-decision-template",
        help="Build a next-question project intake decisions JSON template without writing files.",
    )
    project_intake_decision_template.add_argument("archive_root", help="Archive root to inspect.")
    project_intake_decision_template_source = project_intake_decision_template.add_mutually_exclusive_group(required=True)
    project_intake_decision_template_source.add_argument("--staged-folder", help="One staged project folder for a new intake session.")
    project_intake_decision_template_source.add_argument("--receipt", help="Archive-relative project intake decisions receipt for a continuing session.")
    project_intake_decision_template.add_argument("--session-id", help="Safe session id to place in the decision record template.")
    project_intake_decision_template.add_argument("--staged-folder-ref", help="Optional non-secret staged folder reference for the template.")
    project_intake_decision_template.add_argument("--dry-run", action="store_true", help="Required; template only.")
    project_intake_decision_template.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    project_intake_decision_template.set_defaults(func=command_project_intake_decision_template)

    project_intake_item_plan = subcommands.add_parser(
        "project-intake-item-plan",
        help="Preview the source-intake dry-run route for one selected project intake item.",
    )
    project_intake_item_plan.add_argument("archive_root", help="Archive root to inspect.")
    project_intake_item_plan.add_argument("--receipt", required=True, help="Archive-relative project intake decisions receipt.")
    project_intake_item_plan.add_argument("--local-path", required=True, help="One local file selected by the human for item planning.")
    project_intake_item_plan.add_argument("--source-role", default=archive_services.SOURCE_INTAKE_DEFAULT_ROLE, help="Source role for later draft provenance.")
    project_intake_item_plan.add_argument("--title", help="Optional non-secret human-reviewed title.")
    project_intake_item_plan.add_argument("--mime", help="Optional MIME type.")
    project_intake_item_plan.add_argument("--dry-run", action="store_true", help="Required; preview only.")
    project_intake_item_plan.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    project_intake_item_plan.set_defaults(func=command_project_intake_item_plan)

    recovery_plan = subcommands.add_parser("recovery-plan", help="Show local backup and restore readiness without writing files.")
    recovery_plan.add_argument("archive_root", help="Archive root to inspect.")
    recovery_plan.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    recovery_plan.set_defaults(func=command_recovery_plan)

    upgrade_check = subcommands.add_parser("upgrade-check", help="Check upgrade readiness without writing files.")
    upgrade_check.add_argument("archive_root", help="Archive root to inspect.")
    upgrade_check.add_argument("--dry-run", action="store_true", help="Required; report readiness without writing files.")
    upgrade_check.add_argument("--require-restore-drill", action="store_true", help="Block if no successful restore drill receipt is present.")
    upgrade_check.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    upgrade_check.set_defaults(func=command_upgrade_check)

    restore_drill = subcommands.add_parser("restore-drill", help="Plan or run a local restore drill for the archive control plane.")
    restore_drill.add_argument("archive_root", help="Archive root to copy from.")
    restore_drill.add_argument("--target", required=True, help="Empty or absent folder where the restored copy will be created.")
    restore_drill.add_argument("--dry-run", action="store_true", help="Preview restore drill without creating the target folder.")
    restore_drill.add_argument("--approve", action="store_true", help="Copy the archive control plane and write a restore drill receipt.")
    restore_drill.add_argument("--reviewed-by", help="Reviewer id required for approved restore drill.")
    restore_drill.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    restore_drill.set_defaults(func=command_restore_drill)

    pilot_plan = subcommands.add_parser("pilot-plan", help="Plan a safe first real personal/team archive pilot without writing files.")
    pilot_plan.add_argument("--personal-root", required=True, help="Target folder for the private personal life archive.")
    pilot_plan.add_argument("--team-root", required=True, help="Target folder for the team/company archive.")
    pilot_plan.add_argument("--personal-archive-id", default="archive:personal:life", help="Personal archive id.")
    pilot_plan.add_argument("--personal-principal-id", default="person:me", help="Personal owner/principal id.")
    pilot_plan.add_argument("--personal-principal-name", help="Personal owner display name.")
    pilot_plan.add_argument("--team-archive-id", default="archive:company:founding-team", help="Team/company archive id.")
    pilot_plan.add_argument("--team-principal-id", default="team:founding-team", help="Team owner/principal id.")
    pilot_plan.add_argument("--team-principal-name", help="Team display name.")
    pilot_plan.add_argument(
        "--personal-provider-profile",
        choices=sorted(archive_services.ONBOARDING_PROVIDER_PROFILES),
        default="object_storage_planned",
        help="Provider planning profile for the personal archive.",
    )
    pilot_plan.add_argument(
        "--team-provider-profile",
        choices=sorted(archive_services.ONBOARDING_PROVIDER_PROFILES),
        default="full_provider_plan",
        help="Provider planning profile for the team/company archive.",
    )
    pilot_plan.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    pilot_plan.set_defaults(func=command_pilot_plan)

    preflight = subcommands.add_parser("preflight", help="Check an archive before connecting real personal or team data.")
    preflight.add_argument("archive_root", help="Archive root to inspect.")
    preflight.add_argument("--peer-archive", help="Optional peer archive root to check personal/team separation.")
    preflight.add_argument("--require-source-maps", action="store_true", help="Block if any enabled source has not been mapped yet.")
    preflight.add_argument("--require-restore-drill", action="store_true", help="Block if no successful restore drill receipt is present.")
    preflight.add_argument("--check-docker", action="store_true", help="Check Docker CLI, Compose, daemon, and compose config.")
    preflight.add_argument("--strict", action="store_true", help="Treat warnings as a failing preflight.")
    preflight.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    preflight.set_defaults(func=command_preflight)

    onboard = subcommands.add_parser("onboard", help="Plan or apply beginner-friendly archive onboarding.")
    onboard.add_argument("--target-root", help="Archive folder to create, e.g. /archives/personal or .\\archives\\personal.")
    onboard.add_argument("--type", dest="archive_type", choices=["personal", "company", "family"], help="Archive template type.")
    onboard.add_argument("--archive-id", help="Archive id, e.g. archive:personal:me.")
    onboard.add_argument("--principal-id", help="Owner/principal id, e.g. person:me.")
    onboard.add_argument("--principal-name", help="Human-readable owner/principal display name.")
    onboard.add_argument(
        "--principal-kind",
        choices=["person", "family", "household", "child", "company", "team", "project", "role", "client"],
        help="Principal kind. Defaults from --type.",
    )
    onboard.add_argument("--name", help="Human-readable archive name.")
    onboard.add_argument(
        "--provider-profile",
        choices=sorted(archive_services.ONBOARDING_PROVIDER_PROFILES),
        default="local_only",
        help="External provider planning profile.",
    )
    onboard.add_argument("--guided", action="store_true", help="Ask beginner-friendly questions for missing values.")
    onboard.add_argument("--dry-run", action="store_true", help="Preview onboarding without writing files.")
    onboard.add_argument("--approve", action="store_true", help="Create the archive after the onboarding plan passes.")
    onboard.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    onboard.set_defaults(func=command_onboard)

    transfer_ownership = subcommands.add_parser(
        "transfer-ownership",
        help="Preview or apply an archive ownership transfer.",
    )
    transfer_ownership.add_argument("archive_root", help="Archive root to inspect.")
    transfer_ownership.add_argument("--new-owner", required=True, help="New owner id, e.g. person:child or company:spinout.")
    transfer_ownership.add_argument(
        "--new-owner-kind",
        choices=sorted(archive_services.OWNER_KINDS),
        help="New owner kind. Defaults to the id prefix when possible.",
    )
    transfer_ownership.add_argument("--new-owner-archive", help="Optional archive id for the new owner.")
    transfer_ownership.add_argument(
        "--operator-after",
        action="append",
        help="Operator id after transfer. Repeat for each post-transfer operator.",
    )
    transfer_ownership.add_argument(
        "--approved-by",
        action="append",
        help="Current owner/operator id that approved the proposed transfer. Repeat as needed.",
    )
    transfer_ownership.add_argument("--subject", help="Subject of the transfer, e.g. person:child.")
    transfer_ownership.add_argument("--counterparty-id", help="Trusted counterparty id to verify. Defaults to the new owner.")
    transfer_ownership.add_argument("--counterparty-fingerprint", help="Expected public key fingerprint for the new owner.")
    transfer_ownership.add_argument("--reason", help="Human-readable reason for the proposed transfer.")
    transfer_ownership.add_argument("--dry-run", action="store_true", help="Preview transfer without writing archive files.")
    transfer_ownership.add_argument("--approve", action="store_true", help="Apply the transfer after dry-run gates pass.")
    transfer_ownership.add_argument("--reviewed-by", help="Reviewer id required for real transfer, e.g. person:me.")
    transfer_ownership.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    transfer_ownership.set_defaults(func=command_transfer_ownership)

    init = subcommands.add_parser("init", help="Initialize a new archive from a template.")
    init.add_argument("archive_root", help="Target archive root. Must be absent or empty.")
    init.add_argument("--type", choices=["personal", "company", "family"], required=True, help="Archive template type.")
    init.add_argument("--archive-id", required=True, help="Archive id, e.g. archive:personal:me.")
    init.add_argument("--principal-id", required=True, help="Principal id, e.g. person:me.")
    init.add_argument("--principal-name", help="Human-readable principal display name.")
    init.add_argument(
        "--principal-kind",
        default="person",
        choices=["person", "family", "household", "child", "company", "team", "project", "role", "client"],
        help="Principal kind.",
    )
    init.add_argument("--name", help="Human-readable archive name.")
    init.add_argument("--dry-run", action="store_true", help="Show what would happen without writing files.")
    init.set_defaults(func=command_init)

    return parser


def _harden_std_streams() -> None:
    # Narrow console encodings (e.g. Korean Windows cp949) must never crash CLI output:
    # unencodable characters are replaced instead of raising UnicodeEncodeError. The
    # stream encoding itself is kept so consoles keep rendering their native charset.
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(errors="replace")
        except (OSError, ValueError):
            continue


def main(argv: list[str] | None = None) -> int:
    _harden_std_streams()
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code or 0)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
