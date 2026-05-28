# Project Yggdrasil

[English README](README.en.md)

世界树计划的正式工程仓库。

note：我们正在进行一项大型修改，改变 LLM 的工作流程，本项目的很多文档、模块组装，预计都会发生较大变化

note2：这个项目目前还不能用，但有技术性验证的版本：https://github.com/GSY707/Project-Yggdrasil-dev-test.git

当前仓库是一个长期任务系统，具体目标见 docs\research\系统概念：

- 后端以 FastAPI、SQLAlchemy、Alembic、Redis 为核心，承载任务运行、记忆树持久化、模块控制面和评测链路。
- 前端以 Next.js 15 + React 19 为核心，直接消费 core-api 的正式数据面，而不是扫描仓库文件。
- 模块层已经包含 text-memory、context-pruning、subagent-pr、shared-memory、pause-resume、multimodal-memory、relation-discovery、memory-organizer、training-lab 等正式实现。
- 评测层已经包含 M4-M6 回归、M8 benchmark/live、M9 acceptance，以及新增的 M9 control-plane 回归。

## 当前能力

- 正式任务执行链：任务创建、主 Agent 执行、safe-stop、pause/resume、Sub-Agent、PR 协作。
- 正式记忆链：文本导入、建树、检索扩展、共享空间、权限 tuple、多模态资产落库、关系发现、软遗忘治理。
- 正式 PromptOps：PromptCompiler、seed template、prompt compile artifact、模型调用请求/响应落盘、工具注册与多轮 tool execution 审计。
- 正式训练实验：dataset version、model artifact、验证门和控制面 API。
- 正式运维与评测：OpenTelemetry、Langfuse、backup/restore、compose smoke、evaluation suites。

## 基座与应用插件

- 基座继续保留 Kernel + Module + Adapter 这一内部结构，并提供通用控制面、运行时、PromptOps、评测与运维能力。
- 应用插件负责具体场景下的 Agent 组合、应用配置和应用界面；基座 Web 不承载面向单一场景的应用 UI。
- 当前任务、AgentRun、快照、模型调用与 Prompt 编译工件已经补上 appId 维度，为后续应用插件装配和隔离查询提供基础数据轴。

## 仓库结构

- docs/DEVELOPER_GUIDE.md：开发者手册。
- docs/USER_GUIDE.md：用户手册。
- docs/DIRECTORY_REFERENCE.md：项目完整目录（2026/4/29 更新，含 Phase 4 质量基线）。
- apps/web：Web 工作台，当前已提供总览、任务、节点、协作、资产、训练、Prompt、评测、观测页面。
- services/core-api：控制面 API，当前已暴露 tasks、nodes、collaboration、runtime、memory、assets、training、prompting、evaluations、observability。
- services/agent-runtime：运行时执行入口，负责主 Agent 启动、pause/resume、PromptCompiler 接线与模型执行闭环。
- services/module-host：模块发现、装配、注册与健康管理。
- services/worker：异步执行活动与任务消费入口。
- modules：正式模块实现。
- adapters：模型与媒体处理适配器。
- packages/python-sdk：领域对象、ORM、仓储层、运行时、PromptCompiler、评测与运维工具。
- packages/frontend-sdk：前端共享类型。
- docs：PRD、ADR、协议与数据规格。
- evaluation：正式评测样本、suite 定义与基线数据。
- infra：本地依赖基础设施与观测组件。

## 开源协作

- 本仓库采用 AGPL-3.0 完整开源，默认认为所有已提交的源码、文档、样例和评测材料都可以公开分发；具体边界见 `docs/OPEN_SOURCE_BOUNDARY.md`。
- 参与贡献前先阅读 `CONTRIBUTING.md`、`GOVERNANCE.md`、`SECURITY.md` 和 `CODE_OF_CONDUCT.md`。
- 涉及架构边界、公共接口、协议契约、模块生命周期或破坏性变化的重大设计调整，必须先走 `docs/rfcs/README.md` 定义的 RFC 流程。
- 英文入口文档见 `README.en.md`、`CONTRIBUTING.en.md`、`GOVERNANCE.en.md`、`SECURITY.en.md`、`CODE_OF_CONDUCT.en.md`、`docs/OPEN_SOURCE_BOUNDARY.en.md` 与 `docs/rfcs/README.en.md`。

