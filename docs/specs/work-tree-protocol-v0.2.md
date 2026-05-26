# Work Tree Protocol v0.2

- 文档状态：Accepted for P1 implementation
- 版本：v0.2
- 日期：2026-05-23
- 取代范围：取代 [工作树协议 v0.1](work-tree-protocol-v0.1.md) 的运行语义；v0.1 artifact 仍必须可读并可升级。
- 设计来源：
  - [新工作树方案](../new/工作树.md)
  - [新 Boot Prompt 方案](../new/元提示词.md)
  - [世界树计划正式项目定义草稿](../new/世界树计划正式项目定义.md)
  - [提示词、启动流程、工作流程重做执行文档](../development/ROOT_PROMPT_STARTUP_WORKFLOW_REWORK_EXECUTION_2026_05_23.md)
- 关联文档：
  - [Agent 运行时协议 v0.2](agent-runtime-protocol-v0.2.md)
  - [运行时与工具数据规格 v0.1](runtime-domain-data-spec-v0.1.md)
  - [记忆与建树数据规格 v0.1](memory-domain-data-spec-v0.1.md)
  - [任务接管协议 v0.1](task-takeover-protocol-v0.1.md)

## 1. 定位

工作树是记忆树根节点 `[ID: 003 我要干什么]` 下的动态工作记忆。它不是外部项目管理清单，也不是 takeover plan 的只读投影。它是 LLM 当前执行状态、执行栈、局部上下文、递归分解和摘要上浮的正式载体。

v0.2 的核心变化：

1. 工作树从“计划投影”升级为“执行栈和工作记忆”。
2. LLM 可以在协议约束下动态创建、细分、跳转、总结和关闭工作节点。
3. 系统负责拓扑、版本、权限、审计、恢复指针和窗口一致性。
4. 父节点中的 LLM 负责语义判断、节点命名、局部摘要、失败经验、下潜和上浮决策。
5. child 完成或失败后，必须先回编排父节点，由父节点决定是否进入 sibling、继续拆 leaf 或请求外部输入。
6. 上下文窗口以当前工作切片为主；允许保留有限线性 continuation 轨迹，但长期状态仍必须写入工作树或记忆树。

## 2. 与 v0.1 的决策差异

| 主题 | v0.1 | v0.2 |
| --- | --- | --- |
| 节点来源 | 从 `TaskTakeoverProtocol.plan` 派生 | takeover plan 只作为初始建议，LLM 可动态扩树 |
| 控制流 | 计划步骤驱动 | 当前工作节点驱动，但下一步去向由编排父节点决定 |
| 数据流 | prompt/request/runtime 共享同一 work tree snapshot | 每个窗口必须共享同一 `Working_Node`、工作树版本和检索节点 |
| 完成语义 | runtime 可在交付后直接 completed | 根节点完成后进入 `awaiting-approval`，批准后才 completed |
| 压缩恢复 | recoveryAnchor 为 resume/repair 入口 | `workingNodeAnnotation` 同时是上下文书签和返回指针 |
| 摘要 | 交付摘要附属于 takeover artifact | 每个完成/失败节点必须写 `executionSummary` |
| 冲突处理 | 不定义语义冲突路径 | 定义版本重试、追加日志、提案合并、主动分节点 |

## 3. 根位置与命名

### 3.1 根位置

工作树必须挂在 `[ID: 003 我要干什么]` 根分支下。底层实现可以继续使用 `rootBranch=execution`，但对 LLM 暴露时必须使用中文语义根：

```yaml
semanticRoot:
  id: "003"
  name: "我要干什么"
  implementationRootBranch: "execution"
```

### 3.2 节点命名

工作节点标题不是稳定路由。稳定路由必须来自 `questionsItAnswers`。

规则：

1. `title` 面向人类和 UI，允许短。
2. `questionsItAnswers` 面向 LLM 检索，必须回答“这个节点能回答什么问题”。
3. 不允许只用 `A.1`、`step-3`、`todo`、`misc` 作为语义路牌。
4. 子节点名称表达相对父节点的展开方向，例如“运行时 Boot Prompt 编译改造”而不是“子任务 1”。
5. 节点文本必须优先写自然语言，不要求 LLM 生成机械 JSON 思维链。

## 4. 对象结构

