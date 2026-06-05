# 未完成项并行开发可行性与合并难度评估（2026-06-05）

## 1. 结论

本项目剩余未完成项可以并行推进，但不能按“功能愿望清单”随意拆成多个 PR 同时合并。真正的并行边界不是页面或文档标题，而是这些共享接口：

- Core API 路由方法与前端代理方法。
- 数据对象归属、删除、备份、审计和远端同步契约。
- `packages/frontend-sdk/src/types.ts` 的共享类型。
- Web 工作台导航和几个大型页面组件。
- 运行时任务状态机、执行前确认门禁、长任务窗口压缩与评测合同。
- 产品启动、Docker、桌面封装和用户文档中的“可承诺能力”口径。

综合判断：

| 维度 | 结论 |
| --- | --- |
| 是否适合并行开发 | 适合，但应拆为 4 条主线：数据治理、Web 产品面、产品打包、运行时质量。 |
| 是否适合同时合并 | 不适合。需要先合并契约/代理/共享类型，再合并后端能力，再合并 Web 页面和 E2E。 |
| 最大合并风险 | 数据治理、执行前确认门禁、伪无限上下文等价交付、完整 Docker 产品栈。 |
| 最适合先并行的项 | Web-first 首任务 smoke、只读模块目录页、协作 PR Web 流、provider 只读状态页、提示词资产只读浏览。 |
| 最不适合并行硬推的项 | 删除真实执行、SaaS/远端数据、任务状态机门禁、长窗口运行时重构。 |

一句话：**可以多线开工，但必须先落“契约小 PR”，否则后续会在数据模型、前端 SDK、大页面和文档口径上反复冲突。**

## 2. 评估口径

本评估基于：

- `docs/development/DESIGN_COMPLETION_EVALUATION_2026_06_05.md` 中列出的未完成项。
- Core API 路由和服务层静态检查。
- Web 工作台页面、SDK 类型、Next API 代理和根 `package.json` 静态检查。
- 前端子代理对 Web 未完成项的只读分析结果。

本次没有启动服务、没有跑真实任务、没有验证 Docker Desktop 状态，因此结论是合并规划和开发组织评估，不是运行验收报告。

## 3. 合并难度分级

| 等级 | 含义 | 典型落点 |
| --- | --- | --- |
| 低 | 单一页面、单一文档或新增测试，基本不碰共享契约。 | 新只读页、新文档、局部 smoke。 |
| 中 | 触碰前端共享类型、导航、一个后端 service 或一个 API route。 | 模块目录页、PR Web 流、provider 状态页。 |
| 高 | 触碰数据库迁移、仓储、多条 API、运行时状态机、产品启动脚本或大组件。 | 删除 API、提示词编辑、执行前确认门禁、Docker 产品栈。 |
| 很高 | 同时改变数据治理、安全边界、远端同步、租户/权限或长任务核心语义。 | SaaS/远端数据、真实删除证明、伪无限上下文等价承诺。 |

## 4. 未完成项并行矩阵

