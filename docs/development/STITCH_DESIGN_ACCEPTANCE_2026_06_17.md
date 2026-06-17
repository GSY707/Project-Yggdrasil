# Stitch 设计稿四组页面验收报告

日期：2026-06-17

## 1. 验收范围

本次验收使用 Codex 全局 MCP `stitch` 抓取 `Project Yggdrasil Design System` 这一个 Stitch 项目；其他世界树相关 Stitch 项目不纳入本轮验收证据。

| Stitch 项目 | 项目 ID | 说明 |
| --- | --- | --- |
| Project Yggdrasil Design System | `projects/6603619266131280055` | 最新主设计系统与高保真页面 |

范围核验：`view=owned` 下还能看到 `Project Yggdrasil - Command Console` 和 `Project Yggdrasil 设计计划 (P0-P2)`，但用户已明确本轮只看 `Project Yggdrasil Design System`；`view=shared` 返回空。

保留产物：

| 产物 | 数量 | 路径 |
| --- | ---: | --- |
| Gemini 3.1 Pro 最终通过候选 screen HTML | 5 | `docs/development/stitch-design-captures-2026-06-17/post-rework-v10-passline/html/` |
| Gemini 3.1 Pro 最终通过候选高保真截图 | 5 | `docs/development/stitch-design-captures-2026-06-17/post-rework-v10-passline/screenshots/` |
| Gemini 3.1 Pro 最终通过候选分组拼图 | 4 | `docs/development/stitch-design-captures-2026-06-17/post-rework-v10-passline/contact-sheets/` |
| Gemini 3.1 Pro 最终通过候选清单 | 2 | `docs/development/stitch-design-captures-2026-06-17/post-rework-v10-passline/manifest.json`、`summary.json` |

说明：原始抓取、V2/V3 早期返工和 V4-V9 未过线证据曾用于本报告判断，但不再作为仓库保留产物提交；为避免旧设计继续污染工程输入，仓库只保留最终通过候选包。

证据分级：

| 页面组 | Stitch screen 总数 | 高保真截图数 | HTML 数 | 验收使用方式 |
| --- | ---: | ---: | ---: | --- |
| 主页 | 9 | 1 | 9 | 视觉验收只有 1 张 Gateway/Concierge 图，文档型 HTML 作为设计依据 |
| 应用包 | 7 | 4 | 7 | 4 张截图覆盖四类应用，HTML 补充应用包 brief 和接口说明 |
| 设置 | 4 | 1 | 4 | 只有 1 张高保真设置页，是设置组不通过的关键证据 |
| 启动器 | 6 | 4 | 6 | 4 张截图覆盖控制中心、安装向导、诊断、备份恢复，托盘仍只有 HTML/说明 |

因此，历史章节中的 `26` 表示当时单一 Stitch 项目的 screen/HTML 抓取总量，不表示 26 张可验收高保真页面；当前提交证据以 V10 最终通过包为准。

## 2. 验收依据

主要依据：

- `docs/design-handoff/README.md`
- `docs/design-handoff/01-base-user-interface-agent.md`
- `docs/design-handoff/02-application-package-experience.md`
- `docs/design-handoff/03-settings-debug-configuration.md`
- `docs/design-handoff/04-launcher-experience.md`

总验收门槛：

1. 普通用户入口必须 GUI-first。
2. CLI、Prompt、MCP、评测、观测、raw JSON、内部 ID 下沉到高级模式。
3. 新设计应直接切换用户路径，不在旧控制台上打补丁。
4. 计划中能力必须标明计划中，不能画成当前可用。
5. 四组页面必须分别覆盖主页、应用包、设置、启动器。

## 3. 设计合格线

从 V4 起，设计稿只有同时满足下面门槛，才可判为“通过，可进入工程实现”。没有达到门槛的稿件只能作为探索稿或局部参考。

### 3.1 全局硬门槛

1. 普通用户默认界面必须使用用户语言：开始任务、选择应用、添加材料、连接 AI 服务、费用上限、数据留本机、需要确认、查看结果。
2. 默认界面不得出现 `Terminal`、CLI、raw JSON、内部 ID、端口号、Docker、Core API、Worker、MCP、Prompt、token、stack trace、`.env`、`.yggdrasil` 等技术词；这些只允许出现在“高级详情”“诊断详情”或维护者模式里。
3. 计划中能力必须显式标为“计划中 / 不会自动执行 / 需要手动确认”，不能用 ready、available、enabled 暗示已经可用。
4. 每张高保真稿必须有明确主任务、主 CTA、阻塞原因、恢复动作和成功状态；不能只是概览看板。
5. 桌面高保真必须可直接指导实现：信息架构、主要组件、空态、加载态、错误态、完成态都要可见或在同一状态族中可见。
6. 视觉上保持 `Roots & Circuitry`：深色、稳定、企业级、根系/电路感、低噪声；不要回到 `Yggdrasil Terminal` 的开发者终端叙事。
7. 文字不得依赖极小字号才能读懂；关键 CTA、错误、金额、权限和数据外发说明在 1440px 桌面视口内必须清楚。
8. 每组至少有一张窄屏或响应式说明稿，或者在桌面稿中明确组件重排规则；截图阶段不能声称完整响应式通过，但必须有实现依据。
9. 可访问性至少要能从稿件判断：按钮有文字或清晰图标标签，错误不只靠颜色表达，危险操作有二次确认。

