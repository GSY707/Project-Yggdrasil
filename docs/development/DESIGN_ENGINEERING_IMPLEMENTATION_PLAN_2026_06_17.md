# Stitch 设计落到工程实现与未完成项计划

日期：2026-06-17

## 1. 目标

把 `Project Yggdrasil Design System` 中已经验收通过的最终组合落到工程实现，并把验收报告中的未完成项合并成可执行计划。

最终采用设计：

| 页面组 | 工程输入 |
| --- | --- |
| 主页 | V10 Home: No Gateway Label - PASS |
| 应用包 | V8 Application Packages: Dark Four Column Matrix - PASS |
| 设置 | V6 Settings Center: Clean User Language - PASS |
| 启动器 | V9 Launcher Setup: No OS Branding - PASS；V6 Launcher Daily Use: Clean Main Window and Tray - PASS |

证据入口：

- `docs/development/STITCH_DESIGN_ACCEPTANCE_2026_06_17.md`
- `docs/development/stitch-design-captures-2026-06-17/post-rework-v10-passline/`

## 2. 已确认决策

1. 下一轮开始工程实现，但本轮只产出计划，不改代码。
2. 移动端 / 窄屏后续做，不阻塞桌面主路径。
3. 启动器更新、回滚、卸载不先补 Stitch 独立稿，先进入工程规格和实现；实现后用截图验收补齐。
4. 卸载默认保留本地数据；删除本地数据作为高级危险操作，必须二次确认。
5. 新设计直接切换用户路径，不在旧控制台或旧设计上做平滑兼容补丁。
6. 失败 V2-V9 设计只保留文字结论，不重新引入工程。

## 3. 当前有效未完成项

验收报告第 5-16 节中的大量“不通过 / 剩余缺口”是历史记录，已经被 V10/V8/V6/V9-V6 最终组合覆盖。当前仍有效的未完成项如下。

| 未完成项 | 当前判断 | 处理阶段 |
| --- | --- | --- |
| 桌面主路径工程实现 | P0，立即做 | 阶段 1 |
| 旧控制台、旧设计入口清理 | P0，立即做 | 阶段 1-3 |
| 普通用户界面技术词降噪 | P0，随实现做 | 阶段 1-3 |
| 启动器更新 / 回滚 / 卸载的确认、影响预览、失败恢复 | P0，工程侧补齐 | 阶段 2 |
| 移动端 / 窄屏响应式 | P1，桌面稳定后做 | 阶段 4 |
| 200% zoom、键盘焦点、读屏标签、错误关联 | P1，响应式后集中验收 | 阶段 4-5 |
| 应用包运行态下探、返回父步骤、历史窗口折叠 | P1，主路径之后做 | 阶段 5 |
| 再让 Gemini 大批量返工 | 暂不做 | 仅阻塞时小范围补 |

## 4. 阶段 0：实现前收口

目标：确认落点，避免边做边扩大范围。

任务：

1. 查清当前工程入口：
   - Web 主页 / dashboard。
   - 应用包列表与应用详情页。
   - 设置页。
   - 启动器、安装器、托盘和本地产品启动脚本。
2. 标记要直接替换的旧入口：
   - 旧控制台式主页。
   - 普通用户可见的 raw JSON、内部 ID、端口、Docker、API key、CLI 入口。
   - 旧设计绑定测试。
3. 固定实现输入：
   - 只以 V10/V8/V6/V9-V6 最终通过组合为准。
   - 不把 V2-V9 失败稿作为实现来源。
4. 输出实现清单：
   - 文件路径。
   - 页面路由。
   - 需要删除或下沉的旧组件。
   - 需要新增的状态和测试。

完成标准：

- 能列出每组页面的代码入口。
- 能列出旧入口清理清单。
- 没有把失败设计作为工程输入。

### 4.1 阶段 0 收口结果

状态：已完成。以下清单是阶段 1-3 的实现输入，不再把 V2-V9 失败稿、旧控制台语境或过渡兼容层作为默认用户路径来源。

#### 4.1.1 当前工程入口

