# 任务停止、暂停、继续与恢复能力调查

日期：2026-06-18

范围：任务控制面、worker 队列、safe-stop / pause / resume / retry、预算耗尽续跑、snapshot 恢复、M9 pause/resume 验收链。

本文件是当前能力调查基线。正式目标语义已冻结到 [任务暂停、恢复与继续契约 v0.1](../specs/task-pause-resume-continuation-contract-v0.1.md)。后续实现应直接切到该合同，废旧 skip 和过宽断言应删除或重写。2026-06-18 追加决策：自动 snapshot 只保留最新一个，active-paused 永久保留，Resume 成功并写入新 durable progress 后删除旧 active snapshot，允许用户手动保存 snapshot 并从 user-saved snapshot 显式分支，本地不加密，Cancel audit 默认 30 天。

## 结论

1. 当前已经有可用的“安全停止/恢复”骨架：Core API、agent-runtime API、Web 任务详情页、runtime kernel、pause-resume 模块和 snapshot 表都已接通。
2. 当前没有成熟的“任务取消/强制终止”闭环。`cancel/cancelled/abort` 基本只停留在状态枚举或零散字符串层，缺少 API、worker、UI 和测试合同。
3. 当前最需要推进的不是新增按钮，而是把“恢复合同”变硬：resume 失败不能静默降级，预算耗尽不能把可恢复任务直接打 failed，队列消费不能 pop 后丢失。
4. 2026-06-18 实跑 `evalsuite_acceptance_m9_capabilities` 仍为 1/2 通过，失败 case 是 `evalcase_m9_pause_resume_memory_tree`；失败点仍是 pause/resume 后进入后续 continuation，最后在模型调用前预算检查报 `Token budget exceeded before the next execution step.`。
5. 多个关键端到端测试仍被 `DEBUG_PLAN_SKIP` 跳过。当前单元和控制面测试能证明入口存在，但还不能证明产品级停止/继续可靠。

## 当前能力矩阵

| 能力 | 当前入口 | 当前状态 | 主要缺口 |
| --- | --- | --- | --- |
| start | `POST /tasks/{taskId}/start`、`/runtime/tasks/{taskId}/start`、Web 任务启动 | 可入队 | DB 状态更新与 queue enqueue 非原子 |
| Pause | `POST /tasks/{taskId}/pause`、`/runtime/tasks/{taskId}/pause`、Web `Pause` / `Safe-Stop` | queued 直接生成 active-paused durable snapshot；running 设置 `pendingControlIntent=pause` 并等待 safe-stop | tool-call safe-stop 等价性仍需继续做更细粒度端到端覆盖 |
| safe-stop snapshot | `runtime_kernel/snapshot.py`、`pause-resume` hook、transition pause 分支 | 可生成 `restorable` snapshot，保留 context/root mount/pending actions | package entry 只有 24h TTL；DB 的 `restorable` 不等于 payload 一定可读 |
| resume | `POST /tasks/{taskId}/resume`、Web `从快照恢复` | API 层要求 paused + restorable snapshot，并重新入队 | worker 层仍有 resume 失败降级 start 的路径；rehydrate 失败也会 fallback |
| retry | `POST /tasks/{taskId}/retry`、Web `失败后重试` | failed 任务可带预算更新重新入队 | retry 不是 lossless resume，只是保留任务态重新执行 |
| 预算追加续跑 | Web `预算追加后无损续跑` | paused 走 resume，failed 走 retry | 模型调用后预算超限会 pause；模型调用前预算超限仍可能 failed |
| safe shutdown checkpoint | `SafeShutdownInterrupt` + `save_pending_tool_calls_snapshot()` | 代码支持 pending tool calls checkpoint | Windows `safe_shutdown.ps1` 只是 `taskkill`，未证明能触发进程内 graceful flag |
| approve / revision | `approve-completion` / `request-revision` | awaiting-approval 后可完成或打开修订 | 与 pause/resume 的终态收口仍在 M9 acceptance 暴露缺口 |
| cancel / abort | 无正式用户入口 | 不成熟 | 缺 API、状态机、worker 停止、UI、数据清理和测试 |

## 关键代码入口

控制面：

