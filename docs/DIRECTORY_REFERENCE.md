# 世界树计划 · 目录说明书

> 项目完整目录结构及各路径的职责说明。适合新加入的开发者理解代码组织方式，以及查询特定功能所在位置。（2026/5/4 更新：P0-P2 技术债清理、研究文档归档目录同步与根目录临时文件清理）

---

## 顶层结构

```
世界树计划/
├── README.en.md    # 英文版仓库入口文档
├── .env.example    # 开源版本地环境变量示例（不含真实密钥）
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
│       ├── services/               # 核心业务逻辑层（按资源域拆分）
│       │   ├── __init__.py         # WorkspaceService 组合导出与依赖注入入口
│       │   ├── _base.py            # 共享初始化与内部通用能力
│       │   ├── task_service.py     # 任务与运行状态相关业务
│       │   ├── memory_service.py   # 记忆树、导入与检索业务
│       │   ├── evaluation_service.py # 评测业务
│       │   ├── asset_service.py    # 资产与训练资产业务
│       │   ├── prompting_service.py# Prompt 配置与编译预览业务
│       │   ├── collaboration_service.py # PR 协作业务
│       │   └── runtime_service.py  # 应用、MCP、可观测与工作台业务
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
        └── activities.py           # Temporal Activity 实现
```

**关键说明：**
- `services/` 子包是控制面最核心的业务层，按资源域拆分后由 `WorkspaceService` 统一组合，路由层仅做参数校验和委派。
- Agent Runtime 和 Core API 通过 NATS JetStream 事件总线通信，不直接 HTTP 调用。
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
│       │   ├── repositories/        # 仓储接口实现（按领域拆分，兼容原导入路径）
│       │   │   ├── __init__.py      # 统一导出各 Repository
│       │   │   ├── _common.py       # 共享记录映射与辅助函数
│       │   │   ├── task.py          # TaskRepository
│       │   │   ├── memory.py        # NodeRepository, MemoryRepository
│       │   │   ├── evaluation.py    # EvaluationRepository
│       │   │   ├── asset.py         # AssetRepository
│       │   │   ├── prompting.py     # PromptAssetRepository
│       │   │   ├── collaboration.py # CollaborationRepository
│       │   │   └── platform.py      # Workspace/Runtime/Module/Outbox/Training 仓储
│       │   ├── migrations.py       # 迁移工具函数
│       │   └── vector_store.py     # pgvector 向量操作封装
│       │
│       ├── # ── 运行时核心 ──────────────────────────────
│       ├── runtime_kernel/          # 核心运行时内核（按子能力拆分）
│       │   ├── __init__.py          # 统一导出关键常量与执行入口
│       │   ├── _common.py           # 共享导入与常量
│       │   ├── root_mount.py        # root-mount 构建与预算辅助
│       │   ├── snapshot.py          # pause/resume 快照构建
│       │   └── execution_loop.py    # 主执行循环与写回链路
│       ├── llm_runtime.py          # LLM 调用封装（多模型路由、重试、记录，29KB）；记录 prompt/请求/响应与 round latency / reasoningContent 分段计时
│       ├── tool_runtime.py         # 工具注册与执行运行时
│       ├── hook_runtime.py         # Hook 事件触发与分发运行时
│       ├── hooks.py                # Hook 类型定义与注册接口
│       ├── application_runtime.py  # 应用配置加载与初始化
│       │
│       ├── # ── Prompt 管理 ──────────────────────────────
│       ├── prompting.py            # Prompt 模板管理、版本控制（22KB）
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
│       ├── mcp_servers/            # 内置 MCP Server 实现
│       │
│       ├── # ── 协作与评测 ──────────────────────────────
│       ├── collaboration_runtime.py# PR 协作运行时（47KB）
│       ├── evaluation_runtime/      # 评测 Suite 运行时（按职责拆分）
│       │   ├── __init__.py          # 统一导出评测入口与环境工具
│       │   ├── _common.py           # 共享导入与运行时依赖
│       │   ├── bootstrap.py         # 套件装载、隔离环境与种子准备
│       │   ├── scorer.py            # 覆盖率与评分逻辑
│       │   └── suite_runner.py      # 各 case 执行与 run_evaluation_suite
│       ├── evaluation_cli.py       # 评测命令行工具
│       │
│       ├── # ── 可观测性 ─────────────────────────────────
│       ├── observability.py        # OTel Tracer 封装（11KB）
│       ├── observability_exporters.py # 多后端导出器（Jaeger、Langfuse）
│       │
│       └── # ── 运维工具 ─────────────────────────────────
│           ├── ops_runtime.py      # 备份/恢复、compose smoke、真实用户试跑沙箱准备
│           ├── ops_cli.py          # 运维命令行工具（backup/restore/compose-smoke/pilot-sandbox）
│           └── support.py          # 通用工具函数（含隔离工作区复制）
│
├── contracts/                      # 跨语言共享类型定义
│   ├── package.json
│   └── src/                        # TypeScript 类型（与 Python contracts.py 对应）
│
└── frontend-sdk/                   # 前端专用 SDK
    ├── package.json
    └── src/
        ├── index.ts                # 统一聚合导出入口
        ├── types.ts                # 领域类型定义（Record/Response/Manifest）
        ├── api-client.ts           # 轻量 API 客户端封装
        ├── hooks.ts                # 通用异步状态 Hook 类型
        └── utils.ts                # URL 参数与对象判断工具