| 页面组 | 路由 / 脚本入口 | 当前组件 / 数据入口 | 阶段 1-2 改造责任 |
| --- | --- | --- | --- |
| Web 主页 / dashboard | `/`，`apps/web/app/page.tsx` | `apps/web/app/components/overview-page.tsx`，读取 `/workbench/overview` | 直接替换为 V10 Start 首页：材料入口、任务草案、本地隐私、预算 / 时间预估、启动前审批和阻塞提示 |
| 全局壳层 / 导航 | `apps/web/app/layout.tsx` | `apps/web/app/components/sidebar-nav.tsx` | 把普通用户首屏从“正式控制台 / LLM 网关 / 评测 / 观测 / MCP / Prompt”切到产品主路径；高级入口下沉 |
| 任务入口 | `/tasks`，`apps/web/app/tasks/page.tsx` | `apps/web/app/components/tasks-page.tsx`，`apps/web/app/components/task-launch-panel.tsx`，读取 `/tasks`、`/applications`、`/health`，创建 `/tasks` 并启动 `/tasks/{taskId}/start` | 保留为 Start 首页和应用包的主动作底座，但文案改成普通用户语言，不默认暴露 provider key、`.env`、worker、core-api、命令行 |
| 任务详情 | `/tasks/[taskId]`，`apps/web/app/tasks/[taskId]/page.tsx` | `apps/web/app/components/task-detail-page.tsx`，`apps/web/app/components/task-llm-work-analysis.tsx` | 阶段 1 只承接启动后状态；运行态下探、返回父步骤、历史窗口折叠放到阶段 5 |
| 应用包列表 | `/applications`，`apps/web/app/applications/page.tsx` | `apps/web/app/components/applications-page.tsx`，读取 `/applications` | 直接替换为 V8 四应用矩阵；普通卡片显示 Needs / Templates / Settings / Review Status / Primary Action |
| 应用详情 | `/applications/[appId]`，`apps/web/app/applications/[appId]/page.tsx` | `apps/web/app/components/application-detail-page.tsx`，读取 `/applications/{appId}` 和应用 `web/dashboard.json` / `settingsSchema[]` | 作为四应用详情和模板启动底座；模块、Prompt、appId、原始 JSON 下沉到高级详情 |
| 应用包元数据 | `applications/*/yggdrasil.app.yaml`，`applications/*/web/dashboard.json`，`applications/*/config/defaults.json` | `packages/python-sdk/src/yggdrasil_sdk/app_catalog.py`，`packages/frontend-sdk/src/types.ts` | 继续作为产品级信息源；阶段 1 只选四个默认应用：Deep Research、Graduate Writing、Coding Assistant、Knowledge Base |
| 设置 / 数据隐私 | 目前分散在 `/applications/[appId]`、`/release`、`/data-governance` | `application-detail-page.tsx`、`release-page.tsx`、`data-governance-page.tsx` | 新增或重组普通设置中心：AI Service、Spending、Storage、App Defaults、Data & Privacy；高级 / 维护者入口另放 provider、token、raw payload、MCP、评测、观测、运行时调试 |
| 启动器 / 安装器 / 托盘 | `packaging/desktop/windows/*.cmd` | `Yggdrasil.Install.ps1`、`Yggdrasil.Desktop.ps1`、`Yggdrasil.Tray.ps1`、`Yggdrasil.Update.ps1`、`Build-Yggdrasil.DesktopPackage.ps1` | 阶段 1 做安装、打开应用、健康状态、诊断、备份、应用直达；阶段 2 补更新 / 回滚 / 卸载确认、影响预览和失败恢复 |
| 本地产品启动脚本 | `scripts/product-compose.mjs`，根 `package.json` 的 `product:*` / `yggdrasil:up` 脚本 | `infra/docker-compose.product.yml`，`infra/product.env.template`，`packages/python-sdk/src/yggdrasil_sdk/ops_cli.py`，`packages/python-sdk/src/yggdrasil_sdk/ops_runtime/launcher.py` | 保留为桌面封装背后的维护能力；普通用户 UI 不直接展示 Docker、端口、compose 命令、provider key 参数 |
| Web 到 Core API 代理 | `apps/web/app/api/core/[...path]/route.ts` | 默认代理到 `http://127.0.0.1:5000`，错误文案会暴露 core API 地址 | 保留代理实现；阶段 1 把用户可见错误改成“本地服务未启动 / 需要诊断”，地址和 API 细节进入高级诊断 |

#### 4.1.2 旧入口与技术词清理清单

P0 直接替换或下沉：