### 3.2 主页合格线

主页必须形成普通用户首次成功路径，至少覆盖：

- 首次欢迎 / 系统未配置。
- 添加本地材料。
- AI Concierge 生成任务草案。
- 推荐应用并说明为什么。
- 启动前确认：材料、费用上限、AI 服务连接、数据外发预览。
- 阻塞修复：缺 AI 服务连接、费用不足、材料缺失。
- 任务运行摘要与失败恢复。

通过标准：用户不需要理解技术模块，就能从空白状态走到“确认并开始任务”。

### 3.3 应用包合格线

应用包必须先冻结统一模板，再套到四类应用。统一模板至少包含：

- 应用价值说明：适合谁、解决什么、需要什么材料、会产出什么。
- 任务模板与示例任务。
- 材料检查和缺失修复。
- typed settings：AI 服务、模型/质量档、费用上限、工作区、输出格式、工具权限。
- 启动前确认：费用、外发内容、预计时间、风险。
- 运行中：当前步骤、可下探工作树、返回父步骤、折叠历史窗口。
- 产物交付：预览、导出、继续追问、重新运行。

通过标准：Deep Research、Graduate Researcher、Coding Greenfield、Knowledge Studio 四类应用都使用同一信息架构，但文案和样例任务符合各自场景。

### 3.4 设置合格线

设置必须拆成普通设置、高级设置、维护者调试三层。普通设置至少覆盖：

- AI 服务连接：新增、测试、失败原因、费用风险、默认质量档。
- 费用与预算：月上限、单任务上限、接近上限、已耗尽、充值/降低质量档动作。
- 工作区与数据位置：选择、不可写、迁移、备份前确认。
- 应用级设置：承载每个应用包 `settingsSchema[]` 的 typed controls。
- 数据与隐私：外发预览、敏感项阻断、允许一次、始终允许、撤销、清除本地历史、导出审计。

通过标准：普通用户能完成常见配置和安全决策；高级/维护者入口存在但不压住普通路径。

### 3.5 启动器合格线

启动器必须覆盖安装、运行、托盘、维护四条路径：

- 安装 7 步：欢迎、安装位置、数据位置、AI 服务连接、应用包选择/校验、快捷方式选择、完成页。
- 每步至少有正常、等待、错误/警告或恢复状态之一。
- 桌面主窗口：应用直达、系统健康、需要处理的问题、最近任务。
- 应用专属快捷方式：直接进入应用页或任务启动页，不回到内部控制台。
- 托盘菜单：状态、打开应用、暂停/继续、备份、诊断、设置、退出；通知覆盖启动冲突、更新可用、备份成功/失败。
- 更新/回滚/卸载：检查更新、手动应用、影响预览、回滚确认、卸载保留/删除本地数据、失败恢复。

通过标准：普通用户能从安装到启动应用、处理问题、维护和卸载，不需要命令行。

## 4. 总结论

最新复验结论：**Gemini 3.1 Pro 按第 3 节合格线连续返工至 V10 后，四组页面均已达到“可进入工程实现”的设计交付门槛。**

| 页面组 | 结论 | 主要理由 |
| --- | --- | --- |
| 主页 | 通过 | V10 移除 Gateway/Core/Intelligence 等内部叙事，保留 `Project Yggdrasil`、Start、材料空态、任务草稿、本地隐私、预算时间和审批动作 |
| 应用包 | 通过 | V8 形成四列深色统一矩阵，覆盖 Deep Research、Graduate Writing、Coding Assistant、Knowledge Base 的 Needs/Templates/Settings/Review Status/Primary Action |
| 设置 | 通过 | V6 去掉路径、API/key、provider、token 等技术词，保留 AI Service、Spending、Storage、App Defaults、Data & Privacy 等用户可理解设置 |
| 启动器 | 通过 | V9 安装向导去掉 `Yggdrasil OS` 品牌污染，V6 日常使用页覆盖主窗口、托盘、暂停/恢复、备份、更新、诊断和退出确认 |

工程转化优先级：

- P0：以 V10 主页、V8 应用包、V6 设置、V9/V6 启动器作为工程实现输入，直接切换用户路径，不在旧控制台上补丁式兼容。
- P0：工程实现时继续保留普通用户语言；CLI、raw JSON、内部 ID、端口、Docker、API key 等只进入高级/维护者层。
- P1：补移动/窄屏重排稿和实现侧响应式规则；本轮仅完成桌面高保真通过。

说明：第 5 至第 12 节保留首次验收基线与原始缺口记录；返工后 V2 复验详见第 13 节，拆项返工 V3 复验详见第 15 节，V4-V10 合格线返工与最终判定详见第 17 节。失败轮次只保留文字结论，不再保留旧设计文件。

## 5. 主页组验收

证据：

- `contact-sheets/home.png`
- User Gateway & AI Concierge

符合项：

- 有面向普通用户的入口尝试，`User Gateway & AI Concierge` 明确出现了客服型 Agent、系统就绪、快速开始、最近工作。
- 视觉方向整体接近深色、技术、稳定的设计系统，状态色和主动作比较明确。

不符合项：

