# 工作树图与 Fork 并行实现计划（2026-06-21）

- 文档状态：Candidate
- 前置规格：`docs/specs/work-tree-graph-fork-parallel-protocol-v0.1.md`
- 测试任务：`docs/development/WORK_TREE_GRAPH_FORK_EVALUATION_TASKS_2026_06_21.md`
- 范围：工作树图 ready-set、延迟信息流索引、Fork 自我分裂并行、递归 Fork 同时活跃上限
- 非范围：多线程冲突处理、全局跨任务调度、UI 完整可视化

## 1. 实现结论

第一版应按“先纯函数语义，后 runtime 接线，再真实 worker 并行”的顺序实现。

不要先改 UI，也不要先接真实 LLM 并发。必须先让工作树图在纯函数里可复现地回答：

1. 哪些 child ready。
2. 哪些 child blocked，阻塞原因是什么。
3. 哪些信息流材料应该作为摘要、归类和原文引用挂到目标节点。
4. 当前 fork tree 还能启动多少个 Fork run。
5. 自动启动下一批还是回父节点编排。

随后再把这个结果接到 `AgentRun`、`RuntimeWorkItem`、snapshot / request payload 和 worker 执行循环。

## 2. 当前代码承载点

现有代码已经具备一部分承载能力：

| 能力 | 当前承载 | 计划处理 |
| --- | --- | --- |
| 工作树节点 | `WorkTreeNode` 已有 `parentNodeId`、`childNodeIds`、`dependsOn`、`relationIds`、`priority`、`assignedAgentRunId` | 直接使用，不重建第二套任务图 |
| 工作树快照 | `WorkTreeProtocol` 已随 takeover protocol / prompt artifact / snapshot 进入运行时 | 继续作为任务唯一真源 |
| Agent run | `agent_runs` 已有 `runType`、`parentRunId` | 扩字段承载 Fork 元数据，不用 subagent branch |
| work item | `RuntimeWorkItem` payload 已能带任意 JSON | 用于 queue fork run，后续补 schema 校验 |
| worker | `execute_main_agent_work_item` 已按 payload 构造 request / run | 扩展为识别 `runType=fork` 与 child 焦点 |
| 上下文缓存 | snapshot manifest、request current context、prompt artifact 已能保留上下文 | 增加 `parentContextAnchor` 证明 Fork 共享父上下文锚点 |

需要新增的不是一套新任务系统，而是工作树上的局部图投影和 Fork run 视图。

## 3. 数据与合同调整

### 3.1 新增 Pydantic 合同

建议新增 `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/work_tree_graph.py`，先放纯函数模型和 reducer，避免把图计算塞进 worker。

核心对象：

- `WorkTreeReadySetInput`
- `WorkTreeReadyChild`
- `WorkTreeBlockedChild`
- `WorkTreeReadySetResult`
- `PendingInformationItem`
- `ForkLaunchPolicy`
- `ForkLaunchCandidate`
- `ForkBatchPlan`

这些对象第一版可以是 runtime-kernel 内部合同，不急着放到全局 `contracts.py`。只有当 API 或 prompt artifact 需要稳定暴露时，再提升到 `contracts.py`。

### 3.2 AgentRun 持久字段

`AgentRun` 需要直接识别 Fork，而不是把 Fork 伪装成 Sub-Agent。

建议迁移新增：

| 字段 | 类型 | 用途 |
| --- | --- | --- |
| `fork_root_run_id` | nullable string | 同一个 fork tree 的根 run |
| `fork_depth` | integer default 0 | 递归 Fork 深度，main 为 0 |
| `assigned_work_tree_node_id` | nullable string | 此 Fork 负责的 child |
| `parent_context_anchor` | nullable string | 父上下文缓存锚点 |
| `fork_group_id` | nullable string | 一批 sibling Fork 的批次 id |

必须同步：

- `packages/python-sdk/src/yggdrasil_sdk/persistence/orm.py`
- `packages/python-sdk/src/yggdrasil_sdk/contracts.py` 中的 `AgentRunRecord`
- `packages/python-sdk/src/yggdrasil_sdk/persistence/repositories/task.py`
- `packages/python-sdk/src/yggdrasil_sdk/persistence/repositories/_records.py`
- migration 文件

不建议只把这些值塞到 work item payload 里。payload 可用于启动，但 run 级审计、恢复、活跃 Fork 计数需要数据库真源。

### 3.3 WorkTreeNode 不做破坏性 schema 迁移

`WorkTreeNode` 已有 `relationIds`，第一版不新增复杂 relation 表。信息流延迟传递先放在 runtime graph result / request payload / takeover protocol 附加状态中。

如果实现时发现需要持久 pending 信息，优先新增工作树级附加字段：

```text
WorkTreeProtocol.graphState.pendingInformationItems
```

不要把大段原文塞进父节点。pending item 只存摘要、归类、来源、关系类型、目标 node、原文/证据引用和状态。

## 4. 实现批次

### Batch 0：冻结入口与删除旧口径

目标：防止新设计被旧 sibling continuation 或 subagent 路径吞掉。

动作：

1. 搜索当前 `continue-sibling`、`subagent`、`runType`、`parentRunId`、`dependsOn` 使用点。
2. 标出会与 Fork 语义冲突的旧路径。
3. 不保留“Fork 走 subagent task/branch”的兼容路径。
4. 给 implementation plan 下游任务补明确非目标。

验收：

- 有代码落点清单。
- 明确 Fork 不创建 subagent task，不创建 subagent branch。

### Batch 1：纯函数工作树图核心

目标：先让 T0/T2/T3/T4/T5/T7 在无 worker 状态下跑通。

主要文件：