1. `apps/web/app/layout.tsx`：首屏壳层仍写“World Engine Workbench”“正式控制台”“Web 现在直接消费 core-api”“LLM”等控制台语境；阶段 1 改为产品入口，不保留旧控制台首屏。
2. `apps/web/app/components/sidebar-nav.tsx`：`MCP`、`Prompt`、`评测`、`观测`、`发布与安全` 当前与普通入口同级；阶段 1 改为高级 / 维护者分组或二级入口。
3. `apps/web/app/components/overview-page.tsx`：默认显示数据库 / Redis JSON、模块状态、outbox、评测、模型调用、provider、token、taskId 等内部字段；阶段 1 从普通首页移除，必要内容转为“系统是否准备好”和“需要处理的问题”。
4. `apps/web/app/components/task-launch-panel.tsx`：普通错误提示直接给出 `uv run`、`corepack pnpm`、`.env`、provider key、worker、Core API；阶段 1 改为用户动作，例如“打开设置连接 AI 服务”“启动本地产品”“查看诊断”，具体命令只进高级诊断。
5. `apps/web/app/components/applications-page.tsx`：应用卡片直接展示“内部 ID {manifest.appId}”、模块数、场景数；阶段 1 改为用户可理解的用途、材料需求、产物、模板和启动动作。
6. `apps/web/app/components/application-detail-page.tsx`：默认区域仍暴露 `provider`、`tokenBudgetTotal`、Prompt、种子模板、memory namespace、raw JSON、`effectiveConfig` pre；阶段 1-3 只保留用户级重要设置，技术配置进入高级详情。
7. `apps/web/app/components/release-page.tsx`：默认显示 `uv sync`、`corepack pnpm`、Docker Compose、localhost、`.env`、provider key、JSONL、备份命令；阶段 1-2 改为桌面产品和数据边界说明，高级维护命令下沉。
8. `apps/web/app/components/data-governance-page.tsx`：删除闭环能力可复用，但 Scope ID、Manifest、remoteBoundary JSON、state root、product logs、backup root 等应从普通设置页下沉到高级 / 维护者层。
9. `apps/web/app/components/prompting-page.tsx`、`mcp-bridge-page.tsx`、`evaluations-page.tsx`、`observability-page.tsx`、`nodes-page.tsx`、`node-detail-page.tsx`：不是删除对象，但不再作为普通用户默认主路径入口。
10. `packaging/desktop/windows/Yggdrasil.Tray.ps1`：托盘菜单目前是 Start/Open、Status、Logs、Backup、Snapshots、Restore Latest、Check Updates、Apply Update、Rollback、Stop Product；阶段 1-2 保留能力但重写为用户语言，并补影响预览 / 二次确认 / 失败恢复。
11. `packaging/desktop/windows/Yggdrasil.Install.ps1`：卸载当前直接删除桌面封装和快捷方式；阶段 2 必须改成默认保留本地数据，删除本地数据为高级危险操作并二次确认。
12. `packaging/desktop/windows/Yggdrasil.Update.ps1`：已限制为检查和显式 apply，不做静默自动更新；阶段 2 继续保留这个决策，并补用户可见状态和失败恢复。
13. `apps/web/app/api/core/[...path]/route.ts`：普通页面报错时可能透出 core API 地址；阶段 1 改成面向用户的本地服务状态，地址进入诊断详情。
14. `apps/web/app/components/task-detail-page.tsx`、`task-llm-work-analysis.tsx`：任务 ID、branchId、snapshotId、resume token、traceId、provider、request/response locator、raw JSON 等运行细节保留为高级运行分析，不压住普通用户任务状态。
15. `apps/web/app/components/assets-page.tsx`、`collaboration-page.tsx`：assetId、summaryNodeId、spaceId、branchId、mountId、tupleId、Condition JSON 等内部对象不进入普通首任务路径。
16. `packages/python-sdk/src/yggdrasil_sdk/ops_cli.py`、`ops_runtime/launcher.py`：继续作为 CLI / 源码产品启动实现，但不再直接驱动普通用户文案。

#### 4.1.3 固定实现输入

唯一工程输入：

- 主页：`docs/development/stitch-design-captures-2026-06-17/post-rework-v10-passline/html/01-home-1d381085f787499aaf7e77d686f5f898.html`
- 应用包：`docs/development/stitch-design-captures-2026-06-17/post-rework-v10-passline/html/02-application-package-00913576626343079aea3fbd05f4879c.html`
- 设置：`docs/development/stitch-design-captures-2026-06-17/post-rework-v10-passline/html/03-settings-c600b347a57f4516a777c934bc0e7c19.html`
- 启动器安装：`docs/development/stitch-design-captures-2026-06-17/post-rework-v10-passline/html/04-launcher-ddbd09ed1cf7449782acb76d3506ce5b.html`
- 启动器日常：`docs/development/stitch-design-captures-2026-06-17/post-rework-v10-passline/html/05-launcher-38c3277b844541ffabd47c580abde105.html`
- 验收依据：`docs/development/STITCH_DESIGN_ACCEPTANCE_2026_06_17.md` 第 18 节最终结论和 `post-rework-v10-passline/manifest.json`

禁止作为实现输入：

- V2-V9 失败稿的视觉和信息架构。
- “Yggdrasil OS” 品牌。
- 旧控制台式首页、旧 dashboard 文案、旧设计绑定断言。
- 为旧入口保留平滑迁移的兼容页面。

#### 4.1.4 阶段 1-3 文件级实现清单

