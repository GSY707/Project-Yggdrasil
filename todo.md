
# 世界树计划开发 TODO（执行版）

## 当前阶段
- M1 已完成正式实现与验证，当前仓库已经不再处于“骨架占位”阶段。
- M2 已完成正式实现与验证，当前仓库已经具备 PostgreSQL/Alembic/repository/service/Redis 协调的持久化底座。
- M3 已完成正式实现与验证，当前仓库已经具备数据库驱动的模块生命周期、hook/订阅注册表、健康上报、outbox/NATS 事件总线与 module-host 控制面。
- M4 已完成正式实现与验证，当前仓库已经具备 text-memory 的导入、建树计划、落库 materialize、检索 API 与回归样本闭环。
- 当前主问题已经从“在主 Agent 闭环跑通后，继续推进 Sub-Agent、PR 生命周期与跨链路持续回归”切换到“在 M6 闭环完成后，推进 Web 工作台与持续回归/运维底座”。
- 当前第一优先级：进入 M7，把任务列表、节点详情、版本历史、来源信息与 PR 列表切到正式 API 工作台。

## 规格入口
- [docs/PRD-v0.1.md](docs/PRD-v0.1.md)
- [docs/protocols/README.md](docs/protocols/README.md)
- [docs/specs/README.md](docs/specs/README.md)
- [docs/specs/agent-runtime-protocol-v0.1.md](docs/specs/agent-runtime-protocol-v0.1.md)

## 代码盘点

### 统计口径
- 统计范围：仓库内 95 个代码/配置文件。
- 文件类型：.py、.ts、.tsx、.json、.toml、.yaml、.yml、.css。
- 不包含 markdown 文档，因此 docs 中的大量正式规格文档不计入下面的代码统计。
- 不包含 `.yggdrasil/state/` 下 2 个运行时生成状态文件；它们属于本地状态产物，不计入正式代码分类。

### 分类标准
- 占位代码：接口形状已经固定，但返回的是占位值、空集合、假数据或演示结果，不能承载正式业务。
- 临时代码：仅用于一次性演示、本地过渡或短期调试，后续会被正式实现替换，不应长期保留。
- 正式工程代码：后续应继续沿用的工程边界、包配置、manifest、schema、SDK、服务入口、测试和稳定结构代码。
- 运行时产物：由程序自动生成的本地缓存、快照和状态文件，不纳入正式代码盘点。

### 统计结果
- 占位代码：0 个文件。
- 临时代码：0 个文件。
- 正式工程代码：95 个文件。
- 运行时产物：2 个文件。

### 占位代码清单
- 当前无。

### 临时代码清单
- 当前无。

### 正式工程代码分布
- 正式工作区与基础配置：根目录 package.json、pyproject.toml、pnpm-workspace.yaml、tsconfig.base.json、pytest.ini、[infra/docker-compose.yml](infra/docker-compose.yml)。
- 正式共享层：packages/contracts、packages/python-sdk、packages/frontend-sdk；其中 python-sdk 已补齐 domain records、ORM、repository、bootstrap、Redis 协调能力。
- 正式服务层：core-api、agent-runtime、module-host、worker 的 app/main/config/router/registry/runtime 代码；其中 core-api 已具备 nodes/tasks/runtime/outbox 正式接口。
- 正式模块层：text-memory、context-pruning、subagent-pr 的 manifest、pyproject、插件逻辑与 hook 导出。
- 正式适配器层：model-providers、media-providers 的路由/处理管线实现。
- 正式前端层：web 的 layout、globals、首页工作台、workspace dashboard 组装、Next/ESLint/TypeScript 配置。
- 正式验证层：tests 下的 contract tests、持久化 API/runtime/worker 验证，以及根脚本里的 web typecheck/lint/build、Python pytest 验证入口。
- 正式迁移层：alembic.ini、migrations/env.py、migrations/versions 初始迁移。

### 运行时产物
- [.yggdrasil/state/module-install-records.json](.yggdrasil/state/module-install-records.json)：本地模块安装与启用记录快照。
- [.yggdrasil/state/module-catalog-snapshot.json](.yggdrasil/state/module-catalog-snapshot.json)：本地模块目录聚合快照。
- 处理原则：允许本地生成，不作为提交内容；后续以数据库记录和可重建快照替代当前文件状态源。

