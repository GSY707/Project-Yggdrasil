# Project Yggdrasil

世界树计划的正式工程仓库。

当前仓库已经不再是“骨架 + 占位”的早期状态，而是一个可运行、可评测、可恢复、可扩展的长期任务系统：

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

## 本地开发

### 安装依赖

```powershell
uv sync
corepack pnpm install
```

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
- 当前最小测量下，`strict -> default` 将 request 工件从 `21081 B` 降到 `11435 B`，response 工件从 `1970.8 B` 降到 `1021.2 B`，compiled prompt 工件从 `13532 B` 降到 `9309 B`；`lean` 会继续把 response 工件压到约 `891.4 B`。

### 基础验证

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
```

### 运维命令

```powershell
corepack pnpm infra:up
corepack pnpm infra:down
corepack pnpm infra:smoke
corepack pnpm ops:backup
corepack pnpm ops:restore
corepack pnpm real-user:prepare
```

### 真实用户试跑准备

`corepack pnpm real-user:prepare` 会在仓库外同级目录生成一个专用试跑沙箱，包含工作区快照、隔离 `.yggdrasil` 状态目录、冻结任务材料副本与激活脚本，避免内部试跑回写当前工程仓库。

## 规格入口

- docs/PRD-v0.1.md
- docs/protocols/README.md
- docs/specs/README.md
- docs/specs/agent-runtime-protocol-v0.1.md

## 当前重点

当前阶段的重点已经从“补齐第二阶段模块能力”切换为“真实用户验证执行与隔离试跑收口”。

下一步更值得投入的是：

- 先用 `real-user:prepare` 固化 2 到 3 次内部试跑所需的专用目录、材料副本和隔离状态根。
- 优先执行边界更清晰、工具集合更窄的内部试跑任务，减少真实用户验证前的噪音变量。
- 补 Core API HTTP 关键路径的实测 P50 / P95，并回写 `docs/QUALITY_BASELINE.md`。
- 补首 token / 首次有效输出级别的首响观测，支撑真实用户体验判断。