| 优先级 | 文件 / 模块 | 动作 |
| --- | --- | --- |
| P0 | `apps/web/app/layout.tsx`、`apps/web/app/components/sidebar-nav.tsx`、`apps/web/app/globals.css` | 重做产品壳层、导航分层和桌面主路径样式；普通入口只保留 Start、Apps、Settings、Help / Diagnostics 的主线 |
| P0 | `apps/web/app/components/overview-page.tsx` | 以 V10 直接替换旧总览，不保留旧控制台布局；把 `SetupChecklist` 语义转成用户可处理的问题列表 |
| P0 | `apps/web/app/components/task-launch-panel.tsx` | 作为 Start 首页和应用详情的启动控件底座；新增材料入口、草稿状态、预算 / 时间预估、启动前审批；错误 remediation 改成用户动作 |
| P0 | `apps/web/app/components/applications-page.tsx` | 改成 V8 四列矩阵；如果 catalog 中应用超过四个，普通页只突出四个默认应用，其余下沉到高级 / 更多 |
| P0 | `apps/web/app/components/application-detail-page.tsx` | 对齐 Needs / Templates / Settings / Review Status / Primary Action；raw JSON 和元数据只在高级详情显示 |
| P0 | `apps/web/app/components/release-page.tsx`、`apps/web/app/components/data-governance-page.tsx` | 拆出普通设置需要的数据位置、隐私、备份和危险操作确认；命令、路径和远端边界 JSON 下沉 |
| P0 | `apps/web/app/api/core/[...path]/route.ts` | 保留 API 代理能力，但把用户可见连接失败文案从 core API 地址改成产品状态 / 诊断动作 |
| P0 | 新增设置入口，或重组现有 `/release`、`/data-governance`、应用设置 | 实现 V6 Settings Center：AI Service、Spending、Storage、App Defaults、Data & Privacy、高级 / 维护者入口 |
| P0 | `packages/frontend-sdk/src/types.ts` | 如现有类型缺少预算预估、材料需求、review status、设置分组、维护动作状态，补稳定契约 |
| P0 | `packages/python-sdk/src/yggdrasil_sdk/app_catalog.py`、`applications/*/web/dashboard.json` | 只在必要时补四应用矩阵所需元数据；不把前端写死成无法读取应用包配置 |
| P0 | `package.json`、`scripts/product-compose.mjs`、`packages/python-sdk/src/yggdrasil_sdk/ops_cli.py`、`ops_runtime/launcher.py` | 作为启动器 / 桌面产品背后的维护链路，不作为普通用户主屏命令清单 |
| P0 | `packaging/desktop/windows/Yggdrasil.Install.ps1`、`Yggdrasil.Desktop.ps1`、`Yggdrasil.Tray.ps1`、`Yggdrasil.Update.ps1` | 阶段 1 实现启动器用户语言和应用直达；阶段 2 补更新、回滚、卸载确认与失败恢复 |
| P0 | `packaging/desktop/windows/README.md` | 随启动器实现同步普通用户入口与高级维护入口边界 |
| P0 | `docs/DIRECTORY_REFERENCE.md` | 每轮文档 / 入口变化都同步索引 |
| P1 | `apps/web/app/components/task-detail-page.tsx`、`apps/web/app/components/task-llm-work-analysis.tsx` | 阶段 5 再做运行态下探、返回父步骤、历史窗口折叠 |

#### 4.1.5 测试与验收清单

需要新增或更新：

1. 前端 smoke / 组件测试：普通用户首页不默认出现 `core-api`、`Docker`、`provider key`、`.env`、`raw JSON`、内部 ID、端口和 CLI 命令。
2. 应用包测试：四应用矩阵能从 catalog / dashboard 元数据生成 Needs、Templates、Settings、Review Status、Primary Action。
3. 任务启动测试：缺 AI 服务、缺材料、预算不足、启动前审批、只创建草稿、创建并启动都能表达正确状态。
4. 设置测试：AI Service、Spending、Storage、App Defaults、Data & Privacy 与高级 / 维护者入口分层明确；危险操作二次确认。
5. 启动器脚本测试：安装、打开、健康状态、诊断、备份、检查更新、应用更新、回滚、卸载失败恢复都有可观察状态；卸载默认保留本地数据。
6. 截图验收：主页、应用包、设置、启动器安装、启动器日常、更新 / 回滚 / 卸载确认。
7. API 代理与错误文案测试：Core API 不可达时普通界面不显示 `127.0.0.1:5000`、端口或 raw fetch 错误，只显示本地服务状态和诊断入口。

需要删除或改写的废旧测试：

