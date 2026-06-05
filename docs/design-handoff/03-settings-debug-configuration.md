# 设置 / 调试 / 配置界面

日期：2026-06-05

## 1. 设计目标

设置、调试和配置界面必须把普通用户、高级用户和维护者分开。当前系统有大量真实控制面，但它们不应该以同样权重暴露给首次用户。

目标不是隐藏能力，而是分层：

- 普通用户：能完成首次启动、provider、预算、工作区、数据位置、备份恢复和应用设置。
- 高级用户：能调整 Prompt、MCP、工具权限、模型、应用配置和任务恢复。
- 维护者：能看评测、观测、日志、raw JSON、内部 ID、API 状态和运行时工件。

## 2. 当前已有入口

现有 Web 工作台已经包含：

- 首次启动检查：`apps/web/app/components/overview-page.tsx`
- 应用重要设置：`apps/web/app/components/application-detail-page.tsx`
- MCP bridge：`apps/web/app/components/mcp-bridge-page.tsx`
- Prompt 管理与编译预览：`apps/web/app/components/prompting-page.tsx`
- 评测：`apps/web/app/components/evaluations-page.tsx`
- 观测：`apps/web/app/components/observability-page.tsx`
- 任务控制和恢复：`apps/web/app/components/task-detail-page.tsx`
- LLM 工作分析：`apps/web/app/components/task-llm-work-analysis.tsx`
- 发布与安全：`apps/web/app/components/release-page.tsx`

问题是这些入口仍像内部控制台。设计目标是把它们重新分层，而不是继续扩展同一个侧边栏。

## 3. 设置分层建议

### 3.1 普通设置

普通设置应包含：

| 设置项 | 用户问题 |
| --- | --- |
| 启动状态 | 现在能不能创建第一个任务？ |
| 模型供应商 | 我配置了哪个 provider？能不能连通？ |
| 模型与预算 | 默认模型、token / cost 上限是多少？ |
| 工作区 | 系统会读写哪个本地目录？ |
| 数据位置 | 数据库、状态根、日志、备份在哪里？ |
| 备份 / 恢复 | 如何导出和恢复？ |
| 隐私与出机 | 什么内容会发给 LLM provider 或观测系统？ |
| 应用默认值 | 每个应用的默认模型、预算、输出风格和工具权限是什么？ |

普通设置不能要求用户编辑 raw JSON，也不能默认展示内部表名、route、queue、branchId、spaceId。

### 3.2 高级设置

高级设置应包含：

- Prompt profile / seed template / compile preview
- MCP server、工具同步、enable / disable
- 工具权限配置
- 应用 raw JSON
- 模型路由策略说明
- 任务恢复 token 和快照
- memory namespace 和应用记忆资产

高级设置需要明确“改这里会影响什么”。特别是 provider、工具权限、Prompt 和 memory namespace，不能只是技术字段。

### 3.3 维护者调试

维护者调试应包含：

- Core API / Agent Runtime / Module Host / Worker 状态
- 数据库、Redis、NATS、Temporal、MinIO、OTel / Langfuse 状态
- 任务运行工件
- LLM invocation、request / response artifact、cost、latency
- evaluation suite 和 release check
- observability spans、logs、errors
- raw API payload 和 internal IDs

这部分可以强大，但不应作为普通用户默认入口。

## 4. 推荐页面地图

| 页面 | 面向人群 | 说明 |
| --- | --- | --- |
| `/settings/startup` | 普通用户 | 首次启动检查、阻塞项、修复动作 |
| `/settings/providers` | 普通用户 / 高级用户 | provider key 状态、测试调用、模型可用性、预算提示 |
| `/settings/workspace` | 普通用户 | 工作区、state root、日志、备份路径 |
| `/settings/data` | 普通用户 / 高级用户 | 数据位置、备份、恢复、计划中的删除治理 |
| `/settings/apps` | 普通用户 / 高级用户 | 应用默认设置，使用 typed controls |
| `/advanced/prompting` | 高级用户 | Prompt 资产、编译预览、artifact |
| `/advanced/mcp` | 高级用户 | MCP bridge、server、工具同步 |
| `/advanced/evaluations` | 维护者 | suite、运行结果、回归 |
| `/advanced/observability` | 维护者 | spans、日志、错误、trace |
| `/advanced/runtime` | 维护者 | 任务快照、恢复、窗口、工具动作、raw artifacts |

