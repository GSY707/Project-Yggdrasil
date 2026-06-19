from __future__ import annotations

import json
import shutil
from hashlib import sha256
from pathlib import Path
from typing import Any

from ..contracts import ExternalRef
from ..support import ensure_state_subdir, new_id, read_json, relative_workspace_path, resolve_workspace_root, utc_now, write_json


DURABLE_SNAPSHOT_STORE_VERSION = "durable-snapshot.v1"


def _json_bytes(payload: Any) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha256(payload: Any) -> str:
    return "sha256:" + sha256(_json_bytes(payload)).hexdigest()


def canonical_request_digest(payload: dict[str, Any] | None) -> str:
    return _sha256(payload or {})


def _safe_part(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "_" for ch in str(value or "").strip()) or "unknown"


def _resolve_state_file_locator(locator: str) -> Path:
    path = Path(locator)
    if path.is_absolute():
        return path
    return (resolve_workspace_root() / path).resolve()


def read_state_file_ref(ref: ExternalRef | dict[str, Any] | None, default: Any = None) -> Any:
    if ref is None:
        return default
    if isinstance(ref, dict):
        ref_type = str(ref.get("type") or "")
        locator = str(ref.get("locator") or "")
    else:
        ref_type = ref.type
        locator = ref.locator
    if ref_type != "state-file" or not locator:
        return default
    return read_json(_resolve_state_file_locator(locator), default)


def commit_snapshot_manifest(
    *,
    project_id: str,
    task_id: str,
    snapshot_id: str,
    retention_class: str,
    snapshot_type: str,
    root_mount: dict[str, Any],
    current_context: list[dict[str, Any]],
    request_state: dict[str, Any],
    pending_actions: list[dict[str, Any]],
    pending_writes: list[dict[str, Any]],
    tool_state: dict[str, Any] | None = None,
    budget_state: dict[str, Any] | None = None,
    routing_state: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    base = (
        ensure_state_subdir("snapshots")
        / _safe_part(project_id)
        / _safe_part(task_id)
        / _safe_part(snapshot_id)
    )
    tmp = base.with_name(f"{base.name}.tmp-{new_id('snapstore')}")
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True, exist_ok=True)

    entries_payload: dict[str, Any] = {
        "rootMount": root_mount,
        "currentContext": current_context,
        "requestState": request_state,
        "pendingActions": pending_actions,
        "pendingWrites": pending_writes,
        "toolState": tool_state or {},
        "budgetState": budget_state or {},
        "routingState": routing_state or {},
    }
    entry_refs: dict[str, ExternalRef] = {}
    manifest_entries: dict[str, dict[str, Any]] = {}
    blobs_dir = tmp / "blobs"
    for name, payload in entries_payload.items():
        filename = f"{_safe_part(name)}.json"
        blob_path = blobs_dir / filename
        final_blob_path = base / "blobs" / filename
        write_json(blob_path, payload)
        ref = ExternalRef(type="state-file", locator=relative_workspace_path(final_blob_path))
        entry_refs[name] = ref
        manifest_entries[name] = {
            "ref": ref.model_dump(mode="json"),
            "checksum": _sha256(payload),
            "contentType": "application/json",
        }

    manifest_body = {
        "version": DURABLE_SNAPSHOT_STORE_VERSION,
        "schemaVersion": "task-snapshot.v1",
        "runtimeContractVersion": "task-pause-resume-continuation-contract-v0.1",
        "projectId": project_id,
        "taskId": task_id,
        "snapshotId": snapshot_id,
        "snapshotType": snapshot_type,
        "retentionClass": retention_class,
        "createdAt": utc_now().isoformat(),
        "canonicalRequestDigest": canonical_request_digest(request_state),
        "entries": manifest_entries,
        "metadata": dict(metadata or {}),
    }
    manifest_checksum = _sha256(manifest_body)
    manifest = {**manifest_body, "checksum": manifest_checksum}
    manifest_path = tmp / "manifest.json"
    write_json(manifest_path, manifest)

    if base.exists():
        shutil.rmtree(base)
    tmp.rename(base)
    final_manifest_path = base / "manifest.json"
    manifest_ref = ExternalRef(type="state-file", locator=relative_workspace_path(final_manifest_path))
    return {
        "manifest": manifest,
        "manifestRef": manifest_ref,
        "manifestChecksum": manifest_checksum,
        "entryRefs": entry_refs,
    }


def load_snapshot_manifest(ref: ExternalRef | dict[str, Any] | None) -> dict[str, Any]:
    manifest = read_state_file_ref(ref, default=None)
    if not isinstance(manifest, dict):
        raise FileNotFoundError(f"Snapshot manifest not found: {ref}")
    return manifest


def verify_snapshot_manifest(ref: ExternalRef | dict[str, Any] | None, expected_checksum: str | None) -> dict[str, Any]:
    manifest = load_snapshot_manifest(ref)
    manifest_body = dict(manifest)
    actual_manifest_checksum = str(manifest_body.pop("checksum", ""))
    recomputed_manifest_checksum = _sha256(manifest_body)
    expected = str(expected_checksum or actual_manifest_checksum or "").strip()
    if not expected:
        raise ValueError("manifest-checksum-missing")
    if expected != actual_manifest_checksum or actual_manifest_checksum != recomputed_manifest_checksum:
        raise ValueError("manifest-checksum-mismatch")

    entries = manifest.get("entries") if isinstance(manifest.get("entries"), dict) else {}
    for name, entry in entries.items():
        if not isinstance(entry, dict):
            raise ValueError(f"manifest-entry-invalid:{name}")
        payload = read_state_file_ref(entry.get("ref"), default=None)
        if payload is None:
            raise FileNotFoundError(f"manifest-entry-missing:{name}")
        checksum = str(entry.get("checksum") or "")
        if not checksum or checksum != _sha256(payload):
            raise ValueError(f"manifest-entry-checksum-mismatch:{name}")
    return manifest


def read_snapshot_entry(manifest: dict[str, Any], name: str, default: Any = None) -> Any:
    entries = manifest.get("entries") if isinstance(manifest.get("entries"), dict) else {}
    entry = entries.get(name)
    if not isinstance(entry, dict):
        return default
    return read_state_file_ref(entry.get("ref"), default=default)


def delete_snapshot_payload(ref: ExternalRef | dict[str, Any] | None) -> bool:
    if ref is None:
        return False
    manifest_path = _resolve_state_file_locator(ref["locator"] if isinstance(ref, dict) else ref.locator)
    snapshot_dir = manifest_path.parent
    if not snapshot_dir.exists():
        return False
    shutil.rmtree(snapshot_dir)
    return True
