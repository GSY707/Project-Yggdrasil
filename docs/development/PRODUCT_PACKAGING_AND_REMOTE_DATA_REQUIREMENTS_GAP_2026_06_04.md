# 产品打包与官方远端数据能力需求差距文档

日期：2026-06-04
最近更新：2026-06-06

## 1. 结论

本轮继续把产品化能力从“计划项”推进到“预览可验证”，但仍不把未完成的正式发行、托管和官方远端数据服务写成当前可用能力：

| 能力 | 当前状态 | 结论 |
|------|----------|------|
| 完整 Docker Compose 产品栈 | 预览可验证 | 已新增 `infra/docker-compose.product.yml`、产品 Dockerfile、未跟踪 product env、product smoke、备份、恢复、快照列表、升级和回滚维护命令；正式发行前仍需多版本冷启动/升级演练。 |
| 桌面封装 | 未签名安装包、托盘与手动更新器预览 | 已新增 Windows 未签名安装器、卸载器、托盘控制器、ZIP 构建脚本、更新检查/手动应用脚本和计划任务；签名、正式发布渠道和静默自动更新仍未完成。 |
| 删除 / 清理 / 数据治理 | 本地 Web 保护性执行预览 | 已新增数据资产 manifest、删除预览、审计表、API、备份列表/创建备份、Web `/data-governance` 保护性 task 硬删除和删除证明；asset / node 仍只开放预览。 |
| 托管 / SaaS | 计划中 | 已加入路线图，但当前没有官方账号体系、远端工作区、服务条款、隐私策略、商业支持或 uptime 承诺。 |
| 官方远端数据服务 | 计划中 | 上线前契约已冻结草案 `docs/specs/remote-data-service-contract-v0.1.md`；远端数据托管、远端备份、远端恢复和远端删除仍未实现，当前本地产品模式不会自动上传数据。 |

推荐推进顺序：

1. 先把当前数据资产清单、删除预览、task 级硬删除后端、provider gate 和产品维护命令纳入定向回归。
2. 再把完整 Docker Compose 产品栈做多版本冷启动、备份/恢复、升级/回滚演练。
3. 再把桌面预览升级为签名安装包、正式发布渠道和可验证更新策略。
4. 最后做托管 / SaaS 与官方远端数据服务，因为它依赖账号、租户、安全、备份、删除和服务条款全部冻结。

## 2. 范围

本文件服务于后续三个计划功能的实现拆分：

- 完整 Docker Compose 产品栈。
- 桌面封装。
- 删除 / 清理 / 数据治理。

同时，本文件把用户新增要求纳入计划：

- 托管 / SaaS。
- 官方远端数据托管。
- 官方远端备份。
- 官方远端删除。

本文件不是服务上线公告，不是隐私政策，也不是商业支持承诺。任何用户文档、发布页或 README 都必须区分“预览可验证”“计划中”和“正式支持”，不能把未验收能力写成正式可用能力。

2026-06-06 后口径更新：

- 完整 Docker Compose 产品栈、Windows 桌面封装、数据治理保护性执行不再是纯计划项，已经进入预览可验证状态。
- Provider key 配置状态已抽成共享契约，Core API `/health.providerStatus` 会返回 ready / warning / blocked，Web 任务启动面板会阻止未就绪和 fallback 测试模式下的直接启动。
- 产品 Compose 现在优先读取未跟踪的 `infra/product.env`，并提供 `product:snapshots`、`product:upgrade`、`product:rollback`。
- Windows 桌面封装已补齐未签名安装/卸载、托盘控制器、备份、恢复、快照、升级、回滚、快捷方式安装/卸载、更新检查、手动应用更新和更新检查计划任务入口。
- 更新检查计划任务只写入状态，不会静默应用更新；未签名状态下不允许后台自动执行新版代码。
- 官方远端数据服务契约草案已新增，但仍不是已发布服务。
- 托管 / SaaS、官方远端数据托管、远端备份和远端删除仍是计划项，不能写成当前可用能力。
- Web `/data-governance` 当前展示资产清单、备份快照、删除影响预览、保护性 task 硬删除、删除证明和审计记录；执行前必须无 blocker、精确输入 `confirmScopeId`，且后端会在执行前重新生成 plan。运行中任务会阻塞，不创建删除前备份。

