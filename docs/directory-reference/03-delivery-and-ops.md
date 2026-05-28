## 分册 03：交付与运维

> 包含：evaluation、infra、migrations、tests、scripts、.github 等交付链路与运维相关目录。

## docs/ · 项目文档

```
docs/
├── PRD-v0.1.md                     # 产品需求文档 v0.1
├── DEVELOPER_GUIDE.md              # 开发指南（本套文档之一）
├── USER_GUIDE.md                   # 使用指南（本套文档之一）
├── DIRECTORY_REFERENCE.md          # 目录说明书（本文档）
├── QUALITY_BASELINE.md             # 质量基线：M8 benchmark 数字基准、API 延迟基准、稳定性门禁值与长任务伪无限上下文评测口径
├── P1_TEST_COVERAGE_INVENTORY.md   # P1 任务测试覆盖清单：31个测试全部通过，覆盖记忆树、窗口重启、接管协议、恢复链路完整闭环
├── P2_TASK_14_17_FILE_STATUS_AUDIT.md # P2 任务14-17 文件现状审计：成本预算检查、工具执行隔离、runtime metrics、safe-stop机制全景分析，6项关键缺失+6项重要缺失
├── development/                    # 开发专题文档目录（具体文件见顶层速览）
│   ├── WORLD_TREE_AGENT_WORKFLOW_CURRENT_VS_TARGET_2026_05_26.md
│   │                               #   世界树 Agent 当前工作逻辑 vs 目标工作逻辑：聚焦父节点强编排、有限线性 continuation 轨迹以及上下文在推进/失败/恢复/交付中的变化
│   ├── TASK_CHECKFLOW_AUDIT_AND_ALIGNMENT_2026_05_27.md
│   │                               #   任务核对流程审计与对齐：冻结“理解任务->形成计划->向发起者核对->再执行”流程，并标注当前实现缺口与分级推进建议
│   ├── WORLD_BUILD_INITIAL_AWAKENING_TASK_START_EXECUTION_2026_05_26.md
│   │                               #   世界构建、初次苏醒与任务级工作状态读取实施文档：把新三阶段规格翻译成 contracts/root_mount/execution_loop/prompting/takeover/snapshot/tests 的实现顺序
│   ├── TASK_WORLD_START_STATE_AND_TASK_RUNTIME_SPLIT_2026_05_26.md
│   │                               #   给低智商 code agent 的任务文档：把“起始状态 + 任务级工作状态读取”重构拆成明确步骤、禁止事项、测试命令与完成标准
│   ├── TASK_WORLD_START_STATE_RUNTIME_REWORK_FIXUP_2026_05_26.md
│   │                               #   给 code agent 的返工任务文档：针对验收残留问题，强制收口世界级/任务级边界、无损恢复判定和 TaskRuntimeState 唯一入口
│   ├── FEATURE_CLASSIFICATION_AND_PROMPT_CHECK_PLAN_2026_05_18.md
│   │                               #   功能形态分类与提示词功能检查计划：按纯代码 / 代码+提示词 / 纯提示词分类当前设计，并给出以纯提示词为重点的检查路径
│   └── ...                         #   其他开发专题文档同顶层速览
│
├── new/                            # 新方案草稿与当前重做输入材料
│   ├── 工作树.md                    # 新工作树方案：工作记忆、执行栈、LOD 下潜/上浮与 Working Node 标签
│   ├── 元提示词.md                  # 新 Boot Prompt 方案：I/O 绑定、根指针、行为宪法和现场恢复
│   └── 世界树计划正式项目定义.md    # 正式项目定义草稿与用户笔记：生命周期、根内容、能力、工具、工作树与分期
│
├── adr/                            # 架构决策记录 (Architecture Decision Records)
│   ├── README.md                   # ADR 索引
│   ├── ADR-0001-kernel-module-adapter.md    # 三层架构决策
│   ├── ADR-0002-monorepo-layout.md          # Monorepo 布局决策
│   ├── ADR-0003-postgresql-primary-store.md # PostgreSQL 选型决策
│   ├── ADR-0004-temporal-workflow.md        # Temporal 工作流决策
│   ├── ADR-0005-litellm-model-gateway.md    # LiteLLM 模型网关决策
│   ├── ADR-0006-plugin-extension.md         # 插件扩展机制决策
│   ├── ADR-0007-nats-outbox.md              # NATS 事件出箱决策
│   ├── ADR-0008-authorization.md            # 授权模型演进决策
│   └── ADR-0009-observability-evaluation.md # 可观测与评测决策
│
├── protocols/                      # 内部协议规格
│   ├── README.md                   # 协议索引
│   ├── event-contracts-v0.1.md     # 事件契约（NATS 事件格式；补充 context.restart.requested/completed payload 约束）
│   ├── hook-contracts-v0.1.md      # Hook 接口契约（所有 Hook 事件清单；补充 restart-snapshot rehydrate 约束）
│   ├── module-lifecycle-v0.1.md    # 模块生命周期协议（启动/停止/健康）
│   ├── yggdrasil-module-manifest-v0.1.md    # 模块清单 YAML 规格
│   └── yggdrasil-application-manifest-v0.1.md # 应用清单 YAML 规格
│
├── specs/                          # 数据与 API 规格
│   ├── README.md                   # 规格索引
│   ├── agent-runtime-protocol-v0.2.md       # Agent 运行时协议 v0.2：Boot Prompt、启动、待机、栈式运行、独立 mailbox、Fork 动态预算、结束批准与单路径运行
│   ├── work-tree-protocol-v0.2.md           # 工作树协议 v0.2：动态工作记忆、执行栈、Working Node 标签、WorkContextStack push/pop、摘要上浮与状态机
│   ├── world-build-awakening-task-start-protocol-v0.1.md # 世界构建、初次苏醒与任务启动协议：区分世界级学习与任务级工作状态读取，引入起始状态与无损恢复优先级
│   ├── runtime-domain-data-spec-v0.1.md     # 运行时、work tree、worker activity 与工具数据规格
│   └── asset-packaging-evaluation-data-spec-v0.1.md # 资产打包与评测数据规格
│
├── research/                       # 研究与探索性文档
│   ├── final-goal-roadmap-2026-04-30.md
│   │                               #   通向最终目标的阶段路线图：gate、功能开发簇、提示词成熟度与研究议程
│   ├── work-tree-protocol-draft-2026-05-05.md
│   │                               #   工作树研究草案：任务分解、优先图、熵增控制与阶段性重启的结构化定义
│   ├── hypergraph-reasoning-protocol-draft-2026-05-05.md
│   │                               #   超图推理研究草案：关系平铺、关系原因升维与模式识别的高阶推理方向
│   ├── real-user-validation-plan-2026-04-30.md
│   │                               #   参考版：真实用户验证计划的复用要点；原文已归档
│   ├── real-user-validation-baseline-freeze-2026-04-30.md
│   │                               #   参考版：材料冻结与口径锁定实践；原文已归档
│   ├── real-user-validation-internal-pilot-deepseek-2026-04-30.md
│   │                               #   参考版：内部试跑复盘模板；原文已归档
│   ├── g2-closeout-2026-05-15.md
│   │                               #   参考版：Gate 2 闭环结论与复用口径；原文已归档
│   ├── g3-closeout-2026-05-15.md
│   │                               #   参考版：Gate 3 闭环结论与复用口径；原文已归档
│   ├── g4-closeout-2026-05-15.md
│   │                               #   参考版：Gate 4 闭环结论与复用口径；原文已归档
│   ├── g4-assessment-and-roadmap-2026-05-15.md
│   │                               #   Gate 4 评估与完美实现路线图：多场景官方范围、few-shot 执行链、provider 矩阵与 CI 门禁
│   ├── g4-long-task-window-restart-baseline-2026-05-15.md
│   │                               #   Gate 4 长任务与窗口重启基线研究：LongCat 128k 基线、restart 闭环缺口、任务编排与 work tree 路线
│   ├── G4_WEB_RESEARCH_DEFAULT_FAILURE_AUDIT_2026_05_27.md
│   │                               #   G4 web research 默认入口失败审计：失败模式、读取链与后续修复建议
│   ├── pseudo-infinite-context-window-roadmap-2026-05-16.md
│   │                               #   伪无限上下文窗口研究与优先级路线：当前已确认 restart 技术闭环成立，但交付闭环仍待修正
│   ├── 系统核心理念.md
│   │                               #   记忆树系统的核心设计哲学说明
│   ├── 系统概念/
│   │   ├── Agent 核心设计.md
│   │   ├── Agent 其他设计.md
│   │   ├── Agent行为模式建议组.md
│   │   ├── 记忆树核心设计.md
│   │   └── 记忆树其他设计.md
│   │                               #   中文系统设计文档集合：Agent/记忆树的核心与扩展设计草案
│   ├── future/
│   │   └── Project-Yggdrasil 未来多模态潜空间智能体架构.md
│   │                               #   面向远期能力的前瞻研究草案，不纳入当前 Gate 承诺范围
│   ├── 归档/
│   │                               #   历史归档目录（按约定不在目录索引中展开文件列表）
```

