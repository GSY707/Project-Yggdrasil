# 应用包接口总规范 v0.1

- 文档状态：Candidate
- 适用对象：应用包开发团队、前端团队、模块团队、平台团队
- 目标：让外部团队只看这一份文档，就能为本项目实现一个可装配、可配置、可展示、可验证的应用包。
- 关联文档：
  - [yggdrasil.app.yaml 协议 v0.1](../protocols/yggdrasil-application-manifest-v0.1.md)
  - [Agent 运行时协议 v0.2](agent-runtime-protocol-v0.2.md)
  - [工作树协议 v0.2](work-tree-protocol-v0.2.md)
  - [Graduate Researcher 应用包定义 v0.1](graduate-researcher-app-v0.1.md)

## 1. 总体边界

应用包是挂在 `applications/<appId>/` 下的一组正式资产，不是随意放几份提示词文件。

应用包允许并鼓励包含 `memory/` 目录，用来随包发布静态记忆资产；外部团队实现应用包时，必须把记忆当成正式接口来设计，而不是只做 prompt 和配置。

它负责声明以下内容：

1. 这个应用是谁、依赖什么模块、默认装载什么场景。
2. 主 Agent / Sub-Agent 应该使用哪些 prompt profile、seed template、few-shot 资产。
3. 控制面应该把这个应用展示成什么样子。
4. 运行时应该通过哪些 MCP 工具和模块能力来完成工作。
5. 这个应用随包携带哪些静态记忆资产，以及运行时记忆应使用哪个应用命名空间。

它不负责以下内容：

1. 不在应用包内硬编码敏感密钥。
2. 不把重要配置写死成不可覆盖常量。
3. 不直接读取别的模块内部表结构来完成通信。
4. 不绕过控制面直接改写基座状态。

如果 manifest、提示资产、前端元数据、配置引用或模块依赖缺失，基座应把该应用视为不可装配应用，而不是“先跑起来再说”。

## 2. 标准目录结构

应用包最小推荐结构如下：

```text
applications/<appId>/
├── yggdrasil.app.yaml
├── config/
│   └── defaults.json
├── memory/
│   └── *.yaml|yml|json|md|txt
├── prompt-profiles/
│   └── main-agent.yaml
├── scenes/
│   └── generic-default.yaml
├── few-shots/
│   └── *.yaml|yml|json
└── web/
    └── dashboard.json
```

约定如下：

1. `yggdrasil.app.yaml` 是唯一的应用清单入口。
2. `prompt-profiles/` 存放 prompt profile 资产。
3. `scenes/` 存放 seed template 资产。
4. `few-shots/` 目录下的资产会被递归扫描。
5. `memory/` 存放应用出厂记忆资产，是应用包的一等目录。
6. `config/defaults.json` 存放应用默认配置。
7. `web/dashboard.json` 存放控制面仪表板元数据。

相对路径都以 manifest 所在目录为起点解析；如果某个引用路径不存在，基座应把它当成装配错误，而不是静默降级。

## 3. manifest 接口

manifest 的正式协议见 [yggdrasil.app.yaml 协议 v0.1](../protocols/yggdrasil-application-manifest-v0.1.md)。这里补充应用包视角下的行为约束。

### 3.1 必要字段

至少应提供以下能力：

1. `metadata.id`：应用唯一标识，必须和运行时 `appId` 对齐。
2. `metadata.displayName`：对外显示名称。
3. `metadata.version`：应用版本。
4. `metadata.defaultLoad`：是否作为默认基础应用。
5. `spec.dependencies.modules`：应用依赖的模块列表。
6. `spec.prompting.defaultPromptProfileId`：主 Agent 的默认 prompt profile。
7. `spec.prompting.subagentPromptProfileId`：Sub-Agent 的默认 prompt profile。
8. `spec.prompting.defaultSeedTemplateId`：默认 seed template。
9. `spec.prompting.profileFiles`：应用内 prompt profile 文件列表。
10. `spec.prompting.seedTemplateFiles`：应用内 seed template 文件列表。
11. `spec.prompting.capabilityModules`：提供 prompt/tool 能力的模块。
12. `spec.prompting.sceneModules`：提供场景 seed 的模块。
13. `spec.config.defaultsRef`：默认配置引用。
14. `spec.frontend.entryRoute`：前端入口路由。
15. `spec.frontend.dashboardRef`：dashboard 元数据引用。

### 3.2 运行时读取语义

基座在读取 manifest 后会派生出以下派生值：

1. `manifestPath`：清单文件相对工作区路径。
2. `moduleDependencies`：`spec.dependencies.modules` 的平铺结果。
3. `capabilityModuleIds`：提示/工具能力模块列表。
4. `sceneModuleIds`：场景模块列表。
5. `promptProfileFiles` / `seedTemplateFiles`：相对工作区路径列表。
6. `configDefaultsRef`：默认配置文件引用。
7. `frontendEntryRoute`：前端入口。
8. `dashboardRef`：dashboard 元数据引用。