- 新增 `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/work_tree_graph.py`
- 新增 `tests/runtime/test_work_tree_graph_scheduler.py`

实现：

1. `compute_parent_ready_set(work_tree, parent_node_id, active_runs, graph_state, policy)`。
2. `dependsOn` 硬阻塞。
3. `relationIds` 只影响信息流和检索提示，不阻塞。
4. `priority` 只在同父 ready-set 内排序。
5. `pendingInformationItems` 只保存摘要、归类和引用。
6. `maxForks` 按 running / mounting / waiting-tool 的 Fork run 同时活跃数计算。
7. completed / failed / aborted 不占用槽位。

验收：

- T0 Ready-Set Diamond 通过。
- T2 Delayed Information Flow 通过。
- T3 Auto Batch Pipeline 的 candidate ready-set 可计算。
- T4 Parent Replan Gate 能输出阻断原因。
- T7 Recursive Fork Active Limit 通过。

### Batch 2：Fork run 数据迁移与 repository 接线

目标：让数据库能审计和恢复 Fork，不依赖 transient payload。

主要文件：

- `packages/python-sdk/src/yggdrasil_sdk/persistence/orm.py`
- `packages/python-sdk/src/yggdrasil_sdk/contracts.py`
- `packages/python-sdk/src/yggdrasil_sdk/persistence/repositories/task.py`
- `packages/python-sdk/src/yggdrasil_sdk/persistence/repositories/_records.py`
- `migrations/versions/*_agent_run_fork_fields.py`
- `tests/api/test_persistence_task_runtime_api.py`

实现：

1. `create_agent_run` 支持 `runType=fork`。
2. `create_agent_run` 接收 `forkRootRunId`、`forkDepth`、`assignedWorkTreeNodeId`、`parentContextAnchor`、`forkGroupId`。
3. `list_agent_runs` 返回这些字段。
4. 增加 repository 查询活跃 Fork 数：按 task + forkRootRunId + runType=fork + status in active。
5. 不允许 `runType=fork` 同时创建 subagent branch。

验收：

- fork run 可创建、读取、更新为 completed / failed / aborted。
- 活跃 Fork 数只统计 running / mounting / waiting-tool / initializing。
- completed / failed / aborted 释放槽位。

### Batch 3：Fork batch launch planner

目标：把 ready-set 转成可排队的 Fork run，但仍不先接真实模型输出。

主要文件：

- 新增 `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/fork_runtime.py`
- 修改 `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_control.py`
- 修改 `services/worker/src/yggdrasil_worker/registry.py` 仅在需要新 activity 时调整
- 新增 `tests/runtime/test_fork_launch_planner.py`

实现：

1. `plan_fork_batch(ready_set, policy, active_fork_count)`。
2. 生成同一个 `parentContextAnchor`。
3. 每个 Fork candidate 绑定不同 `assignedWorkTreeNodeId`。
4. 创建 `runType=fork` 的 `AgentRun`。
5. 创建 `RuntimeWorkItem`：

```text
activity = core.agent.main.execute
intent = fork
payload.runType = fork
payload.parentRunId = <direct parent run>
payload.forkRootRunId = <root fork run>
payload.forkDepth = <depth>
payload.assignedWorkTreeNodeId = <child node>
payload.parentContextAnchor = <anchor>
payload.activeForkCount = <count>
payload.availableForkSlots = <slots>
```

6. `maxForks` 到顶时，planner 只产生可启动数量，剩余 child 标记为 waiting-slot / serial-candidate / needs-parent-strategy。

验收：

- T1 Fork Context Anchor 通过。
- T5 Mixed Fork Outcome 的部分完成、部分阻塞状态可表达。
- T7 递归 Fork 到达 `maxForks` 后不得继续排队。

### Batch 4：worker 运行视图与 prompt artifact

目标：Fork run 真实进入 worker 后，看到父上下文缓存 + child 执行焦点，而不是 subagent prompt。

主要文件：

- `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop/worker.py`
- `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/takeover.py`
- `packages/python-sdk/src/yggdrasil_sdk/persistence/repositories/prompting.py`
- `tests/runtime/test_fork_worker_view.py`

实现：

1. worker 识别 `payload.runType=fork`。
2. 创建 AgentRun 时 `runType=fork`，`parentRunId` 指向直接父 run。
3. request 中注入 child 焦点：
   - `currentNodeId`
   - `workTreeNodeId`
   - `topFrameId`
   - `workingNodeAnnotation`
   - `assignedWorkTreeNodeId`
4. WorkContextStack 运行视图切到 assigned child，但 task 级全局 current pointer 不被多个 Fork 相互覆盖。
5. prompt artifact 记录 `runType=fork`、work tree snapshot、assigned node 和 `parentContextAnchor`。
6. 如果父上下文无法重建或超过窗口，不自动压缩；降级为串行或 parent replan。

验收：

- 三个 Fork 的 prompt artifact 使用同一 `parentContextAnchor`。
- 三个 Fork 的 `currentNodeId/topFrameId` 指向不同 child。
- task 级工作树全局 current pointer 不被 Fork 并发覆盖。

### Batch 5：Fork 结果合并与第 n+1 批调度

目标：Fork 子体完成后只写 child 结果和建议，父节点负责合并和重排。

主要文件：

- `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop/transitions.py`
- `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop/state_memory.py`
- `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/work_tree_graph.py`
- `tests/runtime/test_fork_merge_and_auto_batch.py`

实现：

1. Fork 完成时写入 child `executionSummary`、`producedEvidenceRefs`、`failureSummary`。
2. 生成 `ForkResultEnvelope`：
   - `assignedWorkTreeNodeId`
   - `summary`
   - `evidenceRefs`
   - `planImpact`
   - `proposedDependencyChanges`
   - `proposedRelationChanges`
   - `pendingInformationItems`