- 任何断言旧首页必须显示“控制台”“core-api”“LLM 网关”“MCP”“Prompt”“评测”“观测”为普通导航主项的测试。
- 任何断言普通用户应用卡片必须显示 `appId` / 内部 ID / 模块 ID / 场景 ID 的测试。
- 任何把 raw JSON、`.env`、provider key 或命令行 remediation 当作普通用户默认提示的测试。
- 任何引用 V2-V9 失败稿作为目标视觉或结构的测试。

当前已定位的主要回归入口：

- `tests/api/test_persistence_control_plane_api.py`：覆盖 `/applications`、`dashboard.taskTemplates`、`settingsSchema`、应用详情 `effectiveConfig`、Prompt compile preview、registered tools、activate 和 `importantConfig`。保留 API 语义，但不能让这些断言牵引普通 UI 继续暴露 Prompt / JSON / appId。
- `tests/api/test_persistence_app_scope_api.py`：覆盖 app-scope、`/tasks`、`/runtime/model-invocations`、`/prompting/compile-artifacts` 按 `appId` 过滤。保留作用域语义，UI 不默认显示内部 ID。
- `tests/api/test_provider_configuration_api.py`：覆盖 provider key 配置状态和密钥不泄露。保留“不泄露明文 key”语义，普通设置文案改为 AI Service 连接状态。
- `apps/web/package.json` 当前只有 `dev`、`build`、`lint`、`typecheck`，没有项目自有前端单测；阶段 1-3 若新增前端测试，需要同步脚本和文档。

#### 4.1.6 阶段 0 未完成项

无硬性阻塞。阶段 0 的目标是收口和列清单，已完成。代码实现、截图验收和废旧测试删除进入阶段 1-3 执行。

## 5. 阶段 1：桌面主路径 P0

状态：已完成主体实现（2026-06-17）。本阶段已直接切换普通用户 Web 主路径和 Windows 启动器主入口；未进入阶段 2 的更新 / 回滚 / 卸载危险操作闭环仍保持后续项。

目标：让普通用户不用命令行就能从产品入口完成首次成功路径。

### 5.0 阶段 1 实现结果

已完成：

1. `apps/web/app/layout.tsx`、`apps/web/app/components/sidebar-nav.tsx`、`apps/web/app/globals.css`：全局壳层改为本地产品入口；普通导航只保留开始、任务、应用、设置和支持入口；MCP、Prompt、评测、观测等移入维护者入口；去掉旧控制台首屏文案。
2. `apps/web/app/components/overview-page.tsx`：旧总览直接替换为 Start 首页，显示材料入口、任务草稿、本地隐私、AI 服务状态、阻塞项和启动前确认入口，不再默认展示数据库、Redis、模型调用、端口、raw JSON 等内部指标。
3. `apps/web/app/components/task-launch-panel.tsx`：任务启动面板改为普通用户语言，保留草稿和立即启动路径；连接失败、数据服务失败、任务队列失败和 AI 服务未连接都改成“设置 / 帮助与诊断”动作，不再在普通错误里输出命令、端口、`.env` 或 provider key。
4. `apps/web/app/components/applications-page.tsx`：应用页改为四应用统一矩阵，默认突出 Deep Research、Graduate Writing、Coding Assistant、Knowledge Base，并用 Needs / Templates / Settings / Review Status / Primary Action 同一信息架构展示。
5. `apps/web/app/components/application-detail-page.tsx`：应用详情继续承接模板启动和设置，但普通摘要不再默认展示 appId、Prompt、memory namespace、effectiveConfig raw JSON；装配信息进入维护者详情。
6. `apps/web/app/components/settings-page.tsx`、`apps/web/app/settings/page.tsx`：新增普通设置中心，覆盖 AI Service、Spending、Storage、App Defaults、Data & Privacy，并把 Prompt、MCP、评测、观测等放到维护者入口。
7. `apps/web/app/api/core/[...path]/route.ts`：Core API 不可达时返回产品级“本地服务未启动 / 查看帮助与诊断”错误，不再暴露 `127.0.0.1:5000` 或 raw target URL。
8. `packaging/desktop/windows/Yggdrasil.Desktop.ps1`、`Yggdrasil.Tray.ps1`：新增应用页和设置页直达动作，快捷方式与托盘菜单改成 Start / Apps / Settings / Health and Diagnostics / Back Up Local Data 等用户语言，不再把普通入口写成 Web 控制台或日志优先。
9. 验证：`corepack pnpm --filter @yggdrasil/web typecheck` 通过；`corepack pnpm --filter @yggdrasil/web build` 通过，生成 `/settings`、`/applications`、`/` 等路由。

本阶段未完成，进入后续阶段：