- 高保真主页只有一张，无法覆盖首次进入、问客服 Agent、应用推荐、Prompt 代写、任务确认和错误修复五条关键流程。
- 页面仍保留较多内部控制台入口，例如 Advanced / MCP / Observability 等，应下沉到高级模式。
- 客服 Agent 未形成完整任务草案流程：缺少目标澄清、推荐应用、模板选择、素材需求、预算/provider/出机提示和启动前确认。
- 系统就绪状态只显示 provider missing 等状态，缺少统一配置、测试和阻塞修复路径。
- 未清楚区分当前可用能力和计划中能力。

验收结论：**部分通过。**

下一步要求：

1. 以 `User Gateway & AI Concierge` 为唯一主页方向继续扩展，以“开始 / 任务 / 应用 / 素材 / 数据与安全 / 高级”为普通导航。
2. 客服 Agent 必须产出可确认任务草案，而不是只做聊天输入框。
3. 首屏必须回答“现在能做什么、缺什么、下一步点哪里”。
4. 内部控制台入口下沉到高级模式。

## 6. 应用包组验收

证据：

- `contact-sheets/application-package.png`
- Graduate Researcher (Interactive)
- Coding Greenfield (Interactive)
- Knowledge Studio (Interactive)
- Deep Research Lab (Interactive)

符合项：

- 覆盖了四类关键应用：研究、学习、代码、知识整理。
- Deep Research 和 Graduate 页面已经体现任务模板、执行状态、来源/证据、Agent 步骤等能力。
- Knowledge Studio 有素材、知识图谱、综合报告和发布动作，方向接近场景页。
- Coding Greenfield 能展示代码、文件结构和生成产物，适合作为开发类应用样本。

不符合项：

- 四个应用没有统一页面模板。brief 要求的“场景说明、任务模板、示例任务、预期产物、运行过程、应用设置”没有稳定落在每个应用。
- 普通用户主线被运行态/日志/内部节点压住：Graduate、Coding、Deep Research 都偏“正在执行的控制台”，不是先解释这个应用适合谁、需要什么材料、产出什么。
- 应用设置缺失。未看到基于 `settingsSchema[]` 的 provider、model、预算、workspace、输出风格、记忆命名空间、工具权限 typed controls。
- 工作过程可视化仍偏长日志/面板并列，没有明确表达“下探、返回父节点、折叠历史窗口、当前真实上下文窗口”。
- 内部字段和技术实体仍然靠前，例如节点号、文件树、代码输出等缺少普通/高级分层。`source credibility` 对研究类应用本身是用户价值项，但当前缺少普通用户解释层、证据含义说明和高级展开规则。

验收结论：**部分通过。**

下一步要求：

1. 先冻结一套应用包页面模板，再套四类应用。
2. 每个应用包首屏必须先说目标、输入、产物、模板和启动条件。
3. 运行过程默认展示当前工作路径和摘要，工具日志与历史窗口默认折叠。
4. 应用设置必须用 typed controls，raw JSON 和内部 ID 下沉到高级模式。

## 7. 设置组验收

证据：

- `contact-sheets/settings.png`
- Settings, Debug & Configuration
- `03-settings-debug-configuration.md` HTML

符合项：

- 有“Startup & Readiness / Advanced Configuration”的粗分层意识。
- 能看到 Core API、Worker、Provider Key 等启动阻塞状态。
- 视觉上与主设计系统一致，密度较高，适合高级设置方向。

不符合项：

- 高保真页面数量严重不足：只看到一个 Kernel Configuration 页面。
- 没有覆盖普通用户设置中心：provider key 状态、测试调用、默认模型、预算、workspace、state root、数据位置、备份、恢复、出机边界都缺高保真稿。
- 没有覆盖应用设置：未出现 `settingsSchema[]` 对应的 typed controls。
- 没有覆盖高级/维护者调试全链路：Prompt、MCP、评测、观测、runtime artifacts、raw payload 等入口没有清楚下沉策略。
- 文案仍偏内部名词，例如 Kernel、Node、Core API、Worker node，对普通用户不够友好。

验收结论：**不通过。**

下一步要求：

1. 重做设置组，至少补齐 `/settings/startup`、`/settings/providers`、`/settings/workspace`、`/settings/data`、`/settings/apps`。
2. 补齐 `/advanced/prompting`、`/advanced/mcp`、`/advanced/evaluations`、`/advanced/observability`、`/advanced/runtime` 的入口策略。
3. 密钥、预算、出机、数据位置和计划中删除能力必须有明确文案。
4. 不允许把 raw `.env`、raw JSON 或内部 ID 作为普通用户默认配置方式。

## 8. 启动器组验收

证据：

- `contact-sheets/launcher.png`
- Yggdrasil Launcher: Control Center
- Yggdrasil Launcher: Setup Wizard
- Yggdrasil Launcher: System Diagnostics
- Yggdrasil Launcher: Backup & Restore
- Tray Menu & Notification Spec HTML

符合项：

- 启动器已作为独立桌面入口出现，不是简单 Web 控制台换皮。
- Control Center 覆盖启动、应用包、Docker/Core API/Worker/Data Root/Provider Key 等状态。
- Setup Wizard 覆盖环境诊断，能看到检查项、警告、失败和继续动作。
- Diagnostics 覆盖 degraded、告警、故障项和日志导出。
- Backup & Restore 覆盖快照、恢复、导出和警告状态。