3. `planImpact=none` 且 policy 允许时，程序自动计算下一批 ready-set。
4. `requires-parent-replan` 时禁止自动启动，回父节点编排。
5. 信息流只向目标父节点挂 pending item，后续 child 创建后再读取摘要和归类。

验收：

- T3 自动启动下一批通过。
- T4 需要父节点重排时不会自动启动。
- T5 mixed outcome 后只启动满足条件的后续节点。
- T6 信息爆炸保护通过。

### Batch 6：runtime debug harness 与慢测试

目标：证明真实 runtime 链路不是只在 reducer 里成立。

主要文件：

- `tests/runtime/test_work_tree_graph_fork_runtime_harness.py`
- `evaluation/suites/*work-tree-fork*.json`
- 需要时补 `scripts/*fork*` 调试脚本

实现：

1. 构造固定 work tree fixture。
2. 通过 runtime work item 模拟 Fork batch。
3. 不调用 live provider，使用 deterministic model output / fake invocation。
4. 校验 AgentRun、work item、prompt artifact、work tree snapshot、pending 信息流。

验收：

- L2 harness 能证明 run 级元数据、prompt artifact 和 work tree 指针一致。
- nightly 再接真实 provider 或较长任务。

## 5. 测试矩阵

| 测试 | 批次 | 默认 CI | 目的 |
| --- | --- | --- | --- |
| T0 Ready-Set Diamond | Batch 1 | 是 | 控制流和信息流分离 |
| T1 Fork Context Anchor | Batch 3/4 | 是 | Fork 不是 Sub-Agent |
| T2 Delayed Information Flow | Batch 1/5 | 是 | pending 信息流延迟传递 |
| T3 Auto Batch Pipeline | Batch 1/5 | 是 | 程序算 ready-set，policy 决定自动启动 |
| T4 Parent Replan Gate | Batch 1/5 | 是 | 改图必须回父节点 |
| T5 Mixed Fork Outcome | Batch 3/5 | 是 | 部分完成、部分阻塞的合并 |
| T6 Information Explosion Guard | Batch 5 | 是 | 父节点不积累大段原文 |
| T7 Recursive Fork Active Limit | Batch 1/3 | 是 | Fork 子体可继续 Fork，`maxForks` 是同时活跃上限 |
| R1-R4 | Batch 6 | slow / nightly | 接近真实任务收益 |

## 6. 默认策略值

第一版使用以下默认值：

```text
maxForks = 3
allowRecursiveFork = true
autoLaunchPolicy = explicit-policy-gated
readySetScope = direct-children-only
pendingInformationRetention = summary-category-ref-only
```

`maxForks` 只表示同一个任务 / fork tree 内同时活跃 Fork run 上限。历史已完成 Fork 不占用槽位。

## 7. 风险与防错点

### 7.1 把 Fork 做成 Sub-Agent

风险：实现时复用 subagent task / branch 入口，导致 Fork 丢失父 Agent 上下文和判断倾向。

防错：

- `runType=fork` 必须记录在 `AgentRun`。
- 不创建 child task。
- 不创建 subagent branch。
- prompt artifact 必须证明 `parentContextAnchor` 相同。

### 7.2 Fork 并发覆盖 task-global current pointer

风险：多个 Fork 同时改写 `WorkTreeProtocol.currentNodeId`。

防错：

- Fork 使用 run-local execution view。
- task-level work tree 只由父节点合并阶段提交。
- Fork 子体只能写 assigned child 的结果和 proposal。

### 7.3 ready-set 自动化越权

风险：程序计算 ready-set 后直接替父节点做语义编排。

防错：

- reducer 只输出 candidate ready-set / blocked-set。
- 自动启动必须通过 `autoLaunchPolicy`。
- `planImpact=requires-parent-replan` 一律阻断自动启动。

### 7.4 信息流上浮过重

风险：父节点 pending 信息积累大量原文，拖垮上下文。

防错：

- pending item 只存摘要、归类、来源、关系类型、状态、原文/证据引用。
- child 只默认看到摘要和归类，自行决定是否读取原文。

### 7.5 `maxForks` 被误实现为累计上限

风险：Fork 子体继续 Fork 后，历史完成的 Fork 仍占槽，导致并行能力越来越小。

防错：

- 只统计 active statuses。
- completed / failed / aborted 必须释放槽位。
- T7 作为默认 CI 测试。

## 8. 推荐 PR 切分

### PR 1：graph reducer + T0/T2/T3/T4/T7

只加纯函数和测试，不碰 worker。

### PR 2：AgentRun Fork 字段 + repository 查询

加 migration、contracts、repository 和持久化测试。

### PR 3：Fork launch planner + work item payload

把 ready-set 转成 ForkBatchPlan 和 queued work item，不接真实模型。

### PR 4：worker Fork run view + prompt artifact

让 `runType=fork` 真实执行，验证上下文锚点和 child 焦点。

### PR 5：result merge + auto batch + pending 信息流

接第 n+1 批调度和父节点重排门禁。

### PR 6：runtime harness + nightly 真实任务

证明端到端链路和收益，不作为默认 PR 的硬依赖。

## 9. 第一批编码入口

建议下一轮直接做 PR 1：

1. 新建 `work_tree_graph.py`。
2. 写 T0/T2/T3/T4/T7 fixture。
3. 先让 reducer 测试过。
4. 再决定 pending 信息流字段是否需要进入 `WorkTreeProtocol.graphState`。

这样风险最小：即使后续 worker 接线要调整，ready-set、信息流、`maxForks` 语义也已经被测试锁住。

## 10. 实施进展（2026-06-21）