## 3. 当前已有基础

### 3.1 本地产品入口

已有：

- `corepack pnpm yggdrasil:up`。
- `packages/python-sdk/src/yggdrasil_sdk/ops_runtime/launcher.py`。
- Web 工作台 `/release` 页面。
- README 和用户指南中的首次成功路径。

当前能力：

- 拉起基础设施。
- 执行 Alembic 迁移。
- 启动 Core API、Agent Runtime、Module Host、Worker 和 Web。
- 把日志写入 `.yggdrasil/product-logs`。

差距：

- 仍依赖本机源码、`uv`、`pnpm`、Docker 和多个开发依赖。
- 没有产品镜像。
- 没有用户级安装器。
- 没有稳定版本号和正式发布镜像 tag。
- 已有产品栈升级/回滚维护命令，但还缺多版本演练和正式发布策略。
- 已有桌面封装脚本、快捷方式、未签名安装器、托盘控制器和手动更新器，但没有签名发行版或正式桌面服务管理器。

### 3.2 基础设施 Compose

已有：

- `infra/docker-compose.yml`。
- `infra/README.md`。
- `corepack pnpm infra:up` / `infra:down` / `infra:smoke`。

当前能力：

- 启动 PostgreSQL、Redis、NATS、MinIO、Temporal、Jaeger、OpenTelemetry Collector 等依赖。
- 可选启动本地 Langfuse compose。

差距：

- `infra/docker-compose.yml` 仍只代表依赖栈，不应冒充产品栈。
- `infra/docker-compose.product.yml` 已包含 Web、Core API、Agent Runtime、Module Host、Worker 和 migrate job，但仍需正式多版本冷启动和恢复演练。
- 统一 `.env` schema 校验仍未冻结。
- 产品级升级、回滚和清理流程已有预览命令，仍需多版本和异常场景验收。

### 3.3 本地备份 / 恢复

已有：

- `corepack pnpm ops:backup`。
- `corepack pnpm ops:restore`。
- `corepack pnpm product:backup` / `product:restore` / `product:snapshots` / `product:upgrade` / `product:rollback`。
- `packages/python-sdk/src/yggdrasil_sdk/ops_runtime/backup.py`。

当前能力：

- 备份 SQLite 或 PostgreSQL 数据库。
- 备份完整 state root。
- 写入脱敏 `metadata.json`。
- 恢复最近或指定快照。
- 列出快照，并在产品栈升级/回滚前创建保护性快照。

差距：

- Web `/data-governance` 已有备份快照列表和创建保护性备份按钮。
- 没有备份预览、校验、加密、压缩或远端上传。
- 恢复前冲突检查仍不足。
- 没有远端备份库。
- Web task 硬删除已支持 `backupBeforeDelete` 删除前保护性快照；全局日志/备份清理策略仍未冻结。

### 3.4 删除 / 清理

已有：

- `docs/specs/data-governance-manifest-v0.1.md`。
- `packages/python-sdk/src/yggdrasil_sdk/data_governance.py` 数据资产 manifest、删除预览、task 硬删除执行和审计记录。
- `data_governance_operations` 审计表与 Alembic 迁移。
- Core API `/data-governance/manifest`、`/operations`、`/deletion-plan`、`/delete`。
- Core API `/data-governance/backups`、`/backup`。
- Web `/data-governance` 数据治理页，包含资产清单、备份快照、删除预览、保护性 task 硬删除和删除证明。
- Web API 代理已补 `PUT` / `PATCH` / `DELETE` 转发。
- 数据库部分关系使用 cascade / set null / restrict。
- 部分 repository 有局部 `delete` 语句。
- `modules/text-memory` 已有 `forget_node`，`modules/memory-organizer` 已有软遗忘能力；这属于记忆治理，不等于用户级硬删除。
- 用户指南说明可停止服务后手动清理 `.yggdrasil`。