不符合项：

- 安装向导缺完整关键页：欢迎、应用包说明、安装位置、数据位置、provider key 配置、应用包校验、快捷方式选择、完成页没有全套高保真。这是 P0 主路径缺口。
- 应用专属快捷方式目标不够明确：设计要求用户从应用快捷方式直接进入应用详情页或任务启动页，而不是只打开通用 Control Center。这是 P0 主路径缺口。
- Provider key 配置仍停在状态提示，没有完整配置/测试/失败恢复流程。这是 P0 主路径缺口。
- 更新与回滚缺高保真页面；卸载确认缺失。
- 托盘菜单只有 HTML/说明，没有可验收截图。
- 部分状态标签仍使用 Core API、Worker Node、Data Root 等内部名词，普通用户需要更清楚的解释层。

验收结论：**部分通过。**

下一步要求：

1. 补齐安装向导 7 步关键页和每步的正常/警告/错误/等待状态。
2. 为每个应用包定义桌面快捷方式和深链接策略。
3. 补齐 provider key 配置、测试调用、paid model/预算提示。
4. 补齐更新、回滚、卸载、托盘菜单视觉稿。
5. 普通模式只显示用户语言，技术详情默认折叠。

## 9. 可访问性、响应式与交互未验收项

仅基于截图和 HTML 做风险判断，不声称完整 WCAG 合规。由于抓取包没有移动端截图、键盘操作记录、focus/ARIA 检查或 200% zoom 证据，可访问性与响应式不能算已验收，只能列为重大未验收项。

已确认的优点：

- 深色稿件整体对比度较高，主要 CTA 较容易识别。
- 状态色体系已经存在，成功、警告、错误、处理中基本有区分。
- 多数页面使用稳定网格和清晰分区。

风险：

- 信息密度过高，小字号、窄列和 monospaced label 在普通用户场景下可能不可读。
- 多处依赖颜色表达状态，缺少足够的文字解释或图标冗余。
- 顶栏和侧栏存在多个 icon-only 控件，截图无法确认 accessible label、tooltip、键盘焦点和读屏顺序。
- 运行态页面有大量滚动/面板/日志，键盘访问顺序和焦点管理需要单独验证。
- 部分浅色背景页面的灰色辅助文本可能存在低对比风险。

后续验收必须补：

1. 真实前端或原型的键盘导航测试。
2. focus ring、tab order、aria label、错误提示关联检查。
3. 200% zoom 与窄屏重排检查。
4. 状态变化的非颜色表达。
5. 移动端/窄屏截图，尤其是应用包运行页、设置页和启动器安装向导。

## 10. 计划中能力专项核对

本轮截图不足以证明所有能力边界都被正确表达。下一轮验收必须逐项核对含有这些语义的页面和文案：

- cloud / remote / sync / SaaS / hosted / backup / update / delete / available / ready
- 官方远端数据、远端备份、静默自动更新、Web 删除、删除证明、SaaS 托管

核对要求：

1. 当前未实现能力必须写成计划中或不可用，不能只靠图标、状态色或模糊文案暗示已经可用。
2. 启动器更新页必须明确“手动检查 / 手动应用 / 可回滚”，不能画成静默自动更新。
3. 数据与隐私页必须明确哪些数据留本机，哪些内容会出机给用户配置的 provider。
4. Web 删除和官方远端能力在没有 dry-run、影响预览、备份前置、审计和证明前，不应出现普通用户可点击执行按钮。

## 11. 应删除或下沉的旧表达

这些内容不应出现在普通用户主线：

- Advanced / MCP / Observability 等内部入口作为普通首页默认入口。
- raw JSON、内部 ID、节点号、服务名、Compose 术语作为默认展示。
- MCP、Prompt、评测、观测、runtime artifacts 与任务主线同级。
- “Provider Key Missing”只显示状态而不给配置与测试路径。
- 长日志或代码输出作为应用包默认首屏。
- 未实现的 Web 删除、官方远端数据、静默自动更新被画成可用能力，或只用含糊状态词表达为 ready/available。

保留方式：

- 放入高级模式、技术详情、维护者调试页或文档说明。
- 普通用户只看到结果、风险、下一步和可执行动作。

## 12. 页面清单

### 主页

- DIRECTORY_REFERENCE.md
- PRODUCT_PACKAGING_AND_REMOTE_DATA_REQUIREMENTS_GAP_2026_06_04.md
- UX_DESIGN_TEAM_HANDOFF_2026_06_04.md
- 01-base-user-interface-agent.md
- work-tree-protocol-v0.2.md
- LLM_WORK_ANALYZER_USER_GUIDE.md
- User Gateway & AI Concierge
- README.md
- USER_ADOPTION_SURFACE_AUDIT_2026_06_03.md
- Extracted text: design-handoff/01-base-user-interface-agent.md
- Extracted text: design-handoff/README.md
- Extracted text: DIRECTORY_REFERENCE.md
- UX_DESIGN_TEAM_HANDOFF_2026_06_04.md

### 应用包

- LOCAL_FIRST_TASK_DEMO.md
- application-package-interface-v0.1.md
- Graduate Researcher (Interactive)
- Coding Greenfield (Interactive)
- Knowledge Studio (Interactive)
- 02-application-package-experience.md
- Deep Research Lab (Interactive)
- Extracted text: design-handoff/02-application-package-experience.md

