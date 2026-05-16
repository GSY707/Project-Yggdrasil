from __future__ import annotations

from fnmatch import fnmatchcase
from pathlib import Path
from typing import Any

from yggdrasil_sdk.contracts import ToolDescriptor
from yggdrasil_sdk.hooks import HookNames
from yggdrasil_sdk.module import BaseModulePlugin, HookRegistration
from yggdrasil_sdk.persistence import get_persistence_runtime
from yggdrasil_sdk.persistence.constants import DEFAULT_BRANCH_ID, DEFAULT_PROJECT_ID, DEFAULT_SPACE_ID
from yggdrasil_sdk.persistence.repositories import CollaborationRepository, NodeRepository, WorkspaceBootstrapRepository
from yggdrasil_sdk.support import normalize_excerpt


def _subject_candidates(payload: dict[str, Any]) -> list[str]:
    candidates: list[str] = []
    explicit = payload.get("subject")
    if explicit is not None:
        candidates.append(str(explicit))
    owner_profile_id = payload.get("ownerProfileId")
    if owner_profile_id is not None:
        candidates.append(f"profile:{owner_profile_id}")
    actor = payload.get("actor")
    if isinstance(actor, dict) and actor.get("id"):
        candidates.append(f"{actor.get('type', 'user')}:{actor['id']}")
    candidates.append("*")
    deduplicated: list[str] = []
    for candidate in candidates:
        if candidate not in deduplicated:
            deduplicated.append(candidate)
    return deduplicated


def _resource_matches(pattern: str, resource: str) -> bool:
    if pattern == "*":
        return True
    if fnmatchcase(resource, pattern):
        return True
    return resource.startswith(f"{pattern}:")


def _condition_matches(condition: dict[str, Any] | None, context: dict[str, Any]) -> bool:
    if not condition:
        return True
    for key, expected in condition.items():
        actual = context.get(key)
        if isinstance(expected, list):
            if actual not in expected:
                return False
            continue
        if expected != actual:
            return False
    return True


def _relation_matches(record_relation: str, requested_relation: str) -> bool:
    return record_relation in {requested_relation, "admin", "*"}


