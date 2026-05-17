# 世界树计划 · 目录说明书

> 项目完整目录结构及各路径的职责说明。适合新加入的开发者理解代码组织方式，以及查询特定功能所在位置。（2026/5/16 更新：补充记忆树 P0 执行闭环，包含 memory-write 严格阻断、runtime context 物化 sourceRunId、有界 retrieval 扩展与 pruning 合同字段保护；同步补记任务进度由 runtime task state + takeover work tree 联合判定、工具调用错误会包装成 tool result 回喂模型而非静默吞掉；并修正 LLM retry 测试桩流式响应契约，避免 `readline` 缺失导致的假失败）

---

## 顶层结构

```
世界树计划/
├── README.en.md    # 英文版仓库入口文档
├── .env.example    # 开源版本地环境变量示例（不含真实密钥；CLI/服务入口会自动加载）
├── CONTRIBUTING.md # 外部贡献工作流、测试要求、PR 约定
├── CONTRIBUTING.en.md # 英文版贡献指南
├── CODE_OF_CONDUCT.md # 社区行为准则与处理流程
├── CODE_OF_CONDUCT.en.md # 英文版社区行为准则
├── GOVERNANCE.md  # 维护者职责、决策方式与 RFC 入口
├── GOVERNANCE.en.md # 英文版治理说明
├── SECURITY.md    # 漏洞披露与安全支持策略
├── SECURITY.en.md # 英文版安全策略
├── apps/           # 前端应用
├── services/       # 后端微服务
├── packages/       # 共享库
├── modules/        # 可插拔功能模块
├── applications/   # 应用场景插件
├── adapters/       # 外部系统适配器
├── docs/           # 项目文档
├── evaluation/     # 评测框架
├── infra/          # 本地基础设施
├── migrations/     # 数据库迁移
├── scripts/        # CI 辅助脚本
├── tests/          # 集成测试
└── .github/        # GitHub Actions CI 配置
```

---

## 开源协作与治理入口

```
.
├── CONTRIBUTING.md                # 面向外部贡献者的首个入口
├── CONTRIBUTING.en.md             # 英文版贡献指南
├── CODE_OF_CONDUCT.md             # 社区行为规范
├── CODE_OF_CONDUCT.en.md          # 英文版社区行为规范
├── GOVERNANCE.md                  # 角色、评审权与 RFC 决策机制
├── GOVERNANCE.en.md               # 英文版治理说明
├── SECURITY.md                    # 安全问题私下披露流程
├── SECURITY.en.md                 # 英文版安全策略
├── .github/
│   ├── CODEOWNERS                 # 默认代码归属人与评审路由
│   ├── PULL_REQUEST_TEMPLATE.md   # PR 模板
│   └── ISSUE_TEMPLATE/
│       ├── bug_report.yml         # 缺陷提报表单
│       ├── feature_request.yml    # 功能请求表单
│       └── config.yml             # Issue 联系入口与 blank issue 策略
└── docs/
    ├── OPEN_SOURCE_BOUNDARY.md    # 开源边界、支持矩阵与稳定性承诺
    ├── OPEN_SOURCE_BOUNDARY.en.md # 英文版开源边界说明
    └── rfcs/
        ├── README.md              # RFC 流程说明
        ├── README.en.md           # 英文版 RFC 流程说明
        └── 0000-template.md       # RFC 模板
        └── 0000-template.en.md    # 英文版 RFC 模板
```

**关键说明：**
- 本仓库现在按“默认公开、密钥例外”的原则运行：一切提交进仓库的内容都应可公开分发，真实 API key 只能通过环境变量注入。
- `.env.example` 中的 `YGGDRASIL_STATE_ROOT` 指向状态根目录本身（例如 `.yggdrasil`）；运行时会自动在其下创建 `state/` 子目录。
- 重大设计变更不再直接靠 issue 或口头约定推进，统一通过 `docs/rfcs/` 目录下的 RFC 文档完成讨论、批准与留痕。
- 开源协作核心文档现在提供中英文双份入口；中文仍是工程内完整说明，英文版优先服务外部协作者的仓库浏览、贡献、治理与安全理解。

---

## 英文版入口

```
.
├── README.en.md                   # 英文版项目简介与快速入口
├── CONTRIBUTING.en.md             # 英文版贡献指南
├── CODE_OF_CONDUCT.en.md          # 英文版社区行为准则
├── GOVERNANCE.en.md               # 英文版治理说明
├── SECURITY.en.md                 # 英文版安全策略
└── docs/
    ├── OPEN_SOURCE_BOUNDARY.en.md # 英文版开源边界
    └── rfcs/
        ├── README.en.md           # 英文版 RFC 流程
        └── 0000-template.en.md    # 英文版 RFC 模板
```

**关键说明：**
- 英文版目前聚焦开源协作入口，而不是完整替代所有中文工程文档。
- 外部协作者从 README、贡献、安全、治理和 RFC 流程即可完成首轮参与；更深的工程实现仍以中文开发文档和协议文档为主。

---

## apps/ · 前端应用

```
apps/
└── web/                            # Next.js 15 + React 19 工作台
    ├── app/                        # Next.js App Router 路由目录
    │   ├── page.tsx                # 总览页（工作台首页）
    │   ├── layout.tsx              # 全局布局
    │   ├── api/
    │   │   └── core/               # Core API 的前端代理（透传到 :8000）
    │   ├── applications/           # 应用场景浏览页
    │   ├── assets/                 # 资产管理页（上传、查看、版本）
    │   ├── collaboration/          # PR 审查与协作页
    │   ├── evaluations/            # 评测结果展示页
    │   ├── mcp/                    # MCP 模块状态页
    │   ├── nodes/
    │   │   └── [nodeId]/           # 记忆节点详情页（动态路由）
    │   ├── observability/          # 调用链路追踪页
    │   ├── prompting/              # Prompt 模板管理与预览页
    │   ├── tasks/
    │   │   └── [taskId]/           # 任务详情页（动态路由）
    │   ├── training/               # 训练实验管理页
    │   └── components/             # 可复用 React 组件
    ├── lib/                        # 前端工具函数
    ├── package.json                # 前端包配置
    ├── next.config.ts              # Next.js 配置
    └── tsconfig.json               # TypeScript 配置（继承根配置）
```