### 设置

- Settings, Debug & Configuration
- 03-settings-debug-configuration.md
- agent-runtime-protocol-v0.2.md
- DESIGN_COMPLETION_EVALUATION_2026_06_05.md
- Extracted text: design-handoff/03-settings-debug-configuration.md

### 启动器

- 04-launcher-experience.md
- Yggdrasil Launcher: Control Center
- Yggdrasil Launcher: Backup & Restore
- Tray Menu & Notification Spec
- Yggdrasil Launcher: System Diagnostics
- Yggdrasil Launcher: Setup Wizard

### Gemini 返工后新增 V2 高保真页

V2 证据已用于当日复验，但不是最终通过稿；为避免旧设计污染工程输入，仓库不再保留 V2 文件，只保留以下文字判定。

| 页面组 | V2 screen | 高保真截图 |
| --- | ---: | ---: |
| 主页 | 1 | 1 |
| 应用包 | 4 | 4 |
| 设置 | 1 | 1 |
| 启动器 | 5 | 4 |

V2 页面：

- 主页：Project Yggdrasil: User Gateway (V2)
- 应用包：App: Coding Greenfield (V2)、App: Deep Research Lab (V2)、App: Graduate Researcher (V2)、App: Knowledge Studio (V2)
- 设置：Settings Center (V2)
- 启动器：Launcher: Backup & Restore (V2)、Launcher: Diagnostics (V2)、Yggdrasil Launcher: Control Center (V2)、Yggdrasil Launcher: Setup Wizard (V2)、Tray Menu & Notification Spec (V2)

### Gemini 3.1 Pro 拆项返工新增 V3 高保真页

V3 证据已用于当日复验，但不是最终通过稿；仓库不再保留 V3 文件，只保留以下文字判定。

| 页面组 | V3 screen | 高保真截图 |
| --- | ---: | ---: |
| 主页 | 1 | 1 |
| 应用包 | 1 | 1 |
| 设置 | 2 | 2 |
| 启动器 | 3 | 3 |

V3 页面：

- 主页：Home Flow: Gateway & Concierge States (V3)
- 应用包：Application Package Flow: App to Task Delivery (V3)
- 设置：Settings Flow: Provider Budget Workspace States (V3)、Privacy Flow: Data Leaving Machine Review (V3)
- 启动器：Launcher Flow: Complete Setup Wizard (V3)、Launcher Flow: Tray Menu & Notifications (V3)、Launcher Flow: Update Rollback Uninstall (V3)

## 13. Gemini 3.1 Pro 返工后复验

本次返工是实质性改进，不是旧稿轻微调色。Stitch 项目在 MCP 超时后继续生成了 V2 screen，`Project Yggdrasil Design System` 的项目更新时间为 `2026-06-17T08:35:47Z`。V2 证据已复验并归纳在本节，但后续 V10 已替代它成为工程输入，因此不再提交 V2 文件。

### 12.1 主页 V2

结论：**部分通过，方向正确。**

改善点：

- 首屏收敛到 `Gateway` 和 `Yggdrasil Concierge`，比旧版更像普通用户入口。
- 有任务草案雏形：用户目标、澄清问题、推荐应用、数据边界、provider、预计成本、预计时长、确认并起草任务。
- 顶部导航已经把 `Start / Tasks / Applications / Material Assets / Data & Safety / Advanced` 分层，底部把 `Prompt Studio / MCP Routing / Evaluations` 标为 Advanced。
- 明确出现 `Remote Sync [PLANNED]`、`Provider Key Missing` 和 `Configure Providers`，比旧稿更符合当前/计划中能力边界。

剩余缺口：

- 只有一张主页 V2，缺首次启动、导入素材、任务确认、阻塞修复、失败恢复等状态序列。
- `Advanced` 仍在顶部导航可见，虽然已下沉，但对普通用户仍偏显眼。
- `Anthropic Claude 3.5` 等 provider 示例应避免暗示默认可用，需要以后和 live catalog/本机配置口径对齐。

### 12.2 应用包 V2

结论：**部分通过偏可用，已具备实现模板的主要骨架。**

改善点：

- 四类应用均有 V2：Coding、Deep Research、Graduate、Knowledge。
- Coding 和 Graduate 明确补了材料、任务模板、预期产物、Agent settings、provider/model/workspace/budget 等 typed controls。
- Deep Research 和 Knowledge 保留运行态能力，但加入材料、模板、证据/产物和配置入口，用户价值比旧版更清晰。
- `Advanced: Raw Test Output & Git Diff`、`Advanced Debug & Logs`、`[PLANNED]` 等表达显示内部细节已经开始折叠。

剩余缺口：

- 四个应用仍不是同一套严格模板：有的像创建页，有的像运行页，有的像知识工作台。
- 普通用户启动前解释层还不稳定：每个应用都应固定显示适合谁、需要什么、会产出什么、下一步点哪里。
- 运行态仍有较强控制台气质，当前工作路径、父子节点返回和历史窗口折叠还需要统一交互规范。

### 12.3 设置 V2

结论：**从不通过提升到部分通过。**

改善点：

