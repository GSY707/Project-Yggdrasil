# 任务暂停、恢复与继续契约 v0.1

- 文档状态：Draft
- 更新时间：2026-06-18
- 适用范围：Task、AgentRun、TaskSnapshot、worker queue、控制面 API、Web 控制入口
- 目标：把“隔天继续任务”和长期恢复定义为硬能力，而不是运行时最佳努力行为。

## 1. 背景与硬决策

本项目的长任务必须允许用户在第二天、数周后甚至更长时间后继续同一个任务现场。该能力是正式产品能力，不是调试辅助能力。

本契约冻结以下决策：

1. `paused` 是正式可恢复状态，不是失败态。
2. 用户触发 Resume 后，不允许因为快照不可用而静默降级成 Start。
3. 可恢复快照的主存储不得依赖 Redis TTL、进程内对象或临时目录。
4. Redis 只能作为热缓存和唤醒队列；任务恢复的权威状态必须在持久存储中。
5. 快照在未被新快照替代或用户显式删除前不得自动过期。
6. 恢复失败时任务必须保持可解释的 `paused` / `resume-blocked` 状态，不得伪装成成功继续。
7. 旧 `restart` 流程只允许作为历史快照迁移、stress 或回放入口，不再作为用户可见的默认续跑路径。
8. 自动快照只保留最新恢复点；用户手动保存的 snapshot 才作为长期分支点保留。
9. 本地 snapshot store 第一版不默认加密。
10. Cancel audit snapshot 默认保留 30 天，且不可作为 Resume 入口。

## 2. 核心术语

### 2.1 Start

Start 是从未运行任务的首次执行请求。Start 可以创建执行根、root mount、首个 work item 和首个 AgentRun。

Start 不得消费 pause snapshot。若任务已有可恢复现场，控制面必须要求 Resume 或 Retry，而不是 Start。

### 2.2 Pause Intent

Pause Intent 是用户或系统发出的“尽快进入安全暂停”的请求。

Pause Intent 不等于立即杀死进程。运行中任务必须在下一个 Safe-Stop 处保存 Durable Snapshot，然后进入 `paused`。

### 2.3 Queued Pause

Queued Pause 是对尚未被 worker claim 的任务执行暂停。

目标语义：

- 对未开始的 `queued` 任务，控制面应移除或作废对应 work item，并将任务转为 `paused`，保存一个 `pre-start` 或 `queue-intent` 快照。
- 对已暂停任务的 Resume work item，如果用户在 worker claim 前再次暂停，应取消该 resume attempt，任务保持 `paused`，原 active snapshot 仍为 `restorable`。
- Queued Pause 不应依赖 worker 后续碰巧执行到某个分支。

### 2.4 Safe-Stop

Safe-Stop 是可以停止并未来恢复的原子边界。满足 Safe-Stop 时必须同时满足：

1. 当前 AgentRun 没有未记录的非幂等外部副作用。
2. 已经完成的工具调用、模型调用、工作树写入和 artifact 写入都有持久记录。
3. 尚未执行的 pending action 以结构化形式写入 snapshot，并带 checksum。
4. 当前工作节点、WorkContextStack、root mount、预算状态和控制面 intent 可从 snapshot 重建。
5. 如果正在等待外部工具或人工输入，等待状态必须有可重放或可补偿的 anchor。

不满足 Safe-Stop 时不得写出 `restorable` 快照。

### 2.5 Durable Snapshot

Durable Snapshot 是长期可恢复任务现场。它必须由持久元数据和持久 payload manifest 共同组成。

Durable Snapshot 必须能跨越：

- worker 进程重启
- Agent Runtime 服务重启
- Core API 服务重启
- 操作系统重启
- Docker Desktop 重启
- Redis 清空或 TTL 到期
- 常规产品备份与恢复
- 有迁移脚本覆盖的版本升级

Durable Snapshot 不能只保存摘要文本。它必须保存恢复执行需要的结构化现场。

### 2.6 Resume

Resume 是从 `paused` 的 Durable Snapshot 继续执行同一任务现场。

Resume 只能从 active snapshot 恢复。恢复过程必须先校验 manifest、checksum、schema version、runtime contract version 和必要外部引用，再 rehydrate。

如果校验或 rehydrate 失败，任务不得进入普通 Start；它必须保持 `paused` 或进入 `resume-blocked`，并记录 blocker。

### 2.7 Continue

Continue 是 worker 内部对同一任务工作链的后续推进，不是用户恢复动作。

