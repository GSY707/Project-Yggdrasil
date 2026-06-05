# 设计完成度评估（2026-06-05）

## 1. 结论

按当前设计文档口径，本项目已经完成“长期任务 Agent OS 的工程骨架”和“本地 Web-first 试用路径”，但还没有完成“普通外部用户可直接安装、放心管理数据、可选择托管服务”的产品形态。

综合判断：

| 口径 | 完成度 | 判断 |
| --- | ---: | --- |
| 工程设计完成度 | 76/100 | 运行时、记忆、模块、应用包、评测和 Web 工作台均有正式实现与测试证据。 |
| 外部用户采用度 | 63/100 | Web-first 首次任务路径已出现，但安装、provider key、数据治理和发行物仍偏开发者。 |
| 产品发行完成度 | 35/100 | 完整 Docker 产品栈、桌面封装、SaaS、官方远端数据和删除治理仍是计划中。 |
| 综合完成度 | 68/100 | 可定向试用，可继续工程验证；未到大众用户可无指导采用。 |

一句话：**当前不是概念阶段，也不是成熟产品；它是一个工程能力相当完整、产品入口刚开始成形的本地试用版。**

## 2. 评估口径

本次以这些设计文档为准：

- `docs/PRD-v0.1.md`
- `docs/new/世界树计划正式项目定义.md`
- `docs/new/工作树.md`
- `docs/new/元提示词.md`
- `docs/specs/README.md`
- `docs/specs/agent-runtime-protocol-v0.2.md`
- `docs/specs/work-tree-protocol-v0.2.md`
- `docs/specs/world-build-awakening-task-start-protocol-v0.1.md`
- `docs/specs/application-package-interface-v0.1.md`
- `docs/specs/*-data-spec-v0.1.md`
- `docs/development/USER_ADOPTION_SURFACE_AUDIT_2026_06_03.md`
- `docs/development/PRODUCT_PACKAGING_AND_REMOTE_DATA_REQUIREMENTS_GAP_2026_06_04.md`
- `docs/development/TASK_CHECKFLOW_AUDIT_AND_ALIGNMENT_2026_05_27.md`
- `docs/research/project-assessments/memory-tree-theory-gap-assessment-2026-05-17.md`

优先级说明：

1. `docs/new/` 与 `docs/specs/*v0.2.md` 是当前运行语义的高优先级来源。
2. PRD v0.1 仍用于衡量第一版范围和里程碑。
3. 6 月 3 日用户采用度审计是历史基线；部分缺口已在 6 月 4 日后被实现补齐，不能照抄为当前事实。

## 3. 静态证据

本次未启动服务、未跑真实任务，采用静态代码和文档核对。

关键计数：

| 项 | 当前证据 |
| --- | --- |
| 应用包 | `applications/` 下 11 个应用均有 `yggdrasil.app.yaml` 和 `web/dashboard.json`。 |
| 应用任务模板 | 11 个应用合计 19 个 `taskTemplates[]`，所有应用合计 88 个 `settingsSchema[]` 字段。 |
| 顶部场景启动器 | `graduate-researcher`、`deep-research`、`coding-greenfield`、`knowledge-studio` 的模板均有 `exampleTasks[]` 与 `expectedOutputs[]`。 |
| 模块 | `modules/` 下 19 个模块均有 manifest，其中 10 个有 Python plugin。 |
| Core API | 路由层静态计数为 41 个 GET、39 个 POST、0 个 DELETE、0 个 PUT/PATCH。 |
| Web API 代理 | 当前前端代理主要覆盖 GET/POST，后续数据治理若增加 DELETE/PUT/PATCH，需要同步代理层和前端调用。 |
| 测试 | `tests/` 下 45 个 Python 测试文件，`evaluation/suites/` 下 18 个 suite JSON。 |
| 本地产品启动 | `package.json` 已提供 `corepack pnpm yggdrasil:up`，底层为 `uv run yggdrasil-ops launch`。 |

