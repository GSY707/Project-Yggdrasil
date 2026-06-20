# 多 Agent 自分裂与工作树图调度设计盘点（2026-06-20）

- 文档状态：Design baseline
- 范围：只做设计盘点与下一步设计切分，不进入代码实现
- 目标：在既有 v0.2 工作树与多 Agent 协议上，设计“Agent 自我分裂 + 工作树图能力 + 并行 ready-set 调度 + 多线程冲突处理”的下一层正式方案

## 1. 当前已有文档怎么写

### 1.1 多 Agent 三类协作已经有概念边界

`docs/new/世界树计划正式项目定义.md` 已把多 Agent 能力分成三类：

| 类别 | 当前语义 | 已有边界 |
| --- | --- | --- |
| Sub-Agent 异步委派 | 主 Agent 把非决策、重 IO、重建树、局部整理任务委派给权限更低的子 Agent | 子 Agent 低权限、异步执行、结果通过 PR 或提案合并 |
| Agent Fork / Mitosis | 针对同级同构并行需求，复制短期上下文并让多个克隆体潜入不同平行分支 | 每个 fork 只能处理自己的平行分支，合并时读摘要和证据 |
| 联邦 Agent | 多个不同 Agent 通过共享节点、邮箱、提案合并异步协作 | 默认不共享完整上下文，低权限内容必须标记待验证 |

`docs/specs/agent-runtime-protocol-v0.2.md` 已把 Sub-Agent 和 Fork 写成正式协议对象：

- `SubAgentAssignment` 包含 `parentWorkTreeNodeId`、`assignedWorkTreeNodeId`、只读上下文、写入范围、预算和返回合同。
- Fork 被定义为同构上下文分裂，不是普通 Sub-Agent。
- Fork 前必须创建多个平行工作树子节点。
- Fork 预算按模型能力、节点复杂度、上下文窗口和成本动态分配。
- 父 Agent 必须保留合并预算。

当前缺口：已有协议定义了“能分裂”和“分裂后怎么隔离”，但还没有定义“由谁、在何时、基于哪张图自动选择可以并行的节点并触发 fork / sub-agent”。

### 1.2 工作树已有图字段，但没有正式调度层

`docs/specs/work-tree-protocol-v0.2.md` 已经把工作树从任务清单升级成动态工作记忆和执行栈。`WorkTreeNode` 已有下列图能力字段：

| 字段 | 当前语义 | 可复用方向 |
| --- | --- | --- |
| `childNodeIds` | 父子拓扑 | 保持 LOD 递归分解 |
| `dependsOn` | 控制流依赖 | 作为 ready-set 计算的前置条件 |
| `relationIds` | 信息流关联 | 用于知识继承、证据共享、减少重复读取 |
| `localContextRefs` | 当前节点依赖的记忆、资产、文档或外部引用 | 作为子任务初始上下文包 |
| `producedEvidenceRefs` | 当前节点产出的证据 | 作为下游节点继承输入 |
| `assignedAgentRunId` / `ownerAgentId` | 多 Agent 场景下的节点归属 | 作为并行执行租约与写隔离基础 |
| `priority` | 同级排序 | 作为 ready-set 内排序，而不是全局最优调度 |
| `version` | 乐观锁版本 | 作为并发写 CAS 基础 |

同一份协议还明确了两类水平关联：

| 类型 | 字段 | 语义 |
| --- | --- | --- |
| 控制流依赖 | `dependsOn` | 先后顺序、阻塞关系、验证前置 |
| 信息流关联 | `relationIds` | 资料继承、证据共享、语义相关 |

关键边界：`work-tree-protocol-v0.2` 的非目标里明确不要求一次性实现“自动全局最优任务调度器”。因此本轮不应该改成全局最优调度系统，而应该设计“父节点局部图调度”：只在当前父节点可见的子图里计算 ready-set，由父 Agent 保留语义编排权。

### 1.3 协作治理已有分支 / PR，但不是调度协议

