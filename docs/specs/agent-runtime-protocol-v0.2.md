# Agent 运行时协议 v0.2

- 文档状态：Accepted for P1/P2 implementation
- 版本：v0.2
- 日期：2026-05-23
- 取代范围：取代 [Agent 运行时协议 v0.1](agent-runtime-protocol-v0.1.md) 中关于提示词、启动流程、根节点挂载、工作流程、暂停恢复和任务结束的运行语义；v0.1 的模块边界和既有数据规格仍可作为兼容层参考。
- 设计来源：
  - [新 Boot Prompt 方案](../new/元提示词.md)
  - [新工作树方案](../new/工作树.md)
  - [世界树计划正式项目定义草稿](../new/世界树计划正式项目定义.md)
  - [提示词、启动流程、工作流程重做执行文档](../development/ROOT_PROMPT_STARTUP_WORKFLOW_REWORK_EXECUTION_2026_05_23.md)
- 关联文档：
  - [工作树协议 v0.2](work-tree-protocol-v0.2.md)
  - [工作树协议 v0.1](work-tree-protocol-v0.1.md)
  - [任务接管协议 v0.1](task-takeover-protocol-v0.1.md)
  - [运行时与工具数据规格 v0.1](runtime-domain-data-spec-v0.1.md)
  - [协作与治理数据规格 v0.1](collaboration-and-governance-data-spec-v0.1.md)

## 1. 总定位

v0.2 运行时协议把世界树系统重新定义为“LLM 核心 + 代码世界”。代码不再以状态机强行替 LLM 决策，而是提供可持久化记忆、可调用工具、权限边界、上下文窗口、协作机制、审计反馈和恢复能力。

运行时必须保证：

1. LLM 每次醒来都知道自己的物理接口在哪里。
2. LLM 每次醒来都能通过根指针找到身份、世界、工作和系统宪法。
3. LLM 每次醒来都能恢复当前程序计数器，也就是当前工作树节点。
4. 父节点是工作推进的唯一强编排者；child 完成或失败后先回编排父节点，由父节点决定是否进入 sibling、继续拆 leaf 或等待外部输入。
5. LLM 可以自然下潜、总结上浮、委派子任务、写入记忆并处理冲突。
6. 任务完成必须经过工作树根节点完成和用户/上层批准，不由单轮回答直接判定。

## 2. 生命周期

世界树运行生命周期：

```text
编写 -> 编译 -> 启动 -> 待机 -> 运行 -> 等待批准结束 -> 结束
```

### 2.1 编写

开发者编写代码、文档、提示词资产、模块和应用包。

输出：

- 源代码。
- Prompt profile、seed template、few-shot。
- 规格文档和协议。
- 应用包和模块 manifest。

### 2.2 编译

编译不是传统代码编译，而是把代码和文本资产经过记忆编译流程转化为记忆树节点、能力索引和协议索引。

输出：

- `[ID: 001 我是谁]` 下的身份、能力和行为倾向节点。
- `[ID: 002 我在哪]` 下的项目、环境、来源和世界知识节点。
- `[ID: 003 我要干什么]` 下的工作树根、任务留言和待机入口。
- `[NODE_ID: SYS_ROOT_PROTOCOL]` 下的系统宪法和底层协议。
- 能力索引、工具索引、工作索引、知识索引。

### 2.3 启动

启动是 LLM 从无状态模型变成世界树运行核心的过程。启动只做唤醒、寻址、最低行为宪法和现场恢复，不做业务规划。

输出：

- RootMountPackage v0.2。
- Boot Prompt 四段。
- 当前 `Working_Node` 或 standby 状态。
- AgentRun 或 standby session。

### 2.4 待机

待机是没有当前运行任务，或者任务已完成但等待用户输入时的状态。待机不是进程退出。

待机循环：

1. 读取用户消息队列。
2. 读取 Agent 邮箱。
3. 读取系统侧信道唤醒通知。
4. 如果没有输入，保持 idle，不触发 LLM 推理。
5. 如果有输入，创建或恢复工作树节点并进入运行。

### 2.5 运行

运行以当前工作树节点为中心推进。

LLM 在每个节点中可选择：

- 读取记忆索引或节点。
- 读取工具索引。
- 执行工具。
- 创建子工作节点并下潜。
- 写入记忆或关联。
- 委派 Sub-Agent 或 fork。
- 写节点摘要并上浮。
- 请求用户或等待外部事件。