1. 阶段 2 的更新 / 回滚 / 卸载影响预览、二次确认和失败恢复闭环尚未实现。
2. 移动端 / 窄屏、200% zoom、键盘焦点、读屏标签和错误关联仍按阶段 4-5 集中验收。
3. 应用包运行态下探、返回父步骤、历史窗口折叠仍按阶段 5 处理。
4. 前端专用 smoke / 组件测试尚未新增；当前验证使用 TypeScript typecheck 和 Next build。

### 5.1 主页

实现内容：

- Start 首页。
- 添加材料入口。
- 任务草案区域。
- 本地隐私说明。
- 预算 / 时间预估。
- 启动前审批动作。
- 缺 AI 服务、缺材料、预算不足等阻塞提示。

必须清理：

- 默认界面里的 Terminal、CLI、MCP、raw JSON、内部 ID、端口、Docker、API key。
- 旧控制台式高级入口抢占首屏的问题。

完成标准：

- 首屏回答“现在能做什么、缺什么、下一步点哪里”。
- 普通用户能从空白状态走到创建 / 确认任务。

### 5.2 应用包

实现内容：

- 四应用统一矩阵：
  - Deep Research。
  - Graduate Writing。
  - Coding Assistant。
  - Knowledge Base。
- 每个应用使用同一信息架构：
  - Needs。
  - Templates。
  - Settings。
  - Review Status。
  - Primary Action。

必须清理：

- 把运行日志、内部节点、文件树、调试输出下沉到高级详情。
- 不再让四类应用各走一套不一致页面模型。

完成标准：

- 用户能比较四类应用的用途、材料需求、预期产物和启动动作。
- 应用包入口能承接现有 `dashboard.json` / `settingsSchema[]` 元数据。

### 5.3 设置

实现内容：

- 普通设置：
  - AI Service。
  - Spending。
  - Storage。
  - App Defaults。
  - Data & Privacy。
- 高级 / 维护者入口：
  - provider 细节。
  - token / API key。
  - raw payload。
  - MCP、评测、观测、运行时调试。

必须清理：

- 普通设置页不直接暴露路径、provider、token、API key、schema 等技术词。
- 技术项可以存在，但必须进入高级 / 维护者层。

完成标准：

- 普通用户能完成连接 AI 服务、设置预算、选择数据位置、理解外发风险。
- 危险操作有明确确认。

### 5.4 启动器

实现内容：

- 安装向导。
- 桌面主窗口。
- 托盘菜单。
- 应用直达。
- 系统健康与需要处理的问题。
- 诊断入口。
- 备份入口。
- 更新入口。

必须清理：

- 不使用 `Yggdrasil OS` 品牌。
- 不把 Docker、端口、Core API 等技术状态放在普通用户主文案里。
- 应用快捷方式不能只打开通用控制台，应进入应用页或任务启动页。

完成标准：

- 用户能完成安装、打开应用、查看健康状态、处理问题、进入设置 / 诊断 / 备份。

## 6. 阶段 2：启动器维护闭环 P0

状态：已完成（2026-06-18）。更新、升级、回滚和卸载已经具备影响预览、手动确认、成功 / 失败状态记录和恢复动作说明，并已在干净工作区和真实 Docker 产品栈上补齐维护链验证。

目标：补齐最终稿中没有完整分屏展示、但工程必须存在的危险操作闭环。

### 6.0 阶段 2 实现结果

已完成：

