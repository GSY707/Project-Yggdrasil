# yggdrasil.module.yaml 协议 v0.1

- 文档状态：Draft
- 版本：v0.1
- 日期：2026-04-16
- 关联文档：
  - [模块生命周期协议 v0.1](module-lifecycle-v0.1.md)
  - [Hook 点协议 v0.1](hook-contracts-v0.1.md)
  - [事件契约协议 v0.1](event-contracts-v0.1.md)

## 1. 目标

每个模块必须在模块根目录提供一个 yggdrasil.module.yaml，用于声明模块身份、兼容性、运行方式、能力、配置、事件、迁移与前端贡献点。

该文件是模块被发现、安装、启停、治理和审计的唯一正式入口。

## 2. 文件位置

- 文件名固定：yggdrasil.module.yaml
- 文件位置：模块根目录
- 一个模块只能对应一个 manifest

## 3. 顶层结构

```yaml
apiVersion: yggdrasil.io/v0.1
kind: ModuleManifest
metadata:
  id: context-pruning
  displayName: Context Pruning
  version: 0.1.0
  category: runtime
  owner: core
  description: Prune oversized task context without breaking reasoning continuity.
spec:
  runtime:
    mode: in-process
    entryPoint: yggdrasil_modules.context_pruning.plugin:module
    protocol: python-entrypoint
  compatibility:
    kernel: ">=0.1.0 <0.2.0"
  dependencies:
    modules:
      - id: text-memory
        version: ">=0.1.0 <0.2.0"
    adapters:
      - id: model-router
      - id: event-bus
    services:
      - id: nats
        required: true
  capabilities:
    hooks:
      - context.pruning.plan
      - context.pruning.execute
    publishes:
      - context.pruning.requested
      - context.pruning.completed
    subscribes:
      - task.context.overflow
  configSchema:
    type: object
    additionalProperties: false
    properties:
      maxRetainedTokens:
        type: integer
        minimum: 256
    required:
      - maxRetainedTokens
  migrations:
    strategy: alembic
    revisions:
      - 20260416_01_context_pruning
  frontend:
    panels: []
    routes: []
  permissions:
    requested:
      - task.snapshot.read
      - task.snapshot.write
      - node.read
  healthChecks:
    - kind: in-process
      timeoutMs: 3000
```

## 4. 字段定义

### 4.1 顶层字段

- apiVersion：manifest 协议版本。
- kind：固定为 ModuleManifest。
- metadata：模块基础身份信息。
- spec：模块的运行与能力定义。

### 4.2 metadata

- id：模块唯一标识，建议使用 kebab-case，全仓唯一且不可变。
- displayName：面向人类的显示名称。
- version：模块语义化版本。
- category：模块类别，允许值：core-extension、runtime、memory、integration、governance、evaluation、frontend。
- owner：模块所有者，通常是团队或命名空间。
- description：模块功能说明。

### 4.3 spec.runtime

- mode：运行模式，允许值：in-process、remote。
- entryPoint：当 mode 为 in-process 时必须提供。
- protocol：加载协议，允许值：python-entrypoint、grpc、mcp。
- endpoint：当 mode 为 remote 时可提供固定地址或服务发现名。
- startupTimeoutMs：启动超时时间。
- shutdownTimeoutMs：停止超时时间。

### 4.4 spec.compatibility

- kernel：兼容的内核版本范围。
- moduleApi：兼容的模块 API 版本范围。
- frontendApi：如提供前端扩展，则声明兼容的前端扩展 API 版本范围。

### 4.5 spec.dependencies

- modules：依赖的其他模块。
- adapters：依赖的适配器能力。
- services：依赖的外部服务。

依赖项最少包含：

- id
- version 或 required

### 4.6 spec.capabilities

- hooks：本模块实现的 hook 名称。
- publishes：本模块发布的事件类型。
- subscribes：本模块订阅的事件类型。
- commands：可选，对外暴露的命令能力名。

### 4.7 spec.configSchema

- 使用 JSON Schema Draft 2020-12 子集。
- 必须显式声明 additionalProperties。
- 所有敏感字段必须使用 secretRef，而不是明文默认值。

### 4.8 spec.migrations

- strategy：迁移策略，允许值：none、alembic、sql-files、custom。
- revisions：迁移标识列表。
- requiresBackup：是否要求启用前备份。

### 4.9 spec.frontend

- panels：前端面板贡献点。
- routes：前端路由贡献点。
- widgets：前端小组件贡献点。

第一版不要求第三方路由注入，但字段保留。

### 4.10 spec.permissions

- requested：模块声明所需权限能力。
- optional：可选权限能力。

### 4.11 spec.healthChecks

- kind：in-process、http、grpc。
- timeoutMs：超时阈值。
- intervalMs：检查周期。
- failureThreshold：连续失败阈值。

## 5. 必填规则

以下字段为必填：

- apiVersion
- kind
- metadata.id
- metadata.version
- metadata.displayName
- spec.runtime.mode
- spec.compatibility.kernel
- spec.capabilities
- spec.configSchema

## 6. 校验规则

- metadata.id 不允许变更；若需要重命名，应视为新模块。
- version 必须遵守 semver。
- 未声明兼容的模块不得安装。
- 当 mode 为 in-process 时，不得声明 grpc endpoint。
- 当 mode 为 remote 时，必须声明 protocol 与 endpoint 或发现方式。
- hooks、publishes、subscribes 中的名称必须在平台已知注册表中存在。
- migrations 中声明的 revision 必须可解析。

## 7. 安装与启停语义

- manifest 通过校验后才允许进入 installed 状态。
- 配置合法但默认不自动启用，除非 manifest 显式声明 autoEnable 且部署 profile 允许。
- manifest 变更会触发重新验证与兼容性检查。

## 8. 版本兼容策略

- Kernel 主版本不兼容变更时，模块必须显式升级兼容范围。
- 模块次版本可以新增非破坏性字段。
- 模块清单不允许静默忽略未知必填字段。

## 9. 安全要求

- manifest 中不得硬编码长期凭证。
- 所有外部连接凭证必须通过 secretRef 或环境注入。
- 模块请求的权限必须最小化。

## 10. 结果

第一版模块系统以 manifest 为准，不接受“只有代码、没有清单”的模块接入方式。