`docs/specs/collaboration-and-governance-data-spec-v0.1.md` 已冻结：

- Sub-Agent 分支、PR 分支和共享空间分支统一复用 `MemoryBranch`。
- Sub-Agent 不直接写主分支，必须通过 `PullRequest`。
- `SpaceMount` 预留只读、写时复制、双向同步三种挂载语义。

这解决了“结果怎么治理”，但没有解决“多个子任务何时并发启动、写哪个节点、失败后怎么回父节点重排”。

### 1.4 并发冲突已有底座，但需要统一成多 Agent 冲突合同

已有冲突处理分散在几类文档与实现里：

| 位置 | 已有能力 |
| --- | --- |
| `docs/specs/work-tree-protocol-v0.2.md` | 记忆写入携带 `sourceWorkTreeNodeId`、`workingNodeAnnotation`、`agentRunId`、`workTreeVersion`；冲突路径包括乐观锁、追加日志、提案合并和主动分节点 |
| `docs/development/HIGH_CONCURRENCY_TABLE_PLAYBOOK.md` | 进程内 keyed operation queue、SQLite 锁等待重试、事务瘦身、高并发表索引 |
| `docs/research/technical-analysis/sqlite-concurrency-ops-queue-2026-05-17.md` | 建议按 `taskId` / `branchId` 分桶串行化热点写入 |
| `docs/specs/task-pause-resume-continuation-contract-v0.1.md` | 持久 WorkItem、lease、reclaim、Redis 只做 wakeup、任务恢复权威状态在持久存储 |
| `docs/development/RUNTIME_CONCURRENCY_M9_INVESTIGATION_2026_06_11.md` | 指出 lock miss、pop-before-process、长事务、状态覆盖、lock 续租和 fencing token 风险 |

当前缺口：这些机制还没有被统一成“多 Agent 并发执行一个工作树图时，节点级租约、版本前置条件、写入冲突、父节点合并、失败重排”的单一合同。需要注意：`RUNTIME_CONCURRENCY_M9_INVESTIGATION_2026_06_11.md` 是调查基线，不是当前修复记录；当前实现已经有持久 `RuntimeWorkItem`、DB claim、task-lock-miss reclaim 等改进，但跨进程 / Postgres 多 worker 场景仍缺正式设计。

### 1.5 当前实现已经有一部分地基

静态代码证据显示：

- `packages/python-sdk/src/yggdrasil_sdk/contracts.py` 的 `WorkTreeNode` 已实现 `dependsOn`、`relationIds`、`assignedAgentRunId`、`ownerAgentId`、`priority`、`version` 等字段。
- `packages/python-sdk/src/yggdrasil_sdk/collaboration_runtime/context.py` 的 `launch_subagent_task()` 已能创建子分支、子任务、只读上下文包、预算决策和持久 work item。
- `packages/python-sdk/src/yggdrasil_sdk/persistence/repositories/task.py` 已有持久 `RuntimeWorkItem` 的 `queued / leased / reclaimable` 路径。
- `services/worker/src/yggdrasil_worker/registry.py` 已对 task lock miss 和 retryable failure 做 reclaim / requeue。
- `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/takeover_work_tree_runtime.py` 当前仍主要提供 sibling 列表和下一个 sibling 选择，不是基于 `dependsOn + relationIds + priority` 的 ready-set 图调度。

结论：本轮设计不需要重写现有地基；需要补“调度层”和“冲突合同”。

### 1.6 模型路由、预算和 prompt profile 已有数据点，但未形成执行策略

现有文档还提供了三类重要地基：