| ID | 未完成项 | 并行可行性 | 合并难度 | 主要写入范围 | 依赖 / 阻塞 | 推荐拆分方式 |
| --- | --- | --- | --- | --- | --- | --- |
| P0-API-01 | Web API 代理补齐 `DELETE` / `PUT` / `PATCH` | 高 | 低 | `apps/web/app/api/core/[...path]/route.ts` | 无，但会解锁后续删除、设置、编辑类页面 | 单独小 PR，先合并。 |
| P0-DATA-01 | 数据资产归属清单与删除契约 | 中 | 中 | `docs/specs/`、`docs/development/`、数据模型说明 | 需要先定义 task/node/asset/prompt/snapshot/log/backup 的归属 | 先做契约文档和 dry-run 输出格式，不做真实删除。 |
| P0-DATA-02 | 删除 dry-run API、审计、删除证明 | 中低 | 高 | ORM、迁移、仓储、Core API、SDK 类型、测试 | 依赖 P0-API-01 和 P0-DATA-01 | 单独后端 PR；不要和 Web 删除页混合。 |
| P0-DATA-03 | Web 数据删除 / 隐私管理页 | 中 | 高 | 新页面、SDK deletion 类型、导航、release 文档 | 依赖 dry-run API；真实 execute 需要审计闭环 | 先做只读预览页，再接执行按钮。 |
| P0-WEB-01 | Web-first 首任务 E2E smoke | 高 | 中低 | `package.json`、Web smoke/e2e、`task-launch-panel.tsx` 附近错误提示 | 需要稳定本地启动和 provider 状态解释 | 可并行；限制为验收和错误提示，不重构任务面板。 |
| P0-SET-01 | provider 只读状态页 | 高 | 中 | 新 `/settings/providers`、`runtime_service._provider_setup_status()`、SDK 类型、导航 | 不依赖密钥保存策略 | 先做只读状态 + 修复指引。 |
| P0-SET-02 | provider key 保存、测试调用和安全存储 | 中低 | 高 | 后端 secret 存储、设置 API、隐私文档、测试 | 必须先定密钥存储边界，不能写进仓库或普通 DB 明文 | 单独设计和实现；不要附带 UI 大改。 |
| P0-CHECK-01 | 执行前任务核对门禁 | 低 | 高 | task takeover、prompting、execution loop、task service/routes、Web task flow、评测 | 需要明确新任务状态和确认 API；会影响大量现有测试 | 独立 runtime PR；先加阻断式测试，再改状态机。 |
| P1-MOD-01 | 模块管理只读目录页 | 高 | 中低 | 新 `modules-page.tsx`、`app/modules/page.tsx`、`sidebar-nav.tsx`、SDK Module 类型 | 现有后端已有 `GET /modules` | 可第一批并行；启停/安装不要混入。 |
| P1-MOD-02 | 模块 enable/disable/install/quarantine Web 操作 | 中 | 高 | Module Host/Core API lifecycle、SDK、Web 操作流、权限文档 | 需要后端动作契约和失败恢复语义 | 只读目录页合并后再做。 |
| P1-PROMPT-01 | 提示词资产只读浏览、搜索、artifact 查看 | 高 | 中 | `prompting-page.tsx`、prompting routes/types | 可基于现有 list/preview/artifact read | 可并行，但建议先按语义提取页面子组件，避免继续堆大文件。 |
| P1-PROMPT-02 | 提示词编辑、版本、发布、回滚、差异审查 | 中低 | 高 | Prompt API、应用包 YAML/JSON、DB 版本、Web 审查流、测试 | 需要决定“文件源”与“数据库版本源”的主从关系 | 单独契约 PR 后再实现。 |
| P1-COLLAB-01 | 协作 / PR Web 操作流 | 中高 | 中 | `collaboration-page.tsx`、PR 详情页、SDK review 类型 | 后端已有 create/review PR，主要补产品流 | 可并行；注意不要和大范围 SDK 类型改动同批合并。 |
| P1-RUNTIME-01 | 伪无限上下文 / 长任务等价交付 | 低 | 很高 | runtime kernel、evaluation runtime、prompting、LLM work analyzer、G4 suites | 和执行前确认、预算恢复、窗口压缩高度耦合 | 不建议与其他 runtime 改动并行合并；需要长线分支和强验收。 |
| P1-PACK-01 | 完整 Docker Compose 产品栈 | 中 | 高 | Dockerfiles、compose、ops launcher、health check、README/USER_GUIDE | 最终依赖数据卷、备份、删除边界和 provider 配置口径 | 可先做产品栈 skeleton；发布承诺等数据治理后再开。 |
| P2-DESK-01 | 桌面封装 / 托盘 / 自动更新 | 中 | 高 | 桌面 wrapper、ops launcher health manifest、发布文档 | 依赖本地产品启动器和数据管理 API | 可做原型；正式发行等待产品栈和数据治理。 |
| P3-SAAS-01 | 托管 / SaaS / 官方远端数据 | 低 | 很高 | auth、tenant、workspace、remote backup/delete、权限、法务文档 | 依赖数据治理、删除证明、租户模型、隐私/服务条款 | 近期只适合 RFC，不适合直接实现。 |
| P0-DOC-01 | 历史文档和废旧测试口径清理 | 中高 | 中 | `docs/DIRECTORY_REFERENCE.md`、README、USER_GUIDE、DEVELOPER_GUIDE、旧审计文档入口 | 容易和所有 PR 的文档更新冲突 | 设一个 docs owner；按阶段批量清理，不穿插在大功能 PR 里。 |

## 5. 推荐并行批次

### 第一批：低冲突解锁项

这些可以立即并行：

| 分支建议 | 内容 | 合并说明 |
| --- | --- | --- |
| `codex/api-proxy-methods` | Web API 代理补 `DELETE` / `PUT` / `PATCH` | 先合并，给后续控制面减少绕路。 |
| `codex/web-first-task-smoke` | Web-first 首任务 smoke 与必要错误提示 | 不重构 `task-launch-panel.tsx`。 |
| `codex/web-modules-catalog` | 只读模块目录页 | 只碰导航、类型和新页面。 |
| `codex/web-pr-flow` | 协作 PR 创建/查看/review 的 Web 流 | 只补产品流，不扩展后端大契约。 |
| `codex/provider-status-page` | provider 只读状态页和修复指引 | 不做 key 保存。 |

这批的合并顺序建议是：API 代理 -> SDK 类型小改 -> 新页面/测试 -> 文档索引。

### 第二批：先定契约再实现

这些可以并行讨论，但实现前必须先落契约：

| 分支建议 | 内容 | 必须先冻结的契约 |
| --- | --- | --- |
| `codex/data-deletion-contract` | 数据删除 dry-run 输出和对象归属清单 | 数据对象归属、删除范围、审计字段、不可删除项说明。 |
| `codex/prompt-asset-authoring-api` | 提示词编辑/版本/发布/回滚 API | 文件源与数据库版本源的权威关系。 |
| `codex/module-lifecycle-api` | 模块启停/安装/隔离控制面 | module host 失败恢复、权限和 quarantine 语义。 |
| `codex/provider-key-management` | provider key 保存与测试调用 | 密钥存储位置、加密/权限、导出和删除边界。 |