- `services/core-api/src/yggdrasil_core_api/api/routes/tasks.py`
- `services/core-api/src/yggdrasil_core_api/services/task_service.py`
- `services/core-api/src/yggdrasil_core_api/services/runtime_service.py`
- `services/agent-runtime/src/yggdrasil_agent_runtime/app.py`

runtime：

- `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_control.py`
- `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop/worker.py`
- `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop/transitions.py`
- `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/snapshot.py`
- `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/root_mount.py`
- `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/shutdown_control.py`

队列和 worker：

- `services/worker/src/yggdrasil_worker/registry.py`
- `services/worker/src/yggdrasil_worker/main.py`
- `packages/python-sdk/src/yggdrasil_sdk/persistence/coordination.py`

模块与 UI：

- `modules/pause-resume/src/yggdrasil_pause_resume/plugin.py`
- `apps/web/app/components/task-detail-page.tsx`

## 当前验证结果

```powershell
uv run pytest tests\test_m9_pause_resume.py -q
```

结果：`1 passed`。

```powershell
uv run pytest tests\runtime\test_runtime_pause_regressions.py -q
```

结果：`3 passed, 1 skipped`。被跳过项是 pause 请求与 worker 启动竞态回归。

```powershell
uv run pytest tests\api\test_persistence_control_plane_api.py -q
```

结果：`2 passed, 1 skipped`。控制面任务动作可用，但仍有控制面/M9 相关 skip。

```powershell
uv run pytest tests\api\test_persistence_task_runtime_api.py -q
```

结果：`8 passed`。

```powershell
uv run pytest tests\runtime\test_runtime_restart_and_resume.py::test_runtime_retry_failed_task_requeues_with_updated_budget -q
```

结果：`1 passed`。

```powershell
uv run pytest tests\test_m9_acceptance.py -q -rs
```

结果：`1 skipped`，原因是 `Moved to debug plan 2026-06-08: M9 acceptance capability chain`。

```powershell
uv run python -m yggdrasil_sdk.evaluation_cli run --suite evalsuite_acceptance_m9_capabilities
```

结果：`failed`，`passRate = 0.5`，运行记录为 `.yggdrasil/state/evaluations/evalrun_ce8f8bb4b72b4e49a189.json`。`evalcase_m9_shared_multimodal_reasoning` 通过，`evalcase_m9_pause_resume_memory_tree` 失败。

## M9 pause/resume 当前失败链

失败不是“没有生成 snapshot”，也不是“没有恢复上下文”。失败链如下：

1. `m9.pause_resume_memory_tree` case 创建任务，预算为 `tokenBudgetTotal=1400`。
2. start 后立即 pause，worker 执行后生成 safe-stop snapshot，状态进入 `paused`。
3. resume 请求成功入队，worker 消费 snapshot，rehydrate context/root mount/pending actions，并将 snapshot 标记为 `consumed`。
4. 恢复后固定响应已经包含 `## 结果 / ## 证据 / ## 风险 / ## 已知问题`，delivery verification 通过。
5. 但 work tree 继续按子节点链路推进，至少完成第一个 child 后继续排后续 continuation。
6. 下一轮执行在 `execution_loop/worker.py` 的模型调用前预算检查触发 `_enforce_budget()`，抛出 `Token budget exceeded before the next execution step.`。
7. 该异常走 outer failure handler，任务被标记为 `failed`，M9 acceptance 报 `m9 resume completion failed`。

这说明当前 P0 不是 provider 问题，而是恢复后 finalization / continuation / 预算门禁的合同没有统一。

## 设计风险

### P0：queue pop-before-process 会丢 work item

`RedisCoordinator.pop_job()` 使用 `LPOP/BLPOP` 后直接返回 payload。`run_worker_once()` 再 dispatch。worker 在 pop 后、落库前崩溃时，work item 已从队列消失。

目标合同：

- 消费必须有 processing / pending / ack 语义。
- 完成后 ack。
- 超时未 ack 的 work item 可 reclaim。
- task lock miss 不能算处理成功，必须 requeue 或延迟重试。

### P0：模型调用前预算超限仍是 failed

