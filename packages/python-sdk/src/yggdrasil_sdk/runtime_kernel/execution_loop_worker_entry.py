from __future__ import annotations

import sys
from typing import Any

from .execution_loop_part_a import *  # noqa: F403,F401
from .execution_loop_context_retrieval import *  # noqa: F403,F401
from .execution_loop_part_b import *  # noqa: F403,F401
from .execution_loop_exports import *  # noqa: F403,F401
from . import execution_loop_part_b as _execution_loop_part_b


invoke_runtime_completion = _execution_loop_part_b.invoke_runtime_completion
load_runtime_candidate_models = _execution_loop_part_b.load_runtime_candidate_models


def _sync_patch_surface() -> None:
    execution_loop_module = sys.modules.get(f"{__package__}.execution_loop")
    _execution_loop_part_b.invoke_runtime_completion = getattr(
        execution_loop_module,
        "invoke_runtime_completion",
        invoke_runtime_completion,
    )
    _execution_loop_part_b.load_runtime_candidate_models = getattr(
        execution_loop_module,
        "load_runtime_candidate_models",
        load_runtime_candidate_models,
    )


def execute_main_agent_work_item(work_item: dict[str, Any]) -> dict[str, object]:
    _sync_patch_surface()
    return _execution_loop_part_b.execute_main_agent_work_item(work_item)


__all__ = [name for name in globals() if not name.startswith("__")]