具体路由可以由工程阶段决定，但信息架构必须先分层。

## 5. Provider 与模型设置

Provider 设置是普通用户首次成功的硬门槛。设计应覆盖：

- key 是否存在。
- key 不显示明文。
- 可以发起低成本测试调用。
- 当前默认 provider / model。
- 是否允许 paid model。
- 缺 key 时的修复说明。
- 出机说明：任务目标、素材摘要、Prompt 和模型响应会发给对应 provider。
- 预算提示：token / cost 上限、追加预算、失败恢复。

不要把 provider 设置只留在 `.env` 说明里。`.env` 可以作为高级或 fallback 路径。

## 6. 数据与隐私设置

必须清楚区分当前可用和计划中：

| 能力 | 当前状态 | UI 表达 |
| --- | --- | --- |
| 本地数据位置说明 | 可用 | 明确显示 `.yggdrasil`、日志和备份目录 |
| 本地备份 | 可用 | 指向 `corepack pnpm ops:backup`，后续可产品化按钮 |
| 本地恢复 | 可用 | 指向 `corepack pnpm ops:restore` 或恢复命令 |
| Web 删除 / 清理 | 计划中 | 不放危险按钮，只说明计划和当前手动路径 |
| 完整删除证明 | 计划中 | 不承诺 |
| 官方远端数据 | 计划中 | 必须显式账号和同步开关，当前不会自动上传 |
| SaaS | 计划中 | 不提供 uptime 或远端备份承诺 |

删除治理尤其不能做过渡补丁。没有 dry-run、影响预览、备份前置、审计和删除证明前，不应给普通用户危险删除按钮。

## 7. Prompt、MCP、评测、观测的下沉策略

这些能力不是要删除，而是要下沉到高级区：

| 能力 | 普通用户看到 | 高级用户看到 |
| --- | --- | --- |
| Prompt | “任务目标”和“输出风格” | Prompt profile、seed template、compile artifact |
| MCP | “可用工具”和“工具权限” | server、sync、enable/disable、tool exposedName |
| 评测 | “此应用是否可靠”摘要 | suite、case、run、metrics、failure details |
| 观测 | “运行是否正常”摘要 | spans、logs、traceId、service summaries |
| LLM 分析 | “Agent 做了什么” | window、turn、tool、artifact、cache、work tree debug |

设计应为普通用户提供摘要层，再给高级用户进入完整细节的路径。

## 8. 配置编辑规则

设置界面必须遵守：

1. 普通设置用 typed controls。
2. raw JSON 只放在高级模式。
3. 保存前解释影响范围。
4. 高风险设置需要确认。
5. 计划中能力只显示路线和边界，不显示可点击执行按钮。
6. 密钥不明文展示、不写入仓库、不进入普通日志。
7. 文案优先说用户结果，不说内部字段名。
8. 能力变更要同步更新用户文档和目录索引。

## 9. 外包团队交付要求

这一组界面需要交付：

1. 设置中心信息架构。
2. 普通设置、高级设置、维护者调试三层页面原型。
3. Provider 设置完整状态：未配置、已配置、测试成功、测试失败、paid model 禁用、预算不足。
4. 数据与隐私页面：本地数据、出机、备份、恢复、计划中删除和远端服务。
5. 应用配置组件：typed controls、raw JSON 高级折叠、保存确认。
6. Prompt / MCP / 评测 / 观测下沉策略和入口文案。
7. 错误、空状态、加载状态、权限不足和危险操作确认文案。

## 10. 验收问题

验收时要求用户能回答：

- 我现在缺什么才能启动第一个任务？
- 我的 provider key 是否配置好了？
- 默认模型和预算在哪里改？
- 数据、日志、备份在哪里？
- 什么内容会离开本机？
- 当前是否有 Web 删除？如果没有，为什么没有？
- 我要调 Prompt / MCP / 评测 / 观测，应去哪里？
- 改一个应用设置会影响哪些任务？

