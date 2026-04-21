from __future__ import annotations

from pathlib import Path
import re
from typing import Any

from yggdrasil_sdk.contracts import ToolDescriptor
from yggdrasil_sdk.hooks import HookNames
from yggdrasil_sdk.module import BaseModulePlugin, HookRegistration
from yggdrasil_sdk.persistence import get_persistence_runtime
from yggdrasil_sdk.persistence.constants import DEFAULT_BRANCH_ID, DEFAULT_PROJECT_ID, DEFAULT_SPACE_ID
from yggdrasil_sdk.persistence.repositories import NodeRepository, WorkspaceBootstrapRepository
from yggdrasil_sdk.support import new_id, normalize_excerpt


TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_\-\u4e00-\u9fff]+")


def _tokens(node: dict[str, Any]) -> set[str]:
    return {token.lower() for token in TOKEN_PATTERN.findall(f"{node.get('title', '')} {node.get('content', '')}")}


def _proposed_edges(nodes: list[dict[str, Any]], *, min_overlap_terms: int = 2, max_created_edges: int = 12) -> list[dict[str, Any]]:
    edges: list[dict[str, Any]] = []
    tokens_by_id = {str(node["id"]): _tokens(node) for node in nodes if node.get("id") is not None}
    node_list = [node for node in nodes if node.get("id") is not None]
    for index, left in enumerate(node_list):
        left_tokens = tokens_by_id[str(left["id"])]
        for right in node_list[index + 1 :]:
            overlap = left_tokens.intersection(tokens_by_id[str(right["id"])] )
            if len(overlap) < min_overlap_terms:
                continue
            edges.append(
                {
                    "fromNodeId": str(left["id"]),
                    "toNodeId": str(right["id"]),
                    "relationType": "latent-related",
                    "weight": round(min(1.0, 0.2 + len(overlap) * 0.1), 3),
                    "reason": normalize_excerpt("Shared concepts: " + ", ".join(sorted(overlap)[:5]), 160),
                }
            )
            if len(edges) >= max_created_edges:
                return edges
    return edges