---

## evaluation/ · 评测框架

```
evaluation/
├── fixtures/                       # 评测样本数据
│   ├── memory-tree/                # 记忆树操作的标准样本
│   ├── retrieval/                  # 检索质量评测样本
│   ├── task-execution/             # 任务执行的端到端样本
│   └── real-user-validation/       # 真实用户验证冻结材料（任务包、评分表、provider 可用性矩阵等；scorecard 模板现含 first_token_at/first_token_seconds、计划质量与返工字段，由 pilot-sandbox 命令复制到专用目录）
│       ├── live-task-pack-g2-r2.json
│       │                           #   2026-05-15 官方 G2 第 1 轮：YGG-CI-01 / YGG-CG-01 / YGG-CG-03 全量通过
│       ├── live-task-pack-g2-r3-stability.json
│       │                           #   2026-05-15 稳定性复跑第 2 轮：YGG-CG-01 / YGG-CG-03 通过
│       ├── live-task-pack-g2-r4-stability.json
│       │                           #   2026-05-15 稳定性复跑第 3 轮：YGG-CG-01 / YGG-CG-03 通过
│       └── scorecard-2026-05-15-g2-complete.csv
│                                   #   2026-05-15 官方 G2 汇总评分表：7 条 live 样本，CG-03 恢复成功率 100%
│
└── suites/                         # 评测套件定义
    ├── regression-m4-m6.json       # M4-M6 回归套件
    ├── m8-benchmark-memory-strategies.json # M8 离线基准套件
    ├── m8-live-llm.json            # M8 真实 LLM 评测套件
    ├── m9-acceptance.json          # M9 验收套件
    ├── m9-control-plane.json       # M9 控制面回归套件
    ├── g2-regression.json          # G2 受控自治回归套件（复杂文件拆分固定样本）
    ├── g4-multiscene.json          # G4 官方三场景离线套件（快任务/跨会话/恢复/隔离）
    ├── g4-provider-matrix.json     # G4 官方 live provider matrix（DeepSeek + LongCat；live artifact 现含 token 用量拆分、contextLengthObservations 与 runtimeMetrics）
    ├── g4-provider-matrix-longform.json
                                    #   G4 单任务长样本 live provider matrix（先聚焦一个更长的 coding 任务；用于观察长任务 token 与上下文窗口压力）
    ├── g4-real-task-externalized.json
                                    #   G4 默认真实任务入口（single-goal / externalized；用于正式 real-task 合同）
    ├── g4-real-task-unrelated-dual-live.json
                                    #   G4 无关任务双模型 live 入口（固定 unrelated incident RCA；LongCat 2 与 DeepSeek v4 Flash 同题对照，并强制 formal delivery footer 以穿过 delivery gate）
    ├── g4-real-task-web-research-default.json
                                    #   G4 默认真实任务入口（网络检索 + 多源对比 + 矛盾处理；strict 审计与 formal delivery footer）
    ├── g4-web-research-work-tree-long.json
                                    #   G4 web research 长任务入口（固定 LongCat live，强调多窗口 continuation 与工作树连续性）
    └── g4-real-task-work-tree-debug.json
                                    #   G4 真实任务工作树调试 harness（显式嵌套 takeoverProtocol，从 child 节点起步；当前目标已切到 child 先回父节点、父节点再决定 sibling/leaf 的编排语义，不再把 failure->sibling continuation 当默认目标）
```

