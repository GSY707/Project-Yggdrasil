from fastapi import FastAPI
from pydantic import BaseModel

from yggdrasil_sdk import instrument_fastapi_app

from .services import ModuleHostService


app = FastAPI(title="Yggdrasil Module Host", version="0.1.0")
instrument_fastapi_app(app, "module-host")


class QuarantineRequest(BaseModel):
    reason: str


class PublishRequest(BaseModel):
    limit: int = 100


class ConsumeRequest(BaseModel):
    module_id: str | None = None
    limit: int = 10
    timeout_seconds: int = 1


def _service() -> ModuleHostService:
    return ModuleHostService()


@app.get("/health")
def healthcheck() -> dict[str, object]:
    return _service().health()


@app.get("/modules")
def list_modules() -> dict[str, object]:
    return _service().list_modules()


@app.get("/modules/discovered")
def list_discovered_modules() -> dict[str, object]:
    return _service().discovered_modules()


@app.get("/modules/{module_id}")
def module_details(module_id: str) -> dict[str, object]:
    return _service().module_details(module_id)


@app.post("/modules/sync")
def sync_modules() -> dict[str, object]:
    return _service().sync_modules()


@app.post("/modules/reconcile")
def reconcile_modules() -> dict[str, object]:
    return _service().sync_modules()


@app.post("/modules/{module_id}/enable")
def enable_module(module_id: str) -> dict[str, object]:
    return _service().enable_module(module_id)


@app.post("/modules/{module_id}/disable")
def disable_module(module_id: str) -> dict[str, object]:
    return _service().disable_module(module_id)


@app.post("/modules/{module_id}/quarantine")
def quarantine_module(module_id: str, request: QuarantineRequest) -> dict[str, object]:
    return _service().quarantine_module(module_id, reason=request.reason)


@app.post("/modules/{module_id}/unquarantine")
def unquarantine_module(module_id: str) -> dict[str, object]:
    return _service().unquarantine_module(module_id)


@app.get("/hooks")
def list_hooks() -> dict[str, object]:
    return _service().list_hooks()


@app.get("/subscriptions")
def list_subscriptions() -> dict[str, object]:
    return _service().list_subscriptions()


@app.get("/health/reports")
def list_health_reports() -> dict[str, object]:
    return _service().list_health_reports()


@app.get("/config-bindings")
def list_config_bindings() -> dict[str, object]:
    return _service().list_config_bindings()


@app.post("/events/publish")
def publish_events(request: PublishRequest) -> dict[str, object]:
    return _service().publish_pending_events(limit=request.limit)


@app.post("/events/consume")
def consume_events(request: ConsumeRequest) -> dict[str, object]:
    return _service().consume_events(
        module_id=request.module_id,
        limit=request.limit,
        timeout_seconds=request.timeout_seconds,
    )