## 4. 设计项完成度

### 4.1 世界定义与规格收口：85/100

已完成：

- 项目已从“单一对话应用”收口为长期任务 Agent OS、记忆树基础设施和模块平台。
- `docs/specs/README.md` 明确 v0.2 运行语义为当前重做入口。
- `agent-runtime-protocol-v0.2.md` 和 `work-tree-protocol-v0.2.md` 已冻结父节点强编排、工作树、Boot Prompt、RootMount、邮箱、侧信道和 `awaiting-approval` 收口。

未完成：

- 文档层仍有历史基线、完成报告、审计文档并存，新人需要靠 `DIRECTORY_REFERENCE` 分辨“当前真相”和“历史状态”。
- “编写 -> 编译 -> 初次苏醒”的完整记忆编译流程还没有达到产品级闭环。

### 4.2 记忆树与建树：70/100

已完成：

- `Node`、`Edge`、`NodeVersion`、`SourceAnnotation`、`RetrievalRequest`、`ImportJob` 等对象已在规格、ORM、领域模型和 API 中出现。
- 文本记忆模块提供 `read_node`、`read_index`、`update_memory_with_version`、`append_memory_log`、`submit_memory_proposal`、`forget_node` 等工具。
- 资产导入已接到 Web `/assets`，支持文本文件/粘贴、切段预览、摘要节点和附加任务。

未完成：

- 记忆树理论目标尚未完全实现。此前评估给出的“全部记忆上树、窗口仅保留最小子任务工作集”综合完成度为 59/100。
- 自动整理、软遗忘、主动关联发现仍更多是模块化能力或测试能力，不是对普通用户可感知的主闭环。

### 4.3 Boot Prompt、RootMount 与任务启动边界：82/100

已完成：

- `prompting.py` 已有结构化 `bootSections`。
- `root_mount.py` 暴露 `RootMountPackage`、`startupMode`、中文语义根指针、`Working_Node`、邮箱和工作栈字段。
- 测试覆盖 `Working_Node`、standby、root mount、prompt 编译等关键合同。

未完成：

- “初次苏醒形成起始状态”和“任务级读取工作状态”的设计已有实现基础，但完整世界编译与首次苏醒体验还不是用户入口。
- Boot Prompt 的产品解释与调试视图仍偏内部。

### 4.4 工作树、运行时恢复和批准收口：80/100

已完成：

- `WorkTreeProtocol`、`WorkContextStack`、`currentNodeId`、`topFrameId`、`childCompletionSummaries` 都已进入实现和测试。
- 根节点完成后进入 `awaiting-approval`，控制面有 `approve-completion` 和 `request-revision`。
- pause/resume、mailbox wake、side-channel、budget/audit、cache summary 都有测试证据。

未完成：

- 伪无限上下文的“短窗口与长窗口交付等价”仍没有成为稳定产品承诺。
- `restart-recovery` 已收为 legacy/stress 场景，真实长任务的多次窗口压缩与等价交付仍是主线风险。

### 4.5 执行前任务核对门禁：45/100

已完成：

- `task-takeover` 有 parse/extract/plan/verify 结构。
- 文档已冻结“理解任务 -> 形成计划 -> 发起核对 -> 再执行”的目标流程。

未完成：

- runtime/prompt 尚未强制“先提交理解和计划给发起者确认，再执行”。
- 当前多数任务仍会直接进入 prepared/execution 路径。
- 缺少阻断式回归测试和控制面确认动作。

### 4.6 模型路由、工具分发与 MCP：72/100

已完成：

- 运行时记录 `ModelInvocation`、route decisions、token/cost/cache metrics。
- MCP bridge 有 workspace/server/import/sync/enable/disable 控制面。
- 工具执行隔离、别名归一、错误恢复和 sourceWorkTreeNodeId 透传已有测试。

未完成：