Continue 可以发生在以下场景：

- 当前模型回合完成后继续处理同一 work tree 节点。
- 子 Agent 结束后回到父 Agent 编排。
- awaiting approval 后用户批准并进入终态收口。
- 预算追加后继续已排队的运行链。

Continue 不应消费 pause snapshot。只有 Resume 消费或租用 pause snapshot。

### 2.8 Retry

Retry 是失败后的重新尝试。Retry 不保证无损恢复。

Retry 必须保留已有任务历史和失败证据，但可以从失败点附近重新构造请求。Retry 只能用于 `failed`、`resume-blocked` 经用户确认转入修复模式、或明确标记为可重试的 work item。

Retry 不得冒充 Resume。

### 2.9 Cancel

Cancel 是终止任务，不是可恢复暂停。

Cancel 后默认没有可恢复 token。系统可以保存 audit snapshot，但 audit snapshot 不能作为普通 Resume 入口。

### 2.10 Shutdown

Shutdown 是 worker 或服务进程停止。Shutdown 不是任务暂停。

如果进程在可控 shutdown 中停止，worker 应尽力完成当前 Safe-Stop 或写出 crash recovery checkpoint。不可控崩溃依赖 durable work item 和上一个 restorable snapshot 恢复。

## 3. 用户可见语义

### 3.1 Pause

用户点击 Pause 后，可以看到以下状态之一：

| 状态 | 含义 | 可操作 |
| --- | --- | --- |
| `running + pendingControlIntent=pause` | 已请求暂停，任务正在等待 Safe-Stop | 可取消任务，不可 Resume |
| `paused` | 已安全暂停，有 active snapshot | 可 Resume、Cancel、查看现场 |
| `resume-blocked` | 有暂停现场，但当前无法恢复 | 可查看 blocker、运行修复、Cancel |

如果任务已经在队列中但未运行，Pause 应尽快转为 `paused`，不需要等 worker 真正运行一次。

### 3.2 Resume

用户点击 Resume 后，界面应显示 pending resume attempt，但任务不应立即丢失 `paused` 现场。

目标流程：

1. 控制面创建 durable `TaskResumeAttempt`。
2. worker claim resume attempt。
3. worker 校验 snapshot manifest 和所有必要引用。
4. worker rehydrate root mount、work tree、context stack、pending actions、预算与路由状态。
5. rehydrate 成功后创建新的 AgentRun，任务进入 `running`。
6. 新 AgentRun 写出第一个 durable progress record 或替代 checkpoint 后，旧 snapshot 才能被 `consumed` 或 `superseded`。

如果步骤 3 或 4 失败，任务保持 `paused` 或 `resume-blocked`。旧 snapshot 不得被消费。

### 3.3 Continue

Continue 是运行时内部能力，不应作为“恢复暂停任务”的 UI 主词。UI 可以用“继续执行”描述正常运行链，但控制面 API 和日志必须区分：

- `resume`: 从暂停现场恢复。
- `continue`: 从已运行的 work item 链继续推进。
- `retry`: 失败后重试。

### 3.4 Budget Exhausted

预算耗尽不是天然失败。

如果运行时能保存 Safe-Stop，任务必须进入：

```text
paused + safeStopReason=budget-exhausted
```

用户追加预算后，通过 Resume 恢复同一现场。

如果预算在模型调用前就不足，运行时也应写出可解释的暂停现场或 `resume-blocked` blocker，而不是直接失败并丢失继续路径。

## 4. 目标状态机

### 4.1 Task.status

目标用户生命周期只保留以下主状态：

```text
draft
queued
running
paused
resume-blocked
cancelling
cancelled
awaiting-approval
completed
failed
```

`restart-requested` 和 `restarting` 不属于目标用户生命周期。实现阶段应把它们迁出普通控制面，只保留 legacy snapshot 迁移、stress 和回放入口。

### 4.2 主流转

```text
draft -> queued
queued -> running
queued -> paused
running + pendingControlIntent=pause -> paused
paused -> running
paused -> resume-blocked
resume-blocked -> paused
running -> awaiting-approval
awaiting-approval -> running
awaiting-approval -> completed
running -> failed
running -> cancelling -> cancelled
paused -> cancelling -> cancelled
queued -> cancelling -> cancelled
```

`paused -> running` 不是直接状态赋值；它必须经过 durable resume attempt 和 rehydrate 校验。任务可以在 UI 上显示“Resume queued”，但 active snapshot 在真正 rehydrate 成功前仍必须保留。