**关键说明：**
- `app/api/core/` 是纯代理层，不含业务逻辑，请求直接转发至 Core API（`:8000`）。
- 应用场景 UI（如 coding、research）由 `applications/` 目录下的应用插件提供，Web 工作台本身不承载场景专属页面。

---

## services/ · 后端微服务

```
services/
├── core-api/                       # 控制面 API 服务（:8000）
│   ├── pyproject.toml
│   └── src/yggdrasil_core_api/
│       ├── main.py                 # 服务启动入口（uvicorn）
│       ├── app.py                  # FastAPI 应用实例、CORS、中间件
│       ├── config.py               # 配置读取（环境变量）
│       ├── services/               # 核心业务逻辑层（按资源域拆分的 Service 子包）
│       │   ├── task_service.py     # 任务生命周期相关业务逻辑
│       │   ├── memory_service.py   # 记忆树与检索相关业务逻辑
│       │   ├── runtime_service.py  # 运行时状态与执行记录查询
│       │   ├── evaluation_service.py # 评测结果与套件查询
│       │   └── ...                 # 其余资源域 Service
│       └── api/
│           ├── router.py           # 聚合所有路由
│           └── routes/             # 路由模块（每个资源一个文件）
│               ├── applications.py # GET /applications/ - 应用目录
│               ├── assets.py       # /assets/ - 资产 CRUD
│               ├── collaboration.py# /collaboration/ - PR 协作
│               ├── evaluations.py  # /evaluations/ - 评测结果
│               ├── health.py       # /health - 健康检查
│               ├── mcp.py          # /mcp/ - MCP 协议
│               ├── memory.py       # /memory/ - 记忆树操作
│               ├── modules.py      # /modules/ - 模块管理
│               ├── nodes.py        # /nodes/ - 节点 CRUD
│               ├── observability.py# /observability/ - 追踪数据
│               ├── outbox.py       # /outbox/ - 事件出箱
│               ├── prompting.py    # /prompting/ - Prompt 管理
│               ├── runtime.py      # /runtime/ - 运行时状态
│               ├── specs.py        # /specs/ - 规格查询
│               ├── tasks.py        # /tasks/ - 任务生命周期
│               ├── training.py     # /training/ - 训练实验
│               └── workbench.py    # /workbench/ - 总览数据
│
├── agent-runtime/                  # Agent 执行引擎服务（:8001）
│   ├── pyproject.toml
│   └── src/yggdrasil_agent_runtime/
│       ├── main.py                 # 服务启动入口
│       ├── app.py                  # FastAPI 应用实例
│       └── runtime.py              # Agent 执行主逻辑（任务分发、LLM 调用闭环）
│
├── module-host/                    # 模块宿主服务（:8002）
│   ├── pyproject.toml
│   └── src/yggdrasil_module_host/
│       ├── main.py                 # 服务启动入口
│       ├── app.py                  # FastAPI 应用实例
│       └── host.py                 # 模块发现、装配、注册、健康管理
│
└── worker/                         # 异步任务 Worker
    ├── pyproject.toml
    └── src/yggdrasil_worker/
        ├── main.py                 # Worker 启动入口
        └── registry.py             # Worker 活动注册、队列消费、retry/requeue 与 graceful shutdown
```

**关键说明：**
- `services/` 子包是控制面的业务逻辑层，已按资源域拆分；路由层仅做参数校验和委派。
- Agent Runtime 和 Core API 通过 NATS JetStream 事件总线通信，不直接 HTTP 调用。
- Worker 当前通过 `registry.py` 统一管理活动目录、Redis 队列消费和 retry/requeue，不再依赖独立 `activities.py` 实现文件。
- Worker 运行 Temporal Activity，处理耗时异步任务（如批量记忆导入、训练触发）。

---

## packages/ · 共享库