## 已完成资产
- [x] PRD、ADR、协议和数据规格已经形成第一版正式文档。
- [x] Monorepo 骨架与前端/服务/模块/适配器/共享层工作区已经搭建完毕。
- [x] shared contracts、catalog、spec catalog、support 工具层已经形成正式公共能力。
- [x] module-host、core-api、agent-runtime、worker 已具备第一版正式目录/快照/装配逻辑。
- [x] text-memory、context-pruning、subagent-pr、model router、media pipeline 已从占位实现升级为正式 M1 逻辑。
- [x] Web 首页已经替换为正式运行工作台，而不是骨架落位页。
- [x] PostgreSQL/Alembic/repository/service/Redis 协调的共享持久化底座已经落地。
- [x] core-api、module-host、agent-runtime、worker 已接入正式持久化层。
- [x] Python contract tests 与持久化验证已通过：13 passed。
- [x] Alembic upgrade head 已对空 sqlite 库执行通过，初始迁移可运行。
- [x] Web 验证已通过：install、typecheck、lint、build。
- [x] 根目录前端脚本已改为显式走 corepack pnpm，不再依赖全局 pnpm。

## 未来工作重排

### M1. 清理骨架债务（已完成）
- [x] 去掉 8 个占位文件里的占位返回值，替换为正式对象、目录驱动逻辑或启发式实现。
- [x] 替换 3 个临时代码文件，使其进入正式工程边界。
- [x] 清理代码中的占位命名和描述，统一为正式术语。
- [x] 为 manifest、hook、event envelope、shared contracts、runtime、pruning、module catalog、subagent/worker 增加 contract tests。
- [x] 完成 Python pytest、Web typecheck、lint、build 验证。
- 验收：占位代码 0 个，临时代码 0 个，当前仓库可作为 M2 到 M7 的正式起点。

### M2. 持久化底座（已完成）
- [x] 建立 PostgreSQL 基础表和 Alembic 迁移骨架。
- [x] 首批落地对象：Node、Edge、NodeVersion、SourceAnnotation、Task、AgentRun、TaskSnapshot、ModuleInstallRecord、OutboxRecord、ModelRouteDecision。
- [x] 为 core-api 建立 repository 层和 service 层，替代当前直接读文件/快照的实现。
- [x] 补上 Redis 作为热点缓存、分布式锁和异步作业协调入口。
- [x] module-host 改为数据库同步式注册表，worker 增加 Redis 队列协调入口。
- [x] agent-runtime 的 RootMountPackage 与 pause snapshot 已可对真实 Task/AgentRun/Snapshot 落库。
- 验收：已经可以持久化创建和读取节点、任务、模块安装记录、路由决策和快照；pytest 13 passed，Alembic upgrade head 可运行。

### M3. 模块宿主与事件总线（已完成）
- [x] manifest 发现、模块目录聚合和安装记录快照已经具备第一版正式实现。
- [x] 将当前文件快照升级为数据库驱动的模块注册表，并保留本地缓存层。
- [x] 建立模块状态流转：discovered、validated、installed、disabled、active、degraded、quarantined。
- [x] 接上 NATS JetStream 与 outbox 发布链路。
- [x] 建立 hook 注册表、事件订阅注册表、模块配置绑定、健康上报。
- 验收：module-host 能从正式注册表与事件总线驱动模块生命周期，文件快照仅作为本地重建缓存。

### M4. text-memory 第一条纵向链路（已完成）
- [x] 文本切分、候选父节点建议、候选关联建议、检索扩展已经具备第一版启发式实现。
- [x] 实现 ImportJob、ImportFragment、TreePlan 的持久化链路。
- [x] 将节点、边、版本和来源注解正式写入数据库。
- [x] 完成 RetrievalRequest 到 RetrievalBundle 的 API 闭环。
- [x] 建立导入/检索链路的评测样本和回归断言。
- 验收：导入一份小型文本资料后，可以从数据库和 API 稳定检索到节点内容、关联和来源。