## 本地开发

### 安装依赖

```powershell
uv sync
corepack pnpm install
```

如需本地联调，可基于 `.env.example` 准备本地 `.env`，并至少注入一个可用的模型提供方 API key；不要把真实 key 提交到仓库。

### 启动服务

```powershell
uv run yggdrasil-core-api
uv run yggdrasil-agent-runtime
uv run yggdrasil-module-host
uv run yggdrasil-worker
corepack pnpm web:dev
```

### 本地协调后端

- 默认使用 `YGGDRASIL_COORDINATION_BACKEND=auto`，优先尝试本地 Redis，不可达时短时间熔断并回退到进程内 coordination。
- 如果通过 `corepack pnpm infra:up` 启动本地依赖，Redis 由 `infra/docker-compose.yml` 中的 `redis` 服务提供，默认监听 `127.0.0.1:6379`。
- 当前 Windows 本机也已通过 `winget install Redis.Redis` 安装 Redis on Windows，默认安装目录为 `C:\Program Files\Redis`，可执行文件包括 `redis-server.exe` 和 `redis-cli.exe`。
- 当前已验证本机 `127.0.0.1:6379` 可达，`redis-cli ping` 返回 `PONG`。
- pytest 和隔离评测环境默认切到 `YGGDRASIL_COORDINATION_BACKEND=memory`，避免把不可达 Redis 的失败等待计入本地运行时。

### 运行时热路径优化

- 应用目录、prompt registry、tool descriptors 现在都带有进程级 warm cache，减少单次运行里的重复清单扫描、hook 收集和插件加载。
- MCP bridge 的 snapshot 刷新已从请求热路径移出：配置变更和显式同步会刷新 snapshot，工具查找 miss 不再触发全量 refresh。
- builtin MCP server 默认使用 keep-alive session，避免每次请求都重新拉起 `workspace-read/edit/search/execute/python` 子进程。

### 运行时审计级别

- `packages/python-sdk/src/yggdrasil_sdk/llm_runtime.py` 现在支持 `strict`、`default`、`lean` 三档审计级别，可通过运行时请求体里的 `auditLevel` 或环境变量 `YGGDRASIL_RUNTIME_AUDIT_LEVEL` 指定。
- `strict` 保留阶段 4 之前的全量写盘行为：完整 prompt messages、完整 request transcript、完整 tool executions 和 `rawResponse` 都会同步写入工件。
- `default` 现在是推荐默认值：保留关键元数据、message digests、tool/round 摘要和 timings，去掉热路径里最重的全量 transcript 与 `rawResponse`。
- `lean` 在 `default` 基础上进一步压缩为更轻的 request/response/compiled prompt 工件，适合本地 benchmark、开发联调和无须全量审计的运行。
- `YGGDRASIL_EVAL_PRESERVE_SANDBOX=1` 会把 evaluation suite 的隔离沙箱保留到 `.yggdrasil/state/evaluation-sandboxes/`，便于事后检查 `evaluation.db`、`llm/requests`、`llm/responses`、`prompt/compiled` 和 observability 工件；与 `YGGDRASIL_RUNTIME_AUDIT_LEVEL=strict` 组合时最适合做窗口级回放与记忆设计分析。
- 当前最小测量下，`strict -> default` 将 request 工件从 `21081 B` 降到 `11435 B`，response 工件从 `1970.8 B` 降到 `1021.2 B`，compiled prompt 工件从 `13532 B` 降到 `9309 B`；`lean` 会继续把 response 工件压到约 `891.4 B`。

### 基础验证

- 运行 `uv run pytest -q` 前请先确保本地 OTel Collector 已启动（例如执行 `corepack pnpm infra:up`），避免 observability 导出端点不可达导致额外等待。

```powershell
uv run pytest -q
corepack pnpm web:typecheck
corepack pnpm web:lint
corepack pnpm web:build
```

### 评测命令

```powershell
corepack pnpm eval:list
corepack pnpm eval:regression
corepack pnpm eval:m8:benchmark
corepack pnpm eval:m8:live
corepack pnpm eval:m9:control-plane
corepack pnpm eval:m9:acceptance
corepack pnpm eval:g2:regression
corepack pnpm eval:g4:multiscene
corepack pnpm eval:g4:provider-matrix
corepack pnpm eval:g4:provider-matrix:longform
corepack pnpm eval:g4:web-research:default
corepack pnpm eval:g4:web-research:work-tree-long
corepack pnpm eval:g4:real-task-unrelated:dual-live
corepack pnpm eval:g4:work-tree-debug
```

