from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from .application_runtime import resolve_application_active_capabilities
import tempfile
from pathlib import Path
from typing import Any
from urllib import error as urllib_error
from urllib import request as urllib_request

from .contracts import ActorRef, BudgetState, ExternalRef, PullRequestRecord, ReviewCommentRecord, RootMountPackage
from .persistence import CollaborationRepository, NodeRepository, OutboxRepository, RedisCoordinator, TaskRepository, get_persistence_runtime
from .persistence.constants import DEFAULT_BRANCH_ID, DEFAULT_PROJECT_ID, DEFAULT_SPACE_ID
from .persistence.repositories import ModuleStateRepository, WorkspaceBootstrapRepository
from .runtime_kernel import AGENT_RUNTIME_QUEUE, PACKAGE_ENTRY_TTL_SECONDS, execute_main_agent_work_item, load_package_entry
from .support import new_id, normalize_excerpt, resolve_workspace_root, utc_now, write_json


def _normalize_actor(value: Any, *, default_type: str = "agent", default_id: str = "subagent") -> ActorRef:
    if isinstance(value, ActorRef):
        return value
    if isinstance(value, dict) and value.get("id"):
        return ActorRef.model_validate(value)
    return ActorRef(type=default_type, id=default_id)


def _cache_package_entry(coordinator: RedisCoordinator, locator: str, payload: Any) -> bool:
    try:
        coordinator.cache_json(locator, payload, ttl_seconds=PACKAGE_ENTRY_TTL_SECONDS)
        return True
    except Exception:
        return False


def _record_package_event(
    session,
    *,
    project_id: str | None,
    aggregate_type: str,
    aggregate_id: str,
    event_type: str,
    locator: str,
):
    return OutboxRepository(session).record_event(
        {
            "projectId": project_id,
            "aggregateType": aggregate_type,
            "aggregateId": aggregate_id,
            "eventType": event_type,
            "payloadRef": {"type": "package-entry", "locator": locator},
        }
    )


def _sanitize_git_branch_name(value: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9._/-]+", "-", value.strip())
    sanitized = re.sub(r"/{2,}", "/", sanitized).strip("./-")
    return sanitized or "subagent"


def _remaining_int(total: int | None, used: int) -> int | None:
    if total is None:
        return None
    return max(total - used, 0)


def _remaining_float(total: float | None, used: float) -> float | None:
    if total is None:
        return None
    return max(round(total - used, 6), 0.0)


def _derive_child_budget(parent_budget: BudgetState, requested_budget: dict[str, Any] | None) -> BudgetState:
    requested = BudgetState.model_validate(requested_budget or {})
    remaining_tokens = _remaining_int(parent_budget.token_budget_total, parent_budget.token_budget_used)
    remaining_cost = _remaining_float(parent_budget.cost_budget_total, parent_budget.cost_budget_used)

    def _fixed_int(value: int | None, remaining: int | None) -> int | None:
        if value is None or remaining is None:
            return value if value is not None else remaining
        if value > remaining:
            raise ValueError("Requested child token budget exceeds the remaining parent token budget.")
        return value

    def _fixed_float(value: float | None, remaining: float | None) -> float | None:
        if value is None or remaining is None:
            return value if value is not None else remaining
        if value > remaining:
            raise ValueError("Requested child cost budget exceeds the remaining parent cost budget.")
        return round(value, 6)

    def _capped_int(value: int | None, remaining: int | None) -> int | None:
        if remaining is None:
            return value
        if value is None:
            return remaining
        return min(value, remaining)

    def _capped_float(value: float | None, remaining: float | None) -> float | None:
        if remaining is None:
            return round(value, 6) if value is not None else None
        if value is None:
            return remaining
        return round(min(value, remaining), 6)

    if parent_budget.child_budget_mode == "inherit":
        token_total = remaining_tokens
        cost_total = remaining_cost
    elif parent_budget.child_budget_mode == "fixed":
        token_total = _fixed_int(requested.token_budget_total, remaining_tokens)
        cost_total = _fixed_float(requested.cost_budget_total, remaining_cost)
    else:
        token_total = _capped_int(requested.token_budget_total, remaining_tokens)
        cost_total = _capped_float(requested.cost_budget_total, remaining_cost)

    self_think_limit = requested.self_think_token_limit or parent_budget.self_think_token_limit
    if self_think_limit is not None and token_total is not None:
        self_think_limit = min(self_think_limit, token_total)

    max_sub_agents = None if parent_budget.max_sub_agents is None else max(parent_budget.max_sub_agents - 1, 0)
    if requested.max_sub_agents is not None:
        if max_sub_agents is None:
            max_sub_agents = requested.max_sub_agents
        elif parent_budget.child_budget_mode == "fixed":
            max_sub_agents = requested.max_sub_agents
        else:
            max_sub_agents = min(max_sub_agents, requested.max_sub_agents)

    return BudgetState(
        tokenBudgetTotal=token_total,
        tokenBudgetUsed=0,
        costBudgetTotal=cost_total,
        costBudgetUsed=0.0,
        selfThinkTokenLimit=self_think_limit,
        childBudgetMode=parent_budget.child_budget_mode,
        maxSubAgents=max_sub_agents,
    )