已完成 PR 1 / Batch 0-1 的第一版代码落点：

1. 新增 `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/work_tree_graph.py`。
2. 新增 `tests/runtime/test_work_tree_graph_scheduler.py`。
3. 已用纯函数 reducer 锁住 T0/T2/T3/T4/T7 的核心语义：
   - `dependsOn` 是硬控制流阻塞。
   - `relationIds` 只影响 pending 信息流，不阻塞 ready-set。
   - `priority` 只在同父 direct child ready-set 内排序。
   - `pendingInformationItems` 只暴露摘要、归类和引用。
   - `maxForks` 只统计 `initializing` / `mounting` / `running` / `waiting-tool` 的 `runType=fork` 活跃 run；completed / failed / aborted / skipped 不占槽。
4. 已明确 PR1 非目标：
   - 不走 `launch_subagent_task()`。
   - 不创建 subagent task。
   - 不创建 subagent branch。
   - 不走 `core.agent.subagent.execute`。
   - 不改 `AgentRunORM`、repository、migration。
   - 不改 worker 的真实执行路径。
   - 不切换 task-global `WorkTreeProtocol.currentNodeId`。

当前仍未完成：

1. Batch 6：deterministic runtime debug harness 已完成；slow/nightly live provider 真实链路证据仍待单独跑。

本轮验证命令：

```powershell
uv run pytest tests/runtime/test_work_tree_graph_scheduler.py -q --basetemp=tmp/pytest-work-tree-graph
uv run python -m compileall packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/work_tree_graph.py tests/runtime/test_work_tree_graph_scheduler.py
```

## 11. Batch 2 实施进展（2026-06-21）

已完成 AgentRun Fork 字段与 repository 接线：

1. `packages/python-sdk/src/yggdrasil_sdk/persistence/orm.py`
   - `agent_runs` 新增 `fork_root_run_id`、`fork_depth`、`assigned_work_tree_node_id`、`parent_context_anchor`、`fork_group_id`。
2. `packages/python-sdk/src/yggdrasil_sdk/domain.py`
   - `AgentRunRecord.runType` 正式允许 `fork`。
   - `AgentRunRecord` 暴露 `forkRootRunId`、`forkDepth`、`assignedWorkTreeNodeId`、`parentContextAnchor`、`forkGroupId`。
3. `packages/python-sdk/src/yggdrasil_sdk/persistence/repositories/_records.py`
   - `_agent_run_record()` 已映射 5 个 Fork 字段。
4. `packages/python-sdk/src/yggdrasil_sdk/persistence/repositories/task.py`
   - `create_agent_run()` 接收并持久化 5 个 Fork 字段。
   - `update_agent_run()` 可更新 5 个 Fork 字段。
   - 新增 `count_active_fork_runs(task_id, fork_root_run_id=None)`，只统计 `initializing` / `mounting` / `running` / `waiting-tool` 的 `runType=fork`。
5. `migrations/versions/c2f4b8a91d63_agent_run_fork_fields.py`
   - 为 `agent_runs` 增加 Fork 字段与 `fork_root_run_id`、`assigned_work_tree_node_id`、`fork_group_id` 索引。
6. `tests/api/test_persistence_task_runtime_api.py`
   - 新增 repository 与 Core API 回归，验证 Fork 字段创建、读取、更新与 active count 释放。

当前仍未完成：

1. Batch 6：deterministic runtime harness 已完成；slow/nightly live provider 真实链路已补入口，未开启 live 开关时记录为 blocked，开启 `YGGDRASIL_FORK_RUNTIME_LIVE=1` 后已取得真实 LongCat provider evidence。
2. `runType=fork` 的必填字段策略已收紧为 repository 硬校验。

本轮验证命令：

```powershell
uv run pytest tests/api/test_persistence_task_runtime_api.py -q -k "fork_agent_run_fields" --basetemp=tmp/pytest-fork-run-fields
uv run pytest tests/runtime/test_work_tree_graph_scheduler.py -q --basetemp=tmp/pytest-work-tree-graph
uv run alembic heads
```

## 12. Batch 3 实施进展（2026-06-21）

已完成 Fork batch launch planner 的第一版 runtime helper：

1. `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/fork_runtime.py`
   - 新增 `queue_fork_batch()`。
   - 输入 `WorkTreeReadySetResult`、policy、parent run、task repository。
   - 复用 `plan_fork_batch()`，只为可用槽位创建 Fork。
   - 每个 launch candidate 创建一个 `runType=fork` 的 `AgentRun`，状态为 `initializing`。
   - 每个 launch candidate 创建一个 `RuntimeWorkItem`：
     - `activity = core.agent.main.execute`
     - `intent = fork`
     - 顶层 payload 与嵌套 `payload` 都带 `runType=fork`、`parentRunId`、`forkRootRunId`、`forkDepth`、`assignedWorkTreeNodeId`、`parentContextAnchor`、`forkGroupId`、`activeForkCount`、`availableForkSlots`。
   - 同一批 sibling Fork 使用同一个 `parentContextAnchor` 和 `forkGroupId`。
   - 明确不走 `core.agent.subagent.execute`。
2. `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/__init__.py`
   - 导出 `queue_fork_batch()`。
3. `tests/runtime/test_fork_launch_planner.py`
   - 覆盖已有 1 个 active Fork、`maxForks=3` 时只排队 2 个新 Fork，第 3 个 ready child 留在 waiting candidates。
   - 验证 work item 走 main activity + fork intent，不走 subagent activity。

当前仍未完成：

1. Batch 6 deterministic runtime harness 已实现；slow/nightly live provider 真实链路尚未跑证据。
2. `queue_fork_batch()` 直接调用时仍只创建 DB work item；真实 fork 完成路径已在 `transitions.py` 中对自动下一批执行 Redis enqueue。