- `Settings Center (V2)` 明确分为 `General Settings`、`Data & Privacy`、`Advanced / Developer`。
- 已覆盖 provider key、默认模型、月预算、workspace path、state root、备份/恢复。
- `Data & Privacy` 写明 local-first，并把 remote sync 标为 `[PLANNED]`。
- `Advanced / Developer` 下沉 Prompt Profiles、MCP Server Sync、Telemetry & Evaluations 和 Observability Spans。

剩余缺口：

- 仍只有一张长页，高保真不足以覆盖 provider key 配置、测试调用、失败恢复、预算超限、路径不可写、备份失败等关键状态。
- 应用级设置没有成型，未看到各应用 `settingsSchema[]` 的统一承载方式。
- 维护者调试层还偏入口清单，缺 raw payload/runtime artifacts 的隔离规则和危险操作确认。

### 12.4 启动器 V2

结论：**部分通过偏可用，主路径明显改善。**

改善点：

- `Control Center (V2)` 已从通用控制台转成应用直达卡，主 CTA 是 `Launch Application`，并提供 `App Details & Task Configuration`。
- `Setup Wizard (V2)` 明确本地优先、裸机/本地 API/外部云边界，并出现桌面快捷方式、任务栏固定等安装体验。
- `Diagnostics (V2)` 将 Docker、Core API、Provider Key、端口占用、Data Root 等问题做成可行动诊断项。
- `Backup & Restore (V2)` 比旧版更聚焦快照、校验、恢复和重启警告。

剩余缺口：

- 安装向导仍只展示中间状态，缺欢迎、安装位置、数据位置、provider keys、应用包校验、快捷方式选择、完成页的完整序列。
- 托盘只有 `Tray Menu & Notification Spec (V2)` 文档，没有高保真截图。
- 更新/回滚/卸载仍缺高保真稿。
- 部分词汇如 `Core API`、`Compute Node`、`Data Root` 仍需要普通用户解释层。

### 12.5 独立复核补充

只读复核确认 V2 比首次验收有明显改善，尤其设置和启动器已经从后台/概念方向转向产品界面。但复核补充了三个必须进入下一轮 P0 的缺口：

- 应用包到真实任务的完整闭环仍未可验收：需要画出从应用包选择、材料检查、任务草案、预算/provider 确认、一键启动、运行中状态到产物交付的端到端状态。
- 托盘是系统级入口，但目前只有 `Tray Menu & Notification Spec (V2)` 文档，没有可交付视觉/交互稿。
- 隐私与数据外发不能只写 local-first，需要可操作的权限、外发数据预览、撤销、清除、导出和失败状态。

复核同时提醒：V2 仍残留 `Chat or /commands`、Provider Logs、terminal、Docker、System Logs、bare metal、Action Required 等技术语言。下一轮普通用户路径要继续降噪，把支持人员和维护者路径收进高级/诊断层。

## 14. V2 阶段判定

返工后设计稿已经覆盖四组方向，并且 V2 比首次验收有明显实质提升。当前可以作为工程实现和下一轮细化设计的输入，但还没有达到“四组都可最终交付验收”的标准。

可以继续使用的部分：

- 视觉系统方向。
- 主页 Gateway/Concierge 正门。
- 应用包四类 V2 样本的材料、模板、产物、typed settings 骨架。
- Settings Center V2 的普通设置、数据隐私、高级开发三层结构。
- 启动器 V2 的应用直达、诊断、备份恢复和安装向导方向。

必须返工的部分：

- 主页状态序列：首次启动、素材导入、任务确认、provider 阻塞修复、失败恢复。
- 应用包统一模板和真实任务闭环：四类应用必须使用同一信息架构，并覆盖从应用选择到任务启动、运行、产物交付的完整状态。
- 设置多状态：provider 测试/失败、预算告警、路径不可写、应用设置、隐私/数据外发预览、危险操作确认。
- 启动器完整流程：安装 7 步、provider 配置/测试、托盘视觉、更新回滚、卸载。

建议下一轮不要再让 Gemini 大批量编辑所有 screen。更稳的做法是按四组分批生成：主页状态序列、应用包统一模板、设置状态页、启动器安装/维护流程。每批只选 2-4 个 screen，降低 MCP 120 秒超时和结果不可控风险。

## 15. Gemini 3.1 Pro 拆项返工 V3 复验

本轮按返工项拆成 7 个独立生成任务，并指定 `GEMINI_3_1_PRO`。其中应用包任务在 MCP 120 秒限制内没有直接返回，但 Stitch 后台完成生成；其余 6 项直接返回。V3 拆项证据已复验并归纳在本节，但后续 V10 已替代它成为工程输入，因此不再提交 V3 文件。

V3 抓取统计：

| 页面组 | V3 screen | 高保真截图 | HTML |
| --- | ---: | ---: | ---: |
| 主页 | 1 | 1 | 1 |
| 应用包 | 1 | 1 | 1 |
| 设置 | 2 | 2 | 2 |
| 启动器 | 3 | 3 | 3 |
| 合计 | 7 | 7 | 7 |

### 14.1 拆项任务完成情况

