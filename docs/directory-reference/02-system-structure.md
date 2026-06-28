## 分册 02：系统结构

> 包含：apps、services、packages、modules、applications、adapters、docs 主体结构与职责。

## apps/ · 前端应用

```
apps/
└── web/                            # Next.js 15 + React 19 工作台
    ├── app/                        # Next.js App Router 路由目录
    │   ├── page.tsx                # 总览页（工作台首页）
    │   ├── layout.tsx              # 全局布局；P1 后顶栏控制面与功能 chips 已改为中文产品标签
    │   ├── api/
    │   │   └── core/               # Core API 的前端代理（默认透传到 :5000）
    │   ├── applications/           # 应用场景浏览页
    │   ├── assets/                 # 资产管理页（上传、查看、版本）
    │   ├── collaboration/          # PR 审查与协作页
    │   ├── data-governance/        # 数据治理页（资产清单、备份快照、删除 dry-run、保护性 task 删除、删除证明、审计记录）
    │   ├── evaluations/            # 评测结果展示页
    │   ├── mcp/                    # MCP 模块状态页
    │   ├── nodes/
    │   │   └── [nodeId]/           # 记忆节点详情页（动态路由）
    │   ├── observability/          # 调用链路追踪页
    │   ├── prompting/              # Prompt 模板管理与预览页
    │   ├── release/                # 发布与安全页（发布模式、演示路径、本地数据、远端计划和隐私边界）
    │   ├── tasks/
    │   │   ├── page.tsx            # 任务页：应用模板创建/草稿/立即启动入口
    │   │   └── [taskId]/           # 任务详情页（动态路由，现已挂接 LLM 工作分析摘要与独立分析路由）
    │   ├── training/               # 训练实验管理页
    │   └── components/             # 可复用 React 组件
    ├── lib/                        # 前端工具函数
    ├── public/demo/                # README、用户指南和 /release 使用的产品截图
    ├── package.json                # 前端包配置
    ├── next.config.ts              # Next.js 配置
    └── tsconfig.json               # TypeScript 配置（继承根配置）
```

**关键说明：**
- `app/api/core/` 是纯代理层，不含业务逻辑，请求直接转发至 Core API（默认 `:5000`，可用 `YGGDRASIL_CORE_API_BASE_URL` 覆盖）。
- 应用场景 UI（如 coding、research）由 `applications/` 目录下的应用插件提供，Web 工作台本身不承载场景专属页面。
- `apps/web/app/components/overview-page.tsx` 现在把首次任务启动检查放在首页首屏，消费 `/workbench/overview.health.setupChecklist`，把 Core API、数据库、Redis、worker queue、provider key、state root 与 workspace path 的阻塞项直接展示给用户；首屏默认动作是新建任务、选择应用和导入素材。
- `apps/web/app/components/task-launch-panel.tsx` 是 Web-first 任务入口：从应用 dashboard 的 `taskTemplates[]` 生成任务，展示 `exampleTasks[]` / `expectedOutputs[]` 和已附加素材，依次调用 `POST /tasks` 与 `POST /tasks/{taskId}/start`；草稿创建后在面板内保留“已创建 / 立即启动 / 查看任务”反馈，不再依赖刷新任务列表维持状态。
- `apps/web/app/components/assets-page.tsx` 是 P1 素材导入入口：支持浏览器读取文本类文件、切段预览、导入状态、摘要节点展示，并通过 `/tasks?assetId=...` 把素材附加到新任务。
- `apps/web/app/components/release-page.tsx` 是 P2 发布与安全入口：展示当前真实支持的运行模式、provider 配置状态、演示步骤、截图、本地数据/日志/备份位置、出机边界，以及导出/恢复/删除状态；完整 Docker 产品栈和桌面封装当前只写成预览可验证，托管 / SaaS 和官方远端数据服务仍只能写成计划中。
- `apps/web/app/components/data-governance-page.tsx` 是本地数据治理入口：消费 `/data-governance/manifest`、`/backups`、`/backup`、`/deletion-plan`、`/delete` 和 `/operations`，开放备份快照、删除影响预览、受保护 task 硬删除、删除证明与审计查看；asset / node 仍只做预览。
- `apps/web/app/components/application-detail-page.tsx` 已把 `importantConfig` 的常用字段改成 dashboard `settingsSchema[]` 驱动的 typed controls，原始 JSON 只保留为高级模式；P1 后首屏按钮、身份、模块、记忆和配置标签改为用户可读中文。
- `apps/web/app/components/workbench-primitives.tsx` 提供 PageHeader/Surface/StatCard/StatusBadge 等共享组件；`StatusBadge` 现在保留原始状态值用于颜色判定，同时把常见运行状态、导入状态和素材角色显示为中文产品标签。
- `apps/web/app/lib/use-api-resource.ts` 是 Web 控制面通用 API loader；路径切换会清空旧数据，普通 reload 会保留当前数据直到新响应返回，避免任务创建后刷新列表时卸载启动面板。
- `apps/web/app/components/task-detail-page.tsx` 现已作为任务控制面 UI：除 pause/resume 外，也会展示 approve/revision、mailbox state/message 与 side-channel event，收口 P6 的前端可见性；同时已新增 LLM 工作分析摘要卡，并提供进入完整分析页的入口。
- `apps/web/app/components/task-llm-work-analysis.tsx` 负责 Web 端的正式 LLM 工作分析视图：任务详情页用 compact 模式展示摘要，独立分析页用 full 模式展示窗口、轮次、工具、工件和辅助信号；本轮已补上工作树调试摘要卡、节点切换时间线、prefix cache key 与 cache hit/write/non-cache 视图。
- `apps/web/app/tasks/[taskId]/analysis/page.tsx` 为任务级独立分析路由，直接消费 `/tasks/{taskId}/analysis/latest`。