差距：

- Web 只对 `task` 作用域开放受保护硬删除按钮；必须无 blocker、精确确认 `scopeId`，默认先创建保护性备份。
- task 级硬删除后端已提供，但 `DELETE /tasks/{taskId}`、`DELETE /assets/{assetId}`、`DELETE /nodes/{nodeId}` 等 REST 资源路由尚未冻结。
- asset / node 当前只有预览，没有硬删除执行。
- task 级硬删除返回删除证明摘要，包含数据库行数、state file 删除结果、保留边界、warnings 和可选备份快照路径。
- 数据资产 manifest 已覆盖数据库、state root、日志、备份和外部 provider 边界，但日志/备份清理策略尚未执行化。
- 没有远端删除请求和远端删除状态查询。

### 3.5 托管 / SaaS 与官方远端数据

已有：

- 官方远端数据服务上线前契约草案：`docs/specs/remote-data-service-contract-v0.1.md`。
- 没有官方托管服务入口。
- 没有官方远端数据服务入口。
- 没有账号、组织、工作区或租户模型。
- 没有远端备份、恢复、删除请求 API。

当前必须保持的用户承诺：

- 本地产品模式不会自动把数据上传到 Project Yggdrasil 官方服务。
- 如果未来支持远端能力，必须通过显式账号、工作区和同步开关进入。

差距：

- 没有账号体系。
- 没有租户隔离。
- 已有远端服务契约草案，但没有远端存储实现。
- 没有密钥管理策略。
- 没有隐私政策和服务条款。
- 没有数据地域、保留期、删除证明、审计导出和恢复演练机制。
- 没有商业支持和 uptime 运维体系。

## 4. 功能一：完整 Docker Compose 产品栈

### 4.1 用户目标

外部用户可以不理解源码结构、不手动开多个终端，只用 Docker Compose 拉起一个完整本地产品环境，然后通过浏览器完成首次成功路径。

### 4.2 功能需求

| 编号 | 需求 | 验收标准 |
|------|------|----------|
| DCP-01 | 提供产品 compose 文件 | 新增产品 compose 与当前 infra compose 分离，不能把依赖 compose 冒充产品栈。 |
| DCP-02 | 提供服务镜像 | Core API、Agent Runtime、Module Host、Worker、Web 都有可构建镜像和版本标签。 |
| DCP-03 | 提供统一环境配置 | `.env.example` 或产品 `.env.template` 明确 provider key、端口、state root、数据库和观测配置。 |
| DCP-04 | 启动后只有一个主入口 | 用户启动后访问一个 Web URL 即可进入产品，不需要阅读开发者多终端启动说明。 |
| DCP-05 | 健康检查完整 | Compose health check 覆盖数据库、Redis、Core API、Worker 队列、Web 和 provider key 阻塞项。 |
| DCP-06 | 数据卷边界冻结 | 明确数据库、state root、产品日志、备份快照分别落在哪些 volume 或宿主目录。 |
| DCP-07 | 支持备份 / 恢复 | `ops:backup` / `ops:restore` 能在 compose 产品栈下工作，或提供等价 compose 命令。 |
| DCP-08 | 支持升级 / 回滚 | 明确镜像 tag、迁移执行时机、失败回滚和恢复快照策略。 |
| DCP-09 | 日志可查 | 用户能从 Web 或单条命令查看关键服务日志。 |
| DCP-10 | 不泄露凭据 | provider key 不写入镜像、不进入日志、不进入备份明文清单。 |

### 4.3 当前差距

- `infra/docker-compose.yml` 只覆盖依赖；产品栈必须使用 `infra/docker-compose.product.yml`。
- 产品服务镜像已有预览 Dockerfile，但正式 tag、发布镜像和发布渠道策略未冻结。
- 产品 compose 已有基础健康检查矩阵，provider key 阻塞提示已接入 `/health.providerStatus` 和 Web 任务启动面板；首次成功路径仍需产品级 smoke 扩展。
- compose 模式下已有备份、恢复、升级和回滚预览命令，但缺多版本和故障注入验收。
- 没有用户级故障说明。

