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
- `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/takeover_work_tree_runtime.py`
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

1. Batch 2：AgentRun Fork 持久字段、迁移和 repository 查询。
2. Batch 3：Fork batch launch planner 与 runtime work item 排队。
3. Batch 4：worker Fork run view 与 prompt artifact。
4. Batch 5：Fork 结果合并、第 n+1 批调度和 pending 信息流落点。
5. Batch 6：runtime debug harness、slow/nightly 真实链路验证。

本轮验证命令：

```powershell
uv run pytest tests/runtime/test_work_tree_graph_scheduler.py -q --basetemp=tmp/pytest-work-tree-graph
uv run python -m compileall packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/work_tree_graph.py tests/runtime/test_work_tree_graph_scheduler.py
```
