# Readable split facade: explicit part imports, no dynamic exec.
from .suite_cases_g4__part01 import *  # noqa: F403,F401
from .suite_cases_g4__part02 import *  # noqa: F403,F401
from .suite_cases_g4__part03 import *  # noqa: F403,F401

# Explicitly re-export underscore handlers used by suite_runner.
from .suite_cases_g4__part02 import (  # noqa: F401
	_run_g4_scene_prompt_contract_case,
	_run_g4_scene_resume_contract_case,
	_run_g4_scene_runtime_recovery_case,
	_run_g4_scene_switch_isolation_case,
)
from .suite_cases_g4__part03 import _run_g4_live_provider_matrix_case  # noqa: F401