**评测命令映射：**

| 命令 | 对应套件 |
|------|---------|
| `eval:regression` | `suites/regression-m4-m6.json` |
| `eval:m8:benchmark` | `suites/m8-benchmark-memory-strategies.json` |
| `eval:m8:live` | `suites/m8-live-llm.json` |
| `eval:m9:control-plane` | `suites/m9-control-plane.json` |
| `eval:m9:acceptance` | `suites/m9-acceptance.json` |
| `eval:g2:regression` | `suites/g2-regression.json` |
| `eval:g4:multiscene` | `suites/g4-multiscene.json` |
| `eval:g4:provider-matrix` | `suites/g4-provider-matrix.json` |
| `eval:g4:provider-matrix:longform` | `suites/g4-provider-matrix-longform.json` |
| `eval:g4:web-research:default` | `suites/g4-real-task-web-research-default.json` |
| `eval:g4:web-research:work-tree-long` | `suites/g4-web-research-work-tree-long.json` |
| `eval:g4:real-task-unrelated:dual-live` | `suites/g4-real-task-unrelated-dual-live.json` |
| `eval:g4:work-tree-debug` | `suites/g4-real-task-work-tree-debug.json` |

---

## infra/ · 本地基础设施

```
infra/
├── README.md                       # 基础设施使用说明（端口、环境变量、备份恢复）
├── docker-compose.yml              # 主基础设施栈
│                                   #   PostgreSQL 17 :5432
│                                   #   Redis 7.4 :6379
│                                   #   NATS JetStream :4222
│                                   #   MinIO :9000/:9001
│                                   #   Temporal :7233 + UI :8088
│                                   #   Jaeger :16686
│                                   #   OTel Collector :4318
├── langfuse-compose.yml            # Langfuse 本地观测栈（独立端口段，避免冲突）
│                                   #   Langfuse Web :3100
│                                   #   ClickHouse :18123
│                                   #   Langfuse MinIO :19090
└── otel-collector-config.yaml      # OTel Collector 配置（Traces → Jaeger + Debug）
```