1. `packaging/desktop/windows/Yggdrasil.Update.ps1`：`check` 写入 `update-state.json`，包含当前版本、目标版本、fast-forward 状态、变更文件预览、是否会备份 / 重启和恢复建议；`apply` 只允许 clean worktree + fast-forward，执行前需要输入 `APPLY UPDATE` 或显式传 `-ConfirmApply`；失败写入 `update-failed`、错误和恢复动作。
2. `packaging/desktop/windows/Yggdrasil.Desktop.ps1`：`upgrade` 执行前输出影响预览并要求 `UPGRADE YGGDRASIL` 确认；`rollback` 输出当前版本、备份快照、影响范围和恢复动作，并要求 `RESTORE PREVIOUS VERSION` 确认；成功 / 失败写入 `maintenance-state.json`。
3. `packaging/desktop/windows/Yggdrasil.Install.ps1`：卸载默认保留本地数据；`-DeleteLocalData` 只删除仓库内 `.yggdrasil` 和 `.yggdrasil-backups`，且必须输入 `DELETE LOCAL DATA` 或显式传 `-ConfirmDeleteLocalData`；`infra/product.env` 默认保留；成功 / 失败写入 `%LOCALAPPDATA%\ProjectYggdrasil\uninstall-state.json`。
4. `packaging/desktop/windows/README.md`：同步用户入口、维护确认、失败恢复、默认保留本地数据和危险删除命令。
5. 验证：三个 PowerShell 脚本均通过 `System.Management.Automation.Language.Parser.ParseFile` 解析检查。
6. 2026-06-18 补验：
   - `Yggdrasil.Update.ps1 check` 与 `apply -ConfirmApply` 在当前版本已是最新时返回 `current`，仍写出 `impactPreview`。
   - `Yggdrasil.Install.ps1 install` 真实安装到 `%LOCALAPPDATA%\ProjectYggdrasil\Desktop` 并生成 `install.json`。
   - `Yggdrasil.Install.ps1 uninstall -DeleteLocalData` 在非可见终端中拒绝继续，并在删除前停住，`.yggdrasil` 保持存在。
   - 默认 `Yggdrasil.Install.ps1 uninstall` 移除封装和快捷方式，`%LOCALAPPDATA%\ProjectYggdrasil\uninstall-state.json` 写入 `uninstall-succeeded`，且本地 `.yggdrasil` 保留。
   - `Yggdrasil.Desktop.ps1 upgrade -ConfirmUpgrade` 在依赖服务缺失时先写入 `upgrade-failed` 与恢复动作；补齐完整产品栈后真实创建保护性备份、重建产品栈并写入 `upgrade-succeeded`。
   - `Yggdrasil.Desktop.ps1 rollback -ConfirmRollback` 真实创建保护性备份、恢复快照并写入 `rollback-succeeded`。
   - 产品栈 smoke 发现 Python 侧仍固定读取 `infra/product.env.template`，在临时端口 3300 下误报 Web unreachable；已修复为和 `scripts/product-compose.mjs` 一样优先读取未跟踪 `infra/product.env`，并新增 `tests/test_product_compose_smoke_config.py` 锁定。

本阶段剩余项：无。破坏性删除本地数据未执行，这是设计要求下的保护边界；已验证未显式确认时不会删除。

### 6.1 更新

状态：

- 检查更新。
- 有新版本。
- 影响预览。
- 手动确认。
- 更新中。
- 更新成功。
- 更新失败。

规则：

- 不做静默自动更新。
- 必须显示手动检查 / 手动应用 / 可回滚。
- 失败时保留旧版本，并给出重试和诊断入口。

### 6.2 回滚

状态：

- 当前版本。
- 可回滚版本。
- 最近备份快照。
- 影响预览。
- 二次确认。
- 回滚中。
- 回滚成功。
- 回滚失败。

规则：

- 回滚前说明可能影响的应用包、任务、配置和本地数据。
- 回滚失败时保持当前版本，不进入半更新状态。

### 6.3 卸载

状态：

- 卸载入口。
- 默认保留本地数据。
- 高级危险操作：删除本地数据。
- 保留 / 删除内容预览。
- 二次确认。
- 卸载中。
- 卸载完成。
- 卸载失败。

规则：

- 默认保留本地数据。
- 删除本地数据必须单独展开、二次确认，并列出将删除的范围。
- 卸载失败时保留可恢复状态和诊断入口。

完成标准：

- 更新、回滚、卸载都有确认、影响预览、成功、失败恢复。
- 截图验收能覆盖维护闭环，不需要先补 Stitch 独立稿。

## 7. 阶段 3：验证与清理

目标：确保新设计没有被旧路线拖回去。

状态：已完成（2026-06-18）。前端生产构建、类型检查、启动器维护脚本解析、旧普通入口文案扫描、桌面安装 / 卸载、更新 current 路径、真实 Docker upgrade / rollback、失败恢复状态和 product smoke 配置一致性均已验证。

### 7.0 阶段 3 实现结果

已完成：

1. 前端验证：
   - `corepack pnpm --filter @yggdrasil/web build` 通过，新增 `/settings` 路由已纳入生产构建。
   - `corepack pnpm --filter @yggdrasil/web typecheck` 通过。
   - 阶段 1 已用真实 Core API 数据验证 Start 首页、应用矩阵、设置中心和 390px 窄屏设置页无横向溢出。
2. 启动器验证：
   - `Yggdrasil.Update.ps1`、`Yggdrasil.Desktop.ps1`、`Yggdrasil.Install.ps1` 通过 PowerShell Parser 解析。
   - 更新、升级、回滚、卸载脚本已经有影响预览、人工确认、状态文件和失败恢复动作说明。
   - `check` / `apply-current`、安装、默认卸载、删除本地数据确认门、Docker upgrade、Docker rollback 均已实际执行。
   - 真实 Docker 验证中先复现 `upgrade-failed`：产品栈只剩应用服务、依赖服务缺失时，备份阶段无法解析 `postgres`；随后通过 `product:up` 补齐依赖服务后完成 `upgrade-succeeded` 和 `rollback-succeeded`。
   - Windows 端口 3000 在 Docker bind 时返回不可用，临时使用未跟踪 `infra/product.env` 将 `YGGDRASIL_WEB_PORT` 调整到 3300 完成验收；临时文件和脚本状态 JSON 已在验收后删除。
