# 数据治理清单与本地删除协议 v0.1

日期：2026-06-05

## 1. 状态

本规格定义当前本地数据治理的第一版产品契约：

- 已提供数据资产 manifest：`GET /data-governance/manifest`。
- 已提供删除影响预览：`POST /data-governance/deletion-plan`。
- 已提供删除审计记录：`GET /data-governance/operations`。
- 已提供 task 级硬删除后端入口：`POST /data-governance/delete`，必须传入 `confirmScopeId`。
- Web `/data-governance` 当前只开放 dry-run 预览和审计查看，不直接暴露危险硬删除按钮。

asset / node 作用域当前只返回预览，不执行硬删除。托管 / SaaS、官方远端备份、官方远端删除仍是计划项。

## 2. 数据资产 manifest

Manifest 由 `packages/python-sdk/src/yggdrasil_sdk/data_governance.py` 生成，覆盖以下资产组：

| 资产组 | 主要位置 | 当前删除策略 |
|--------|----------|--------------|
| tasks | `tasks`、`agent_runs`、`task_snapshots` | task 级硬删除已支持 |
| runtime | `model_invocations`、`model_route_decisions`、`state/llm`、`state/runtime` | 随 task 删除 |
| prompt-artifacts | `prompt_compile_artifacts`、`state/prompt` | 随 task 删除 |
| memory | `nodes`、`edges`、`node_versions`、`source_annotations` | 仅预览，硬删除待冻结 |
| assets | `assets`、`asset_segments`、`asset_embeddings` | 仅预览，硬删除待冻结 |
| mailbox-side-channel | `mailbox_messages`、`side_channel_events`、`outbox_records` | 随 task 删除 |
| observability | `state/observability`、Langfuse、OTel | 本地文件待单独策略；远端不自动删除 |
| product-logs-backups | `.yggdrasil/product-logs`、`.yggdrasil-backups` | 不随 task 静默删除 |

本地模式必须继续保持：不会自动把数据上传到 Project Yggdrasil 官方服务。任何未来远端同步都必须通过显式账号、工作区和同步开关进入。

## 3. 删除预览

请求：

```json
{
  "scopeKind": "task",
  "scopeId": "task_xxx",
  "includeStateFiles": true,
  "reason": "用户填写的删除原因"
}
```

响应包含：

- `database.tables[]`：会删除或计划处理的表、数量和样本 id。
- `stateFiles[]`：可安全删除的 state-root 文件列表。
- `retainedData[]`：明确不会被本次删除处理的数据，例如旧备份、产品日志、外部 provider。
- `warnings[]`：删除边界说明。
- `blockers[]`：运行中任务等阻塞项。

每一次 dry-run 都会写入 `data_governance_operations`，状态为 `planned`。

## 4. task 级硬删除

执行请求必须包含对象名确认：

```json
{
  "scopeKind": "task",
  "scopeId": "task_xxx",
  "confirmScopeId": "task_xxx",
  "includeStateFiles": true,
  "reason": "用户填写的删除原因"
}
```

当前硬删除规则：

- `queued`、`running`、`pause-requested`、`restarting` 状态的任务会被阻塞。
- 删除顺序显式覆盖 `outbox_records`、`prompt_compile_artifacts`、`model_invocations`、`model_route_decisions`、`mailbox_messages`、`side_channel_events`、`task_snapshots`、`agent_runs`、`tasks`。
- SQLite 和 PostgreSQL 都不能只依赖数据库 cascade；运行时子表必须显式删除。
- 文件删除只允许落在 `YGGDRASIL_STATE_ROOT` 下且已确认存在的普通文件。
- 旧备份、产品日志、外部 provider、Langfuse、远端 OTel 和未来官方远端服务不会被本地 task 删除自动处理。

## 5. 审计

审计表：`data_governance_operations`。

记录字段包括：

- 操作类型：`deletion-plan` 或 `delete`。
- 作用域：`scopeKind` / `scopeId`。
- 是否 dry-run。
- 状态：`planned` / `completed` / `blocked` / `failed`。
- 请求人、原因、plan 摘要、result 摘要、错误摘要。

后续如果开放 Web 硬删除按钮，必须先补齐二次确认、删除前备份提示、恢复演练和删除证明摘要，不能把当前 dry-run 页面直接改成无保护删除按钮。