def _root_ids(project_id: str, branch_id: str) -> dict[str, str]:
    return {
        root_branch: new_id("node", project_id, branch_id, root_branch, stable=True)
        for root_branch in ("identity", "context", "execution")
    }


def _select_readonly_context_items(node_repository: NodeRepository, parent_task, request: dict[str, Any]) -> list[dict[str, Any]]:
    explicit_context = request.get("currentContext")
    if isinstance(explicit_context, list):
        return [item for item in explicit_context if isinstance(item, dict)]

    if parent_task.active_snapshot_id:
        snapshot = TaskRepository(node_repository.session).get_snapshot(parent_task.active_snapshot_id)
        if snapshot is not None:
            payload = load_package_entry(snapshot.context_ref.locator)
            if isinstance(payload, list):
                return [item for item in payload if isinstance(item, dict)]

    context_items: list[dict[str, Any]] = []
    for node in node_repository.list_nodes(branch_id=parent_task.branch_id, limit=int(request.get("contextNodeLimit") or 64)):
        if node.node_type == "root":
            continue
        context_items.append(
            {
                "kind": "node",
                "id": node.id,
                "branchId": node.branch_id,
                "title": node.title,
                "content": normalize_excerpt(node.content, 320),
                "rootBranch": node.root_branch,
                "nodeType": node.node_type,
            }
        )
    return context_items[-24:]


def _build_readonly_context_package_from_session(
    session,
    *,
    parent_task,
    child_task_id: str,
    child_branch_id: str,
    parent_run_id: str | None,
    request: dict[str, Any],
) -> tuple[dict[str, Any], str, bool]:
    node_repository = NodeRepository(session)
    context_items = _select_readonly_context_items(node_repository, parent_task, request)
    identity_refs, context_refs, execution_refs = node_repository.root_mount_refs(
        parent_task.project_id,
        parent_task.branch_id,
        parent_task.execution_root_node_id,
    )
    active_capabilities = resolve_application_active_capabilities(parent_task.app_id)
    summary_parts = [
        "Identity root is mounted for stable agent policy.",
        "Context root is mounted for project and world state.",
        "Execution root is mounted for current task progress and resumability.",
    ]
    if parent_task.current_focus:
        summary_parts.append(f"Current focus: {normalize_excerpt(parent_task.current_focus, 120)}")
    if parent_task.current_objective or parent_task.goal:
        summary_parts.append(f"Objective: {normalize_excerpt(parent_task.current_objective or parent_task.goal, 160)}")
    if parent_task.resume_message:
        summary_parts.append(f"Resume message available: {normalize_excerpt(parent_task.resume_message, 120)}")

    root_mount = RootMountPackage(
        id=new_id("mount", parent_task.id, parent_task.project_id, parent_task.branch_id, stable=True),
        taskId=parent_task.id,
        projectId=parent_task.project_id,
        branchId=parent_task.branch_id,
        systemIntro=(
            "Project Yggdrasil mounts identity, context, and execution roots before each run so "
            "the agent starts from stable runtime state instead of prompt-only conventions."
        ),
        identityRefs=identity_refs,
        contextRefs=context_refs,
        executionRefs=execution_refs,
        rootSummary=" ".join(summary_parts),
        taskObjective=parent_task.current_objective or parent_task.goal,
        resumeMessage=parent_task.resume_message,
        budgetState=parent_task.budget,
        activeCapabilities=active_capabilities,
        generatedAt=utc_now(),
    ).model_dump(by_alias=True, mode="json")
    root_mount["mountedNodeRefs"] = [
        *root_mount["identityRefs"],
        *root_mount["contextRefs"],
        *root_mount["executionRefs"],
    ]
    root_mount["spaceId"] = parent_task.space_id
    root_mount["source"] = "database"
    package = {
        "id": new_id("subctx", parent_task.id, child_task_id, stable=True),
        "mode": "readonly",
        "sourceTaskId": parent_task.id,
        "sourceAgentRunId": parent_run_id,
        "sourceBranchId": parent_task.branch_id,
        "targetTaskId": child_task_id,
        "targetBranchId": child_branch_id,
        "taskObjective": parent_task.current_objective or parent_task.goal,
        "currentFocus": parent_task.current_focus,
        "mountedNodeRefs": root_mount.get("mountedNodeRefs") or [],
        "rootMount": root_mount,
        "contextItems": context_items,
        "generatedAt": utc_now().isoformat(),
    }
    locator = f"runtime/tasks/{child_task_id}/readonly-context/current"
    cached = _cache_package_entry(RedisCoordinator(get_persistence_runtime().settings), locator, package)
    return package, locator, cached