3. 清理扫描：
   - 普通主路径未发现继续默认展示 `World Engine Workbench`、旧控制台、raw JSON、内部 ID、provider key、Token budget、Base Template 等旧设计文案。
   - 扫描命中的 `LLM`、`core-api` 等词主要位于高级诊断页、观测页、Prompt/Training 维护页和后端/API 测试；这些属于高级 / 维护者层，不作为普通用户入口。
   - 未发现需要删除的废旧 UI 测试；后端/API 测试中的技术词仍对应真实 API 语义，不删除。
4. 本地环境修复：
   - 本机 `apps/web/node_modules/next` 曾缺失 `next/dist/compiled/jest-worker/processChild.js`，已通过 `corepack pnpm store add next@15.3.0` 与 `corepack pnpm install --force --filter @yggdrasil/web` 修复后再验证。
5. 配置一致性修复：
   - `packages/python-sdk/src/yggdrasil_sdk/ops_runtime/compose.py` 的 product smoke 已改为优先读取 `infra/product.env`，否则端口覆盖会被 Compose 使用、但 smoke 仍按 template 检查。
   - `tests/test_product_compose_smoke_config.py` 覆盖本地 `product.env` 优先级和 template 回退。

未完成，保留为后续阶段：

1. 阶段 4 / 阶段 5 的完整窄屏、200% zoom、键盘焦点、读屏标签和深层应用运行态仍未实现。
2. 未执行真实删除本地数据，因为该操作按设计必须由用户在可见终端中输入 `DELETE LOCAL DATA`；本轮验证覆盖了未确认时的拒绝路径和默认保留路径。

任务：

1. 跑前端 / 启动器相关测试。
2. 做桌面截图验收：
   - 主页。
   - 应用包。
   - 设置。
   - 启动器安装。
   - 启动器日常。
   - 更新 / 回滚 / 卸载确认。
3. 扫描普通用户 UI 文案：
   - 禁止默认显示 CLI、raw JSON、内部 ID、端口、Docker、API key。
   - 技术词只允许在高级 / 维护者层。
4. 删除废旧测试或旧设计绑定测试。
5. 更新：
   - `docs/DIRECTORY_REFERENCE.md`。
   - 实现记录或验收记录。

完成标准：

- 新用户路径能跑通。
- 旧入口不再作为默认路径。
- 废旧测试不再牵引旧设计。

## 8. 阶段 4：移动端 / 窄屏 P1

目标：桌面主路径稳定后，再补窄屏实现与验收。

任务：

- 导航折叠。
- 应用矩阵重排。
- 设置分组改为单列或分段。
- 启动器安装步骤窄屏布局。
- 文本溢出检查。
- 移动端 / 窄屏截图。

完成标准：

- 关键按钮、错误、金额、权限和数据外发说明在窄屏不溢出、不重叠。
- 不用缩小到不可读字号来塞内容。

## 9. 阶段 5：增强验收 P1

目标：补齐设计报告里仍未覆盖的深层交互与可访问性。

任务：

- 200% zoom。
- 键盘焦点。
- 读屏标签。
- 错误提示与控件关联。
- 应用包运行态：
  - 当前工作路径。
  - 下探子步骤。
  - 返回父步骤。
  - 折叠历史窗口。
  - 产物交付后的继续追问 / 导出 / 重新运行。

完成标准：

- 可访问性不只靠颜色表达状态。
- 应用运行态能表达世界树工作过程，但不压住普通用户主线。

## 10. 不做事项

1. 不再大批量命令 Gemini 返工。
2. 不为旧控制台保留平滑迁移路径。
3. 不重新引入失败 V2-V9 设计稿。
4. 不把新设计做成旧页面上的补丁。
5. 不保留废旧测试来兼容旧路线。

## 11. 推荐执行顺序

1. 阶段 0：代码入口调查与旧入口清单。
2. 阶段 1：桌面主路径实现（2026-06-17 已完成主体实现）。
3. 阶段 2：启动器维护闭环（2026-06-17 已完成主体实现）。
4. 阶段 3：验证、截图、清理和文档同步（2026-06-18 已完成）。
5. 阶段 4：移动端 / 窄屏（未完成）。
6. 阶段 5：增强可访问性与应用运行态（未完成）。

如果阶段 1 或阶段 2 遇到设计无法落地的问题，只针对对应状态族小范围补 Stitch，不回到大批量返工。