- 自动选模仍更像工程能力和评测能力，不是用户可调的产品功能。
- 高级 MCP 配置仍要求用户理解工具/服务/工作区边界。

### 4.7 Sub-Agent、协作、分支和 PR：65/100

已完成：

- 协作数据规格覆盖 space、branch、mount、permission tuple、pull request。
- Core API 有 spaces、branches、permission、subagent launch、pull request review。
- runtime 有 mailbox/side-channel/parent merge 的实现和测试。

未完成：

- “多 Agent 联邦、应用市场购买外部 Agent、Fork 同构分裂”仍是设计预留，不是产品级可用。
- PR 审核更像内部治理模型，普通用户看不到完整协作体验。

### 4.8 模块平台：72/100

已完成：

- 19 个模块都有 manifest。
- Module Host 提供 discovery、sync、reconcile、enable/disable、quarantine、hooks、subscriptions、health reports。
- Kernel/Module/Adapter 分层在目录和 ADR 中基本成立。

未完成：

- 第一版不支持真正运行时热更新，这符合非目标，但也限制外部模块生态。
- 部分 scene 模块只有 YAML 资产，没有 Python plugin；这是合理形态，但应用开发者需要明确区别“资产模块”和“能力模块”。
- 模块配置和生命周期对普通用户仍不可见或偏运维；Web 工作台没有完整模块管理页，主要通过概览和应用页展示模块摘要。

### 4.9 应用包与 Web-first 入口：78/100

已完成：

- 应用包接口已要求 manifest、prompt、scene、few-shot、memory、dashboard、taskTemplates、settingsSchema。
- 11 个应用均已装配 dashboard；顶部 4 个应用已像场景启动器。
- `TaskLaunchPanel` 支持选择应用模板、创建草稿、创建并启动、附加素材、错误解释。

未完成：

- 只有顶部 4 个应用有完整示例任务和预期产物，其余应用仍偏模板化。
- 应用价值表达已经改善，但与成熟产品的“我该选哪个”仍有距离。

### 4.10 Web 控制台与首次成功路径：73/100

已完成：

- `/overview` 有首次任务启动检查。
- `/tasks` 有创建和启动入口。
- `/assets` 能导入并附加素材。
- `/applications` 和应用详情能作为新任务入口。
- `/release` 把本地产品边界、备份恢复、隐私出机边界和计划中能力说清楚。

未完成：

- provider key 仍主要依赖 `.env` 和环境变量，不是完整设置页。
- 真实首个成功任务仍依赖用户本机 Docker、uv、pnpm、provider key、worker 和队列健康。
- 没有明显的 UI E2E 测试覆盖“打开 Web -> 导入素材 -> 创建任务 -> 启动任务 -> 查看状态”的完整点击路径。
- 没有数据删除页；后续 DELETE/PUT/PATCH 类控制面需要同步扩展 Next API 代理。
- 本次未启动服务核验实际首任务，因此这一项不能评为完成。

### 4.10.1 提示词资产管理：70/100

已完成：

- 应用和模块已经通过 prompt profile、scene、few-shot、registered tools 和 compile preview 形成提示词装配链。
- Core API 有 prompting routes，Web 有 prompting 页面，测试覆盖 PromptCompiler 和 runtime prompt 合同。

未完成：

- Web 端还没有成熟的提示词编辑、版本发布、回滚和差异审查工作流。
- 当前更适合开发者验证 prompt 编译结果，不适合作为非开发者的提示词运营台。

### 4.11 评测、观测和审计闭环：82/100

已完成：

- 评测 suite、evaluation runtime、LLM work analyzer、Langfuse trace 分析、observability summary 都已存在。
- `release:check` 聚合 Python、评测、Web lint/typecheck/build。
- 多处测试覆盖 `awaiting-approval`、runtime budget/audit、cache summary、mailbox、memory tools、M9 模块能力。

未完成：

