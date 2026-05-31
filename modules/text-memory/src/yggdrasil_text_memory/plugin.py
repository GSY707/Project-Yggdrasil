from __future__ import annotations
from collections import defaultdict
from pathlib import Path
import re
import time
from typing import Any, Callable
from sqlalchemy.exc import OperationalError
from yggdrasil_sdk.contracts import EventEnvelope, EventHandlingResult, ModuleEventEmission, ToolDescriptor
from yggdrasil_sdk.hook_runtime import collect_hook_results
from yggdrasil_sdk.hooks import HookNames
from yggdrasil_sdk.module import BaseModulePlugin, HookRegistration
from yggdrasil_sdk.persistence import get_persistence_runtime
from yggdrasil_sdk.persistence.constants import DEFAULT_BRANCH_ID
from yggdrasil_sdk.persistence.repositories import NodeRepository, WorkspaceBootstrapRepository
from yggdrasil_sdk.support import new_id, normalize_excerpt, utc_now
STOP_WORDS = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "to",
    "of",
    "is",
    "are",
    "在",
    "的",
    "了",
    "和",
    "是",
    "与",
}
_PLAN_TREE_TARGET_CHARS = 320
_PLAN_TREE_DEPTH = 2
_MAX_RETRIEVAL_LEAF_NODES = 4
_MAX_RETRIEVAL_RELATED_NODES = 4
_SQLITE_LOCK_RETRY_ATTEMPTS = 3
_SQLITE_LOCK_RETRY_BASE_DELAY_SECONDS = 0.15
def _is_sqlite_lock_error(error: Exception) -> bool:
    return "database is locked" in str(error).lower()
def _run_with_sqlite_lock_retry(action: Callable[[], dict[str, object]]) -> dict[str, object]:
    for attempt in range(1, _SQLITE_LOCK_RETRY_ATTEMPTS + 1):
        try:
            return action()
        except OperationalError as error:
            if not _is_sqlite_lock_error(error) or attempt >= _SQLITE_LOCK_RETRY_ATTEMPTS:
                raise
            # SQLite lock in concurrent eval sandboxes is usually transient; short backoff is enough.
            delay_seconds = _SQLITE_LOCK_RETRY_BASE_DELAY_SECONDS * attempt
            time.sleep(delay_seconds)
    raise RuntimeError("unreachable")
def _tokenize(text: str) -> list[str]:
    tokens = re.findall(r"[A-Za-z0-9_\-\u4e00-\u9fff]+", text.lower())
    return [token for token in tokens if token not in STOP_WORDS]
def _derive_title(text: str, fallback: str) -> str:
    first_sentence = re.split(r"[。！？.!?\n]", text, maxsplit=1)[0].strip()
    title = normalize_excerpt(first_sentence or fallback, 48)
    return title or fallback
def _classify_root_branch(text: str) -> str:
    lowered = text.lower()
    if any(keyword in lowered for keyword in ("identity", "role", "persona", "风格", "身份", "偏好")):
        return "identity"
    if any(keyword in lowered for keyword in ("task", "goal", "todo", "计划", "任务", "目标")):
        return "execution"
    return "context"
def _derive_related_hints(text: str, limit: int = 4) -> list[str]:
    hints: list[str] = []
    for token in _tokenize(text):
        if token in hints:
            continue
        hints.append(token)
        if len(hints) >= limit:
            break
    return hints
def _split_source_text(text: str, target_chars: int) -> list[str]:
    paragraphs = [segment.strip() for segment in re.split(r"\n\s*\n", text) if segment.strip()]
    if not paragraphs:
        compact = " ".join(text.split())
        return [compact] if compact else []

    segments: list[str] = []
    current = ""
    for paragraph in paragraphs:
        compact = " ".join(paragraph.split())
        if not compact:
            continue
        if len(compact) > target_chars * 1.4:
            sentences = [piece.strip() for piece in re.split(r"(?<=[。！？.!?])\s+", compact) if piece.strip()]
        else:
            sentences = [compact]
        for sentence in sentences:
            if not current:
                current = sentence
                continue
            if len(current) + 1 + len(sentence) <= target_chars:
                current = f"{current} {sentence}"
                continue
            segments.append(current)
            current = sentence
    if current:
        segments.append(current)
    return segments