| 位置 | 已有能力 | 当前缺口 |
| --- | --- | --- |
| `docs/specs/runtime-domain-data-spec-v0.1.md` | `BudgetState.maxSubAgents`、`AgentRun.runType`、`ModelRouteDecision`，并要求自动选模产生 route decision 记录 | 没有定义 Fork/Sub-Agent 调度时如何分配 token、成本、工具回合、时间和父 Agent 保留预算 |
| `docs/specs/application-package-interface-v0.1.md` | 应用包可声明 `subagentPromptProfileId`，prompt profile 的 `runScope` 可为 `main/subagent/any` | 没有定义不同应用包如何约束 fork/sub-agent 的可用 prompt profile 和工具权限 |
| `docs/development/MOE_MODEL_ROUTING_ASSESSMENT_2026_06_14.md` | 已按 D0-D4 拆出主模型、子任务模型、风险和验收重点 | 仍是评估框架，尚未产品化为每个子体的自动 route decision |
| `modules/subagent-runtime/` | 当前实际注册 Sub-Agent prompt profile | 它不是完整执行框架，执行闭环在 `collaboration_runtime`、worker 和 `subagent-pr` 附近 |

因此本轮还需要把“调度器决定可以并行”与“路由器决定用哪个模型/预算”分开设计，避免后续实现把两者耦合成难以测试的黑箱。

## 2. 本轮应该设计哪些内容

### 2.1 工作树图能力规格

建议新增正式规格：`docs/specs/work-tree-graph-relations-v0.1.md`。

该规格应先补齐 `relationIds` 的正式语义，避免把“信息流关联”留成只有字段、没有生命周期的弱约束。

需要定义：

1. `relationIds` 指向什么：正式 `MemoryEdge`、`WorkTreeRelation`、还是 `LinkProposal`。
2. 关系方向：单向继承、双向语义相关、证据共享、冲突/矛盾、替代路径、验证前置。
3. 关系置信度：confirmed、proposed、weak-signal；低置信关系不得直接驱动调度，只能影响检索排序或提示父节点确认。
4. proposal 生命周期：提出、审查、采用、拒绝、过期、被上游版本变更失效。
5. 与 memory-domain Edge 的边界：工作树边服务执行状态；记忆树边服务长期知识，不把两者强行合并成一张表。
6. 与 relation-discovery 的边界：关系发现模块可以提供候选边，但是否进入正式工作树图由父 Agent 或治理流程决定。

这份规格是图调度的前置，因为调度器必须能区分“控制流阻塞边”和“信息流继承边”。

### 2.2 工作树局部图调度协议

建议新增正式规格：`docs/specs/work-tree-graph-scheduler-protocol-v0.1.md`。

该协议应定义：

1. `WorkTreeExecutionGraph`：从当前父节点的子树投影出来的局部执行图，不创建第二套任务树。
2. `readySet` 计算规则：节点 `status=pending|blocked`，所有 `dependsOn` 已完成或被父节点显式豁免，且节点未被其他 Agent 租约占用。
3. `blockedSet` 规则：依赖未完成、继承输入缺失、版本过期、预算不足、权限不足、父节点要求人工确认。
4. `priority` 规则：只在同一父节点局部 ready-set 内排序；不做全局最优。
5. 并行触发规则：ready-set 中互不写同一节点、互不争用同一高风险资源、预算允许时，父 Agent 可以触发 Sub-Agent 或 Fork。
6. 父节点编排边界：scheduler 只能提出候选 ready-set 和风险；最终启动、串行降级、合并、重排仍由父 Agent 决定。

第一版不要做全局最短路径、复杂优化器、跨任务全局调度或训练出来的策略优化。

### 2.3 Agent 自我分裂 / Fork 扩展协议

建议新增正式规格：`docs/specs/agent-fork-protocol-v0.1.md`。

该协议应补齐：

| 设计项 | 需要冻结的内容 |
| --- | --- |
| 触发条件 | 同级同构节点、可隔离写入、ready-set 大于 1、父 Agent 有合并预算 |
| ForkPlan | parentRunId、parentWorkTreeNodeId、childNodeIds、contextDigest、budgetPlan、modelPlan、mergeGate |
| Fork 上下文继承 | 直接继承父 Agent 当前上下文缓存快照，child 节点只提供执行焦点；不额外压缩生成替代上下文包 |
| 写入边界 | fork 实例只能写自己的 `assignedWorkTreeNodeId`、追加日志或提交 proposal |
| 失败降级 | 任一子节点模型不满足上下文/质量门槛时，降级串行或请求预算调整 |
| 合并门禁 | 父 Agent 只读 child 摘要、证据和冲突清单，不拼接完整上下文 |