### M5. 主 Agent 第一条闭环（已完成）
- [x] RootMountPackage 与 pause snapshot 的预览装配逻辑已经落地。
- [x] 上下文修剪的 plan/execute 第一版已经落地。
- [x] 实现任务预算、Token 预算、ModelRouteDecision 的持久化与真实执行约束。
- [x] 实现异步写入、最小 safe-stop 语义和恢复点。
- [x] 把当前预览逻辑接到真实任务执行链。
- 验收：主 Agent 已能完成一次任务启动、写入、暂停、恢复的最小正式闭环；当前全量 pytest 为 19 passed。

### M6. Sub-Agent 与 PR 最小闭环（已完成）
- [x] PR 记录、评论记录、工具注册和 worker activity 描述已经具备正式对象与第一版逻辑。
- [x] 实现分支模型与 Sub-Agent 创建。
- [x] 实现预算继承、模型选择与只读上下文传递。
- [x] 接入真实 Git/GitHub PR 生命周期。
- [x] 验证共享空间预埋字段在分支和 PR 流中的传递。
- 验收：Sub-Agent 能独立产出结果并以 PR 形式提交，由主 Agent 审核、评论和合并；当前全量 pytest 为 21 passed。

### M7. Web 控制台从首页升级为工作台
- [x] 首页已经替换为正式运行工作台，可读取 todo、规格目录、模块快照和服务面板。
- [ ] 提供任务列表、节点详情、版本历史、来源信息、PR 列表基础页面。
- [ ] 再补树浏览、图谱浏览、时间线、暂停/恢复入口。
- [ ] 从直接读取仓库文件升级为读取正式 API。
- 验收：Web 控制台可作为第一版日常操作入口，而不只是仓库级 dashboard。

### M8. 评测与运维底座
- [ ] 建立第一批基准任务集。
- [ ] 建立无记忆、纯向量、记忆树检索的基线对照。
- [ ] 接入 OpenTelemetry、Langfuse、日志与成本指标。
- [ ] 建立本地 Compose 联调、备份策略、CI 骨架。
- 验收：每次核心链路变更都能跑回归并看到成本与效果差异。

### M9. 第二阶段模块化能力
- [ ] 多模态记忆模块。
- [ ] 自动整理与软遗忘模块。
- [ ] 主动关联发现模块。
- [ ] 高级权限与共享记忆空间模块。
- [ ] 训练与蒸馏实验模块。
- [ ] 任务暂停与无感恢复的完整产品化交付。
- 前提：M4 到 M8 完成前，不进入这些模块的正式开发，只允许保留字段、状态和接口预埋。

## 当前最该做的 10 件事
1. 让 Web 控制台从读仓库文件切到读正式 API。
2. 提供任务列表、节点详情、版本历史、来源信息、PR 列表基础页面。
3. 建立覆盖 runtime、subagent 和 memory 三条链路的回归样本集与 CI 入口。
4. 补齐可观测性、成本、任务和模块级指标的运维底座。
5. 把 Docker Compose 联调从 PostgreSQL/Redis/NATS 扩展到 Temporal 与 MinIO 的完整工作流闭环。
6. 为主 Agent 与 Sub-Agent 增加启动、暂停、恢复、审查、合并的 smoke tests。
7. 为 Web 工作台再补树浏览、图谱浏览、时间线、暂停/恢复入口。
8. 为 collaboration 路径接入更完整的 GitHub review/merge 状态同步和权限控制。
9. 为共享空间/高级权限预埋字段补齐 API 与验证。
10. 建立第一批评测任务集和成本/效果对照基线。

## 明确不该现在做的事
- 不要在 M4 之前实现多模态、训练、共享空间的正式业务逻辑。
- 不要让模块直接读写其他模块的内部实现。
- 不要绕过 module-host 或 shared SDK 直接硬编码 hook 协议。
- 不要把运行时生成状态文件重新纳入版本控制。
- 不要再往 todo 里重复写已经冻结到 docs 的技术选型细节，todo 只保留执行计划和盘点结果。

## 一句话原则
- M1 和 M2 已经把工程边界与持久化底座立住，接下来优先做真实事件链路、纵向业务闭环和持续回归能力，不再回到骨架式占位开发。