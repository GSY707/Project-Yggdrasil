# Architecture Data Flow

## End-to-End Flow

1. 请求进入：Web 页面或 CLI 发起任务、记忆、评测、协作请求。
2. 控制面受理：Core API 路由层校验输入并委派到 service 层。
3. 状态持久化：service 调用 SDK 仓储层写入任务、节点、工件元数据。
4. 运行调度：Runtime/Worker 通过协调后端（Redis 或 memory）消费工作项。
5. 执行编排：`runtime_kernel` 聚合上下文、触发模块 hook、调用 LLM。
6. 模块处理：text-memory / pruning / shared-memory 等模块产出结构化结果。
7. 结果回写：快照、消息、指标、工件与评测结果入库。
8. 展示消费：Core API 提供统一查询接口，Web 工作台直接读取。

## Data Planes

- 控制面数据：任务状态、节点结构、模块清单、应用清单。
- 执行面数据：prompt 编译结果、模型请求响应、工具调用回执。
- 评测面数据：suite 配置、case 结果、评分指标、基线对照。
- 运维面数据：trace、日志、备份快照、沙箱材料。

## Key Storage Touchpoints

- Alembic + SQLAlchemy 持久化层：`migrations/`、`packages/python-sdk/src/yggdrasil_sdk/persistence/`
- 运行状态目录：`.yggdrasil/`（非源码目录）
- 评测材料：`evaluation/fixtures/`、`evaluation/suites/`
- 文档与协议：`docs/specs/`、`docs/protocols/`

## Event and Queue Flow

- 主执行队列名由 `runtime_kernel` 暴露（`AGENT_RUNTIME_QUEUE`）。
- Worker 在 `registry.py` 中发现活动并分发执行。
- Subagent 分支通过协作运行时回写结果与 PR 相关状态。

## Failure Handling

- 工具调用异常会以 tool result 结构回喂模型，而非静默吞错。
- runtime 支持 safe shutdown、pending tool calls 快照与 pause/resume。
- 协调后端不可用时可回退到内存后端（取决于环境策略）。