def build_readonly_context_package(parent_task_id: str, child_task_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    request = payload or {}
    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        parent_task = TaskRepository(session).get_task(parent_task_id)
        if parent_task is None:
            raise KeyError(parent_task_id)
        package, locator, cached = _build_readonly_context_package_from_session(
            session,
            parent_task=parent_task,
            child_task_id=child_task_id,
            child_branch_id=str(request.get("childBranchId") or DEFAULT_BRANCH_ID),
            parent_run_id=str(request["parentRunId"]) if request.get("parentRunId") is not None else None,
            request=request,
        )
    return {
        "readonlyContext": package,
        "readonlyContextRef": {"type": "package-entry", "locator": locator},
        "cached": cached,
    }


class GitCollaborationAdapter:
    def __init__(self, payload: dict[str, Any] | None = None) -> None:
        request = payload or {}
        configured_repo = request.get("repoPath") or os.getenv("YGGDRASIL_GIT_REPO_PATH")
        self.repo_path = Path(configured_repo).resolve() if configured_repo else resolve_workspace_root()
        self.github_owner = str(request.get("githubOwner") or os.getenv("YGGDRASIL_GITHUB_OWNER") or "")
        self.github_repo = str(request.get("githubRepo") or os.getenv("YGGDRASIL_GITHUB_REPO") or "")
        self.github_token = str(request.get("githubToken") or os.getenv("YGGDRASIL_GITHUB_TOKEN") or "")
        self.github_api_url = str(request.get("githubApiUrl") or os.getenv("YGGDRASIL_GITHUB_API_URL") or "https://api.github.com").rstrip("/")

    def _run_git(self, *args: str, cwd: Path | None = None) -> str:
        command = ["git", "-C", str((cwd or self.repo_path).resolve()), *args]
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
        if completed.returncode != 0:
            detail = completed.stderr.strip() or completed.stdout.strip() or "unknown git error"
            raise RuntimeError(detail)
        return completed.stdout.strip()

    def ensure_repository(self) -> None:
        self._run_git("rev-parse", "--is-inside-work-tree")

    def branch_exists(self, branch_name: str) -> bool:
        completed = subprocess.run(
            ["git", "-C", str(self.repo_path), "show-ref", "--verify", f"refs/heads/{branch_name}"],
            capture_output=True,
            text=True,
            check=False,
        )
        return completed.returncode == 0

    def get_head(self, ref: str) -> str:
        return self._run_git("rev-parse", ref)

    def create_branch(self, branch_name: str, base_ref: str) -> dict[str, Any]:
        self.ensure_repository()
        if not self.branch_exists(branch_name):
            self._run_git("branch", branch_name, base_ref)
        return {"branchName": branch_name, "headRef": self.get_head(branch_name), "baseRef": base_ref}

    def _worktree_base_dir(self) -> Path:
        repo_marker = re.sub(r"[^A-Za-z0-9]+", "-", self.repo_path.name)[:12] or "repo"
        base_dir = Path(tempfile.gettempdir()) / "ygwt" / repo_marker
        base_dir.mkdir(parents=True, exist_ok=True)
        return base_dir

    def _add_worktree(self, branch_name: str, *, base_ref: str | None = None) -> Path:
        branch_marker = _sanitize_git_branch_name(branch_name).replace("/", "-")[:18] or "branch"
        path = Path(tempfile.mkdtemp(prefix=f"{branch_marker}-", dir=self._worktree_base_dir()))
        try:
            if self.branch_exists(branch_name):
                self._run_git("worktree", "add", "--force", str(path), branch_name)
            else:
                if base_ref is None:
                    raise RuntimeError(f"Base ref is required when creating worktree for new branch {branch_name}.")
                self._run_git("worktree", "add", "--force", "-b", branch_name, str(path), base_ref)
            return path
        except Exception:
            shutil.rmtree(path, ignore_errors=True)
            raise

    def _remove_worktree(self, path: Path) -> None:
        try:
            self._run_git("worktree", "remove", "--force", str(path))
        finally:
            shutil.rmtree(path, ignore_errors=True)

    def write_manifest_commit(
        self,
        *,
        branch_name: str,
        base_ref: str,
        relative_path: str,
        payload: dict[str, Any],
        commit_message: str,
    ) -> dict[str, Any]:
        self.ensure_repository()
        self.create_branch(branch_name, base_ref)
        worktree = self._add_worktree(branch_name)
        try:
            manifest_path = worktree / relative_path
            write_json(manifest_path, payload)
            self._run_git("add", relative_path, cwd=worktree)
            status = self._run_git("status", "--short", cwd=worktree)
            committed = False
            if status.strip():
                self._run_git(
                    "-c",
                    "user.name=Project Yggdrasil",
                    "-c",
                    "user.email=yggdrasil@local",
                    "commit",
                    "-m",
                    commit_message,
                    cwd=worktree,
                )
                committed = True
            return {
                "branchName": branch_name,
                "headRef": self.get_head(branch_name),
                "manifestPath": relative_path,
                "committed": committed,
            }
        finally:
            self._remove_worktree(worktree)

    def merge_branch(self, *, source_branch: str, target_branch: str, message: str) -> dict[str, Any]:
        self.ensure_repository()
        worktree = self._add_worktree(target_branch)
        try:
            self._run_git(
                "-c",
                "user.name=Project Yggdrasil",
                "-c",
                "user.email=yggdrasil@local",
                "merge",
                "--no-ff",
                "-m",
                message,
                source_branch,
                cwd=worktree,
            )
            return {"targetBranch": target_branch, "mergeCommitRef": self.get_head(target_branch)}
        finally:
            self._remove_worktree(worktree)

    def github_enabled(self) -> bool:
        return bool(self.github_owner and self.github_repo and self.github_token)

    def _github_request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        if not self.github_enabled():
            raise RuntimeError("GitHub integration is not configured.")
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = urllib_request.Request(
            f"{self.github_api_url}{path}",
            data=data,
            method=method,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self.github_token}",
                "User-Agent": "Project-Yggdrasil",
                "X-GitHub-Api-Version": "2022-11-28",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib_request.urlopen(request, timeout=20) as response:
                body = response.read().decode("utf-8")
        except urllib_error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"GitHub API {method} {path} failed: {body}") from exc
        return json.loads(body) if body else {}

    def create_remote_pull_request(self, *, title: str, body: str, head: str, base: str) -> dict[str, Any] | None:
        if not self.github_enabled():
            return None
        return self._github_request(
            "POST",
            f"/repos/{self.github_owner}/{self.github_repo}/pulls",
            {"title": title, "body": body, "head": head, "base": base},
        )

    def submit_remote_review(self, *, external_id: str, decision: str, body: str) -> dict[str, Any] | None:
        if not self.github_enabled():
            return None
        event = "COMMENT"
        if decision == "approved":
            event = "APPROVE"
        elif decision == "rejected":
            event = "REQUEST_CHANGES"
        return self._github_request(
            "POST",
            f"/repos/{self.github_owner}/{self.github_repo}/pulls/{external_id}/reviews",
            {"body": body, "event": event},
        )

    def merge_remote_pull_request(self, *, external_id: str, commit_title: str) -> dict[str, Any] | None:
        if not self.github_enabled():
            return None
        return self._github_request(
            "PUT",
            f"/repos/{self.github_owner}/{self.github_repo}/pulls/{external_id}/merge",
            {"commit_title": commit_title, "merge_method": "merge"},
        )


