# 运行时与工具数据规格 v0.1

- 文档状态：Candidate
- 版本：v0.1
- 日期：2026-04-16

## 1. 范围

本规格覆盖以下对象：

- AgentIdentityProfile
- BudgetState
- Task
- AgentRun
- TaskSnapshot
- RootMountPackage
- ContextPruningPlan
- ToolDescriptor
- ToolInvocationRecord
- ModelRouteDecision

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

### 4.1 结构

```yaml
Task:
  id: string
  projectId: string
  spaceId: string
  branchId: string
  title: string
  goal: string
  status: draft | queued | running | pause-requested | paused | restart-requested | restarting | completed | failed | cancelled
  currentFocus: string|null
  currentObjective: string|null
  resumeMessage: string|null
  restartMessage: string|null
  ownerProfileId: string
  executionRootNodeId: string|null
  activeSnapshotId: string|null
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
- running -> pause-requested
- pause-requested -> paused
- paused -> queued
- running -> restart-requested
- restart-requested -> restarting
- restarting -> running
- running -> completed
- running -> failed
- running -> cancelled

### 4.3 约束

- paused 不是异常态，而是正式可恢复态。
- Task 必须始终可映射到一个 execution root 或等价的工作树入口。

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
  agentRunId: string
  projectId: string
  branchId: string
  snapshotType: pause | restart | checkpoint
  status: created | flushed | restorable | consumed | superseded
  resumeToken: string
  contextRef: ExternalRef
  rootMountRef: ExternalRef
  pendingWrites: [EntityRef]
  pendingActions: [object]
  resumeMessage: string|null
  safeStopReason: string
  createdAt: datetime
  consumedAt: datetime|null
```

### 6.2 约束

- pause 只能在 safe-stop 语义满足时生成可恢复快照。
- consumed 快照不能再次作为恢复入口。

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
  rationale: string
  status: proposed | executed | verified | failed
  createdBy: ActorRef
  createdAt: datetime
```

### 8.1 冻结决策

- 困难任务上下文修剪在任何风险级别都不要求人工确认。
- 但所有修剪动作必须留下 ContextPruningPlan 和审计记录。

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

### 11.3 约束

- 任何自动选模都应产生 ModelRouteDecision 记录。
- 候选项必须至少记录 model、provider、scoreSummary。

## 12. 第一版与第二版边界

- 第一版必须实现 Task、AgentRun、BudgetState、ToolDescriptor、ToolInvocationRecord、ModelRouteDecision。
- 第一版必须预埋 TaskSnapshot，即使 pause / resume 在第二版完整交付。