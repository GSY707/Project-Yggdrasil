# ADR 索引

- 目录状态：Active
- 更新时间：2026-04-16
- 关联文档：
  - [PRD v0.1](../PRD-v0.1.md)
  - [开发 TODO](../../todo.md)

## 状态说明

- Accepted：当前版本已采用，后续实现必须遵守。
- Proposed：已形成正式方案，但仍待冻结。
- Superseded：已被新 ADR 替代。
- Deprecated：不建议继续沿用。

## 已编写 ADR

| 编号 | 标题 | 状态 | 关注点 | 链接 |
| --- | --- | --- | --- | --- |
| ADR-0001 | Kernel + Module + Adapter 分层 | Accepted | 核心架构边界 | [查看](ADR-0001-kernel-module-adapter.md) |
| ADR-0002 | Monorepo 与仓库分层结构 | Accepted | 仓库与目录结构 | [查看](ADR-0002-monorepo-layout.md) |
| ADR-0003 | PostgreSQL 作为主数据存储 | Accepted | 主数据库与索引 | [查看](ADR-0003-postgres-primary-store.md) |
| ADR-0004 | Temporal 作为工作流引擎 | Accepted | 长任务与恢复 | [查看](ADR-0004-temporal-workflow-engine.md) |
| ADR-0005 | LiteLLM + 自定义模型路由 | Accepted | 模型网关与选模 | [查看](ADR-0005-litellm-model-gateway.md) |
| ADR-0006 | 模块扩展机制 | Accepted | 模块 manifest、hook、加载方式 | [查看](ADR-0006-plugin-extension-mechanism.md) |
| ADR-0007 | NATS JetStream + Outbox 事件机制 | Accepted | 事件发布与一致性 | [查看](ADR-0007-nats-outbox-eventing.md) |
| ADR-0008 | 权限系统演进路线 | Accepted | 认证、鉴权、数据面隔离 | [查看](ADR-0008-authz-evolution.md) |
| ADR-0009 | 可观测性与评测体系 | Accepted | 日志、追踪、评测、回归 | [查看](ADR-0009-observability-evaluation.md) |

## ADR 编写顺序与依赖

1. ADR-0001 决定系统分层与边界。
2. ADR-0002 固定仓库与模块落点。
3. ADR-0003 到 ADR-0005 固定核心基础设施。
4. ADR-0006 和 ADR-0007 固定模块化底座与事件机制。
5. ADR-0008 和 ADR-0009 固定治理与评测闭环。

## 下一批候选 ADR

- ADR-0010：多模态资产协议与对象存储目录规范。
- ADR-0011：上下文修剪模块的输入输出契约。
- ADR-0012：训练数据治理与实验发布门禁。
- ADR-0013：前端扩展点与插件加载策略。
- ADR-0014：模块配置存储与密钥管理策略。