from __future__ import annotations

from hashlib import sha1
from pathlib import Path
import re
from typing import Any

from yggdrasil_media_providers.pipeline import plan_asset_processing
from yggdrasil_sdk.contracts import ExternalRef, ToolDescriptor
from yggdrasil_sdk.module import BaseModulePlugin, HookRegistration
from yggdrasil_sdk.hooks import HookNames
from yggdrasil_sdk.persistence import get_persistence_runtime
from yggdrasil_sdk.persistence.constants import DEFAULT_BRANCH_ID, DEFAULT_PROJECT_ID, DEFAULT_SPACE_ID
from yggdrasil_sdk.persistence.repositories import AssetRepository, NodeRepository, WorkspaceBootstrapRepository
from yggdrasil_sdk.support import ensure_state_subdir, new_id, normalize_excerpt, relative_workspace_path, resolve_workspace_root, utc_now, write_json


TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_\-\u4e00-\u9fff]+")


def _normalize_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _segment_text(text: str, target_chars: int) -> list[tuple[int, int, str]]:
    compact = _normalize_text(text)
    if not compact:
        return []
    sentences = [segment.strip() for segment in re.split(r"(?<=[。！？.!?])\s+", compact) if segment.strip()]
    if not sentences:
        sentences = [compact]
    segments: list[tuple[int, int, str]] = []
    current = ""
    start_offset = 0
    cursor = 0
    for sentence in sentences:
        if not current:
            start_offset = cursor
            current = sentence
            cursor += len(sentence) + 1
            continue
        if len(current) + 1 + len(sentence) <= target_chars:
            current = f"{current} {sentence}"
            cursor += len(sentence) + 1
            continue
        segments.append((start_offset, start_offset + len(current), current))
        start_offset = cursor - len(sentence) - 1
        current = sentence
        cursor += len(sentence) + 1
    if current:
        segments.append((start_offset, start_offset + len(current), current))
    return segments


def _embedding_payload(text: str, max_terms: int) -> dict[str, Any]:
    frequencies: dict[str, int] = {}
    for token in TOKEN_PATTERN.findall(text.lower()):
        frequencies[token] = frequencies.get(token, 0) + 1
    ranked_terms = sorted(frequencies.items(), key=lambda item: (-item[1], item[0]))[:max_terms]
    return {
        "terms": [{"term": term, "weight": weight} for term, weight in ranked_terms],
        "dimension": len(ranked_terms),
    }


