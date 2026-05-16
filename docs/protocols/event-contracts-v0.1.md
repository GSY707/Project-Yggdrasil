# 事件契约协议 v0.1

- 文档状态：Draft
- 版本：v0.1
- 日期：2026-04-16

## 1. 目标

定义模块化系统中的异步事件信封、命名规范、核心事件目录与兼容策略。

## 2. 事件信封

所有事件必须采用统一信封：

```json
{
  "specversion": "1.0",
  "eventType": "task.pause.requested",
  "eventVersion": 1,
  "eventId": "evt_01J...",
  "occurredAt": "2026-04-16T08:00:00Z",
  "source": "core-api",
  "actor": {
    "type": "user",
    "id": "u_123"
  },
  "projectId": "project_default",
  "spaceId": null,
  "branchId": "main",
  "taskId": "task_123",
  "agentRunId": "run_456",
  "correlationId": "corr_123",
  "causationId": "cmd_789",
  "schemaRef": "yggdrasil://events/task.pause.requested/v1",
  "payload": {}
}
```

## 3. 必填字段

- specversion
- eventType
- eventVersion
- eventId
- occurredAt
- source
- projectId
- correlationId
- payload

第一版为第二版共享空间预留 spaceId 与 branchId 字段，即使当前单项目模式下可能只使用默认值。

## 4. 命名规范

- eventType 格式：<aggregate>.<action>
- 使用小写字母与点分隔。
- 同一事件的破坏性变化通过 eventVersion 升级，不在 eventType 中重复写版本。

示例：

- node.created
- node.versioned
- task.paused
- context.pruning.completed
- module.enabled

## 5. 发布与投递规则

- 关键领域变更先写入 outbox，再异步投递到 NATS JetStream。
- 消费者必须幂等。
- 无法处理的事件必须进入重试或死信流程。
- 事件默认至少一次投递。

## 6. 第一版核心事件目录

### 6.1 节点与关系

- node.created
- node.updated
- node.moved
- node.deleted
- node.versioned
- edge.created
- edge.updated
- edge.deleted

### 6.2 导入与建树

- import.accepted
- import.segmented
- memory.tree.plan.proposed
- memory.tree.materialized
- memory.link.proposed

### 6.3 任务与运行时

- task.created
- task.started
- task.checkpoint.created
- task.pause.requested
- task.paused
- task.resume.requested
- task.resumed
- task.completed
- task.failed
- agent.run.started
- agent.run.completed
- agent.run.failed

### 6.4 启动与上下文处理

- startup.sequence.started
- startup.root-mounted
- startup.completed
- context.pruning.requested
- context.pruning.planned
- context.pruning.completed
- context.restart.requested
- context.restart.completed

### 6.5 记忆写入与来源

- memory.write.requested
- memory.write.completed
- memory.write.failed
- source.annotation.recorded

### 6.6 模块治理

- module.discovered
- module.installed
- module.enabled
- module.degraded
- module.disabled
- module.quarantined
- module.removed

### 6.7 协作与评测

- pr.created
- pr.reviewed
- pr.merged
- pr.rejected
- evaluation.started
- evaluation.completed

## 7. 事件 Payload 原则

- payload 只放本事件必要信息，不复制整份领域对象。
- 大对象通过 objectRef 或 entityRef 引用。
- 所有 payload schema 必须可版本化。

## 8. 任务暂停事件约定

### 8.1 task.pause.requested

payload 至少包含：

- requestedBy
- reason
- pauseMode，允许值：manual、policy
- waitForSafeStop，默认 true

### 8.2 task.paused

payload 至少包含：

- snapshotId
- flushedWrites
- pendingExternalActions
- resumeToken

### 8.3 task.resumed

payload 至少包含：

- snapshotId
- restoredFromCheckpoint
- resumePath

### 8.4 context.restart.requested

payload 至少包含：

- snapshotId
- snapshotType，第一版固定为 `restart`
- restartReason，允许值至少包含 `effectiveContextWindow`、`forcedWindowRestartBudget`、`planned-window-rotation`
- sourceWindowIndex
- targetWindowIndex
- restartCount
- cumulativeWindowSpanTokens
- effectiveContextWindow
- windowRestartThreshold
- carryForwardContextRef
- resumeToken

补充约束：

- `carryForwardContextRef` 指向精简后的 handoff package，而不是重启前完整上下文镜像。
- 同一次 restart handoff 中生成的 `resumeToken` 必须全局唯一，不能复用旧 token。
- 当 stress 口径启用 `forcedWindowRestartBudget` 时，事件对应的 requestState 视图必须体现预算单调递减后的值。

### 8.5 context.restart.completed

payload 至少包含：

- snapshotId
- resumePath，第一版允许值至少包含 `restart-snapshot` 与 `snapshot`
- restoredFromCheckpoint
- sourceWindowIndex
- targetWindowIndex
- restartCount
- carryForwardLossCount
- effectiveContextWindow

补充约束：

- 只有在下一窗口成功消费 restart snapshot、恢复 requestState、并重新进入正式模型调用路径后，才能发布 `context.restart.completed`。
- 如果 restart snapshot 被消费但 carry-forward package 无法恢复到可执行状态，应视为 restart 失败，而不是提前发布 completed。

## 9. 兼容策略

- 新增非必填字段不提升主版本。
- 删除字段或改变字段语义必须提升 eventVersion。
- 消费者必须忽略自己不认识的非必填字段。

## 10. 第一版约束

- 第一版不做跨组织公共事件市场。
- 第一版只允许受信模块发布高风险领域事件。
- 第一版必须为任务暂停和共享空间预留字段，但不要求完整实现全部消费方。