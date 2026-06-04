## 分册 04：配置与速查

> 包含：根目录配置文件、docs 技术治理补充、文件查找速查。

## 根目录配置文件

| 文件 | 用途 |
|------|------|
| `pyproject.toml` | Python UV 工作区根配置，声明所有子工作区成员，Ruff 代码检查规则 |
| `package.json` | Node.js/pnpm 根配置，定义所有 `pnpm` 脚本命令 |
| `pnpm-workspace.yaml` | pnpm Monorepo 工作区成员声明 |
| `tsconfig.base.json` | TypeScript 基础配置，所有前端包继承 |
| `alembic.ini` | Alembic 数据库迁移工具主配置 |
| `pytest.ini` | pytest 运行配置（测试发现规则、标记定义） |
| `uv.lock` | Python 依赖锁定文件（不要手动修改） |
| `pnpm-lock.yaml` | Node.js 依赖锁定文件（不要手动修改） |
| `LLM.txt` | LLM 配置说明文档；运行时代码不会读取此文件，真实凭据只通过环境变量注入 |
| `docs/research/README.md` | research 目录组织导航：按用途分类为路线图、项目评估、完成报告、规范设计、技术分析和历史归档 |
| `docs/development/WORLD_BUILD_INITIAL_AWAKENING_TASK_START_EXECUTION_2026_05_26.md` | 世界构建、初次苏醒与任务级工作状态读取实施文档：把新三阶段口径压成实现层计划，明确本轮先做运行时分层，不在这一轮实现完整世界编译流水线 |
| `docs/development/TASK_WORLD_START_STATE_AND_TASK_RUNTIME_SPLIT_2026_05_26.md` | 给 code agent 的执行任务文档：用不可误解的顺序指挥粗粒度代码改造，覆盖 contracts/root_mount/execution_loop/prompting/takeover/snapshot 与三组关键测试 |
| `docs/development/TASK_WORLD_START_STATE_RUNTIME_REWORK_FIXUP_2026_05_26.md` | 给 code agent 的返工任务文档：针对验收发现的残留问题，要求世界级阶段彻底不见任务信息、只有真实最近现场才能无损恢复，并让 TaskRuntimeState 成为唯一任务态入口 |
| `docs/development/WORLD_TREE_AGENT_WORKFLOW_CURRENT_VS_TARGET_2026_05_26.md` | 世界树 Agent 当前工作逻辑 vs 目标工作逻辑：从世界树 agent 视角整理“父节点强编排、child 回编排父节点、有限线性轨迹、awaiting-approval 收口”的正式目标链路 |
| `docs/development/TASK_CHECKFLOW_AUDIT_AND_ALIGNMENT_2026_05_27.md` | 任务核对流程审计与对齐：冻结“理解任务->形成计划->向发起者核对->再执行”的目标流程，并对照当前协议/提示词/运行时/测试的缺口 |
| `docs/specs/agent-runtime-protocol-v0.2.md` | Agent 运行时协议 v0.2：本轮继续把“启动”细化为“初次苏醒形成起始状态 + 任务级单独读取工作状态”，并补上工具/知识索引优先的正式口径 |
| `docs/specs/work-tree-protocol-v0.2.md` | 工作树协议 v0.2：本轮继续把工作树边界收紧为任务级正式对象，强调 `[ID: 003 我要干什么]` 在建世界/初次苏醒阶段只保存协议与入口，不直接携带具体任务工作树 |
| `docs/specs/world-build-awakening-task-start-protocol-v0.1.md` | 世界构建、初次苏醒与任务启动协议 v0.1：把通用 Agent 的建世界、一次性初次苏醒、起始状态、任务开始和无损恢复顺序拆成正式规则，并进一步收紧为“工具/知识索引优先、能力/知识节点可关联工具节点、开始工作前必须先读取工作状态”的正式口径 |
| `docs/new/世界树计划正式项目定义.md` | 世界树计划正式项目定义草稿与用户笔记：以 LLM 为核心，将代码定位为服务 LLM 的世界环境，并明确代码只做边界与警戒 |
| `docs/new/工作树.md` | 新工作树方案：定义工作树节点 schema、LOD 拓扑、状态流转、父节点强编排、有限线性 continuation 轨迹和 Working Node 标签 |
| `docs/new/元提示词.md` | 新元提示词/Boot Prompt 方案：启动时完成 I/O 绑定、根指针寻址、行为宪法和程序计数器恢复，并要求 continuation 优先沿父节点编排位置继续 |
| `docs/LLM_WORK_ANALYZER_USER_GUIDE.md` | LLM 工作分析器用户手册：说明 Web 页面入口、完整分析页的七个主层次、CLI/API 用法和推荐排障流程，并固定 work-tree debug、时间线、cache trace、child bubble 与 mixed outcome 的读法 |
| `docs/research/specifications/系统核心理念.md` | 记忆树系统的核心设计哲学说明 |
| `docs/research/roadmaps/pseudo-infinite-context-window-roadmap-2026-05-16.md` | 伪无限上下文窗口研究：理论依据、当前缺口、100 次窗口重启/压缩评测 |
| `docs/research/project-assessments/g4-long-task-window-restart-baseline-2026-05-15.md` | G4 长任务基线研究：LongCat 窗口、restart 闭环缺口、任务编排与 work tree 最小落地路线 |
| `docs/development/G4_WEB_RESEARCH_DEFAULT_FAILURE_AUDIT_2026_05_27.md` | G4 web research 默认入口失败审计 |
| `docs/research/technical-analysis/memory-tree-agent-work-breakdown-2026-05-16.md` | 记忆树 Agent 全工作拆分研究：26 个最小可推进子任务 |
| `docs/research/roadmaps/memory-tree-agent-executable-roadmap-2026-05-16.md` | 记忆树 Agent 可执行路线图 |
| `docs/research/completion-reports/P2_VERIFICATION_AND_P3_DELIVERY_2026_05_17.md` | P2 执行结果验证与 P3 完成报告 |
| `docs/research/technical-analysis/runtime-two-failures-summary-2026-05-17.md` | 运行时两个失败用例摘要 |
| `docs/research/project-assessments/memory-tree-effect-report-2026-05-17.md` | 记忆树效果详细报告 |
| `docs/research/specifications/concepts/` | Agent / 记忆树中文系统设计文档集合 |

