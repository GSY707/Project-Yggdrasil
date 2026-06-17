# Runtime 并发、状态恢复与 M9 验收调查基线

日期：2026-06-11

范围：

- 并发与稳定性：worker 队列、任务锁、长事务、状态覆盖、写入队列。
- Runtime 状态机与恢复链：task/run/snapshot 状态流、pause/resume、restart、无损恢复降级。
- M9 控制面与验收链：控制面 API、Web 代理、评测门禁、M9 acceptance 失败点。

本文件是调查基线，不是修复记录。后续实现应直接切到目标状态，不为旧状态机和旧测试保留过渡补丁。

## 结论

1. M9 控制面当前是连通的。`evalsuite_regression_m9_control_plane` 实测 2/2 通过，核心 API、Web 代理和资源/prompt/训练/应用包/MCP/任务/评测控制面已经有可用链路。
2. M9 acceptance 不是资源控制面失败，而是 pause/resume 后的 Runtime 状态收口失败。恢复后已经产生结构化交付并通过 delivery verification，但下一轮执行继续消耗预算，最后以 `Token budget exceeded before the next execution step.` 失败。
3. 并发侧存在两个必须先修的 P0：任务锁竞争失败会让 work item 被当作已处理吞掉；Redis 队列是 pop-before-process，没有 ack 或 visibility timeout，worker 崩溃会丢任务。
4. Runtime 恢复链还不是无损合同：数据库 snapshot 可标记 `restorable`，但真实 payload 只在 Redis package entry 中保留 24h；worker 对失效 resume 可能静默降级到 start；恢复 hook 失败也会降级而不是硬失败。
5. `docs/development/DEBUG_PLAN_2026_06_08.md` 中跳过的测试仍应保留为修复目标，但废旧断言需要随着新合同删除或重写，不能继续用 skip 掩盖路线分叉。

## 已执行验证

### M9 控制面

命令：

```powershell
uv run python -m yggdrasil_sdk.evaluation_cli run --suite evalsuite_regression_m9_control_plane
```

结果：

- 通过，passRate = 1.0。
- 运行记录：`.yggdrasil/state/evaluations/evalrun_0befffe749234c24ab74.json`。

### M9 acceptance

命令：

```powershell
uv run python -m yggdrasil_sdk.evaluation_cli run --suite evalsuite_acceptance_m9_capabilities
```

结果：

- 工具侧等待超时，但 evaluation run 已落盘。
- 运行记录：`.yggdrasil/state/evaluations/evalrun_58f3e90a50894780b02d.json`。
- passRate = 0.5。
- `evalcase_m9_shared_multimodal_reasoning` 通过。
- `evalcase_m9_pause_resume_memory_tree` 失败。
- 失败摘要：`m9 resume completion failed`，底层 Runtime 结果为 `Token budget exceeded before the next execution step.`

关键证据：

- 恢复后的 takeover plan 全部标为 completed。
- delivery sections 存在，并且 result/evidence/pending/incomplete 四个 hard gate verification 均 passed。
- work tree root 最后被标为 failed，failureSummary 是预算耗尽。
- 这说明当前失败点不在 M9 能力装配，而在恢复后的最终状态判定和续跑条件。

### M9 专项 pytest

命令：

```powershell
uv run pytest tests\test_m9_pause_resume.py tests\test_m9_shared_memory.py tests\test_m9_multimodal_and_relations.py tests\test_m9_memory_organizer.py tests\test_m9_training_lab.py -q
```

结果：

- 6 passed。

## 代码地图

并发与 worker：

- `services/core-api/src/yggdrasil_core_api/services/task_service.py`
- `services/core-api/src/yggdrasil_core_api/services/runtime_service.py`
- `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop/worker.py`
- `packages/python-sdk/src/yggdrasil_sdk/persistence/repositories/task.py`
- `packages/python-sdk/src/yggdrasil_sdk/persistence/coordination.py`
- `packages/python-sdk/src/yggdrasil_sdk/persistence/write_queue.py`

Runtime 状态与恢复：

- `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_control.py`
- `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop/worker.py`
- `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop/transitions.py`
- `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/snapshot.py`
- `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/root_mount.py`
- `packages/python-sdk/src/yggdrasil_sdk/llm_runtime/core.py`

M9 控制面与验收：

- `services/core-api/src/yggdrasil_core_api/routes/*.py`
- `apps/web/app/api/core/[...path]/route.ts`
- `apps/web/app/components/settings-page.tsx`
- `apps/web/app/components/evaluations-page.tsx`
- `evaluation/suites/m9-control-plane.json`
- `evaluation/suites/m9-acceptance.json`
- `packages/python-sdk/src/yggdrasil_sdk/evaluation_runtime/suite_cases/m9.py`
- `tests/api/test_persistence_control_plane_api.py`
- `tests/test_m9_acceptance.py`

## 并发与稳定性发现

### P0：任务锁竞争失败会丢 work item

`execute_main_agent_work_item()` 获取 task lock 失败时返回 `{"status": "locked"}`。`run_worker_once()` 只看到 payload 被处理过，不会 requeue、nack 或延迟重试。两个 worker 抢同一 task 时，失败方可能把该 work item 永久吞掉。