运行补充规则：

1. child 完成或失败后必须先回编排父节点，runtime 不得默认替父节点直接选择下一个 sibling。
2. 父节点可基于 child 摘要、最近线性 continuation 轨迹和当前约束，决定进入已有 child、创建新 leaf、进入 sibling 或请求外部输入。
3. runtime 可插入预算、树深和安全警戒，但这些警戒只提供边界信息，不替代父节点的语义编排。

### 2.6 等待批准结束

工作树根节点完成后，任务进入 `awaiting-approval`。此时系统应向用户或上层流程展示结果、证据、未完成项和工作树摘要。

允许操作：

- `approve_task_completion`
- `request_revision`
- `reopen_work_node`
- `archive_task`

### 2.7 结束

只有批准后，任务才能进入 `completed`。结束时必须完成：

- 工作树根节点有 `executionSummary`。
- 关键记忆和经验已写入记忆树。
- 未完成项已明确记录。
- 审计 artifact 已落盘。
- 运行预算和指标已结算。

## 3. Boot Prompt 协议

### 3.1 目标

Boot Prompt 的目标不是教 LLM 做具体任务，而是完成系统级唤醒。它类似 init 进程，只负责加载驱动、挂载文件系统、设置最低权限、交出程序计数器。

### 3.2 四段结构

Boot Prompt 必须分为四段，且在 compiled prompt artifact 中可被结构化审计。

```yaml
BootPrompt:
  version: "0.2.0"
  physicalIoBinding: string
  rootPointerMap: string
  behaviorConstitution: string
  pcRecovery: string
```

### 3.3 physicalIoBinding

必须声明：

1. 你不是普通聊天机器人，而是 Project Yggdrasil 的核心调度器。
2. 你只能通过正式工具、MCP 泛型工具、消息工具和侧信道协议触碰外部世界。
3. 默认文本输出不是对外动作。对用户发消息必须调用正式消息工具。
4. 工具调用、记忆写入、外部动作都必须可审计。
5. 高风险动作必须遵守权限和确认策略。

禁止包含：

- 场景业务知识。
- 具体项目实现细节。
- 当前任务的完整计划。
- 长篇工具手册全文。

### 3.4 rootPointerMap

必须声明四个根指针：

```yaml
RootPointerMap:
  identity:
    semanticId: "001"
    name: "我是谁"
    implementationRootBranch: "identity"
  world:
    semanticId: "002"
    name: "我在哪"
    implementationRootBranch: "context"
  work:
    semanticId: "003"
    name: "我要干什么"
    implementationRootBranch: "execution"
  systemProtocol:
    nodeId: "SYS_ROOT_PROTOCOL"
    name: "系统宪法与底层协议"
```

必须说明：

1. 完整知识不在 Boot Prompt 中，而在记忆树中。
2. 当前上下文以当前工作集为主，但允许保留有限线性 continuation 轨迹，以换取稳定前缀和缓存命中。
3. 保留的线性轨迹应是父节点编排所需的短轨迹、cleanup 说明和 child 摘要，不得无限积累原始执行现场。
4. 需要细节时应读取索引，再按需加载节点。
5. 能力、工具、工作、知识都通过索引地图寻址。

### 3.5 behaviorConstitution

必须包含最低行为宪法：

1. 节点写入受长度、权限、版本和拓扑宽度限制。
2. 禁止一次性打包大量信息强行写入。
3. 长文本、大量未知文件、仓库扫描、资料预读必须优先委派 Sub-Agent。
4. 记忆更新优先级高于任务推进。
5. 节点命名必须以 `questions_it_answers` 作为路牌。
6. 只能信任同权限或更高权限记忆；低权限记忆只能作为待验证输入。
7. 遇到写冲突必须走版本重试、追加日志或提案合并，不得静默覆盖。
8. 当前任务完成前必须写入工作节点摘要。
9. child 完成或失败后必须先把结果交回编排父节点，由父节点决定下一步，而不是让 runtime 直接替代编排。

### 3.6 pcRecovery

必须包含现场恢复：