class RelationDiscoveryModule(BaseModulePlugin):
    module_id = "relation-discovery"

    def manifest_path(self) -> Path:
        return Path(__file__).resolve().parents[2] / "yggdrasil.module.yaml"

    def register_hooks(self) -> tuple[HookRegistration, ...]:
        return (
            HookRegistration(name=HookNames.MODULE_ENABLE_PREFLIGHT, handler=self.enable_preflight),
            HookRegistration(name=HookNames.MODULE_HEALTH_REPORT, handler=self.report_health),
            HookRegistration(name=HookNames.AGENT_TOOLS_REGISTER, handler=self.register_tools_hook),
            HookRegistration(name=HookNames.MEMORY_INGEST_SUGGEST_LINKS, handler=self.suggest_links),
            HookRegistration(name=HookNames.MEMORY_RETRIEVE_RERANK, handler=self.rerank_retrieval),
        )

    def register_tools(self) -> tuple[dict[str, object], ...]:
        tools = (
            ToolDescriptor(
                name="relation_discovery.scan_branch",
                moduleId=self.module_id,
                version="0.1.0",
                displayName="Scan Branch Relations",
                description="Scan a branch for latent links and materialize missing relation edges.",
                schemaRef="docs/specs/memory-domain-data-spec-v0.1.md",
                executionMode="sync",
                timeoutMs=5000,
                permissionRequired=["node.read", "edge.write"],
                inputSchema={
                    "type": "object",
                    "properties": {
                        "branchId": {"type": "string"},
                        "dryRun": {"type": "boolean"},
                    },
                    "additionalProperties": False,
                },
                implementationRef="yggdrasil_relation_discovery.plugin:scan_branch_relations_tool",
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
        return {"status": "ok", "summary": "Relation Discovery preflight passed."}

    def report_health(self, payload: dict[str, object]) -> dict[str, object]:
        return {
            "status": "healthy",
            "summary": "Relation Discovery is ready to propose links and rerank retrieval bundles.",
        }

    def suggest_links(self, payload: dict[str, object]) -> dict[str, object]:
        nodes = [node for node in payload.get("candidateNodes") or [] if isinstance(node, dict)]
        edges = _proposed_edges(nodes)
        return {
            "candidateEdges": edges,
            "summary": f"Proposed {len(edges)} latent relation edges from candidate nodes.",
        }

    def scan_branch_relations(self, payload: dict[str, object]) -> dict[str, object]:
        execution_context = payload.get("executionContext") if isinstance(payload.get("executionContext"), dict) else {}
        branch_id = str(payload.get("branchId") or execution_context.get("branchId") or DEFAULT_BRANCH_ID)
        dry_run = bool(payload.get("dryRun", False))

        runtime = get_persistence_runtime()
        with runtime.session_scope() as session:
            WorkspaceBootstrapRepository(session).ensure_default_workspace()
            repository = NodeRepository(session)
            nodes = [
                node.model_dump(by_alias=True, mode="json")
                for node in repository.list_nodes(branch_id=branch_id, limit=300)
                if node.node_type != "root"
            ]
            nodes_by_id = {str(node["id"]): node for node in nodes}
            existing_edges = repository.list_edges(branch_id=branch_id, limit=500)
            existing_pairs = {
                tuple(sorted((edge.from_node_id, edge.to_node_id)))
                for edge in existing_edges
            }
            proposals = [
                proposal
                for proposal in _proposed_edges(nodes)
                if tuple(sorted((proposal["fromNodeId"], proposal["toNodeId"]))) not in existing_pairs
            ]
            if dry_run:
                return {
                    "status": "preview",
                    "branchId": branch_id,
                    "proposals": proposals,
                }
            created = []
            for proposal in proposals:
                source_node = nodes_by_id[proposal["fromNodeId"]]
                edge = repository.create_edge(
                    {
                        "projectId": source_node["projectId"],
                        "spaceId": source_node["spaceId"],
                        "branchId": branch_id,
                        "fromNodeId": proposal["fromNodeId"],
                        "toNodeId": proposal["toNodeId"],
                        "relationType": proposal["relationType"],
                        "weight": proposal["weight"],
                        "reason": proposal["reason"],
                        "createdBy": {"type": "module", "id": self.module_id},
                        "updatedBy": {"type": "module", "id": self.module_id},
                    }
                )
                created.append(edge.model_dump(by_alias=True, mode="json"))
        return {
            "status": "created",
            "branchId": branch_id,
            "createdEdges": created,
            "summary": f"Materialized {len(created)} latent relation edges in branch {branch_id}.",
        }

    def rerank_retrieval(self, payload: dict[str, object]) -> dict[str, object]:
        retrieval_bundle = payload.get("retrievalBundle") if isinstance(payload.get("retrievalBundle"), dict) else {}
        node_payloads = [node for node in retrieval_bundle.get("nodePayloads") or [] if isinstance(node, dict)]
        edges = [edge for edge in payload.get("edges") or [] if isinstance(edge, dict)]
        connection_counts: dict[str, int] = {}
        for edge in edges:
            from_node_id = str(edge.get("fromNodeId") or "")
            to_node_id = str(edge.get("toNodeId") or "")
            if from_node_id:
                connection_counts[from_node_id] = connection_counts.get(from_node_id, 0) + 1
            if to_node_id:
                connection_counts[to_node_id] = connection_counts.get(to_node_id, 0) + 1
        reranked = sorted(
            node_payloads,
            key=lambda node: (
                connection_counts.get(str((node.get("ref") or {}).get("id") or node.get("id") or ""), 0),
                len(str(node.get("relatedNames") or [])),
            ),
            reverse=True,
        )
        matched_refs = [node.get("ref") for node in reranked if isinstance(node.get("ref"), dict)]
        top_titles = ", ".join(str(node.get("title") or "") for node in reranked[:3])
        return {
            "matchedNodeRefs": matched_refs,
            "nodePayloads": reranked,
            "naturalLanguageSummary": (
                f"Reranked retrieval bundle using latent graph connectivity. Top linked nodes: {top_titles}."
            ),
        }


plugin = RelationDiscoveryModule()


def scan_branch_relations_tool(payload: dict[str, object]) -> dict[str, object]:
    return plugin.scan_branch_relations(payload)