### 4.4 需要补充的测试

- `docker compose config`。
- 产品栈冷启动 smoke。
- 首次成功路径 API smoke。
- 备份 / 恢复 / 快照列表 / 升级 / 回滚 smoke。
- provider key 缺失、fallback 测试模式和密钥值不泄露的阻塞提示回归。
- 数据卷删除前 dry-run。

## 5. 功能二：桌面封装

### 5.1 用户目标

普通用户可以安装一个桌面应用，用桌面入口启动 / 停止本地产品，查看健康状态、日志和备份恢复入口，而不是学习源码、命令行和多服务进程。

### 5.2 功能需求

| 编号 | 需求 | 验收标准 |
|------|------|----------|
| DESK-01 | Windows 优先安装包 | 至少先提供 Windows 安装、卸载和启动入口。 |
| DESK-02 | 启动本地产品 | 桌面壳能启动或调用本地产品栈，并把用户带到 Web 工作台。 |
| DESK-03 | 服务状态可见 | 显示 Core API、Worker、Web、数据库、provider key、state root 状态。 |
| DESK-04 | 日志可见 | 能打开产品日志目录或在界面显示最近错误。 |
| DESK-05 | 安全停止 | 能停止服务，避免直接杀进程导致数据库或 state root 损坏。 |
| DESK-06 | 备份 / 恢复入口 | 桌面入口可以触发本地备份、查看快照和恢复指定快照。 |
| DESK-07 | 删除前保护 | 删除或重置本地状态前必须展示影响范围，并建议先备份。 |
| DESK-08 | 更新策略 | 明确自动更新、手动更新、迁移执行和回滚策略。 |
| DESK-09 | 显式远端开关 | 如未来接入官方远端服务，桌面端必须默认本地优先，远端同步必须显式开启。 |
| DESK-10 | 不隐藏外联 | 任何 provider、观测、远端同步和更新网络访问都必须可解释。 |

### 5.3 当前差距

- 已有 Windows 未签名安装器、卸载器、托盘控制器、维护命令、快捷方式安装和 ZIP 构建入口，但还没有 Electron / Tauri / 其他桌面壳最终选型。
- 已有未签名安装包预览，没有代码签名、SmartScreen 信誉、正式发布渠道或版本发布流程。
- 已有 PowerShell WinForms 托盘控制器，没有原生桌面服务管理器。
- 当前只有命令入口封装，没有桌面端备份恢复图形 UI。
- 已有更新检查和手动应用更新入口；计划任务只检查更新并写入 `update-state.json`，不做静默自动应用。
- 没有桌面端远端同步同意流程。

### 5.4 技术路线建议

第一版不要做复杂原生功能。推荐先把桌面封装限定为：

- 安装器。
- 本地产品启动 / 停止。
- 打开 Web 工作台。
- 健康状态。
- 日志入口。
- 备份 / 恢复入口。
- 数据位置和隐私边界说明。

不要在第一版桌面封装中同时引入远端同步。远端能力应等数据治理和 SaaS 契约冻结后再接。

## 6. 功能三：删除 / 清理 / 数据治理

### 6.1 用户目标

用户可以明确知道系统保存了哪些数据，可以导出、备份、恢复和删除数据，并能知道删除会影响哪些任务、素材、记忆、日志、备份和远端副本。

### 6.2 本地删除需求