```yaml
PcRecovery:
  startupMode: cold-standby|hot-resume|work-node-active|restart-recovery|approval-review
  currentWorkingNodeId: string|null
  workingNodeAnnotation: string|null
  pcMemo: string|null
  resumeMessage: string|null
  restartMessage: string|null
  mailboxSummary: string|null
  sideChannelSummary: string|null
  nextDecisionHint: string|null
```

规则：

1. 如果 `currentWorkingNodeId` 非空，必须出现 `<Working_Node: {id}>`。
2. `pcMemo` 是上一窗口给当前窗口的短备忘录，不得替代工作树节点摘要。
3. `resumeMessage` 和 `restartMessage` 只能出现一次。
4. 恢复态不得重新从初始计划开始，除非工作树损坏且无法修复。

## 4. RootMountPackage v0.2

### 4.1 对象结构

```yaml
RootMountPackage:
  version: "0.2.0"
  id: string
  taskId: string|null
  projectId: string
  spaceId: string
  branchId: string
  rootPointerMap: RootPointerMap
  sysRootProtocolRef: EntityRef
  mountedNodeRefs: [EntityRef]
  identityRefs: [EntityRef]
  worldRefs: [EntityRef]
  workRefs: [EntityRef]
  abilityIndexRefs: [EntityRef]
  toolIndexRefs: [EntityRef]
  workIndexRefs: [EntityRef]
  knowledgeIndexRefs: [EntityRef]
  workTree: WorkTreeProtocol|null
  currentWorkingNode: WorkTreeNode|null
  workingNodeAnnotation: string|null
  pcMemo: string|null
  startupMode: cold-standby|hot-resume|work-node-active|restart-recovery|approval-review
  mailboxState: MailboxState
  sideChannelState: SideChannelState
  budgetState: BudgetState
  activeCapabilities: [string]
  activeToolIndex: [ToolDescriptor]
  rootSummary: string
  generatedAt: datetime
```

### 4.2 加载顺序

启动时必须按顺序加载：

1. 你的能力：内部能力，说明 LLM 可以读写什么、如何整理记忆、如何委派。
2. 你的工具：外部能力，说明当前可调用工具和 MCP 能力。
3. 你的工作：当前工作树、当前节点、待机状态、留言、预算。
4. 你的知识：当前任务需要的知识节点和检索结果。

如果预算不足：

1. 能力和工具只加载索引，不加载全文。
2. 工作必须加载当前节点和 active path。
3. 知识按当前节点检索，不加载全局知识。

### 4.3 根挂载规则

1. Kernel 必须挂载根指针和当前工作节点。
2. 模块只能追加 mount fragments，不能删除 Kernel 强制项。
3. 场景 seed 和应用 profile 不得改写 Boot Prompt 四段，只能作为 scene overlay。
4. root mount 必须可落盘、可缓存、可用于 snapshot 恢复。

## 5. Prompt 编译分层

v0.2 prompt 编译必须分层：

```yaml
CompiledPrompt:
  bootSections:
    physicalIoBinding: string
    rootPointerMap: string
    behaviorConstitution: string
    pcRecovery: string
  sceneSections:
    profileRole: string
    sceneIdentityOverlay: string
    sceneExecutionBias: string
    outputStyleHint: string
  runtimeSections:
    currentWorkTree: string
    currentWorkingNode: string
    memoryRetrievalState: string
    mountedContextItems: string
    toolIndexSummary: string
  messages: [ChatMessage]
```

规则：

1. `bootSections` 是系统级，所有 app 共享。
2. `sceneSections` 只提供倾向，不得覆盖 Boot Prompt。
3. `runtimeSections` 是当前窗口工作集。
4. few-shot 只作为风格示例，不得成为真实上下文。
5. 恢复态默认不注入 few-shot，除非当前工作节点明确需要。

## 6. 启动模式

| 模式 | 触发条件 | 当前节点 | 下一步 |
| --- | --- | --- | --- |
| `cold-standby` | 无未完成任务，无用户消息 | null | 进入待机 |
| `hot-resume` | 有 paused snapshot | snapshot 中节点 | rehydrate 后继续 |
| `work-node-active` | 有未完成工作节点 | currentNodeId | 加载当前节点继续 |
| `restart-recovery` | 有 restart snapshot（legacy 兼容） | snapshot 中节点 | 仅兼容恢复旧快照 |
| `approval-review` | 根节点完成待批准 | rootNodeId 或 null | 等待批准或返工 |