### 3.3 装配规则

1. manifest 只声明“应用需要什么”，不承担“如何拼装”的执行逻辑。
2. prompt profile 与 seed template 的最终 registry = 应用包资产 + 模块 hook 贡献 + few-shot 资产。
3. 应用包显式声明的 profile、scene、module 若缺失，应用不得被视为可装配。
4. `defaultLoad` 只影响默认激活策略，不代表它比其他应用更完整。

## 4. prompt / 记忆文件接口

这一层定义应用包如何提供“思考资产”和“长期沉淀资产”。

### 4.1 prompt profile 接口

Prompt profile 负责定义一个运行角色的完整行为协议。其结构由 `PromptProfileDefinition` 固定：

1. `id`
2. `name`
3. `version`
4. `runScope`
5. `systemRole`
6. `kernelTruth`
7. `behaviorGuidelines`
8. `toolPolicy`
9. `memoryPolicy`
10. `evidencePolicy`
11. `outputContract`
12. `selfEvolution`（可选）
13. `fewShotRefs`
14. `sourceAppId` / `sourceModuleId`（可选，由加载器回填）

约束：

1. `runScope` 只能是 `main`、`subagent` 或 `any`。
2. `systemRole` 说清楚角色是谁。
3. `kernelTruth` 说清楚运行在什么基座上、哪些事实不能被提示词改写。
4. `behaviorGuidelines` 必须写行为规则，而不是写成松散建议。
5. `toolPolicy` 必须说明工具优先级、调用边界和禁用场景。
6. `memoryPolicy` 必须说明结论如何沉淀为记忆树节点或可检索文档。
7. `evidencePolicy` 必须区分来源事实、实验结果、判断和待验证空白。
8. `outputContract` 必须把输出结构讲清楚，避免模型自由发挥成单段总结。
9. `fewShotRefs` 必须和实际 few-shot 资产一一对应。

### 4.2 seed template 接口

Seed template 负责定义一个场景的身份、语境和执行偏置。其结构由 `SeedTemplateDefinition` 固定：

1. `id`
2. `name`
3. `version`
4. `domain`
5. `scenario`
6. `identityOverlay`
7. `contextOverlay`
8. `executionBias`
9. `toolPolicyOverlay`（可选）
10. `outputStyle`（可选）
11. `retrievalHints`
12. `selectionRules`
13. `fewShotRefs`
14. `sourceAppId` / `sourceModuleId`（可选，由加载器回填）

约束：

1. `seed template` 是场景 overlay，不得改写 boot prompt 的公共边界。
2. `identityOverlay` 只描述“我是谁/我在什么场景里”。
3. `contextOverlay` 只描述场景语境，不得塞进整套运行规则。
4. `executionBias` 用来说明当前场景更偏向什么路径。
5. `retrievalHints` 与 `selectionRules` 必须保留机器可读结构。
6. `fewShotRefs` 应与该场景的示例资产一致，不要让引用漂移。

### 4.3 few-shot 资产接口

few-shot 资产会被递归扫描，结构由 `FewShotAsset` 固定：

1. `id`
2. `name`
3. `version`
4. `description`（可选）
5. `messages`
6. `sourceAppId` / `sourceModuleId`（可选，由加载器回填）

`messages` 中每条消息的结构固定为：

1. `role`：只能是 `user`、`assistant`、`system`
2. `content`：纯文本内容

约束：

1. 一个 few-shot 资产应尽量对应一个完整范式，不要把多个范式粘在一起。
2. 示例内容应该可独立阅读，不依赖仓库外隐式上下文。
3. 如果某个场景需要频繁复用示例，应把它做成正式 few-shot 资产，而不是塞进 prompt profile。

### 4.4 记忆接口

应用包采用混合方案：一部分记忆随包发布，一部分记忆由运行时按 `appId` 命名空间持久化。

应用团队在设计记忆相关资产时，应遵守以下接口约束：

1. 出厂记忆放在 `memory/` 目录，作为可版本化、可审计的应用知识底座。外部团队如果要交付一个完整应用包，不能只提供 prompt files，必须同时说明 memory 目录的内容和用途。
2. 运行记忆按 `spec.memory.namespace` 持久化，默认与 `appId` 同名，作为应用私有长期记忆空间。
3. 长期知识必须沉淀到记忆树节点、可检索文档或正式工件引用里。
4. 结论应包含来源、证据级别、边界、未决问题。
5. 步骤之间只能通过显式产物衔接，不能靠隐式上下文传递关键事实。
6. 如果应用需要附加状态，应把状态放到基座可管理的配置、工作区状态或应用私有记忆空间中，而不是藏在 prompt 文本里。