本轮验证命令：

```powershell
uv run pytest tests/runtime/test_fork_launch_planner.py -q --basetemp=tmp/pytest-fork-launch
```

## 13. Batch 4 实施进展（2026-06-21）

已完成 worker Fork run view 的第一版接线：

1. `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop/worker.py`
   - 识别 `runType=fork`。
   - 从 `assignedWorkTreeNodeId` / `workTreeNodeId` / `currentNodeId` 派生 run-local child 指针。
   - 为 fork 请求补齐 `assignedWorkTreeNodeId`、`workTreeNodeId`、`currentNodeId`、`topFrameId`、`workingNodeAnnotation` 和 `memoryRetrievalState.workTreeNodeId`。
   - 若 `queue_fork_batch()` 已预创建 fork AgentRun，worker 会更新该 run，而不是再次创建同 id run。
   - fork 不再自动生成 root takeover protocol，也不通过 takeover preview 覆盖 child 指针。
2. `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop/transitions.py`
   - fork 完成时只完成自身 AgentRun 和窗口写入，不把 task-global `status` / `currentFocus` / snapshot 指针推进为主线完成态。
3. `tests/runtime/test_fork_launch_planner.py`
   - 新增 worker 消费 fork work item 回归，锁住 child 视图、父上下文锚点、预创建 fork run 复用，以及父任务焦点不被 fork 覆盖。

当前仍未完成：

1. Batch 6 deterministic runtime harness 已实现；slow/nightly live provider 真实链路和长任务证据仍未完成。

本轮验证命令：

```powershell
uv run pytest tests/runtime/test_fork_launch_planner.py -q --basetemp=tmp/pytest-fork-launch
uv run pytest tests/runtime/test_fork_launch_planner.py tests/runtime/test_work_tree_graph_scheduler.py tests/api/test_persistence_task_runtime_api.py -q -k "fork_launch or worker_consumes_fork or work_tree_graph or fork_agent_run_fields" --basetemp=tmp/pytest-fork-batches
```

## 14. Batch 5 实施进展（2026-06-21）

已完成 Fork result merge 与 auto next batch 的第一版 helper 合同：

1. `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/fork_runtime.py`
   - 新增 `ForkResultEnvelope`。
   - 新增 `ForkMergeAndBatchResult`。
   - 新增 `merge_fork_result_and_plan_next_batch()`。
   - Fork 完成时可把 `assignedWorkTreeNodeId` 对应 child 写成 `completed` / `failed`，同步 `executionSummary`、`failureSummary`、`producedEvidenceRefs` 和 `assignedAgentRunId`。
   - `planImpact=none` 且 ready-set 允许时，复用 `queue_fork_batch()` 创建第 n+1 批 DB work item。
   - `requires-parent-replan` 或 pending 信息触发 parent replan 时，不自动排下一批。
   - `pendingInformationItems` 使用结构化 Pydantic 合同，`extra=forbid`，防止把大段原文塞进 parent pending 信息。
2. `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/__init__.py`
   - 导出 `ForkResultEnvelope`、`ForkMergeAndBatchResult`、`ForkRuntimeBatchResult`、`QueuedForkRun` 和 `merge_fork_result_and_plan_next_batch()`。
3. `tests/runtime/test_fork_merge_and_auto_batch.py`
   - 覆盖 T3：`planImpact=none` 后自动创建下一批 fork DB work item。
   - 覆盖 T4/T6：`requires-parent-replan` 禁止自动启动，pending 信息拒绝额外 raw content。
   - 覆盖 T5：mixed outcome 后失败依赖链保持 blocked，只启动仍满足条件的 ready child。
4. `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop/worker.py`
   - 清理 ruff 暴露的既有 `F601` 重复字典键，保留原 payload 语义。

2026-06-22 继续完成 Batch 5 后半：

1. `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/fork_runtime.py`
   - `queue_fork_batch()` 新增可选 `work_tree`、`parent_node_id`、`auto_launch_next_batch`，把 `forkMergeContext` 写入 fork work item payload。
   - 自动下一批会继承合并后的 `workTreeSnapshot`，保证第 n+1 批完成时仍能继续 merge。
2. `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop/transitions.py`
   - fork 完成时若 payload 明确带 `forkMergeContext.workTreeSnapshot` 和 `parentNodeId`，会构造 `ForkResultEnvelope` 并调用 `merge_fork_result_and_plan_next_batch()`。
   - `forkMergeResult` 写入 request/rootMount/window artifact 返回结果。
   - 下一批 DB work item 创建后会立即 `coordinator.enqueue_job()`，进入真实 worker 队列。
   - 没有 merge context 的 fork 保持 Batch 4 行为，不猜测父图。
3. `tests/runtime/test_fork_merge_and_auto_batch.py`
   - 新增真实 worker 回归：fork work item 完成后合并 child 结果，生成下一批 fork work item，并把下一批 work item 入队。

2026-06-22 继续完成 Batch 6 deterministic harness，并清理 Ruff `F403/F405`：

1. `packages/python-sdk/src/yggdrasil_sdk/persistence/repositories/_records.py`
   - 移除 `from ._imports import *`，改为显式导入本文件实际使用的 ORM / domain / contract 名称。
2. `packages/python-sdk/src/yggdrasil_sdk/persistence/repositories/task.py`
   - 移除 `from ._common import *`，改为显式导入 TaskRepository 实际使用的常量、ORM、record mapper、`sa`、`Session`、`utc_now` 等名称。
3. `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop/transitions.py`
   - 移除 `from .state import *`，改为显式导入 transition 完成态所需的 pause/window/takeover/fork enqueue 依赖。