```
packages/
├── python-sdk/                     # 核心 Python SDK（被所有服务和模块依赖）
│   ├── pyproject.toml
│   └── src/yggdrasil_sdk/
│       ├── __init__.py             # 对外导出的公共 API
│       │
│       ├── # ── 领域模型层 ──────────────────────────────
│       ├── domain.py               # 核心领域对象（Task, Node, Agent, Memory 等，23KB）
│       ├── contracts.py            # 服务间数据契约与 Pydantic 模型（16KB）
│       │
│       ├── # ── 持久化层 ─────────────────────────────────
│       ├── persistence/
│       │   ├── models.py           # SQLAlchemy ORM 模型
│       │   ├── repositories/       # 仓储实现子包（task/memory/evaluation 等）
│       │   ├── migrations.py       # 迁移工具函数
│       │   └── vector_store.py     # pgvector 向量操作封装
│       │
│       ├── # ── 运行时核心 ──────────────────────────────
│       ├── runtime_kernel/         # 核心运行时内核子包（root mount、主循环、快照、安全关闭、任务接管；execution_loop 现已在 prompt 前按 work tree 锚点把 currentContext 物化进记忆树并执行 retrieval）
│       ├── llm_runtime.py          # LLM 调用封装（多模型路由、指数退避重试、安全关闭中断）；`SafeShutdownInterrupt` + pending-tool-calls 断点续跑；Prompt artifact 现带 takeover/work tree snapshot，response 工件现带 runtimeMetrics
│       ├── tool_runtime.py         # 工具注册与执行运行时
│       ├── hook_runtime.py         # Hook 事件触发与分发运行时
│       ├── hooks.py                # Hook 类型定义与注册接口
│       ├── application_runtime.py  # 应用配置加载与初始化
│       │
│       ├── # ── Prompt 管理 ──────────────────────────────
│       ├── prompting.py            # Prompt 模板管理、版本控制（22KB）；runtime prompt 的 response requirements 现内置 memory-write 标签语法提示，并追加 memory_retrieval_state 结构化节
│       ├── prompt_modules/
│       │   ├── compiler.py         # PromptCompiler 核心（模板 + 记忆 → 最终 Prompt）
│       │   └── formatters.py       # 不同格式的 Prompt 输出渲染
│       │
│       ├── # ── 记忆与模块 ──────────────────────────────
│       ├── model_routing.py        # 模型路由策略（按场景、按成本、按能力选模）
│       ├── catalog.py              # 模块目录（发现、注册、能力查询）；含 2s TTL 进程级缓存
│       ├── app_catalog.py          # 应用目录（应用配置加载与管理）
│       ├── spec_catalog.py         # 规格目录（协议规格注册与查询）
│       ├── module.py               # Module 基类（所有模块继承此类）
│       │
│       ├── # ── MCP 集成 ─────────────────────────────────
│       ├── mcp_bridge.py           # MCP 协议桥接实现（32KB）
│       ├── mcp_bridge_module.py    # MCP 模块封装
│       ├── mcp_servers/            # 内置 MCP Server 实现（含 execute_server 默认拒绝网络命令的 permission layer）
│       │
│       ├── # ── 协作与评测 ──────────────────────────────
│       ├── collaboration_runtime.py# PR 协作运行时（47KB）
│       ├── evaluation_runtime/     # 评测运行时子包（bootstrap / scorer / suite_runner；含 G4 longform / window stress / real-task parity 指标聚合、文件/目录语料装载、可选隔离沙筃保留，以及 live-provider-matrix 的正式合同型 acceptance 检查；_run_g4_live_provider_matrix_case 现在 forward responseRequirements / restartMessage）
│       ├── evaluation_cli.py       # 评测命令行工具
│       │
│       ├── # ── 可观测性 ─────────────────────────────────
│       ├── observability.py        # OTel Tracer 封装（11KB）
│       ├── observability_exporters.py # 多后端导出器（Jaeger、Langfuse）
│       │
│       └── # ── 运维工具 ─────────────────────────────────
│           ├── ops_runtime.py      # 运维兼容门面，保持 CLI 与外部导入路径稳定
│           ├── ops_runtime_backup.py # runtime 备份与恢复实现
│           ├── ops_runtime_compose.py # compose smoke 检查实现
│           ├── ops_runtime_live.py # 真实用户 live task pack 执行编排，含 repair、worker requeue drain、paid-provider 门控、pause/resume 与真实任务窗口对照入口
│           ├── ops_runtime_sandbox.py # 真实用户试跑沙箱准备实现
│           ├── ops_runtime_scorecard.py # scorecard 汇总与 live 评分行生成
│           ├── ops_runtime_shared.py # 运维共享 helper（路径、命令、冻结材料）
│           ├── ops_cli.py          # 运维命令行工具（backup/restore/compose-smoke/pilot-sandbox/pilot-live/pilot-scorecard）
│           └── support.py          # 通用工具函数（含隔离工作区复制、CJK word_count 估算）
│
├── contracts/                      # 跨语言共享类型定义
│   ├── package.json
│   └── src/                        # TypeScript 类型（与 Python contracts.py 对应）
│
└── frontend-sdk/                   # 前端专用 SDK
    ├── package.json
    └── src/                        # React Hooks、API 客户端、前端类型
```

**关键说明：**
- `runtime_kernel/` 是系统最核心的运行时子包，承载任务状态机、Agent 执行编排、上下文管理、快照与任务接管。
- `runtime_kernel/execution_loop.py` 现在会先基于 takeover protocol 预生成 work tree 锚点，再把外来 `currentContext` 物化为 temporary memory nodes（含 `sourceWorkTreeNodeId/sourceRunId`）、通过 `MEMORY_RETRIEVE_EXPAND` 重建 prompt 工作集，并把冻结字段的 retrieval state / takeoverProtocol / memory tag writes 写回 snapshot requestState、Prompt artifact 与 ModelInvocation 审计；对 restart carry-forward 恢复场景会按窗口预算裁剪检索结果，避免重复超窗重启。
- `runtime_kernel/execution_loop.py` 也负责正式任务进度流转：`Task.status/currentFocus/windowIndex/restartCount` 提供全局运行态，`TaskTakeoverProtocol.workTree.currentNodeId/status` 提供执行节点级进度；当前完成判定仍由 runtime 在写入执行结果后直接落 `completed`，而不是由独立 verifier 二次裁决。
- `prompting.py` 的 response requirements 现会向模型暴露最小 `memory-write` 标签语法；runtime prompt 还会附带结构化 `memory_retrieval_state`，用于核查当前 prompt 是否确实基于记忆树工作集而非旧摘要上下文。
- `llm_runtime.py` + `tool_runtime.py` 构成正式工具分发链：工具描述符先注册为 LLM function spec，执行期异常会被包成 `{status:error,error:...}` 的 tool message 回填到 conversation，因此默认不是“吞错”，但 runtime 当前也不会基于工具失败自动阻止任务完成，是否返工主要仍取决于模型后续回合和交付协议。
- `evaluation_runtime/` 是评测框架子包，承载套件加载、隔离运行、评分聚合和各阶段评测场景；设置 `YGGDRASIL_EVAL_PRESERVE_SANDBOX=1` 时，会把 case 沙箱保留到 `.yggdrasil/state/evaluation-sandboxes/` 供事后审计。
- `persistence/` 是唯一允许直接操作数据库的层，其他代码必须通过仓储接口。