### 4.1 WorkTreeProtocolV2

```yaml
WorkTreeProtocol:
  version: "0.2.0"
  id: string
  taskId: string
  rootNodeId: string
  currentNodeId: string|null
  rootObjective: string
  status: planned|standby|active|summarizing|recovering|restarting|paused|awaiting-approval|completed|failed
  nodes: [WorkTreeNode]
  loadedNodeIds: [string]
  activePathNodeIds: [string]
  indexMapRefs: [EntityRef]
  pcMemo: string|null
  recoveryAnchor: string|null
  entropyBudgetRemaining: integer
  versionCounter: integer
  updatedAt: datetime
```

字段语义：

| 字段 | 必填 | 写入者 | 说明 |
| --- | --- | --- | --- |
| `version` | 是 | Kernel | 固定为 `0.2.0`，读取 v0.1 时由兼容层升级 |
| `id` | 是 | Kernel | 工作树协议对象 ID |
| `taskId` | 是 | Kernel | 所属任务 |
| `rootNodeId` | 是 | Kernel/LLM proposal | 当前任务工作树根节点 |
| `currentNodeId` | 条件必填 | Kernel | 当前工作节点。`standby/completed/failed` 可为空 |
| `rootObjective` | 是 | LLM/Kernel | 根任务目标摘要 |
| `status` | 是 | Kernel | 工作树总体状态 |
| `nodes` | 是 | Kernel | 当前工作树节点集合。实现可按页存储，但 artifact 中必须可重建 |
| `loadedNodeIds` | 是 | Kernel | 当前窗口实际加载的节点 |
| `activePathNodeIds` | 是 | Kernel | 从根节点到当前节点的路径 |
| `indexMapRefs` | 是 | Kernel | 能力、工具、协议、知识索引入口 |
| `pcMemo` | 否 | LLM | 程序计数器备忘录，给下一窗口恢复现场 |
| `recoveryAnchor` | 否 | Kernel | 当前可恢复入口，必须可追溯到 snapshot 或工作节点 |
| `entropyBudgetRemaining` | 是 | Kernel | 观测字段，指示当前工作树可继续扩张余量 |
| `versionCounter` | 是 | Kernel | 乐观锁版本号 |
| `updatedAt` | 是 | Kernel | 最后修改时间 |

### 4.2 WorkTreeNodeV2

```yaml
WorkTreeNode:
  id: string
  parentNodeId: string|null
  title: string
  questionsItAnswers: [string]
  nodeText: string
  localGoal: string
  localConstraints: [string]
  localContextRefs: [EntityRef]
  workingNodeAnnotation: string
  executionSummary: string|null
  failureSummary: string|null
  phase: planning|executing|recovering|restarting|verification|delivery|standby|coordination
  status: pending|in-progress|summarizing|completed|failed|blocked|skipped
  childNodeIds: [string]
  dependsOn: [string]
  relationIds: [string]
  expectedEvidence: [string]
  producedEvidenceRefs: [EntityRef]
  sourceMemoryNodeIds: [string]
  assignedAgentRunId: string|null
  ownerAgentId: string|null
  priority: integer
  detailLevel: integer
  version: integer
  createdAt: datetime
  updatedAt: datetime
```

字段语义：

