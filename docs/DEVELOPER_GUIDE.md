# 世界树计划 · 开发指南

> 面向参与本项目开发的工程师。涵盖环境搭建、架构理解、开发规范、测试与 CI 门禁。

---

## 目录

1. [系统架构概览](#1-系统架构概览)
2. [技术栈](#2-技术栈)
3. [本地环境搭建](#3-本地环境搭建)
4. [项目初始化](#4-项目初始化)
5. [启动服务](#5-启动服务)
6. [开发工作流](#6-开发工作流)
7. [模块开发规范](#7-模块开发规范)
8. [应用插件开发规范](#8-应用插件开发规范)
9. [数据库迁移](#9-数据库迁移)
10. [测试体系](#10-测试体系)
11. [评测体系](#11-评测体系)
12. [CI 门禁](#12-ci-门禁)
13. [可观测性](#13-可观测性)
14. [常见问题](#14-常见问题)

---

## 1. 系统架构概览

世界树计划采用 **Kernel / Module / Adapter** 三层架构：

```
┌─────────────────────────────────────────────────────────────────┐
│                        Web 工作台 (Next.js)                      │
└───────────────────────────────┬─────────────────────────────────┘
                                │ HTTP
┌───────────────────────────────▼─────────────────────────────────┐
│                      Core API  (FastAPI :8000)                   │
│  tasks / nodes / memory / assets / prompting / evaluations ...   │
└───┬──────────────┬──────────────┬──────────────┬────────────────┘
    │              │              │              │
    ▼              ▼              ▼              ▼
Agent Runtime  Module Host     Worker        python-sdk
(执行引擎)    (模块宿主)    (异步任务)     (共享内核)
    │              │
    └──────┬───────┘
           ▼
      基础设施层
 PostgreSQL / Redis / NATS
 MinIO / Temporal / OTel
```

### 核心概念

| 概念 | 说明 |
|------|------|
| **记忆树 (Memory Tree)** | 以分层节点组织的长期记忆图谱，是 Agent 的持久化状态载体 |
| **任务 (Task)** | 一次完整的 Agent 执行单元，具有状态机和可恢复性 |
| **模块 (Module)** | 通过 Hook 协议扩展核心能力的可插拔单元 |
| **应用 (Application)** | 面向特定场景的 Agent 配置与提示组合 |
| **PromptCompiler** | 将模板、变量、记忆节点编译为最终模型输入的组件 |
| **Outbox** | 基于 NATS JetStream 的事件总线，各服务间解耦通信 |

---

## 2. 技术栈

### 后端

| 技术 | 版本 | 用途 |
|------|------|------|
| Python | 3.12+ | 主要语言 |
| FastAPI | ≥0.115 | HTTP API 框架 |
| SQLAlchemy | ≥2.0 | ORM |
| Alembic | ≥1.14 | 数据库迁移 |
| Pydantic | ≥2.6 | 数据验证与序列化 |
| UV | latest | Python 包管理与工作区 |

### 前端

| 技术 | 版本 | 用途 |
|------|------|------|
| TypeScript | 5.8 | 主要语言 |
| React | 19 | UI 框架 |
| Next.js | 15 | 应用框架 |
| pnpm | latest | 包管理 |

### 基础设施

| 服务 | 版本 | 用途 |
|------|------|------|
| PostgreSQL | 17 + pgvector | 主数据库 + 向量存储 |
| Redis | 7.4 | 缓存与会话 |
| NATS | 2.10 (JetStream) | 事件总线 |
| MinIO | latest | 对象存储 (S3 兼容) |
| Temporal | 1.26.2 | 工作流引擎 |
| Jaeger | 1.63 | 分布式追踪 |
| OpenTelemetry Collector | 0.123 | 遥测数据汇聚 |
| Langfuse | latest | LLM 观测 |

---

## 3. 本地环境搭建

### 3.1 前置依赖

- **Docker Desktop**（用于启动基础设施）
- **Python 3.12+**
- **UV**（Python 工作区管理）：`pip install uv` 或参考 [uv 官方文档](https://docs.astral.sh/uv/)
- **Node.js 20+** + **Corepack**（已内置于 Node.js 16.13+）
- **pnpm**：`corepack enable && corepack prepare pnpm@latest --activate`

### 3.2 环境变量

项目根目录已提供 `.env.example`。本地联调时可基于该文件准备 `.env`，最低配置如下：

```bash
# 持久化与服务发现
YGGDRASIL_DATABASE_URL=sqlite+pysqlite:///./.yggdrasil/local-dev.db
YGGDRASIL_AUTO_CREATE_SCHEMA=1
YGGDRASIL_REDIS_URL=redis://127.0.0.1:6379/0
YGGDRASIL_NATS_URL=nats://127.0.0.1:4222
YGGDRASIL_NATS_STREAM=YGGDRASIL
YGGDRASIL_NATS_SUBJECT_PREFIX=yggdrasil.events
YGGDRASIL_STATE_ROOT=.yggdrasil/state
YGGDRASIL_CORE_API_BASE_URL=http://127.0.0.1:8000
YGGDRASIL_GIT_REPO_PATH=.
YGGDRASIL_MCP_PROJECT_WORKSPACE=.

# OpenTelemetry（可选，联调建议开启）
YGGDRASIL_OTEL_EXPORTER_OTLP_ENDPOINT=http://127.0.0.1:4318

# Langfuse（可选）
LANGFUSE_PUBLIC_KEY=
LANGFUSE_SECRET_KEY=
LANGFUSE_BASE_URL=http://127.0.0.1:3100

# 可选端口覆盖（Windows 本机冲突时常用）
YGGDRASIL_MINIO_API_PORT=9000
YGGDRASIL_MINIO_CONSOLE_PORT=9001

# 运行时建议默认值
YGGDRASIL_RUNTIME_AUDIT_LEVEL=default
YGGDRASIL_COORDINATION_BACKEND=auto

# LLM 模型密钥（至少配置一个）
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
LONGCAT_API_KEY=
OPENROUTER_API_KEY=
DEEPSEEK_API_KEY=
VECTORENGINE_API_KEY=
```

LLM 凭据只通过环境变量注入，运行时代码不会读取仓库内的 `LLM.txt`。

推荐至少设置以下变量之一：

```bash
LONGCAT_API_KEY=YOUR_LONGCAT_KEY
OPENROUTER_API_KEY=YOUR_OPENROUTER_KEY
DEEPSEEK_API_KEY=YOUR_DEEPSEEK_KEY
VECTORENGINE_API_KEY=YOUR_VECTORENGINE_KEY
```

Windows PowerShell 示例：

```powershell
$env:DEEPSEEK_API_KEY = "YOUR_DEEPSEEK_KEY"
$env:YGGDRASIL_ALLOW_PAID_MODELS = "1"
```

CI 或长期开发环境请使用各自的 secret manager / 用户级环境变量，不要把真实 key 写入仓库、评测沙箱或测试材料。

### 3.3 端口分配

| 服务 | 默认端口 |
|------|---------|
| Core API | 8000 |
| Agent Runtime | 8001 |
| Module Host | 8002 |
| Web 工作台 | 3000 |
| PostgreSQL | 5432 |
| Redis | 6379 |
| NATS | 4222 |
| MinIO API | 9000 |
| MinIO Console | 9001 |
| Temporal UI | 8088 |
| Jaeger UI | 16686 |
| OTel Collector HTTP | 4318 |
| Langfuse UI | 3100 |

如有端口冲突，可通过环境变量覆盖，例如：

```bash
YGGDRASIL_MINIO_CONSOLE_PORT=19001
YGGDRASIL_TEMPORAL_UI_PORT=18088
```

---

## 4. 项目初始化

```bash
# 1. 克隆仓库
git clone <repo-url>
cd 世界树计划

# 2. 安装 Python 依赖（所有工作区）
uv sync

# 3. 安装 Node.js 依赖
corepack pnpm install

# 4. 启动基础设施
corepack pnpm infra:up

# 5. 等待基础设施就绪后运行数据库迁移
uv run alembic upgrade head

# 6. （可选）启动 Langfuse 本地观测
corepack pnpm infra:langfuse:up
```

### 验证基础设施

```bash
corepack pnpm infra:smoke
```

### 4.1 真实用户试跑前提

- 真实用户验证或内部试跑前，必须先执行 `corepack pnpm real-user:prepare`。该命令会在仓库外同级目录生成隔离工作区、冻结材料副本、独立 `.yggdrasil` 状态根与激活脚本。
- 当前 Windows 主机若默认 `9000/9001` 被占用，请先覆盖 MinIO 宿主端口：

```powershell
$env:YGGDRASIL_MINIO_API_PORT = "19000"
$env:YGGDRASIL_MINIO_CONSOLE_PORT = "19001"
corepack pnpm infra:up
corepack pnpm infra:smoke
```

- 进入试跑环境时优先使用 `real-user:prepare` 生成的激活脚本；至少要确保 `YGGDRASIL_GIT_REPO_PATH`、`YGGDRASIL_MCP_PROJECT_WORKSPACE`、`YGGDRASIL_STATE_ROOT` 都指向沙箱。仅修改 `YGGDRASIL_STATE_ROOT` 不足以阻止内置 MCP 回写真实仓库。
- 首轮试跑提交物至少包括评分表、录屏、trace 和任务工件目录。

---

## 5. 启动服务

建议开 4 个终端分别运行各服务：

```bash
# 终端 1：控制面 API
uv run yggdrasil-core-api

# 终端 2：Agent 执行引擎
uv run yggdrasil-agent-runtime

# 终端 3：模块宿主
uv run yggdrasil-module-host

# 终端 4：异步任务 Worker
uv run yggdrasil-worker

# 终端 5：Web 工作台
corepack pnpm web:dev
```

启动后访问 `http://localhost:3000` 进入工作台。

---

## 6. 开发工作流

外部贡献者进入实现前，先阅读根目录的 `CONTRIBUTING.md`、`GOVERNANCE.md`、`SECURITY.md` 与 `CODE_OF_CONDUCT.md`。如果改动会影响架构边界、协议、公共接口、模块生命周期或破坏兼容性，先按 `docs/rfcs/README.md` 提交 RFC。

### 6.1 分支策略

- `main`：主干，需通过所有 CI 门禁
- `feat/<name>`：功能开发分支
- `fix/<name>`：缺陷修复分支

### 6.2 Python 代码规范

本项目使用 **Ruff** 进行代码检查与格式化，配置见根 `pyproject.toml`。

```bash
# 格式化
uv run ruff format .

# 检查
uv run ruff check .

# 自动修复
uv run ruff check --fix .
```

### 6.3 TypeScript 代码规范

```bash
# 类型检查
corepack pnpm web:typecheck

# Lint
corepack pnpm web:lint

# 构建验证
corepack pnpm web:build
```

### 6.4 提交前检查清单

- [ ] `uv run pytest -q` 全部通过
- [ ] `corepack pnpm web:typecheck` 无错误
- [ ] `corepack pnpm web:lint` 无错误
- [ ] `corepack pnpm web:build` 构建成功
- [ ] 如有数据库变更：`uv run alembic check` 通过
- [ ] 如有基础设施变更：`corepack pnpm infra:smoke` 通过
- [ ] 如修改公共接口、协议契约、模块生命周期或架构边界：附 RFC 链接或说明为何不需要 RFC

---

## 7. 模块开发规范

模块是世界树的核心扩展机制，每个模块是一个独立的 Python 包，位于 `/modules/<module-name>/`。

### 7.1 目录结构

```
modules/my-module/
├── pyproject.toml              # 包配置，依赖声明
├── yggdrasil.module.yaml       # 模块清单（必须）
└── src/
    └── my_module/
        ├── __init__.py
        └── plugin.py           # 主模块类
```

### 7.2 模块清单 (yggdrasil.module.yaml)

```yaml
name: my-module
version: 0.1.0
description: "模块功能描述"

# 声明模块注册的 Hook 处理器
hooks:
  - event: memory.node.after_write
    handler: my_module.plugin:on_node_written
  - event: task.before_execute
    handler: my_module.plugin:on_task_start

# 声明模块所需权限
permissions:
  - memory.read
  - memory.write

# 声明模块能力标签
capabilities:
  - memory-enhancement
```

### 7.3 模块主类

```python
# src/my_module/plugin.py
from yggdrasil_sdk.module import YggdrasilModule, HookContext

class MyModule(YggdrasilModule):
    async def on_start(self) -> None:
        """模块启动时调用"""
        pass

    async def on_stop(self) -> None:
        """模块停止时调用"""
        pass

async def on_node_written(ctx: HookContext) -> None:
    """Hook 处理器，接收记忆节点写入事件"""
    node = ctx.payload
    # 处理逻辑...
```

### 7.4 Hook 事件列表

主要 Hook 事件（完整列表见 `docs/protocols/hook-contracts-v0.1.md`）：

| 事件 | 触发时机 |
|------|---------|
| `task.before_execute` | 任务开始执行前 |
| `task.after_execute` | 任务执行完成后 |
| `memory.node.after_write` | 记忆节点写入后 |
| `memory.node.before_retrieve` | 记忆检索前 |
| `agent.before_llm_call` | LLM 调用前 |
| `agent.after_llm_call` | LLM 调用后 |

### 7.5 模块注意事项

- **禁止**模块直接读写其他模块的内部实现，必须通过 SDK 协议接口。
- **禁止**模块绕过 Shared SDK 和正式协议。
- 模块应具有幂等性，同一事件多次触发不应产生副作用。
- 模块启动失败不应导致整个 Module Host 崩溃，应捕获异常并上报健康状态。

---

## 8. 应用插件开发规范

应用插件位于 `/applications/<app-name>/`，负责特定场景的 Agent 配置。

### 8.1 目录结构

```
applications/my-app/
├── yggdrasil.app.yaml          # 应用清单
├── prompts/                    # 场景专用提示模板
│   ├── system.md
│   └── seed.md
└── modules/                    # 应用绑定的模块列表（可选）
```

### 8.2 应用清单 (yggdrasil.app.yaml)

```yaml
name: my-app
version: 0.1.0
description: "应用场景描述"
display_name: "我的应用"

# 绑定模块
modules:
  - text-memory
  - context-pruning
  - my-module

# 模型路由配置
model_routing:
  default: anthropic/claude-opus-4-5
  fast: anthropic/claude-haiku-4-5

# 种子上下文
seed_context:
  system_prompt_template: prompts/system.md
  initial_memory_template: prompts/seed.md
```

---

## 9. 数据库迁移

本项目使用 **Alembic** 管理数据库 Schema 版本。

```bash
# 查看当前迁移状态
uv run alembic current

# 应用所有迁移到最新版本
uv run alembic upgrade head

# 回滚一个版本
uv run alembic downgrade -1

# 生成新迁移文件（修改 ORM Model 后执行）
uv run alembic revision --autogenerate -m "描述变更内容"

# 检查迁移是否与模型同步
uv run alembic check
```

### 迁移规范

- 迁移文件命名要清晰描述变更内容，使用英文。
- 每次 PR 如有 Model 变更，必须附带对应迁移文件。
- `alembic check` 必须通过 CI 门禁。
- 禁止在迁移文件中放置业务逻辑。

---

## 10. 测试体系

### 10.1 运行测试

> **重要**：本项目使用 UV 工作区管理 Python 依赖，`yggdrasil_sdk` 等包仅在工作区虚拟环境中可用。
> 必须通过 `uv run pytest` 运行测试，**直接调用 `pytest` 会因找不到模块而报错**。

```bash
# 运行所有测试
uv run pytest -q

# 运行特定测试文件
uv run pytest tests/test_m9_shared_memory.py -v

# 运行带标记的测试
uv run pytest -m "not slow" -q
uv run pytest -m slow -n auto --dist loadfile -q

# 运行并查看覆盖率
uv run pytest --cov=yggdrasil_sdk -q
```

### 10.2 测试分层

| 测试文件 | 范围 |
|---------|------|
| `test_persistence_api.py` | 数据库 ORM 与仓储层 |
| `test_prompting_runtime.py` | PromptCompiler 链路 |
| `test_runtime_and_pruning.py` | 运行时内核与上下文裁剪 |
| `test_m8_runtime.py` | M8 运行时回归 |
| `test_m9_shared_memory.py` 等 5 个 `test_m9_*` 文件 | M9 模块专项测试 |
| `test_m9_acceptance.py` | M9 验收测试 |

### 10.3 编写测试规范

- 集成测试必须连接真实数据库，**禁止** Mock 数据库层（避免 Mock/Prod 差异掩盖问题）。
- 测试应具有自清理能力（使用事务回滚或独立测试数据库）。
- 有副作用、运行时闭环、控制面 API、评测回归这类慢测试用 `@pytest.mark.slow` 标记。
- `slow` 用例默认留给 nightly 跑，并通过 `pytest-xdist` 以 `-n auto --dist loadfile` 并行执行。

---

## 11. 评测体系

评测是验证系统质量的正式机制，区别于单元测试。

```bash
# 列出所有评测 Suite
corepack pnpm eval:list

# 运行回归评测（M4-M6 基线）
corepack pnpm eval:regression

# M8 benchmark（离线基准）
corepack pnpm eval:m8:benchmark

# M8 live（真实 LLM 调用）
corepack pnpm eval:m8:live

# M9 控制面回归
corepack pnpm eval:m9:control-plane
```

评测套件定义位于 `/evaluation/suites/`，样本数据位于 `/evaluation/fixtures/`。

---

## 12. CI 门禁

CI 配置位于 `.github/workflows/ci.yml`，采用分层门禁策略：

### 第一层：基础质量门禁（每次 Push）

- Python 语法检查 (Ruff)
- TypeScript 类型检查
- 单元测试 (`uv run pytest -q`)
- 前端构建验证

### 第二层：集成门禁（PR 合并前）

- 完整测试套件
- Alembic 迁移检查 (`alembic check`)
- Compose smoke 测试
- M9 控制面回归评测

### 第三层：质量趋势（定期）

- M8 benchmark 与 live 评测
- 长期趋势指标记录

---

## 13. 可观测性

### 13.1 分布式追踪 (Jaeger)

访问 `http://localhost:16686` 查看服务间调用链路。

所有服务通过 OpenTelemetry SDK 自动上报 traces，收集器配置见 `infra/otel-collector-config.yaml`。

### 13.2 LLM 观测 (Langfuse)

访问 `http://localhost:3100`，使用默认账号：
- 账号：`admin@example.com`
- 密码：`LangfuseLocal123!`

每次 LLM 调用（包括 prompt 编译、工具调用、模型响应）都会自动记录到 Langfuse。

### 13.3 在代码中添加追踪

```python
from yggdrasil_sdk.observability import get_tracer

tracer = get_tracer(__name__)

async def my_function():
    with tracer.start_as_current_span("my_operation") as span:
        span.set_attribute("key", "value")
        # 业务逻辑...
```

---

## 14. 常见问题

**Q: 启动 Core API 时报 `connection refused` 错误**

A: 先确认基础设施已启动：`corepack pnpm infra:up`，并等待 PostgreSQL 和 Redis 完全就绪（约 10-30 秒）。

**Q: 数据库迁移失败**

A: 检查 `DATABASE_URL` 环境变量是否正确配置，确认 PostgreSQL 已启动且数据库存在。

**Q: 模块没有被 Module Host 加载**

A: 检查 `yggdrasil.module.yaml` 格式是否正确，确认模块包已通过 `uv sync` 安装。

**Q: Alembic check 报告迁移不同步**

A: 运行 `uv run alembic revision --autogenerate -m "sync"` 生成同步迁移文件。

**Q: 前端调用 API 报 CORS 错误**

A: 确认 Core API 的 CORS 配置包含 `http://localhost:3000`，检查 `services/core-api/src/yggdrasil_core_api/app.py`。

**Q: LLM 调用没有出现在 Langfuse**

A: 检查 `LANGFUSE_PUBLIC_KEY`、`LANGFUSE_SECRET_KEY`、`LANGFUSE_BASE_URL` 三个环境变量是否正确配置。