---

## modules/ · 可插拔功能模块

每个模块是一个独立的 Python 包，通过 Hook 协议扩展核心能力。

```
modules/
├── # ── 记忆能力模块 ─────────────────────────────────────
├── text-memory/                    # 文本导入与检索扩展
│   ├── yggdrasil.module.yaml       # 模块清单（Hook 声明、权限、能力）
│   ├── pyproject.toml
│   └── src/text_memory/
│       └── plugin.py               # 主模块类
│
├── context-pruning/                # 上下文动态压缩（核心模块）
│   ├── yggdrasil.module.yaml
│   └── src/context_pruning/        # 基于信息熵的上下文裁剪实现
│
├── shared-memory/                  # 多用户共享记忆空间与权限控制（写权限现在可按 sourceWorkTreeNodeId 做节点级约束）
│   └── src/shared_memory/
│
├── multimodal-memory/              # 图片/音频资产的记忆节点关联（资产与摘要节点现可回挂到 related/source work tree）
│   └── src/multimodal_memory/
│
├── memory-organizer/               # 自动记忆整理与软遗忘治理
│   └── src/memory_organizer/
│
├── relation-discovery/             # 跨节点语义关联发现（新建边会带 source-work-tree 审计线索）
│   └── src/relation_discovery/
│
├── # ── 任务能力模块 ─────────────────────────────────────
├── pause-resume/                   # 任务暂停/恢复与快照管理
│   └── src/pause_resume/
│
├── task-takeover/                  # Gate 2 任务接管协议（目标解析、约束、计划、验证、交付）
│   └── src/yggdrasil_task_takeover/
│
├── subagent-runtime/               # Sub-Agent 独立分支执行框架
│   └── src/subagent_runtime/
│
├── subagent-pr/                    # Sub-Agent PR 提交与协作
│   └── src/subagent_pr/
│
├── # ── 平台能力模块 ─────────────────────────────────────
├── mcp-bridge/                     # Model Context Protocol 服务桥接
│   └── src/mcp_bridge/
│
├── training-lab/                   # 训练数据集、模型产物、验证门管理
│   └── src/training_lab/
│
└── # ── 场景模块（与应用插件配套） ────────────────────────
    ├── scene-coding-new-project/   # 从零编写代码场景的模块支持
    ├── scene-coding-inherit-project/ # 继承代码库场景的模块支持
    ├── scene-research-deep/        # 深度研究场景的模块支持
    ├── scene-writing-epic/         # 长篇创作场景的模块支持
    ├── scene-learning-coach/       # 学习辅导场景的模块支持
    ├── scene-maintenance-default/  # 系统运维场景的模块支持
    └── scene-scenic-guide/         # 信息导览场景的模块支持
```

**每个模块的标准文件结构：**

```
modules/<name>/
├── yggdrasil.module.yaml   # 必须：Hook 声明、所需权限、能力标签
├── pyproject.toml          # 必须：包配置与依赖
└── src/<package>/
    ├── __init__.py
    └── plugin.py           # 模块主类（继承 YggdrasilModule）
```

---

## applications/ · 应用场景插件

每个应用是一个针对特定场景预配置的 Agent 工作方式。

```
applications/
├── base-template/                  # 所有应用继承的基础模板
│   ├── yggdrasil.app.yaml          # 基础应用清单
│   └── prompts/                    # 基础提示模板
│
├── coding-greenfield/              # 从零开始的软件开发
├── coding-inherit/                 # 继承已有代码库
├── deep-research/                  # 深度研究与文献整理
├── epic-writing/                   # 长篇内容创作
├── knowledge-studio/               # 知识库建设与管理
├── learning-coach/                 # 个性化学习辅导
├── maintenance-ops/                # 系统运维与巡检
├── scenic-guide/                   # 信息导览与规划
└── software-factory/               # 大型软件工程全流程
```

**每个应用的标准文件结构：**

```
applications/<name>/
├── yggdrasil.app.yaml      # 应用清单（绑定模块、模型路由、种子上下文）
└── prompts/
    ├── system.md           # 系统提示（定义 Agent 身份与工作方式）
    └── seed.md             # 种子记忆（初始化上下文）
```

---

## adapters/ · 外部系统适配器

```
adapters/
├── model-providers/                # LLM 模型提供商适配器包
│   ├── pyproject.toml
│   └── src/yggdrasil_model_providers/
│       ├── __init__.py             # 导出 provider catalog / invoke_model / route_model
│       ├── gateway.py              # 真实 provider 调用网关；LongCat/OpenRouter/DeepSeek/VectorEngine；DeepSeek V4、thinking mode、tool-name aliasing
│       └── router.py               # 模型路由对接层（委派 python-sdk 的 route decision）
│
└── media-providers/                # 媒体处理适配器包
    ├── pyproject.toml
    └── src/                        # 媒体 provider 具体实现
```

**关键说明：**
- `gateway.py` 现在维护实时 provider catalog，并按当前可用凭证暴露候选模型。
- paid provider（如 `deepseek_direct`）只有在显式设置 `YGGDRASIL_ALLOW_PAID_MODELS=1` 时才会进入 runtime candidate catalog。
- DeepSeek 直连 profile 已切换到 `deepseek-v4-flash` / `deepseek-v4-pro`，并兼容 thinking mode、`reasoning_effort` 与 `reasoning_content` 回传。
- `packages/python-sdk/model_routing.py` 实现路由策略，适配器负责具体 API 调用和 provider 兼容性差异吸收。