模型调用后预算超限已有 `paused + restorable snapshot` 路径；模型调用前预算超限仍直接抛异常并进入 failed。对长任务恢复链而言，这会把“需要追加预算继续”的可恢复状态误判成失败。

目标合同：

- pre-invocation budget exhausted 也应生成 restorable snapshot 或明确进入 `paused`。
- `runtimeControl.canTopUp` 应能覆盖这一类暂停。
- M9 acceptance 不应因为预算追加点前移而失败。

### P0：resume 不能静默 fallback start

API 层已经校验 paused + restorable snapshot，但 worker 层仍存在 snapshot 不可用时把 `command=resume` 改成 `start` 的路径；rehydrate hook 失败也会 fallback。

目标合同：

- `command=resume` 失败必须显式失败，并落 snapshot blocker / task currentFocus。
- 不允许恢复失败后悄悄按 start-state 执行。
- `restorable` 必须代表 payload 可读；payload 丢失时要标记不可恢复。

### P1：pause 状态合同需要收紧

合理合同应区分三种情况：

- `queued`：取消未 claim work item，立即生成 `pre-start + active-paused` durable snapshot，进入 `paused`。
- `running`：保持 `running`，设置 `pendingControlIntent=pause`，等待下一次 safe-stop。
- `running + pendingControlIntent=pause`：幂等。
- `draft/completed/failed/cancelled/awaiting-approval/paused`：应返回冲突或引导使用 start/resume/retry/approve/revision，不应继续写 `pauseRequested=true`。

### P1：safe shutdown 脚本与进程内 graceful flag 未打通

`shutdown_control.py` 提供进程内 flag，worker 注册 SIGTERM/SIGINT handler；`scripts/safe_shutdown.ps1` 当前实际执行 `taskkill /PID /T`，注释与行为不一致。Windows 下是否能走到 `SafeShutdownInterrupt` 并保存 pending-tool-calls checkpoint 尚未由端到端测试证明。

目标合同：

- Windows stop 脚本必须发送可被 Python handler 捕获的信号，或改为调用正式 runtime shutdown endpoint。
- 测试要覆盖 pending tool calls checkpoint 在 worker 停机时可恢复。

### P1：cancel / abort 缺失

当前 safe-stop 是“可恢复暂停”，不是“用户取消任务”。如果要推进“任务停止”，需要明确两条语义：

- Safe-Stop：保留现场，目标是继续。
- Cancel：终止任务，清理或保留可审计记录，不再继续。

Cancel 需要独立 API、状态迁移、worker 协作中断、UI 按钮、审计事件和测试，不能复用 pause 的字段糊过去。

## 推进顺序

### 阶段 1：契约与数据模型收口

目标：先把“隔天/长期继续”变成数据契约，不再让实现沿用短期 Redis TTL 恢复口径。

1. 以 [任务暂停、恢复与继续契约 v0.1](../specs/task-pause-resume-continuation-contract-v0.1.md) 为实现来源，更新 runtime domain schema。
2. 新增 `TaskResumeAttempt`、持久 `WorkItem`、Durable Snapshot manifest schema、snapshot retention class 和 `TaskBranch`。
3. 将 `restart-requested` / `restarting` 移出普通用户状态机，只保留 legacy/stress 入口。
4. 明确 `paused`、`resume-blocked`、`cancelling`、`cancelled` 的状态流转和 API 冲突返回。
5. 删除或重写仍把 legacy restart 当作主续跑能力的测试。

完成门槛：

```powershell
uv run pytest tests\runtime\test_runtime_pause_regressions.py tests\runtime\test_runtime_restart_and_resume.py -q
```

### 阶段 2：Durable Snapshot 与 ResumeAttempt

目标：暂停现场能跨天、跨重启、跨 Redis 清空、跨产品备份恢复继续。

1. 把 pause snapshot payload 从 Redis TTL package 迁到持久 snapshot store。
2. 实现 manifest、checksum、原子提交和 active snapshot 绑定。
3. `command=resume` 不允许降级 start；rehydrate 失败写 blocker 并进入 `resume-blocked`。
4. Resume attempt 使用 lease，不在 worker claim 时立刻消费 snapshot。
5. 模型调用前预算超限也必须进入 `paused + safeStopReason=budget-exhausted` 或明确 blocker。