### 6.1 cold-standby

冷启动不得强行创建任务。它只加载根指针、能力索引、工具索引和邮箱状态。

### 6.2 hot-resume

恢复优先级：

1. pending tool calls checkpoint
2. restart snapshot
3. paused task snapshot
4. unfinished work tree node
5. task resume message
6. cold standby

### 6.3 restart-recovery（legacy 兼容）

重启恢复必须验证：

1. snapshot checksum。
2. pending actions checksum。
3. `currentWorkingNodeId` 存在。
4. `workingNodeAnnotation` 与 current node 一致。
5. protected refs 未丢失。

冻结说明：

1. 默认执行路径不再主动发起 window restart。
2. 新任务在窗口超阈值时，先执行上下文压缩；若压缩后仍超阈值，当前工作树支线直接标记为 `failed`。
3. `restart-recovery` 仅用于消费历史 restart snapshot 或 stress/回放场景。

## 7. 待机协议

### 7.1 MailboxState

邮箱使用独立 `mailbox` 表，不复用 outbox/event 表作为主存储。outbox/event 只记录投递、通知和审计事件。

```yaml
MailboxState:
  unreadCount: integer
  latestMessageId: string|null
  latestMessageSummary: string|null
  notificationsEnabled: boolean
```

规则：

1. Agent 默认通过邮箱通信。
2. LLM 必须主动读取邮箱，除非开启通知。
3. 邮箱通知通过侧信道插入，不中断当前工具调用。
4. 对外发消息必须走消息工具或邮箱工具。
5. `mailbox` 表至少需要保存 message id、sender、recipient agent/profile、thread id、关联 task/work node、read state、priority、payload ref、createdAt、readAt。
6. 邮箱消息可以唤醒 standby，也可以作为当前工作节点的侧信道输入，但不能静默改写工作树。

### 7.2 Standby Loop

```text
enter_standby
  -> check_user_message_queue
  -> check_mailbox
  -> check_side_channel_notifications
  -> if no input: idle
  -> if input: create_or_resume_work_node
  -> enter_active
```

待机状态下不得：

1. 无输入触发 LLM 自行长推理。
2. 自动改写长期记忆。
3. 自动完成历史任务。

## 8. 运行协议

### 8.1 主循环

```text
load_boot_prompt
load_current_work_node
load_work_context_stack
load_memory_index_for_node
invoke_llm
process_tool_calls
apply_memory_writes
update_work_tree_and_context_stack
persist_window_execution
decide_next_state
```

### 8.1.1 栈式上下文主循环

工作树主流程不是“每个子任务完成就重启窗口”，而是“同一 AgentRun 内维护 `WorkContextStack`，通过 push/pop 保留父级上下文前缀并充分利用模型缓存”。

典型流程：

```text
root frame: <初始节点>启动内容
push: <工作开始>大致规划过程
push: <执行节点1>执行过程，继续往下探细节
push: <分过程1>继续细节下探
push: <最细节执行1>最细节执行的过程
complete 最细节执行1
pop -> 回到 分过程1，并追加“最细节执行1完成”
push: <最细节执行2>
complete 最细节执行2
pop -> 回到 分过程1
complete 分过程1
pop -> 回到 执行节点1，并追加“分过程1完成”
push: <分过程2>
```

运行时要求：

1. `push_frame` 优先复用已有 message prefix 和 provider prefix cache，不重新编译根到父级的完整上下文。
2. `pop_frame` 只把子节点摘要、证据引用和下一步影响写回父帧，不把子节点完整 transcript 拼回父级上下文。
3. 只要 token 和工具状态允许，子节点完成后的默认动作是 pop，而不是 pause/restart/resume。
4. 当上下文接近阈值时，先对已完成子帧做摘要和 artifact 化，并执行中段压缩；不再把 restart 作为默认续跑路径。
5. 若压缩后仍超阈值，runtime 必须将当前节点写回 `failed + failureSummary`，并由父级或人工决定后续恢复策略。

### 8.2 LLM 决策空间

LLM 每轮必须在当前工作节点内选择一种或多种动作：

