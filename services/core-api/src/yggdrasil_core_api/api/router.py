from fastapi import APIRouter

from .routes.applications import router as applications_router
from .routes.assets import router as assets_router
from .routes.collaboration import router as collaboration_router
from .routes.evaluations import router as evaluations_router
from .routes.health import router as health_router
from .routes.mcp import router as mcp_router
from .routes.memory import router as memory_router
from .routes.modules import router as modules_router
from .routes.nodes import router as nodes_router
from .routes.observability import router as observability_router
from .routes.outbox import router as outbox_router
from .routes.prompting import router as prompting_router
from .routes.runtime import router as runtime_router
from .routes.specs import router as specs_router
from .routes.tasks import router as tasks_router
from .routes.training import router as training_router
from .routes.workbench import router as workbench_router


router = APIRouter()
router.include_router(health_router, tags=["health"])
router.include_router(specs_router, prefix="/specs", tags=["specs"])
router.include_router(modules_router, prefix="/modules", tags=["modules"])
router.include_router(mcp_router, prefix="/mcp", tags=["mcp"])
router.include_router(applications_router, prefix="/applications", tags=["applications"])
router.include_router(assets_router, prefix="/assets", tags=["assets"])
router.include_router(memory_router, prefix="/memory", tags=["memory"])
router.include_router(nodes_router, prefix="/nodes", tags=["nodes"])
router.include_router(tasks_router, prefix="/tasks", tags=["tasks"])
router.include_router(collaboration_router, prefix="/collaboration", tags=["collaboration"])
router.include_router(training_router, prefix="/training", tags=["training"])
router.include_router(prompting_router, prefix="/prompting", tags=["prompting"])
router.include_router(workbench_router, prefix="/workbench", tags=["workbench"])
router.include_router(evaluations_router, prefix="/evaluations", tags=["evaluations"])
router.include_router(observability_router, prefix="/observability", tags=["observability"])
router.include_router(runtime_router, prefix="/runtime", tags=["runtime"])
router.include_router(outbox_router, prefix="/outbox", tags=["outbox"])