---

## migrations/ · 数据库迁移

```
migrations/
├── env.py                          # Alembic 环境配置（SQLAlchemy 连接配置）
├── script.py.mako                  # 迁移文件模板
└── versions/                       # 迁移版本文件（按时间戳排序）
    ├── <timestamp>_initial_schema.py
    ├── <timestamp>_add_node_relations.py
    └── ...
```

**关联配置：**
- 根目录 `alembic.ini`：迁移工具主配置
- `packages/python-sdk/src/yggdrasil_sdk/persistence/orm.py`：ORM 模型（迁移的源）

**当前迁移头补充：**
- `migrations/versions/5f7c2e9a1b44_task_snapshot_runtime_pointer_fields.py`：为 task_snapshots 补 currentNodeId / workingNodeAnnotation / pcMemo / topFrameId / stackDigest，支撑 P1 的 v0.2 工作树恢复指针与 WorkContextStack 持久化。
- `migrations/versions/b6c1d7e92f44_align_json_columns_with_jsonb.py`：把后续几次 migration 中遗漏为 PostgreSQL `JSON` 的列补齐为 `JSONB`，消除 `alembic check` 的类型漂移。
- `migrations/versions/a91c2e7d4f33_memory_tree_worktree_audit_fields.py`：为 nodes / retrieval_requests / model_invocations / assets / prompt_compile_artifacts 补 work tree 审计字段，支撑“记忆树即全部记忆”的 snapshot、rehydrate 与多模态/关系发现闭环。

---

## tests/ · 集成测试