Fork 与 Sub-Agent 的区别必须保持清楚：Fork 是同构上下文分裂，适合平行 sibling，必须保留父 Agent 的当前认知与判断倾向；Sub-Agent 是较低权限的异步委派，适合非决策重活或专项能力。2026-06-21 已用 `docs/specs/work-tree-graph-fork-parallel-protocol-v0.1.md` 纠偏：Fork 不应被设计为只拿裁剪上下文包的普通委派。

### 2.4 知识继承与上下文传递协议

建议新增正式规格：`docs/specs/work-tree-knowledge-inheritance-v0.1.md`，或并入图调度协议第二章。

要解决的问题是：下游子任务不重复读取父节点、上游节点和相关资料，而是继承可审计、可失效的知识包。

建议定义 `InheritanceBundle`：

```yaml
InheritanceBundle:
  parentWorkTreeNodeId: string
  targetWorkTreeNodeId: string
  sourceNodeIds: [string]
  sourceRelationIds: [string]
  sourceEvidenceRefs: [EntityRef]
  parentSummaryRef: EntityRef
  upstreamSummaries:
    - nodeId: string
      status: completed|failed|blocked
      summaryRef: EntityRef
      producedEvidenceRefs: [EntityRef]
  localContextRefs: [EntityRef]
  versionVector:
    workTreeVersion: integer
    memoryNodeVersions: object
  digest: string
  invalidationPolicy: on-version-change|on-parent-rewrite|manual
```

设计边界：

- 继承的是摘要、证据引用、检索结果和版本指针，不是完整原始上下文。
- `relationIds` 用于信息流继承，`dependsOn` 用于控制流阻塞，不要混用。
- 继承包必须有 digest 和 version vector；版本过期时进入 blocked 或要求父节点重新整理。
- 如果继承包缺关键证据，子任务不得假装已读取，应返回 `missingInfo`。

### 2.5 多 Agent 并发冲突合同

建议新增正式规格：`docs/specs/multi-agent-conflict-contract-v0.1.md`。

该合同应覆盖：

| 冲突面 | 第一版规则 |
| --- | --- |
| 节点执行租约 | `assignedAgentRunId` / `ownerAgentId` 必须带 lease、leaseUntil、fencingToken；过期后可 reclaim |
| 工作树写入 | 修改节点必须带 `expectedWorkTreeVersion`；失败返回结构化 conflict，不静默覆盖 |
| 记忆写入 | 单节点修改走 latestVersionId；碎片资料走 append log；大型连续修改走 proposal / PR |
| 父节点合并 | 父 Agent 根据 child 摘要、证据、冲突清单合并，不直接拼接全部子上下文 |
| 队列一致性 | work item ack 必须发生在 DB 状态更新后；Redis 只做 wakeup |
| 长事务 | LLM 调用、文件扫描、网络检索不得持有写事务 |
| 冲突升级 | 同一节点连续冲突超过阈值时，必须主动分节点或转 proposal |
| Task/Run/Snapshot 状态迁移 | 状态更新必须带 expected status/version；失败返回 conflict/retryable，不做字段覆盖式静默覆盖 |
| Postgres 多 worker claim | 需要定义 `FOR UPDATE SKIP LOCKED`、advisory lock 或等价原子 claim 策略，以及 lease 到期 reclaim scanner |
| 分布式 keyed queue | 当前进程内 keyed lock 只能解决单进程热点写；多 worker 场景需要 DB/Redis Streams/Postgres advisory lock 等分布式 key 串行化策略 |
| 崩溃恢复验收 | 覆盖 claim 后崩溃、lease 到期 reclaim、Redis 清空、backup/restore 后 resume、outbox/补偿扫描 |