---

## services/ · 后端微服务

```
services/
├── core-api/                       # 控制面 API 服务（:5000）
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
│               ├── data_governance.py # /data-governance/ - 数据资产清单、备份快照、删除 dry-run、审计、删除前备份与 task 硬删除后端
│               ├── evaluations.py  # /evaluations/ - 评测结果
│               ├── health.py       # /health - 健康检查（含首次启动 setupChecklist）
│               ├── mcp.py          # /mcp/ - MCP 协议
│               ├── memory.py       # /memory/ - 记忆树操作
│               ├── modules.py      # /modules/ - 模块管理
│               ├── nodes.py        # /nodes/ - 节点 CRUD
│               ├── observability.py# /observability/ - 追踪数据
│               ├── outbox.py       # /outbox/ - 事件出箱
│               ├── prompting.py    # /prompting/ - Prompt 管理
│               ├── runtime.py      # /runtime/ - 运行时状态、模型调用与 LLM 工作分析入口
│               ├── specs.py        # /specs/ - 规格查询
│               ├── tasks.py        # /tasks/ - 任务生命周期、P4 approve/revision 控制面与 latest LLM analysis 入口
│               ├── training.py     # /training/ - 训练实验
│               └── workbench.py    # /workbench/ - 总览数据（首页也消费嵌套 health setupChecklist）
│
├── agent-runtime/                  # Agent 执行引擎服务（:5001）
│   ├── pyproject.toml
│   └── src/yggdrasil_agent_runtime/
│       ├── main.py                 # 服务启动入口
│       ├── app.py                  # FastAPI 应用实例
│       └── runtime.py              # Agent 执行主逻辑（任务分发、LLM 调用闭环；现导出 approve/revision 运行时控制）
│
├── module-host/                    # 模块宿主服务（:5002）
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
│       ├── runtime_kernel/         # 核心运行时内核子包（root mount、主循环、快照、安全关闭、任务接管、工作树图 ready-set reducer；execution_loop 已收敛为包级入口 + state/worker/transitions 语义模块；takeover reducer 现负责 work tree/context stack 推进、revision reopen 与 approval finalize）
│       ├── llm_runtime/            # LLM 调用封装包（core/artifacts/invoke 三层；包入口保留原 `yggdrasil_sdk.llm_runtime` 导入面）
│       ├── tool_runtime.py         # 工具注册与执行运行时
│       ├── hook_runtime.py         # Hook 事件触发与分发运行时
│       ├── hooks.py                # Hook 类型定义与注册接口
│       ├── application_runtime.py  # 应用配置加载与初始化
│       │
│       ├── # ── Prompt 管理 ──────────────────────────────
│       ├── prompting.py            # Prompt 模板管理、版本控制；runtime prompt 已增加 bootSections 四段（physical_interface/world_roots/behavior_constitution/scene_recovery），其中 physical_interface 现在只保留稳定接口绑定与实际 tool/capability inventory，场景化 tool policy 已移出 boot；恢复态会规范化 Working_Node / currentNodeId / memoryRetrievalState.workTreeNodeId / pcMemo，并在 P4 路径附带 `work_context_stack` / `childCompletionSummaries`；`runtime_hints` 只作为辅助线索；response requirements 已瘦身为 LLM 自主推进、任务需要交付和安全/不可逆动作确认的短合同，few-shot 仍在恢复态自动跳过
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
│       ├── collaboration_runtime/  # PR 协作运行时包（context/subagents 语义模块）
│       ├── evaluation_runtime/     # 评测运行时子包（bootstrap / scorer / suite_runner；含 G4 longform / window stress / real-task parity 指标聚合、文件/目录语料装载、可选隔离沙箱保留，以及 live-provider-matrix 的正式合同型 acceptance 检查；fallback local evaluation 环境在 preserve sandbox 或显式 state root 下也会把 suite metrics 与 case sandboxes 写入持久 state，case 级 isolated runtime 现也会继承 suite 传入的 workspace_root，避免 clean workspace run 仍回拷原仓库）
│       ├── evaluation_cli.py       # 评测命令行工具
│       │
│       ├── # ── 可观测性 ─────────────────────────────────
│       ├── observability.py        # OTel Tracer 封装（11KB）
│       ├── observability_exporters.py # 多后端导出器（Jaeger、Langfuse；本地 4318/3100 不可达时自动跳过可选 exporter）
│       │
│       └── # ── 运维工具 ─────────────────────────────────
│           ├── data_governance.py  # 数据资产 manifest、删除影响预览、task 硬删除执行、删除证明与审计记录
│           ├── ops_runtime/        # 运维运行时包（backup/compose/sandbox/scorecard/live/launcher/shared；compose 现含产品栈 smoke）
│           ├── ops_cli.py          # 运维命令行工具（backup/restore/compose-smoke/product-compose-smoke/launch/pilot-sandbox/pilot-live/pilot-scorecard）
│           └── support.py          # 通用工具函数（含隔离工作区复制、CJK word_count 估算；sandbox 复制会动态忽略当前配置的 state root/state dir，并默认跳过仓库顶层 tmp，避免持久审计目录与临时输出被递归拷贝进下一轮评测）
│
├── contracts/                      # 跨语言共享类型定义
│   ├── package.json
│   └── src/                        # TypeScript 类型（与 Python contracts.py 对应）
│
└── frontend-sdk/                   # 前端专用 SDK
    ├── package.json
    └── src/                        # React Hooks、API 客户端、前端类型；`types.ts` 现已补齐 TaskDetailResponse、ApplicationDashboard、taskTemplates/settingsSchema/exampleTasks/expectedOutputs、AssetIngestResponse、TaskLaunchAttachment、setupChecklist、DataGovernance 备份和删除证明契约
```