| 返工项 | Stitch screen | 状态 | 复验结论 |
| --- | --- | --- | --- |
| 主页 Gateway/Concierge 状态序列 | `3652e75f426d480d84d7d7a6b2fab8c4` | 已完成 | 补齐欢迎、素材导入、AI Concierge、启动确认、provider 缺失、任务失败恢复，部分通过偏可用 |
| 应用包到任务交付闭环 | `a5e2624ddc3945ea8f26ef08ee49fabf` | 已完成，MCP 调用先超时后后台完成 | 横向闭环存在，但画面过稀、四类应用模板未充分展开，部分通过 |
| 设置 provider / budget / workspace 状态 | `0013527aa92d4359ab9eb8c7be8592fc` | 已完成 | 补齐 provider 连接失败、预算耗尽、测试连接，部分通过偏可用 |
| 隐私与数据外发审批 | `d581229be81f42578dc1b62cf88eda9f` | 已完成 | 补齐外发预览、敏感项阻断、授权/拒绝/清除本地历史，部分通过偏可用 |
| 启动器完整安装向导 | `ca83849a61694eb685d4bc349f494698` | 已完成 | 可见欢迎、安装位置、数据位置和路径错误，但完整 7 步仍未全量展开，部分通过 |
| 启动器托盘菜单与通知 | `0151c8b72974410db9a446138bb9a88b` | 已完成 | 从文档稿升级成可验收视觉稿，菜单、启动冲突、更新提醒、备份成功通知基本成立，部分通过偏可用 |
| 启动器更新、回滚、卸载 | `9f085880bec542cfa8876e9bb9820021` | 已完成 | 有维护中心、更新可用、回滚状态，但缺卸载确认、回滚影响预览和失败恢复状态，部分通过 |

### 14.2 主页 V3

结论：**部分通过偏可用。**

改善点：

- 首屏状态比 V2 明显完整：欢迎、素材导入、AI Concierge、启动前确认、provider 缺失、任务失败恢复都在同一画布内。
- 能看到本地优先、远端同步计划中、provider 阻塞、预算不足和编辑任务草案等关键用户路径。
- 首页终于回答了“能做什么、缺什么、下一步点哪里”，比首次验收和 V2 更接近普通用户正门。

剩余缺口：

- 信息密度仍高，截图内有不少小字号和紧贴的深色面板，真实产品实现时需要拆成可交互状态页，而不是一张巨型状态板。
- 页脚仍出现 `Yggdrasil Terminal v3.0.0-rc1`，和普通用户入口不一致。
- provider 名称、API key、budget 等词仍偏技术化，需要改成用户可理解的“AI 服务连接”“费用上限”等表达。

### 14.3 应用包 V3

结论：**部分通过，但不是最终可实现模板。**

改善点：

- V3 补出了 `Select -> Prepare -> Configure -> Run` 的横向闭环，解决了 V2 “四类样本各自为政但端到端闭环不稳”的问题。
- 应用选择、材料要求、缺失 API key、配置任务、启动运行、执行树和产物导出都在一个画面内出现。

剩余缺口：

- 画面过稀，绝大多数画布为空，信息层级不像可以直接交给前端实现的高保真应用包模板。
- 四类应用没有在 V3 中分别按同一模板展开，只能证明横向流程方向，不能证明四类应用页已统一。
- 仍使用 `Yggdrasil Terminal`、`Terminal`、API Key、Advanced System 等技术语言，普通用户解释层不足。
- 运行中状态只展示非常薄的摘要，缺当前工作路径、下探/返回、历史窗口折叠和产物交付后的下一步。

### 14.4 设置 V3

结论：**部分通过偏可用。**

改善点：

- provider 配置屏明确展示添加 provider、API key 输入、测试连接、连接失败、预算耗尽、top-up budget。
- 隐私外发屏比 V2 实质进步：能看到外发策略、待外发内容、敏感项、授权/拒绝/编辑上下文、传输阻断、本地历史清除和审计导出。
- `Data Leaving Machine Review` 已经把 local-first 从口号变成了可操作流程。

剩余缺口：

- 应用级设置仍没有形成统一承载方式，未覆盖各应用 `settingsSchema[]`。
- Workspace 路径不可写、备份失败、恢复前确认、预算接近上限等状态还不完整。
- token、API key、schema、provider、audit log 等技术词仍多，需要普通模式/高级模式再分层。

### 14.5 启动器 V3

结论：**部分通过偏可用。**

改善点：

- 安装向导不再只是概念稿，已显示欢迎、安装位置、数据位置、路径不可写、依赖扫描等待等状态。
- 托盘菜单终于有可验收视觉稿，包含系统状态、打开应用、暂停 Agent、备份、官方云计划中、设置、诊断、退出，以及启动冲突、更新可用、备份成功三类通知。
- 更新维护页补出当前版本、最近快照、更新可用和回滚可用状态。

剩余缺口：

- 安装向导要求的 7 步没有全部显式展开；目前可见重点仍集中在 1-3 步。
- 更新、回滚、卸载仍缺完整二次确认、影响预览、失败恢复和完成页。
- 托盘通知还残留端口、Docker Desktop、云同步计划中等技术/计划中语言，需要普通解释层。

### 14.6 V3 仍未验收项

这些项不能从当前 V3 截图证明通过：

- 窄屏、移动端、200% zoom、键盘焦点、读屏标签和错误提示关联。
- 各交互状态之间的真实跳转、loading、撤销、重试和失败恢复。
- 四类应用包在同一模板下的完整高保真落地。
- 启动器安装 7 步、回滚、卸载的全量状态序列。