这意味着：应用包负责“告诉模型如何记忆”，并且可以随包提供静态记忆资产；但它仍然不应该把底层存储实现硬编码到 prompt 里。

### 4.5 应用记忆清单接口

应用包可在 manifest 的 `spec.memory` 中声明以下字段：

1. `namespace`：运行时记忆命名空间，建议默认等于 `appId`。
2. `assetFiles`：应用出厂记忆文件列表，文件相对路径以应用根目录为起点。

约束：

1. `namespace` 必须稳定且可迁移，不能随一次运行随机变化。
2. `assetFiles` 应指向可被基座读出的正式文件，推荐使用 `.yaml`、`.yml`、`.json`、`.md` 或 `.txt`。
3. 应用包的静态记忆资产应尽量以小而稳定的知识卡、决策卡、术语表或默认偏好卡为主。
4. 运行时写入的记忆不得直接覆盖出厂记忆文件，只能写回应用私有记忆空间。

## 5. MCP 服务器接口

应用包本身不直接实现工具执行；它通过模块依赖和 mcp bridge 使用 MCP 能力。

### 5.1 角色分工

1. 应用包负责声明需要哪些能力模块、场景模块和工具偏置。
2. `mcp-bridge` 负责发现、同步、启用和暴露工具。
3. MCP server 负责真正提供工具实现。
4. prompt compiler 负责把当前应用、当前场景和当前可用工具装配成运行时 prompt。

### 5.2 bridge 级接口

`GET /mcp` 返回的状态是控制面的总览，核心字段包括：

1. `projectWorkspace`
2. `workspaceOptions`
3. `servers`
4. `syncedServers`
5. `tools`
6. `availableImports`

### 5.3 bridge 级操作接口

以下操作构成应用包侧可见的 MCP 管理接口：

1. `POST /mcp/imports/refresh`：刷新本机可复制的 MCP 服务定义。
2. `POST /mcp/sync`：同步全部或指定服务到 bridge。
3. `POST /mcp/workspace`：切换 bridge 使用的项目工作区。
4. `POST /mcp/servers`：新增或更新一个 MCP server 定义。
5. `POST /mcp/servers/{serverId}/enable`：启用服务。
6. `POST /mcp/servers/{serverId}/disable`：禁用服务。
7. `POST /mcp/servers/{serverId}/sync`：同步单个服务。

### 5.4 工具暴露规则

1. 对模型公开的不是 remote tool name，而是 bridge 生成的 `exposedName`。
2. `toolPrefix` 用于避免名称冲突，应用团队不得假设远端工具名会原样可见。
3. `keepAlive` 影响 server 生命周期，应用包不应把它当作业务逻辑。
4. 当工具集合变化时，prompt registry 与 compile preview 都应反映最新状态。

### 5.5 面向应用包的工具要求

如果应用需要依赖某类工具，应满足以下规则：

1. 工具能力先通过模块依赖或内建 MCP server 提供，再由应用 manifest 声明使用。
2. 新增工具不能只改 prompt，不改 bridge 或模块实现。
3. 需要外部网络或文档抓取的能力，应通过专用 MCP server 提供，不要把网页抓取逻辑写进应用前端。
4. 需要稳定的工具名时，应把工具稳定性作为接口契约的一部分写入测试和文档。

## 6. 前端界面接口

应用包的前端界面不是“把所有页面都塞进基座”，而是通过 manifest 提供可发现、可跳转、可展示的应用元数据。

### 6.1 manifest 级前端入口

`spec.frontend` 至少应提供：

1. `entryRoute`：应用主入口路由。
2. `dashboardRef`：dashboard 元数据文件。

### 6.2 dashboard.json 接口

当前控制面消费的 dashboard 元数据至少包含：

1. `hero.eyebrow`
2. `hero.title`
3. `hero.summary`
4. `quickActions[]`

`quickActions[]` 内每项至少应包含：

1. `label`
2. `href`

可选扩展字段可以保留，但控制面只保证读取上述最小字段。

### 6.3 前端页面约定

应用包的前端页面应至少满足以下行为：

1. 应用列表页从 `GET /applications` 读取应用清单。
2. 应用详情页从 `GET /applications/{appId}` 读取应用摘要、配置绑定、有效配置和 dashboard。
3. 激活应用通过 `POST /applications/{appId}/activate` 完成。
4. 重要配置更新通过 `POST /applications/{appId}/config` 完成。
5. prompt 管理页通过 `appId` 查询参数切换当前应用。

### 6.4 UI 设计边界