| 字段 | 必填 | 写入者 | 说明 |
| --- | --- | --- | --- |
| `id` | 是 | Kernel | 稳定节点 ID |
| `parentNodeId` | 根节点外必填 | Kernel | 父节点 ID。根节点为 null |
| `title` | 是 | LLM | 短标题 |
| `questionsItAnswers` | 是 | LLM | 语义索引路牌，至少 1 条 |
| `nodeText` | 是 | LLM | 50 到 200 字左右的自然语言状态切片 |
| `localGoal` | 是 | LLM | 当前节点的局部目标 |
| `localConstraints` | 是 | LLM | 当前节点必须遵守的局部约束 |
| `localContextRefs` | 可空 | Kernel/LLM | 当前节点依赖的记忆、资产、文档或外部引用 |
| `workingNodeAnnotation` | 是 | Kernel | 固定格式 `<Working_Node: {id}>` |
| `executionSummary` | 条件必填 | LLM | 完成或跳过前必须写入 |
| `failureSummary` | 条件必填 | LLM | 失败或阻塞时必须写入，说明避坑经验 |
| `phase` | 是 | Kernel/LLM | 节点所处执行阶段 |
| `status` | 是 | Kernel | 节点状态 |
| `childNodeIds` | 是 | Kernel | 子节点列表 |
| `dependsOn` | 可空 | LLM | 控制流依赖 |
| `relationIds` | 可空 | LLM/Relation module | 信息流关联 |
| `expectedEvidence` | 可空 | LLM | 节点完成需要的证据 |
| `producedEvidenceRefs` | 可空 | Kernel/LLM | 节点产出的证据 |
| `sourceMemoryNodeIds` | 可空 | Kernel | 来源记忆节点 |
| `assignedAgentRunId` | 可空 | Kernel | 当前处理该节点的 AgentRun |
| `ownerAgentId` | 可空 | Kernel | 多 Agent 场景下的拥有者 |
| `priority` | 是 | LLM/Kernel | 同级排序，数值越小越优先 |
| `detailLevel` | 是 | Kernel/LLM | LOD 深度，根节点为 0 |
| `version` | 是 | Kernel | 节点乐观锁版本 |
| `createdAt/updatedAt` | 是 | Kernel | 审计时间 |

### 4.3 节点文本长度

目标范围：

- 中文节点文本建议 50 到 200 个汉字。
- 英文节点文本建议 40 到 120 个词。
- 超过目标范围不是立即失败，但写入前必须尝试拆分或摘要。

硬性要求：

1. `nodeText` 不得塞入长篇文档、完整日志、完整代码块。
2. 大文本必须写入外部资产或记忆叶子节点，再由 `localContextRefs` 引用。
3. 如果 LLM 想一次写入超长内容，Kernel 应返回可恢复错误并建议拆子节点或委派 Sub-Agent。

## 5. Working Node Annotation

### 5.1 格式

```text
<Working_Node: {node_id}>
```

`node_id` 必须等于 `WorkTreeProtocol.currentNodeId`。不允许使用标题、序号或临时标签代替。

### 5.2 上下文要求

每个模型调用窗口必须同时满足：

1. Boot Prompt 的现场恢复段包含 `Working_Node`。
2. `memoryRetrievalState.workTreeNodeId` 等于当前节点 ID。
3. snapshot 或 window execution artifact 记录同一个当前节点 ID。
4. LLM 产生的记忆写入带 `sourceWorkTreeNodeId=currentNodeId`。

### 5.3 作用

| 作用 | 说明 |
| --- | --- |
| 物理书签 | 锚定 LLM 当前认知焦点，避免长链条任务中漂移 |
| 返回指针 | 节点完成、失败、压缩后可沿父节点返回 |
| 压缩边界 | 上下文压缩可指定起点和终点工作节点 |
| 审计标签 | Prompt、检索、工具、写树、snapshot 可统一追踪 |

### 5.4 WorkContextStack

工作树提供持久拓扑，`WorkContextStack` 提供当前运行窗口里的栈式上下文。主流程必须同时维护两者：

- 工作树回答“有哪些节点、父子关系、状态、摘要和恢复入口”。
- 上下文栈回答“当前 LLM 窗口实际保留了哪条从根到叶子的上下文路径，以及如何返回父级而不重启”。

对象结构：

```yaml
WorkContextStack:
  version: "0.2.0"
  taskId: string
  agentRunId: string
  rootFrameId: string
  topFrameId: string
  frames: [WorkContextFrame]
  cachePolicy: preserve-prefix|allow-recompile
  stackDigest: string
  updatedAt: datetime
```

```yaml
WorkContextFrame:
  id: string
  nodeId: string
  parentFrameId: string|null
  stackDepth: integer
  workingNodeAnnotation: string
  entryContextDigest: string
  prefixCacheKey: string|null
  frameHeader: string
  frameLocalTranscriptRef: EntityRef|null
  childCompletionSummaries:
    - childNodeId: string
      summary: string
      evidenceRefs: [EntityRef]
      completedAt: datetime
  cursorState: string|null
  status: active|suspended|completed|failed
```

字段语义：