| 动作 | 说明 |
| --- | --- |
| 读取索引 | 读能力、工具、工作、知识索引 |
| 读取节点 | 读记忆节点或工作节点 |
| 执行工具 | 调用结构化工具或 MCP 工具 |
| 下潜 | 创建子工作节点并进入 |
| 上浮 | 写摘要并返回父节点 |
| 委派 | 启动 Sub-Agent 处理非决策重活 |
| Fork | 分裂同构分支处理平行子节点 |
| 写记忆 | 写入重要事实、约束、经验、关联 |
| 等待 | 进入 blocked 或 standby |
| 请求批准 | 根节点完成后进入 awaiting-approval |

### 8.3 运行时不得替 LLM 做的事

运行时不得：

1. 根据单轮回答自动判定根任务完成。
2. 在没有节点摘要时跳出当前工作节点。
3. 静默丢弃 LLM 认为重要的记忆写入请求。
4. 把旧 snapshot summary 当作完整工作状态。
5. 用 `currentFocus` 代替 `workTree.currentNodeId`。

## 9. 记忆工具协议

LLM 可见的最小记忆工具集：

### 9.1 read_memory_nodes

```yaml
input:
  nodeNamesOrIds: [string]
output:
  nodes:
    - nodeId: string
      parentNodeId: string|null
      title: string
      content: string
      childNodes: [EntityRef]
      relations: [EntityRef]
```

### 9.2 read_memory_index

```yaml
input:
  nodeNamesOrIds: [string]
  expandDepth: integer = 2
output:
  indexEntries:
    - parentNodeId: string
      childNodes: [EntityRef]
      questionsItAnswers: [string]
```

### 9.3 update_memory_node

模式：

| 模式 | 用途 |
| --- | --- |
| `write` | 在父节点下写新节点 |
| `modify` | 改名、改内容、移动父节点 |
| `relation` | 追加、删除或覆盖关联 |

所有写入必须携带：

```yaml
sourceWorkTreeNodeId: string
workTreeVersion: integer
permissionLevel: admin|user|network
```

### 9.4 forget_memory_node

规则：

1. 有子节点时必须返回子节点数并请求二次确认。
2. 高权限记忆不能被低权限主体遗忘。
3. 遗忘必须保留审计记录。

### 9.5 冲突工具

| 工具 | 用途 |
| --- | --- |
| `update_memory_with_version` | 乐观锁重试 |
| `append_memory_log` | 并发资料碎片追加 |
| `submit_memory_proposal` | 大型修改提案合并 |

## 10. 上下文窗口协议

### 10.1 窗口是缓存

上下文窗口只保存：

1. Boot Prompt。
2. `WorkContextStack` 当前 active frames。
3. 当前工作节点。
4. active path 摘要。
5. 父帧 child completion summaries。
6. 当前节点必要资料。
7. 近期工具结果。
8. 必要的侧信道通知。

不保存：

1. 整棵记忆树。
2. 整棵工作树。
3. 已完成节点的详细推演。
4. 大量原始文件全文。
5. 已 pop 子帧的完整 transcript。

### 10.1.1 缓存保留策略

默认策略是 `preserve-prefix`：

1. 根帧、规划帧和父级执行帧构成稳定前缀。
2. 下探子节点时只追加子帧 header、局部资料和工具结果。
3. 子节点完成时移除或 artifact 化子帧长 transcript，只保留摘要回填。
4. 返回父节点时保留父节点原始上下文和 cursor，避免重新生成父级规划。
5. 只有当 provider 不支持缓存、上下文超过阈值、工具 checkpoint 要求安全停止、或 snapshot 恢复需要重建时，才进入 `allow-recompile`。

边界说明：

1. `preserve-prefix` 和 `prefixCacheKey` 先定义的是 runtime continuation contract，也就是“哪段前缀在 push/pop/window continuation 中必须保持稳定”。
2. provider 侧真实缓存命中是第二层信号，来自 usage 里的 `cacheHitInputTokens` / `cacheWriteInputTokens`；它可以增强性能，但不是 continuation 语义本身。
3. 因此，runtime 可以在 provider 没有返回 cache hit 的情况下仍然满足 continuation 合同；同样，单独出现 provider cache 命中也不能替代对 `currentNodeId / topFrameId / prefixCacheKey` 一致性的检查。

### 10.2 自我资源状态

运行时应提供资源状态查询：

```yaml
ContextResourceState:
  estimatedTokens: integer
  hardLimitTokens: integer
  warningThresholdTokens: integer
  currentWorkingNodeId: string
  compressionRecommended: boolean
  restartRecommended: boolean
```