---

## docs/ · 项目文档

```
docs/
├── PRD-v0.1.md                     # 产品需求文档 v0.1
├── DEVELOPER_GUIDE.md              # 开发指南（本套文档之一）
├── USER_GUIDE.md                   # 使用指南（本套文档之一）
├── DIRECTORY_REFERENCE.md          # 目录说明书（本文档）
├── QUALITY_BASELINE.md             # 质量基线：M8 benchmark 数字基准、API 延迟基准、稳定性门禁值与长任务伪无限上下文评测口径
│
├── adr/                            # 架构决策记录 (Architecture Decision Records)
│   ├── README.md                   # ADR 索引
│   ├── ADR-0001-kernel-module-adapter.md    # 三层架构决策
│   ├── ADR-0002-monorepo-layout.md          # Monorepo 布局决策
│   ├── ADR-0003-postgresql-primary-store.md # PostgreSQL 选型决策
│   ├── ADR-0004-temporal-workflow.md        # Temporal 工作流决策
│   ├── ADR-0005-litellm-model-gateway.md    # LiteLLM 模型网关决策
│   ├── ADR-0006-plugin-extension.md         # 插件扩展机制决策
│   ├── ADR-0007-nats-outbox.md              # NATS 事件出箱决策
│   ├── ADR-0008-authorization.md            # 授权模型演进决策
│   └── ADR-0009-observability-evaluation.md # 可观测与评测决策
│
├── protocols/                      # 内部协议规格
│   ├── README.md                   # 协议索引
│   ├── event-contracts-v0.1.md     # 事件契约（NATS 事件格式；补充 context.restart.requested/completed payload 约束）
│   ├── hook-contracts-v0.1.md      # Hook 接口契约（所有 Hook 事件清单；补充 restart-snapshot rehydrate 约束）
│   ├── module-lifecycle-v0.1.md    # 模块生命周期协议（启动/停止/健康）
│   ├── yggdrasil-module-manifest-v0.1.md    # 模块清单 YAML 规格
│   └── yggdrasil-application-manifest-v0.1.md # 应用清单 YAML 规格
│
├── specs/                          # 数据与 API 规格
│   ├── README.md                   # 规格索引
│   ├── agent-runtime-protocol-v0.1.md       # Agent 运行时协议规格
│   ├── task-takeover-protocol-v0.1.md       # Gate 2 任务接管协议：目标/约束/计划/验证/交付与出口标准
│   ├── runtime-domain-data-spec-v0.1.md     # 运行时、work tree、worker activity 与工具数据规格
│   ├── work-tree-protocol-v0.1.md           # Gate 3 工作树正式协议：执行节点、恢复锚点与完成态同步
│   └── asset-packaging-evaluation-data-spec-v0.1.md # 资产打包与评测数据规格
│
├── research/                       # 研究与探索性文档
│   ├── final-goal-roadmap-2026-04-30.md
│   │                               #   通向最终目标的阶段路线图：gate、功能开发簇、提示词成熟度与研究议程
│   ├── work-tree-protocol-draft-2026-05-05.md
│   │                               #   工作树研究草案：任务分解、优先图、熵增控制与阶段性重启的结构化定义
│   ├── hypergraph-reasoning-protocol-draft-2026-05-05.md
│   │                               #   超图推理研究草案：关系平铺、关系原因升维与模式识别的高阶推理方向
│   ├── real-user-validation-plan-2026-04-30.md
│   │                               #   参考版：真实用户验证计划的复用要点；原文已归档
│   ├── real-user-validation-baseline-freeze-2026-04-30.md
│   │                               #   参考版：材料冻结与口径锁定实践；原文已归档
│   ├── real-user-validation-internal-pilot-deepseek-2026-04-30.md
│   │                               #   参考版：内部试跑复盘模板；原文已归档
│   ├── g2-closeout-2026-05-15.md
│   │                               #   参考版：Gate 2 闭环结论与复用口径；原文已归档
│   ├── g3-closeout-2026-05-15.md
│   │                               #   参考版：Gate 3 闭环结论与复用口径；原文已归档
│   ├── g4-closeout-2026-05-15.md
│   │                               #   参考版：Gate 4 闭环结论与复用口径；原文已归档
│   ├── g4-assessment-and-roadmap-2026-05-15.md
│   │                               #   Gate 4 评估与完美实现路线图：多场景官方范围、few-shot 执行链、provider 矩阵与 CI 门禁
│   ├── g4-long-task-window-restart-baseline-2026-05-15.md
│   │                               #   Gate 4 长任务与窗口重启基线研究：LongCat 128k 基线、restart 闭环缺口、任务编排与 work tree 路线
│   ├── g4-real-task-window-parity-rerun-log-audit-2026-05-16.md
│   │                               #   4M 真实任务保留日志重跑记录：窗口 1/2 行为、保留沙箱路径、最终输出偏移与根因分析
│   ├── pseudo-infinite-context-window-roadmap-2026-05-16.md
│   │                               #   伪无限上下文窗口研究与优先级路线：当前已确认 restart 技术闭环成立，但交付闭环仍待修正
│   ├── 系统核心理念.md
│   │                               #   记忆树系统的核心设计哲学说明
│   ├── 系统概念/
│   │   ├── Agent 核心设计.md
│   │   ├── Agent 其他设计.md
│   │   ├── Agent行为模式建议组.md
│   │   ├── 记忆树核心设计.md
│   │   └── 记忆树其他设计.md
│   │                               #   中文系统设计文档集合：Agent/记忆树的核心与扩展设计草案
│   ├── future/
│   │   └── Project-Yggdrasil 未来多模态潜空间智能体架构.md
│   │                               #   面向远期能力的前瞻研究草案，不纳入当前 Gate 承诺范围
│   ├── 归档/
│   │                               #   历史归档目录（按约定不在目录索引中展开文件列表）
```

