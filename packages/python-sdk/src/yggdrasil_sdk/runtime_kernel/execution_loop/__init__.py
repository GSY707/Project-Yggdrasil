from __future__ import annotations

from typing import Any

from .state import *  # noqa: F403,F401
from .transitions import *  # noqa: F403,F401
from .worker import *  # noqa: F403,F401
from . import worker as _worker_module

invoke_runtime_completion = _worker_module.invoke_runtime_completion
load_runtime_candidate_models = _worker_module.load_runtime_candidate_models


def execute_main_agent_work_item(work_item: dict[str, Any]) -> dict[str, object]:
    _worker_module.invoke_runtime_completion = invoke_runtime_completion
    _worker_module.load_runtime_candidate_models = load_runtime_candidate_models
    return _worker_module.execute_main_agent_work_item(work_item)


__all__ = [name for name in globals() if not name.startswith("__")]