| `todo.md` | 开发里程碑、阶段完成度与工作台优先事项追踪 |

---

## docs/ 补充 · 技术治理文档

```
docs/
├── ANTI_TECH_DEBT.md               # 防技术债开发规范：文件规模限制、异常处理规范、质量基线要求、
│                                   #   PR 检查清单、存量技术债清理计划（TD-01 ~ TD-09）
│                                   #   （2026-05-04 首版）
└── ...（其他文档同上）
```

---

## 文件查找速查

| 我想找… | 去哪里找 |
|---------|---------|
| 任务执行的核心逻辑（含记忆树物化检索、memory-write 标签写树与窗口重启主循环） | `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop/` |
| LLM 调用与模型路由 | `packages/python-sdk/src/yggdrasil_sdk/llm_runtime/` |
| Prompt 编译逻辑 | `packages/python-sdk/src/yggdrasil_sdk/prompting.py` |
| 某个 API 路由实现 | `services/core-api/src/yggdrasil_core_api/api/routes/<resource>.py` |
| 某个 API 的业务逻辑 | `services/core-api/src/yggdrasil_core_api/services/<resource>_service.py` |
| 数据库 ORM 模型 | `packages/python-sdk/src/yggdrasil_sdk/persistence/orm.py` |
| 数据契约/Pydantic 模型 | `packages/python-sdk/src/yggdrasil_sdk/contracts.py` |
| 领域对象定义 | `packages/python-sdk/src/yggdrasil_sdk/domain.py` |
| Hook 事件清单 | `docs/protocols/hook-contracts-v0.1.md` |
| 模块清单格式规格 | `docs/protocols/yggdrasil-module-manifest-v0.1.md` |
| 某个模块的实现 | `modules/<module-name>/src/<package>/plugin.py` |
| 基础设施端口配置 | `infra/README.md` 或 `infra/docker-compose.yml` |
| 本地产品一键启动 | `corepack pnpm yggdrasil:up` / `packages/python-sdk/src/yggdrasil_sdk/ops_runtime/launcher.py` |
| 发布模式、演示、隐私边界和远端计划 | `apps/web/app/components/release-page.tsx`、`apps/web/app/release/page.tsx`、`docs/development/PRODUCT_PACKAGING_AND_REMOTE_DATA_REQUIREMENTS_GAP_2026_06_04.md` |
| 前端页面 | `apps/web/app/<page>/page.tsx` |
| 评测套件定义 | `evaluation/suites/*.json` |
| 质量基线与延迟门禁值 | `docs/QUALITY_BASELINE.md` |
| 架构决策理由 | `docs/adr/ADR-<number>-*.md` |
| CI 工作流定义 | `.github/workflows/{pr,ci,release-check}.yml` |
| Alembic 迁移一致性检查 | `scripts/check_migrations.sh` |
| 端到端冒烟测试 | `scripts/smoke_test.sh` |

