from __future__ import annotations

from contextlib import contextmanager
import json
import os
from pathlib import Path
import re
import shutil
from time import perf_counter
import subprocess
import tempfile
import threading
from typing import Any, Iterator

from ..contracts import ExternalRef
from ..domain import EvaluationSuiteRecord
from ..mcp_bridge import close_mcp_bridge_sessions
from ..observability_exporters import finish_langfuse_generation
from ..observability_exporters import flush_observability_exporters
from ..observability_exporters import start_langfuse_generation
from ..observability import observe_span, record_log, record_metric
from ..persistence import EvaluationRepository, PromptAssetRepository, RuntimeRepository, ensure_workspace_bootstrap, get_persistence_runtime, initialize_schema, reset_persistence_runtime
from ..persistence.constants import DEFAULT_BRANCH_ID, DEFAULT_PROJECT_ID
from ..persistence.repositories import CollaborationRepository, NodeRepository, TaskRepository, TrainingRepository, WorkspaceBootstrapRepository
from ..support import ensure_state_subdir, new_id, normalize_excerpt, prepare_runtime_workspace_sandbox, read_json, relative_workspace_path, resolve_workspace_root, resolve_state_dir, utc_now, write_json