目标合同：

- lock miss 不能算成功处理。
- 必须 requeue 或放入 delayed retry。
- 测试要覆盖两个 worker 抢同一 task 时最终只执行一次且未丢 work item。

### P0：Redis 队列 pop-before-process，没有 ack 语义

当前队列消费是 `LPOP/BLPOP` 后直接执行。worker 在 pop 后、状态落库前崩溃，work item 已经从队列消失。这个问题比单个测试失败更严重，会直接破坏恢复链。

目标合同：

- work item 进入 processing 集合或 stream pending 状态。
- 完成后 ack。
- 超时未 ack 的 work item 可以被 reclaim。

### P1：主 worker 持有长 DB session 包住外部调用

worker 在一个 `session_scope()` 内做 task 查询、状态更新、prompt/LLM/tool/runtime 执行和后续落库。外部调用越慢，事务越长，并发下越容易触发锁等待、陈旧状态覆盖和 SQLite/Postgres 行锁放大。

目标合同：

- claim 阶段短事务。
- 外部执行阶段不持有写事务。
- finalize 阶段短事务并带状态前置条件。

### P1：task 状态更新缺少 CAS

`TaskRepository.update_task()` 是字段覆盖式更新，没有版本号或 expected status。pause、resume、restart、completion、retry 同时落库时，后提交者可能覆盖先提交者。

目标合同：

- 关键状态迁移使用 expected status / version。
- transition 失败要返回明确冲突，而不是静默覆盖。

### P1：任务锁缺少续租和 fencing token

当前 task lock 有固定 TTL。长执行超过 TTL 时，另一个 worker 可以拿到同一 task 的锁。即使概率不高，也会破坏 `runId`、snapshot 和 work tree 状态。

目标合同：

- 长执行续租。
- 落库携带 fencing token 或 lease id。
- finalize 阶段校验当前 lease 仍有效。

### P1：DB 状态更新与 queue enqueue 不原子

start/resume/retry/revision 路径会先改 task 状态再 enqueue。若 DB commit 与 enqueue 之间失败，task 会停在 queued，但队列没有对应 work item。

目标合同：

- 使用 outbox，或在同一恢复扫描中补偿 queued-but-not-enqueued task。
- 不再依赖调用路径的“刚好成功”。

### P2：其他稳定性风险

- outbox claim 需要原子 claim，避免多 worker 重复发布。
- memory fallback 是进程内对象，多进程测试不能当作可靠后端。
- node version / child count 等写入仍需要检查跨进程冲突路径。

## Runtime 状态机与恢复链发现

### 当前主要状态流

task 状态：

```text
draft -> queued -> running -> pause-requested -> paused -> queued/resume -> running -> queued/continuation -> awaiting-approval -> completed
```

run 状态：

```text
initializing -> mounting -> running -> waiting-tool/draining/pausing -> paused/completed/failed/aborted
```

snapshot 状态：

```text
created -> flushed -> restorable -> consumed/superseded
```

`TaskRuntimeState.phase` 主要包含：

```text
start-state | task-state-loaded | lossless-restore
```

### 恢复 payload 与 DB 状态不一致

snapshot 表只存 `contextRef` 和 `rootMountRef` locator，真实 context/root mount payload 写在 Redis package entry。package entry 默认 TTL 是 24h。TTL 过期后，DB 仍可能显示 snapshot `restorable`，但实际不可恢复。

目标合同：

- `restorable` 必须代表 payload 可读。
- payload 失效时恢复要硬失败并标记 snapshot blocker，不能静默 start。
- 若要求长期可恢复，payload 需要持久后端而不是短 TTL Redis。

### pause 请求对非 running 状态约束不足

`request_task_pause()` 当前偏向设置 `pauseRequested`，对 queued/completed/failed 等状态没有足够硬拒绝。这样 API 层可能显示 `pause-requested`，但真实 worker 状态仍是 queued 或已结束。

目标合同：

- only running 可进入 pause-requested。
- queued、completed、failed、cancelled 请求 pause 要返回明确冲突。
- UI runtimeControl 也要按同一合同展示可操作性。

### resume 降级为 start 会破坏无损恢复

`queue_main_agent_execution()` 对 resume 请求做过校验，但 worker 实际执行时仍可能遇到 snapshot 失效、resume token 不匹配或 rehydrate hook 失败。当前部分路径会降级成 start 或 start-state，而不是明确恢复失败。

目标合同：

- `command=resume` 不能静默变成 start。
- 恢复失败要写入 task/run/snapshot 的统一失败原因。
- `TASK_RESUME_REHYDRATE` hook 失败应成为恢复失败证据，不能只 fallback。

### corrupted snapshot 合同需要重定

`tests/runtime/test_runtime_restart_and_resume.py` 中存在“corrupted snapshot 仍 restorable”的旧断言痕迹；实现侧已经更接近“损坏 snapshot 生成 blocker，不应 restorable”。应以实现目标为准，删除旧断言或重写为 blocker 合同。

