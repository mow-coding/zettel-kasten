"""Execution-local lookups reused only after reading exact current bytes.

No mtime-only trust, persisted authority, or deletion permission is cached.
Append generations parse only the suffix; replacement generations rebuild.
"""
import json
from pathlib import Path


class ManifestLookup:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.raw = None
        self.by_object = {}
        self.reads = self.parsed_rows = self.rebuilds = self.reuses = 0

    def rows(self, object_id):
        from . import archive_services as services
        path = services.archive_internal_path(self.root, "objects/manifests/files.jsonl")
        if not path.exists():
            self.raw, self.by_object = None, {}
            return ()
        raw = services.archive_index_stable_file_snapshot(self.root, path,
            max_bytes=services.ZETTEL_OBJET_LINK_MANIFEST_MAX_BYTES)["raw"]
        self.reads += 1
        if raw == self.raw:
            self.reuses += 1
            return tuple(self.by_object.get(object_id, ()))
        append = self.raw is not None and self.raw.endswith(b"\n") and raw.startswith(self.raw)
        segment = raw[len(self.raw):] if append else raw
        parsed = []
        # Same row semantics as the historical reader. Authorization and
        # preservation writers still perform their own strict final checks.
        for line in segment.decode("utf-8").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                parsed.append(row)
        if not append:
            self.by_object = {}
            self.rebuilds += 1
        for row in parsed:
            key = row.get("object_id")
            if isinstance(key, str):
                self.by_object.setdefault(key, []).append(row)
        self.parsed_rows += len(parsed)
        self.raw = raw
        return tuple(self.by_object.get(object_id, ()))

    def observations(self):
        return {"exact_manifest_reads": self.reads, "parsed_rows": self.parsed_rows,
            "full_lookup_rebuilds": self.rebuilds, "unchanged_generation_reuses": self.reuses,
            "authority_or_remote_verification_cached": False}