def _collect_branch_changes(session, branch_id: str) -> dict[str, Any]:
    repository = NodeRepository(session)
    nodes = [node for node in repository.list_nodes(branch_id=branch_id, limit=5000) if node.node_type != "root"]
    edges = repository.list_edges(branch_id=branch_id, limit=5000)
    annotations = repository.list_source_annotations(branch_id=branch_id, limit=5000)
    changed_entities = [
        *[{"kind": "node", "id": node.id} for node in nodes],
        *[{"kind": "edge", "id": edge.id} for edge in edges],
        *[{"kind": "source-annotation", "id": annotation.id} for annotation in annotations],
    ]
    return {
        "nodes": nodes,
        "edges": edges,
        "annotations": annotations,
        "changedEntities": changed_entities,
    }


def launch_subagent_task(parent_task_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    request = payload or {}
    runtime = get_persistence_runtime()
    coordinator = RedisCoordinator(runtime.settings)
    actor = _normalize_actor(request.get("createdBy"), default_id="subagent")
    parent_run_id = str(request["parentRunId"]) if request.get("parentRunId") is not None else None
    adapter = GitCollaborationAdapter(request)

    with runtime.session_scope() as session:
        bootstrap = WorkspaceBootstrapRepository(session)
        bootstrap.ensure_default_workspace()
        task_repository = TaskRepository(session)
        collaboration_repository = CollaborationRepository(session)

        parent_task = task_repository.get_task(parent_task_id)
        if parent_task is None:
            raise KeyError(parent_task_id)
        if parent_task.budget.max_sub_agents is not None and parent_task.budget.max_sub_agents <= 0:
            raise ValueError(f"Task {parent_task_id} has exhausted its maxSubAgents budget.")

        target_branch_id = str(request.get("targetBranchId") or parent_task.branch_id)
        target_branch = collaboration_repository.get_branch(target_branch_id)
        if target_branch is None:
            raise KeyError(target_branch_id)

        branch_name_seed = str(request.get("branchName") or f"yggdrasil/subagent/{parent_task.id}/{utc_now().strftime('%Y%m%d%H%M%S')}")
        git_branch_name = _sanitize_git_branch_name(branch_name_seed)
        child_branch = collaboration_repository.create_branch(
            {
                "projectId": parent_task.project_id,
                "spaceId": parent_task.space_id,
                "name": git_branch_name,
                "baseBranchId": target_branch.id,
                "createdBy": actor.model_dump(mode="json"),
            }
        )
        branch_roots = bootstrap.ensure_branch_workspace(
            branch_id=child_branch.id,
            project_id=child_branch.project_id,
            space_id=child_branch.space_id,
            branch_name=child_branch.name,
            base_branch_id=child_branch.base_branch_id,
            created_by=actor,
        )

        child_budget = _derive_child_budget(parent_task.budget, request.get("subAgentBudget") if isinstance(request.get("subAgentBudget"), dict) else None)
        child_task = task_repository.create_task(
            {
                "appId": parent_task.app_id,
                "projectId": parent_task.project_id,
                "spaceId": parent_task.space_id,
                "branchId": child_branch.id,
                "title": str(request.get("title") or f"Sub-Agent for {parent_task.title}"),
                "goal": str(request.get("goal") or parent_task.goal),
                "currentFocus": str(request.get("currentFocus") or "subagent-planning"),
                "currentObjective": str(request.get("currentObjective") or parent_task.current_objective or parent_task.goal),
                "ownerProfileId": parent_task.owner_profile_id,
                "executionRootNodeId": branch_roots["executionRootNodeId"],
                "budget": child_budget.model_dump(by_alias=True),
                "status": "queued",
            }
        )

        readonly_context, readonly_locator, readonly_cached = _build_readonly_context_package_from_session(
            session,
            parent_task=parent_task,
            child_task_id=child_task.id,
            child_branch_id=child_branch.id,
            parent_run_id=parent_run_id,
            request=request,
        )

        if parent_task.budget.max_sub_agents is not None:
            task_repository.update_task(
                parent_task.id,
                {
                    "budgetState": parent_task.budget.model_copy(update={"max_sub_agents": max(parent_task.budget.max_sub_agents - 1, 0)}),
                },
            )

        branch_init = adapter.create_branch(child_branch.name, target_branch.name)
        child_branch = collaboration_repository.update_branch(child_branch.id, {"headRef": branch_init["headRef"]})

        readonly_ref = {"type": "package-entry", "locator": readonly_locator}
        task_event_locator = f"collaboration/tasks/{child_task.id}"
        _cache_package_entry(
            coordinator,
            task_event_locator,
            {
                "task": child_task.model_dump(by_alias=True, mode="json"),
                "parentTaskId": parent_task.id,
                "childBranchId": child_branch.id,
                "readonlyContextRef": readonly_ref,
            },
        )
        task_created_event = _record_package_event(
            session,
            project_id=child_task.project_id,
            aggregate_type="task",
            aggregate_id=child_task.id,
            event_type="task.created",
            locator=task_event_locator,
        )

        work_item = {
            "activity": "core.agent.subagent.execute",
            "taskId": child_task.id,
            "parentTaskId": parent_task.id,
            "parentRunId": parent_run_id,
            "sourceBranchId": child_branch.id,
            "targetBranchId": target_branch.id,
            "command": "start",
            "requestedAt": utc_now().isoformat(),
            "payload": {
                **request,
                "runType": "subagent",
                "parentRunId": parent_run_id,
                "currentFocus": str(request.get("currentFocus") or "subagent-execution"),
                "currentObjective": str(request.get("currentObjective") or child_task.current_objective or child_task.goal),
                "readonlyContextRef": readonly_ref,
                "readonlyContextCached": readonly_cached,
            },
        }
        queue_depth = coordinator.enqueue_job(AGENT_RUNTIME_QUEUE, work_item)

    return {
        "status": "queued",
        "parentTaskId": parent_task_id,
        "branch": child_branch.model_dump(by_alias=True, mode="json"),
        "task": child_task.model_dump(by_alias=True, mode="json"),
        "readonlyContext": readonly_context,
        "readonlyContextRef": readonly_ref,
        "outboxRecord": task_created_event.model_dump(by_alias=True, mode="json"),
        "workItem": work_item,
        "queue": AGENT_RUNTIME_QUEUE,
        "queueDepth": queue_depth,
        "git": branch_init,
    }


def create_pull_request(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    request = payload or {}
    runtime = get_persistence_runtime()
    coordinator = RedisCoordinator(runtime.settings)
    adapter = GitCollaborationAdapter(request)
    actor = _normalize_actor(request.get("createdBy"), default_id="subagent")

    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        collaboration_repository = CollaborationRepository(session)
        source_branch_id = str(request.get("sourceBranchId"))
        target_branch_id = str(request.get("targetBranchId") or DEFAULT_BRANCH_ID)

        source_branch = collaboration_repository.get_branch(source_branch_id)
        if source_branch is None:
            raise KeyError(source_branch_id)
        target_branch = collaboration_repository.get_branch(target_branch_id)
        if target_branch is None:
            raise KeyError(target_branch_id)

        changes = _collect_branch_changes(session, source_branch.id)
        title = str(request.get("title") or f"Merge {source_branch.name} into {target_branch.name}")
        summary = normalize_excerpt(
            str(
                request.get("summary")
                or f"Sub-Agent proposes {len(changes['changedEntities'])} persisted entities from {source_branch.name} into {target_branch.name}."
            ),
            240,
        )
        pr = collaboration_repository.upsert_pull_request(
            PullRequestRecord(
                id=str(request.get("id") or new_id("pr", source_branch.id, target_branch.id)),
                projectId=source_branch.project_id,
                sourceBranchId=source_branch.id,
                targetBranchId=target_branch.id,
                title=title,
                summary=summary,
                status="open",
                createdBy=actor,
                reviewedBy=None,
                externalId=None,
                externalUrl=None,
                mergeCommitRef=None,
                mergedAt=None,
                createdAt=utc_now(),
            )
        )

        manifest_path = f".yggdrasil/collaboration/{source_branch.id}/pull-request.json"
        manifest = {
            "pullRequest": pr.model_dump(by_alias=True, mode="json"),
            "sourceBranch": source_branch.model_dump(by_alias=True, mode="json"),
            "targetBranch": target_branch.model_dump(by_alias=True, mode="json"),
            "sourceTaskId": request.get("sourceTaskId"),
            "sourceRunId": request.get("sourceRunId"),
            "readonlyContextRef": request.get("readonlyContextRef"),
            "changedEntities": changes["changedEntities"],
            "generatedAt": utc_now().isoformat(),
        }
        git_result = adapter.write_manifest_commit(
            branch_name=source_branch.name,
            base_ref=target_branch.name,
            relative_path=manifest_path,
            payload=manifest,
            commit_message=f"chore(collaboration): open {pr.id}",
        )
        source_branch = collaboration_repository.update_branch(source_branch.id, {"headRef": git_result["headRef"]})

        review_comment = collaboration_repository.add_review_comment(
            ReviewCommentRecord(
                id=new_id("review", pr.id, "open", stable=True),
                prId=pr.id,
                author=ActorRef(type="module", id="subagent-pr"),
                targetKind="package",
                targetId=manifest_path,
                body=normalize_excerpt(
                    f"Review required before merge. Changed entities: {', '.join(entity['id'] for entity in changes['changedEntities'][:6]) or 'none'}.",
                    240,
                ),
                status="open",
                createdAt=utc_now(),
                resolvedAt=None,
            )
        )

        remote_pr = adapter.create_remote_pull_request(
            title=pr.title,
            body=f"{pr.summary}\n\nInternal manifest: {manifest_path}",
            head=source_branch.name,
            base=target_branch.name,
        )
        if remote_pr is not None:
            pr = collaboration_repository.update_pull_request(
                pr.id,
                {
                    "externalId": str(remote_pr.get("number")),
                    "externalUrl": remote_pr.get("html_url"),
                },
            )

        locator = f"collaboration/pull-requests/{pr.id}/current"
        response = {
            "pullRequest": pr.model_dump(by_alias=True, mode="json"),
            "reviewComments": [review_comment.model_dump(by_alias=True, mode="json")],
            "changedEntities": changes["changedEntities"],
            "manifestPath": manifest_path,
            "git": git_result,
            "github": remote_pr,
        }
        _cache_package_entry(coordinator, locator, response)
        pr_created_event = _record_package_event(
            session,
            project_id=pr.project_id,
            aggregate_type="pull-request",
            aggregate_id=pr.id,
            event_type="pr.created",
            locator=locator,
        )

    return {
        **response,
        "outboxRecord": pr_created_event.model_dump(by_alias=True, mode="json"),
    }


def _merge_branch_entities(session, *, source_branch_id: str, target_branch_id: str, actor: ActorRef) -> dict[str, Any]:
    collaboration_repository = CollaborationRepository(session)
    node_repository = NodeRepository(session)
    source_branch = collaboration_repository.get_branch(source_branch_id)
    target_branch = collaboration_repository.get_branch(target_branch_id)
    if source_branch is None or target_branch is None:
        raise KeyError("Source or target branch not found.")

    source_roots = _root_ids(source_branch.project_id, source_branch.id)
    target_roots = _root_ids(target_branch.project_id, target_branch.id)
    source_root_by_id = {node_id: root_branch for root_branch, node_id in source_roots.items()}

    created_nodes: list[dict[str, Any]] = []
    created_edges: list[dict[str, Any]] = []
    created_annotations: list[dict[str, Any]] = []
    node_mapping: dict[str, str] = {}
    edge_mapping: dict[str, str] = {}

    source_nodes = [node for node in node_repository.list_nodes(branch_id=source_branch_id, limit=5000) if node.node_type != "root"]
    for node in source_nodes:
        parent_id = None
        if node.parent_id is not None:
            if node.parent_id in node_mapping:
                parent_id = node_mapping[node.parent_id]
            elif node.parent_id in source_root_by_id:
                parent_id = target_roots[source_root_by_id[node.parent_id]]
        if parent_id is None and node.root_branch in target_roots:
            parent_id = target_roots[node.root_branch]

        created = node_repository.create_node(
            {
                "projectId": target_branch.project_id,
                "spaceId": target_branch.space_id,
                "branchId": target_branch.id,
                "parentId": parent_id,
                "rootBranch": node.root_branch,
                "nodeType": node.node_type,
                "status": "active",
                "title": node.title,
                "content": node.content,
                "detailLevel": node.detail_level,
                "importance": node.importance,
                "stability": node.stability,
                "forgetRate": node.forget_rate,
                "feedforwardScore": node.feedforward_score,
                "accessScore": node.access_score,
                "activityK": node.activity_k,
                "floatScore": node.float_score,
                "createdBy": node.created_by.model_dump(mode="json"),
                "updatedBy": actor.model_dump(mode="json"),
                "changeReason": f"merge-from:{source_branch.id}",
            }
        )
        node_mapping[node.id] = created.id
        created_nodes.append(created.model_dump(by_alias=True, mode="json"))

    for edge in node_repository.list_edges(branch_id=source_branch_id, limit=5000):
        from_node_id = node_mapping.get(edge.from_node_id)
        to_node_id = node_mapping.get(edge.to_node_id)
        if edge.from_node_id in source_root_by_id:
            from_node_id = target_roots[source_root_by_id[edge.from_node_id]]
        if edge.to_node_id in source_root_by_id:
            to_node_id = target_roots[source_root_by_id[edge.to_node_id]]
        if from_node_id is None or to_node_id is None:
            continue
        created = node_repository.create_edge(
            {
                "projectId": target_branch.project_id,
                "spaceId": target_branch.space_id,
                "branchId": target_branch.id,
                "fromNodeId": from_node_id,
                "toNodeId": to_node_id,
                "relationType": edge.relation_type,
                "weight": edge.weight,
                "reason": edge.reason,
                "evidenceAnnotationIds": [],
                "status": "active",
                "createdBy": edge.created_by.model_dump(mode="json"),
                "updatedBy": actor.model_dump(mode="json"),
            }
        )
        edge_mapping[edge.id] = created.id
        created_edges.append(created.model_dump(by_alias=True, mode="json"))

    for annotation in node_repository.list_source_annotations(branch_id=source_branch_id, limit=5000):
        owner_id = annotation.owner_id
        if annotation.owner_kind == "node":
            owner_id = node_mapping.get(annotation.owner_id)
        elif annotation.owner_kind == "edge":
            owner_id = edge_mapping.get(annotation.owner_id)
        if owner_id is None:
            continue
        evidence_refs = []
        for ref in annotation.evidence_refs:
            mapped_id = ref.id
            if ref.kind == "node":
                mapped_id = node_mapping.get(ref.id)
            elif ref.kind == "edge":
                mapped_id = edge_mapping.get(ref.id)
            if mapped_id is None:
                continue
            evidence_refs.append({"kind": ref.kind, "id": mapped_id})
        created = node_repository.add_source_annotation(
            annotation.owner_kind,
            owner_id,
            {
                "projectId": target_branch.project_id,
                "branchId": target_branch.id,
                "sourceType": annotation.source_type,
                "sourceRef": annotation.source_ref.model_dump(mode="json") if annotation.source_ref else None,
                "excerpt": annotation.excerpt,
                "inferenceSummary": annotation.inference_summary,
                "evidenceRefs": evidence_refs,
                "confidence": annotation.confidence,
                "createdBy": annotation.created_by.model_dump(mode="json"),
            },
        )
        created_annotations.append(created.model_dump(by_alias=True, mode="json"))

    return {
        "nodes": created_nodes,
        "edges": created_edges,
        "sourceAnnotations": created_annotations,
        "counts": {
            "nodes": len(created_nodes),
            "edges": len(created_edges),
            "sourceAnnotations": len(created_annotations),
        },
    }


def review_pull_request(pr_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    request = payload or {}
    decision = str(request.get("decision") or "approved").lower()
    if decision in {"approve", "approved"}:
        decision = "approved"
    elif decision in {"reject", "rejected"}:
        decision = "rejected"
    else:
        raise ValueError(f"Unsupported review decision: {decision}")

    runtime = get_persistence_runtime()
    coordinator = RedisCoordinator(runtime.settings)
    adapter = GitCollaborationAdapter(request)
    actor = _normalize_actor(request.get("reviewedBy"), default_id="main-agent")

    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        collaboration_repository = CollaborationRepository(session)
        pull_request = collaboration_repository.get_pull_request(pr_id)
        if pull_request is None:
            raise KeyError(pr_id)
        source_branch = collaboration_repository.get_branch(pull_request.source_branch_id)
        target_branch = collaboration_repository.get_branch(pull_request.target_branch_id)
        if source_branch is None or target_branch is None:
            raise KeyError("Source or target branch missing.")

        review_comment = collaboration_repository.add_review_comment(
            ReviewCommentRecord(
                id=str(request.get("reviewCommentId") or new_id("review", pr_id, decision, utc_now().isoformat())),
                prId=pr_id,
                author=actor,
                targetKind="plan",
                targetId=pr_id,
                body=normalize_excerpt(
                    str(request.get("comment") or f"Pull request {pr_id} reviewed with decision {decision}."),
                    240,
                ),
                status="resolved" if decision == "approved" else "rejected",
                createdAt=utc_now(),
                resolvedAt=utc_now(),
            )
        )

        remote_review = None
        if pull_request.external_id:
            remote_review = adapter.submit_remote_review(
                external_id=pull_request.external_id,
                decision=decision,
                body=review_comment.body,
            )

        pr_status = "approved" if decision == "approved" else "rejected"
        merge_summary = None
        git_merge = None
        remote_merge = None
        merged_at = None
        merge_commit_ref = pull_request.merge_commit_ref

        if decision == "approved" and bool(request.get("mergeImmediately", False)):
            merge_summary = _merge_branch_entities(
                session,
                source_branch_id=source_branch.id,
                target_branch_id=target_branch.id,
                actor=actor,
            )
            git_merge = adapter.merge_branch(
                source_branch=source_branch.name,
                target_branch=target_branch.name,
                message=f"chore(collaboration): merge {pull_request.id}",
            )
            merge_commit_ref = git_merge["mergeCommitRef"]
            if pull_request.external_id:
                remote_merge = adapter.merge_remote_pull_request(external_id=pull_request.external_id, commit_title=pull_request.title)
                if remote_merge is not None and remote_merge.get("sha"):
                    merge_commit_ref = str(remote_merge["sha"])
            merged_at = utc_now()
            pr_status = "merged"
            collaboration_repository.update_branch(source_branch.id, {"status": "merged"})
            collaboration_repository.update_branch(target_branch.id, {"headRef": merge_commit_ref})

        pull_request = collaboration_repository.update_pull_request(
            pr_id,
            {
                "status": pr_status,
                "reviewedBy": actor.model_dump(mode="json"),
                "mergedAt": merged_at,
                "mergeCommitRef": merge_commit_ref,
            },
        )

        locator = f"collaboration/pull-requests/{pr_id}/review/{review_comment.id}"
        response = {
            "pullRequest": pull_request.model_dump(by_alias=True, mode="json"),
            "reviewComment": review_comment.model_dump(by_alias=True, mode="json"),
            "mergeSummary": merge_summary,
            "git": git_merge,
            "githubReview": remote_review,
            "githubMerge": remote_merge,
        }
        _cache_package_entry(coordinator, locator, response)
        reviewed_event = _record_package_event(
            session,
            project_id=pull_request.project_id,
            aggregate_type="pull-request",
            aggregate_id=pull_request.id,
            event_type="pr.reviewed",
            locator=locator,
        )
        merged_event = None
        if pr_status == "merged":
            merged_event = _record_package_event(
                session,
                project_id=pull_request.project_id,
                aggregate_type="pull-request",
                aggregate_id=pull_request.id,
                event_type="pr.merged",
                locator=f"collaboration/pull-requests/{pr_id}/merge",
            )

    return {
        **response,
        "outboxRecords": {
            "reviewed": reviewed_event.model_dump(by_alias=True, mode="json"),
            "merged": merged_event.model_dump(by_alias=True, mode="json") if merged_event is not None else None,
        },
    }


def execute_subagent_work_item(work_item: dict[str, Any]) -> dict[str, Any]:
    request = work_item.get("payload") if isinstance(work_item.get("payload"), dict) else {}
    readonly_context_ref = request.get("readonlyContextRef") if isinstance(request.get("readonlyContextRef"), dict) else None
    current_context = request.get("currentContext") if isinstance(request.get("currentContext"), list) else None
    if current_context is None and isinstance(readonly_context_ref, dict) and readonly_context_ref.get("locator"):
        readonly_payload = load_package_entry(str(readonly_context_ref["locator"]))
        if isinstance(readonly_payload, dict) and isinstance(readonly_payload.get("contextItems"), list):
            current_context = [item for item in readonly_payload["contextItems"] if isinstance(item, dict)]

    execution_result = execute_main_agent_work_item(
        {
            "activity": "core.agent.main.execute",
            "taskId": work_item.get("taskId"),
            "command": work_item.get("command") or request.get("command") or "start",
            "payload": {
                **request,
                "runType": "subagent",
                "currentContext": current_context or [],
                "executionActorId": str(request.get("executionActorId") or "subagent"),
            },
        }
    )
    if execution_result.get("status") != "completed":
        return {
            "status": str(execution_result.get("status") or "failed"),
            "taskId": work_item.get("taskId"),
            "execution": execution_result,
        }

    pr_result = create_pull_request(
        {
            **request,
            "sourceBranchId": work_item.get("sourceBranchId") or work_item.get("taskBranchId"),
            "targetBranchId": work_item.get("targetBranchId"),
            "sourceTaskId": work_item.get("taskId"),
            "sourceRunId": execution_result.get("run", {}).get("id"),
            "readonlyContextRef": readonly_context_ref,
            "createdBy": request.get("createdBy") or {"type": "agent", "id": "subagent"},
            "title": request.get("prTitle") or request.get("title") or execution_result.get("task", {}).get("title"),
            "summary": request.get("prSummary") or execution_result.get("createdNode", {}).get("content"),
        }
    )
    return {
        "status": "completed",
        "taskId": work_item.get("taskId"),
        "execution": execution_result,
        "pullRequest": pr_result["pullRequest"],
        "reviewComments": pr_result["reviewComments"],
        "manifestPath": pr_result["manifestPath"],
        "git": pr_result.get("git"),
        "github": pr_result.get("github"),
        "outboxRecord": pr_result.get("outboxRecord"),
    }