这份合同需要把已有 high-concurrency playbook、pause/resume durable work item 和工作树冲突路径统一起来，避免每个模块各自解释“冲突”。

### 2.6 父 Agent 合并与失败重排协议

建议在 `agent-fork-protocol` 或独立小节中定义：

- child completed：上浮 `executionSummary`、`producedEvidenceRefs`、`missingInfo=[]`。
- child failed：上浮 `failureSummary`、失败证据、可重试性、建议父节点重排选项。
- child blocked：上浮 blockerCode、缺失输入、所需人工/工具/预算。
- partial success：父节点决定拆分剩余节点、转串行、升级模型或请求用户确认。
- 所有 child 回来后，父节点重新计算 ready-set，而不是 runtime 直接跳 sibling。

### 2.7 超图推理转正桥接

建议新增研究到规格的桥接文档：`docs/development/HYPERGRAPH_REASONING_PROMOTION_CRITERIA_2026_06_20.md`。

这不是第一轮实现项。它只定义什么时候可以把 `docs/research/specifications/hypergraph-reasoning-protocol-draft-2026-05-05.md` 从研究稿提升为正式协议。

转正条件至少应包括：

1. relation-discovery 输出稳定，能区分正式边和候选边。
2. memory-domain Edge / LinkProposal 已有可审计生命周期。
3. work-tree `relationIds` 已能引用关系对象并携带版本。
4. analyzer artifact 能展示“关系边如何改变检索、继承或调度结果”。
5. 评测样本证明关系模式对象减少重复检索或改善任务推进，而不是只增加复杂度。

第一版工作树图调度不依赖完整超图推理；只需要稳定的控制流边和信息流边。

### 2.8 Fork/Sub-Agent 模型路由与资源分配

建议新增正式规格：`docs/specs/multi-agent-resource-routing-contract-v0.1.md`。

该规格应定义：

1. `maxSubAgents` 如何作为并发上限，而不是只作为创建次数计数。
2. 父 Agent 保留预算下限：合并、验收、返工、用户说明必须有独立预算。
3. 每个子体的 `ModelRouteDecision`：记录任务难度、风险、上下文需求、工具权限、成本、TPS 和降级原因。
4. 工具权限分配：fork 子体默认继承最小工具集；Sub-Agent 只获得 assignment 需要的工具。
5. 时间预算与 reclaim：子体超时后回父节点，不静默继续占用节点租约。
6. 预算扣减审计：token、cost、tool round、wall time、child count 都要能从父任务追溯。

这份合同应直接复用 `BudgetState` 和 `ModelRouteDecision`，不要再新建一套预算对象。

### 2.9 控制面和用户体验设计

建议新增开发文档：`docs/development/MULTI_AGENT_GRAPH_CONTROL_PLANE_UX_2026_06_20.md`。

这不是优先级最高的底层规格，但必须在实现前明确最小可见面：

1. 用户能看到当前父节点下有哪些 running / queued / blocked / completed 子体。
2. 用户能暂停、取消或重试某个子体，而不是只能操作整棵任务。
3. 用户能看到子体的只读上下文、产出摘要、证据引用、冲突和 merge decision。
4. 父节点收到 child completion 后的 mailbox / side-channel 事件应可审计。
5. PR/proposal 合并不能被包装成“自动成功”；需要显示合并、拒绝、请求修改和返工路径。

### 2.10 观测与评测设计

建议新增开发文档：`docs/development/MULTI_AGENT_WORKTREE_GRAPH_EVALUATION_PLAN_2026_06_20.md`，或放在实施计划里。

至少要定义这些指标：

| 指标 | 用途 |
| --- | --- |
| ready-set correctness | 可并行节点是否真的满足依赖 |
| duplicate-read reduction | 知识继承是否减少重复读取/查找 |
| parent-merge budget | 父 Agent 是否保留足够 token/cost 做合并 |
| route decision correctness | 子体模型/预算/工具权限是否匹配任务难度和风险 |
| conflict rate | 多 Agent 写入冲突率和冲突恢复率 |
| stale-inheritance invalidation | 上游变更后继承包是否正确失效 |
| parallel speedup | 并行是否提升总耗时，而不是增加调度开销 |
| semantic drift | 子任务是否偏离父节点局部目标 |