**关键说明：**
- `runtime_kernel/` 是系统最核心的运行时子包，承载任务状态机、Agent 执行编排、上下文管理、快照、任务接管、工作树图调度纯函数、Fork batch planner、Fork result merge helper 与 Batch 6 deterministic runtime harness 验证入口。
- `runtime_kernel/work_tree_graph.py` 是工作树图 / Fork 并行纯函数 reducer：只读取 `WorkTreeProtocol`、active fork run 视图、graphState 和 policy，输出 direct child ready/blocked set、pending 信息流摘要、`maxForks` / `reserveParentMergeSlots` 后的可用 Fork 槽位、`allowRecursiveFork=false` 递归启动阻断与候选 batch；它明确不复用 subagent task/branch，也不切 task-global `currentNodeId`。
- `runtime_kernel/fork_runtime.py` 是 Batch 3/5 Fork batch 与 result merge runtime helper：把 ready-set 可启动项创建为 `runType=fork` 的 AgentRun 与 `core.agent.main.execute` / `intent=fork` 的 RuntimeWorkItem；`merge_fork_result_and_plan_next_batch()` 会把 ForkResultEnvelope 合并到 child 节点，并在 `planImpact=none` 且 ready-set 允许时创建下一批 DB work item；真实 fork 完成路径已由 `execution_loop/transitions.py` 负责 Redis enqueue，Batch 6 harness 已用两轮 worker + fake LLM 落库验证 prompt artifact、workTreeSnapshot 继承和 pending summary-only 信息流。
- `runtime_kernel/root_mount.py` 现在不再只给底层 identity/context/execution refs；它还会输出中文语义根指针、`SYS_ROOT_PROTOCOL`、`startupLoadOrder`、tool/capability index、mailbox/standby 状态，以及 `standby / resume-node / bootstrap` 三态 `startupMode`，作为启动恢复的数据面。
- `runtime_kernel/execution_loop/` 当前为包级运行主链：`state_metrics.py` / `state_window.py` / `state_memory.py` 承载指标、窗口工件、记忆树物化与 assistant tag 解析，`transitions.py` 承载完成/续跑/审批流转，`worker.py` 承载主 worker 入口；包入口仍保持 `yggdrasil_sdk.runtime_kernel.execution_loop` monkeypatch 与导入面。执行链仍保持“先基于 takeover protocol 预生成 work tree 锚点，再把外来 `currentContext` 物化进记忆树并执行 retrieval”，并已在 retrieval 前优先恢复 `currentNodeId / workingNodeAnnotation / pcMemo`，同时额外落 `runtime/window-executions/*.json` 结构化窗口工件，记录每窗 work tree、retrieval、合同摘要与交付状态。2026-06-28 起，`state_metrics._window_restart_trigger()` 只在显式 `forceWindowRestart` 或实际超过窗口阈值时触发窗口切换/overflow，`forcedWindowRestartBudget` 不再伪造未超阈值的失败。Batch 4 已在 `worker.py` 接入 `runType=fork` child-local run view，并在 `transitions.py` 隔离 fork 完成态，避免 fork 完成覆盖父任务全局 status/currentFocus；Batch 6 已移除当前 fork 路径 touched 文件里的星号导入，`F403/F405` 不再需要用忽略项压制。
- 本轮设计冻结已同步到规格层：`docs/specs/agent-runtime-protocol-v0.2.md` 明确 `restart-recovery` 仅 legacy/stress 兼容、v2 默认“压缩优先+超阈值失败”；`docs/specs/work-tree-protocol-v0.2.md` 把第 9 章改为“窗口超阈值处理”，补齐压缩范围起止约束；`docs/specs/runtime-domain-data-spec-v0.1.md` 为 `ContextPruningPlan` 增加 `compressionRange` 元数据并固化 `maxUncompressedTailBeforeDecompress` 语义。
- `runtime_kernel/execution_loop.py` 也负责正式任务进度流转：`Task.status/currentFocus/windowIndex/restartCount` 提供全局运行态，`TaskTakeoverProtocol.workTree.currentNodeId/status` 与 `WorkContextStack.topFrameId` 提供执行节点级进度；在当前单一路径下，非根子节点完成/失败会先回父节点，由父节点通过 `work-node-enter` / `work-node-create` 显式编排后续路径，根节点完成仍进入 `awaiting-approval`（后续需收窄到显式用户确认 / 不可逆动作边界）。`task-takeover` 模块现在只保留安全 / 来源证据类 hard gate；`delivery.result / evidence` 为 advisory，`pending / incomplete` 不再作为硬交付门禁，缺少可选章节不会触发格式型 retry / failed。
- `runtime_kernel/execution_loop/worker.py` 对恢复态 snapshot 额外做完整性校验；若 `pendingAction.checksum` 失配，会先把 snapshot 标记为 `created` 并持久化 `snapshot-corrupted:*` blocker，再拒绝恢复；同一文件现在也会把 `invoke_runtime_completion()` 的 provider/LLM invocation exception 纳入 failed-leaf continuation：非根叶子若已有 `failureTransition.requiresContinuation`，会像窗口超限一样先写回 `failed + failureSummary`，再排队 sibling/parent continuation，而不是直接把整任务打成 failed，对应回归位于 `tests/test_runtime_p4_foundation.py`。
- `prompting.py` 的 response requirements 现会向模型暴露最小 `memory-write` 标签语法，并显式给出 `work-node-create` / `work-node-enter` 标签契约；工作树只作为上下文卫生工具，简单任务可直接完成，需要隔离噪声、候选方向、重复项、局部实验或并行工作时才建节点。runtime prompt 还会附带结构化 `memory_retrieval_state`，并在恢复态把 Working_Node、`currentNodeId`、`pcMemo` 与 retrieval node pointer 统一到同一执行节点；P4 路径额外会渲染 `work_context_stack`，把最近几层 frame 的 `childCompletionSummaries` 暴露给父节点续跑；few-shot 示例不再作为独立 user/assistant 消息写入 prompt，而是折叠进系统示例块，并在恢复态跳过以降低重复文本；takeover 协议段现在也优先给出 work tree / step count 摘要，而不是重新渲染显式计划清单。
- `llm_work_analysis.py` 现作为正式的 run-first 分析器：主键骨架是 task/run/model_invocations，本地补读 request/response/prompt/metrics/takeover/work-context/window-execution 工件，并默认把结果写入 `state/analysis/llm-work/` 供评测与调试复用；当前已补齐 cache summary、work-tree timeline、approval stop、mixed outcome 与 per-invocation `runtime/window-executions/by-invocation/` 历史工件读取。
- `langfuse_trace_layered_analysis.py` 现兼容中文化的任务目标/任务说明/当前焦点标签，避免 prompt 标签本地化后 Langfuse 文本审查丢失任务抽取结果。
- `llm_runtime/` + `tool_runtime.py` 构成正式工具分发链；`llm_runtime/core.py`、`llm_runtime/artifacts.py` 与 `llm_runtime/invoke.py` 分别承载预算/消息、工件/工具会话、模型调用主流程，包入口负责 Langfuse monkeypatch 同步。
- `evaluation_runtime/` 是评测框架子包，承载套件加载、隔离运行、评分聚合和各阶段评测场景；设置 `YGGDRASIL_EVAL_PRESERVE_SANDBOX=1` 时，会把 case 沙箱保留到 `.yggdrasil/state/evaluation-sandboxes/` 供事后审计；若 suite runner 落入 local fallback，它现在也会沿用持久 state 根，避免 evalrun 与 strict 审计工件只写进临时目录；Batch 6 已接入 `runtime.fork_harness` 与 `runtime.fork_harness_live_candidate`，其中 live candidate 未显式开启时会记录为 blocked/non-pass，开启后已通过真实 LongCat runtime completed 证据。
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
├── graduate-researcher/            # 研究生学习与研究（预算驱动）
├── maintenance-ops/                # 系统运维与巡检
├── scenic-guide/                   # 信息导览与规划
└── software-factory/               # 大型软件工程全流程
```

**每个应用的标准文件结构：**

```
applications/<name>/
├── yggdrasil.app.yaml      # 应用清单（绑定模块、模型路由、种子上下文）
├── config/defaults.json     # 应用默认配置
├── web/dashboard.json       # 控制面元数据：hero、quickActions、taskTemplates、exampleTasks、expectedOutputs、settingsSchema
├── memory/                  # 应用静态记忆资产（随包发布，运行时按应用命名空间叠加）
├── prompt-profiles/          # 主 Agent / Sub-Agent prompt profile
└── scenes/                   # seed template / 场景启动资产
```

**关键说明：**
- `web/dashboard.json` 现在是用户采用面的关键入口，必须提供 `taskTemplates[]` 供 Web 任务启动面板使用；顶部应用模板应提供 `exampleTasks[]` 与 `expectedOutputs[]`，并提供 `settingsSchema[]` 把 provider、model、预算、workspace、输出风格、记忆命名空间和工具权限渲染为 typed controls。
- `apps/web/app/components/task-launch-panel.tsx` 会读取 `/health.providerStatus`；provider key 缺失或 `YGGDRASIL_DISABLE_LIVE_LLM=1` fallback 测试模式会阻止直接启动真实任务，但仍允许创建草稿。
- `services/core-api/src/yggdrasil_core_api/services/runtime_service.py` 的 `list_applications()` 已把 dashboard payload 随 `GET /applications` 返回，任务页无需再逐个请求应用详情才能显示模板。

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
- `packages/python-sdk/src/yggdrasil_sdk/provider_config.py` 是 provider key 配置状态的共享契约，不暴露 key 值；Core API `/health.providerStatus` 和 Web 启动阻塞都应从这里取状态。
- paid provider（如 `deepseek_direct`）只有在显式设置 `YGGDRASIL_ALLOW_PAID_MODELS=1` 时才会进入 runtime candidate catalog。
- DeepSeek 直连 profile 已切换到 `deepseek-v4-flash` / `deepseek-v4-pro`，并兼容 thinking mode、`reasoning_effort` 与 `reasoning_content` 回传。
- `packages/python-sdk/model_routing.py` 实现路由策略，适配器负责具体 API 调用和 provider 兼容性差异吸收。

---


