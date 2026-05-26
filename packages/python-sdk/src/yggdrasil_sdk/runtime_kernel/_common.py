from __future__ import annotations

import logging
from time import perf_counter
from typing import Any, Literal

_logger = logging.getLogger(__name__)

from ..application_runtime import resolve_application_active_capabilities, resolve_runtime_application_id
from ..contracts import ActorRef, BudgetState, EntityRef, ExternalRef, RootMountPackage, TaskSnapshotSummary, TaskTakeoverProtocol, TaskRuntimeState, WorkContextStack
from ..hook_runtime import active_module_ids, call_module_hook, collect_hook_results, load_active_module, validate_memory_write
from ..hooks import HookNames
from ..llm_runtime import invoke_runtime_completion, load_runtime_candidate_models
from ..model_routing import build_model_route_decision
from ..persistence import OutboxRepository, RedisCoordinator, RuntimeRepository, TaskRepository, get_persistence_runtime
from ..persistence.constants import DEFAULT_APP_ID, DEFAULT_BRANCH_ID, DEFAULT_PROJECT_ID, DEFAULT_SPACE_ID
from ..persistence.repositories import MemoryRepository, NodeRepository, WorkspaceBootstrapRepository
from ..support import ensure_state_subdir, new_id, normalize_excerpt, relative_workspace_path, resolve_workspace_root, utc_now, write_json


AGENT_RUNTIME_QUEUE = "agent-runtime"
PACKAGE_ENTRY_TTL_SECONDS = 60 * 60 * 24