```

**关键说明：**
- `runtime_kernel/` 子包是任务状态机与执行编排核心，按 root-mount、snapshot、execution loop 拆分。
- `evaluation_runtime/` 子包承载完整评测框架，按 bootstrap、scorer、suite runner 拆分。
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
├── shared-memory/                  # 多用户共享记忆空间与权限控制
│   └── src/shared_memory/
│
├── multimodal-memory/              # 图片/音频资产的记忆节点关联
│   └── src/multimodal_memory/
│
├── memory-organizer/               # 自动记忆整理与软遗忘治理
│   └── src/memory_organizer/
│
├── relation-discovery/             # 跨节点语义关联发现
│   └── src/relation_discovery/
│
├── # ── 任务能力模块 ─────────────────────────────────────
├── pause-resume/                   # 任务暂停/恢复与快照管理
│   └── src/pause_resume/
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
├── prompt-profiles/
│   └── main-agent.yaml     # 主 Agent prompt profile（含 behavior/tool/memory/evidence 策略）
└── scenes/
    └── generic-default.yaml# 默认场景种子（新建应用建议至少包含该文件）
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
├── QUALITY_BASELINE.md             # 质量基线：M8 benchmark 数字基准、API 延迟基准、稳定性门禁值
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
│   ├── event-contracts-v0.1.md     # 事件契约（NATS 事件格式）
│   ├── hook-contracts-v0.1.md      # Hook 接口契约（所有 Hook 事件清单）
│   ├── module-lifecycle-v0.1.md    # 模块生命周期协议（启动/停止/健康）
│   ├── yggdrasil-module-manifest-v0.1.md    # 模块清单 YAML 规格
│   └── yggdrasil-application-manifest-v0.1.md # 应用清单 YAML 规格
│
├── specs/                          # 数据与 API 规格
│   ├── README.md                   # 规格索引
│   ├── agent-runtime-protocol-v0.1.md       # Agent 运行时协议规格
│   └── asset-packaging-evaluation-data-spec-v0.1.md # 资产打包与评测数据规格
│
├── research/                       # 研究与探索性文档
│   ├── final-goal-roadmap-2026-04-30.md
│   │                               #   通向最终目标的阶段路线图：gate、功能开发簇、提示词成熟度与研究议程
│   ├── real-user-validation-plan-2026-04-30.md
│   │                               #   真实用户验证计划：冻结材料、时间盒、评分口径与执行顺序
│   ├── real-user-validation-baseline-freeze-2026-04-30.md
│   │                               #   真实用户验证基线与材料冻结记录
│   ├── real-user-validation-internal-pilot-deepseek-2026-04-30.md
│   │                               #   DeepSeek V4 provider 更新后的内部试跑、调试与成本记录
│   └── 归档/
│       ├── prompt-engineering-and-seed-templates-v0.1.md
│       │                           #   提示词工程、PromptProfile、SeedTemplate 设计调研（归档）
│       ├── runtime-optimization-plan-2026-04-29.md
│       │                           #   运行时优化总计划（归档）
│       └── test-suite-cpu-time-analysis-2026-04-29.md
│                                   #   pytest CPU/等待时间拆分（归档）
```

---

## evaluation/ · 评测框架

```
evaluation/
├── fixtures/                       # 评测样本数据
│   ├── memory-tree/                # 记忆树操作的标准样本
│   ├── retrieval/                  # 检索质量评测样本
│   ├── task-execution/             # 任务执行的端到端样本
│   └── real-user-validation/       # 真实用户验证冻结材料（任务包、评分表等；由 pilot-sandbox 命令复制到专用目录）
│
└── suites/                         # 评测套件定义
    ├── regression/                 # M4-M6 回归套件
    ├── m8-benchmark/               # M8 离线基准套件
    ├── m8-live/                    # M8 真实 LLM 评测套件
    ├── m9-acceptance/              # M9 验收套件
    └── m9-control-plane/           # M9 控制面回归套件
```