### 10.3 自动警告

当上下文接近阈值时，系统通过侧信道插入警告，提示 LLM：

1. 写当前节点摘要。
2. 压缩中间段。
3. 委派 Sub-Agent。
4. 准备窗口重启。

### 10.4 压缩恢复

压缩必须绑定工作节点范围。恢复时必须先恢复 `Working_Node`，再展开压缩摘要。

压缩优先级：

1. 已 pop 子帧 transcript。
2. 当前父帧中较旧的 child completion summaries，保留短摘要和证据引用。
3. 可由记忆树重新召回的资料。
4. 当前节点直接依赖资料最后压缩。

禁止优先压缩：

1. 当前 top frame header。
2. 当前 `Working_Node`。
3. 当前节点未完成工具调用状态。
4. 当前父帧 `cursorState`。

## 11. 多 Agent 协议

### 11.1 Sub-Agent

适用场景：

1. 大量未知文件预读。
2. 长文本建树。
3. 非决策性验证。
4. 局部资料整理。
5. 独立上下文实验。

主 Agent 必须提供：

```yaml
SubAgentAssignment:
  parentWorkTreeNodeId: string
  assignedWorkTreeNodeId: string
  readonlyContextRefs: [EntityRef]
  writableOutputScope: proposal|work-node-summary|memory-log
  budget: BudgetState
  returnContract: result|evidence|risks|missingInfo|memoryWrites
```

### 11.2 Fork

Fork 是同构 Agent 上下文分裂，不是普通 Sub-Agent。

规则：

1. Fork 前必须创建多个平行工作树子节点。
2. 每个 fork 实例获得一致目标和当前短期记忆副本。
3. 每个 fork 实例只能写自己的节点或提交 proposal。
4. 合并时只读取摘要和证据，不拼接完整上下文。
5. Fork 预算按候选模型能力动态分配，而不是固定平均分配。

预算分配输入：

```yaml
ForkBudgetAllocationInput:
  parentBudget: BudgetState
  forkCount: integer
  childNodeComplexities:
    - nodeId: string
      estimatedTokens: integer
      estimatedToolCost: number
      riskLevel: low|medium|high
  candidateModels:
    - model: string
      contextWindowTokens: integer
      qualityScore: number
      latencyScore: number
      costPer1k: number
```

预算分配输出：

```yaml
ForkBudgetAllocation:
  allocations:
    - nodeId: string
      model: string
      tokenBudgetTotal: integer
      costBudgetTotal: number
      maxContextTokens: integer
      reason: string
  parentReservedBudget: BudgetState
```

规则：

1. 高复杂度或高风险节点优先分配更强模型、更大上下文和更多 token。
2. 简单同构节点可使用低成本模型。
3. 父 Agent 必须保留合并预算，不得把 parent budget 全部分配给 fork 子体。
4. 如果任一子节点没有满足最低上下文或质量门槛的模型，Fork 计划必须降级为串行或请求预算调整。

### 11.3 联邦 Agent

联邦 Agent 使用共享节点、邮箱和提案合并。默认不共享完整上下文。

## 12. 权限与信任

权限等级：

```text
admin > user > network
```

规则：

1. 只能信任同级或更高权限记忆。
2. 低权限记忆必须标记为待验证来源。
3. 高权限记忆冲突时，高权限优先。
4. Sub-Agent 权限低于主 Agent。
5. 网络资料默认 `network` 权限，除非由管理员确认提升。

## 13. 结束批准协议

### 13.1 请求批准

根工作节点完成后，运行时创建：

```yaml
TaskCompletionApprovalRequest:
  taskId: string
  rootWorkTreeNodeId: string
  resultSummary: string
  evidenceRefs: [EntityRef]
  pendingItems: [string]
  incompleteItems: [string]
  memoryWrites: [EntityRef]
  workTreeSummaryRef: EntityRef
  requestedAt: datetime
```

状态迁移：

```text
active -> summarizing -> awaiting-approval
```

### 13.2 批准

批准后：

```text
awaiting-approval -> completed
```

必须落盘：

- `task.completion.approved` event
- 最终工作树 artifact
- 最终任务摘要
- 预算结算

### 13.3 返工

如果用户或上层要求返工：