| 字段 | 说明 |
| --- | --- |
| `rootFrameId` | 初始节点对应的上下文帧 |
| `topFrameId` | 当前最深工作帧，必须对应 `WorkTreeProtocol.currentNodeId` |
| `cachePolicy` | 默认 `preserve-prefix`，表示 runtime continuation 优先保留根/父帧稳定前缀；provider 是否命中缓存要看调用 usage，而不是只看 policy |
| `entryContextDigest` | 进入该节点时父级上下文的摘要指纹，用于检测返回时是否漂移 |
| `prefixCacheKey` | runtime continuation cache 的前缀身份，可由本地 runtime 或 provider 提供；它证明“前缀被稳定保留”，但不单独证明 provider 已命中缓存 |
| `frameHeader` | 当前帧进入时追加到上下文的短文本，如 `<执行节点1>执行过程，继续往下探细节` |
| `frameLocalTranscriptRef` | 当前帧较长执行过程的 transcript 或 artifact 引用 |
| `childCompletionSummaries` | 子节点完成后回填到父帧的短摘要列表 |
| `cursorState` | 父帧恢复后下一步要继续的局部游标，例如“继续最细节执行2” |

边界约定：

1. runtime continuation cache 由 `cachePolicy=preserve-prefix`、`WorkContextStack` 和 `prefixCacheKey` 共同描述，负责保证 push/pop/window continuation 时保留同一段稳定前缀。
2. provider prefix cache 是模型供应商侧的真实命中/写入行为，必须通过 usage 里的 `cacheHitInputTokens` / `cacheWriteInputTokens` 证明。
3. `prefixCacheKey` 非空但 `cacheHitInputTokens=0` 仍然可能是合法状态，这表示 runtime 已维持稳定前缀，但 provider 这次没有给出缓存命中。
4. 反过来，provider 给出 cache hit/write 指标，但如果 `currentNodeId`、`topFrameId` 或 `prefixCacheKey` 漂移，就不能把它解释成 work-tree continuation 语义成立。

### 5.5 栈式主流程

目标主流程：

```text
<初始节点>启动内容
<工作开始>大致规划过程
<执行节点1>执行过程，继续往下探细节
<分过程1>继续细节下探
<最细节执行1>最细节执行的过程
```

当 `<最细节执行1>` 完成时，runtime 不应默认窗口重启，也不应重新从根节点拼 prompt。它必须执行：

```text
pop_frame(最细节执行1)
  -> 写最细节执行1.executionSummary
  -> 把长执行过程移出当前窗口或压缩为 artifact
  -> 将“最细节执行1完成：摘要/证据/下一步影响”追加到父帧 childCompletionSummaries
  -> topFrame 恢复为 分过程1
```

恢复后的有效上下文应近似为：

```text
<初始节点>启动内容
<工作开始>大致规划过程
<执行节点1>执行过程，继续往下探细节
<分过程1>继续细节下探，最细节执行1完成
```

恢复到 `<分过程1>` 后，下一步不由 runtime 自动决定，而是由 `<分过程1>` 这个编排父节点决定：继续 `<最细节执行2>`、继续拆 leaf、上浮、或请求外部输入。当 `<分过程1>` 完成时，再次执行 `pop_frame(分过程1)`，父级上下文应近似为：

```text
<初始节点>启动内容
<工作开始>大致规划过程
<执行节点1>执行过程，继续往下探细节，分过程1完成
```

然后继续 `<分过程2>`。

硬性要求：

1. 子节点完成后的默认动作是 `pop_frame` 回编排父节点，不是 `window_restart`，也不是 runtime 直接替父节点跳到下一个 sibling。
2. `window_restart` 只在 token、工具 checkpoint、安全停止或 provider 限制触发时发生。
3. `pop_frame` 必须保留父帧进入时的上下文前缀，并允许保留有限的线性 continuation 轨迹，充分利用 LLM prefix cache。
4. 子节点长执行过程必须折叠为子节点摘要和证据引用；如需保留轨迹，也只保留父节点编排所需的短轨迹与 cleanup 说明，不继续占用父级窗口。
5. 父帧恢复时必须能继续读取自己的 `cursorState`、最近 child 摘要和当前未完成子节点状态，再由父节点决定下一步，而不是重新规划整棵树。
6. 如果父帧上下文 digest 变化，runtime 必须要求 LLM 写 `pcMemo` 或重新读取父节点摘要后再继续。

