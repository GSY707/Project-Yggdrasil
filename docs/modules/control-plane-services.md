# Module: control-plane-services

## Responsibility

`services/core-api` 提供统一控制面 API，负责将外部请求映射为任务、记忆、协作、评测与观测的业务操作。

## Key Files

- `services/core-api/src/yggdrasil_core_api/main.py`：服务启动入口。
- `services/core-api/src/yggdrasil_core_api/app.py`：FastAPI 应用装配。
- `services/core-api/src/yggdrasil_core_api/api/router.py`：总路由注册点。
- `services/core-api/src/yggdrasil_core_api/api/routes/*.py`：资源域路由。
- `services/core-api/src/yggdrasil_core_api/services/*.py`：业务服务层。

## Entry Points

- HTTP 入口：`/health`, `/tasks`, `/memory`, `/runtime`, `/evaluations` 等。
- Web 代理入口：`apps/web/app/api/core/`。

## Data Flow

请求 -> route 参数校验 -> service 逻辑 -> SDK persistence/runtime -> 返回 contracts。

## Important Types / Classes / Functions

- `main()`：`services/core-api/src/yggdrasil_core_api/main.py` 服务入口。
- `router`（`APIRouter` 实例）：`services/core-api/src/yggdrasil_core_api/api/router.py`。
- `router.include_router(...)`：资源域路由装配点（tasks/memory/runtime/evaluations 等）。
- 资源 service 实现（例如 `memory_service.py`）作为路由委派目标。

## Common Change Scenarios

- 新增 API：在 `api/routes/` 新建路由并挂到 `api/router.py`。
- 扩展返回字段：同步修改 contracts 与前端消费。
- 调整业务规则：优先改 `services/` 层，不把业务逻辑塞到路由层。

## Tests

- `tests/test_memory_pipeline_api.py`
- `tests/test_persistence_api.py`
- `tests/test_m9_acceptance.py`

## Risks

- 字段契约变更会联动 web、evaluation、worker。
- route 层误加重逻辑会导致可测试性下降。

## Related Docs

- `docs/architecture/overview.md`
- `docs/architecture/module-boundaries.md`
- `docs/development/build-and-test.md`