```
tests/
├── conftest.py                     # pytest 共享 Fixture：session 级 schema 初始化（单次），每 test 截断数据表并默认使用 memory coordination
├── fixtures/                       # 测试用固定样本数据
│
├── # ── 基础层测试 ────────────────────────────────────────
├── test_persistence_api.py         # 迁移索引文件（持久化 API 专项测试已拆分到 tests/api）
├── api/
│   ├── test_persistence_task_runtime_api.py
│   │                               # tasks/nodes/runtime/workbench 等基础 API 持久化与读取回归
│   ├── test_persistence_control_plane_api.py
│   │                               # 启停控制、资产/训练/prompt/mcp 控制面 API 回归
│   └── test_persistence_app_scope_api.py
│                                   # appId 过滤语义与 M9 control-plane suite 回归
├── test_prompting_runtime.py       # PromptCompiler 链路端到端
├── test_runtime_and_pruning.py     # 迁移索引文件（运行时/裁剪专项测试已拆分到 tests/runtime）
├── test_runtime_p4_foundation.py   # P4/P7 基础回归：work tree reducer、awaiting-approval、单路径运行态与 approval/revision 闭环
├── runtime/
│   ├── test_runtime_core_and_memory.py
│   │                               # 运行时核心挂载、上下文裁剪、记忆树物化与 memory-write 标签回归
│   ├── test_runtime_restart_and_resume.py
│   │                               # 窗口重启与 pause/resume 主闭环回归
│   ├── test_runtime_budget_and_audit.py
│   │                               # 预算硬约束、审计级别与 response 指标回归
│   └── test_runtime_pause_regressions.py
│                                   # pause 请求竞态回归、多轮 pause/resume 污染防护与 runtime metrics 计数回归
├── test_text_memory_and_adapters.py# 文本记忆模块与适配器集成
├── test_module_catalog.py          # 模块目录发现与注册
├── test_module_host_eventing.py    # 模块宿主事件总线集成
├── test_mcp_bridge.py              # MCP 协议桥接回归
├── test_support.py                 # 通用支持函数回归（含 CJK word_count 口径、workspace sandbox 复制边界）
├── test_deepseek_gateway.py        # DeepSeek V4 / thinking / 文档化 LLM 配置回归
├── test_memory_pipeline_api.py     # 记忆流水线 API 回归
├── test_subagent_and_worker.py     # Sub-Agent 与 Temporal Worker 集成（含 awaiting-approval/continuing、parent wake 与 work-tree 合并语义）
├── test_secret_hygiene.py          # 仓库凭据泄露与文档回归检查
│
├── # ── Phase 1 专项测试（质量巩固） ────────────────────────
├── test_phase1_permissions_and_errors.py
│   │                               #   Pause-Resume：执行中途 pause / resume 轮次一致性
│   │                               #   权限元组：read-only mount、exclusive-read、无权限 Space
│   │                               #   错误恢复：LLM 5xx 回滚、Redis 不可用、快照损坏
│
├── # ── Phase 3 专项测试（稳定性与边界） ─────────────────────
├── test_phase3_stability_and_scale.py
│   │                               #   规模：1000 节点检索延迟基准
│   │                               #   规模：10 万词 fragment 导入内存/时间上界
│   │                               #   并发：2 worker 同时 pause 不产生双重快照
│   │                               #   并发：Sub-agent 并发写同一 Space 不产生数据竞争
│   │                               #   Hook 故障隔离：单模块 hook 异常不影响其他模块
│
├── # ── M8/M9 里程碑测试 ─────────────────────────────────
├── test_m8_runtime.py              # M8：评测与运维基础回归（含评测/真实试跑沙箱隔离）
├── test_g4_multiscene.py           # G4：官方三场景 multiscene suite、real-task suite 约束与 local fallback 持久审计回归
├── test_m9_shared_memory.py        # M9：shared-memory 专项测试（含按 work tree 节点约束的写权限）
├── test_m9_pause_resume.py         # M9：pause-resume 专项测试
├── test_m9_multimodal_and_relations.py
│                                   #   M9：multimodal-memory + relation-discovery 专项测试（含资产/边的 work tree 溯源）
├── test_m9_memory_organizer.py     # M9：memory-organizer 专项测试
├── test_m9_training_lab.py         # M9：training-lab 专项测试
└── test_m9_acceptance.py           # M9：端到端验收测试 + 控制面 API 回归
```

