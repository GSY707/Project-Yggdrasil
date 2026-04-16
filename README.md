# Project Yggdrasil

世界树计划的第一版仓库骨架。

本仓库按已经冻结的规格搭建，目标是让后续模块开发优先依赖文档规格、共享 SDK 和正式协议，而不是相互读取内部实现。

## 结构

- apps/web：Web 控制台占位实现。
- services/core-api：领域 API 骨架。
- services/agent-runtime：Agent 运行时骨架。
- services/module-host：模块发现、装载与健康检查骨架。
- services/worker：后台任务执行骨架。
- modules：第一版核心模块占位实现。
- adapters：外部依赖适配层占位实现。
- packages/contracts：正式 contracts 与 schema 目录。
- packages/frontend-sdk：前端扩展类型定义。
- packages/python-sdk：Python 共享类型和模块接口。
- infra：本地依赖基础设施。

## 规格入口

- docs/PRD-v0.1.md
- docs/protocols/README.md
- docs/specs/README.md

## 本地开发

前端工作区使用 pnpm 管理，Python 工作区使用 uv 管理。

### 前端

```powershell
pnpm install
pnpm web:dev
```

### Python

```powershell
uv sync
uv run yggdrasil-core-api
uv run yggdrasil-module-host
```

### 基础设施

```powershell
docker compose -f infra/docker-compose.yml up -d
```

## 说明

当前代码以仓库骨架和空实现为主，重点是稳定目录边界、依赖边界和开发入口，而不是完成业务逻辑。