```text
awaiting-approval -> active
```

必须指定返工节点：

- reopen root
- reopen existing child
- create revision child

## 14. 事件与审计

v0.2 必须预留事件：

| 事件 | 触发 |
| --- | --- |
| `runtime.boot.started` | 开始启动 |
| `runtime.boot.completed` | Boot Prompt 和 root mount 生成完成 |
| `agent.standby.entered` | 进入待机 |
| `agent.standby.wakeup` | 待机被消息或通知唤醒 |
| `work-tree.node.created` | 创建工作节点 |
| `work-tree.node.entered` | 切换当前节点 |
| `work-tree.node.summarized` | 写节点摘要 |
| `work-tree.node.completed` | 完成节点 |
| `work-tree.node.failed` | 节点失败 |
| `work-tree.node.blocked` | 节点阻塞 |
| `work-tree.pc-memo.updated` | 更新程序计数器备忘录 |
| `task.approval.requested` | 根节点完成等待批准 |
| `task.completion.approved` | 批准完成 |
| `task.revision.requested` | 返工 |
| `mailbox.message.received` | 邮箱收到消息 |
| `side-channel.notification.inserted` | 侧信道通知插入 |

## 15. v0.1 兼容和单路径运行

### 15.1 运行路径约束

单路径运行时为默认且唯一运行路径。

- 新任务统一使用 v0.2 Boot Prompt、RootMountPackage 和 WorkTreeProtocol。
- 根节点完成后统一进入 `awaiting-approval`，审批后才进入 `completed`。
- 旧 `completed` 快速路径已淘汰，不再作为可选分支。

### 15.2 旧 artifact 兼容

- 旧 v0.1 artifact 仍需可读。
- 读取时自动升级到 v0.2 所需最小字段（例如 bootstrap 节点、root frame、指针字段）。

## 16. 验收标准

P1/P2 最小验收：

1. RootMountPackage 暴露四个根指针和加载顺序。
2. CompiledPrompt 有结构化 Boot Prompt 四段。
3. 每个运行窗口都有 `Working_Node`。
4. 每个运行窗口都有 `WorkContextStack`，且 top frame 与 `Working_Node` 一致。
5. 子节点完成后默认 pop 回父帧，并保留父级上下文前缀。
6. resume/restart 不重复注入 memo。
7. 工作树根节点完成后进入 `awaiting-approval`。
8. 任务批准后才进入 `completed`。
9. 冷启动无任务时进入 standby，不触发 LLM 推理。
10. 邮箱使用独立 mailbox 表，侧信道字段有稳定占位和 artifact 字段。
11. Fork 预算按模型能力动态分配，且保留父 Agent 合并预算。

建议最小测试：

```powershell
uv run pytest tests/test_prompting_runtime.py tests/test_runtime_p4_foundation.py tests/runtime/test_runtime_restart_and_resume.py -q
```

涉及记忆和共享空间时追加：

```powershell
uv run pytest tests/runtime/test_runtime_core_and_memory.py tests/test_m9_shared_memory.py -q
```

## 17. 已确认产品决策与后续可调点

下列产品决策已确认。实现时按确认决策推进，后续只通过配置或小版本修正具体策略。

| 问题 | 默认决策 | 后续可调整点 |
| --- | --- | --- |
| 批准完成由谁触发 | 用户或上层控制面调用批准接口 | UI 交互、自动验收策略 |
| 邮箱底层存储 | 使用独立 `mailbox` 表；outbox/event 只做投递和审计 | mailbox 索引、归档策略、通知策略 |
| 默认文本输出是否完全忽略 | 产品运行时忽略，开发调试可保留 transcript | UI 提示策略 |
| Fork 的初始上下文预算 | 按模型能力、节点复杂度、上下文窗口和成本动态分配，并保留父 Agent 合并预算 | 分配权重、模型候选策略 |
| 节点长度计数 | 中文按字符估算，英文按词估算 | 后续接 tokenizer 精确计数 |

## 18. 非目标

v0.2 协议冻结不要求一次性完成：

1. 完整邮箱 UI。
2. 完整应用市场与联邦 Agent 购买流程。
3. 完整自动记忆整理 GC。
4. 完整上下文资源监控 UI。
5. 完整多模型自动任务拆分策略。

但所有字段、事件和状态必须为这些能力保留位置。