4. `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop/worker.py`
   - 移除 `from .state import *`，改为显式导入 worker 主循环所需的 runtime repository、takeover、snapshot、metrics、memory write、model route 和 fork 相关依赖。
5. `tests/runtime/test_work_tree_graph_fork_runtime_harness.py`
   - 新增 Batch 6 deterministic runtime harness。
   - 使用 fake LLM，但 fake 内部真实写入 `model_invocations` 与 `prompt_compile_artifacts`，避免只测 reducer。
   - 连续跑两轮 `run_worker_once("agent-runtime")`：第一轮完成 `child-a` 并自动排 `child-b`；第二轮消费 `child-b`，验证 pending summary-only 信息被传入。
   - 验证 fork AgentRun 元数据、work item completed 状态、prompt artifact `runType=fork`、继承后的 `workTreeSnapshot`、父任务 `currentFocus` 不被 fork 覆盖，以及不创建 child task / task branch。
6. `evaluation/suites/work-tree-fork-runtime-harness.json`
   - 新增 Batch 6 deterministic evaluation suite：`runtime.fork_harness` 会执行 harness pytest，并把通过的合同写入 evaluation metrics。
7. `evaluation/suites/work-tree-fork-runtime-live-candidate.json`
   - 新增手动 live candidate suite：`runtime.fork_harness_live_candidate` 必须显式设置 `YGGDRASIL_FORK_RUNTIME_LIVE=1` 才会走 live provider，否则记录为 `blocked` 且 suite metrics 为 non-pass；开启 live 后要求 fallback 关闭、真实 `longcat / LongCat-2.0-Preview` invocation、prompt artifact 和 live invocation evidence 与 runtime completed 终态达标。该入口是 live smoke，不是长任务证据。
8. `packages/python-sdk/src/yggdrasil_sdk/evaluation_runtime/suite_cases/runtime.py`
   - 新增 `runtime.fork_harness` 与 `runtime.fork_harness_live_candidate` handler。
9. `packages/python-sdk/src/yggdrasil_sdk/evaluation_runtime/suite_runner.py`
   - 支持 handler 返回 `status=blocked/skipped` 时把 case 记为 non-pass，避免 live blocker 被误读成 passed。
10. `package.json`
   - 新增 `eval:work-tree:fork-runtime-harness` 与 `eval:work-tree:fork-runtime-live`。
11. `packages/python-sdk/src/yggdrasil_sdk/persistence/repositories/task.py`
   - 收紧 `runType=fork` repository 硬校验：创建 fork run 必须提供 `parentRunId`、`forkRootRunId`、`forkDepth >= 1`、`assignedWorkTreeNodeId`、`parentContextAnchor`、`forkGroupId`；更新时不允许清空这些恢复字段或把 depth 降到 0。
12. `tests/api/test_persistence_task_runtime_api.py`
   - 新增 repository/API 回归，验证缺少 fork 必填字段或更新清空必填字段会失败。

2026-06-25 继续完成 live provider 长任务证据：

1. `evaluation/suites/work-tree-fork-runtime-live-candidate.json`
   - live candidate 增加显式 live invocation evidence 与 completed 终态口径：`YGGDRASIL_FORK_RUNTIME_LIVE=1` 后关闭 fallback，要求真实 `longcat / LongCat-2.0-Preview` invocation、prompt compile artifact、至少 2 次 live invocation 证据，并记录 runtime terminal 状态。
   - 固定 `tokenBudgetTotal=200000`、`maxTokens=1400`、`maxWorkerRounds=6`、`planConfirmed=true`，并支持 paused 后自动 resume。
2. `packages/python-sdk/src/yggdrasil_sdk/evaluation_runtime/suite_cases/runtime.py`
   - live LLM handler 从单轮 worker 扩展为多轮 worker，记录 `workerRounds`、`invocationCount`、`acceptedLiveInvocationEvidence`、`acceptedBudgetPause` 和 runtime terminal 状态。
   - 失败摘要压缩为 round-level 状态，避免把完整 runtime payload 塞进错误。
3. `packages/python-sdk/src/yggdrasil_sdk/contracts.py`
   - `TaskTakeoverProtocol.status` 补齐正式 `failed` 状态，匹配 transitions / work tree 失败路径真实写入值。
4. `packages/python-sdk/src/yggdrasil_sdk/llm_runtime/invoke.py` 与 `packages/python-sdk/src/yggdrasil_sdk/prompting.py`
   - `allowToolExecution=false` 现在是硬开关：prompt 不再暴露结构化工具，runtime 也会把模型私自返回的 tool calls 记录为 `ignoredToolCalls`，不会进入工具执行循环。
5. `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/takeover.py`
   - completed protocol / completed work-tree 在 delivery advance 入口直接返回 `completed`，不再因 root node 残留 pending children 重复进入 `parent-orchestration-required`。
6. live provider 证据：
   - `corepack pnpm run eval:work-tree:fork-runtime-live` 在 `YGGDRASIL_FORK_RUNTIME_LIVE=1` 与 `YGGDRASIL_EVAL_PRESERVE_SANDBOX=1` 下通过，生成 `evalrun_69093187bf6c46e587c3`。
   - 本次 passed metrics 记录 `provider=longcat`、`model=LongCat-2.0-Preview`、`invocationCount=2`、最新 `invocationId=llm_2dc66b87c9a8410a9bd3`、`totalTokens=5273`、`promptCompileArtifactId=promptcmp_4774d9474c4c435b904a`、`acceptedLiveInvocationEvidence=true`、`runtimeTerminalStatus=completed`、`taskStatus=completed`。

当前仍未完成：

