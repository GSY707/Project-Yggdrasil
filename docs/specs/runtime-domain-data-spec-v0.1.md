# 运行时与工具数据规格 v0.1

- 文档状态：Candidate
- 版本：v0.1
- 日期：2026-05-15

## 1. 范围

本规格覆盖以下对象：

- AgentIdentityProfile
- BudgetState
- Task
- AgentRun
- TaskSnapshot
- WorkTreeProtocol
- RootMountPackage
- ContextPruningPlan
- ToolDescriptor
- ToolInvocationRecord
- ModelRouteDecision
- WorkerActivityDescriptor

## 2. AgentIdentityProfile

### 2.1 目标

表达“我是谁”根分支中的稳定身份策略与运行偏好。

### 2.2 结构

```yaml
AgentIdentityProfile:
  id: string
  projectId: string
  branchId: string
  identityRootNodeId: string
  writePolicy: kernel-only-canonical + overlay-proposals
  memoryMutationAggressiveness: string
  permissionTier: string
  evolutionDirective: string|null
  allowedToolNamespaces: [string]
  intuitionSigma: number
  treePreferencePrompt: string|null
  createdAt: datetime
  updatedAt: datetime
```

### 2.3 冻结决策

- “我是谁”允许长期改写。
- 但正式长期改写只能由内核态流程完成。
- 普通任务流程只能提交 overlay 或 rewrite proposal，不能直接覆写 canonical identity。

## 3. BudgetState

```yaml
BudgetState:
  tokenBudgetTotal: integer|null
  tokenBudgetUsed: integer
  costBudgetTotal: number|null
  costBudgetUsed: number
  selfThinkTokenLimit: integer|null
  childBudgetMode: inherit | fixed | capped
  maxSubAgents: integer|null
```

## 4. Task

暂停、恢复、继续、重试和取消的正式语义见 [任务暂停、恢复与继续契约 v0.1](task-pause-resume-continuation-contract-v0.1.md)。本节字段必须服从该契约；旧 `restart-requested` / `restarting` 只保留为 legacy/stress 实现细节，不属于目标用户生命周期。

### 4.1 结构

```yaml
Task:
  id: string
  projectId: string
  spaceId: string
  branchId: string
  title: string
  goal: string
  status: draft | queued | running | paused | resume-blocked | cancelling | cancelled | awaiting-approval | completed | failed
  currentFocus: string|null
  currentObjective: string|null
  resumeMessage: string|null
  restartMessage: string|null
  ownerProfileId: string
  executionRootNodeId: string|null
  activeSnapshotId: string|null
  activeResumeAttemptId: string|null
  resumeBlockedReason: string|null
  pendingControlIntent: string|null
  windowIndex: integer
  restartCount: integer
  cumulativeWindowSpanTokens: integer
  carryForwardLossCount: integer
  budget: BudgetState
  pauseRequested: boolean
  lastSafeStopAt: datetime|null
  startedAt: datetime|null
  endedAt: datetime|null
  createdAt: datetime
  updatedAt: datetime
```

### 4.2 状态流转

- draft -> queued
- queued -> running
- queued -> paused
- running + pendingControlIntent=pause -> paused
- paused -> running
- paused -> resume-blocked
- resume-blocked -> paused
- running -> awaiting-approval
- awaiting-approval -> running
- awaiting-approval -> completed
- running -> completed
- running -> failed
- running -> cancelling
- cancelling -> cancelled
- paused -> cancelling
- queued -> cancelling

默认策略说明：

- 默认路径下，窗口超阈值不再进入 restart 流程。
- 超阈值处理顺序为：先执行 context pruning；若压缩后仍超阈值，当前支线直接 `running -> failed`。
- `paused -> running` 必须经过 durable resume attempt、snapshot manifest 校验和 rehydrate，不得通过普通 start/queued 路径伪装。
- `restart-requested` / `restarting` 只允许作为历史 restart snapshot 迁移、stress 或回放实现细节。

### 4.3 约束

- paused 不是异常态，而是正式可恢复态。
- Task 必须始终可映射到一个 execution root 或等价的工作树入口。
- resume-blocked 表示暂停现场存在但当前不可恢复，必须带 blocker code/message，且不得自动 fallback start。

### 4.4 Work tree 投影

Task 的 execution root 负责承载运行时写入，而正式的执行分解由 `TaskTakeoverProtocol.workTree` 提供。

