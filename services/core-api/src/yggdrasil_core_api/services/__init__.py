from ._base import WorkspaceServiceBase
from .asset_service import AssetServiceMixin
from .collaboration_service import CollaborationServiceMixin
from .data_governance_service import DataGovernanceServiceMixin
from .evaluation_service import EvaluationServiceMixin
from .memory_service import MemoryServiceMixin
from .prompting_service import PromptingServiceMixin
from .runtime_service import RuntimeServiceMixin
from .task_service import TaskServiceMixin


class WorkspaceService(
    TaskServiceMixin,
    MemoryServiceMixin,
    EvaluationServiceMixin,
    AssetServiceMixin,
    PromptingServiceMixin,
    CollaborationServiceMixin,
    DataGovernanceServiceMixin,
    RuntimeServiceMixin,
    WorkspaceServiceBase,
):
    pass


def get_workspace_service() -> WorkspaceService:
    return WorkspaceService()


__all__ = ["WorkspaceService", "get_workspace_service"]