**pytest 标记说明：**

| 标记 | 含义 | 运行时机 |
|------|------|---------|
| （无标记） | 快速单元 / 集成测试，使用 SQLite | PR、merge |
| `slow` | 慢的运行时闭环 / 控制面 API / 评测回归测试 | 仅在相关改动需要时手动执行，或发布前全量检查中统一处理 |

---

## scripts/ · CI 辅助脚本

```
scripts/
├── analyze_llm_work_run.py        # LLM 工作分析脚本包装器：按 task/run/invocation 生成 run/window/turn/tool/artifact/source 报告
├── analyze_langfuse_real_task_trace.py # Langfuse trace 分析：恢复真实任务最终输出、结论段与逐窗口快照/工作树历史
├── analyze_langfuse_real_task_trace_layered.py # Langfuse 文本审查兼容入口：输出 prompt/output 摘录、重复窗口文本簇和 Langfuse UI 审查焦点
├── analyze_langfuse_real_task_execution_audit.py # Langfuse 文本审查主入口：面向 Langfuse 文字交互分析的报告生成器，内部可接本地状态增强
├── render_live_audit_export.py     # live audit 导出包渲染器：把 evaluation/request/response/window-executions/spans/outbox 汇总成人类可读 Markdown 报告和离线 HTML 浏览页
├── check_migrations.sh             # 验证 Alembic 迁移头与 ORM 模型一致
│                                   #   启动临时 pgvector 容器 → alembic upgrade head
│                                   #   → alembic check（检测 ORM 漂移）
├── smoke_test.sh                   # Compose 冒烟测试：启动 infra stack，调 core-api /health
│                                   #   启动 postgres/redis/nats/minio → alembic upgrade head
│                                   #   → 启动 core-api → GET /health
├── safe_shutdown.sh                # 向 worker 进程发送 SIGTERM，等待安全关闭检查点保存（Linux/macOS）
└── safe_shutdown.ps1               # 同上，Windows PowerShell 版本
```

**运行方式：**
```bash
bash scripts/check_migrations.sh   # 需要 docker，约 30 s
bash scripts/smoke_test.sh         # 需要 docker compose，约 60 s
```

---

## .github/ · GitHub Actions CI

```
.github/
└── workflows/
    ├── pr.yml      # PR smoke（触发：pull_request）
    │               #   Python syntax smoke + web lint/typecheck/build
    │               #   目标：只拦明显语法/构建损坏，约 3-5 min
    │
    ├── ci.yml      # merge smoke（触发：push to main）
    │               #   Python syntax smoke + web lint/typecheck/build
    │               #   目标：主干低成本冒烟，约 3-5 min
    │
    └── release-check.yml # 发布前手动全量检查（触发：workflow_dispatch）
                          #   migration-check：check_migrations.sh（ORM 漂移检测）
                          #   smoke-test：smoke_test.sh（端到端 /health 验证）
                          #   full-regression：release:check（SQLite 全量回归 + 评测 + web）
                          #   postgres-regression：pytest --postgres -m "not slow"
                          #   live-provider-smoke：可选输入，按需触发 eval:m8:live
                          #   g4-provider-matrix：可选输入，按需触发 eval:g4:provider-matrix
```

**当前测试/门禁策略：**

| 层级 | 触发 | 跳过内容 | 耗时 |
|------|------|---------|------|
| 本地开发 | 每次改动后 | 全仓回归、PostgreSQL、benchmark、live smoke | 按受影响测试而定 |
| PR | pull_request | 全仓 Python 测试、评测、docker | ~3-5 min |
| merge | push to main | 全仓 Python 测试、评测、docker | ~3-5 min |
| release-check | 手动 | 默认不跑 live provider smoke / G4 provider matrix（可选开启） | ~30-60 min |

---