- live provider 和 paid provider 仍受环境变量与外部服务影响，不能把所有评测结果理解为随时可复现。
- Graduate 高标准任务仍需要人工评审、外部来源、预算和 provider 稳定性共同闭合。

### 4.12 安全、权限与数据治理：55/100

已完成：

- 有权限等级、共享空间、permission tuple、secret hygiene 测试和开源边界文档。
- 本地产品文档明确 provider、trace、远端出机边界。

未完成：

- 没有完整 auth/tenant/workspace SaaS 模型。
- 没有 DELETE API；Core API 路由当前静态计数为 0 个 DELETE。
- 没有删除预览、dry-run 删除 API、删除审计表、删除证明和 Web 数据管理页。
- 软遗忘不能等同于用户级硬删除。

### 4.13 产品打包、发行、桌面和远端数据：35/100

已完成：

- 本地产品模式可通过 `corepack pnpm yggdrasil:up` 启动。
- `/release`、README、用户指南已明确哪些模式可用、哪些计划中。
- 本地 backup/restore 有 CLI。

未完成：

- 完整 Docker Compose 产品栈仍未发布；`infra/docker-compose.yml` 只启动依赖。
- 没有桌面安装包、托盘控制器、自动更新、桌面状态管理。
- 没有托管 / SaaS、官方远端数据托管、远端备份、远端删除。
- 没有服务条款、隐私政策、商业支持和 uptime 承诺。

## 5. PRD 里程碑完成度

| 里程碑 | 完成度 | 判断 |
| --- | ---: | --- |
| M0 规格冻结 | 85/100 | 规格和 ADR 足够完整，但历史文档仍多，需要靠索引导向当前真相。 |
| M1 文本记忆内核闭环 | 75/100 | 核心对象、导入、检索、版本、工具都有实现；理论目标尚未完全达标。 |
| M2 任务恢复闭环 | 80/100 | pause/resume、snapshot、work tree、approval 已有主闭环；伪无限上下文仍未完全稳定。 |
| M3 协作闭环 | 65/100 | Sub-Agent/PR/branch/permission 数据面存在；完整协作产品体验不足。 |
| M4 工程闭环 | 78/100 | Web、评测、观测、审计、CI 都有；普通用户入口和发行仍弱。 |

## 6. 当前最值得推进的缺口

按外部用户采用度和设计完整性排序：

1. **数据治理与删除闭环**：先做数据资产清单、dry-run 删除 API、删除审计和 Web 数据管理页。没有这个，外部用户不敢放心投入真实数据。
2. **完整 Docker 产品栈**：把当前源码启动器升级为可交付自托管形态，冻结镜像、健康检查、数据卷、备份恢复和升级策略。
3. **真实首任务 smoke**：为 Web-first 路径增加自动化 smoke，覆盖导入素材、选择应用、创建任务、启动任务、看到状态。
4. **provider 设置页**：从 `.env` 迁移到可验证的设置向导，至少提供 key 存在性、测试调用和预算提示。
5. **执行前核对门禁**：如果坚持“先核对再执行”作为产品目标，需要补状态、控制面动作和阻断式测试。
6. **清理历史误导文档**：不要删除有归档价值的审计，但应在索引和新报告中明确哪些是历史基线，避免旧判断继续带跑路线。

## 7. 本次完成与未完成

已完成：

- 梳理了设计文档的评估维度。
- 静态核对了应用包、模块、API 路由、测试、评测 suite、Web 任务启动、本地启动器、发布页和数据治理缺口。
- 给出按设计域拆分的完成度评分。

未完成：

- 未启动 Docker、Core API、Worker 或 Web。
- 未执行真实任务或 `release:check`。
- 未验证 provider key 与 live provider 可用性。

原因：

- 本次任务是设计完成度评估，静态证据已足够形成方向性结论；真实启动和 live 任务会显著增加时间与外部依赖变量，适合作为下一轮“首次成功路径 smoke”单独执行。