### 4.3 Work item intent

队列 work item 必须显式携带 intent：

```text
start
resume
continue
retry
approval
cancel-drain
maintenance
```

worker 不得只根据 Task.status 推断执行意图。

### 4.4 禁止流转

以下流转禁止：

- `paused -> draft`
- `paused -> queued` 且没有 durable resume attempt
- `paused -> running` 且没有 snapshot 校验记录
- `resume-blocked -> running` 且没有修复或迁移记录
- `cancelled -> queued`
- `completed -> queued`
- snapshot 校验失败后自动 Start

## 5. Durable Snapshot 数据契约

### 5.1 Snapshot metadata

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

### 5.2 Snapshot manifest

Snapshot manifest 必须是可校验的结构化 payload 索引：

```yaml
SnapshotManifest:
  version: string
  snapshotId: string
  taskId: string
  createdAt: datetime
  contentHash: string
  entries:
    - path: string
      kind: json | markdown | binary | external-ref
      checksum: string
      sizeBytes: integer
      requiredForRestore: boolean
  restorePlan:
    currentNodeId: string|null
    workContextStackRef: string
    rootMountRef: string
    requestStateRef: string
    pendingActionsRef: string
    budgetStateRef: string
    routingStateRef: string
    toolStateRefs: [string]
    artifactRefs: [string]
  compatibility:
    runtimeContractVersion: string
    minRuntimeVersion: string
    migrationRequired: boolean
    migrationId: string|null
```

### 5.3 必须保存的现场

Durable Snapshot 至少保存：

- Task 基本目标、用户原始请求、当前控制 intent。
- 当前 work tree、current node、WorkContextStack、recovery anchor。
- root mount package 和任务级 runtime sections。
- 已完成模型调用摘要、必要原文引用、route decision、provider/model 选择。
- 已完成工具调用记录、pending tool call、pending writes、artifact manifest。
- 预算状态、token 使用、费用使用、下一步预算需求。
- prompt/runtime contract version、模块版本、应用包版本。
- 外部依赖引用和恢复时的验证规则。
- 失败或暂停原因、用户可见 resume message。

### 5.4 不得只保存的内容

以下内容不能单独作为可恢复快照：

- 一段自然语言总结。
- Redis package key。
- Langfuse trace id。
- UI 当前页状态。
- 最近一次 LLM 输出。
- 没有 checksum 的临时文件路径。

这些内容可以作为辅助证据，但不能作为恢复权威数据。

## 6. 存储与保留策略

### 6.1 权威存储

建议的本地第一版实现：

- 数据库保存 TaskSnapshot metadata、ResumeAttempt、WorkItem、事件和索引。
- 文件系统 snapshot store 保存 manifest 与 payload blob。
- Redis 只保存热缓存和唤醒信号。

snapshot store 建议路径由产品 state root 管理，例如：

```text
state/snapshots/{projectId}/{taskId}/{snapshotId}/manifest.json
state/snapshots/{projectId}/{taskId}/{snapshotId}/blobs/*
```

实现可以改用对象存储，但必须保持相同 manifest 契约。

### 6.2 原子提交

写入 restorable snapshot 必须按以下顺序：

1. 构建结构化 snapshot payload。
2. 写入临时 snapshot 目录或 staging object prefix。
3. 计算每个 entry checksum 和 manifest checksum。
4. 持久化并 flush/commit payload。
5. 原子 rename 或 commit manifest。
6. 在数据库事务中把 TaskSnapshot 标为 `restorable`，并设置 `tasks.activeSnapshotId`。
7. 发布 outbox event 或 Redis wakeup。

步骤 6 之前的 snapshot 不能被 Resume 使用。

### 6.3 保留策略

默认策略：

- running 期间自动快照只保留最新一个 `latest-auto`，用于 provider、网络、worker 或进程故障后的恢复。
- paused 且尚未继续的 active snapshot 使用 `active-paused`，必须永久保留，直到用户 Resume、Cancel、删除任务或手动另存。
- 用户 Resume 后，旧 active snapshot 只有在新 AgentRun 写出第一个 durable progress record、替代 snapshot 或终态记录后，才能删除 payload 或标为 `consumed`。
- 用户手动保存的 snapshot 使用 `user-saved`，不可被自动清理，可作为未来分支点。
- Cancel audit snapshot 使用 `cancel-audit`，不可 Resume，默认 `expiresAt = createdAt + 30 days`。
- 被 supersede 的自动 snapshot 可删除或归档，但不得影响 active-paused 或 user-saved snapshot。
- 本地第一版 snapshot store 不默认加密；隐私说明、备份和删除流程必须明确包含 snapshot payload。
- 用户显式删除任务时，必须删除 snapshot metadata、payload、resume token 和 work item。
- 产品备份必须包含 snapshot store；产品恢复后 Resume 仍应可用。