1. live suite 的“长任务证据”门槛仍未硬化为强制多 invocation / 多 worker round；当前 stronger evidence 仍依赖历史 `evalrun_69093187bf6c46e587c3`，而不是 suite 对 `minLiveInvocations` 的硬失败。
2. R1-R4 当前已落成 deterministic suite/case，但还不是真实 live 多 worker 仓库审查 run；后续如要证明真实收益，需要把 `evalsuite_work_tree_fork_evaluation_tasks` 升级为 live / slow 变体并加入 wall-clock、duplicate-read、merge-cost 指标。

2026-06-26 追加收口：

1. `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/takeover_protocol_lifecycle.py` 已删除；delivery/revision lifecycle 的正式入口收敛到 `runtime_kernel/takeover.py`，不再保留重复实现面。
2. `packages/python-sdk/src/yggdrasil_sdk/observability_exporters.py` 已把本地 Langfuse/OTEL ingest `127.0.0.1:3100` 改为可选：当 project keys 存在但本地 3100 不可达时，不创建 Langfuse client，flush 阶段也不会触发 SDK exporter 重试告警；远端 endpoint 不做本地探测。
3. `tests/test_m8_runtime.py` 增加本地 Langfuse endpoint 不可达时跳过 client 构造的回归，并调整本地 base URL 测试为显式模拟端点可达。
4. 评估任务试跑状态复核：T0-T7 已覆盖并重新跑过；R1-R4 已落成 deterministic suite/case，真实收益仍需 live/slow 变体继续验证。
5. 本轮 3100 可选化后重跑 `corepack pnpm run eval:work-tree:fork-runtime-live` 通过，生成 `evalrun_913700242df54a1d93cc`，`provider=longcat`、`model=LongCat-2.0-Preview`、`runtimeTerminalStatus=completed`、`taskStatus=completed`、`passRate=1.0`，且输出未再出现 `127.0.0.1:3100` 不可达告警。本 run 只有 1 次 invocation，因此只作为“可选 exporter + live completed smoke”证据；更强的长任务证据仍以 `evalrun_69093187bf6c46e587c3` 的 2 次 invocation 记录为准。
6. T6 Budget-Limited Fork Batch 已补完整原始场景：`reserveParentMergeSlots` 进入 `ForkLaunchPolicy`，`tests/runtime/test_work_tree_graph_scheduler.py` 覆盖 8 child / max 4 / reserve 1 -> 只启动 3 个、剩余等待，以及合并预算吃满后降级为父策略。
7. T7 Recursive Fork Active Limit 已补完整递归图：A/B 一级 fork 后，A1/A2 可在 `maxForks=5` 下继续启动，B1/B2 只剩一个槽位时只启动 B1；同时补 `allowRecursiveFork=false` 时保留 child ready-set 但禁止 fork launch。
8. R1-R4 已新增 `evaluation/suites/work-tree-fork-evaluation-tasks.json` 与 `eval:work-tree:fork-evaluation-tasks`，由 `runtime.fork_evaluation_task` deterministic handler 验证 R1 四区域审查、R2 release gate parent replan、R3 三资料包 summary-only 对比、R4 多文件迁移计划 + 父合并预算保留。已通过 `evalrun_23503bda7dee4c39b90e`，4/4 passed。
9. 公开展示题已新增为 `evaluation/suites/work-tree-fork-public-showcase.json` 与 `eval:work-tree:fork-public-showcase`。题面是“2030 韧性能源与应急通信计划”：benefit case 产出 `serialBaselineMinutes=320`、`forkParallelMinutes=133`、`wallClockSpeedup=2.406`、`wallClockReduction0_1=0.5844`、`duplicateReadReduction0_1=0.3333`、`mergeOverheadRatio0_1=0.2857`、`evidenceCoverage0_1=1.0`；这些是基于拆分计划的展示估算，不是实测收益证明。live case 已真实调用 `longcat / LongCat-2.0-Preview`，`evalrun_f6ca4e22241542d4906b` completed，2/2 cases passed，live 侧记录 `workerRounds=2`、`invocationCount=2`、`totalTokens=7364`、`runtimeTerminalStatus=completed`；该 run 是合格展示 live smoke，不是长任务证据。

live 长任务门槛设计：

1. 长任务门槛必须是显式手动、昂贵、真实 live 评测；不得放入 nightly 默认路径，避免持续产生大额 provider 支出。未设置 `requireLongTaskEvidence=true` 的 suite 只能称为 smoke 或展示，不得称为长任务证据。
2. 非真实实测数据没有长任务说服力；少于 100000 token 的短任务也不得作为长程能力证明。展示题中的 benefit case 只能说明“按拆分计划估算的收益假设”，不能替代真实 A/B 实测。
3. 长程任务硬门槛：`longTaskGateKind=long`、`requireLongTaskEvidence=true`、至少 `longTaskMinInvocations=100`、`longTaskMinNonCacheTokens=1000000`、`longTaskMinWorkTreeDepth=2`、`longTaskRequiredTerminalStatus=completed`。token 口径是非缓存成本 token，即非缓存输入 token + 输出 token；要求 `aggregateNonCacheInputTokenSource=explicit`，不能用缓存命中不明的 fallback 估算冒充。
4. 超长程任务硬门槛：`longTaskGateKind=ultra`、`requireLongTaskEvidence=true`、至少 `longTaskMinInvocations=1000`、`longTaskMinNonCacheTokens=10000000`、`longTaskMinWorkTreeDepth=4`、`longTaskRequiredTerminalStatus=completed`。这是独立手动评测档，不进 nightly。
5. 真正评估 Work-Tree Fork 收益时，应另建昂贵手动 A/B suite：同题分别跑串行 baseline 与 fork live，比较真实 wall-clock、非缓存成本 token、质量评分、失败率、重复读取/重复上下文比例和 parent merge overhead。只有这种 A/B 结果才可作为“收益证据”；public showcase 只负责展示可读题面与 live provider 输出。