```yaml
WorkTreeProtocol:
  version: string
  rootObjective: string
  status: planned | active | paused | verified | completed
  currentNodeId: string|null
  nodes: [WorkTreeNode]
  recoveryAnchor: string|null
  entropyBudgetRemaining: integer

WorkTreeNode:
  id: string
  title: string
  phase: planning | executing | recovering | restarting | verification | delivery
  status: pending | in-progress | completed | blocked | skipped
  planStepIds: [string]
  constraintIds: [string]
  dependsOn: [string]
  expectedEvidence: [string]
  recoveryAnchor: string|null
```

约束：

- work tree 必须从 takeover plan 派生。
- 任务完成时 work tree 必须同步为 `completed`。
- pause/resume 或 repair 只能通过正式 recovery anchor 续跑。

## 5. AgentRun

```yaml
AgentRun:
  id: string
  taskId: string
  projectId: string
  branchId: string
  parentRunId: string|null
  runType: main | subagent | maintenance | evaluation
  selectedModel: string
  selectedProvider: string|null
  routeDecisionId: string|null
  status: initializing | mounting | running | waiting-tool | draining | pausing | paused | completed | failed | aborted
  nextObjective: string|null
  windowIndex: integer
  restartCount: integer
  cumulativeWindowSpanTokens: integer
  inputTokensUsed: integer
  outputTokensUsed: integer
  costUsed: number
  startedAt: datetime
  endedAt: datetime|null
```

## 6. TaskSnapshot

### 6.1 结构

```yaml
TaskSnapshot:
  id: string
  taskId: string
  agentRunId: string|null
  projectId: string
  branchId: string
  snapshotType: pause | pre-start | budget-exhausted | crash-recovery | audit | legacy-restart
  status: created | committing | restorable | leased | consumed | superseded | blocked | invalid | archived
  schemaVersion: string
  runtimeContractVersion: string
  retentionClass: active-paused | latest-auto | user-saved | cancel-audit
  storageManifestRef: ExternalRef
  manifestChecksum: string
  resumeTokenHash: string|null
  contextRef: ExternalRef
  rootMountRef: ExternalRef
  pendingWrites: [EntityRef]
  pendingActions: [object]
  resumeMessage: string|null
  safeStopReason: string
  blockerCode: string|null
  blockerMessage: string|null
  savedLabel: string|null
  savedByUserId: string|null
  expiresAt: datetime|null
  createdAt: datetime
  verifiedAt: datetime|null
  leasedUntil: datetime|null
  consumedAt: datetime|null
  supersededBySnapshotId: string|null
```

### 6.2 约束

- pause 只能在 safe-stop 语义满足时生成可恢复快照。
- `restorable` 快照必须是 Durable Snapshot，payload 权威存储不得只依赖 Redis、进程内对象或临时目录。
- Resume 只能通过 active `restorable` 快照和 durable resume attempt 执行；校验失败时进入 `resume-blocked`，不得 fallback start。
- legacy-restart 快照必须把 carry-forward package 写入 `contextRef`，并通过 `pendingActions.requestState` 保留下一窗口的 `windowIndex`、`restartCount`、`effectiveContextWindow` 与相关 handoff 元数据。
- 当启用 stress 口径时，restart 快照可以通过 `forcedWindowRestartBudget` 驱动多次受控 handoff；每次 handoff 后该预算必须单调递减。
- consumed 快照不能再次作为恢复入口。
- active restorable snapshot 不得 TTL 删除；产品备份与恢复必须覆盖 snapshot manifest 和 payload。
- running 期间自动快照只保留最新一个 `latest-auto`。
- active-paused snapshot 必须永久保留，直到用户 Resume、Cancel、删除任务或手动保存后明确处理。
- user-saved snapshot 不自动清理，可作为对话分支源。
- cancel-audit snapshot 默认 30 天过期，且不可 Resume。
- 本地 snapshot store 第一版不默认加密。

## 6A. TaskResumeAttempt

### 6A.1 结构

```yaml
TaskResumeAttempt:
  id: string
  taskId: string
  snapshotId: string
  requestedBy: user | system | recovery
  status: queued | leased | restoring | running | blocked | cancelled | completed
  leaseOwner: string|null
  leaseUntil: datetime|null
  blockerCode: string|null
  blockerMessage: string|null
  createdAt: datetime
  updatedAt: datetime
```

### 6A.2 约束

- 同一 task 同时只能有一个 active resume attempt。
- Resume attempt 使用 lease，不得 claim 后立刻消费 snapshot。
- worker 崩溃或 lease 过期后，active snapshot 必须仍可恢复。
- 只有新的 AgentRun 写出第一个 durable progress record、替代 snapshot 或终态记录后，旧 snapshot 才能 `consumed` 或 `superseded`。