### 6.4 版本升级

长期恢复必须面对版本升级。

恢复前必须做 compatibility check：

- schema version 不支持：`resume-blocked`，blocker=`snapshot_schema_unsupported`。
- runtime contract version 需要迁移且迁移存在：先迁移，再 rehydrate。
- 迁移失败：`resume-blocked`，保留原 snapshot。
- manifest checksum 不匹配：`resume-blocked` 或 snapshot `invalid`，不得 Start。

## 7. Resume Attempt 契约

### 7.1 数据结构

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

### 7.2 租约规则

Resume attempt 使用租约，不使用一次性抢占消费。

规则：

1. worker claim attempt 后，snapshot status 可进入 `leased`，但仍保留为可恢复现场。
2. worker 崩溃或超时后，lease 到期，snapshot 回到 `restorable`。
3. 只有新 AgentRun 写出第一个 durable progress record、替代 snapshot 或终态记录后，旧 snapshot 才能 `consumed` 或 `superseded`。
4. 同一 task 同时只能有一个 active resume attempt。
5. 重复点击 Resume 必须幂等返回当前 attempt。

### 7.3 恢复失败

恢复失败分两类：

| 类型 | 处理 |
| --- | --- |
| 可修复阻塞 | Task -> `resume-blocked`，snapshot -> `blocked` 或保持 `restorable`，记录 blocker |
| 数据损坏 | Task -> `resume-blocked`，snapshot -> `invalid`，保留证据，禁止自动 Start |

可修复阻塞包括缺少迁移、模块版本不兼容、外部引用暂不可用、provider 配置缺失。数据损坏包括 checksum 不匹配、必需 payload 缺失、manifest 无法解析。

## 8. Worker Queue 可靠性契约

当前 pop-before-process 队列模型不足以支撑长期恢复。目标实现必须满足：

1. WorkItem 是持久对象，有 `queued | leased | completed | failed | cancelled | reclaimable` 状态。
2. worker claim 使用 lease，不能 LPOP 后丢失。
3. lease 过期后 work item 可被 reclaim。
4. Redis 只能作为 wakeup，不是 work item 权威存储。
5. work item ack 必须发生在数据库状态更新后。
6. worker 发现 task lock 不可用时，不得把 work item 当作完成处理。
7. task status、snapshot status、work item status 必须在同一事务或 outbox 模式下保持可恢复一致。

推荐本地第一版采用数据库 work item + Redis wakeup；后续可替换为 Redis Streams 或专用队列，但数据库仍是恢复权威。

## 9. 对话分支与手动保存 snapshot

对话分支不是长期暂停/恢复的 P0 前置条件，但本契约必须为它预留正确入口。否则“手动保存 snapshot”只会成为不可用的存档。

目标设计：

1. 自动 snapshot 不直接成为分支点；用户必须先手动保存，或在创建分支时显式把当前 active snapshot 转成 `user-saved`。
2. 分支从 immutable `user-saved` snapshot 创建，不消费原 snapshot。
3. 分支创建新 Task 或新 conversation branch，原任务保持原状态和历史不变。
4. 分支任务拥有自己的 active snapshot、work item、budget 和完成产物。
5. 原 snapshot 可以 copy-on-write 共享 payload，但 manifest 必须 immutable，且引用计数或反向索引必须可被数据治理删除流程识别。
6. 第一版不做“每条消息任意分叉”的完整对话树，也不为每个 token / turn 自动保存长期分支点。

建议 API：

```text
POST /tasks/{taskId}/snapshots/save-current
POST /tasks/{taskId}/branches
```

`save-current` 把当前 active snapshot 或 latest-auto snapshot 标成 `user-saved`，可带 `label` 和 `note`。

`branches` 从 `sourceSnapshotId` 创建新任务分支：

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

实现上不要复用 `Task.branchId` 表达对话分支；该字段已经承载项目/空间分支语义。对话分支应使用独立 `TaskBranch` 或 `conversationBranchId`。

## 10. Tool-call 暂停安全点与等价性

当用户在模型正在 streaming tool-call 时点击 Pause，运行时不得把半个 tool-call 写成 `restorable` snapshot。

目标暂停屏障：