def _normalize_fragment(fragment: dict[str, Any], fallback_import_job_id: str, index: int) -> dict[str, Any]:
    text = str(fragment.get("normalizedText") or fragment.get("text") or "").strip()
    fragment_id = str(fragment.get("id") or new_id("frag", fallback_import_job_id, index, stable=True))
    raw_ref = fragment.get("rawRef") if isinstance(fragment.get("rawRef"), dict) else None
    related_hints = fragment.get("relatedHints") if isinstance(fragment.get("relatedHints"), list) else []
    return {
        "id": fragment_id,
        "text": text,
        "rawRef": raw_ref,
        "relatedHints": [str(hint) for hint in related_hints],
        "approxTokens": int(fragment.get("approxTokens") or max(len(text) // 4, 1)),
    }
def _build_edge_candidates(nodes: list[dict[str, Any]], project_id: str, space_id: str, branch_id: str) -> list[dict[str, Any]]:
    edges: list[dict[str, Any]] = []
    node_tokens = {node["id"]: set(_tokenize(f"{node['title']} {node['content']}")) for node in nodes}

    for index, left_node in enumerate(nodes):
        left_tokens = node_tokens[left_node["id"]]
        for right_node in nodes[index + 1 :]:
            shared_tokens = left_tokens.intersection(node_tokens[right_node["id"]])
            if len(shared_tokens) < 2 and left_node["rootBranch"] != right_node["rootBranch"]:
                continue
            relation_type = "related-to"
            if left_node["rootBranch"] == right_node["rootBranch"]:
                relation_type = "same-root-context"
            weight = min(1.0, 0.2 + 0.1 * len(shared_tokens))
            edges.append(
                {
                    "id": new_id("edge", left_node["id"], right_node["id"], stable=True),
                    "projectId": project_id,
                    "spaceId": space_id,
                    "branchId": branch_id,
                    "fromNodeId": left_node["id"],
                    "toNodeId": right_node["id"],
                    "relationType": relation_type,
                    "weight": round(weight, 3),
                    "reason": normalize_excerpt(
                        f"Shared concepts: {', '.join(sorted(shared_tokens)[:4])}" if shared_tokens else "Related by root branch.",
                        180,
                    ),
                    "evidenceAnnotationIds": [],
                    "status": "active",
                    "createdAt": utc_now().isoformat(),
                    "createdBy": {"type": "module", "id": "text-memory"},
                    "updatedAt": utc_now().isoformat(),
                    "updatedBy": {"type": "module", "id": "text-memory"},
                }
            )
    return edges
def _score_node_for_query(
    node: dict[str, Any],
    query_tokens: set[str],
    seeded_node_ids: set[str],
    *,
    reverse_trace_mode: bool,
    work_tree_node_id: str | None,
) -> float:
    node_tokens = set(_tokenize(f"{node.get('title', '')} {node.get('content', '')}"))
    overlap = len(node_tokens.intersection(query_tokens))
    seed_bonus = 2.0 if node["id"] in seeded_node_ids else 0.0
    branch_bonus = 0.5 if node.get("rootBranch") == "execution" and query_tokens else 0.0
    source_work_tree_node_id = str(node.get("sourceWorkTreeNodeId") or "").strip() or None
    work_tree_bonus = 0.0
    if work_tree_node_id is not None and source_work_tree_node_id == work_tree_node_id:
        work_tree_bonus = 3.0 if reverse_trace_mode else 1.5
    return overlap + seed_bonus + branch_bonus + work_tree_bonus + float(node.get("importance", 0.5))
class TextMemoryModule(BaseModulePlugin):
    module_id = "text-memory"

    def manifest_path(self) -> Path:
        return Path(__file__).resolve().parents[2] / "yggdrasil.module.yaml"

    def register_hooks(self) -> tuple[HookRegistration, ...]:
        return (
            HookRegistration(name=HookNames.MODULE_ENABLE_PREFLIGHT, handler=self.enable_preflight),
            HookRegistration(name=HookNames.MODULE_HEALTH_REPORT, handler=self.report_health),
            HookRegistration(name=HookNames.AGENT_TOOLS_REGISTER, handler=self.register_tools_hook),
            HookRegistration(name=HookNames.MEMORY_INGEST_PREPROCESS, handler=self.preprocess_import),
            HookRegistration(name=HookNames.MEMORY_INGEST_PLAN_TREE, handler=self.plan_tree),
            HookRegistration(name=HookNames.MEMORY_RETRIEVE_EXPAND, handler=self.expand_retrieval),
            HookRegistration(name=HookNames.MEMORY_WRITE_VALIDATE, handler=self.validate_memory_write),
        )

    def register_tools(self) -> tuple[dict[str, object], ...]:
        tools = (
            ToolDescriptor(
                name="text_memory.retrieve",
                moduleId=self.module_id,
                version="0.1.0",
                displayName="Retrieve Durable Memory Context",
                description="Search the current branch memory graph and return grounded nodes, related links, and a natural language retrieval summary.",
                schemaRef="docs/specs/memory-domain-data-spec-v0.1.md",
                executionMode="sync",
                timeoutMs=5000,
                permissionRequired=["memory.read"],
                inputSchema={
                    "type": "object",
                    "properties": {
                        "queryText": {"type": "string"},
                        "maxLeafNodes": {"type": "integer", "minimum": 1, "maximum": 8, "default": 4},
                        "maxRelatedNodes": {"type": "integer", "minimum": 0, "maximum": 8, "default": 4},
                        "tokenBudget": {"type": "integer", "minimum": 32},
                    },
                    "required": ["queryText"],
                    "additionalProperties": False,
                },
                implementationRef="yggdrasil_text_memory.plugin:retrieve_memory_tool",
            ),
            ToolDescriptor(
                name="text_memory.read_node",
                moduleId=self.module_id,
                version="0.1.0",
                displayName="Read Memory Node",
                description="Read a durable memory node, its latest version pointer, and optionally recent version history.",
                schemaRef="docs/specs/memory-domain-data-spec-v0.1.md",
                executionMode="sync",
                timeoutMs=4000,
                permissionRequired=["memory.read"],
                inputSchema={
                    "type": "object",
                    "properties": {
                        "nodeId": {"type": "string"},
                        "includeVersions": {"type": "boolean", "default": False},
                        "versionLimit": {"type": "integer", "minimum": 1, "maximum": 20, "default": 5},
                    },
                    "required": ["nodeId"],
                    "additionalProperties": False,
                },
                implementationRef="yggdrasil_text_memory.plugin:read_memory_node_tool",
            ),
            ToolDescriptor(
                name="text_memory.read_index",
                moduleId=self.module_id,
                version="0.1.0",
                displayName="Read Memory Index",
                description="List durable memory nodes for the current branch with lightweight filtering for LLM-visible navigation.",
                schemaRef="docs/specs/memory-domain-data-spec-v0.1.md",
                executionMode="sync",
                timeoutMs=4000,
                permissionRequired=["memory.read"],
                inputSchema={
                    "type": "object",
                    "properties": {
                        "queryText": {"type": "string"},
                        "rootBranch": {"type": "string"},
                        "nodeType": {"type": "string"},
                        "includeArchived": {"type": "boolean", "default": False},
                        "limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 12},
                    },
                    "additionalProperties": False,
                },
                implementationRef="yggdrasil_text_memory.plugin:read_memory_index_tool",
            ),
            ToolDescriptor(
                name="text_memory.update_memory_with_version",
                moduleId=self.module_id,
                version="0.1.0",
                displayName="Update Memory With Version Guard",
                description="Update or relate a memory node only when the caller still holds the latest version pointer; otherwise return a structured conflict payload.",
                schemaRef="docs/specs/memory-domain-data-spec-v0.1.md",
                executionMode="sync",
                timeoutMs=5000,
                permissionRequired=["memory.write"],
                inputSchema={
                    "type": "object",
                    "properties": {
                        "nodeId": {"type": "string"},
                        "expectedLatestVersionId": {"type": "string"},
                        "mode": {"type": "string", "enum": ["write", "revise", "relate"], "default": "revise"},
                        "title": {"type": "string"},
                        "content": {"type": "string"},
                        "relatedNodeId": {"type": "string"},
                        "relationType": {"type": "string"},
                        "reason": {"type": "string"},
                        "changeReason": {"type": "string"},
                    },
                    "required": ["nodeId", "expectedLatestVersionId"],
                    "additionalProperties": False,
                },
                implementationRef="yggdrasil_text_memory.plugin:update_memory_with_version_tool",
            ),
            ToolDescriptor(
                name="text_memory.append_memory_log",
                moduleId=self.module_id,
                version="0.1.0",
                displayName="Append Memory Log",
                description="Append an additive log entry to an existing memory node without requiring the caller to win the latest-version race.",
                schemaRef="docs/specs/memory-domain-data-spec-v0.1.md",
                executionMode="sync",
                timeoutMs=5000,
                permissionRequired=["memory.write"],
                inputSchema={
                    "type": "object",
                    "properties": {
                        "nodeId": {"type": "string"},
                        "logEntry": {"type": "string"},
                        "changeReason": {"type": "string"},
                    },
                    "required": ["nodeId", "logEntry"],
                    "additionalProperties": False,
                },
                implementationRef="yggdrasil_text_memory.plugin:append_memory_log_tool",
            ),
            ToolDescriptor(
                name="text_memory.submit_memory_proposal",
                moduleId=self.module_id,
                version="0.1.0",
                displayName="Submit Memory Proposal",
                description="Create a merge proposal child node when a durable memory change is too risky to apply directly.",
                schemaRef="docs/specs/memory-domain-data-spec-v0.1.md",
                executionMode="sync",
                timeoutMs=5000,
                permissionRequired=["memory.write"],
                inputSchema={
                    "type": "object",
                    "properties": {
                        "nodeId": {"type": "string"},
                        "title": {"type": "string"},
                        "proposal": {"type": "string"},
                        "rationale": {"type": "string"},
                    },
                    "required": ["nodeId", "proposal"],
                    "additionalProperties": False,
                },
                implementationRef="yggdrasil_text_memory.plugin:submit_memory_proposal_tool",
            ),
            ToolDescriptor(
                name="text_memory.forget_node",
                moduleId=self.module_id,
                version="0.1.0",
                displayName="Forget Memory Node",
                description="Soft-forget a memory node by archiving it while preserving version history and optional merge target metadata.",
                schemaRef="docs/specs/memory-domain-data-spec-v0.1.md",
                executionMode="sync",
                timeoutMs=5000,
                permissionRequired=["memory.write"],
                inputSchema={
                    "type": "object",
                    "properties": {
                        "nodeId": {"type": "string"},
                        "reason": {"type": "string"},
                        "status": {"type": "string", "enum": ["archived", "merged", "temporary"], "default": "archived"},
                        "mergedIntoNodeId": {"type": "string"},
                    },
                    "required": ["nodeId"],
                    "additionalProperties": False,
                },
                implementationRef="yggdrasil_text_memory.plugin:forget_memory_node_tool",
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
        install = payload.get("install") if isinstance(payload.get("install"), dict) else {}
        if str(install.get("runtimeMode") or "") != "in-process":
            return {"status": "error", "summary": "Text Memory requires in-process runtime mode."}
        return {"status": "ok", "summary": "Text Memory preflight passed."}

    def report_health(self, payload: dict[str, object]) -> dict[str, object]:
        return {
            "status": "healthy",
            "summary": "Text Memory is ready to plan imports and expand retrieval context.",
        }

    def preprocess_import(self, payload: dict[str, object]) -> dict[str, object]:
        import_job = payload.get("importJob") if isinstance(payload.get("importJob"), dict) else {}
        import_policy = payload.get("importPolicy") if isinstance(payload.get("importPolicy"), dict) else {}
        target_chars = int(import_policy.get("segmentTargetChars") or _PLAN_TREE_TARGET_CHARS)
        raw_ref = payload.get("rawRef") if isinstance(payload.get("rawRef"), dict) else None
        ordered_fragments = payload.get("orderedFragments") if isinstance(payload.get("orderedFragments"), list) else None
        if ordered_fragments:
            normalized_fragments = [
                _normalize_fragment(fragment, str(import_job.get("id") or new_id("import", self.module_id)), index)
                for index, fragment in enumerate(ordered_fragments)
                if isinstance(fragment, dict)
            ]
            return {
                "status": "ok",
                "orderedFragments": normalized_fragments,
                "fragmentCount": len(normalized_fragments),
            }

        source_texts: list[str] = []
        if payload.get("sourceText") is not None:
            source_texts.append(str(payload.get("sourceText") or ""))
        if isinstance(payload.get("sourceTexts"), list):
            source_texts.extend(str(item or "") for item in payload["sourceTexts"])
        if not source_texts:
            return {"status": "error", "summary": "No sourceText or sourceTexts provided for import preprocessing."}

        import_job_id = str(import_job.get("id") or new_id("import", self.module_id))
        fragments: list[dict[str, Any]] = []
        ordinal = 0
        for text_index, source_text in enumerate(source_texts, start=1):
            for segment in _split_source_text(source_text, target_chars):
                ordinal += 1
                fragments.append(
                    {
                        "id": new_id("frag", import_job_id, ordinal, stable=True),
                        "ordinal": ordinal,
                        "rawRef": raw_ref
                        or {
                            "type": "package-entry",
                            "locator": f"core-api/memory/import-jobs/{import_job_id}/sources/{text_index}#fragment-{ordinal}",
                        },
                        "normalizedText": segment,
                        "approxTokens": max(len(segment) // 4, 1),
                        "relatedHints": _derive_related_hints(segment),
                    }
                )
        return {
            "status": "ok",
            "orderedFragments": fragments,
            "fragmentCount": len(fragments),
        }

    def plan_tree(self, payload: dict[str, object]) -> dict[str, object]:
        import_job = payload.get("importJob") if isinstance(payload.get("importJob"), dict) else {}
        import_job_id = str(import_job.get("id", new_id("import", self.module_id)))
        project_id = str(import_job.get("projectId", "project_default"))
        space_id = str(import_job.get("spaceId", "space_default"))
        branch_id = str(import_job.get("branchId", "branch_main"))
        ordered_fragments = payload.get("orderedFragments") if isinstance(payload.get("orderedFragments"), list) else []
        normalized_fragments = [
            _normalize_fragment(fragment, import_job_id, index)
            for index, fragment in enumerate(ordered_fragments)
            if isinstance(fragment, dict)
        ]

        candidate_nodes: list[dict[str, Any]] = []
        candidate_parents: list[dict[str, Any]] = []
        candidate_annotations: list[dict[str, Any]] = []
        discarded_fragment_refs: list[str] = []

        for index, fragment in enumerate(normalized_fragments):
            if len(fragment["text"]) < 12:
                discarded_fragment_refs.append(fragment["id"])
                continue

            root_branch = _classify_root_branch(fragment["text"])
            node_id = new_id("node", import_job_id, fragment["id"], stable=True)
            version_id = new_id("ver", node_id, stable=True)
            title = _derive_title(fragment["text"], f"Fragment {index + 1}")
            content = normalize_excerpt(fragment["text"], 200)
            parent_ref = {
                "kind": "node",
                "id": new_id("node", project_id, branch_id, root_branch, stable=True),
            }
            candidate_nodes.append(
                {
                    "id": node_id,
                    "projectId": project_id,
                    "spaceId": space_id,
                    "branchId": branch_id,
                    "parentId": parent_ref["id"],
                    "rootBranch": root_branch,
                    "nodeType": "detail" if index else "summary",
                    "status": "temporary",
                    "title": title,
                    "content": content,
                    "detailLevel": min(9, 2 + index),
                    "importance": round(min(1.0, 0.45 + len(fragment["text"]) / 300), 3),
                    "stability": 0.55,
                    "forgetRate": 0.2,
                    "feedforwardScore": 0.5,
                    "accessScore": 0.1,
                    "activityK": 0.4,
                    "floatScore": 0.3,
                    "latestVersionId": version_id,
                    "mergedIntoNodeId": None,
                    "childrenCount": 0,
                    "edgeCount": 0,
                    "createdAt": utc_now().isoformat(),
                    "createdBy": {"type": "module", "id": self.module_id},
                    "updatedAt": utc_now().isoformat(),
                    "updatedBy": {"type": "module", "id": self.module_id},
                }
            )
            candidate_parents.append(
                {
                    "fragmentId": fragment["id"],
                    "candidateNodeId": node_id,
                    "parentRef": parent_ref,
                    "rootBranch": root_branch,
                }
            )
            if fragment["rawRef"]:
                candidate_annotations.append(
                    {
                        "id": new_id("srcann", node_id, stable=True),
                        "projectId": project_id,
                        "branchId": branch_id,
                        "ownerKind": "node",
                        "ownerId": node_id,
                        "sourceType": "external",
                        "sourceRef": fragment["rawRef"],
                        "excerpt": normalize_excerpt(fragment["text"], 240),
                        "inferenceSummary": None,
                        "evidenceRefs": [{"kind": "import-fragment", "id": fragment["id"]}],
                        "confidence": 0.92,
                        "createdAt": utc_now().isoformat(),
                        "createdBy": {"type": "module", "id": self.module_id},
                    }
                )

        candidate_edges = _build_edge_candidates(candidate_nodes, project_id, space_id, branch_id)
        confidence = 0.0
        if normalized_fragments:
            confidence = round((len(candidate_nodes) + len(candidate_edges) * 0.25) / len(normalized_fragments), 3)

        return {
            "candidateParents": candidate_parents,
            "candidateNodes": candidate_nodes,
            "candidateEdges": candidate_edges,
            "candidateSourceAnnotations": candidate_annotations,
            "discardedFragmentRefs": discarded_fragment_refs,
            "nodeCount": len(candidate_nodes),
            "depth": _PLAN_TREE_DEPTH,
            "confidence": min(1.0, confidence),
            "rationale": (
                f"Generated {len(candidate_nodes)} candidate nodes from {len(normalized_fragments)} fragments "
                f"with {len(candidate_edges)} link proposals."
            ),
        }

    def expand_retrieval(self, payload: dict[str, object]) -> dict[str, object]:
        retrieval_request = payload.get("retrievalRequest") if isinstance(payload.get("retrievalRequest"), dict) else payload
        nodes = [node for node in payload.get("nodes", payload.get("candidateNodes", [])) if isinstance(node, dict)]
        edges = [edge for edge in payload.get("edges", payload.get("candidateEdges", [])) if isinstance(edge, dict)]
        source_annotations = [
            annotation
            for annotation in payload.get("sourceAnnotations", payload.get("candidateSourceAnnotations", []))
            if isinstance(annotation, dict)
        ]

        if not nodes:
            request_id = str(retrieval_request.get("id", new_id("retr", self.module_id)))
            return {
                "requestId": request_id,
                "matchedNodeRefs": [],
                "nodePayloads": [],
                "childNameMap": {},
                "relatedNameMap": {},
                "sourceAnnotationRefs": [],
                "naturalLanguageSummary": "No nodes were available for retrieval.",
                "truncated": False,
                "generatedAt": utc_now().isoformat(),
            }

        query_text = str(retrieval_request.get("queryText") or "")
        query_tokens = set(_tokenize(query_text))
        reverse_trace_mode = bool(retrieval_request.get("reverseTraceMode", False))
        work_tree_node_id = str(retrieval_request.get("workTreeNodeId") or "").strip() or None
        seeded_node_ids = {
            str(seed_ref.get("id"))
            for seed_ref in retrieval_request.get("seedNodeRefs", [])
            if isinstance(seed_ref, dict) and seed_ref.get("id")
        }
        max_related_nodes = min(max(int(retrieval_request.get("maxRelatedNodes") or _MAX_RETRIEVAL_RELATED_NODES), 0), _MAX_RETRIEVAL_RELATED_NODES)
        max_leaf_nodes = min(max(int(retrieval_request.get("maxLeafNodes") or _MAX_RETRIEVAL_LEAF_NODES), 1), _MAX_RETRIEVAL_LEAF_NODES)

        ranked_nodes = sorted(
            nodes,
            key=lambda node: _score_node_for_query(
                node,
                query_tokens,
                seeded_node_ids,
                reverse_trace_mode=reverse_trace_mode,
                work_tree_node_id=work_tree_node_id,
            ),
            reverse=True,
        )
        matched_nodes = ranked_nodes[:max_leaf_nodes]
        matched_node_ids = {node["id"] for node in matched_nodes}
        node_by_id = {node["id"]: node for node in nodes}

        child_name_map: dict[str, list[str]] = defaultdict(list)
        for node in nodes:
            parent_id = node.get("parentId")
            if parent_id in matched_node_ids:
                child_name_map[parent_id].append(str(node.get("title")))

        related_name_map: dict[str, list[str]] = defaultdict(list)
        related_edges: list[dict[str, Any]] = []
        sorted_edges = sorted(
            edges,
            key=lambda edge: (
                0
                if work_tree_node_id
                and (
                    str(node_by_id.get(str(edge.get("fromNodeId")), {}).get("sourceWorkTreeNodeId") or "").strip() == work_tree_node_id
                    or str(node_by_id.get(str(edge.get("toNodeId")), {}).get("sourceWorkTreeNodeId") or "").strip() == work_tree_node_id
                )
                else 1,
                -float(edge.get("weight", 0.0)),
                str(edge.get("id") or ""),
            ),
        )
        for edge in sorted_edges:
            from_node_id = edge.get("fromNodeId")
            to_node_id = edge.get("toNodeId")
            if from_node_id in matched_node_ids and to_node_id in node_by_id and len(related_edges) < max_related_nodes:
                related_edges.append(edge)
                related_name_map[from_node_id].append(str(node_by_id[to_node_id].get("title")))
            if to_node_id in matched_node_ids and from_node_id in node_by_id and len(related_edges) < max_related_nodes:
                related_edges.append(edge)
                related_name_map[to_node_id].append(str(node_by_id[from_node_id].get("title")))

        matched_annotations = [
            annotation["id"]
            for annotation in source_annotations
            if annotation.get("ownerId") in matched_node_ids
        ]
        node_payloads = [
            {
                "ref": {"kind": "node", "id": node["id"]},
                "title": node.get("title"),
                "content": node.get("content"),
                "rootBranch": node.get("rootBranch"),
                "detailLevel": node.get("detailLevel"),
                "childNames": child_name_map.get(node["id"], []),
                "relatedNames": related_name_map.get(node["id"], []),
            }
            for node in matched_nodes
        ]

        summary_titles = ", ".join(node.get("title", "") for node in matched_nodes[:3])
        request_id = str(retrieval_request.get("id", new_id("retr", query_text or self.module_id)))
        estimated_tokens = sum(len(str(payload_item.get("content", ""))) // 4 for payload_item in node_payloads)
        token_budget = retrieval_request.get("tokenBudget")
        truncated = bool(token_budget) and estimated_tokens > int(token_budget)

        return {
            "requestId": request_id,
            "matchedNodeRefs": [{"kind": "node", "id": node["id"]} for node in matched_nodes],
            "nodePayloads": node_payloads,
            "childNameMap": dict(child_name_map),
            "relatedNameMap": dict(related_name_map),
            "sourceAnnotationRefs": matched_annotations,
            "naturalLanguageSummary": (
                f"Retrieved {len(matched_nodes)} nodes for query '{query_text or 'seeded retrieval'}'. "
                f"Top nodes: {summary_titles}. "
                f"Bounded expansion kept at most {max_leaf_nodes} nodes and {max_related_nodes} related links."
                + (
                    f" Reverse trace anchored at work tree node {work_tree_node_id}."
                    if reverse_trace_mode and work_tree_node_id is not None
                    else ""
                )
            ),
            "truncated": truncated,
            "generatedAt": utc_now().isoformat(),
        }

    def validate_memory_write(self, payload: dict[str, object]) -> dict[str, object]:
        candidate_nodes = [node for node in payload.get("candidateNodes", []) if isinstance(node, dict)]
        candidate_edges = [edge for edge in payload.get("candidateEdges", []) if isinstance(edge, dict)]
        if not candidate_nodes:
            node_payload = payload.get("nodePayload") if isinstance(payload.get("nodePayload"), dict) else None
            if node_payload is not None:
                title = str(node_payload.get("title") or "").strip()
                content = str(node_payload.get("content") or "").strip()
                if not title or not content:
                    return {"status": "error", "summary": "Runtime write payload must include both title and content."}
                return {"status": "ok", "summary": "Validated runtime write payload for durable materialization."}
            return {"status": "error", "summary": "Tree plan does not contain any candidate nodes."}
        node_ids = {str(node.get("id")) for node in candidate_nodes if node.get("id")}
        invalid_edges = [
            edge
            for edge in candidate_edges
            if str(edge.get("fromNodeId")) not in node_ids or str(edge.get("toNodeId")) not in node_ids
        ]
        if invalid_edges:
            return {
                "status": "error",
                "summary": f"Tree plan contains {len(invalid_edges)} edges referencing unknown nodes.",
            }
        oversized_nodes = [
            node
            for node in candidate_nodes
            if len(str(node.get("content") or "")) > 240
            and str(node.get("rootBranch") or "") != "execution"
            and str(node.get("nodeType") or "") != "task"
        ]
        if oversized_nodes:
            return {
                "status": "error",
                "summary": f"Tree plan contains {len(oversized_nodes)} nodes whose content exceeds the allowed bound.",
            }
        return {
            "status": "ok",
            "summary": f"Validated {len(candidate_nodes)} nodes and {len(candidate_edges)} edges for durable materialization.",
        }

    def handle_event(self, envelope: EventEnvelope) -> EventHandlingResult:
        if envelope.event_type != "import.accepted":
            return EventHandlingResult(
                status="ignored",
                handled=False,
                summary=f"Event {envelope.event_type} is not handled by {self.module_id}.",
            )

        import_job = envelope.payload.get("importJob") if isinstance(envelope.payload.get("importJob"), dict) else {}
        aggregate_id = str(import_job.get("id") or envelope.task_id or new_id("import", envelope.event_id, stable=True))
        plan_payload = self.plan_tree(envelope.payload)
        plan_payload["importJob"] = import_job
        emission = ModuleEventEmission(
            aggregateType="import-job",
            aggregateId=aggregate_id,
            eventType="memory.tree.plan.proposed",
            payload=plan_payload,
            projectId=envelope.project_id,
            spaceId=envelope.space_id,
            branchId=envelope.branch_id,
            taskId=envelope.task_id,
            correlationId=envelope.correlation_id,
            causationId=envelope.event_id,
            source=self.module_id,
        )
        return EventHandlingResult(
            status="handled",
            handled=True,
            summary="Generated memory tree plan for accepted import.",
            emittedEvents=[emission],
            healthStatus="healthy",
        )
def _memory_tool_actor(execution_context: dict[str, Any]) -> dict[str, str]:
    run_id = str(execution_context.get("runId") or "").strip()
    if run_id:
        return {"type": "agent", "id": run_id}
    return {"type": "module", "id": "text-memory"}
def _memory_source_work_tree_node_id(execution_context: dict[str, Any]) -> str | None:
    direct_value = str(execution_context.get("sourceWorkTreeNodeId") or "").strip()
    if direct_value:
        return direct_value
    root_mount = execution_context.get("rootMount") if isinstance(execution_context.get("rootMount"), dict) else {}
    direct_root_mount_value = str(root_mount.get("currentNodeId") or "").strip()
    if direct_root_mount_value:
        return direct_root_mount_value
    takeover_protocol = root_mount.get("takeoverProtocol") if isinstance(root_mount.get("takeoverProtocol"), dict) else {}
    work_tree = takeover_protocol.get("workTree") if isinstance(takeover_protocol.get("workTree"), dict) else {}
    work_tree_value = str(work_tree.get("currentNodeId") or "").strip()
    return work_tree_value or None
def _memory_node_payload(node: Any) -> dict[str, Any]:
    return node.model_dump(by_alias=True, mode="json")
def _memory_version_payload(version: Any) -> dict[str, Any]:
    return version.model_dump(by_alias=True, mode="json")
def read_memory_node_tool(payload: dict[str, object]) -> dict[str, object]:
    raw_node_id = payload.get("nodeId")
    node_id = "" if isinstance(raw_node_id, (dict, list, tuple, set)) else str(raw_node_id or "").strip()
    if node_id in {"{}", "[]"}:
        node_id = ""
    fallback_selected = False
    if not node_id:
        fallback_candidates = read_memory_index_tool(
            {
                "executionContext": payload.get("executionContext") if isinstance(payload.get("executionContext"), dict) else {},
                "branchId": payload.get("branchId"),
                "rootBranch": payload.get("rootBranch"),
                "nodeType": payload.get("nodeType"),
                "includeArchived": False,
                "limit": 1,
            }
        )
        nodes = fallback_candidates.get("nodes") if isinstance(fallback_candidates, dict) else []
        first_node = nodes[0] if isinstance(nodes, list) and nodes else None
        if isinstance(first_node, dict):
            node_id = str(first_node.get("id") or "").strip()
            fallback_selected = bool(node_id)
    if not node_id:
        raise KeyError("nodeId")
    include_versions = bool(payload.get("includeVersions"))
    version_limit = min(max(int(payload.get("versionLimit") or 5), 1), 20)

    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        node_repository = NodeRepository(session)
        node = node_repository.get_node(node_id)
        if node is None:
            raise KeyError(f"Node {node_id} not found.")
        versions = node_repository.list_versions(node_id, limit=version_limit if include_versions else 1)

    latest_version = versions[-1] if versions else None
    return {
        "node": _memory_node_payload(node),
        "latestVersionId": node.latest_version_id,
        "latestVersion": _memory_version_payload(latest_version) if latest_version is not None else None,
        "versions": [_memory_version_payload(version) for version in versions] if include_versions else [],
        "fallbackNodeSelected": fallback_selected,
        "summary": normalize_excerpt(
            f"Read memory node {node.title} with latest version {node.latest_version_id}.",
            160,
        ),
    }
def read_memory_index_tool(payload: dict[str, object]) -> dict[str, object]:
    execution_context = payload.get("executionContext") if isinstance(payload.get("executionContext"), dict) else {}
    branch_id = str(payload.get("branchId") or execution_context.get("branchId") or DEFAULT_BRANCH_ID)
    root_branch_filter = str(payload.get("rootBranch") or "").strip() or None
    node_type_filter = str(payload.get("nodeType") or "").strip() or None
    query_text = str(payload.get("queryText") or "").strip()
    query_tokens = set(_tokenize(query_text)) if query_text else set()
    include_archived = bool(payload.get("includeArchived"))
    limit = min(max(int(payload.get("limit") or 12), 1), 50)

    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        node_repository = NodeRepository(session)
        nodes = [
            node
            for node in node_repository.list_nodes(branch_id=branch_id, limit=max(limit * 4, 100))
            if node.node_type != "root"
        ]

    filtered_nodes = []
    for node in nodes:
        if root_branch_filter and node.root_branch != root_branch_filter:
            continue
        if node_type_filter and node.node_type != node_type_filter:
            continue
        if not include_archived and node.status == "archived":
            continue
        if query_tokens:
            node_tokens = set(_tokenize(f"{node.title} {node.content}"))
            if not (query_tokens & node_tokens):
                continue
        filtered_nodes.append(node)

    ranked_nodes = sorted(
        filtered_nodes,
        key=lambda node: (
            -float(node.importance),
            -int(node.detail_level),
            str(node.title or ""),
        ),
    )[:limit]

    return {
        "nodes": [
            {
                "id": node.id,
                "title": node.title,
                "rootBranch": node.root_branch,
                "nodeType": node.node_type,
                "status": node.status,
                "latestVersionId": node.latest_version_id,
                "sourceWorkTreeNodeId": node.source_work_tree_node_id,
            }
            for node in ranked_nodes
        ],
        "count": len(ranked_nodes),
        "summary": normalize_excerpt(
            f"Listed {len(ranked_nodes)} memory nodes from branch {branch_id}.",
            160,
        ),
    }
def update_memory_with_version_tool(payload: dict[str, object]) -> dict[str, object]:
    execution_context = payload.get("executionContext") if isinstance(payload.get("executionContext"), dict) else {}
    node_id = str(payload.get("nodeId") or "").strip()
    expected_latest_version_id = str(payload.get("expectedLatestVersionId") or "").strip()
    if not node_id:
        raise KeyError("nodeId")
    if not expected_latest_version_id:
        raise KeyError("expectedLatestVersionId")
    mode = str(payload.get("mode") or "revise").strip().lower()
    if mode not in {"write", "revise", "relate"}:
        raise ValueError(f"Unsupported mode: {mode}")

    actor = _memory_tool_actor(execution_context)
    source_work_tree_node_id = _memory_source_work_tree_node_id(execution_context)

    runtime = get_persistence_runtime()

    def _action() -> dict[str, object]:
        with runtime.session_scope() as session:
            WorkspaceBootstrapRepository(session).ensure_default_workspace()
            node_repository = NodeRepository(session)
            node = node_repository.get_node(node_id)
            if node is None:
                raise KeyError(f"Node {node_id} not found.")
            if node.latest_version_id != expected_latest_version_id:
                recent_versions = node_repository.list_versions(node_id, limit=5)
                return {
                    "status": "conflict",
                    "mode": mode,
                    "node": _memory_node_payload(node),
                    "expectedLatestVersionId": expected_latest_version_id,
                    "currentLatestVersionId": node.latest_version_id,
                    "recentVersions": [_memory_version_payload(version) for version in recent_versions],
                    "recommendedActions": [
                        "text_memory.append_memory_log",
                        "text_memory.submit_memory_proposal",
                    ],
                    "summary": normalize_excerpt(
                        f"Version conflict on node {node.title}; latest pointer moved to {node.latest_version_id}.",
                        180,
                    ),
                }

            if mode == "relate":
                related_node_id = str(payload.get("relatedNodeId") or "").strip()
                if not related_node_id:
                    raise KeyError("relatedNodeId")
                related_node = node_repository.get_node(related_node_id)
                if related_node is None:
                    raise KeyError(f"Node {related_node_id} not found.")
                edge = node_repository.create_edge(
                    {
                        "projectId": node.project_id,
                        "spaceId": node.space_id,
                        "branchId": node.branch_id,
                        "fromNodeId": node.id,
                        "toNodeId": related_node.id,
                        "relationType": str(payload.get("relationType") or "related-to"),
                        "reason": str(payload.get("reason") or f"Linked from memory tool at {source_work_tree_node_id or 'no-work-tree'}"),
                        "createdBy": actor,
                        "updatedBy": actor,
                    }
                )
                return {
                    "status": "updated",
                    "mode": mode,
                    "node": _memory_node_payload(node),
                    "edge": edge.model_dump(by_alias=True, mode="json"),
                    "summary": normalize_excerpt(f"Created relation from {node.title} to {related_node.title}.", 160),
                }

            version_payload: dict[str, Any] = {
                "changeReason": str(payload.get("changeReason") or f"memory-tool-{mode}"),
                "createdBy": actor,
                "updatedBy": actor,
                "sourceWorkTreeNodeId": source_work_tree_node_id,
            }
            if payload.get("title") is not None:
                version_payload["title"] = str(payload.get("title") or "")
            if payload.get("content") is not None:
                version_payload["content"] = str(payload.get("content") or "")
            if "title" not in version_payload and "content" not in version_payload:
                raise ValueError("write/revise mode requires title or content.")

            version = node_repository.append_version(node_id, version_payload)
            updated_node = node_repository.get_node(node_id)
            return {
                "status": "updated",
                "mode": mode,
                "node": _memory_node_payload(updated_node) if updated_node is not None else None,
                "version": _memory_version_payload(version),
                "summary": normalize_excerpt(f"Updated memory node {node.title} via {mode} mode.", 160),
            }

    return _run_with_sqlite_lock_retry(_action)
def append_memory_log_tool(payload: dict[str, object]) -> dict[str, object]:
    execution_context = payload.get("executionContext") if isinstance(payload.get("executionContext"), dict) else {}
    node_id = str(payload.get("nodeId") or "").strip()
    log_entry = str(payload.get("logEntry") or "").strip()
    if not node_id:
        raise KeyError("nodeId")
    if not log_entry:
        raise KeyError("logEntry")

    actor = _memory_tool_actor(execution_context)
    source_work_tree_node_id = _memory_source_work_tree_node_id(execution_context)
    runtime = get_persistence_runtime()

    def _action() -> dict[str, object]:
        with runtime.session_scope() as session:
            WorkspaceBootstrapRepository(session).ensure_default_workspace()
            node_repository = NodeRepository(session)
            version = node_repository.append_memory_log_entry(
                node_id,
                log_entry,
                {
                    "changeReason": str(payload.get("changeReason") or "append-memory-log"),
                    "createdBy": actor,
                    "updatedBy": actor,
                    "sourceWorkTreeNodeId": source_work_tree_node_id,
                },
            )
            updated_node = node_repository.get_node(node_id)
            return {
                "status": "appended",
                "node": _memory_node_payload(updated_node) if updated_node is not None else None,
                "version": _memory_version_payload(version),
                "summary": normalize_excerpt(
                    f"Appended memory log to node {updated_node.title if updated_node is not None else node_id}.",
                    160,
                ),
            }

    return _run_with_sqlite_lock_retry(_action)
def submit_memory_proposal_tool(payload: dict[str, object]) -> dict[str, object]:
    execution_context = payload.get("executionContext") if isinstance(payload.get("executionContext"), dict) else {}
    node_id = str(payload.get("nodeId") or "").strip()
    proposal = str(payload.get("proposal") or "").strip()
    if not node_id:
        raise KeyError("nodeId")
    if not proposal:
        raise KeyError("proposal")

    actor = _memory_tool_actor(execution_context)
    source_work_tree_node_id = _memory_source_work_tree_node_id(execution_context)
    runtime = get_persistence_runtime()

    def _action() -> dict[str, object]:
        with runtime.session_scope() as session:
            WorkspaceBootstrapRepository(session).ensure_default_workspace()
            node_repository = NodeRepository(session)
            node = node_repository.get_node(node_id)
            if node is None:
                raise KeyError(f"Node {node_id} not found.")
            proposal_node = node_repository.create_node(
                {
                    "projectId": node.project_id,
                    "spaceId": node.space_id,
                    "branchId": node.branch_id,
                    "parentId": node.id,
                    "rootBranch": node.root_branch,
                    "nodeType": "task",
                    "status": "temporary",
                    "title": str(payload.get("title") or normalize_excerpt(f"Memory proposal for {node.title}", 72)),
                    "content": "\n".join(
                        part
                        for part in [
                            f"Target node: {node.id}",
                            f"Target latest version: {node.latest_version_id}",
                            f"Proposal: {proposal}",
                            f"Rationale: {str(payload.get('rationale') or '').strip()}" if payload.get("rationale") else None,
                        ]
                        if part
                    ),
                    "sourceWorkTreeNodeId": source_work_tree_node_id,
                    "createdBy": actor,
                    "updatedBy": actor,
                    "changeReason": "memory-proposal",
                }
            )
            return {
                "status": "proposed",
                "proposalNode": _memory_node_payload(proposal_node),
                "targetNodeId": node.id,
                "targetLatestVersionId": node.latest_version_id,
                "summary": normalize_excerpt(f"Created memory proposal under node {node.title}.", 160),
            }

    return _run_with_sqlite_lock_retry(_action)
def forget_memory_node_tool(payload: dict[str, object]) -> dict[str, object]:
    execution_context = payload.get("executionContext") if isinstance(payload.get("executionContext"), dict) else {}
    node_id = str(payload.get("nodeId") or "").strip()
    if not node_id:
        raise KeyError("nodeId")

    actor = _memory_tool_actor(execution_context)
    source_work_tree_node_id = _memory_source_work_tree_node_id(execution_context)
    runtime = get_persistence_runtime()

    def _action() -> dict[str, object]:
        with runtime.session_scope() as session:
            WorkspaceBootstrapRepository(session).ensure_default_workspace()
            node_repository = NodeRepository(session)
            node = node_repository.get_node(node_id)
            if node is None:
                raise KeyError(f"Node {node_id} not found.")
            version = node_repository.append_version(
                node_id,
                {
                    "status": str(payload.get("status") or "archived"),
                    "mergedIntoNodeId": str(payload.get("mergedIntoNodeId")) if payload.get("mergedIntoNodeId") is not None else None,
                    "changeReason": str(payload.get("reason") or "forget-memory-node"),
                    "createdBy": actor,
                    "updatedBy": actor,
                    "sourceWorkTreeNodeId": source_work_tree_node_id,
                },
            )
            updated_node = node_repository.get_node(node_id)
            return {
                "status": "forgotten",
                "node": _memory_node_payload(updated_node) if updated_node is not None else None,
                "version": _memory_version_payload(version),
                "summary": normalize_excerpt(f"Soft-forgot memory node {node.title}.", 160),
            }

    return _run_with_sqlite_lock_retry(_action)
plugin = TextMemoryModule()
def retrieve_memory_tool(payload: dict[str, object]) -> dict[str, object]:
    execution_context = payload.get("executionContext") if isinstance(payload.get("executionContext"), dict) else {}
    branch_id = str(payload.get("branchId") or execution_context.get("branchId") or DEFAULT_BRANCH_ID)
    query_text = str(payload.get("queryText") or "").strip()
    if not query_text:
        raise KeyError("queryText")
    active_capabilities = [
        str(module_id)
        for module_id in execution_context.get("activeCapabilities") or []
        if str(module_id) != plugin.module_id
    ]

    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        node_repository = NodeRepository(session)
        nodes = [
            node.model_dump(by_alias=True, mode="json")
            for node in node_repository.list_nodes(branch_id=branch_id, limit=int(payload.get("nodeScanLimit") or 200))
            if node.node_type != "root"
        ]
        edges = [
            edge.model_dump(by_alias=True, mode="json")
            for edge in node_repository.list_edges(branch_id=branch_id, limit=int(payload.get("edgeScanLimit") or 200))
        ]
        source_annotations = [
            annotation.model_dump(by_alias=True, mode="json")
            for annotation in node_repository.list_source_annotations(branch_id=branch_id, limit=int(payload.get("annotationLimit") or 200))
        ]

    retrieval_request = {
        "id": new_id("retr", branch_id, query_text),
        "queryText": query_text,
        "maxLeafNodes": int(payload.get("maxLeafNodes") or 4),
        "maxRelatedNodes": int(payload.get("maxRelatedNodes") or 4),
        "tokenBudget": int(payload["tokenBudget"]) if payload.get("tokenBudget") is not None else None,
    }
    retrieval_payload = {
        "retrievalRequest": retrieval_request,
        "nodes": nodes,
        "edges": edges,
        "sourceAnnotations": source_annotations,
        "executionContext": execution_context,
    }

    if active_capabilities:
        expansion_results = collect_hook_results(
            HookNames.MEMORY_RETRIEVE_EXPAND,
            retrieval_payload,
            module_ids=active_capabilities,
        )
        nodes_by_id = {str(node.get("id")): node for node in nodes if node.get("id") is not None}
        edges_by_id = {str(edge.get("id")): edge for edge in edges if edge.get("id") is not None}
        annotations_by_id = {
            str(annotation.get("id")): annotation
            for annotation in source_annotations
            if annotation.get("id") is not None
        }
        module_expansions: list[dict[str, object]] = []
        for item in expansion_results:
            if item.get("error"):
                continue
            result = item.get("result") if isinstance(item.get("result"), dict) else {}
            module_expansions.append(
                {
                    "moduleId": item.get("moduleId"),
                    "summary": result.get("summary"),
                }
            )
            for node in result.get("nodes") or []:
                if isinstance(node, dict) and node.get("id") is not None:
                    nodes_by_id[str(node["id"])] = node
            for edge in result.get("edges") or []:
                if isinstance(edge, dict) and edge.get("id") is not None:
                    edges_by_id[str(edge["id"])] = edge
            for annotation in result.get("sourceAnnotations") or []:
                if isinstance(annotation, dict) and annotation.get("id") is not None:
                    annotations_by_id[str(annotation["id"])] = annotation
        retrieval_payload["nodes"] = list(nodes_by_id.values())
        retrieval_payload["edges"] = list(edges_by_id.values())
        retrieval_payload["sourceAnnotations"] = list(annotations_by_id.values())
        retrieval_payload["moduleExpansions"] = module_expansions

    retrieval_bundle = plugin.expand_retrieval(retrieval_payload)
    if active_capabilities:
        rerank_results = collect_hook_results(
            HookNames.MEMORY_RETRIEVE_RERANK,
            {
                **retrieval_payload,
                "retrievalBundle": retrieval_bundle,
            },
            module_ids=active_capabilities,
        )
        for item in rerank_results:
            if item.get("error"):
                continue
            result = item.get("result") if isinstance(item.get("result"), dict) else {}
            if isinstance(result.get("matchedNodeRefs"), list):
                retrieval_bundle["matchedNodeRefs"] = [reference for reference in result["matchedNodeRefs"] if isinstance(reference, dict)]
            if isinstance(result.get("nodePayloads"), list):
                retrieval_bundle["nodePayloads"] = [node for node in result["nodePayloads"] if isinstance(node, dict)]
            if result.get("naturalLanguageSummary"):
                retrieval_bundle["naturalLanguageSummary"] = str(result["naturalLanguageSummary"])
            if isinstance(result.get("relatedNameMap"), dict):
                retrieval_bundle["relatedNameMap"] = dict(result["relatedNameMap"])
    return retrieval_bundle