---

## evaluation/ · 评测框架

```
evaluation/
├── fixtures/                       # 评测样本数据
│   ├── memory-tree/                # 记忆树操作的标准样本
│   ├── retrieval/                  # 检索质量评测样本
│   ├── task-execution/             # 任务执行的端到端样本
│   └── real-user-validation/       # 真实用户验证冻结材料（任务包、评分表、provider 可用性矩阵等；scorecard 模板现含 first_token_at/first_token_seconds、计划质量与返工字段，由 pilot-sandbox 命令复制到专用目录）
│       ├── live-task-pack-g2-r2.json
│       │                           #   2026-05-15 官方 G2 第 1 轮：YGG-CI-01 / YGG-CG-01 / YGG-CG-03 全量通过
│       ├── live-task-pack-g2-r3-stability.json
│       │                           #   2026-05-15 稳定性复跑第 2 轮：YGG-CG-01 / YGG-CG-03 通过
│       ├── live-task-pack-g2-r4-stability.json
│       │                           #   2026-05-15 稳定性复跑第 3 轮：YGG-CG-01 / YGG-CG-03 通过
│       └── scorecard-2026-05-15-g2-complete.csv
│                                   #   2026-05-15 官方 G2 汇总评分表：7 条 live 样本，CG-03 恢复成功率 100%
│
└── suites/                         # 评测套件定义
    ├── regression-m4-m6.json       # M4-M6 回归套件
    ├── m8-benchmark-memory-strategies.json # M8 离线基准套件
    ├── m8-live-llm.json            # M8 真实 LLM 评测套件
    ├── m9-acceptance.json          # M9 验收套件
    ├── m9-control-plane.json       # M9 控制面回归套件
    ├── g2-regression.json          # G2 受控自治回归套件（复杂文件拆分固定样本）
    ├── g4-multiscene.json          # G4 官方三场景离线套件（快任务/跨会话/恢复/隔离）
    ├── g4-provider-matrix.json     # G4 官方 live provider matrix（DeepSeek + LongCat；live artifact 现含 token 用量拆分、contextLengthObservations 与 runtimeMetrics）
    ├── g4-provider-matrix-longform.json
                                    #   G4 单任务长样本 live provider matrix（先聚焦一个更长的 coding 任务；用于观察长任务 token 与上下文窗口压力）
    ├── g4-real-task-window-parity.json
                                    #   G4 真实任务窗口对照（把当前 repo 的真实语料作为同一任务输入，对比 64k / 128k 窗口效果；现显式要求 release brief 小节、parity judgment 与 restart 证据；已添加 responseRequirements 交付合同和 restartMessage 跨窗口提示）
    └── g4-window-restart-stress.json
                                    #   G4 官方伪无限上下文窗口 stress（显式 effectiveContextWindow + forcedWindowRestartBudget；LongCat/DeepSeek 正式对照）
```

**评测命令映射：**

| 命令 | 对应套件 |
|------|---------|
| `eval:regression` | `suites/regression-m4-m6.json` |
| `eval:m8:benchmark` | `suites/m8-benchmark-memory-strategies.json` |
| `eval:m8:live` | `suites/m8-live-llm.json` |
| `eval:m9:control-plane` | `suites/m9-control-plane.json` |
| `eval:m9:acceptance` | `suites/m9-acceptance.json` |
| `eval:g2:regression` | `suites/g2-regression.json` |
| `eval:g4:multiscene` | `suites/g4-multiscene.json` |
| `eval:g4:provider-matrix` | `suites/g4-provider-matrix.json` |
| `eval:g4:provider-matrix:longform` | `suites/g4-provider-matrix-longform.json` |
| `eval:g4:real-task-parity` | `suites/g4-real-task-window-parity.json` |
| `eval:g4:window-stress` | `suites/g4-window-restart-stress.json` |

---

## infra/ · 本地基础设施

```
infra/
├── README.md                       # 基础设施使用说明（端口、环境变量、备份恢复）
├── docker-compose.yml              # 主基础设施栈
│                                   #   PostgreSQL 17 :5432
│                                   #   Redis 7.4 :6379
│                                   #   NATS JetStream :4222
│                                   #   MinIO :9000/:9001
│                                   #   Temporal :7233 + UI :8088
│                                   #   Jaeger :16686
│                                   #   OTel Collector :4318
├── langfuse-compose.yml            # Langfuse 本地观测栈（独立端口段，避免冲突）
│                                   #   Langfuse Web :3100
│                                   #   ClickHouse :18123
│                                   #   Langfuse MinIO :19090
└── otel-collector-config.yaml      # OTel Collector 配置（Traces → Jaeger + Debug）
```

---

## migrations/ · 数据库迁移

```
migrations/
├── env.py                          # Alembic 环境配置（SQLAlchemy 连接配置）
├── script.py.mako                  # 迁移文件模板
└── versions/                       # 迁移版本文件（按时间戳排序）
    ├── <timestamp>_initial_schema.py
    ├── <timestamp>_add_node_relations.py
    └── ...
```

**关联配置：**
- 根目录 `alembic.ini`：迁移工具主配置
- `packages/python-sdk/src/yggdrasil_sdk/persistence/models.py`：ORM 模型（迁移的源）