完成门槛：

- Pause 后清空 Redis，Resume 仍成功。
- Resume claim 后 worker 崩溃，lease 到期后仍能 Resume。
- manifest 损坏时进入 `resume-blocked`，不得 Start。
- 产品 backup/restore 后 active snapshot 可 Resume。
- Resume 成功后旧 active snapshot 在新 durable progress 写入后被删除或 consumed；user-saved snapshot 不被自动清理。

### 阶段 3：worker 队列可靠性

目标：停止/继续过程不丢 work item。

1. 用持久 WorkItem + lease 替换 pop-before-process，Redis 只做 wakeup。
2. `run_worker_once()` 对 lock miss 返回 requeue/delayed retry，不当作 processed。
3. start/resume/retry/revision 的 DB 更新与 enqueue 通过 outbox 或补偿扫描闭环。
4. task lock 增加 lease 续租或 fencing token，避免长执行超过 TTL 后双 worker 写同一任务。

完成门槛：

- 两个 worker 抢同一 task 不丢 job。
- worker pop 后模拟崩溃，超时后 job 可 reclaim。
- queued-but-not-enqueued task 可被补偿恢复。
- Redis 丢失不会丢失权威 work item。

### 阶段 4：正式 cancel / abort

目标：把“暂停继续”和“终止取消”拆开。

1. 新增 `POST /tasks/{taskId}/cancel` 和 `/runtime/tasks/{taskId}/cancel`。
2. 定义状态迁移：queued/running/paused 可 cancel；completed/cancelled 幂等；failed 可标记 closed 或保持 failed。
3. worker 在每轮安全点读取 cancel flag；若有 active tool call，走可审计中断或等待安全点。
4. Web 任务详情页新增取消入口，文案必须区分 Safe-Stop 与 Cancel。
5. 增加审计事件 `task.cancel.requested` / `task.cancelled`。

完成门槛：

- cancel queued 任务不会执行。
- cancel running 任务停在安全点并不生成可恢复 resume token，除非明确选择“取消前保留快照”。
- cancel 后 resume/retry/start 都给明确冲突。

### 阶段 5：M9 验收、用户文档和发布门禁

目标：M9 pause/resume 不再是短进程恢复，而是长期恢复门禁。

1. 恢复或重写 `tests/test_m9_acceptance.py`，不要继续整体 skip。
2. M9 acceptance 增加 Redis 清空、worker crash/reclaim、backup/restore 的恢复断言。
3. 补 tool-call streaming 中 pause request 的等价性测试：drain 到 safe-stop 后，下一次 canonical request digest 与无暂停路径一致，或进入明确 blocker。
4. 补 user-saved snapshot 创建分支测试，确认父/子任务状态和 snapshot 不互相覆盖。
5. `docs/USER_GUIDE.md` 将 pause/resume 标成“长期恢复已过门禁”或继续标注“预览”，不能模糊承诺。
6. `docs/DEVELOPER_GUIDE.md` 标明关键测试是否仍有 skip，修复后逐个恢复。
7. release/nightly 门禁明确是否包含 M9 acceptance。
8. 删除或重写不符合新合同的废旧测试，不保留过渡断言。

## 下一步建议

最短可推进切口：

1. 先落 Durable Snapshot manifest、TaskResumeAttempt、snapshot retention class、TaskBranch 和持久 WorkItem 的 schema / migration。
2. 再把 snapshot payload 从 Redis TTL package 迁到持久 snapshot store。
3. 然后改 Resume：不得 fallback start，claim 不消费 snapshot，失败进入 `resume-blocked`。
4. 最后恢复 M9 acceptance，并把“隔天/长期继续”作为发布门禁。

不要先做的事：

- 不要先增加更多 UI 按钮；当前问题不是入口少。
- 不要先只修单个预算报错；预算前检问题要在 Durable Snapshot 恢复合同下统一收口。
- 不要把 M9 acceptance 的预算单纯调大来掩盖 runtime precheck 问题；可以作为临时诊断，但不能作为修复。
- 不要继续保留大范围 skipped “旧债清单”；每个 skip 应被恢复、重写或删除。