| 编号 | 需求 | 验收标准 |
|------|------|----------|
| DEL-01 | 数据资产清单 | 列出任务、节点、资产、asset segments、embeddings、model invocations、prompt artifacts、snapshots、mailbox、side-channel、logs、observability、backups。 |
| DEL-02 | 删除作用域 | 支持按任务、素材、节点、应用、工作区和全量本地状态删除。 |
| DEL-03 | 删除预览 | 删除前返回会删除的数据库行、state 文件、日志、备份和受影响对象数量。 |
| DEL-04 | dry-run | CLI/API/Web 都能先 dry-run，不直接删除。 |
| DEL-05 | 备份前置 | 高风险删除默认提示或自动创建本地备份。 |
| DEL-06 | 删除审计 | 记录谁、何时、删除了什么、是否 dry-run、是否生成备份、是否成功。 |
| DEL-07 | 删除证明 | 本地删除完成后生成可读摘要，说明已删除范围和无法删除范围。 |
| DEL-08 | 失败恢复 | 删除中断时能重试或回滚到删除前快照。 |
| DEL-09 | 外部 provider 边界 | 明确 LLM provider、Langfuse、OTel 等第三方系统不受本地删除自动控制，除非未来接入对应远端删除 API。 |
| DEL-10 | UI 操作防误删 | Web 删除按钮需要二次确认、对象名称确认和高风险提示。 |

### 6.3 官方远端数据需求

| 编号 | 需求 | 验收标准 |
|------|------|----------|
| RDATA-01 | 账号与工作区 | 远端数据必须绑定账号、组织、工作区和租户边界。 |
| RDATA-02 | 显式同步 | 本地数据上传到官方服务必须由用户显式开启，不允许默认上传。 |
| RDATA-03 | 远端托管 | 定义哪些对象可以远端托管：任务、素材、节点、快照、模型调用摘要、Prompt 工件、运行日志。 |
| RDATA-04 | 数据分类 | 区分密钥、个人数据、任务内容、模型响应、日志、审计、备份和可公开样例。 |
| RDATA-05 | 加密 | 明确传输加密、静态加密、密钥托管、密钥轮换和管理员访问边界。 |
| RDATA-06 | 数据地域 | 明确默认地域、可选地域、跨境传输和迁移策略。 |
| RDATA-07 | 远端备份 | 定义备份频率、保留期、恢复点目标、恢复时间目标和恢复演练。 |
| RDATA-08 | 远端恢复 | 用户能查看远端快照、选择恢复点，并知道恢复会覆盖哪些本地或远端数据。 |
| RDATA-09 | 远端删除 | 用户能发起删除工作区、任务、素材、备份或账号数据请求，并查询进度。 |
| RDATA-10 | 删除证明 | 删除完成后提供可读证明，说明删除对象、保留例外、法务保留和第三方系统边界。 |
| RDATA-11 | 审计导出 | 管理员和用户可导出远端访问、备份、恢复、删除审计。 |
| RDATA-12 | 服务条款和隐私策略 | 上线前必须有正式条款，不允许只靠 README 说明。 |

### 6.4 当前差距

- 数据资产 manifest、统一删除 service、数据治理 API、Web dry-run 页和审计表已完成第一版。
- task 级硬删除已支持后端执行，但 Web 暂不暴露危险删除按钮。
- asset / node 仅支持预览，尚未支持硬删除。
- 日志和备份清理策略尚未执行化。
- 已冻结远端服务契约草案，但没有远端账号 / 租户 / 工作区。
- 没有远端备份库。
- 没有远端删除状态机。
- 没有隐私政策、服务条款和 DPA 级别材料。

### 6.5 必须先冻结的数据清单

后续实现前必须列出以下对象的数据位置和删除策略：

