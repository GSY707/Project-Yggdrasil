# Module: python-sdk-kernel

## Responsibility

`packages/python-sdk` 是跨服务共享基座，提供领域模型、合同类型、持久化仓储、运行时编排、模型调用、评测运行时与运维工具。

## Key Files

- `packages/python-sdk/src/yggdrasil_sdk/domain.py`
- `packages/python-sdk/src/yggdrasil_sdk/contracts.py`
- `packages/python-sdk/src/yggdrasil_sdk/llm_runtime.py`
- `packages/python-sdk/src/yggdrasil_sdk/prompting.py`
- `packages/python-sdk/src/yggdrasil_sdk/persistence/`
- `packages/python-sdk/src/yggdrasil_sdk/evaluation_runtime/`

## Entry Points

- runtime 内核导出：`runtime_kernel/__init__.py`
- 评测 CLI：`evaluation_cli.py`
- 运维 CLI：`ops_cli.py`

## Data Flow

contracts/domain 定义 -> runtime/persistence 使用 -> services 和 modules 复用 -> evaluation 汇总输出。

## Important Types / Classes / Functions

- runtime：`execute_main_agent_work_item`、`queue_main_agent_execution`、`prepare_pause_snapshot`
- persistence：`get_persistence_runtime` 与 `persistence/repositories/*` 接口
- llm：`llm_runtime.py` 内 provider 路由与 retry 入口
- evaluation：`run_evaluation_suite`、`list_evaluation_suite_definitions`
- CLI：`evaluation_cli.main()`、`ops_cli` 命令入口

## Common Change Scenarios

- 新增字段：先改 contracts/domain，再更新 persistence 与 API。
- 修改模型调用：先改 `llm_runtime.py`，再回归 adapter 与评测。
- 修改 prompt 编译：改 `prompting.py` 并验证 runtime artifact。

## Tests

- `tests/test_m8_runtime.py`
- `tests/test_g2_regression.py`
- `tests/test_g4_multiscene.py`
- `tests/test_phase3_stability_and_scale.py`

## Risks

- 该层改动影响面极大，必须执行最小回归集。
- contracts 与 repository 不一致会造成运行期隐式失败。

## Related Docs

- `docs/architecture/overview.md`
- `docs/development/build-and-test.md`
- `docs/development/large-file-inventory.md`