1. Pause request 到达后，当前模型 stream 进入 `draining`，不再启动新的模型请求。
2. 如果 assistant turn 尚未完整结束，只能等待完整 turn、超时失败或写 crash-recovery checkpoint；不能生成普通 pause snapshot。
3. assistant tool-call 完整解析后，必须持久化原始 provider chunk、规范化 arguments、tool call id、调用顺序和 checksum。
4. 若要保证严格的后续上下文等价，推荐在 tool 执行完成且 tool result / side effects / artifacts 全部提交后暂停。
5. 如果选择在“assistant 已产生 tool-call、tool 尚未执行”处暂停，只能保证 pending tool-call 等价；time-sensitive tool 的结果可能因恢复时间不同而不完全等价。

本项目的等价性分三层：

| 等价性 | 能否保证 | 说明 |
| --- | --- | --- |
| 状态机等价 | 必须保证 | 不重复 tool-call，不丢 pending action，不改变 work tree 指针、预算和控制 intent |
| 下一次模型请求等价 | 应保证 | 在 tool result 已提交的 safe-stop 上，Resume 编译出的下一次模型请求应与无暂停路径的 canonical request digest 一致 |
| 模型输出字节等价 | 不保证 | provider 非确定性、模型版本、采样、时间和外部环境可能导致后续输出不同；本契约不承诺这一层 |

因此，对“模型正在输出一个 tool-call，用户此时暂停”的回答是：

- 如果“tool-call 结束”指 tool result 已提交，并且暂停发生在下一次模型请求之前，可以做到与无暂停路径在运行时状态和下一次模型输入上等价。
- 如果“tool-call 结束”只指 assistant 已经输出完整 tool-call、但工具尚未执行，可以做到 pending call 不丢不重；但对会受时间、网络或外部状态影响的工具，不能保证结果与无暂停立即执行完全一样。
- 如果 stream 中途断开或只拿到部分 arguments，不允许生成普通 restorable pause snapshot；应保持运行、等待完整 turn、或进入明确 blocker。

为支撑下一次模型请求等价，snapshot 必须保存或可重建：

- assistant tool-call 原文、规范化 arguments、tool call id 和顺序。
- tool execution record、stdout/stderr、结构化结果、错误、artifact refs 和 side-effect fence。
- work tree、WorkContextStack、pending actions、budget、route decision。
- prompt compiler inputs，或直接保存下一次 canonical compiled request 及 digest。

## 11. 控制面 API 语义

### 11.1 Pause

```text
POST /tasks/{taskId}/pause
```

语义：

- `running`: 设置 `pendingControlIntent=pause`，保持 `running` 并等待 Safe-Stop。
- `queued`: 取消未 claim work item，创建 `pre-start` 或 `queue-intent` snapshot，进入 `paused`。
- `paused`: 幂等返回当前 active snapshot。
- `resume-blocked`: 可保持 blocked，不创建新 pause。
- `completed/cancelled`: 返回不可暂停。

### 11.2 Resume

```text
POST /tasks/{taskId}/resume
```

语义：

- 只允许 `paused` 或用户确认后的 `resume-blocked`。
- 必须存在 active restorable snapshot。
- 创建或返回 durable resume attempt。
- 不得直接把任务改成普通 `queued` 并丢失 paused 现场。

### 11.3 Continue

```text
POST /tasks/{taskId}/continue
```

语义：

- 只用于 awaiting approval、等待用户输入、或已运行链的下一步推进。
- 不消费 pause snapshot。
- 如果任务是 `paused`，控制面必须要求 Resume。

### 11.4 Retry

```text
POST /tasks/{taskId}/retry
```

语义：

- 只用于 `failed` 或明确可重试的 blocked attempt。
- 必须写入 retry reason。
- UI 必须提示 Retry 不是无损恢复。

### 11.5 Cancel

```text
POST /tasks/{taskId}/cancel
```

语义：

- `queued`: 取消 work item，进入 `cancelled`。
- `paused`: 将 active snapshot 转为不可 Resume 的 `cancel-audit` 或删除恢复 token，进入 `cancelled`。
- `running`: 进入 `cancelling`，在下一个安全边界终止；默认保存 30 天 `cancel-audit` snapshot。
- `completed/cancelled`: 幂等返回终态。

## 12. 观测与错误

所有暂停、恢复、继续、重试、取消都必须写事件：