## 6B. TaskBranch

对话分支从用户手动保存的 snapshot 创建，不复用 Task 的项目 `branchId` 字段。

```yaml
TaskBranch:
  id: string
  parentTaskId: string
  childTaskId: string
  sourceSnapshotId: string
  sourceSnapshotChecksum: string
  label: string|null
  createdByUserId: string
  createdAt: datetime
```

约束：

- source snapshot 必须是 `user-saved`。
- 创建分支不得消费 source snapshot。
- child task 必须拥有独立 budget、work item、active snapshot 和 completion artifact。
- 第一版只要求显式从 user-saved snapshot 分支，不要求完整消息级对话树。

## 7. RootMountPackage

```yaml
RootMountPackage:
  id: string
  taskId: string
  projectId: string
  branchId: string
  systemIntro: string
  identityRefs: [EntityRef]
  contextRefs: [EntityRef]
  executionRefs: [EntityRef]
  rootSummary: string
  taskObjective: string|null
  resumeMessage: string|null
  budgetState: BudgetState
  activeCapabilities: [string]
  generatedAt: datetime
```

### 7.1 说明

- systemIntro 对应原始设计中的“系统介绍”。
- RootMountPackage 是正式启动数据，不是把提示词拼接过程藏在代码里。

## 8. ContextPruningPlan

```yaml
ContextPruningPlan:
  id: string
  taskId: string
  sourceRunId: string
  nextObjective: string
  protectedRefs: [EntityRef]
  retainedRefs: [EntityRef]
  compressedRefs: [EntityRef]
  droppedRefs: [EntityRef]
  compressionRange:
    startIndex: integer
    endIndex: integer
    maxUncompressedTailBeforeDecompress: integer
  rationale: string
  status: proposed | executed | verified | failed
  createdBy: ActorRef
  createdAt: datetime
```

### 8.1 冻结决策

- 困难任务上下文修剪在任何风险级别都不要求人工确认。
- 但所有修剪动作必须留下 ContextPruningPlan 和审计记录。
- 压缩范围必须受起止约束：
  - 起点：基础规则前缀（合同锚点、关键恢复锚点、系统摘要）不得进入压缩区间。
  - 终点：尾部至少保留 `maxUncompressedTailBeforeDecompress + 1` 个未压缩段，避免“刚压完即触发自动解压”。

## 9. ToolDescriptor

### 9.1 目标

正式定义泛型工具分发器看到的工具描述对象。

### 9.2 结构

```yaml
ToolDescriptor:
  name: string
  moduleId: string
  version: string
  displayName: string
  schemaRef: string
  permissionRequired: [string]
  executionMode: sync | async | stream
  timeoutMs: integer
  idempotent: boolean
```

## 10. ToolInvocationRecord

```yaml
ToolInvocationRecord:
  id: string
  taskId: string
  agentRunId: string
  toolName: string
  argsRef: ExternalRef
  status: requested | running | succeeded | failed | cancelled | timed-out
  resultRef: ExternalRef|null
  errorSummary: string|null
  startedAt: datetime
  finishedAt: datetime|null
```

## 11. ModelRouteDecision

### 11.1 目标

把原始设计中的“模型能力分析与自动任务分配”固化成正式数据对象。

### 11.2 结构

```yaml
ModelRouteDecision:
  id: string
  taskId: string|null
  agentRunId: string|null
  selectedModel: string
  selectedProvider: string|null
  candidateModels: [object]
  reason: string
  budgetScore: number
  qualityScore: number
  latencyScore: number
  routePolicyVersion: string
  createdAt: datetime
```

## 12. WorkerActivityDescriptor

```yaml
WorkerActivityDescriptor:
  name: string
  moduleId: string
  description: string
  implementationRef: string
  timeoutMs: integer
  retryable: boolean
```

约束：

- worker 只能对 `retryable=true` 的 activity 执行自动重入队列。
- `timeoutMs` 是正式活动 SLA/观测字段；当前版本不承诺用进程级 kill 强制中断同步 Python 执行。

### 11.3 约束

- 任何自动选模都应产生 ModelRouteDecision 记录。
- 候选项必须至少记录 model、provider、scoreSummary。

## 12. 第一版与第二版边界

- 第一版必须实现 Task、AgentRun、BudgetState、ToolDescriptor、ToolInvocationRecord、ModelRouteDecision。
- 第一版必须实现 TaskSnapshot、Durable Snapshot manifest、paused、resume-blocked 与 TaskResumeAttempt 的正式恢复契约；不能只预埋字段。