本轮验证命令：

```powershell
uv run pytest tests/runtime/test_fork_merge_and_auto_batch.py -q --basetemp=tmp/pytest-fork-merge
uv run pytest tests/runtime/test_fork_merge_and_auto_batch.py tests/runtime/test_fork_launch_planner.py tests/runtime/test_work_tree_graph_scheduler.py tests/api/test_persistence_task_runtime_api.py -q -k "fork_merge or fork_launch or worker_consumes_fork or work_tree_graph or fork_agent_run_fields" --basetemp=tmp/pytest-fork-batches-3
uv run ruff check packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/fork_runtime.py tests/runtime/test_fork_merge_and_auto_batch.py packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/__init__.py
uv run pytest tests/runtime/test_work_tree_graph_fork_runtime_harness.py -q --basetemp=tmp/pytest-fork-runtime-harness
uv run pytest tests/runtime/test_work_tree_graph_fork_runtime_harness.py tests/runtime/test_fork_merge_and_auto_batch.py tests/runtime/test_fork_launch_planner.py tests/runtime/test_work_tree_graph_scheduler.py tests/api/test_persistence_task_runtime_api.py -q -k "fork_runtime_harness or fork_merge or fork_launch or worker_consumes_fork or work_tree_graph or fork_agent_run_fields" --basetemp=tmp/pytest-fork-batch6-regression
uv run ruff check --select F403,F405 packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop/worker.py packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop/transitions.py packages/python-sdk/src/yggdrasil_sdk/persistence/repositories/task.py packages/python-sdk/src/yggdrasil_sdk/persistence/repositories/_records.py tests/runtime/test_work_tree_graph_fork_runtime_harness.py tests/runtime/test_fork_merge_and_auto_batch.py tests/runtime/test_fork_launch_planner.py
uv run ruff check tests/runtime/test_work_tree_graph_fork_runtime_harness.py packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop/worker.py packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop/transitions.py packages/python-sdk/src/yggdrasil_sdk/persistence/repositories/task.py packages/python-sdk/src/yggdrasil_sdk/persistence/repositories/_records.py
uv run python -m json.tool evaluation/suites/work-tree-fork-runtime-harness.json
uv run python -m json.tool evaluation/suites/work-tree-fork-runtime-live-candidate.json
uv run pytest tests/api/test_persistence_task_runtime_api.py -q -k "fork_agent_run_fields or incomplete_fork_agent_run_fields or clearing_required_fork_agent_run_fields" --basetemp=tmp/pytest-fork-run-required
corepack pnpm run eval:work-tree:fork-runtime-harness
corepack pnpm run eval:work-tree:fork-runtime-live
uv run pytest tests/runtime/test_work_tree_graph_fork_runtime_harness.py tests/runtime/test_fork_merge_and_auto_batch.py tests/runtime/test_fork_launch_planner.py tests/runtime/test_work_tree_graph_scheduler.py tests/api/test_persistence_task_runtime_api.py -q -k "fork_runtime_harness or fork_merge or fork_launch or worker_consumes_fork or work_tree_graph or fork_agent_run_fields or incomplete_fork_agent_run_fields or clearing_required_fork_agent_run_fields" --basetemp=tmp/pytest-fork-batch6-required-regression
uv run ruff check packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/fork_runtime.py packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop/worker.py packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop/transitions.py packages/python-sdk/src/yggdrasil_sdk/persistence/repositories/task.py packages/python-sdk/src/yggdrasil_sdk/persistence/repositories/_records.py packages/python-sdk/src/yggdrasil_sdk/evaluation_runtime/suite_cases/runtime.py packages/python-sdk/src/yggdrasil_sdk/evaluation_runtime/suite_runner.py tests/runtime/test_work_tree_graph_fork_runtime_harness.py tests/runtime/test_fork_merge_and_auto_batch.py tests/runtime/test_fork_launch_planner.py tests/api/test_persistence_task_runtime_api.py
uv run ruff check packages/python-sdk/src/yggdrasil_sdk/observability_exporters.py tests/test_m8_runtime.py
uv run pytest tests/test_m8_runtime.py -q -k "observability_summary_reports_exporters or langfuse_client_uses_local_base_url_and_project_keys or langfuse_client_skips_unavailable_local_base_url" --basetemp=tmp/pytest-otel-optional
uv run pytest tests/runtime/test_work_tree_graph_scheduler.py tests/runtime/test_fork_launch_planner.py tests/runtime/test_fork_merge_and_auto_batch.py tests/runtime/test_work_tree_graph_fork_runtime_harness.py tests/api/test_persistence_task_runtime_api.py -q -k "fork_runtime_harness or fork_merge or fork_launch or worker_consumes_fork or work_tree_graph or fork_agent_run_fields or incomplete_fork_agent_run_fields or clearing_required_fork_agent_run_fields" --basetemp=tmp/pytest-fork-eval-tasks-current
uv run pytest tests/test_runtime_p4_stability_hardening.py::test_completed_work_tree_does_not_reenter_parent_orchestration -q --basetemp=tmp/pytest-takeover-cleanup
corepack pnpm run eval:work-tree:fork-runtime-live
uv run pytest tests/runtime/test_work_tree_graph_scheduler.py tests/runtime/test_fork_launch_planner.py -q --basetemp=tmp/pytest-fork-t6-t7
corepack pnpm run eval:work-tree:fork-evaluation-tasks
corepack pnpm run eval:work-tree:fork-public-showcase
```