class MultimodalMemoryModule(BaseModulePlugin):
    module_id = "multimodal-memory"

    def manifest_path(self) -> Path:
        return Path(__file__).resolve().parents[2] / "yggdrasil.module.yaml"

    def register_hooks(self) -> tuple[HookRegistration, ...]:
        return (
            HookRegistration(name=HookNames.MODULE_ENABLE_PREFLIGHT, handler=self.enable_preflight),
            HookRegistration(name=HookNames.MODULE_HEALTH_REPORT, handler=self.report_health),
            HookRegistration(name=HookNames.AGENT_TOOLS_REGISTER, handler=self.register_tools_hook),
        )

    def register_tools(self) -> tuple[dict[str, object], ...]:
        tools = (
            ToolDescriptor(
                name="multimodal_memory.ingest_asset",
                moduleId=self.module_id,
                version="0.1.0",
                displayName="Ingest Multimodal Asset",
                description="Create a formal asset record, segments, embeddings, and a memory node from multimodal input materials.",
                schemaRef="docs/specs/asset-packaging-evaluation-data-spec-v0.1.md",
                executionMode="sync",
                timeoutMs=6000,
                permissionRequired=["asset.write", "node.write"],
                inputSchema={
                    "type": "object",
                    "properties": {
                        "mediaType": {"type": "string"},
                        "sourceUri": {"type": "string"},
                        "sourceText": {"type": "string"},
                        "transcript": {"type": "string"},
                        "captions": {"type": "string"},
                        "ownerNodeId": {"type": "string"},
                        "spaceId": {"type": "string"},
                        "branchId": {"type": "string"},
                    },
                    "required": ["mediaType"],
                    "additionalProperties": False,
                },
                implementationRef="yggdrasil_multimodal_memory.plugin:ingest_asset_tool",
            ),
        )
        return tuple(tool.model_dump(by_alias=True) for tool in tools)

    def register_tools_hook(self, payload: dict[str, object]) -> dict[str, object]:
        return {
            "tools": list(self.register_tools()),
            "toolCount": len(self.register_tools()),
            "moduleId": self.module_id,
        }

    def enable_preflight(self, payload: dict[str, object]) -> dict[str, object]:
        try:
            plan_asset_processing("image")
        except Exception as exc:
            return {"status": "error", "summary": f"Multimodal Memory preflight failed: {exc}"}
        return {"status": "ok", "summary": "Multimodal Memory preflight passed."}

    def report_health(self, payload: dict[str, object]) -> dict[str, object]:
        return {
            "status": "healthy",
            "summary": "Multimodal Memory is ready to persist assets, segments, embeddings, and grounded memory nodes.",
        }

    def ingest_asset(self, payload: dict[str, object]) -> dict[str, object]:
        execution_context = payload.get("executionContext") if isinstance(payload.get("executionContext"), dict) else {}
        project_id = str(execution_context.get("projectId") or payload.get("projectId") or DEFAULT_PROJECT_ID)
        space_id = str(payload.get("spaceId") or execution_context.get("spaceId") or DEFAULT_SPACE_ID)
        branch_id = str(payload.get("branchId") or execution_context.get("branchId") or DEFAULT_BRANCH_ID)
        source_work_tree_node_id = str(execution_context.get("sourceWorkTreeNodeId") or "").strip() or None
        media_type = str(payload.get("mediaType") or "document")
        source_text = _normalize_text(payload.get("sourceText") or payload.get("transcript") or payload.get("captions") or payload.get("sourceUri"))
        if not source_text:
            raise ValueError("Multimodal asset ingestion requires sourceText, transcript, captions, or sourceUri.")

        workspace_root = resolve_workspace_root()
        planned_pipeline = plan_asset_processing(media_type)
        checksum = sha1(source_text.encode("utf-8")).hexdigest()
        asset_id = str(payload.get("id") or new_id("asset", media_type, checksum[:12]))
        asset_dir = ensure_state_subdir(f"assets/{planned_pipeline['assetKind']}", workspace_root)
        asset_manifest_path = asset_dir / f"{asset_id}.json"
        write_json(
            asset_manifest_path,
            {
                "assetId": asset_id,
                "mediaType": media_type,
                "sourceUri": payload.get("sourceUri"),
                "sourceText": source_text,
                "plan": planned_pipeline,
                "ingestedAt": utc_now().isoformat(),
            },
        )
        asset_storage_key = relative_workspace_path(asset_manifest_path, workspace_root)
        actor = execution_context.get("actor") if isinstance(execution_context.get("actor"), dict) else {"type": "module", "id": self.module_id}

        runtime = get_persistence_runtime()
        with runtime.session_scope() as session:
            WorkspaceBootstrapRepository(session).ensure_default_workspace()
            WorkspaceBootstrapRepository(session).ensure_branch_workspace(
                branch_id=branch_id,
                project_id=project_id,
                space_id=space_id,
            )
            asset_repository = AssetRepository(session)
            node_repository = NodeRepository(session)
            asset = asset_repository.create_asset(
                {
                    "id": asset_id,
                    "projectId": project_id,
                    "spaceId": space_id,
                    "branchId": branch_id,
                    "ownerNodeId": payload.get("ownerNodeId"),
                    "mediaType": media_type,
                    "role": "original",
                    "storageKey": asset_storage_key,
                    "checksum": checksum,
                    "sourceRef": {"type": "file", "locator": asset_storage_key},
                    "relatedWorkTreeNodeIds": [source_work_tree_node_id] if source_work_tree_node_id is not None else [],
                    "createdBy": actor,
                }
            )
            segments = _segment_text(source_text, 220)
            segment_payloads: list[dict[str, Any]] = []
            for index, (start_offset, end_offset, segment_text) in enumerate(segments, start=1):
                embedding_id = new_id("embedding", asset.id, index, stable=True)
                embedding_dir = ensure_state_subdir("assets/embeddings", workspace_root)
                embedding_path = embedding_dir / f"{embedding_id}.json"
                payload_body = _embedding_payload(segment_text, 24)
                write_json(
                    embedding_path,
                    {
                        "embeddingId": embedding_id,
                        "assetId": asset.id,
                        "ownerKind": "asset-segment",
                        "ownerOrdinal": index,
                        "vector": payload_body,
                    },
                )
                embedding_record = asset_repository.create_embedding(
                    {
                        "id": embedding_id,
                        "ownerKind": "asset-segment",
                        "ownerId": new_id("assetseg", asset.id, index, stable=True),
                        "model": "keyword-hash-v1",
                        "dimension": payload_body["dimension"],
                        "vectorRef": {"type": "file", "locator": relative_workspace_path(embedding_path, workspace_root)},
                    }
                )
                segment_payloads.append(
                    {
                        "id": new_id("assetseg", asset.id, index, stable=True),
                        "ordinal": index,
                        "startOffset": start_offset,
                        "endOffset": end_offset,
                        "textExcerpt": normalize_excerpt(segment_text, 220),
                        "summary": normalize_excerpt(segment_text, 96),
                        "embeddingId": embedding_record.id,
                    }
                )
            segment_records = asset_repository.replace_asset_segments(asset.id, segment_payloads)
            _, context_refs, _ = node_repository.root_mount_refs(project_id, branch_id)
            summary_node = node_repository.create_node(
                {
                    "projectId": project_id,
                    "spaceId": space_id,
                    "branchId": branch_id,
                    "parentId": payload.get("ownerNodeId") or context_refs[0].id,
                    "rootBranch": "context",
                    "nodeType": "reference",
                    "title": normalize_excerpt(f"{planned_pipeline['assetKind']} asset: {payload.get('sourceUri') or media_type}", 96),
                    "content": "\n".join(
                        [
                            f"Media type: {media_type}",
                            f"Derived roles: {', '.join(planned_pipeline['derivedRoles'])}",
                            f"Summary strategy: {planned_pipeline['summaryStrategy']}",
                            f"Segments: {len(segment_records)}",
                            f"Excerpt: {normalize_excerpt(source_text, 180)}",
                        ]
                    ),
                    "sourceWorkTreeNodeId": source_work_tree_node_id,
                    "createdBy": actor,
                    "updatedBy": actor,
                    "changeReason": "multimodal-asset-ingest",
                }
            )
            node_repository.add_source_annotation(
                "node",
                summary_node.id,
                {
                    "projectId": project_id,
                    "branchId": branch_id,
                    "sourceType": "external",
                    "sourceRef": {"type": "file", "locator": asset_storage_key},
                    "excerpt": normalize_excerpt(source_text, 180),
                    "confidence": 0.92,
                    "createdBy": actor,
                },
            )

        return {
            "asset": asset.model_dump(by_alias=True, mode="json"),
            "segments": [record.model_dump(by_alias=True, mode="json") for record in segment_records],
            "segmentCount": len(segment_records),
            "processingPlan": planned_pipeline,
            "summaryNode": summary_node.model_dump(by_alias=True, mode="json"),
        }


plugin = MultimodalMemoryModule()


def ingest_asset_tool(payload: dict[str, object]) -> dict[str, object]:
    return plugin.ingest_asset(payload)