| 对象 | 主要位置 | 删除策略待定点 |
|------|----------|----------------|
| Task | 数据库 `tasks` 与相关 runtime 表 | 是否允许删除运行中任务；是否保留审计摘要。 |
| AgentRun | 数据库与 state root runtime 工件 | 是否随 task 删除；是否保留聚合统计。 |
| Node / Memory | 数据库 `nodes`、relations、import fragments | 删除节点时如何处理关系、索引和子树。 |
| Asset | 数据库 assets、segments、embeddings 与文件引用 | 是否支持删除单素材及其所有派生节点。 |
| ModelInvocation | 数据库与 LLM 请求/响应工件 | 是否需要脱敏保留成本统计。 |
| PromptCompileArtifact | 数据库与 prompt state 工件 | 是否随 task / invocation 删除。 |
| Observability | 本地 JSONL、Langfuse、OTel 远端 | 本地可删；远端需单独 API 或用户自行处理。 |
| Soft forgetting | 文本记忆模块和 memory organizer 状态 | 软遗忘不是硬删除；不能把它当作用户数据删除证明。 |
| Product logs | `.yggdrasil/product-logs` | 是否按服务、时间范围或全量清理。 |
| Backups | `.yggdrasil-backups/<timestamp>` | 删除源数据是否同时删除旧备份；若不删除需提示。 |
| Remote backups | 未来官方远端备份库 | 删除请求、保留期、法务保留和删除证明。 |

## 7. 托管 / SaaS 需求

### 7.1 产品目标

托管 / SaaS 不是“把本地产品放到一台服务器上”。它必须提供账号、租户、工作区、远端数据治理、备份恢复、安全运维和服务承诺。否则会制造比本地产品更高的数据风险。

### 7.2 功能需求

| 编号 | 需求 | 验收标准 |
|------|------|----------|
| SaaS-01 | 账号体系 | 支持登录、组织、工作区、成员和角色。 |
| SaaS-02 | 租户隔离 | 所有任务、节点、资产、日志、备份按租户隔离，测试覆盖越权读取和越权删除。 |
| SaaS-03 | 计费或配额 | 至少有成本、调用量、存储量和并发限制；是否收费可后置。 |
| SaaS-04 | Provider key 策略 | 明确用户自带 key、官方托管 key 或混合模式；密钥不得进入日志和普通备份明文。 |
| SaaS-05 | 远端存储 | 定义数据库、对象存储、向量/embedding、观测、备份和审计存储。 |
| SaaS-06 | 运维监控 | 有服务健康、错误率、队列积压、成本异常和备份失败告警。 |
| SaaS-07 | 安全流程 | 漏洞响应、访问日志、管理员访问、密钥轮换和数据泄露处理流程。 |
| SaaS-08 | 支持边界 | 明确 uptime、支持响应、维护窗口和服务状态页。 |
| SaaS-09 | 合规材料 | 隐私政策、服务条款、数据处理说明、删除和保留政策。 |
| SaaS-10 | 用户退出 | 支持导出、删除、关闭账号和迁出到自托管。 |

### 7.3 当前差距

- 当前开源仓库没有 SaaS 控制面。
- 没有 auth / tenant / workspace 数据模型。
- 没有托管环境 IaC。
- 没有远端对象存储和远端备份服务。
- 没有服务状态页。
- 没有隐私政策、服务条款和运营支持流程。

## 8. 实施阶段建议

### 阶段 A：数据治理规格和本地删除闭环

目标：

- 建立数据资产 manifest。
- 定义删除作用域。
- 新增 dry-run 删除 API。
- 新增 Web 删除 / 清理入口。
- 让备份、恢复、删除三个动作形成闭环。

交付物：

- 数据资产 manifest。
- 删除协议 / 规格。
- API 和 Web 原型。
- 删除审计表。
- 本地删除测试。

### 阶段 B：完整 Docker Compose 产品栈

目标：

- 发布完整本地产品 compose。
- 冻结数据卷和升级策略。
- 让外部用户可通过 Docker Compose 完成首次成功路径。

交付物：

- 产品 Dockerfile。
- 产品 compose。
- `.env` 模板。
- 健康检查。
- compose smoke。
- README / USER_GUIDE / `/release` 更新。

### 阶段 C：桌面封装

目标：

- 为 Windows 用户提供安装和本地产品控制入口。
- 将服务启动、健康状态、日志、备份、恢复、删除入口包装为用户可见界面。

交付物：

- 桌面封装技术选型。
- 安装 / 卸载流程。
- 服务控制器。
- 本地产品状态页。
- 备份恢复入口。
- 删除前保护。

### 阶段 D：托管 / SaaS 与官方远端数据服务

目标：

