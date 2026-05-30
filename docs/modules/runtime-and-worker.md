# Module: runtime-and-worker

## Responsibility

该模块群负责任务执行闭环：排队、执行、子代理分支、pause/resume、安全停机与快照恢复。

## Key Files

- `services/agent-runtime/src/yggdrasil_agent_runtime/runtime.py`
- `services/worker/src/yggdrasil_worker/registry.py`
- `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/__init__.py`
- `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop.py`
- `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/snapshot.py`

## Entry Points

- `execute_main_agent_work_item`
- `queue_main_agent_execution`
- worker 活动 `core.agent.main.execute` / `core.agent.subagent.execute`

## Data Flow

任务请求 -> 队列入列 -> worker 弹出工作项 -> runtime_kernel 主循环 -> 工具/模型/模块执行 -> 快照与结果回写。

## Important Types / Classes / Functions

- `AGENT_RUNTIME_QUEUE`
- `execute_main_agent_work_item`
- `prepare_pause_snapshot`
- `request_task_pause`
- `discover_worker_activities`（worker 动态活动发现）
- `dispatch_work_item`（活动路由分发）
- `run_worker_once`（单轮消费执行）
- `services/worker/src/yggdrasil_worker/main.py` 默认进入常驻消费模式，`uv run yggdrasil-worker` 会持续轮询 `AGENT_RUNTIME_QUEUE`

## Common Change Scenarios

- 修改暂停恢复：先看 `snapshot.py` + `execution_loop.py`。
- 修改工作项分发：先看 `worker/registry.py` 的 `dispatch_work_item`。
- 修改 shutdown 行为：先看 `shutdown_control`。

## Tests

- `tests/test_runtime_and_pruning.py`
- `tests/test_subagent_and_worker.py`
- `tests/test_task_takeover.py`
- `tests/test_llm_retry_and_safe_shutdown.py`

## Risks

- 该链路属于高耦合热路径，易出现“看似通过但恢复态失真”。
- 队列和快照字段变化若未同步测试，可能出现重复执行或丢执行。

## Related Docs

- `docs/architecture/data-flow.md`
- `docs/development/large-file-inventory.md`
