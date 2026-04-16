# 模块平台数据规格 v0.1

- 文档状态：Candidate
- 版本：v0.1
- 日期：2026-04-16

## 1. 范围

本规格覆盖以下对象：

- ModuleInstallRecord
- ModuleConfigBinding
- HookContributionRecord
- EventSubscriptionRecord
- HealthReport
- OutboxRecord

## 2. ModuleInstallRecord

```yaml
ModuleInstallRecord:
  id: string
  moduleId: string
  moduleVersion: string
  desiredState: enabled | disabled
  lifecycleState: discovered | validated | incompatible | installed | disabled | enabling | active | degraded | draining | quarantined | uninstalling | removed | failed
  runtimeMode: in-process | remote
  manifestRef: ExternalRef
  configBindingId: string|null
  installedAt: datetime|null
  enabledAt: datetime|null
  disabledAt: datetime|null
  lastError: string|null
```

## 3. ModuleConfigBinding

```yaml
ModuleConfigBinding:
  id: string
  moduleInstallId: string
  configSchemaVersion: string
  effectiveConfigRef: ExternalRef
  sourceMode: database-primary-file-overlay
  updatedAt: datetime
  updatedBy: ActorRef
```

### 3.1 冻结决策

- 模块配置采用数据库为主、文件覆盖为辅。
- 模块不得假设配置只来自磁盘文件。

## 4. HookContributionRecord

```yaml
HookContributionRecord:
  id: string
  moduleInstallId: string
  hookName: string
  implementationRef: string
  executionOrder: integer
  timeoutMs: integer
  sideEffects: none | read-only | controlled-write
  enabled: boolean
  createdAt: datetime
```

## 5. EventSubscriptionRecord

```yaml
EventSubscriptionRecord:
  id: string
  moduleInstallId: string
  eventType: string
  consumerGroup: string
  deliveryMode: at-least-once
  status: active | paused | error
  createdAt: datetime
  updatedAt: datetime
```

## 6. HealthReport

```yaml
HealthReport:
  id: string
  moduleInstallId: string
  status: healthy | degraded | unhealthy | quarantined
  summary: string
  detailsRef: ExternalRef|null
  observedAt: datetime
```

## 7. OutboxRecord

```yaml
OutboxRecord:
  id: string
  projectId: string|null
  aggregateType: string
  aggregateId: string
  eventType: string
  eventVersion: integer
  payloadRef: ExternalRef
  publishStatus: pending | publishing | published | dead-letter
  attempts: integer
  availableAt: datetime
  publishedAt: datetime|null
  lastError: string|null
  createdAt: datetime
```

### 7.1 说明

- OutboxRecord 是正式持久化对象，不允许模块绕过它偷偷直发关键领域事件。

## 8. 第一版约束

- 第一版模块宿主与核心 API 默认拆成独立进程，但允许同机部署。
- 第一版不支持未登记模块直接调用高风险 hook。
- 第一版不支持跳过 ModuleInstallRecord 直接手工注入模块。