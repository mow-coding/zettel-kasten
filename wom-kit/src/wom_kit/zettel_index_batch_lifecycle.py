"""Shared same-generation index lifecycle for batch Zet writers.

The domain writers remain the authority for their exact field effects.  This
adapter only coordinates the generated SQLite projection around those effects:
one durable dirty intent before the first canonical Zet write, one atomic batch
delta after the exact operation completes, and an honest rebuild-required
result whenever no safe current generation can be maintained.
"""

from __future__ import annotations

from dataclasses import dataclass
import hmac
from pathlib import Path
import sqlite3
from typing import Any, Iterable, Mapping

from . import archive_services


def _dirty_index_generation(
    root: Path,
    *,
    expected_mutation_owner_sha256: str,
) -> str | None:
    db_path = root / archive_services.INDEX_RELATIVE_PATH
    if not db_path.is_file():
        return None
    try:
        conn = archive_services.connect_archive_index(
            db_path,
            row_factory=True,
        )
        try:
            metadata = archive_services.read_archive_index_metadata(conn)
        finally:
            conn.close()
    except (OSError, sqlite3.Error, ValueError):
        return None
    generation = str(metadata.get("generation") or "")
    if (
        metadata.get("schema") != archive_services.INDEX_METADATA_SCHEMA
        or metadata.get("state") != archive_services.INDEX_STATE_DIRTY
        or archive_services.INDEX_SEAL_PENDING_KEY in metadata
        or archive_services.INDEX_GENERATION_RE.fullmatch(generation) is None
        or not hmac.compare_digest(
            str(metadata.get(archive_services.INDEX_MUTATION_OWNER_KEY) or ""),
            expected_mutation_owner_sha256,
        )
    ):
        return None
    return generation


def _truth(
    *,
    generation: str | None,
    generated_index_updated: bool,
    index_marked_dirty: bool,
    index_current: bool,
    index_delta_failed: bool,
    mutation_started: bool,
    mutation_resumed: bool,
    rebuild_required: bool | None = None,
) -> dict[str, Any]:
    if rebuild_required is None:
        rebuild_required = not index_current
    return {
        "index_generation": generation,
        "generated_index_updated": generated_index_updated,
        "index_marked_dirty": index_marked_dirty,
        "index_current": index_current,
        "index_rebuild_required": rebuild_required,
        "index_reason_codes": (
            [archive_services.INDEX_REBUILD_REQUIRED]
            if rebuild_required
            else []
        ),
        "index_delta_failed": index_delta_failed,
        "index_mutation_started": mutation_started,
        "index_mutation_resumed": mutation_resumed,
    }


