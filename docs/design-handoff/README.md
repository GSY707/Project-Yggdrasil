# UX 重塑外包资料包

日期：2026-06-07

## 1. 用途

这个目录是交给外部 UX / 产品设计团队的工作资料包。它只覆盖“与用户接触的重新设计”。安装、打包、Docker、桌面封装、SaaS 等背后实现仍以已有技术文档为准；但启动器作为用户可见的安装、启动、诊断和应用包入口，需要纳入本资料包。

- `docs/development/PRODUCT_PACKAGING_AND_REMOTE_DATA_REQUIREMENTS_GAP_2026_06_04.md`
- `docs/development/USER_ADOPTION_SURFACE_AUDIT_2026_06_03.md`
- `docs/development/DESIGN_COMPLETION_EVALUATION_2026_06_05.md`

本资料包的判断口径：

- 普通用户入口必须 GUI-first。
- CLI、Prompt、MCP、评测、观测、原始 JSON 和内部 ID 应进入高级模式。
- 新设计应直接重构用户路径，不要在旧控制台上继续打补丁。
- 未上线能力必须标为计划中，不能被画成当前可用能力。

## 2. 产品一句话

世界树计划是一个本地优先的 LLM 工作台。用户通过应用模板导入素材、创建任务、观察 Agent 运行、获得可恢复的长期工作结果；高级用户和维护者可以进入 Prompt、MCP、评测、观测、调试和 CLI 层做深度控制。

## 3. 本轮要设计的四组界面

| 界面组 | 目标 | 设计资料 |
| --- | --- | --- |
| 基座面向用户界面 | 给普通用户一个正门：客服型 Agent、首次启动、应用推荐、问题回答、Prompt 代写和任务启动 | `01-base-user-interface-agent.md` |
| 特化应用包界面 | 每个应用包按场景展示价值、模板、产物、设置和必要的 Agent 工作过程 | `02-application-package-experience.md` |
| 设置 / 调试 / 配置界面 | 把普通设置、高级配置和维护者调试分层，避免普通用户被内部控制台压住 | `03-settings-debug-configuration.md` |
| 启动器 / 安装器体验 | 把本地产品栈、应用包直达入口、Docker/provider 检查、备份恢复、更新回滚和诊断做成普通用户可理解的桌面入口 | `04-launcher-experience.md` |

## 4. 当前真实基础

设计团队不需要从空白系统开始画概念稿。当前仓库已经有这些真实入口：

- Web 工作台：`apps/web/app/`
- 首次启动检查：`apps/web/app/components/overview-page.tsx`
- 任务创建与启动：`apps/web/app/components/task-launch-panel.tsx`
- 任务详情与控制：`apps/web/app/components/task-detail-page.tsx`
- LLM 工作分析：`apps/web/app/components/task-llm-work-analysis.tsx`
- 素材导入：`apps/web/app/components/assets-page.tsx`
- 应用列表与详情：`apps/web/app/components/applications-page.tsx`、`apps/web/app/components/application-detail-page.tsx`
- MCP、Prompt、评测、观测：`mcp-bridge-page.tsx`、`prompting-page.tsx`、`evaluations-page.tsx`、`observability-page.tsx`
- 发布与安全边界：`apps/web/app/components/release-page.tsx`

应用包也已经有正式元数据：

- `applications/*/yggdrasil.app.yaml`
- `applications/*/web/dashboard.json`
- `applications/*/config/defaults.json`
- `applications/*/prompt-profiles/`
- `applications/*/memory/`

其中 `graduate-researcher`、`deep-research`、`coding-greenfield`、`knowledge-studio` 已经提供场景化 `taskTemplates[]`、`exampleTasks[]`、`expectedOutputs[]` 和 `settingsSchema[]`，适合作为第一批设计样本。

## 5. 外包团队应交付什么

最低交付物：

1. 信息架构：普通模式、高级模式、开发者/维护者模式的分层导航。
2. 四组界面的关键流程原型：首次进入、询问客服 Agent、选择应用、创建任务、观察运行、查看结果、进入设置/调试、安装启动器并直达应用包。
3. 应用包页面模板：至少覆盖研究、学习、代码、知识整理四类应用。
4. Agent 工作过程可视化规格：真实上下文窗口、工作树下探/返回、历史窗口回顾、工具动作、错误和折叠规则。
5. 设置/调试分层规格：普通用户设置、应用配置、高级调试、数据与隐私边界。
6. 内容设计：用户词表、按钮文案、错误提示、空状态、计划中/当前可用能力标记。
7. 设计系统：组件、状态、密度、响应式规则、可访问性要求。
8. 工程落地映射：新页面和现有 `apps/web` 组件、应用包 `dashboard.json` 字段、Core API 能力之间的映射。
9. 删除/下沉清单：哪些旧控制台入口应从普通用户主线移走，哪些废旧测试或文档不应继续表达旧路线。
10. 启动器交付：安装向导、桌面主窗口、托盘菜单、应用包直达快捷方式、诊断、备份恢复、更新回滚和错误状态的设计规格。

## 6. 设计验收门槛

新方案至少应满足：

- 新用户不看 README 也能理解下一步该做什么。
- 用户能通过客服型 Agent 知道这个项目是什么、能做什么、当前还不能承诺什么。
- 用户能用自然目标被路由到合适应用包，而不是从内部 appId 里猜。
- 用户能让系统代写任务 Prompt / 目标 / 模板选择，并在启动前确认。
- 长任务用户能看见 Agent 正在做什么、为什么进入某个子步骤、何时返回父节点、哪些内容被折叠。
- 用户能展开历史窗口回顾，但默认界面不被完整日志淹没。
- 普通设置不要求编辑 `.env`、raw JSON 或内部 ID。
- 高级工具仍可找到，但不会成为普通用户默认入口。
- 数据位置、provider 出机、备份恢复、计划中的删除/远端能力必须表达清楚。
- 用户从应用专属快捷方式打开产品时，应能直接进入对应应用包界面或任务启动页，而不是回到内部控制台。

## 7. 资料来源

设计时优先看：

- `docs/development/UX_DESIGN_TEAM_HANDOFF_2026_06_04.md`
- `docs/development/USER_ADOPTION_SURFACE_AUDIT_2026_06_03.md`
- `docs/development/DESIGN_COMPLETION_EVALUATION_2026_06_05.md`
- `docs/development/PRODUCT_PACKAGING_AND_REMOTE_DATA_REQUIREMENTS_GAP_2026_06_04.md`
- `docs/development/INSTALL_LAUNCHER_AND_APP_PACKAGE_DISTRIBUTION_2026_06_06.md`
- `docs/demos/LOCAL_FIRST_TASK_DEMO.md`
- `docs/specs/application-package-interface-v0.1.md`
- `docs/LLM_WORK_ANALYZER_USER_GUIDE.md`
- `docs/specs/agent-runtime-protocol-v0.2.md`
- `docs/specs/work-tree-protocol-v0.2.md`
