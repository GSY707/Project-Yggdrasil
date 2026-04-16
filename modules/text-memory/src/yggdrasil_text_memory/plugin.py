from __future__ import annotations

from collections import defaultdict
from pathlib import Path
import re
from typing import Any

from yggdrasil_sdk.contracts import EventEnvelope, EventHandlingResult, ModuleEventEmission
from yggdrasil_sdk.hooks import HookNames
from yggdrasil_sdk.module import BaseModulePlugin, HookRegistration
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


def _score_node_for_query(node: dict[str, Any], query_tokens: set[str], seeded_node_ids: set[str]) -> float:
    node_tokens = set(_tokenize(f"{node.get('title', '')} {node.get('content', '')}"))
    overlap = len(node_tokens.intersection(query_tokens))
    seed_bonus = 2.0 if node["id"] in seeded_node_ids else 0.0
    branch_bonus = 0.5 if node.get("rootBranch") == "execution" and query_tokens else 0.0
    return overlap + seed_bonus + branch_bonus + float(node.get("importance", 0.5))


class TextMemoryModule(BaseModulePlugin):
    module_id = "text-memory"

    def manifest_path(self) -> Path:
        return Path(__file__).resolve().parents[2] / "yggdrasil.module.yaml"

    def register_hooks(self) -> tuple[HookRegistration, ...]:
        return (
            HookRegistration(name=HookNames.MODULE_ENABLE_PREFLIGHT, handler=self.enable_preflight),
            HookRegistration(name=HookNames.MODULE_HEALTH_REPORT, handler=self.report_health),
            HookRegistration(name=HookNames.MEMORY_INGEST_PREPROCESS, handler=self.preprocess_import),
            HookRegistration(name=HookNames.MEMORY_INGEST_PLAN_TREE, handler=self.plan_tree),
            HookRegistration(name=HookNames.MEMORY_RETRIEVE_EXPAND, handler=self.expand_retrieval),
            HookRegistration(name=HookNames.MEMORY_WRITE_VALIDATE, handler=self.validate_memory_write),
        )

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
        policy = payload.get("importPolicy") if isinstance(payload.get("importPolicy"), dict) else import_job.get("importPolicy")
        target_chars = int((policy or {}).get("segmentTargetChars") or 320)
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
        seeded_node_ids = {
            str(seed_ref.get("id"))
            for seed_ref in retrieval_request.get("seedNodeRefs", [])
            if isinstance(seed_ref, dict) and seed_ref.get("id")
        }
        max_related_nodes = int(retrieval_request.get("maxRelatedNodes") or 4)
        max_leaf_nodes = int(retrieval_request.get("maxLeafNodes") or 6)

        ranked_nodes = sorted(
            nodes,
            key=lambda node: _score_node_for_query(node, query_tokens, seeded_node_ids),
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
        related_edges = []
        for edge in edges:
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
                f"Top nodes: {summary_titles}."
            ),
            "truncated": truncated,
            "generatedAt": utc_now().isoformat(),
        }

    def validate_memory_write(self, payload: dict[str, object]) -> dict[str, object]:
        candidate_nodes = [node for node in payload.get("candidateNodes", []) if isinstance(node, dict)]
        candidate_edges = [edge for edge in payload.get("candidateEdges", []) if isinstance(edge, dict)]
        if not candidate_nodes:
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
        oversized_nodes = [node for node in candidate_nodes if len(str(node.get("content") or "")) > 240]
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


plugin = TextMemoryModule()