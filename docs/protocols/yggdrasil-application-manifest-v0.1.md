# yggdrasil.app.yaml 协议 v0.1

- 文档状态：Draft
- 版本：v0.1
- 日期：2026-04-21
- 关联文档：
  - [yggdrasil.module.yaml 协议 v0.1](yggdrasil-module-manifest-v0.1.md)
  - [Hook 点协议 v0.1](hook-contracts-v0.1.md)

## 1. 目标

应用插件用于声明“哪一个 Agent 应用”被装进基座，以及该应用默认使用哪些 Prompt 资产、记忆资产、能力模块、场景模块、前端入口和重要配置。

Kernel 负责发现、装配、治理和审计应用插件；应用插件负责承载默认模板、场景选择、出厂记忆和不重要的应用内资源。

## 2. 文件位置

- 文件位置：应用根目录
- 一个应用目录只能对应一个 manifest

## 3. 顶层结构

```yaml
apiVersion: yggdrasil.io/v0.1
kind: ApplicationManifest
metadata:
  id: yggdrasil.app.base
  displayName: Base Template
  version: 0.1.0
  owner: core
  description: Default fallback application loaded by the kernel.
  defaultLoad: true
spec:
  dependencies:
    modules:
      - id: subagent-runtime
        version: ">=0.1.0 <0.2.0"
  prompting:
    defaultPromptProfileId: yggdrasil.main-agent
    subagentPromptProfileId: yggdrasil.subagent
    defaultSeedTemplateId: yggdrasil.seed.generic.default
    profileFiles:
      - prompt-profiles/main-agent.yaml
    seedTemplateFiles:
      - scenes/generic-default.yaml
    capabilityModules:
      - subagent-runtime
    sceneModules: []
  config:
    defaultsRef: config/defaults.json
  memory:
    namespace: yggdrasil.app.base
    assetFiles:
      - memory/core-knowledge.yaml
  frontend:
    entryRoute: /applications/yggdrasil.app.base
    dashboardRef: web/dashboard.json
```

memory：应用包内的静态记忆配置，包含 namespace 与 assetFiles。

## 4. 字段定义

### 4.1 metadata

- id：应用唯一标识，必须与运行时 appId 对齐。
- displayName：面向人类的显示名称。
- version：应用语义化版本。
- owner：应用维护方。
- description：应用说明。
- defaultLoad：基座首次启动时是否默认装载。

### 4.2 spec.dependencies.modules

- 声明该应用依赖的能力模块或场景模块。
- Kernel 可以据此做可发现性与装配检查。

### 4.3 spec.prompting

- defaultPromptProfileId：主 Agent 默认 prompt profile。
- subagentPromptProfileId：Sub-Agent 默认 prompt profile。
- defaultSeedTemplateId：无更具体匹配时的兜底场景。
- profileFiles：应用包内的 prompt profile 资产文件。
- seedTemplateFiles：应用包内的 seed template 资产文件。
- capabilityModules：为该应用提供 prompt/profile/tool 能力的模块列表。
- sceneModules：为该应用提供具体场景 seed template 的模块列表。

### 4.4 spec.config

- defaultsRef：应用包内的默认配置文件。
- 重要配置的覆盖值不应写回应用包，应由基座统一管理。

### 4.5 spec.frontend

- entryRoute：应用在控制面的主入口路由。
- dashboardRef：应用包提供的仪表板配置或 UI 元数据。

### 4.6 spec.memory

- namespace：运行时记忆命名空间，用于区分不同应用的私有长期记忆空间，建议默认与 appId 相同。
- assetFiles：应用出厂记忆资产文件列表，基座应将这些文件作为静态知识底座装载；运行时写入不得直接覆盖这些文件。

## 5. 装配语义

- 应用插件发现只负责找到 manifest 和包内资产。
- Prompt profile、seed template 与 memory 的最终装配结果 = 应用包资产 + 应用依赖模块通过 hook 提供的贡献。
- 如果应用声明的 profile、scene 或模块缺失，Kernel 应拒绝把它视为可装配应用。

## 6. 管理边界

- 重要配置：由基座统一保存、覆盖和审计。
- 非重要配置、展示元数据、默认文案、应用内 dashboard 配置、出厂记忆资产：放在应用包内。
- 外部团队在编写应用包时，应默认预留 `memory/` 目录；即使没有静态记忆，也要在文档里明确写“无 memory 资产”，不要省略这一层。

## 7. 第一版约束

- 基座必须能在没有任何具体业务应用时装载默认基础应用。
- 主 Agent 与通用 Sub-Agent 默认模板不允许再以内核常量表形式硬编码。
- 具体场景应优先通过模块贡献，而不是继续把场景表写死在 Kernel。