最小验收套件应覆盖：

1. `dependsOn` 阻塞：依赖未完成时不进入 ready-set。
2. `relationIds` 继承：相关节点产物进入继承包，但不阻塞控制流。
3. Fork 并行：两个同级同构节点可并行，并且写入隔离。
4. Sub-Agent 异步：重 IO 节点可委派，结果通过 summary / proposal 回父节点。
5. 冲突恢复：两个 Agent 争写同一节点时返回 conflict，一个转 append log 或 proposal。
6. 父节点重排：某 child failed 后先回父节点，由父节点决定 retry / sibling / split / user input。
7. 路由审计：每个 fork/sub-agent 都产生可追踪的 `ModelRouteDecision` 与预算扣减记录。
8. 多 worker 恢复：worker claim 后崩溃、lease 到期 reclaim、Redis wakeup 丢失和 backup/restore 后 resume 都有可执行验收。

## 3. 推荐设计顺序

| 顺序 | 交付物 | 原因 |
| --- | --- | --- |
| 1 | `work-tree-graph-relations-v0.1.md` | 先定义 `relationIds` 指向、方向、置信度和 proposal 生命周期 |
| 2 | `work-tree-graph-scheduler-protocol-v0.1.md` | 再定义 ready-set、依赖、局部优先图，避免 Fork 直接变成随意并行 |
| 3 | `agent-fork-protocol-v0.1.md` | 在调度边界清楚后，定义自分裂上下文、预算和合并 |
| 4 | `multi-agent-resource-routing-contract-v0.1.md` | 把 D0-D4、预算、工具权限和 `ModelRouteDecision` 变成可审计策略 |
| 5 | `work-tree-knowledge-inheritance-v0.1.md` | 明确知识继承包，减少重复读取并提供版本失效 |
| 6 | `multi-agent-conflict-contract-v0.1.md` | 把节点租约、CAS、PR、append log、work item lease 统一成一个冲突合同 |
| 7 | 控制面 UX 设计 | 明确并行子体可视化、暂停/取消/重试和合并审查最小面 |
| 8 | 超图推理转正桥接 | 只定义 Gate 3+ 转正条件，不阻塞第一版图调度 |
| 9 | 实施计划与评测计划 | 再把实现分成 disjoint work packages，避免多个 Agent 改同一核心文件 |

## 4. 本轮不要做的事

1. 不重做工作树 v0.2，不新增第二套任务树。
2. 不恢复旧的自动 sibling continuation。
3. 不做全局最优调度器，只做父节点局部 ready-set 调度。
4. 不让子 Agent 或 fork 子体直接改父节点、root currentNodeId 或主分支记忆。
5. 不共享完整上下文给所有子体，只传摘要、证据引用、版本指针和必要只读上下文。
6. 不为了兼容旧测试保留旧语义；旧断言如果阻碍新协议，应删除或改写。
7. 不把 `subagent-runtime` 误称为完整执行框架；当前它是 prompt profile 注册层。

## 5. 当前结论

这轮改进的核心不是“再设计一套多 Agent 系统”，而是补齐当前文档中的中间层：

```text
工作树 v0.2 已有节点、依赖、关系、优先级、版本和父节点编排
        ↓
缺：父节点局部图调度 ready-set
        ↓
缺：ready-set 到 Sub-Agent / Fork 的启动合同
        ↓
缺：知识继承包，避免重复读取和重复检索
        ↓
缺：多 Agent 并发写入的统一冲突合同
        ↓
缺：评测与观测指标证明并行确实有效
```

因此下一步应先补正式规格，再进入实现。实现阶段应优先围绕已有字段与持久 work item 扩展，不应该用兼容层包住旧路线。