### 5.6 树与栈的一致性

| 项 | 工作树 | 上下文栈 |
| --- | --- | --- |
| 当前指针 | `currentNodeId` | `topFrame.nodeId` |
| 父子关系 | `parentNodeId/childNodeIds` | `parentFrameId` |
| 节点完成 | `status=completed` + `executionSummary` | `pop_frame` 后写入父帧 `childCompletionSummaries` |
| 节点失败 | `status=failed` + `failureSummary` | `pop_frame` 后写入父帧失败摘要 |
| 长过程保存 | 节点 artifact / 记忆引用 | `frameLocalTranscriptRef` |
| 恢复入口 | `workingNodeAnnotation` + `pcMemo` | `topFrameId` + `stackDigest` |

任一窗口中必须满足：

```text
WorkTreeProtocol.currentNodeId == WorkContextStack.topFrame.nodeId
WorkTreeNode.workingNodeAnnotation == WorkContextStack.topFrame.workingNodeAnnotation
```

## 6. 拓扑规则

### 6.1 垂直 LOD

父节点是子节点的高层摘要。子节点是父节点一个方向的更高精度展开。

规则：

1. 父节点必须能用自己的 `executionSummary` 或 `nodeText` 覆盖子节点完成后的结果。
2. 子节点不能与父节点目标无关。
3. 子节点完成后，必须通过摘要上浮更新父节点的局部状态。
4. 上下文限制的是工作深度，不是总任务长度。

### 6.2 水平关联

同级节点可以通过两类边连接：

| 类型 | 字段 | 语义 |
| --- | --- | --- |
| 控制流依赖 | `dependsOn` | 先后顺序、阻塞关系、验证前置 |
| 信息流关联 | `relationIds` | 资料继承、证据共享、语义相关 |

规则：

1. 上层节点的边更偏控制流。
2. 底层节点的边更偏信息流。
3. 如果 LLM 发现两个节点存在可复用信息，必须建立或建议建立关联。
4. 大量并发写同一宏观节点时，应优先创建更细分子节点实现空间隔离。

### 6.3 加载窗口

当前上下文窗口应加载：

1. Boot Prompt 四段。
2. 当前 `WorkContextStack` 的 active frames，至少包含根帧到 top frame 的 frame header。
3. 当前工作节点。
4. 根到当前节点的 `activePathNodeIds`。
5. 当前节点必要的父节点摘要。
6. 父帧中的 `childCompletionSummaries`，用于父节点继续编排下一步。
7. 最近有限长度的线性 continuation 轨迹，用于说明刚完成/刚失败的 child、已清理的上下文和当前待判断入口。
8. 必要的兄弟节点状态摘要，不加载完整兄弟正文。
9. 当前节点相关的记忆检索结果。
10. 能力与协议索引地图。

不应加载：

1. 整棵工作树全文。
2. 大量已完成叶子节点的推演过程。
3. 与当前节点无关的历史对话。
4. 可以通过记忆树重新召回的大块资料全文。
5. 已 pop 的子帧完整 transcript，除非当前节点明确要求复查。

## 7. 状态机

### 7.1 协议状态

| 状态 | 含义 | 允许的下一状态 |
| --- | --- | --- |
| `planned` | 已生成根节点或初始树，但尚未进入运行 | `standby`, `active` |
| `standby` | 无当前执行节点，等待用户消息、邮箱消息或调度信号 | `active`, `completed` |
| `active` | 当前有工作节点正在处理 | `summarizing`, `paused`, `restarting`, `recovering`, `awaiting-approval`, `failed` |
| `summarizing` | 当前节点正在写摘要并准备上浮 | `active`, `awaiting-approval`, `failed` |
| `recovering` | 正在从 snapshot、restart 或 pcMemo 恢复 | `active`, `paused`, `failed` |
| `restarting` | 正在进行窗口重启交接 | `recovering`, `failed` |
| `paused` | 任务处于安全暂停，可恢复 | `recovering`, `failed` |
| `awaiting-approval` | 根节点已完成，等待用户或上层批准 | `completed`, `active`, `failed` |
| `completed` | 用户或上层批准任务完成 | 无 |
| `failed` | 任务不可继续或已明确失败 | `recovering`, `active` |