**当前迁移头补充：**
- `migrations/versions/b6c1d7e92f44_align_json_columns_with_jsonb.py`：把后续几次 migration 中遗漏为 PostgreSQL `JSON` 的列补齐为 `JSONB`，消除 `alembic check` 的类型漂移。
- `migrations/versions/a91c2e7d4f33_memory_tree_worktree_audit_fields.py`：为 nodes / retrieval_requests / model_invocations / assets / prompt_compile_artifacts 补 work tree 审计字段，支撑“记忆树即全部记忆”的 snapshot、rehydrate 与多模态/关系发现闭环。

---

## tests/ · 集成测试

```
tests/
├── conftest.py                     # pytest 共享 Fixture：session 级 schema 初始化（单次），每 test 截断数据表并默认使用 memory coordination
├── fixtures/                       # 测试用固定样本数据
│
├── # ── 基础层测试 ────────────────────────────────────────
├── test_persistence_api.py         # 持久化层：ORM、仓储、迁移
├── test_prompting_runtime.py       # PromptCompiler 链路端到端
├── test_runtime_and_pruning.py     # 运行时内核 + 上下文裁剪（含记忆树物化检索、snapshot requestState 恢复、memory-write 标签落树与窗口重启闭环回归）
├── test_text_memory_and_adapters.py# 文本记忆模块与适配器集成
├── test_module_catalog.py          # 模块目录发现与注册
├── test_module_host_eventing.py    # 模块宿主事件总线集成
├── test_mcp_bridge.py              # MCP 协议桥接回归
├── test_support.py                 # 通用支持函数回归（含 CJK word_count 口径）
├── test_deepseek_gateway.py        # DeepSeek V4 / thinking / 文档化 LLM 配置回归
├── test_memory_pipeline_api.py     # 记忆流水线 API 回归
├── test_subagent_and_worker.py     # Sub-Agent 与 Temporal Worker 集成
├── test_secret_hygiene.py          # 仓库凭据泄露与文档回归检查
│
├── # ── Phase 1 专项测试（质量巩固） ────────────────────────
├── test_phase1_permissions_and_errors.py
│   │                               #   Pause-Resume：执行中途 pause / resume 轮次一致性
│   │                               #   权限元组：read-only mount、exclusive-read、无权限 Space
│   │                               #   错误恢复：LLM 5xx 回滚、Redis 不可用、快照损坏
│
├── # ── Phase 3 专项测试（稳定性与边界） ─────────────────────
├── test_phase3_stability_and_scale.py
│   │                               #   规模：1000 节点检索延迟基准
│   │                               #   规模：10 万词 fragment 导入内存/时间上界
│   │                               #   并发：2 worker 同时 pause 不产生双重快照
│   │                               #   并发：Sub-agent 并发写同一 Space 不产生数据竞争
│   │                               #   Hook 故障隔离：单模块 hook 异常不影响其他模块
│
├── # ── M8/M9 里程碑测试 ─────────────────────────────────
├── test_m8_runtime.py              # M8：评测与运维基础回归（含评测/真实试跑沙箱隔离）
├── test_g4_multiscene.py           # G4：官方三场景 multiscene suite 与 live budget 回归
├── test_m9_shared_memory.py        # M9：shared-memory 专项测试（含按 work tree 节点约束的写权限）
├── test_m9_pause_resume.py         # M9：pause-resume 专项测试
├── test_m9_multimodal_and_relations.py
│                                   #   M9：multimodal-memory + relation-discovery 专项测试（含资产/边的 work tree 溯源）
├── test_m9_memory_organizer.py     # M9：memory-organizer 专项测试
├── test_m9_training_lab.py         # M9：training-lab 专项测试
└── test_m9_acceptance.py           # M9：端到端验收测试 + 控制面 API 回归
```

**pytest 标记说明：**

| 标记 | 含义 | 运行时机 |
|------|------|---------|
| （无标记） | 快速单元 / 集成测试，使用 SQLite | PR、merge |
| `slow` | 慢的运行时闭环 / 控制面 API / 评测回归测试 | 仅在相关改动需要时手动执行，或发布前全量检查中统一处理 |

---

## scripts/ · CI 辅助脚本

```
scripts/
├── check_migrations.sh             # 验证 Alembic 迁移头与 ORM 模型一致
│                                   #   启动临时 pgvector 容器 → alembic upgrade head
│                                   #   → alembic check（检测 ORM 漂移）
├── smoke_test.sh                   # Compose 冒烟测试：启动 infra stack，调 core-api /health
│                                   #   启动 postgres/redis/nats/minio → alembic upgrade head
│                                   #   → 启动 core-api → GET /health
├── safe_shutdown.sh                # 向 worker 进程发送 SIGTERM，等待安全关闭检查点保存（Linux/macOS）
└── safe_shutdown.ps1               # 同上，Windows PowerShell 版本
```

**运行方式：**
```bash
bash scripts/check_migrations.sh   # 需要 docker，约 30 s
bash scripts/smoke_test.sh         # 需要 docker compose，约 60 s
```

---

## .github/ · GitHub Actions CI

```
.github/
└── workflows/
    ├── pr.yml      # PR smoke（触发：pull_request）
    │               #   Python syntax smoke + web lint/typecheck/build
    │               #   目标：只拦明显语法/构建损坏，约 3-5 min
    │
    ├── ci.yml      # merge smoke（触发：push to main）
    │               #   Python syntax smoke + web lint/typecheck/build
    │               #   目标：主干低成本冒烟，约 3-5 min
    │
    └── release-check.yml # 发布前手动全量检查（触发：workflow_dispatch）
                          #   migration-check：check_migrations.sh（ORM 漂移检测）
                          #   smoke-test：smoke_test.sh（端到端 /health 验证）
                          #   full-regression：release:check（SQLite 全量回归 + 评测 + web）
                          #   postgres-regression：pytest --postgres -m "not slow"
                          #   live-provider-smoke：可选输入，按需触发 eval:m8:live
                          #   g4-provider-matrix：可选输入，按需触发 eval:g4:provider-matrix
```

