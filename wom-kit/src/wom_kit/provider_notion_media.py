"""Notion nested media discovery and actual byte staging for approved workers."""
from __future__ import annotations

from dataclasses import dataclass, field
from collections import deque
import hashlib
import http.client
import ipaddress
import os
from pathlib import Path
import socket
import ssl
from typing import Callable
from urllib.parse import urljoin, urlsplit
import uuid

from . import provider_artifacts as artifacts


@dataclass(frozen=True)
class MediaReference:
    container_id: str
    container_kind: str
    pointer: tuple
    url: str = field(repr=False)
    file_kind: str = "file"
    source_revision: str | None = None

    @property
    def key(self):
        return artifacts.digest(artifacts.canonical([self.container_kind, self.container_id, self.pointer]))


def media_references(document: dict, *, container_id: str, container_kind: str) -> list[MediaReference]:
    found = []
    def walk(value, pointer=()):
        if isinstance(value, dict):
            kind = value.get("type")
            if kind in {"file", "external"} and isinstance(value.get(kind), dict):
                url = value[kind].get("url")
                if isinstance(url, str) and url:
                    found.append(MediaReference(container_id, container_kind, pointer, url, kind,
                        document.get("last_edited_time") if isinstance(document.get("last_edited_time"), str) else None))
                    return
            for key, child in value.items():
                walk(child, (*pointer, key))
        elif isinstance(value, list):
            for ordinal, child in enumerate(value):
                walk(child, (*pointer, ordinal))
    walk(document)
    return found


def discover(page_ids, read: Callable, *, max_blocks=10000) -> list[MediaReference]:
    """read(kind, UUID, cursor=None) returns private API payload, never a log."""
    refs, seen, blocks_seen = [], set(), set()
    for page_id in page_ids:
        page = read("page", page_id, None)
        refs.extend(media_references(page, container_id=page_id, container_kind="page"))
        queue = deque([page_id])
        while queue:
            parent = queue.popleft()
            if parent in seen:
                continue
            seen.add(parent)
            if len(seen) > max_blocks:
                raise artifacts.ProviderArtifactError("notion_media_block_limit")
            cursor, cursors = None, set()
            while True:
                response = read("children", parent, cursor)
                if not isinstance(response.get("results"), list):
                    raise artifacts.ProviderArtifactError("notion_media_children_malformed")
                for block in response["results"]:
                    if not isinstance(block, dict) or not isinstance(block.get("id"), str):
                        raise artifacts.ProviderArtifactError("notion_media_block_malformed")
                    blocks_seen.add(block["id"])
                    if len(blocks_seen) > max_blocks:
                        raise artifacts.ProviderArtifactError("notion_media_block_limit")
                    refs.extend(media_references(block, container_id=block["id"], container_kind="block"))
                    if block.get("has_children") and block.get("type") != "child_database":
                        queue.append(block["id"])
                if not response.get("has_more"):
                    break
                cursor = response.get("next_cursor")
                if not isinstance(cursor, str) or not cursor or cursor in cursors:
                    raise artifacts.ProviderArtifactError("notion_media_cursor_invalid")
                cursors.add(cursor)
    return list({ref.key: ref for ref in refs}.values())


class _PinnedHTTPS(http.client.HTTPSConnection):
    def __init__(self, hostname, address):
        super().__init__(hostname, timeout=30, context=ssl.create_default_context())
        self.address = address

    def connect(self):
        raw = socket.create_connection((self.address, 443), self.timeout)
        self.sock = self._context.wrap_socket(raw, server_hostname=self.host)


class Download:
    def __init__(self, connection, response):
        self.connection, self.response = connection, response
        self.status = response.status

    def read(self, size):
        return self.response.read(size)

    def close(self):
        self.response.close()
        self.connection.close()


def open_media(url: str):
    """No bearer/proxy/cookies; every bounded redirect is pinned public HTTPS."""
    connection = None
    try:
        seen = set()
        for _ in range(6):
            if url in seen:
                raise ValueError()
            seen.add(url)
            parsed = urlsplit(url)
            if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.port not in {None, 443}:
                raise ValueError()
            addresses = [item[4][0] for item in socket.getaddrinfo(parsed.hostname, 443, type=socket.SOCK_STREAM)]
            if not addresses or any(not ipaddress.ip_address(address).is_global for address in addresses):
                raise ValueError()
            connection = _PinnedHTTPS(parsed.hostname, addresses[0])
            target = parsed.path or "/"
            if parsed.query:
                target += "?" + parsed.query
            connection.request("GET", target, headers={"Accept": "*/*"})
            response = connection.getresponse()
            if response.status not in {301, 302, 303, 307, 308}:
                return Download(connection, response)
            location = response.getheader("Location")
            response.close()
            connection.close()
            connection = None
            if not isinstance(location, str) or not location:
                raise ValueError()
            url = urljoin(url, location)
        raise ValueError()
    except Exception:
        if connection is not None:
            connection.close()
        raise artifacts.ProviderArtifactError("notion_media_transport_unavailable") from None


def _stream_blob(root, stream, *, max_bytes):
    with artifacts.bound_artifact_parent(root, "workbench/provider-blobs/write.bin") as (bound_root, _):
        return _stream_blob_bound(bound_root, stream, max_bytes=max_bytes)