```text
task.pause_requested
task.safe_stopped
task.snapshot_committed
task.resume_requested
task.resume_leased
task.resume_restored
task.resume_blocked
task.snapshot_consumed
task.continue_requested
task.retry_requested
task.cancel_requested
task.cancelled
```

`resume-blocked` 必须暴露：

- blocker code
- blocker message
- snapshot id
- manifest checksum
- 是否可自动修复
- 推荐下一动作

日志和 UI 不得只显示“恢复失败”。

## 13. 验收测试

第一批必须新增或改写的测试：

1. Pause 后清空 Redis，第二天 Resume 成功。
2. Pause 后模拟长时间流逝，snapshot 不因 TTL 消失。
3. Resume attempt 被 worker claim 后 worker 崩溃，lease 过期后仍可 Resume。
4. manifest checksum 损坏时进入 `resume-blocked`，不得 Start。
5. 缺少迁移时进入 `resume-blocked`，迁移补齐后可 Resume。
6. queued task Pause 不需要 worker 执行也能进入 `paused`。
7. Resume work item 尚未 claim 时再次 Pause，原 snapshot 仍 restorable。
8. 预算耗尽前检和后检都进入 `paused + safeStopReason=budget-exhausted` 或明确 blocker。
9. 产品备份恢复后 active snapshot 可 Resume。
10. task 删除会删除 snapshot payload 和 resume token。
11. cancel paused task 后不能 Resume。
12. legacy restart tests 不再作为主续跑验收；必要时迁移为 legacy-only 测试，否则删除。
13. Resume 成功后旧 active snapshot 在新 durable progress record 写入后被删除或标为 consumed；手动保存的 snapshot 不被删除。
14. Cancel 默认生成 30 天过期的 audit snapshot，且不能 Resume。
15. Pause request 发生在 streaming tool-call 中时，必须 drain 到 safe-stop；snapshot 与无暂停路径的下一次 canonical request digest 一致，或进入明确 blocker。
16. 从 user-saved snapshot 创建分支不会消费源 snapshot，父任务和子任务状态互不覆盖。

验收命令应覆盖单元、API、worker 和至少一个 acceptance case。

## 14. 实现路线

### 阶段 1：契约与数据模型

- 更新 runtime data spec，采用本契约的状态和 snapshot status。
- 新增 `TaskResumeAttempt`、持久 `WorkItem`、snapshot manifest schema、snapshot retention class 与 `TaskBranch`。
- 明确 `restart-*` 只属于 legacy/stress。

### 阶段 2：持久 snapshot store

- 把 snapshot payload 从 Redis TTL package 迁出。
- 实现 manifest、checksum、原子提交和 active snapshot 绑定。
- 实现 latest-auto 只保留最新一个、active-paused 永久、user-saved 不自动清理、cancel-audit 30 天过期。
- 产品 backup/restore 纳入 snapshot store。

### 阶段 3：控制面切换

- Pause/Resume/Continue/Retry/Cancel API 按本契约重写。
- Resume 不再先改普通 queued。
- 恢复失败进入 `resume-blocked`，不得 fallback start。
- 新增 save-current snapshot 和从 user-saved snapshot 创建分支的最小 API。

### 阶段 4：worker 队列可靠性

- 用持久 WorkItem + lease 替换 pop-before-process。
- worker lock miss 不再吞掉 work item。
- Redis 仅作为 wakeup。

### 阶段 5：测试清理与验收

- 删除或改写依赖旧 restart 主路径的测试。
- 新增长期恢复、Redis 丢失、worker 崩溃、备份恢复、数据损坏、tool-call pause equivalence 和分支创建测试。
- M9 pause/resume acceptance 必须验证真正长期恢复链，而不是单进程短恢复。

## 15. 已确认产品策略

用户已明确要求“隔天继续任务”可靠，且隔很长时间也应可靠。因此长期持久化不是待决策项。

已确认策略：

- 运行时自动快照只保留最新一个。
- active-paused snapshot 永久保留，直到 Resume、Cancel、删除任务或用户手动保存后明确处理。
- 用户 Resume 后，旧 active snapshot 在新 durable progress record、替代 snapshot 或终态记录写入后删除或标为 consumed。
- 允许用户手动保存 snapshot；手动保存的 snapshot 可作为分支点，不被自动清理。
- 本地 snapshot store 第一版不默认加密。
- Cancel 默认保存 30 天不可 Resume 的 audit snapshot。

对话分支策略：

- 需要做，但不作为 pause/resume P0。
- 第一版只做基于 user-saved snapshot 的显式分支，不做每条消息任意分叉的完整对话树。