1. 控制面页面只负责展示和操作，不应扫描仓库寻找业务逻辑。
2. 应用专属页面可以存在，但必须通过 manifest 的 `entryRoute` 稳定暴露。
3. dashboard 只适合轻量展示和跳转，不适合承载复杂业务状态机。
4. 应用团队如果要新增交互入口，应优先放在 manifest 能发现的路由和 dashboard 元数据里。

## 7. 控制面 API 接口

下面是应用包最核心的控制面 API。外部团队如果要做应用包，至少要把这些接口的输入输出理解清楚。

### 7.1 应用管理

#### GET /applications

返回应用清单。

响应要点：

1. `activeAppId`
2. `applications[]`
3. `applications[].application`
4. `applications[].configBinding`

#### GET /applications/{appId}

返回单个应用详情。

响应要点：

1. `application`
2. `configBinding`
3. `effectiveConfig`
4. `dashboard`
5. `memoryNamespace`
6. `memoryAssetFiles`
7. `applicationMemoryAssets`

#### POST /applications/{appId}/activate

激活一个应用。

响应要点：

1. `application`
2. `configBinding`
3. `effectiveConfig`

#### POST /applications/{appId}/config

更新应用的重要配置。

请求语义：

1. 推荐使用 `{ "importantConfig": { ... } }`。
2. 如果直接提交对象，基座会把它当作 `importantConfig` 使用。

响应要点：

1. `application`
2. `configBinding`
3. `effectiveConfig`

### 7.2 prompt 与编译预览

#### GET /prompting/prompt-profiles?appId=&activeCapabilities=

返回当前应用可用的 prompt profile。

#### GET /prompting/seed-templates?appId=&activeCapabilities=

返回当前应用可用的 seed template。

#### GET /prompting/registered-tools?appId=&activeCapabilities=

返回当前应用可注册的工具清单。

#### GET /prompting/compile-artifacts?projectId=&taskId=&appId=&limit=

返回 prompt compile artifact 列表。

#### GET /prompting/compile-artifacts/{artifactId}

返回单个 prompt compile artifact、编译消息、关联的 model invocation、请求和响应 payload。

#### POST /prompting/compile-preview

返回一次运行时 prompt 编译预览。

请求常见字段：

1. `appId`
2. `task`
3. `request`
4. `rootMount`
5. `currentContext`
6. `runType`
7. `taskType`
8. `activeCapabilities`
9. `resumePath`

响应要点：

1. `appId`
2. `compiledPrompt`
3. `registeredTools`

### 7.3 MCP bridge

#### GET /mcp

返回 bridge 状态、工作区、server 列表和已桥接工具。

#### POST /mcp/imports/refresh

刷新可复制的本机 MCP 服务定义。

#### POST /mcp/sync

同步全部或指定 MCP server。

#### POST /mcp/workspace

更新 bridge 的项目工作区。

#### POST /mcp/servers

新增或更新 server 定义。

#### POST /mcp/servers/{serverId}/enable

启用 server。

#### POST /mcp/servers/{serverId}/disable

禁用 server。

#### POST /mcp/servers/{serverId}/sync

同步单个 server。

## 8. 配置合并接口

应用包的默认配置不是最终配置。最终配置按以下顺序生成：

1. 读取 `config/defaults.json`。
2. 读取 workspace 里的应用绑定 `importantConfig`。
3. 对两个对象做深合并，后者覆盖前者。

这意味着：

1. 默认值可以放在应用包里。
2. 重要配置应由基座侧工作区状态管理。
3. 任何需要长期变更的运行参数，都不应该只靠改默认文件解决。

## 9. 验收清单

一个应用包要被认为接口完整，至少应满足：

1. `yggdrasil.app.yaml` 可以被基座发现并读出完整摘要。
2. 所有 prompt profile / seed template / few-shot 引用都能落到实际文件。
3. `GET /applications` 和 `GET /applications/{appId}` 返回该应用。
4. `POST /applications/{appId}/activate` 能切换激活态。
5. `POST /applications/{appId}/config` 能更新重要配置并回写有效配置。
6. `GET /prompting/prompt-profiles`、`GET /prompting/seed-templates`、`GET /prompting/registered-tools` 能看到该应用的装配结果。
7. `POST /prompting/compile-preview` 能编译出与应用一致的 prompt。
8. `GET /mcp` 能看到该应用依赖的工具供给。
9. 前端可以通过 `entryRoute` 和 `dashboardRef` 找到入口与导航。

## 10. 交付原则

1. 应用包优先交付“能装配、能运行、能追踪”的正式接口，而不是只交付概念说明。
2. 如果新加字段、新增页面或新增工具能力，必须同步更新这份接口文档。
3. 如果需要破坏性变更，必须先走 RFC，再改 manifest、prompt 资产、前端和 API。