class SharedMemoryModule(BaseModulePlugin):
    module_id = "shared-memory"

    def manifest_path(self) -> Path:
        return Path(__file__).resolve().parents[2] / "yggdrasil.module.yaml"

    def register_hooks(self) -> tuple[HookRegistration, ...]:
        return (
            HookRegistration(name=HookNames.MODULE_ENABLE_PREFLIGHT, handler=self.enable_preflight),
            HookRegistration(name=HookNames.MODULE_HEALTH_REPORT, handler=self.report_health),
            HookRegistration(name=HookNames.AGENT_TOOLS_REGISTER, handler=self.register_tools_hook),
            HookRegistration(name=HookNames.AGENT_STARTUP_MOUNT_ROOT, handler=self.mount_root),
            HookRegistration(name=HookNames.MEMORY_RETRIEVE_EXPAND, handler=self.expand_retrieval),
            HookRegistration(name=HookNames.MEMORY_WRITE_VALIDATE, handler=self.validate_memory_write),
        )

    def register_tools(self) -> tuple[dict[str, object], ...]:
        tools = (
            ToolDescriptor(
                name="shared_memory.describe_mounts",
                moduleId=self.module_id,
                version="0.1.0",
                displayName="Describe Shared Mounts",
                description="Describe mounted spaces, effective access, and candidate shared branches for the current execution context.",
                schemaRef="docs/specs/collaboration-and-governance-data-spec-v0.1.md",
                executionMode="sync",
                timeoutMs=3000,
                permissionRequired=["space.read"],
                inputSchema={
                    "type": "object",
                    "properties": {
                        "spaceId": {"type": "string"},
                        "branchId": {"type": "string"},
                    },
                    "additionalProperties": False,
                },
                implementationRef="yggdrasil_shared_memory.plugin:describe_mounts_tool",
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
            return {"status": "error", "summary": "Shared Memory requires in-process runtime mode."}
        return {"status": "ok", "summary": "Shared Memory preflight passed."}

    def report_health(self, payload: dict[str, object]) -> dict[str, object]:
        return {
            "status": "healthy",
            "summary": "Shared Memory is ready to resolve mounts, permissions, and mounted retrieval context.",
        }

    def _is_allowed(
        self,
        repository: CollaborationRepository,
        *,
        project_id: str,
        subjects: list[str],
        relations: list[str],
        resource: str,
        context: dict[str, Any],
    ) -> bool:
        tuples = repository.list_permission_tuples(project_id=project_id, limit=500)
        matched = []
        for record in tuples:
            if record.subject not in subjects and record.subject != "*":
                continue
            if not any(_relation_matches(record.relation, relation) for relation in relations):
                continue
            if not _resource_matches(record.resource, resource):
                continue
            if not _condition_matches(record.condition, context):
                continue
            matched.append(record)
        if any(record.effect == "deny" for record in matched):
            return False
        if any(record.effect == "allow" for record in matched):
            return True
        return False

    def _resolve_accessible_mounts(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        project_id = str(payload.get("projectId") or DEFAULT_PROJECT_ID)
        host_space_id = str(payload.get("spaceId") or payload.get("hostSpaceId") or DEFAULT_SPACE_ID)
        branch_id = str(payload.get("branchId") or DEFAULT_BRANCH_ID)
        subjects = _subject_candidates(payload)
        runtime = get_persistence_runtime()
        with runtime.session_scope() as session:
            WorkspaceBootstrapRepository(session).ensure_default_workspace()
            collaboration_repository = CollaborationRepository(session)
            node_repository = NodeRepository(session)
            mounts = collaboration_repository.list_space_mounts(
                project_id=project_id,
                host_space_id=host_space_id,
                status="active",
                limit=200,
            )
            accessible: list[dict[str, Any]] = []
            for mount in mounts:
                permission_context = {
                    "branchId": branch_id,
                    "spaceId": mount.mounted_space_id,
                    "mountMode": mount.mount_mode,
                }
                if not self._is_allowed(
                    collaboration_repository,
                    project_id=project_id,
                    subjects=subjects,
                    relations=["mount", "read", "admin"],
                    resource=f"space:{mount.mounted_space_id}",
                    context=permission_context,
                ):
                    continue
                branches = collaboration_repository.list_branches(
                    project_id=project_id,
                    space_id=mount.mounted_space_id,
                    status="active",
                    limit=32,
                )
                mounted_context_refs: list[dict[str, Any]] = []
                for branch in branches:
                    _, context_refs, _ = node_repository.root_mount_refs(project_id, branch.id)
                    mounted_context_refs.extend(reference.model_dump(mode="json") for reference in context_refs)
                accessible.append(
                    {
                        "mountId": mount.id,
                        "hostSpaceId": mount.host_space_id,
                        "mountedSpaceId": mount.mounted_space_id,
                        "mountMode": mount.mount_mode,
                        "branchIds": [branch.id for branch in branches],
                        "mountedNodeRefs": mounted_context_refs,
                    }
                )
        return accessible

    def mount_root(self, payload: dict[str, object]) -> dict[str, object]:
        accessible_mounts = self._resolve_accessible_mounts(dict(payload))
        mounted_refs = [
            reference
            for mount in accessible_mounts
            for reference in mount.get("mountedNodeRefs") or []
            if isinstance(reference, dict)
        ]
        mount_fragments = [
            {
                "moduleId": self.module_id,
                "spaceId": mount["mountedSpaceId"],
                "mountMode": mount["mountMode"],
                "branchIds": mount["branchIds"],
            }
            for mount in accessible_mounts
        ]
        summary = "No shared spaces are mounted for the current subject."
        if accessible_mounts:
            summary = (
                f"Mounted {len(accessible_mounts)} shared spaces with "
                f"{sum(len(mount['branchIds']) for mount in accessible_mounts)} readable branches."
            )
        return {
            "summary": summary,
            "mountFragments": mount_fragments,
            "mountedNodeRefs": mounted_refs,
            "accessibleMounts": accessible_mounts,
        }

    def expand_retrieval(self, payload: dict[str, object]) -> dict[str, object]:
        execution_context = payload.get("executionContext") if isinstance(payload.get("executionContext"), dict) else {}
        context_payload = {
            "projectId": execution_context.get("projectId") or payload.get("projectId") or DEFAULT_PROJECT_ID,
            "spaceId": execution_context.get("rootMount", {}).get("spaceId") if isinstance(execution_context.get("rootMount"), dict) else execution_context.get("spaceId") or payload.get("spaceId") or DEFAULT_SPACE_ID,
            "branchId": execution_context.get("branchId") or payload.get("branchId") or DEFAULT_BRANCH_ID,
            "ownerProfileId": execution_context.get("ownerProfileId") or payload.get("ownerProfileId"),
            "subject": execution_context.get("subject") or payload.get("subject"),
        }
        accessible_mounts = self._resolve_accessible_mounts(context_payload)
        if not accessible_mounts:
            return {"nodes": [], "edges": [], "sourceAnnotations": [], "summary": "No shared mounts expanded retrieval."}

        max_expanded_nodes = 120
        runtime = get_persistence_runtime()
        with runtime.session_scope() as session:
            WorkspaceBootstrapRepository(session).ensure_default_workspace()
            node_repository = NodeRepository(session)
            nodes: list[dict[str, Any]] = []
            edges: list[dict[str, Any]] = []
            annotations: list[dict[str, Any]] = []
            for mount in accessible_mounts:
                for mounted_branch_id in mount["branchIds"]:
                    branch_nodes = [
                        node.model_dump(by_alias=True, mode="json")
                        for node in node_repository.list_nodes(branch_id=mounted_branch_id, limit=max_expanded_nodes)
                        if node.node_type != "root"
                    ]
                    for node in branch_nodes:
                        node["mountMode"] = mount["mountMode"]
                        node["mountedSpaceId"] = mount["mountedSpaceId"]
                        node["mountedBranchId"] = mounted_branch_id
                    nodes.extend(branch_nodes)
                    edges.extend(
                        edge.model_dump(by_alias=True, mode="json")
                        for edge in node_repository.list_edges(branch_id=mounted_branch_id, limit=max_expanded_nodes)
                    )
                    annotations.extend(
                        annotation.model_dump(by_alias=True, mode="json")
                        for annotation in node_repository.list_source_annotations(branch_id=mounted_branch_id, limit=max_expanded_nodes)
                    )
        return {
            "nodes": nodes,
            "edges": edges,
            "sourceAnnotations": annotations,
            "summary": (
                f"Expanded retrieval with {len(nodes)} mounted nodes from "
                f"{len(accessible_mounts)} shared spaces."
            ),
        }

    def validate_memory_write(self, payload: dict[str, object]) -> dict[str, object]:
        project_id = str(payload.get("projectId") or DEFAULT_PROJECT_ID)
        host_space_id = str(payload.get("hostSpaceId") or payload.get("spaceId") or DEFAULT_SPACE_ID)
        target_space_id = str(payload.get("targetSpaceId") or payload.get("spaceId") or DEFAULT_SPACE_ID)
        target_branch_id = str(payload.get("targetBranchId") or payload.get("branchId") or DEFAULT_BRANCH_ID)
        if target_space_id == host_space_id:
            return {"status": "ok", "allowed": True, "summary": "Write remains in the host space."}

        runtime = get_persistence_runtime()
        with runtime.session_scope() as session:
            WorkspaceBootstrapRepository(session).ensure_default_workspace()
            collaboration_repository = CollaborationRepository(session)
            mounts = collaboration_repository.list_space_mounts(
                project_id=project_id,
                host_space_id=host_space_id,
                mounted_space_id=target_space_id,
                status="active",
                limit=10,
            )
            if not mounts:
                return {
                    "status": "deny",
                    "allowed": False,
                    "blockers": ["unmounted-space-target"],
                    "summary": f"Space {target_space_id} is not mounted into host space {host_space_id}.",
                }
            mount = mounts[0]
            if mount.mount_mode == "readonly":
                return {
                    "status": "deny",
                    "allowed": False,
                    "blockers": ["readonly-mount"],
                    "summary": f"Readonly mount blocks writes into {target_space_id}.",
                }
            if mount.mount_mode == "copy-on-write":
                return {
                    "status": "ok",
                    "allowed": True,
                    "targetSpaceId": host_space_id,
                    "targetBranchId": str(payload.get("branchId") or DEFAULT_BRANCH_ID),
                    "annotations": [
                        {
                            "sourceType": "memory",
                            "summary": f"Write was redirected from mounted space {target_space_id} to host space {host_space_id} by copy-on-write policy.",
                            "confidence": 0.94,
                        }
                    ],
                    "summary": f"Copy-on-write redirected the write back to host space {host_space_id}.",
                }

            subjects = _subject_candidates(dict(payload))
            candidate_nodes = [node for node in payload.get("candidateNodes") or [] if isinstance(node, dict)]
            source_work_tree_node_id = str(payload.get("sourceWorkTreeNodeId") or "").strip() or None
            if source_work_tree_node_id is None:
                for candidate_node in candidate_nodes:
                    node_work_tree_id = str(
                        candidate_node.get("sourceWorkTreeNodeId")
                        or candidate_node.get("workTreeNodeId")
                        or ""
                    ).strip()
                    if node_work_tree_id:
                        source_work_tree_node_id = node_work_tree_id
                        break
            permission_context = {
                "branchId": target_branch_id,
                "spaceId": target_space_id,
                "mountMode": mount.mount_mode,
                "sourceWorkTreeNodeId": source_work_tree_node_id,
            }
            if not self._is_allowed(
                collaboration_repository,
                project_id=project_id,
                subjects=subjects,
                relations=["write", "admin"],
                resource=f"space:{target_space_id}",
                context=permission_context,
            ):
                return {
                    "status": "deny",
                    "allowed": False,
                    "blockers": [f"write-denied:{target_space_id}"],
                    "summary": f"Subject cannot write to mounted space {target_space_id}.",
                }

            available_branches = collaboration_repository.list_branches(
                project_id=project_id,
                space_id=target_space_id,
                status="active",
                limit=32,
            )
            if not available_branches:
                return {
                    "status": "deny",
                    "allowed": False,
                    "blockers": ["mounted-space-has-no-branch"],
                    "summary": f"Mounted space {target_space_id} does not expose any writable branch.",
                }
            branch_ids = {branch.id for branch in available_branches}
            resolved_branch_id = target_branch_id if target_branch_id in branch_ids else available_branches[0].id
            return {
                "status": "ok",
                "allowed": True,
                "targetSpaceId": target_space_id,
                "targetBranchId": resolved_branch_id,
                "summary": f"Bidirectional mount allows writing into shared space {target_space_id} on branch {resolved_branch_id}.",
            }


plugin = SharedMemoryModule()


def describe_mounts_tool(payload: dict[str, object]) -> dict[str, object]:
    execution_context = payload.get("executionContext") if isinstance(payload.get("executionContext"), dict) else {}
    resolved = plugin.mount_root(
        {
            "projectId": execution_context.get("projectId") or DEFAULT_PROJECT_ID,
            "spaceId": payload.get("spaceId") or execution_context.get("spaceId") or DEFAULT_SPACE_ID,
            "branchId": payload.get("branchId") or execution_context.get("branchId") or DEFAULT_BRANCH_ID,
            "ownerProfileId": execution_context.get("ownerProfileId"),
            "subject": execution_context.get("subject") or f"profile:{execution_context.get('ownerProfileId')}" if execution_context.get("ownerProfileId") else None,
        }
    )
    return {
        "summary": normalize_excerpt(str(resolved.get("summary") or "No shared mounts available."), 180),
        "accessibleMounts": resolved.get("accessibleMounts") or [],
        "mountFragments": resolved.get("mountFragments") or [],
    }