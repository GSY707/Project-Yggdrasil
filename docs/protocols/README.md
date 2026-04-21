# 协议索引

- 目录状态：Draft
- 更新时间：2026-04-16
- 关联文档：
  - [PRD v0.1](../PRD-v0.1.md)
  - [Agent 运行时协议 v0.1](../specs/agent-runtime-protocol-v0.1.md)

## 说明

这里定义的是系统协议，而不是提示词草稿。

- 提示词负责告诉模型“如何思考、如何表达、如何遵守边界”。
- 协议负责规定“系统何时触发、如何持久化、如何恢复、如何扩展、如何通信”。

建树算法、启动流程、根节点挂载、困难任务上下文整理、任务暂停都不应只放在提示词里，它们必须在运行时协议中有正式定义。

## 文档列表

- [yggdrasil.app.yaml 协议 v0.1](yggdrasil-application-manifest-v0.1.md)
- [yggdrasil.module.yaml 协议 v0.1](yggdrasil-module-manifest-v0.1.md)
- [模块生命周期协议 v0.1](module-lifecycle-v0.1.md)
- [Hook 点协议 v0.1](hook-contracts-v0.1.md)
- [事件契约协议 v0.1](event-contracts-v0.1.md)