**当前测试/门禁策略：**

| 层级 | 触发 | 跳过内容 | 耗时 |
|------|------|---------|------|
| 本地开发 | 每次改动后 | 全仓回归、PostgreSQL、benchmark、live smoke | 按受影响测试而定 |
| PR | pull_request | 全仓 Python 测试、评测、docker | ~3-5 min |
| merge | push to main | 全仓 Python 测试、评测、docker | ~3-5 min |
| release-check | 手动 | 默认不跑 live provider smoke / G4 provider matrix（可选开启） | ~30-60 min |

---

## 根目录配置文件

| 文件 | 用途 |
|------|------|
| `pyproject.toml` | Python UV 工作区根配置，声明所有子工作区成员，Ruff 代码检查规则 |
| `package.json` | Node.js/pnpm 根配置，定义所有 `pnpm` 脚本命令 |
| `pnpm-workspace.yaml` | pnpm Monorepo 工作区成员声明 |
| `tsconfig.base.json` | TypeScript 基础配置，所有前端包继承 |
| `alembic.ini` | Alembic 数据库迁移工具主配置 |
| `pytest.ini` | pytest 运行配置（测试发现规则、标记定义） |
| `uv.lock` | Python 依赖锁定文件（不要手动修改） |
| `pnpm-lock.yaml` | Node.js 依赖锁定文件（不要手动修改） |
| `LLM.txt` | LLM 配置说明文档；运行时代码不会读取此文件，真实凭据只通过环境变量注入 |
| `docs/research/系统核心理念.md` | 记忆树系统的核心设计哲学说明 |
| `docs/research/pseudo-infinite-context-window-roadmap-2026-05-16.md` | 伪无限上下文窗口研究：理论依据、当前缺口、100 次窗口重启/压缩评测，以及“技术闭环已成立但交付闭环未证实”的最新口径 |
| `docs/research/g4-long-task-window-restart-baseline-2026-05-15.md` | G4 长任务基线研究：LongCat 窗口、restart 闭环缺口、任务编排与 work tree 最小落地路线 |
| `docs/research/g4-real-task-window-parity-rerun-log-audit-2026-05-16.md` | 4M 真实任务保留日志重跳记录：保留沙筃路径、窗口级行为、最终输出、根因分析、收紧 acceptance 后的正式 failed run，以及工程现实与理论设想差距和推进路线（responseRequirements / restartMessage / snapshot 修复） |
| `docs/research/memory-tree-agent-work-breakdown-2026-05-16.md` | 记忆树 Agent 全工作拆分研究：26 个最小可推进子任务、难度分级（L1-L5）、逐项实现路径与执行优先级，并可作为“记忆树替代上下文窗口”主线的影响排序输入 |
| `docs/research/memory-tree-agent-executable-roadmap-2026-05-16.md` | 记忆树 Agent 可执行路线图：按“写树-取树-恢复-验收”闭环重排 26 项任务，给出逐项输入/实现/验证/证据/退出条件的工程化执行稿 |
| `docs/research/系统概念/` | Agent / 记忆树中文系统设计文档集合 |
| `docs/research/future/` | 不进入当前 Gate 承诺范围的前瞻研究草案 |
| `todo.md` | 开发里程碑、阶段完成度与工作台优先事项追踪 |

---

## docs/ 补充 · 技术治理文档

```
docs/
├── ANTI_TECH_DEBT.md               # 防技术债开发规范：文件规模限制、异常处理规范、质量基线要求、
│                                   #   PR 检查清单、存量技术债清理计划（TD-01 ~ TD-09）
│                                   #   （2026-05-04 首版）
└── ...（其他文档同上）
```

---

## 文件查找速查

| 我想找… | 去哪里找 |
|---------|---------|
| 任务执行的核心逻辑（含记忆树物化检索、memory-write 标签写树与窗口重启主循环） | `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop.py` |
| LLM 调用与模型路由 | `packages/python-sdk/src/yggdrasil_sdk/llm_runtime.py` |
| Prompt 编译逻辑 | `packages/python-sdk/src/yggdrasil_sdk/prompt_modules/compiler.py` |
| 某个 API 路由实现 | `services/core-api/src/yggdrasil_core_api/api/routes/<resource>.py` |
| 某个 API 的业务逻辑 | `services/core-api/src/yggdrasil_core_api/services/<resource>_service.py` |
| 数据库 ORM 模型 | `packages/python-sdk/src/yggdrasil_sdk/persistence/models.py` |
| 数据契约/Pydantic 模型 | `packages/python-sdk/src/yggdrasil_sdk/contracts.py` |
| 领域对象定义 | `packages/python-sdk/src/yggdrasil_sdk/domain.py` |
| Hook 事件清单 | `docs/protocols/hook-contracts-v0.1.md` |
| 模块清单格式规格 | `docs/protocols/yggdrasil-module-manifest-v0.1.md` |
| 某个模块的实现 | `modules/<module-name>/src/<package>/plugin.py` |
| 基础设施端口配置 | `infra/README.md` 或 `infra/docker-compose.yml` |
| 前端页面 | `apps/web/app/<page>/page.tsx` |
| 评测套件定义 | `evaluation/suites/*.json` |
| 质量基线与延迟门禁值 | `docs/QUALITY_BASELINE.md` |
| 架构决策理由 | `docs/adr/ADR-<number>-*.md` |
| CI 工作流定义 | `.github/workflows/{pr,ci,release-check}.yml` |
| Alembic 迁移一致性检查 | `scripts/check_migrations.sh` |
| 端到端冒烟测试 | `scripts/smoke_test.sh` |