**评测命令映射：**

| 命令 | 对应套件 |
|------|---------|
| `eval:regression` | `suites/regression/` |
| `eval:m8:benchmark` | `suites/m8-benchmark/` |
| `eval:m8:live` | `suites/m8-live/` |
| `eval:m9:control-plane` | `suites/m9-control-plane/` |

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
├── test_runtime_and_pruning.py     # 运行时内核 + 上下文裁剪
├── test_text_memory_and_adapters.py# 文本记忆模块与适配器集成
├── test_module_catalog.py          # 模块目录发现与注册
├── test_module_host_eventing.py    # 模块宿主事件总线集成
├── test_mcp_bridge.py              # MCP 协议桥接回归
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
├── test_m9_shared_memory.py        # M9：shared-memory 专项测试
├── test_m9_pause_resume.py         # M9：pause-resume 专项测试
├── test_m9_multimodal_and_relations.py
│                                   #   M9：multimodal-memory + relation-discovery 专项测试
├── test_m9_memory_organizer.py     # M9：memory-organizer 专项测试
├── test_m9_training_lab.py         # M9：training-lab 专项测试
└── test_m9_acceptance.py           # M9：端到端验收测试 + 控制面 API 回归
```

**pytest 标记说明：**

| 标记 | 含义 | 运行时机 |
|------|------|---------|
| （无标记） | 快速单元 / 集成测试，使用 SQLite | PR、merge |
| `slow` | 慢的运行时闭环 / 控制面 API / 评测回归测试；nightly 以 `pytest -m slow -n auto --dist loadfile` 并行执行 | nightly 仅 |

---

## scripts/ · CI 辅助脚本

```
scripts/
├── check_migrations.sh             # 验证 Alembic 迁移头与 ORM 模型一致
│                                   #   启动临时 pgvector 容器 → alembic upgrade head
│                                   #   → alembic check（检测 ORM 漂移）
└── smoke_test.sh                   # Compose 冒烟测试：启动 infra stack，调 core-api /health
                                    #   启动 postgres/redis/nats/minio → alembic upgrade head
                                    #   → 启动 core-api → GET /health
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
    ├── pr.yml      # PR 门禁（触发：pull_request）
    │               #   pytest -m "not slow" + web lint/typecheck/build
    │               #   目标：快速反馈，约 5 min
    │
    ├── ci.yml      # merge 门禁（触发：push to main）
    │               #   pytest -m "not slow" + eval:regression
    │               #   + eval:m9:control-plane + web lint/typecheck/build
    │               #   目标：完整验证，约 15 min
    │
    └── nightly.yml # 每日夜间（02:17 UTC，workflow_dispatch 可手动触发）
                    #   migration-check：check_migrations.sh（ORM 漂移检测）
                    #   smoke-test：smoke_test.sh（端到端 /health 验证）
                    #   slow-tests：pytest -m slow -n auto --dist loadfile
                    #     （并行慢集成 / 评测回归；未收集到用例时 no-op）
                    #   postgres-tests：pytest --postgres -m "not slow"
                    #     （夜间 PostgreSQL 回归门禁，防止 SQLite 偏差）
                    #   benchmark：eval:m8:benchmark（离线基准评测）
```

**CI 三层策略：**

| 层级 | 触发 | 跳过内容 | 耗时 |
|------|------|---------|------|
| PR | pull_request | slow 测试、回归评测、docker | ~5 min |
| merge | push to main | slow 测试、docker | ~15 min |
| nightly | 定时 / 手动 | — | ~30-60 min |

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
| `系统核心理念.md` | 记忆树系统的核心设计哲学说明 |
| `todo.md` | 当前执行阶段与未完成优先项追踪（工作台总览数据源） |

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
| 任务执行的核心逻辑 | `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop.py` |
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
| 评测套件定义 | `evaluation/suites/<suite>/` |
| 质量基线与延迟门禁值 | `docs/QUALITY_BASELINE.md` |
| 架构决策理由 | `docs/adr/ADR-<number>-*.md` |
| CI 工作流定义 | `.github/workflows/{pr,ci,nightly}.yml` |
| Alembic 迁移一致性检查 | `scripts/check_migrations.sh` |
| 端到端冒烟测试 | `scripts/smoke_test.sh` |