目标合同：

- corrupted snapshot 不可标为 restorable。
- 失败原因必须稳定落盘，便于 UI 和验收链读取。

### shutdown flag import 需要核实

`packages/python-sdk/src/yggdrasil_sdk/llm_runtime/core.py` 中存在从 `.runtime_kernel.shutdown_control` 引入的路径迹象。按当前包结构，应核实是否应为 `..runtime_kernel.shutdown_control` 或显式 facade。这个问题可能影响中断、取消或 shutdown 相关测试。

## M9 控制面与验收链发现

### 控制面已接通

已确认 API/前端代理链路覆盖：

- assets
- training
- prompting
- applications
- MCP
- tasks
- evaluations

`apps/web/app/api/core/[...path]/route.ts` 已支持 GET/POST/PUT/PATCH/DELETE，不再是只读代理。

### acceptance 失败点是 pause/resume finalization

`evalcase_m9_pause_resume_memory_tree` 的失败不是“没有恢复上下文”：

- pauseStatus 可进入 paused。
- resume 后有 mounted shared space 和 followup actions。
- delivery sections 和 verification 已经通过。
- 最终状态没有在正确时机收口，继续执行到预算耗尽，导致 task/work tree failed。

目标合同：

- resume 后若 delivery hard gates 已满足，应进入 `awaiting-approval` 或完成态，而不是继续生成下一轮执行。
- snapshot consumed / active snapshot 清理必须与最终状态一致。
- acceptance 用例应断言恢复链的状态收口，而不是靠更大 token budget 掩盖问题。

### 发布门禁不完整

`release:check` 当前包含 M9 control-plane，但未纳入 M9 acceptance。短期可以先稳定 control-plane，修复 Runtime 后再把 acceptance 纳入门禁；不能长期只跑控制面，因为它覆盖不到 pause/resume 恢复失败。

### UI 与文档存在滞后

- evaluations 页面仍有 M4-M8 口径。
- sidebar 文案仍有 M4-M6 口径。
- `docs/modules/evaluation-and-tests.md` 仍提到旧的 `suite_cases_part_a/b`。

这些不阻断本轮 Runtime 修复，但应在 M9 acceptance 稳定后一起更新，避免外部用户和后续 agent 按旧门禁理解项目状态。

## 修复顺序建议

1. 先修 worker lock miss 丢任务。范围小、风险高、可快速补测试。
2. 修 resume 合同：`command=resume` 不允许静默 start，恢复失败必须稳定落库；同时重写 corrupted snapshot 旧断言。
3. 修 M9 pause/resume finalization：恢复后 delivery gate 已通过时必须进入确定终态，不允许预算耗尽才失败。
4. 恢复 `tests/runtime/test_runtime_restart_and_resume.py`、`tests/runtime/test_runtime_pause_regressions.py`、`tests/runtime/test_runtime_budget_and_audit.py` 中仍符合新合同的用例，删除或重写旧合同用例。
5. 恢复 `tests/api/test_persistence_control_plane_api.py` 和 `tests/test_m9_acceptance.py`，把 M9 acceptance 从 debug plan 移回可执行验收。
6. 做队列 ack/visibility timeout、DB CAS、短事务、lock 续租/fencing。这是较大改造，应单独拆 PR。
7. 最后补 UI 文案、评测文档和 `release:check` 门禁，把 M9 acceptance 加回发布链。

## 并行性、合并冲突与前置依赖

| 工作包 | 并行性 | 合并冲突 | 前置依赖 |
|---|---|---|---|
| worker lock miss requeue | 高 | 低到中，集中在 worker/queue 测试 | 无 |
| resume 合同与 corrupted snapshot | 中 | 中，集中在 `execution_control.py`、`worker.py`、snapshot 测试 | 需要冻结“恢复失败硬失败”合同 |
| M9 finalization | 中 | 中到高，可能碰 `transitions.py`、takeover、M9 suite case | 依赖 resume 合同清晰 |
| 恢复 debug plan 跳过测试 | 中 | 中，多个测试文件 | 依赖前 2-3 项 |
| queue ack/visibility + outbox | 低 | 高，涉及队列、worker、任务 API | 建议等小修稳定后做 |
| UI/文档/release 门禁 | 高 | 低 | 依赖 M9 acceptance 稳定 |

## 本轮已完成与未完成

已完成：

- 拆分调查了并发与稳定性、Runtime 状态机与恢复链、M9 控制面与验收链。
- 使用子代理并结合本地代码检查交叉验证。
- 运行并记录 M9 control-plane、M9 acceptance、M9 专项 pytest 的当前结果。
- 明确 M9 acceptance 当前失败归因：Runtime pause/resume 后续状态收口与预算链，而不是资源控制面。
- 产出本调查基线，并同步目录索引。

未完成：

- 尚未修改 Runtime 或 worker 实现代码。
- 尚未恢复 debug plan 中被 skip 的测试。
- 尚未做 Docker/Postgres/Redis 多 worker 崩溃恢复实测。
- 尚未更新 M9 UI 文案、evaluation 文档和 release 门禁。