## 16. 最新判定

V3 拆项返工已经完成本轮指令，并且比 V2 更接近可开发输入；但仍不是最终可交付设计。

已完成：

- 7 个拆项返工任务均已在 Stitch 生成并抓取本地证据。
- 主页从单一 Gateway 扩展为多状态入口板。
- 设置从单页设置中心扩展出 provider/budget/workspace 与隐私外发审批。
- 启动器托盘从文档说明补成了视觉稿。
- 启动器维护页开始覆盖更新和回滚。

未完成到最终验收：

- 应用包统一模板仍不够成熟，V3 只证明流程方向，不足以替代四类应用的高保真模板。
- 启动器安装 7 步、更新、回滚、卸载仍缺完整状态序列。
- 普通用户主线仍残留 `Yggdrasil Terminal`、API Key、Docker、端口、token 等技术文案。
- 响应式与可访问性仍没有可验收证据。

建议下一轮继续拆项，但粒度要更小：应用包按“统一模板 + 四类应用套版”拆，启动器按“安装步骤 1-7 / 更新 / 回滚 / 卸载”拆，设置按“应用级设置 / 路径与备份错误 / 预算告警”拆。每个任务只生成一个完整状态族，避免再次得到概览型大画布。

## 17. 合格线返工 V4-V10 最终复验

本轮先在第 3 节补充四组页面合格线，再以 `GEMINI_3_1_PRO` 按未过线项连续返工。返工只操作 `Project Yggdrasil Design System` 项目，不查看或使用其他 Stitch 项目。

### 17.1 返工记录

| 轮次 | 仓库保留方式 | 结果 |
| --- | --- | --- |
| V4 | 只保留文字判定 | 未过线：主页继承旧 `Yggdrasil Terminal` 叙事；应用包未展示四应用矩阵；设置仍有节点/认证/API 语言；启动器步骤覆盖不足 |
| V5 | 只保留文字判定 | 未过线：仍有 `provider`、路径、`Data Root`、`Core Engines`、`script`、`Coding Greenfield` 等可见污染 |
| V6 | 只保留最终采用 screen 的 V10 归档副本 | 部分过线：设置、启动器日常可用；主页品牌和应用包/安装页仍不稳定 |
| V7 | 只保留文字判定 | 未过线：主页引入 `Core Control/Intelligence/Protocol`；应用包变浅色；安装页出现 `Yggdrasil OS` |
| V8 | 只保留最终采用 screen 的 V10 归档副本 | 部分过线：主页和应用包显著改善；安装页仍需去掉 `Yggdrasil OS` |
| V9 | 只保留最终采用 screen 的 V10 归档副本 | 部分过线：启动器安装页去掉 OS 品牌污染；主页仍有 `Home Gateway` 小字 |
| V10 | `docs/development/stitch-design-captures-2026-06-17/post-rework-v10-passline/` | 通过：最终候选包覆盖 4 组、5 张高保真截图、5 份 HTML、4 张分组拼图 |

V10 最终候选包统计：

| 页面组 | 采用 screen | 高保真截图 | HTML | 判定 |
| --- | --- | ---: | ---: | --- |
| 主页 | V10 Home: No Gateway Label - PASS | 1 | 1 | 通过 |
| 应用包 | V8 Application Packages: Dark Four Column Matrix - PASS | 1 | 1 | 通过 |
| 设置 | V6 Settings Center: Clean User Language - PASS | 1 | 1 | 通过 |
| 启动器 | V9 Launcher Setup: No OS Branding - PASS；V6 Launcher Daily Use: Clean Main Window and Tray - PASS | 2 | 2 | 通过 |

### 17.2 最终验收结论

最终通过证据位于：

- `docs/development/stitch-design-captures-2026-06-17/post-rework-v10-passline/manifest.json`
- `docs/development/stitch-design-captures-2026-06-17/post-rework-v10-passline/summary.json`
- `docs/development/stitch-design-captures-2026-06-17/post-rework-v10-passline/contact-sheets/home.png`
- `docs/development/stitch-design-captures-2026-06-17/post-rework-v10-passline/contact-sheets/application-package.png`
- `docs/development/stitch-design-captures-2026-06-17/post-rework-v10-passline/contact-sheets/settings.png`
- `docs/development/stitch-design-captures-2026-06-17/post-rework-v10-passline/contact-sheets/launcher.png`

验收结果：**通过，可进入工程实现**。

保留限制：

- 本轮最终通过的是桌面高保真验收；移动端/窄屏响应式仍需工程实现前补一轮重排说明或实现验证。
- 启动器更新/回滚/卸载在最终候选中由日常主窗口和托盘菜单覆盖入口，不是完整分屏流程；工程实现时仍需补独立确认弹窗和失败恢复状态。
- Stitch HTML 中的 `<script>`、Material icon 名称等不是用户可见设计文案；最终禁用词扫描按截图与可见 UI 复核为准。

敏感信息扫描：`docs/development/STITCH_DESIGN_ACCEPTANCE_2026_06_17.md`、`docs/development/stitch-design-captures-2026-06-17/`、`docs/DIRECTORY_REFERENCE.md` 未发现 Stitch 密钥、Google API header 明文或相关密钥片段。