第二批不要抢先做复杂 UI。先把 API、类型、测试和文档口径合并，页面再接入。

### 第三批：必须隔离的大改

这些不应与其他大功能 PR 并行合并：

| 分支建议 | 内容 | 原因 |
| --- | --- | --- |
| `codex/task-confirmation-gate` | 执行前任务核对门禁 | 会改任务状态机、prompt、runtime、Web 启动和大量测试。 |
| `codex/long-task-parity` | 伪无限上下文和长任务等价交付 | 会改窗口压缩、恢复、评测和分析工具。 |
| `codex/product-compose-stack` | 完整 Docker 产品栈 | 会改启动方式、端口、health、文档和 CI。 |
| `codex/desktop-wrapper` | 桌面封装 | 依赖 product launcher 和数据治理；适合后置。 |
| `codex/saas-rfc` | 托管 / SaaS / 官方远端数据 | 近期只做 RFC；直接实现会过早引入租户和法务复杂度。 |

## 6. 合并热点文件

下列文件或目录需要避免多人同时大改：

| 热点 | 风险 |
| --- | --- |
| `apps/web/app/api/core/[...path]/route.ts` | 当前只导出 GET/POST；删除、设置、编辑类功能都会需要方法扩展。 |
| `packages/frontend-sdk/src/types.ts` | 所有新 API 都会改共享类型，容易产生机械冲突。 |
| `apps/web/app/components/sidebar-nav.tsx` | 新 settings/modules/data 页面都会改导航。 |
| `apps/web/app/components/task-launch-panel.tsx` | 首任务、provider、执行前确认都会碰。 |
| `apps/web/app/components/prompting-page.tsx` | 文件较大，提示词资产只读和编辑功能会高冲突。 |
| `apps/web/app/components/collaboration-page.tsx` | PR Web 流容易和协作页面整理冲突。 |
| `apps/web/app/components/task-detail-page.tsx` | 执行前确认、审批、runtimeControl 和任务分析都可能改。 |
| `apps/web/app/components/assets-page.tsx` | 素材导入、删除预览、数据治理可能交叉。 |
| `services/core-api/src/yggdrasil_core_api/services/runtime_service.py` | 当前混合 health、application config、modules 等逻辑；provider 设置和模块生命周期会冲突。 |
| `services/core-api/src/yggdrasil_core_api/services/task_service.py` | 删除、确认门禁、重试、启动状态都会碰。 |
| `services/core-api/src/yggdrasil_core_api/api/routes/*.py` | 新控制面 API 会集中落这里。 |
| `packages/python-sdk/src/yggdrasil_sdk/persistence/orm.py` | 删除审计、数据归属、SaaS 租户都会改 schema。 |
| `migrations/versions/*` | 多个迁移并行时最容易产生顺序和 revision 冲突。 |
| `package.json` | smoke、Docker、release check、产品启动都会改脚本。 |
| `README.md`、`docs/USER_GUIDE.md`、`docs/DEVELOPER_GUIDE.md`、`docs/DIRECTORY_REFERENCE.md` | 所有用户入口变更都要同步，文档冲突不可避免，需要单点整理。 |

## 7. 推荐合并顺序

1. 合并 API 代理方法、共享类型最小扩展、数据/设置/提示词契约文档。
2. 合并后端能力：删除 dry-run、provider 状态、模块生命周期、prompt authoring API。
3. 合并 Web 页面：settings、modules、data privacy、prompt asset、collaboration PR。
4. 合并 Web-first E2E 和 release smoke，把用户首次成功路径锁住。
5. 合并 Docker 产品栈和启动器 health manifest。
6. 合并历史文档和废旧测试清理，删除过时入口，不保留“旧设计兼容路径”。
7. 最后推进桌面封装、SaaS/远端数据和长任务等价交付这类高风险主线。

## 8. 对当前团队协作的操作建议

- 每个并行 PR 必须声明唯一主写入范围，尤其是 Web 大组件、SDK 类型和迁移目录。
- 新页面可以并行，新共享契约不要并行；共享契约必须先合并。
- 大组件改造只允许语义提取，例如把模块目录、提示词 artifact、PR 详情拆成业务组件；不要做 `part_a/part_b` 这类机械拆分。
- 数据删除、provider key 保存、SaaS 不做平滑兼容补丁；必须直接按新契约切换。
- 废旧测试应随废旧设计删除，不能继续在 release check 里表达旧路线。
- 每个涉及用户入口、端口、启动脚本、API 能力或目录迁移的 PR，都必须同步更新 `docs/DIRECTORY_REFERENCE.md`。

## 9. 本轮未完成事项

- 未运行 Web、Core API、Agent Runtime 或 Docker。
- 未跑 Playwright、pytest、evaluation 或 release check。
- 未验证两个后端/产品侧子代理的最终回包；本报告已基于本地静态证据和前端子代理结论先完成。