### 7.2 节点状态

| 状态 | 含义 | 进入条件 | 退出条件 |
| --- | --- | --- | --- |
| `pending` | 节点已创建但未进入 | 创建子节点或初始计划生成 | `in-progress`, `skipped` |
| `in-progress` | 当前或已分配执行 | `enter_node` | `summarizing`, `blocked`, `failed` |
| `summarizing` | 正在压缩执行结果 | LLM 判断节点可结束或失败 | `completed`, `failed`, `blocked` |
| `completed` | 节点完成且已有摘要 | `executionSummary` 已写入 | 不再执行，只可追加审计 |
| `failed` | 节点失败且已有避坑摘要 | `failureSummary` 已写入 | 可由父节点决定重试或另建分支 |
| `blocked` | 需要外部输入、权限或前置节点 | 明确 blocker | blocker 解除后回 `in-progress` |
| `skipped` | 节点被证明确认不需要执行 | 写明跳过原因 | 不再执行 |

### 7.3 核心迁移

```text
create_root -> enter_node(root)
enter_node(parent) -> create_child -> enter_node(child)
enter_node(node) -> execute -> summarize_node(node)
summarize_node(child) -> complete_node(child) -> return_to_parent
summarize_node(child) -> fail_node(child) -> return_to_parent
complete_node(root) -> awaiting-approval
approve_task -> completed
pause_request -> paused
window_restart -> restarting -> recovering -> active
```

## 8. 操作协议

### 8.1 create_child_node

用途：在当前节点下创建更精细的工作切片。

输入：

```yaml
parentNodeId: string
title: string
questionsItAnswers: [string]
nodeText: string
localGoal: string
localConstraints: [string]
localContextRefs: [EntityRef]
expectedEvidence: [string]
priority: integer
```

约束：

1. `parentNodeId` 必须存在。
2. 子节点目标必须是父节点目标的局部展开。
3. `questionsItAnswers` 不得为空。
4. 创建后默认 `status=pending`。

### 8.2 enter_node

用途：把当前工作指针切换到目标节点。

约束：

1. 目标节点必须存在。
2. 如果切换离开当前 `in-progress` 节点，当前节点必须处于 `completed/failed/blocked/skipped`，或写入 `pcMemo` 说明临时跳转原因。
3. 切换后必须更新 `Working_Node`、`activePathNodeIds`、`loadedNodeIds`、`memoryRetrievalState.workTreeNodeId`。

### 8.3 summarize_node

用途：将节点冗长执行过程压缩成高密度摘要。

输出：

```yaml
executionSummary: string|null
failureSummary: string|null
producedEvidenceRefs: [EntityRef]
nextRecommendation: string|null
```

约束：

1. 成功节点必须写 `executionSummary`。
2. 失败节点必须写 `failureSummary`。
3. 摘要应保留可复用结论、证据、决策理由、避坑经验和后续建议。
4. 摘要不能包含完整推理流水账。

### 8.4 complete_node

用途：正式完成节点。

约束：

1. 当前节点必须已有 `executionSummary`。
2. 当前节点 `expectedEvidence` 若非空，必须有对应 `producedEvidenceRefs` 或明确说明不适用。
3. 完成子节点后，系统返回父节点。
4. 完成根节点后，工作树进入 `awaiting-approval`。

### 8.5 fail_node

用途：正式记录节点失败。

约束：

1. 必须写 `failureSummary`。
2. 必须说明失败类型：信息不足、权限不足、工具失败、设计不成立、外部阻塞、预算不足。
3. 父节点读取失败摘要后决定：重试、改走兄弟分支、请求用户、终止任务。

### 8.6 append_relation

用途：连接工作节点和记忆节点、证据节点或其他工作节点。

约束：

1. 关系必须说明方向和原因。
2. 控制流关系写入 `dependsOn`。
3. 信息流关系写入 `relationIds`。
4. 低置信关系可先写入 relation proposal，不直接污染正式边。

### 8.7 push_frame

用途：进入子节点时，把子节点上下文追加到栈顶，并尽量保留父级 prompt 前缀缓存。

输入：

```yaml
targetNodeId: string
frameHeader: string
cursorState: string|null
```

约束：