补充说明：`corepack pnpm eval:m8:live` 不是离线假跑，它会按 live suite 中的 `requestedProvider/requestedModel` 直接检查真实 provider 候选。当前默认请求 `longcat/LongCat-2.0-Preview`，并保留 `longcat/LongCat-Flash-Lite` 作为对照 case；如果未配置 `YGGDRASIL_LLM_API_KEY_LONGCAT` 或 `LONGCAT_API_KEY`，suite 会在调用前失败，并且不会产生任何供应商侧调用记录。

`corepack pnpm eval:g4:multiscene` 是 Gate 4 官方离线门禁，覆盖 coding / research / writing 三场景的快任务合同、跨会话恢复合同、pause/resume 恢复与场景切换隔离。`corepack pnpm eval:g4:provider-matrix` 是 Gate 4 官方 live provider matrix，覆盖同一组三场景在 `deepseek_direct / deepseek-v4-pro` 与 `longcat / LongCat-2.0-Preview` 上的正式复跑。

`corepack pnpm eval:g4:provider-matrix:longform` 是单任务长样本入口：它暂时只聚焦一个更长的 coding-greenfield 任务，并在 `deepseek_direct / deepseek-v4-pro` 与 `longcat / LongCat-2.0-Preview` 上复跑，用于观察更高任务长度下的首响、完成质量与返工口径。

`corepack pnpm eval:g4:web-research:default` 是当前默认真实任务入口：它固定网络检索、多源对比与矛盾处理合同，要求主报告后追加 formal delivery footer（`## 结果` / `## 证据` / `## 风险` / `## 已知问题`），并通过 `strict` 审计记录窗口续跑与证据链路。

`corepack pnpm eval:g4:web-research:work-tree-long` 是 web research 的长任务工作树入口：固定 LongCat live 网络搜索，重点观察多窗口 continuation 与工作树连续性。

`corepack pnpm eval:g4:real-task-unrelated:dual-live` 是“先用与本项目完全无关的任务看实际执行过程”的最小 live 入口：它固定为同一个外部 incident RCA 题目，分别在 `longcat / LongCat-2.0-Preview` 与 `deepseek_direct / deepseek-v4-flash` 上各跑一遍，并要求主报告后追加 formal delivery footer（`## 结果` / `## 证据` / `## 风险` / `## 已知问题`），用于直接观察世界树 agent 在 unrelated real-task 下的实际推进方式。

`corepack pnpm eval:g4:work-tree-debug` 是当前仓库的真实任务工作树调试入口：它不再把 provider 锁定当主目标，而是预置显式嵌套 `takeoverProtocol`，让真实任务从子节点起步，重点检查 `currentNodeId`、`WorkContextStack`、叶子失败上浮、窗口 continuation 和 `awaiting-approval` 语义是否符合工作树 v0.2 设想。

如果要在 live suite 或 `pilot-live` 中使用付费 provider（例如 `deepseek_direct / deepseek-v4-pro`），除了配置 API key 之外，还必须显式设置 `YGGDRASIL_ALLOW_PAID_MODELS=1`；否则 paid candidate 不会进入 runtime catalog。

### 运维命令

```powershell
corepack pnpm infra:up
corepack pnpm infra:down
corepack pnpm infra:smoke
corepack pnpm ops:backup
corepack pnpm ops:restore
corepack pnpm real-user:prepare
corepack pnpm real-user:scorecard --csv .\evaluation\fixtures\real-user-validation\scorecard-2026-05-15-g2-complete.csv
```

### 真实用户试跑准备

`corepack pnpm real-user:prepare` 会在仓库外同级目录生成一个专用试跑沙箱，包含工作区快照、隔离 `.yggdrasil` 状态目录、冻结任务材料副本与激活脚本，避免内部试跑回写当前工程仓库。

命令行入口与服务启动入口现在会自动加载仓库根 `.env`。本地开发若使用 `YGGDRASIL_STATE_ROOT`，它应指向状态根目录本身（例如 `.yggdrasil`），而不是 `.yggdrasil/state`，否则运行时会再追加一层 `state/`。