@dataclass
class ZettelIndexBatchLifecycle:
    """Coordinate one exact-operation batch against an optional Zet index."""

    root: Path
    generation: str | None
    can_begin: bool
    mutation_active: bool
    mutation_started: bool
    mutation_resumed: bool
    has_zettel_targets: bool
    operation_owner_sha256: str
    lease_token: archive_services.ArchiveIndexMutationLeaseToken | None = None

    @property
    def precondition_blocked(self) -> bool:
        """Whether a Zet writer must stop before any exact-operation write."""

        return bool(
            self.has_zettel_targets
            and not self.can_begin
            and not self.mutation_active
        )

    def precondition_truth(self) -> dict[str, Any]:
        """Return the fixed rebuild truth for a blocked writer precondition."""

        return _truth(
            generation=self.generation,
            generated_index_updated=False,
            index_marked_dirty=False,
            index_current=False,
            index_delta_failed=False,
            mutation_started=False,
            mutation_resumed=self.mutation_resumed,
        )

    @classmethod
    def inspect(
        cls,
        root: Path,
        *,
        has_zettel_targets: bool,
        allow_dirty_resume: bool,
        operation_owner_sha256: str,
    ) -> "ZettelIndexBatchLifecycle":
        if (
            archive_services.INDEX_SNAPSHOT_SHA256_RE.fullmatch(
                str(operation_owner_sha256 or "")
            )
            is None
        ):
            raise archive_services.ArchiveServiceError(
                archive_services.INDEX_REBUILD_REQUIRED
            )
        if not has_zettel_targets:
            return cls(
                root=root,
                generation=None,
                can_begin=False,
                mutation_active=False,
                mutation_started=False,
                mutation_resumed=False,
                has_zettel_targets=False,
                operation_owner_sha256=operation_owner_sha256,
            )
        try:
            evidence = archive_services.require_current_zettel_index(root)
        except (archive_services.ArchiveServiceError, OSError, ValueError):
            evidence = {"ok": False}
        if evidence.get("ok") is True:
            generation = str(evidence.get("generation") or "")
            if archive_services.INDEX_GENERATION_RE.fullmatch(generation):
                return cls(
                    root=root,
                    generation=generation,
                    can_begin=True,
                    mutation_active=False,
                    mutation_started=False,
                    mutation_resumed=False,
                    has_zettel_targets=True,
                    operation_owner_sha256=operation_owner_sha256,
                )
        if allow_dirty_resume:
            generation = _dirty_index_generation(
                root,
                expected_mutation_owner_sha256=operation_owner_sha256,
            )
            if generation is not None:
                return cls(
                    root=root,
                    generation=generation,
                    can_begin=False,
                    mutation_active=True,
                    mutation_started=False,
                    mutation_resumed=True,
                    has_zettel_targets=True,
                    operation_owner_sha256=operation_owner_sha256,
                )
        return cls(
            root=root,
            generation=None,
            can_begin=False,
            mutation_active=False,
            mutation_started=False,
            mutation_resumed=False,
            has_zettel_targets=True,
            operation_owner_sha256=operation_owner_sha256,
        )

    def before_canonical_write(self) -> None:
        """Persist one dirty intent after target revalidation, before CAS."""

        if not self.has_zettel_targets:
            return
        if self.mutation_active:
            if self.lease_token is None and self.generation is not None:
                self.lease_token = archive_services.resume_archive_index_mutation(
                    self.root,
                    expected_generation=self.generation,
                    expected_mutation_owner_sha256=(
                        self.operation_owner_sha256
                    ),
                )
            return
        if not self.can_begin or self.generation is None:
            return
        self.lease_token = archive_services.begin_archive_index_mutation(
            self.root,
            expected_generation=self.generation,
            mutation_owner_sha256=self.operation_owner_sha256,
        )
        self.mutation_active = True
        self.mutation_started = True
        self.can_begin = False

    def _mark_dirty(self) -> bool:
        if not self.mutation_active or self.generation is None:
            return False
        try:
            marked = bool(
                archive_services.mark_archive_index_dirty(
                    self.root,
                    expected_generation=self.generation,
                    expected_mutation_owner_sha256=(
                        self.operation_owner_sha256
                    ),
                    lease_token=self.lease_token,
                )
            )
            self.lease_token = None
            return marked
        except archive_services._ArchiveIndexDirtyRestoreUncertainError:
            # The common writer intentionally retains the exact opaque token
            # when it cannot prove durable DIRTY.  Preserve both the exception
            # and our only reference so a recovery caller can finish safely.
            raise
        except (archive_services.ArchiveServiceError, OSError, ValueError):
            self.lease_token = None
            return False

    def interrupted(self) -> dict[str, Any]:
        """Return durable truth after a failed or interrupted exact runner."""

        if not self.has_zettel_targets:
            return _truth(
                generation=None,
                generated_index_updated=False,
                index_marked_dirty=False,
                index_current=False,
                index_delta_failed=False,
                mutation_started=False,
                mutation_resumed=False,
                rebuild_required=False,
            )
        marked = self._mark_dirty()
        if self.mutation_active:
            return _truth(
                generation=self.generation,
                generated_index_updated=False,
                index_marked_dirty=marked,
                index_current=False,
                index_delta_failed=False,
                mutation_started=self.mutation_started,
                mutation_resumed=self.mutation_resumed,
            )
        if self.can_begin:
            return _truth(
                generation=self.generation,
                generated_index_updated=False,
                index_marked_dirty=False,
                index_current=True,
                index_delta_failed=False,
                mutation_started=False,
                mutation_resumed=False,
            )
        return _truth(
            generation=self.generation,
            generated_index_updated=False,
            index_marked_dirty=False,
            index_current=False,
            index_delta_failed=False,
            mutation_started=False,
            mutation_resumed=self.mutation_resumed,
        )

    def delta_failed(self) -> dict[str, Any]:
        """Keep an active generation dirty after post-write delta failure."""

        if not self.has_zettel_targets:
            return _truth(
                generation=None,
                generated_index_updated=False,
                index_marked_dirty=False,
                index_current=False,
                index_delta_failed=False,
                mutation_started=False,
                mutation_resumed=False,
                rebuild_required=False,
            )
        marked = self._mark_dirty()
        return _truth(
            generation=self.generation,
            generated_index_updated=False,
            index_marked_dirty=marked,
            index_current=False,
            index_delta_failed=self.mutation_active,
            mutation_started=self.mutation_started,
            mutation_resumed=self.mutation_resumed,
        )

    def finalize(
        self,
        entries: Iterable[Mapping[str, Any]],
    ) -> dict[str, Any]:
        """Apply one exact batch delta, or preserve honest rebuild truth."""

        materialized = tuple(dict(entry) for entry in entries)
        if not self.has_zettel_targets:
            return _truth(
                generation=None,
                generated_index_updated=False,
                index_marked_dirty=False,
                index_current=False,
                index_delta_failed=False,
                mutation_started=False,
                mutation_resumed=False,
                rebuild_required=False,
            )
        if self.mutation_active and self.generation is not None:
            if self.lease_token is None:
                try:
                    self.lease_token = archive_services.resume_archive_index_mutation(
                        self.root,
                        expected_generation=self.generation,
                        expected_mutation_owner_sha256=(
                            self.operation_owner_sha256
                        ),
                    )
                except (
                    archive_services.ArchiveServiceError,
                    OSError,
                    ValueError,
                ):
                    return _truth(
                        generation=self.generation,
                        generated_index_updated=False,
                        index_marked_dirty=False,
                        index_current=False,
                        index_delta_failed=True,
                        mutation_started=self.mutation_started,
                        mutation_resumed=self.mutation_resumed,
                    )
            try:
                updated = bool(
                    archive_services.upsert_zettel_index_entries(
                        self.root,
                        materialized,
                        expected_generation=self.generation,
                        expected_mutation_owner_sha256=(
                            self.operation_owner_sha256
                        ),
                        lease_token=self.lease_token,
                    )
                )
            except archive_services._ArchiveIndexDirtyRestoreUncertainError:
                raise
            except (archive_services.ArchiveServiceError, OSError, ValueError):
                updated = False
            if updated:
                archive_services._release_archive_index_mutation_lease(
                    self.root,
                    lease_token=self.lease_token,
                )
                self.lease_token = None
                self.mutation_active = False
                return _truth(
                    generation=self.generation,
                    generated_index_updated=True,
                    index_marked_dirty=False,
                    index_current=True,
                    index_delta_failed=False,
                    mutation_started=self.mutation_started,
                    mutation_resumed=self.mutation_resumed,
                )
            marked = self._mark_dirty()
            return _truth(
                generation=self.generation,
                generated_index_updated=False,
                index_marked_dirty=marked,
                index_current=False,
                index_delta_failed=True,
                mutation_started=self.mutation_started,
                mutation_resumed=self.mutation_resumed,
            )
        if self.can_begin:
            # ExactOperationManifest found every field already at destination;
            # no canonical byte changed, so no dirty intent or delta is needed.
            return _truth(
                generation=self.generation,
                generated_index_updated=False,
                index_marked_dirty=False,
                index_current=True,
                index_delta_failed=False,
                mutation_started=False,
                mutation_resumed=False,
            )
        return _truth(
            generation=self.generation,
            generated_index_updated=False,
            index_marked_dirty=False,
            index_current=False,
            index_delta_failed=False,
            mutation_started=False,
            mutation_resumed=self.mutation_resumed,
        )


__all__ = ["ZettelIndexBatchLifecycle"]