1. `targetNodeId` 必须是当前节点的子节点，或是经过显式跳转批准的关联节点。
2. push 后 `WorkTreeProtocol.currentNodeId` 必须等于 `targetNodeId`。
3. push 后 `WorkContextStack.topFrame.nodeId` 必须等于 `targetNodeId`。
4. 父帧不得被丢弃，只能进入 `suspended` 或保持在 active path。
5. 如果当前窗口 token 仍可容纳，push 不得触发 window restart。

### 8.8 pop_frame

用途：子节点完成、失败或阻塞后，返回父级上下文帧，并把子节点结果以摘要形式写回父帧。

输入：

```yaml
sourceNodeId: string
parentNodeId: string
summary: string
evidenceRefs: [EntityRef]
nextCursorState: string|null
outcome: completed|failed|blocked|skipped
```

约束：

1. `sourceNodeId` 必须等于当前 top frame 的 nodeId。
2. `summary` 必须来自 `executionSummary` 或 `failureSummary`。
3. pop 后 `WorkTreeProtocol.currentNodeId` 必须等于父节点，除非父节点也立即完成并继续 pop。
4. 父帧必须追加 `childCompletionSummaries`。
5. pop 不得把子节点完整执行过程拼回父级上下文。
6. pop 后优先继续父帧 `cursorState` 指向的下一子节点。

## 9. 上下文压缩与窗口超阈值处理

### 9.1 压缩触发

可由以下信号触发：

1. token 预算接近阈值。
2. 当前节点执行过程产生大量中间推演。
3. LLM 主动判断“高熵拥挤”。
4. 用户或策略请求压缩。
5. 进入长文本、大量文件或多分支合并阶段。

### 9.2 压缩边界

上下文压缩必须指定：

```yaml
startWorkingNodeId: string
endWorkingNodeId: string
compressionRatio: number
retainedRefs: [EntityRef]
compressedRefs: [EntityRef]
droppedRefs: [EntityRef]
```

推荐只压缩中间段，避免压缩当前叶子节点的直接依赖。

冻结约束：

1. 压缩起点必须在“基础规则前缀”之后（合同锚点、恢复锚点、关键摘要不得被压掉）。
2. 压缩终点必须为尾部留出缓冲：至少保留 `n+1` 个未压缩段（`n` 默认 1）。
3. 压缩规划器必须输出可审计的区间元数据（起点、终点、n）。

### 9.3 超阈值处理（v2 默认）

当窗口超过阈值时，v2 默认流程如下：

1. 先执行上下文压缩（受 9.2 起止约束）。
2. 若压缩后仍超阈值，当前工作树支线写回 `failed + failureSummary`。
3. 是否继续由父节点、人工批准或后续修订流程决定。

### 9.4 重启恢复（legacy / stress）

窗口重启必须恢复：

1. `WorkTreeProtocol.currentNodeId`
2. `workingNodeAnnotation`
3. `pcMemo`
4. `activePathNodeIds`
5. 当前节点直接依赖的 `localContextRefs`
6. 上一次检索摘要和 protected refs

恢复后第一轮 prompt 必须能证明自己没有退回初始规划状态。

## 10. 多 Agent 协作

### 10.1 Sub-Agent

Sub-Agent 用于大量预读、建树、摘要、验证、非决策性重活。

规则：

1. Sub-Agent 权限低于主 Agent。
2. Sub-Agent 必须绑定一个工作树节点或子节点。
3. Sub-Agent 不接管全局 currentNodeId。
4. Sub-Agent 结果必须写回节点摘要、候选记忆节点或 PR proposal。
5. 主 Agent 负责语义合并和最终上浮。

### 10.2 Fork

Fork 用于同级同构并行需求。

规则：

1. Fork 前必须先创建多个同级子节点。
2. 每个 fork 实例只处理自己的子节点。
3. Fork 共享起始短期上下文，但后续写入必须按节点隔离。
4. 合并时先读每个子节点摘要，不直接拼接所有上下文。

### 10.3 联邦 Agent

联邦 Agent 通过共享节点、邮箱和提案合并协作。

规则：

1. 跨 Agent 默认异步。
2. 共享节点写入必须走权限和版本检查。
3. 低权限 Agent 不能覆盖高权限记忆。
4. 大型连续修改必须走 proposal/PR 合并。