### 真实用户试跑前提

- 当前 Windows 主机若默认 `9000/9001` 被占用，启动 infra 前先覆盖 MinIO 端口：`YGGDRASIL_MINIO_API_PORT=19000`、`YGGDRASIL_MINIO_CONSOLE_PORT=19001`。
- 真实试跑必须先执行 `corepack pnpm real-user:prepare`，再进入生成的专用沙箱并使用激活脚本；不要直接对当前工程仓库运行试跑任务。
- 试跑环境至少要保证 `YGGDRASIL_GIT_REPO_PATH`、`YGGDRASIL_MCP_PROJECT_WORKSPACE`、`YGGDRASIL_STATE_ROOT` 都指向沙箱。仅切换状态目录并不够，内置 MCP 仍可能回写真实仓库。
- 首轮内部试跑的交付物至少包括评分表、录屏、trace 与任务工件目录。

## 规格入口

- docs/PRD-v0.1.md
- docs/protocols/README.md
- docs/specs/README.md
- docs/specs/agent-runtime-protocol-v0.2.md

## 当前重点

当前阶段的重点已经切换为“在维持 Gate 4 正式基线不回退的前提下，把工作树 v0.2 单路径运行语义落到运行时与评测链路”。

### 阶段状态（2026-05-16）

- Gate 1 已闭合：在 `deepseek_direct` / `deepseek-v4-pro` 下完成 `YGG-CI-01`、`YGG-CG-01`、`YGG-CG-03` 官方复跑，3 张任务卡全部验收通过。
- Gate 2 已闭合：完成 1 轮全量官方复跑 + 2 轮稳定性复跑；`YGG-CG-01` / `YGG-CG-03` 连续 3 轮全部通过，人工接管中位数 0，用户澄清回合中位数 0，恢复成功率 100%。
- Gate 3 已闭合：首 token 观测、work tree 正式对象、post-invocation budget hard fail、`execute_server` 默认拒绝网络命令、worker retry/requeue 与 paid-provider live batch 已全部落下正式证据。
- Gate 4 已闭合：few-shot 执行链、官方三场景资产收口、`evalsuite_g4_multiscene`、`evalsuite_g4_provider_matrix`、Prompt 控制面 few-shot 显示与手动 release gate 已完成闭环。
- 运行时已进入工作树 v0.2 收敛阶段：默认语义为子节点完成/失败后回到父节点编排，不再把窗口重启作为常态推进路径。
- 真实任务主入口已切到 web research 合同：默认入口为 `evalsuite_g4_real_task_web_research_default`（`eval:g4:web-research:default`），并保留 `evalsuite_g4_web_research_work_tree_long` 作为长任务工作树续跑观测入口。
- 当前正式闭环证据应分开看：Gate 2/3/4 基线闭环参考见 `docs/research/g2-closeout-2026-05-15.md`、`docs/research/g3-closeout-2026-05-15.md`、`docs/research/g4-closeout-2026-05-15.md`；真实任务默认入口的最新修正结论见 `docs/development/G4_WEB_RESEARCH_DEFAULT_FAILURE_AUDIT_2026_05_27.md`。

下一步更值得投入的是：

- 先修正恢复态 prompt contract、记忆树/工作树恢复语义，以及“release brief 已完成、parity judgment 已给出”的强验收口径。
- 在上述修正完成后，再在 DeepSeek 上补齐同一条真实任务的 `64k` vs `128k` 对照，确认多 provider 下的 parity 结论是否稳定。
- 基于 stress + real-task 两条 live 证据，重新冻结 `restartCount`、`cumulativeWindowSpanTokens`、`restartSuccessRate0_1`、`goalCompletionParity0_1`、`deliveryEquivalence0_1` 与 `qualityDeltaToLongWindow0_100` 的正式门槛。
- 在上述主线完成前，只维持必要的 G4 provider matrix 样本补录与最小非阻塞技术债清理，避免被次要事项分散。
- 相关研究入口见 `docs/research/pseudo-infinite-context-window-roadmap-2026-05-16.md`、`docs/research/g4-long-task-window-restart-baseline-2026-05-15.md` 与 `docs/development/G4_WEB_RESEARCH_DEFAULT_FAILURE_AUDIT_2026_05_27.md`。


