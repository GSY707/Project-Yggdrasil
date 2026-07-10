# Architecture Overview

> 项目设计哲学唯一主文档：[世界树计划完整设计哲学](design-philosophy-and-cognitive-principles.md)。本页只说明工程架构；若两者冲突，以主哲学文档为准。

## System Purpose

Project Yggdrasil 是一个长期任务执行系统，目标是在统一控制面下完成任务执行、记忆管理、协作评审、评测闭环与可观测性采集。

系统由 Python 服务基座、模块插件层、适配器层、评测层和 Web 工作台构成。

## Main Runtime Flow

1. 客户端（Web 或脚本）通过 Core API 创建或驱动任务。
2. Core API 写入持久化并派发运行请求。
3. Agent Runtime 调用 `runtime_kernel` 执行主循环。
4. Worker 从协调队列消费活动，执行主 Agent 或子 Agent 工作项。
5. Runtime 调用模块插件（记忆、剪枝、协作等）并通过 Adapter 触发模型调用。
6. 结果、快照、审计工件和评测指标回写持久化层。
7. Core API 与 Web 消费同一数据面进行展示与操作。

## Major Components

- Control Plane：`services/core-api`
- Runtime Engine：`services/agent-runtime` + `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel`
- Worker Executor：`services/worker`
- Module Host：`services/module-host`
- Shared SDK：`packages/python-sdk`、`packages/frontend-sdk`、`packages/contracts`
- Feature Modules：`modules/*`
- Provider Adapters：`adapters/*`
- Scenario Apps：`applications/*`
- Frontend Console：`apps/web`
- Evaluation System：`evaluation/*` + `packages/python-sdk/src/yggdrasil_sdk/evaluation_runtime`

## Dependency Direction

推荐依赖方向：

- Web -> Core API
- Core API -> Python SDK（contracts、persistence、runtime facade）
- Agent Runtime / Worker -> runtime_kernel + modules + adapters
- Modules -> Python SDK contracts/hooks/persistence
- Adapters -> provider SDK / HTTP API
- Evaluation -> Python SDK runtime + suites/fixtures

禁止反向：

- Python SDK 基础层反向依赖 Web。
- Adapter 反向依赖具体场景应用。
- 测试辅助代码进入生产路径。

详细规则见 [Module Boundaries](module-boundaries.md)。

## High-Risk Areas

- `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop.py`：任务主循环与窗口重启核心路径。
- `packages/python-sdk/src/yggdrasil_sdk/llm_runtime.py`：模型调用和重试策略。
- `services/worker/src/yggdrasil_worker/registry.py`：活动分发和队列消费。
- `modules/text-memory/src/yggdrasil_text_memory/plugin.py`：记忆写入、检索、边关系构建。
- `packages/python-sdk/src/yggdrasil_sdk/evaluation_runtime/suite_cases_g4.py`：Gate 4 关键评测合同。

## Known Constraints

- 本仓库同时包含 Python 与 Node 构建链，验证时需要分别执行。
- live provider 与 paid provider 受环境变量门控，默认不应假设可用。
- `.yggdrasil/` 是运行期状态目录，不应直接作为源代码语义依据。
- 场景应用的行为受 `applications/*/yggdrasil.app.yaml` 与 prompt profile 双重控制。