def _stream_blob_bound(root, stream, *, max_bytes):
    partial_rel = f"workbench/provider-blobs/{uuid.uuid4().hex}.partial"
    partial = artifacts.safe_path(root, partial_rel, create_parent=True)
    sha, count = hashlib.sha256(), 0
    try:
        with open(partial, "xb") as target:
            while True:
                chunk = stream.read(min(1024 * 1024, max_bytes - count + 1))
                if not chunk:
                    break
                count += len(chunk)
                if count > max_bytes:
                    raise artifacts.ProviderArtifactError("notion_media_size_limit")
                sha.update(chunk)
                target.write(chunk)
            target.flush()
            os.fsync(target.fileno())
        relative = f"workbench/provider-blobs/{sha.hexdigest()}.bin"
        destination = artifacts.safe_path(root, relative)
        if destination.exists():
            existing_sha = hashlib.sha256()
            with open(destination, "rb") as existing:
                for chunk in iter(lambda: existing.read(1024 * 1024), b""):
                    existing_sha.update(chunk)
            if existing_sha.hexdigest() != sha.hexdigest():
                raise artifacts.ProviderArtifactError("provider_artifact_collision")
        else:
            from .object_storage_restore import _atomic_move_file_no_replace
            try:
                _atomic_move_file_no_replace(partial, destination)
            except FileExistsError:
                existing_sha = hashlib.sha256()
                with open(artifacts.safe_path(root, relative), "rb") as existing:
                    for chunk in iter(lambda: existing.read(1024 * 1024), b""):
                        existing_sha.update(chunk)
                if existing_sha.hexdigest() != sha.hexdigest():
                    raise artifacts.ProviderArtifactError("provider_artifact_collision") from None
        return {"path": relative, "sha256": "sha256:" + sha.hexdigest(), "size_bytes": count}
    finally:
        if partial.exists():
            partial.unlink()


def fetch_media(root: Path, *, page_ids: list[str], batch_id: str, read: Callable,
                download: Callable = open_media, max_bytes: int = 512 * 1024 * 1024) -> dict:
    """Execute within an approved worker; results stop at staging, not capture."""
    if not batch_id or not all(char.isascii() and (char.isalnum() or char in "-_") for char in batch_id):
        raise artifacts.ProviderArtifactError("notion_media_batch_invalid")
    if not isinstance(max_bytes, int) or isinstance(max_bytes, bool) or max_bytes < 1:
        raise artifacts.ProviderArtifactError("notion_media_limit_invalid")
    receipt_path = f"workbench/notion-media/{batch_id}/media-receipt.json"
    request_path = f"workbench/notion-media/{batch_id}/source-intake-batch-request.json"
    with artifacts.exclusive_run(root, f"workbench/notion-media/{batch_id}/run.lock"):
        rows, items = [], []
        previous = artifacts.read_json(root, receipt_path) if artifacts.safe_path(root, receipt_path).exists() else {}
        previous = {row.get("reference_sha256"): row for row in previous.get("items", []) if isinstance(row, dict)}
        for ref in discover(page_ids, read):
            stream = None
            try:
                retained = previous.get(ref.key)
                if (ref.source_revision is not None and retained and retained.get("status") in {"staged", "existing_staged"}
                        and retained.get("source_revision") == ref.source_revision):
                    old_path = artifacts.safe_path(root, retained["path"])
                    sha = hashlib.sha256()
                    with open(old_path, "rb") as existing:
                        for chunk in iter(lambda: existing.read(1024 * 1024), b""):
                            sha.update(chunk)
                    if "sha256:" + sha.hexdigest() != retained["sha256"]:
                        raise artifacts.ProviderArtifactError("provider_artifact_collision")
                    rows.append({**retained, "status": "existing_staged"})
                    items.append({"item_id": "media-" + ref.key[7:31], "local_path": retained["path"], "source_role": "attachment"})
                    continue
                stream = download(ref.url)
                if stream.status in {401, 403, 404} and ref.file_kind == "file":
                    stream.close()
                    document = read(ref.container_kind, ref.container_id, None)
                    refreshed = {item.key: item for item in media_references(document, container_id=ref.container_id, container_kind=ref.container_kind)}
                    if ref.key not in refreshed:
                        raise artifacts.ProviderArtifactError("notion_media_reference_changed")
                    stream = download(refreshed[ref.key].url)
                if stream.status != 200:
                    raise artifacts.ProviderArtifactError("notion_media_http_failed")
                blob = _stream_blob(root, stream, max_bytes=max_bytes)
                rows.append({"reference_sha256": ref.key, "container_id": ref.container_id,
                    "container_kind": ref.container_kind, "pointer": ref.pointer, "status": "staged",
                    "source_revision": ref.source_revision, **blob})
                items.append({"item_id": "media-" + ref.key[7:31], "local_path": blob["path"], "source_role": "attachment"})
            except artifacts.ProviderArtifactError as exc:
                rows.append({"reference_sha256": ref.key, "status": "failed", "reason_code": exc.code})
            except Exception:
                rows.append({"reference_sha256": ref.key, "status": "failed", "reason_code": "notion_media_download_failed"})
            finally:
                if stream is not None:
                    stream.close()
            paths, aliases = artifacts.write_intake_requests(root, f"workbench/notion-media/{batch_id}", "notion-media-" + batch_id, items)
            artifacts.write_json(root, receipt_path, {"schema": "wom-kit/notion-media-receipt/v1", "items": rows, "intake_requests": paths, "intake_item_aliases": aliases})
        if rows:
            paths, aliases = artifacts.write_intake_requests(root, f"workbench/notion-media/{batch_id}", "notion-media-" + batch_id, items)
            artifacts.write_json(root, receipt_path, {"schema": "wom-kit/notion-media-receipt/v1", "items": rows, "intake_requests": paths, "intake_item_aliases": aliases})
        failed = sum(row["status"] == "failed" for row in rows)
        return {"ok": not failed, "staged": len(items), "failed": failed, "capture_completed": False,
            "intake_requests": paths if rows else [],
            "receipt_path": receipt_path if rows else None, "intake_request": request_path if items else None}