- 冻结账号、租户、工作区和远端数据治理。
- 实现官方远端数据托管、远端备份、远端删除。
- 在服务条款和隐私政策完备后开放有限试点。

交付物：

- SaaS RFC。
- auth / tenant / workspace 数据模型。
- 远端存储协议。
- 远端备份 / 恢复 / 删除状态机。
- 隐私政策和服务条款草案。
- 安全和运维 runbook。

## 9. 风险

| 风险 | 影响 | 缓解 |
|------|------|------|
| 把计划项写成已上线能力 | 外部用户误解支持边界 | `/release`、README、用户指南统一使用“计划中”；验收前不得写“可用”。 |
| 删除功能误删 | 用户数据不可恢复 | dry-run、备份前置、二次确认、删除审计和恢复测试必须先做。 |
| 软遗忘被误当成硬删除 | 用户以为数据已被彻底清除 | 文档、API 和 UI 必须区分软遗忘、软删除、硬删除和删除证明。 |
| 备份包含敏感信息 | 密钥或隐私数据泄露 | 备份清单必须区分密钥、任务内容、日志和外部 provider 数据。 |
| 删除后旧备份复活数据 | 用户删除的数据通过恢复重新出现 | 删除策略必须覆盖备份快照、保留期、删除前快照和恢复后过滤规则。 |
| 远端同步默认开启 | 破坏本地优先承诺 | 远端能力必须显式账号、工作区和同步开关。 |
| SaaS 缺租户隔离 | 严重数据泄露 | 租户隔离和越权测试是 SaaS 上线前硬门禁。 |
| 桌面封装掩盖服务失败 | 用户不知道后台损坏 | 桌面 UI 必须显示健康状态和日志入口。 |
| Compose 产品栈与源码启动漂移 | 文档和测试失真 | Compose smoke、Web smoke 和备份恢复 smoke 必须纳入发布检查。 |

## 10. 验收门禁

后续实现任一计划功能时，至少满足以下门禁：

- 更新 `/release` 页面。
- 更新 README。
- 更新 `docs/USER_GUIDE.md`。
- 更新 `docs/DEVELOPER_GUIDE.md`。
- 更新 `docs/DIRECTORY_REFERENCE.md` 及分册索引。
- 不能把未发布能力写成可用。
- 删除旧的错误测试和过渡文档，避免继续引导旧路线。
- 增加对应自动化测试或 smoke。
- 对涉及数据删除、远端同步、远端备份的功能补充安全和隐私说明。

## 11. 未决问题

1. 桌面封装采用 Electron、Tauri，还是更薄的本地启动器加浏览器入口？
2. 完整 Docker 产品栈是否要求离线安装，还是允许首次启动拉取镜像和依赖？
3. 本地删除是否支持“只删除任务但保留审计摘要”？
4. 删除旧备份时，是否需要默认保留最近一个删除前快照？
5. 远端数据服务是否允许自托管远端备份，还是只支持官方 SaaS？
6. 官方 SaaS 使用用户自带 provider key、官方托管 key，还是两者都支持？
7. 远端删除证明需要做到用户可读摘要，还是需要机器可验证证明？
8. 数据地域和保留期是否在首个试点前冻结，还是先限定单一区域试点？

## 12. 下一步建议

最小可推进任务如下：

1. 跑通并固化 `tests/api/test_data_governance_api.py`、`tests/api/test_provider_configuration_api.py`、`product:compose:config`、`product:smoke` 和 Web typecheck。
2. 为 `/data-governance` 增加备份前置提示、二次确认设计和删除证明摘要，但仍不要直接开放无保护硬删除按钮。
3. 验证产品 Compose 多版本冷启动、首次成功路径、备份/恢复、快照列表、升级/回滚和故障中断恢复。
4. 将 Windows 薄启动器升级为正式安装包/托盘控制器前，先冻结健康摘要和日志目录协议。
5. 单独起草 SaaS RFC，明确账号、租户、远端存储、远端备份、远端删除、隐私和服务条款。