## 11. 记忆写入和冲突处理

每个从工作树触发的记忆写入必须携带：

```yaml
sourceWorkTreeNodeId: string
workingNodeAnnotation: string
agentRunId: string
workTreeVersion: integer
```

冲突路径：

| 路径 | 适用场景 | 语义 |
| --- | --- | --- |
| `update_memory_with_version` | 单节点乐观锁冲突 | 读最新版本，让 LLM 语义融合后重试 |
| `append_memory_log` | 大量资料碎片并发收集 | 无锁追加日志，后续 GC/整理 Agent 合并 |
| `submit_memory_proposal` | 大型连续修改 | 在分支写完后提交提案，由主 Agent 或治理流程合并 |
| 主动分节点 | 宏观节点过宽 | 先建立细分子节点，降低写冲突和语义混杂 |

## 12. Artifact 一致性

同一次窗口执行中，以下 artifact 必须看到同一份工作树指针：

| Artifact | 必须字段 |
| --- | --- |
| compiled prompt | `Working_Node`, `currentNodeId`, `activePathNodeIds` |
| LLM request | `takeoverProtocol.workTree` 或 v0.2 `workTree` snapshot |
| context stack artifact | `topFrameId`, `topFrame.nodeId`, `stackDigest`, `cachePolicy` |
| memory retrieval request | `workTreeNodeId` |
| model invocation record | `workTreeSnapshot` |
| window execution record | `workTreeCurrentNodeId`, `topFrameId`, `workTreeStatus`, `stateFingerprint`, `stackDigest` |
| task snapshot | `currentNodeId`, `workingNodeAnnotation`, `pcMemo`, `topFrameId`, `stackDigest` |
| memory write | `sourceWorkTreeNodeId` |

如果任意两处不一致，runtime 必须拒绝完成迁移，并进入可恢复错误。

## 13. v0.1 兼容

### 13.1 读取 v0.1

读取 v0.1 `WorkTreeProtocol` 时：

1. `version` 升级为 `0.2.0`。
2. `rootNodeId` 使用第一个无依赖节点；若没有节点，创建 bootstrap 根节点。
3. `parentNodeId` 按 `dependsOn` 无法推导时默认挂到根节点。
4. `questionsItAnswers` 从 `title`、`expectedEvidence` 和 plan step title 生成。
5. `nodeText` 从 `title`、`phase`、`expectedEvidence` 生成。
6. `workingNodeAnnotation` 由节点 ID 生成。
7. `verified` 状态映射为 `awaiting-approval`，除非已有明确用户批准记录。

### 13.2 写出策略

兼容迁移期可以同时写：

- v0.2 正式 artifact。
- v0.1 兼容摘要，用于旧代码读取。

但任何新功能只能依赖 v0.2 语义。

## 14. 验收标准

P1/P2 实现必须满足：

1. 能从 v0.1 artifact 升级到 v0.2 工作树。
2. 每个运行窗口都有同一 `Working_Node`。
3. `WorkTreeProtocol.currentNodeId` 与 `WorkContextStack.topFrame.nodeId` 始终一致。
4. 动态创建子节点后可 push frame、可恢复、可审计、可写摘要。
5. 子节点完成后默认 pop frame 回父级上下文，不默认 window restart。
6. pop 后父帧包含子节点完成摘要，并能继续下一个兄弟节点。
7. 完成节点前必须存在摘要。
8. 完成根节点后进入 `awaiting-approval`。
9. 记忆写入必须带 `sourceWorkTreeNodeId`。
10. 窗口重启后不重新生成初始计划，不丢当前节点和栈顶 frame。
11. 多 Agent 并发写入不会覆盖同一节点版本。

建议最小测试：

```powershell
uv run pytest tests/test_runtime_p4_foundation.py tests/runtime/test_runtime_restart_and_resume.py tests/runtime/test_runtime_core_and_memory.py -q
```

## 15. 非目标

v0.2 不要求一次性实现：

1. 完整 UI 可视化编辑器。
2. 自动全局最优任务调度器。
3. 所有多 Agent 联邦市场能力。
4. 完整 HippoRAG/PPR 关系建议器。
5. 训练系统自动优化工作树策略。

但 v0.2 字段和状态必须为上述能力预留，不允许用一次性实现堵死。
