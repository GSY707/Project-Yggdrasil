| `docs/development/WORLD_TREE_AGENT_WORKFLOW_CURRENT_VS_TARGET_2026_05_26.md` | 世界树 Agent 当前工作逻辑 vs 目标工作逻辑（2026-05-26）：冻结“父节点强编排、child 完成/失败先回编排父节点、允许有限线性 continuation 轨迹、leaf 拆分尽量交给 LLM、根节点停在 awaiting-approval”的目标口径 |
| `docs/development/LLM_WORK_ANALYZER.md` | LLM 工作分析器设计与使用说明：说明 run-first 分析器的数据源、粒度、持久化位置、API/CLI 入口与当前限制 |
| `docs/LLM_WORK_ANALYZER_USER_GUIDE.md` | LLM 工作分析器用户手册：面向任务操作者和评测/排障同学，说明 Web、CLI、API 入口与常见排查流程；当前已补齐 work-tree debug 摘要卡、时间线、cache trace、child bubble 与 mixed outcome 的固定读法 |
| `docs/development/REAL_TASK_TEST_CONVENTIONS_AND_WORK_TREE_BACKLOG_2026_05_25.md` | 真实任务测试约定与工作树后续任务拆分（2026-05-25）：冻结“默认真实任务应单目标、弱项目内生化、由 agent 自主规划”的出题约定，并记录 P1/P2/P3/P5 本轮收口状态 |
| `docs/development/WORK_TREE_REAL_TASK_DEBUG_BASELINE_2026_05_25.md` | 工作树真实任务调试基线（2026-05-25）：把“父节点强编排”的工作树目标冻结成真实任务调试模型，并把验收重点转到 child 先回父节点、父节点再决定 sibling/leaf 的路径 |
| `docs/development/ROOT_PROMPT_STARTUP_WORKFLOW_REWORK_EXECUTION_2026_05_23.md` | 提示词、启动流程、工作流程重做执行文档（2026-05-23）：基于 `docs/new/` 三份新方案，给出 Boot Prompt、父节点强编排的工作树 v0.2、有限线性 continuation 轨迹、启动恢复、运行循环、记忆冲突、多 Agent 与验收门禁的落地步骤 |
| `docs/development/WORLD_BUILD_INITIAL_AWAKENING_TASK_START_EXECUTION_2026_05_26.md` | 世界构建、初次苏醒与任务级工作状态读取实施文档（2026-05-26）：把新三阶段规格翻译成实现层执行计划，明确 root mount 只做世界级/起始状态挂载，任务级工作状态单独读取，并给出 contracts/root_mount/execution_loop/prompting/takeover/snapshot/tests 的落地顺序 |
| `docs/development/TASK_WORLD_START_STATE_AND_TASK_RUNTIME_SPLIT_2026_05_26.md` | 给低智商 code agent 的任务文档（2026-05-26）：用严格顺序把“起始状态 + 任务级工作状态读取”重构拆成明确待办、测试命令、完成标准和禁止事项，适合直接转交做粗活 |
| `docs/specs/agent-runtime-protocol-v0.2.md` | Agent 运行时协议 v0.2：继续向新三阶段口径收口，补上“初次苏醒形成起始状态、任务级单独读取工作状态、工具/知识索引优先”的关键约束，同时保留 Boot Prompt、RootMountPackage、上下文窗口和结束批准的正式结构 |
| `docs/specs/work-tree-protocol-v0.2.md` | 工作树协议 v0.2：继续向任务级工作状态口径收口，明确工作树是在任务开始并读取工作状态后挂载到 `[ID: 003 我要干什么]` 语义根下的动态执行栈与工作记忆 |
| `docs/specs/world-build-awakening-task-start-protocol-v0.1.md` | 世界构建、初次苏醒与任务启动协议 v0.1：把“先建世界 / 再醒来 / 再开始工作”拆成世界级与任务级两层，强调建世界与初次苏醒不得接触具体工作信息，并进一步冻结“工具/知识索引优先、能力/知识到工具的关联召回、起始状态、无损恢复和分层诊断”规则 |
| `docs/new/工作树.md` | 新工作树方案：把工作树定义为“我要干什么”分支下的动态工作记忆与执行栈，并明确父节点强编排、有限线性 continuation 轨迹和 child 摘要上浮 |
| `docs/new/元提示词.md` | 新元提示词/Boot Prompt 方案：启动时只做 I/O 绑定、根指针寻址、行为宪法和现场恢复，并要求 continuation 优先沿父节点编排位置和最近线性轨迹继续 |
| `docs/new/世界树计划正式项目定义.md` | 世界树计划正式项目定义草稿与用户笔记：以 LLM 为核心重新定义生命周期、根内容、能力、工具、工作树、上下文窗口、多 Agent、邮箱和分期，并明确代码只做边界与警戒 |
| `docs/research/project-assessments/memory-tree-theory-gap-assessment-2026-05-17.md` | 记忆树理论目标差距评估（2026-05-17）：围绕"全部记忆上树、窗口仅最小子任务工作集"给出实现现状、主要差距与量化结论（综合完成度 59/100，差距 41/100） |
| `docs/research/specifications/P2_IMPLEMENTATION_SPEC_2026_05_17.md` | P2 推理执行稳态化详细代码实现规范入口（已拆分索引）：聚合任务14/15/16/17与集成验收导航 |
| `docs/research/specifications/P2_TASK14_LLM_BUDGET_SPEC_2026_05_17.md` | P2 任务14实现规范：LLM 调用与预算治理（预检/后检、硬 fail 边界、budgetCheckResult） |
| `docs/research/specifications/P2_TASK15_TOOL_ROUND_SPEC_2026_05_17.md` | P2 任务15实现规范：工具调用执行回合（failure 隔离、重试边界、round toolFailures） |
| `docs/research/specifications/P2_TASK16_RUNTIME_METRICS_SPEC_2026_05_17.md` | P2 任务16实现规范：runtime metrics 快照与工件导出（统一口径、窗口对比） |
| `docs/research/specifications/P2_TASK17_SAFE_STOP_SPEC_2026_05_17.md` | P2 任务17实现规范：安全停止与可恢复断点（pending action checksum、恢复验证） |
| `docs/research/specifications/P2_IMPLEMENTATION_INTEGRATION_GUIDE_2026_05_17.md` | P2 任务14-17集成与验收指南：跨任务集成清单、验收门槛、测试路径 |
| `docs/research/specifications/P2_IMPLEMENTATION_CHECKLIST_2026_05_17.md` | P2 任务14-17 快速参考实现检查清单：文件修改位置、关键代码片段行号、集成顺序、验收标准、常见错误提示 |
| `docs/research/completion-reports/P2_COMPLETION_SUMMARY_2026_05_17.md` | P2 阶段完成总结（2026-05-17）：全部4任务完成✅、28/28测试通过✅、代码修改清单、架构兼容性分析、后续行动计划、质量指标统计 |
| `docs/research/technical-analysis/sqlite-concurrency-ops-queue-2026-05-17.md` | SQLite 并发优化研究（2026-05-17）：锁告警成因、操作队列适配性、可放开锁策略边界、事务瘦身与批量写建议、分阶段性能提升路线 |
| `docs/development/HIGH_CONCURRENCY_TABLE_PLAYBOOK.md` | 高并发表使用与迁移说明：操作队列键策略、事务瘦身原则、索引迁移项、并发基准执行方式与注意事项 |
| `docs/development/LARGE_FILE_SPLIT_REPORT_2026_05_17.md` | 大文件扫描与拆分报告（2026-05-17）：扫描口径、拆分结果、验证命令与后续建议 |
| `docs/development/LLM_REAL_TASK_INFINITE_CONTEXT_EVAL_2026_05_17.md` | LLM 真实任务无限上下文能力评估（2026-05-17，已纠偏）：基于 Langfuse trace 的 LLM 最终输出、任务目标对照、4 条路径结果分叉与逐窗口分析 |
| `docs/development/LANGFUSE_TRACE_DATA_LOSS_AUDIT_2026_05_18.md` | Langfuse trace 数据损耗审计（2026-05-18）：对比本地 runtime 工件、Langfuse observation 与五层分析程序的保留字段、缺失字段，以及中间窗口重复的 runtime 根因 |
| `docs/development/MEMORY_TREE_INFINITE_CONTEXT_OPTIMIZATION_PLAYBOOK_2026_05_18.md` | 记忆树与伪无限上下文窗口优化作战手册（2026-05-18，已补全执行版）：除总体路线外，现已包含执行状态矩阵、当前仓库分析结论、优化优先级、窗口审计命令和具体下一步实现顺序 |
| `docs/development/FEATURE_CLASSIFICATION_AND_PROMPT_CHECK_PLAN_2026_05_18.md` | 功能形态分类与提示词功能检查计划（2026-05-18）：按纯代码 / 代码+提示词 / 纯提示词分类当前设计，并给出以纯提示词为重点的检查路径 |
| `packages/python-sdk/src/yggdrasil_sdk/llm_work_analysis.py` | LLM 工作分析核心：以 run 为主键拼接 DB 与 state 工件，输出 run/window/turn/tool/artifact/source 多粒度分析，并持久化到 `state/analysis/llm-work/` |
| `packages/python-sdk/src/yggdrasil_sdk/langfuse_trace_layered_analysis.py` | Langfuse 文本审查模块：以 Langfuse observation 重建窗口骨架，默认输出 LLM 交互文本摘录、重复窗口文本簇和 Langfuse UI 审查焦点；当前已能补读 `runtime/window-executions` 本地工件，用结构化窗口状态增强重复窗口判定与因果分析，并兼容中文化的任务目标/任务说明/当前焦点标签提取 |
| `scripts/analyze_llm_work_run.py` | LLM 工作分析脚本包装器：按 task/run/invocation 触发正式分析器，并输出 JSON 或 Markdown 报告 |
| `scripts/analyze_langfuse_real_task_trace.py` | Langfuse 真实任务窗口分析脚本：按 trace 提取 LLM 最终输出、第 6 节结论与逐窗口 snapshot/work tree 历史 |
| `scripts/analyze_langfuse_real_task_trace_layered.py` | Langfuse 文本审查兼容入口：按 trace 生成 LLM prompt/output 摘录、重复窗口文本簇和 Langfuse UI 审查焦点 |
| `scripts/analyze_langfuse_real_task_execution_audit.py` | Langfuse 文本审查主入口：按 trace 生成 LLM 交互文本视图，并在内部复用窗口冗余判定与本地状态增强逻辑 |
| `scripts/benchmarks/sqlite_concurrency_benchmark.py` | SQLite 并发基准单 profile 执行脚本：支持 baseline/optimized 配置、节点写入与快照争用场景测试、JSON 结果输出 |
| `scripts/benchmarks/sqlite_concurrency_compare.py` | SQLite 并发前后对比脚本：串行运行 baseline 与 optimized，输出吞吐/p95/锁错误对比报告 |
| `migrations/versions/7ad7d9b8c4f1_runtime_mailbox_side_channel_tables.py` | Runtime 邮箱/侧信道迁移：新增 `mailbox_messages` 与 `side_channel_events` 表及其索引，补齐 P6 持久化落库 |
| `migrations/versions/6c4e1f2b8a77_prompt_compile_boot_sections.py` | Prompt 编译工件迁移：为 `prompt_compile_artifacts` 增加 `boot_sections`，持久化 Boot Prompt 四段 |
| `migrations/versions/1e3a7b8c9d01_high_concurrency_indexes.py` | 高并发表索引迁移：nodes/import_fragments/task_snapshots/model_invocations 复合索引 |
# 世界树计划 · 目录说明书

> 项目完整目录结构及各路径的职责说明。适合新加入的开发者理解代码组织方式，以及查询特定功能所在位置。（2026/5/26 更新：`docs/new/世界树计划正式项目定义.md`、`docs/new/工作树.md`、`docs/new/元提示词.md`、`docs/specs/agent-runtime-protocol-v0.2.md`、`docs/specs/work-tree-protocol-v0.2.md`、`docs/development/ROOT_PROMPT_STARTUP_WORKFLOW_REWORK_EXECUTION_2026_05_23.md`、`docs/development/WORK_TREE_REAL_TASK_DEBUG_BASELINE_2026_05_25.md` 与 `docs/development/WORLD_TREE_AGENT_WORKFLOW_CURRENT_VS_TARGET_2026_05_26.md` 已统一收口到新目标：父节点强编排、child 完成/失败先回编排父节点、允许有限线性 continuation 轨迹、leaf 拆分尽量交给 LLM、代码只做边界与警戒、根节点仍以 `awaiting-approval` 收口；同日继续落下首轮实现推进：`runtime_kernel/takeover.py` 已把 child 完成/失败后的默认路径改为先回编排父节点，`execution_loop_part_a.py` 新增 `work-node-enter` 助手标签以支持父节点显式进入已有 child，`tests/test_runtime_p4_foundation.py` 已改成锁住 `child -> parent re-orchestrate -> existing child -> parent -> awaiting-approval` 的新路径。2026/5/25 更新：测试环境默认通过 `tests/conftest.py` 关闭 `LANGFUSE_TRACING_ENABLED`，并在 `README.md` 基础验证章节补充“跑测试前先启动 OTel Collector”的备注，避免导出端点不可达带来的额外等待；同日更新：新增 `llm_work_analysis.py` 作为正式 LLM 工作分析器，按 run 拼接 DB 与 state 工件并产出 run/window/turn/tool/artifact/source 多粒度分析；`scripts/analyze_llm_work_run.py` 与 core-api `/runtime/analysis/runs`、`/tasks/{taskId}/analysis/latest` 已接入这一能力，用于评测与调试；同日继续更新：新增 `REAL_TASK_TEST_CONVENTIONS_AND_WORK_TREE_BACKLOG_2026_05_25.md`，正式冻结“默认真实任务应尽量弱项目内生化、单目标、由 agent 自主规划”的出题约定，并把工作树后续工作拆成测试合同、门禁闭环、缓存、硬化、观测五类任务包；此前 2026/5/24 更新：`runtime_kernel/takeover.py` 已从初始化器升级为正式 reducer，负责 work tree/context stack 推进、revision reopen 与 approval finalize；`execution_loop_transitions.py` 已形成完整 P4 闭环：根节点完成进入 `awaiting-approval`，并通过控制面 approve/revision 闭环；`execution_loop_part_a.py` / `execution_loop_part_b.py` 现已支持以 `work-node-create` 助手输出标签在正式主循环里动态扩树、在 retrieval 查询中优先使用 work tree 当前节点语义，并在异常/预算失败时把当前节点写回 `failed + failureSummary`；`execution_loop_transitions.py` 还会为 continuation/pause/restart 输出独立 `workContextStackRef` 栈快照引用；P5 现已补齐并发安全闭环：`tool_runtime.py` 会向正式工具透传 `sourceWorkTreeNodeId`，`modules/text-memory/` 暴露 `read_node` / `read_index` / `update_memory_with_version` / `append_memory_log` / `submit_memory_proposal` / `forget_node` 等正式记忆工具，`append_memory_log` 现通过仓储层原子追加避免并发日志静默覆盖，`prompting.py` 也已明确“正式记忆工具优先、`<memory-write>` 旁路次之”，并在宽节点或高冲突场景优先引导创建细分子节点做空间隔离；P6 已完成闭环：`collaboration_runtime_part_a.py` / `collaboration_runtime_part_b.py` 不仅为 sub-agent launch/worker/PR manifest 透传 `workTreeNodeId` 与 `subagentBudgetDecision`，还会把 child completion summary 合并回 parent work tree 与 `childCompletionSummaries`，再通过独立 `mailbox_messages` / `side_channel_events` 持久化表、对应 Alembic 迁移 `7ad7d9b8c4f1_runtime_mailbox_side_channel_tables.py`、`runtime/tasks/{taskId}/mailbox` / `side-channel` API 和 `execution_loop_part_b.py` 的 mailbox 注入路径唤醒 parent 继续汇总；`runtime_kernel/root_mount.py` 现在优先从仓储读取 mailbox state 并返回 `mailboxMessages`，`takeover.py` 也已补齐 `load_persisted_work_context_stack()` 与 parent merge helper；`services/core-api/.../tasks.py` 与 `services/agent-runtime/app.py` 新增 `approve-completion` / `request-revision` 路由，`runtime_service.py` 暴露 `canApprove/canRequestRevision/recommendedRevisionNodeId`；`packages/frontend-sdk/src/types.ts` 与 `apps/web/app/components/task-detail-page.tsx` 现已把这些运行时控制字段、mailbox state/message 和 side-channel event 正式接到任务详情页；P7 门禁已统一到单路径：`tests/test_runtime_p4_foundation.py` 覆盖显式传递与默认请求两种入口，均进入 `awaiting-approval`，不再保留 legacy `completed` 快速路径；`prompting.py` 会把 `work_context_stack` 和 `childCompletionSummaries` 暴露给模型；`contracts.py` 修复了显式 root-only v0.2 work tree 被错误包裹成自引用 root 的兼容升级问题。此前 2026/5/24 更新：`runtime_kernel/root_mount.py` 现已输出中文语义根指针、`SYS_ROOT_PROTOCOL`、启动加载顺序、tool/capability index、mailbox/standby 状态与 `startupMode`，`execution_loop_part_b.py` 在 retrieval 前优先恢复 `currentNodeId/Working_Node/pcMemo`、对无活动工作 `start` 直接走 `standby` 短路，并把损坏 snapshot 的 blocker 持久化；`execution_loop_transitions.py` 在根节点交付时切到 `awaiting-approval`，并要求 work tree 节点先写 `executionSummary`；2026/5/23 更新：补充提示词、启动流程、工作流程重做执行文档、`docs/new/` 三份新方案入口，以及 Agent 运行时/工作树 v0.2 正式规格；2026/5/18 更新：补充“功能形态分类与提示词功能检查计划”文档入口；2026/5/17 已完成开发相关大文件治理，`P2_IMPLEMENTATION_SPEC_2026_05_17.md` 已拆分为任务14/15/16/17与集成验收五份子文档；`tests/test_runtime_and_pruning.py` 已按主题拆分至 `tests/runtime/` 下 4 个文件；`tests/test_persistence_api.py` 已按 API 主题拆分至 `tests/api/` 下 3 个文件；`execution_loop.py`、`llm_runtime.py`、`ops_runtime_live.py`、`collaboration_runtime.py` 已改为兼容门面并拆分到 part 文件。）
> 2026/5/26 本轮继续同步：`prompting.py` 的 response requirements 已增强任务编排引导，明确 root 默认负责编排与最终汇总、天然可拆的任务优先下放 child、child 只处理单一局部目标并回父节点交摘要、同一节点连续恢复/重启时优先继续拆分而不是反复在 root 硬写整份交付；`tests/test_prompting_runtime.py` 已补断言锁住这些引导。此前 2026/5/26 同步：新增 `evaluation/suites/g4-real-task-unrelated-dual-live.json` 与 `eval:g4:real-task-unrelated:dual-live`，把“先用与本项目完全无关的题目观察真实执行过程”固定成正式入口；当前题面为外部 incident RCA，同题分别跑 `longcat / LongCat-2.0-Preview` 与 `deepseek_direct / deepseek-v4-flash`，并在主报告后强制追加 formal delivery footer（`## 结果` / `## 证据` / `## 风险` / `## 已知问题`），避免 unrelated live run 先被 runtime delivery gate 截断。此前 2026/5/26 同步：`execution_loop_part_b.py` 已恢复 root/single-path overflow 的 carry-forward restart snapshot 续跑，`tests/runtime/test_runtime_restart_and_resume.py` 与 `tests/test_g4_multiscene.py` 已改成锁住 `window-restart-queued` 闭环；`execution_loop_transitions.py` 现对 `delivery-gate-blocked` 增加一次限次纠偏续跑，`tests/test_runtime_p2_delivery_gate.py` 新增“误停补一轮可恢复、二次仍缺段才失败”回归。此前 2026/5/25 同步：`evaluation/suites/g4-real-task-externalized.json` 已作为默认真实任务入口，`g4-real-task-minimal-workset.json` 只保留 legacy 参考，`g4-real-task-work-tree-debug.json` 明确为 `runtime-debug-harness`；`modules/task-takeover/src/yggdrasil_task_takeover/plugin.py` 已把 `delivery.pending` / `delivery.incomplete` 升级为 hard gate，`tests/test_runtime_p2_delivery_gate.py` 新增“缺字段即 delivery-gate-blocked”与“多节点链路 revision -> 复跑 -> approve”回归；`docs/LLM_WORK_ANALYZER_USER_GUIDE.md` 与两份 v0.2 协议文档也已补齐 work-tree debug 固定读法，以及 provider prefix cache 与 runtime continuation cache 的边界说明。

---

## 顶层结构

```
世界树计划/
├── README.en.md    # 英文版仓库入口文档
├── .env.example    # 开源版本地环境变量示例（不含真实密钥；CLI/服务入口会自动加载）
├── CONTRIBUTING.md # 外部贡献工作流、测试要求、PR 约定
├── CONTRIBUTING.en.md # 英文版贡献指南
├── CODE_OF_CONDUCT.md # 社区行为准则与处理流程
├── CODE_OF_CONDUCT.en.md # 英文版社区行为准则
├── GOVERNANCE.md  # 维护者职责、决策方式与 RFC 入口
├── GOVERNANCE.en.md # 英文版治理说明
├── SECURITY.md    # 漏洞披露与安全支持策略
├── SECURITY.en.md # 英文版安全策略
├── apps/           # 前端应用
├── services/       # 后端微服务
├── packages/       # 共享库
├── modules/        # 可插拔功能模块
├── applications/   # 应用场景插件
├── adapters/       # 外部系统适配器
├── docs/           # 项目文档
├── evaluation/     # 评测框架
├── infra/          # 本地基础设施
├── migrations/     # 数据库迁移
├── scripts/        # CI 辅助脚本
├── tests/          # 集成测试
└── .github/        # GitHub Actions CI 配置
```

---

## 开源协作与治理入口

```
.
├── CONTRIBUTING.md                # 面向外部贡献者的首个入口
├── CONTRIBUTING.en.md             # 英文版贡献指南
├── CODE_OF_CONDUCT.md             # 社区行为规范
├── CODE_OF_CONDUCT.en.md          # 英文版社区行为规范
├── GOVERNANCE.md                  # 角色、评审权与 RFC 决策机制
├── GOVERNANCE.en.md               # 英文版治理说明
├── SECURITY.md                    # 安全问题私下披露流程
├── SECURITY.en.md                 # 英文版安全策略
├── .github/
│   ├── CODEOWNERS                 # 默认代码归属人与评审路由
│   ├── PULL_REQUEST_TEMPLATE.md   # PR 模板
│   └── ISSUE_TEMPLATE/
│       ├── bug_report.yml         # 缺陷提报表单
│       ├── feature_request.yml    # 功能请求表单
│       └── config.yml             # Issue 联系入口与 blank issue 策略
└── docs/
    ├── OPEN_SOURCE_BOUNDARY.md    # 开源边界、支持矩阵与稳定性承诺
    ├── OPEN_SOURCE_BOUNDARY.en.md # 英文版开源边界说明
    └── rfcs/
        ├── README.md              # RFC 流程说明
        ├── README.en.md           # 英文版 RFC 流程说明
        └── 0000-template.md       # RFC 模板
        └── 0000-template.en.md    # 英文版 RFC 模板
```

**关键说明：**
- 本仓库现在按“默认公开、密钥例外”的原则运行：一切提交进仓库的内容都应可公开分发，真实 API key 只能通过环境变量注入。
- `.env.example` 中的 `YGGDRASIL_STATE_ROOT` 指向状态根目录本身（例如 `.yggdrasil`）；运行时会自动在其下创建 `state/` 子目录。
- 重大设计变更不再直接靠 issue 或口头约定推进，统一通过 `docs/rfcs/` 目录下的 RFC 文档完成讨论、批准与留痕。
- 开源协作核心文档现在提供中英文双份入口；中文仍是工程内完整说明，英文版优先服务外部协作者的仓库浏览、贡献、治理与安全理解。

---

## 英文版入口

```
.
├── README.en.md                   # 英文版项目简介与快速入口
├── CONTRIBUTING.en.md             # 英文版贡献指南
├── CODE_OF_CONDUCT.en.md          # 英文版社区行为准则
├── GOVERNANCE.en.md               # 英文版治理说明
├── SECURITY.en.md                 # 英文版安全策略
└── docs/
    ├── OPEN_SOURCE_BOUNDARY.en.md # 英文版开源边界
    └── rfcs/
        ├── README.en.md           # 英文版 RFC 流程
        └── 0000-template.en.md    # 英文版 RFC 模板
```

**关键说明：**
- 英文版目前聚焦开源协作入口，而不是完整替代所有中文工程文档。
- 外部协作者从 README、贡献、安全、治理和 RFC 流程即可完成首轮参与；更深的工程实现仍以中文开发文档和协议文档为主。

---

## apps/ · 前端应用

```
apps/
└── web/                            # Next.js 15 + React 19 工作台
    ├── app/                        # Next.js App Router 路由目录
    │   ├── page.tsx                # 总览页（工作台首页）
    │   ├── layout.tsx              # 全局布局
    │   ├── api/
    │   │   └── core/               # Core API 的前端代理（透传到 :8000）
    │   ├── applications/           # 应用场景浏览页
    │   ├── assets/                 # 资产管理页（上传、查看、版本）
    │   ├── collaboration/          # PR 审查与协作页
    │   ├── evaluations/            # 评测结果展示页
    │   ├── mcp/                    # MCP 模块状态页
    │   ├── nodes/
    │   │   └── [nodeId]/           # 记忆节点详情页（动态路由）
    │   ├── observability/          # 调用链路追踪页
    │   ├── prompting/              # Prompt 模板管理与预览页
    │   ├── tasks/
    │   │   └── [taskId]/           # 任务详情页（动态路由，现已挂接 LLM 工作分析摘要与独立分析路由）
    │   ├── training/               # 训练实验管理页
    │   └── components/             # 可复用 React 组件
    ├── lib/                        # 前端工具函数
    ├── package.json                # 前端包配置
    ├── next.config.ts              # Next.js 配置
    └── tsconfig.json               # TypeScript 配置（继承根配置）
```

**关键说明：**
- `app/api/core/` 是纯代理层，不含业务逻辑，请求直接转发至 Core API（`:8000`）。
- 应用场景 UI（如 coding、research）由 `applications/` 目录下的应用插件提供，Web 工作台本身不承载场景专属页面。
- `apps/web/app/components/task-detail-page.tsx` 现已作为任务控制面 UI：除 pause/resume 外，也会展示 approve/revision、mailbox state/message 与 side-channel event，收口 P6 的前端可见性；同时已新增 LLM 工作分析摘要卡，并提供进入完整分析页的入口。
- `apps/web/app/components/task-llm-work-analysis.tsx` 负责 Web 端的正式 LLM 工作分析视图：任务详情页用 compact 模式展示摘要，独立分析页用 full 模式展示窗口、轮次、工具、工件和辅助信号；本轮已补上工作树调试摘要卡、节点切换时间线、prefix cache key 与 cache hit/write/non-cache 视图。
- `apps/web/app/tasks/[taskId]/analysis/page.tsx` 为任务级独立分析路由，直接消费 `/tasks/{taskId}/analysis/latest`。

---

## services/ · 后端微服务

```
services/
├── core-api/                       # 控制面 API 服务（:8000）
│   ├── pyproject.toml
│   └── src/yggdrasil_core_api/
│       ├── main.py                 # 服务启动入口（uvicorn）
│       ├── app.py                  # FastAPI 应用实例、CORS、中间件
│       ├── config.py               # 配置读取（环境变量）
│       ├── services/               # 核心业务逻辑层（按资源域拆分的 Service 子包）
│       │   ├── task_service.py     # 任务生命周期相关业务逻辑
│       │   ├── memory_service.py   # 记忆树与检索相关业务逻辑
│       │   ├── runtime_service.py  # 运行时状态与执行记录查询
│       │   ├── evaluation_service.py # 评测结果与套件查询
│       │   └── ...                 # 其余资源域 Service
│       └── api/
│           ├── router.py           # 聚合所有路由
│           └── routes/             # 路由模块（每个资源一个文件）
│               ├── applications.py # GET /applications/ - 应用目录
│               ├── assets.py       # /assets/ - 资产 CRUD
│               ├── collaboration.py# /collaboration/ - PR 协作
│               ├── evaluations.py  # /evaluations/ - 评测结果
│               ├── health.py       # /health - 健康检查
│               ├── mcp.py          # /mcp/ - MCP 协议
│               ├── memory.py       # /memory/ - 记忆树操作
│               ├── modules.py      # /modules/ - 模块管理
│               ├── nodes.py        # /nodes/ - 节点 CRUD
│               ├── observability.py# /observability/ - 追踪数据
│               ├── outbox.py       # /outbox/ - 事件出箱
│               ├── prompting.py    # /prompting/ - Prompt 管理
│               ├── runtime.py      # /runtime/ - 运行时状态、模型调用与 LLM 工作分析入口
│               ├── specs.py        # /specs/ - 规格查询
│               ├── tasks.py        # /tasks/ - 任务生命周期、P4 approve/revision 控制面与 latest LLM analysis 入口
│               ├── training.py     # /training/ - 训练实验
│               └── workbench.py    # /workbench/ - 总览数据
│
├── agent-runtime/                  # Agent 执行引擎服务（:8001）
│   ├── pyproject.toml
│   └── src/yggdrasil_agent_runtime/
│       ├── main.py                 # 服务启动入口
│       ├── app.py                  # FastAPI 应用实例
│       └── runtime.py              # Agent 执行主逻辑（任务分发、LLM 调用闭环；现导出 approve/revision 运行时控制）
│
├── module-host/                    # 模块宿主服务（:8002）
│   ├── pyproject.toml
│   └── src/yggdrasil_module_host/
│       ├── main.py                 # 服务启动入口
│       ├── app.py                  # FastAPI 应用实例
│       └── host.py                 # 模块发现、装配、注册、健康管理
│
└── worker/                         # 异步任务 Worker
    ├── pyproject.toml
    └── src/yggdrasil_worker/
        ├── main.py                 # Worker 启动入口
        └── registry.py             # Worker 活动注册、队列消费、retry/requeue 与 graceful shutdown
```

**关键说明：**
- `services/` 子包是控制面的业务逻辑层，已按资源域拆分；路由层仅做参数校验和委派。
- Agent Runtime 和 Core API 通过 NATS JetStream 事件总线通信，不直接 HTTP 调用。
- Worker 当前通过 `registry.py` 统一管理活动目录、Redis 队列消费和 retry/requeue，不再依赖独立 `activities.py` 实现文件。
- Worker 运行 Temporal Activity，处理耗时异步任务（如批量记忆导入、训练触发）。

---

## packages/ · 共享库

```
packages/
├── python-sdk/                     # 核心 Python SDK（被所有服务和模块依赖）
│   ├── pyproject.toml
│   └── src/yggdrasil_sdk/
│       ├── __init__.py             # 对外导出的公共 API
│       │
│       ├── # ── 领域模型层 ──────────────────────────────
│       ├── domain.py               # 核心领域对象（Task, Node, Agent, Memory 等，23KB）
│       ├── contracts.py            # 服务间数据契约与 Pydantic 模型（16KB）
│       │
│       ├── # ── 持久化层 ─────────────────────────────────
│       ├── persistence/
│       │   ├── models.py           # SQLAlchemy ORM 模型
│       │   ├── repositories/       # 仓储实现子包（task/memory/evaluation 等）
│       │   ├── migrations.py       # 迁移工具函数
│       │   └── vector_store.py     # pgvector 向量操作封装
│       │
│       ├── # ── 运行时核心 ──────────────────────────────
│       ├── runtime_kernel/         # 核心运行时内核子包（root mount、主循环、快照、安全关闭、任务接管；execution_loop 已拆分为 execution_loop_part_a/b + transitions，入口文件保留兼容导出；takeover reducer 现负责 work tree/context stack 推进、revision reopen 与 approval finalize）
│       ├── llm_runtime.py          # LLM 调用封装兼容门面（实现拆分到 llm_runtime_part_a/b；保留原导入路径）
│       ├── tool_runtime.py         # 工具注册与执行运行时
│       ├── hook_runtime.py         # Hook 事件触发与分发运行时
│       ├── hooks.py                # Hook 类型定义与注册接口
│       ├── application_runtime.py  # 应用配置加载与初始化
│       │
│       ├── # ── Prompt 管理 ──────────────────────────────
│       ├── prompting.py            # Prompt 模板管理、版本控制（22KB）；runtime prompt 已增加 bootSections 四段（physical_interface/world_roots/behavior_constitution/scene_recovery），其中 physical_interface 现在只保留稳定接口绑定与实际 tool/capability inventory，场景化 tool policy 已移出 boot；恢复态会规范化 Working_Node / currentNodeId / memoryRetrievalState.workTreeNodeId / pcMemo，并在 P4 路径附带 `work_context_stack` / `childCompletionSummaries`；response requirements 已显式加入 `work-node-create` / `work-node-enter` 标签契约用于父节点编排，few-shot 仍在恢复态自动跳过
│       ├── prompt_modules/
│       │   ├── compiler.py         # PromptCompiler 核心（模板 + 记忆 → 最终 Prompt）
│       │   └── formatters.py       # 不同格式的 Prompt 输出渲染
│       │
│       ├── # ── 记忆与模块 ──────────────────────────────
│       ├── model_routing.py        # 模型路由策略（按场景、按成本、按能力选模）
│       ├── catalog.py              # 模块目录（发现、注册、能力查询）；含 2s TTL 进程级缓存
│       ├── app_catalog.py          # 应用目录（应用配置加载与管理）
│       ├── spec_catalog.py         # 规格目录（协议规格注册与查询）
│       ├── module.py               # Module 基类（所有模块继承此类）
│       │
│       ├── # ── MCP 集成 ─────────────────────────────────
│       ├── mcp_bridge.py           # MCP 协议桥接实现（32KB）
│       ├── mcp_bridge_module.py    # MCP 模块封装
│       ├── mcp_servers/            # 内置 MCP Server 实现（含 execute_server 默认拒绝网络命令的 permission layer）
│       │
│       ├── # ── 协作与评测 ──────────────────────────────
│       ├── collaboration_runtime.py# PR 协作运行时兼容门面（实现拆分到 collaboration_runtime_part_a/b）
│       ├── evaluation_runtime/     # 评测运行时子包（bootstrap / scorer / suite_runner；含 G4 longform / window stress / real-task parity 指标聚合、文件/目录语料装载、可选隔离沙箱保留，以及 live-provider-matrix 的正式合同型 acceptance 检查；fallback local evaluation 环境在 preserve sandbox 或显式 state root 下也会把 suite metrics 与 case sandboxes 写入持久 state，case 级 isolated runtime 现也会继承 suite 传入的 workspace_root，避免 clean workspace run 仍回拷原仓库）
│       ├── evaluation_cli.py       # 评测命令行工具
│       │
│       ├── # ── 可观测性 ─────────────────────────────────
│       ├── observability.py        # OTel Tracer 封装（11KB）
│       ├── observability_exporters.py # 多后端导出器（Jaeger、Langfuse）
│       │
│       └── # ── 运维工具 ─────────────────────────────────
│           ├── ops_runtime.py      # 运维兼容门面，保持 CLI 与外部导入路径稳定
│           ├── ops_runtime_backup.py # runtime 备份与恢复实现
│           ├── ops_runtime_compose.py # compose smoke 检查实现
│           ├── ops_runtime_live.py # 真实用户 live task pack 兼容门面（实现拆分到 ops_runtime_live_part_a/b）
│           ├── ops_runtime_sandbox.py # 真实用户试跑沙箱准备实现
│           ├── ops_runtime_scorecard.py # scorecard 汇总与 live 评分行生成
│           ├── ops_runtime_shared.py # 运维共享 helper（路径、命令、冻结材料）
│           ├── ops_cli.py          # 运维命令行工具（backup/restore/compose-smoke/pilot-sandbox/pilot-live/pilot-scorecard）
│           └── support.py          # 通用工具函数（含隔离工作区复制、CJK word_count 估算；sandbox 复制会动态忽略当前配置的 state root/state dir，并默认跳过仓库顶层 tmp，避免持久审计目录与临时输出被递归拷贝进下一轮评测）
│
├── contracts/                      # 跨语言共享类型定义
│   ├── package.json
│   └── src/                        # TypeScript 类型（与 Python contracts.py 对应）
│
└── frontend-sdk/                   # 前端专用 SDK
    ├── package.json
    └── src/                        # React Hooks、API 客户端、前端类型；`types.ts` 现已补齐 TaskDetailResponse 的 runtimeControl approve/revision、mailbox 与 side-channel 契约
```

**关键说明：**
- `runtime_kernel/` 是系统最核心的运行时子包，承载任务状态机、Agent 执行编排、上下文管理、快照与任务接管。
- `runtime_kernel/root_mount.py` 现在不再只给底层 identity/context/execution refs；它还会输出中文语义根指针、`SYS_ROOT_PROTOCOL`、`startupLoadOrder`、tool/capability index、mailbox/standby 状态，以及 `standby / resume-node / bootstrap` 三态 `startupMode`，作为启动恢复的数据面。
- `runtime_kernel/execution_loop.py` 当前为兼容导出门面，核心实现位于 `runtime_kernel/execution_loop_part_a.py`、`runtime_kernel/execution_loop_part_b.py` 与 `runtime_kernel/execution_loop_transitions.py`；执行链仍保持“先基于 takeover protocol 预生成 work tree 锚点，再把外来 `currentContext` 物化进记忆树并执行 retrieval”，并已在 retrieval 前优先恢复 `currentNodeId / workingNodeAnnotation / pcMemo`，同时额外落 `runtime/window-executions/*.json` 结构化窗口工件，记录每窗 work tree、retrieval、合同摘要与交付状态；当前 retrieval 还支持“压缩段尾部自动解压”判定：当最后一个 `carry-forward-package` 之后的未压缩段数量在 `1..n`（`maxUncompressedTailBeforeDecompress`，默认 `1`）时，不再对检索结果执行 carry-forward trim。当前运行时的窗口超阈值路径已回到“两级续跑”语义：若当前节点是非根叶子，仍优先写回 `failed + failureSummary` 并按 `childCompletionSummaries(status=failed)` 上浮到父节点，再由父节点决定进入已有 child / 创建新 child / 汇总交付；若本地 work-tree continuation 不可用（例如 root/single-path overflow），则改走 carry-forward restart snapshot，排队一个带 `resumeToken` 的 `window-restart-queued` 闭环，而不是直接把任务终结成 `failed-window-overflow`。
- 本轮设计冻结已同步到规格层：`docs/specs/agent-runtime-protocol-v0.2.md` 明确 `restart-recovery` 仅 legacy/stress 兼容、v2 默认“压缩优先+超阈值失败”；`docs/specs/work-tree-protocol-v0.2.md` 把第 9 章改为“窗口超阈值处理”，补齐压缩范围起止约束；`docs/specs/runtime-domain-data-spec-v0.1.md` 为 `ContextPruningPlan` 增加 `compressionRange` 元数据并固化 `maxUncompressedTailBeforeDecompress` 语义。
- `runtime_kernel/execution_loop.py` 也负责正式任务进度流转：`Task.status/currentFocus/windowIndex/restartCount` 提供全局运行态，`TaskTakeoverProtocol.workTree.currentNodeId/status` 与 `WorkContextStack.topFrameId` 提供执行节点级进度；在当前单一路径下，非根子节点完成/失败会先回父节点，由父节点通过 `work-node-enter` / `work-node-create` 显式编排后续路径，根节点完成进入 `awaiting-approval`，随后只能由 approve/revision 控制面推进到 `completed` 或重新打开节点。`task-takeover` 模块现已把 `delivery.result / evidence / pending / incomplete` 全部升级为正式门禁；若首次输出缺少 `pending` 或 `incomplete`，runtime 会先在同一节点排一轮纠偏续跑，要求直接补齐正式交付；若纠偏后仍未过 gate，才会收敛成 `delivery-gate-blocked`。
- `runtime_kernel/execution_loop_part_b.py` 对恢复态 snapshot 额外做完整性校验；若 `pendingAction.checksum` 失配，会先把 snapshot 标记为 `created` 并持久化 `snapshot-corrupted:*` blocker，再拒绝恢复；同一文件现在也会把 `invoke_runtime_completion()` 的 provider/LLM invocation exception 纳入 failed-leaf continuation：非根叶子若已有 `failureTransition.requiresContinuation`，会像窗口超限一样先写回 `failed + failureSummary`，再排队 sibling/parent continuation，而不是直接把整任务打成 failed，对应回归位于 `tests/test_runtime_p4_foundation.py`。
- `prompting.py` 的 response requirements 现会向模型暴露最小 `memory-write` 标签语法，并显式给出 `work-node-create` / `work-node-enter` 标签契约（父节点强编排下由父节点决定进入已有 child、创建新 child 或汇总交付）；runtime prompt 还会附带结构化 `memory_retrieval_state`，并在恢复态把 Working_Node、`currentNodeId`、`pcMemo` 与 retrieval node pointer 统一到同一执行节点；P4 路径额外会渲染 `work_context_stack`，把最近几层 frame 的 `childCompletionSummaries` 暴露给父节点续跑；few-shot 示例不再作为独立 user/assistant 消息写入 prompt，而是折叠进系统示例块，并在恢复态跳过以降低重复文本；takeover 协议段现在也优先给出 work tree / step count 摘要，而不是重新渲染显式计划清单。
- `llm_work_analysis.py` 现作为正式的 run-first 分析器：主键骨架是 task/run/model_invocations，本地补读 request/response/prompt/metrics/takeover/work-context/window-execution 工件，并默认把结果写入 `state/analysis/llm-work/` 供评测与调试复用；当前已补齐 cache summary、work-tree timeline、approval stop、mixed outcome 与 per-invocation `runtime/window-executions/by-invocation/` 历史工件读取。
- `langfuse_trace_layered_analysis.py` 现兼容中文化的任务目标/任务说明/当前焦点标签，避免 prompt 标签本地化后 Langfuse 文本审查丢失任务抽取结果。
- `llm_runtime.py` + `tool_runtime.py` 构成正式工具分发链；`llm_runtime.py` 已拆分为 `llm_runtime_part_a.py`/`llm_runtime_part_b.py` 并保持原导入路径，避免外部调用改动。
- `evaluation_runtime/` 是评测框架子包，承载套件加载、隔离运行、评分聚合和各阶段评测场景；设置 `YGGDRASIL_EVAL_PRESERVE_SANDBOX=1` 时，会把 case 沙箱保留到 `.yggdrasil/state/evaluation-sandboxes/` 供事后审计；若 suite runner 落入 local fallback，它现在也会沿用持久 state 根，避免 evalrun 与 strict 审计工件只写进临时目录。
- `persistence/` 是唯一允许直接操作数据库的层，其他代码必须通过仓储接口。

---

## modules/ · 可插拔功能模块

每个模块是一个独立的 Python 包，通过 Hook 协议扩展核心能力。

```
modules/
├── # ── 记忆能力模块 ─────────────────────────────────────
├── text-memory/                    # 文本导入与检索扩展
│   ├── yggdrasil.module.yaml       # 模块清单（Hook 声明、权限、能力）
│   ├── pyproject.toml
│   └── src/text_memory/
│       └── plugin.py               # 主模块类
│
├── context-pruning/                # 上下文动态压缩（核心模块）
│   ├── yggdrasil.module.yaml
│   └── src/context_pruning/        # 基于信息熵的上下文裁剪实现
│
├── shared-memory/                  # 多用户共享记忆空间与权限控制（写权限现在可按 sourceWorkTreeNodeId 做节点级约束）
│   └── src/shared_memory/
│
├── multimodal-memory/              # 图片/音频资产的记忆节点关联（资产与摘要节点现可回挂到 related/source work tree）
│   └── src/multimodal_memory/
│
├── memory-organizer/               # 自动记忆整理与软遗忘治理
│   └── src/memory_organizer/
│
├── relation-discovery/             # 跨节点语义关联发现（新建边会带 source-work-tree 审计线索）
│   └── src/relation_discovery/
│
├── # ── 任务能力模块 ─────────────────────────────────────
├── pause-resume/                   # 任务暂停/恢复与快照管理
│   └── src/pause_resume/
│
├── task-takeover/                  # Gate 2 任务接管协议（目标解析、约束、计划、验证、交付）
│   └── src/yggdrasil_task_takeover/
│
├── subagent-runtime/               # Sub-Agent 独立分支执行框架
│   └── src/subagent_runtime/
│
├── subagent-pr/                    # Sub-Agent PR 提交与协作
│   └── src/subagent_pr/
│
├── # ── 平台能力模块 ─────────────────────────────────────
├── mcp-bridge/                     # Model Context Protocol 服务桥接
│   └── src/mcp_bridge/
│
├── training-lab/                   # 训练数据集、模型产物、验证门管理
│   └── src/training_lab/
│
└── # ── 场景模块（与应用插件配套） ────────────────────────
    ├── scene-coding-new-project/   # 从零编写代码场景的模块支持
    ├── scene-coding-inherit-project/ # 继承代码库场景的模块支持
    ├── scene-research-deep/        # 深度研究场景的模块支持
    ├── scene-writing-epic/         # 长篇创作场景的模块支持
    ├── scene-learning-coach/       # 学习辅导场景的模块支持
    ├── scene-maintenance-default/  # 系统运维场景的模块支持
    └── scene-scenic-guide/         # 信息导览场景的模块支持
```

**每个模块的标准文件结构：**

```
modules/<name>/
├── yggdrasil.module.yaml   # 必须：Hook 声明、所需权限、能力标签
├── pyproject.toml          # 必须：包配置与依赖
└── src/<package>/
    ├── __init__.py
    └── plugin.py           # 模块主类（继承 YggdrasilModule）
```

---

## applications/ · 应用场景插件

每个应用是一个针对特定场景预配置的 Agent 工作方式。

```
applications/
├── base-template/                  # 所有应用继承的基础模板
│   ├── yggdrasil.app.yaml          # 基础应用清单
│   └── prompts/                    # 基础提示模板
│
├── coding-greenfield/              # 从零开始的软件开发
├── coding-inherit/                 # 继承已有代码库
├── deep-research/                  # 深度研究与文献整理
├── epic-writing/                   # 长篇内容创作
├── knowledge-studio/               # 知识库建设与管理
├── learning-coach/                 # 个性化学习辅导
├── maintenance-ops/                # 系统运维与巡检
├── scenic-guide/                   # 信息导览与规划
└── software-factory/               # 大型软件工程全流程
```

**每个应用的标准文件结构：**

```
applications/<name>/
├── yggdrasil.app.yaml      # 应用清单（绑定模块、模型路由、种子上下文）
└── prompts/
    ├── system.md           # 系统提示（定义 Agent 身份与工作方式）
    └── seed.md             # 种子记忆（初始化上下文）
```

---

## adapters/ · 外部系统适配器

```
adapters/
├── model-providers/                # LLM 模型提供商适配器包
│   ├── pyproject.toml
│   └── src/yggdrasil_model_providers/
│       ├── __init__.py             # 导出 provider catalog / invoke_model / route_model
│       ├── gateway.py              # 真实 provider 调用网关；LongCat/OpenRouter/DeepSeek/VectorEngine；DeepSeek V4、thinking mode、tool-name aliasing
│       └── router.py               # 模型路由对接层（委派 python-sdk 的 route decision）
│
└── media-providers/                # 媒体处理适配器包
    ├── pyproject.toml
    └── src/                        # 媒体 provider 具体实现
```

**关键说明：**
- `gateway.py` 现在维护实时 provider catalog，并按当前可用凭证暴露候选模型。
- paid provider（如 `deepseek_direct`）只有在显式设置 `YGGDRASIL_ALLOW_PAID_MODELS=1` 时才会进入 runtime candidate catalog。
- DeepSeek 直连 profile 已切换到 `deepseek-v4-flash` / `deepseek-v4-pro`，并兼容 thinking mode、`reasoning_effort` 与 `reasoning_content` 回传。
- `packages/python-sdk/model_routing.py` 实现路由策略，适配器负责具体 API 调用和 provider 兼容性差异吸收。

---

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
│   ├── WORLD_BUILD_INITIAL_AWAKENING_TASK_START_EXECUTION_2026_05_26.md
│   │                               #   世界构建、初次苏醒与任务级工作状态读取实施文档：把新三阶段规格翻译成 contracts/root_mount/execution_loop/prompting/takeover/snapshot/tests 的实现顺序
│   ├── TASK_WORLD_START_STATE_AND_TASK_RUNTIME_SPLIT_2026_05_26.md
│   │                               #   给低智商 code agent 的任务文档：把“起始状态 + 任务级工作状态读取”重构拆成明确步骤、禁止事项、测试命令与完成标准
│   ├── ROOT_PROMPT_STARTUP_WORKFLOW_REWORK_EXECUTION_2026_05_23.md
│   │                               #   提示词、启动流程、工作流程重做执行文档：Boot Prompt、工作树 v0.2、WorkContextStack 栈式上下文、启动恢复、运行循环、记忆冲突、多 Agent 与验收门禁
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
│   ├── agent-runtime-protocol-v0.1.md       # Agent 运行时协议规格
│   ├── task-takeover-protocol-v0.1.md       # Gate 2 任务接管协议：目标/约束/计划/验证/交付与出口标准
│   ├── runtime-domain-data-spec-v0.1.md     # 运行时、work tree、worker activity 与工具数据规格
│   ├── work-tree-protocol-v0.1.md           # Gate 3 工作树正式协议：执行节点、恢复锚点与完成态同步
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
│   ├── g4-real-task-window-parity-rerun-log-audit-2026-05-16.md
│   │                               #   4M 真实任务保留日志重跑记录：窗口 1/2 行为、保留沙箱路径、最终输出偏移与根因分析
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
    ├── g4-real-task-window-parity.json
                                    #   G4 真实任务窗口对照（repo-wide baseline；现已接入 strict 审计、window-execution 指标、workTreeContinuity/minimalWorkset 正式门禁，并要求 7 段简报后追加 formal delivery footer 以穿过 runtime delivery gate）
    ├── g4-real-task-window-parity-flash.json
                                    #   G4 真实任务窗口对照 flash 变体（保留 LongCat 2，对 DeepSeek paid 路径切到 deepseek-v4-flash；用于实际任务 flash live 复跑，同样追加 formal delivery footer 合同）
    ├── g4-real-task-minimal-workset.json
                                    #   G4 真实任务最小工作集 legacy 参考（repo-specific 历史样本；不再作为默认真实任务模板）
    ├── g4-real-task-work-tree-debug.json
                                    #   G4 真实任务工作树调试 harness（显式嵌套 takeoverProtocol，从 child 节点起步；当前目标已切到 child 先回父节点、父节点再决定 sibling/leaf 的编排语义，不再把 failure->sibling continuation 当默认目标）
    └── g4-window-restart-stress.json
                                    #   G4 官方伪无限上下文窗口 stress（显式 effectiveContextWindow + forcedWindowRestartBudget；LongCat/DeepSeek 正式对照）
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
| `eval:g4:real-task-parity` | `suites/g4-real-task-window-parity.json` |
| `eval:g4:real-task-parity:flash` | `suites/g4-real-task-window-parity-flash.json` |
| `eval:g4:real-task-unrelated:dual-live` | `suites/g4-real-task-unrelated-dual-live.json` |
| `eval:g4:real-task-minimal-workset` | `suites/g4-real-task-minimal-workset.json` |
| `eval:g4:work-tree-debug` | `suites/g4-real-task-work-tree-debug.json` |
| `eval:g4:window-stress` | `suites/g4-window-restart-stress.json` |

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
| `docs/development/ROOT_PROMPT_STARTUP_WORKFLOW_REWORK_EXECUTION_2026_05_23.md` | 提示词、启动流程、工作流程重做执行文档：把 `docs/new/` 方案转成可分阶段实现、验证和回滚的工程任务，现已纳入父节点强编排与有限线性 continuation 轨迹主流程 |
| `docs/development/WORLD_BUILD_INITIAL_AWAKENING_TASK_START_EXECUTION_2026_05_26.md` | 世界构建、初次苏醒与任务级工作状态读取实施文档：把新三阶段口径压成实现层计划，明确本轮先做运行时分层，不在这一轮实现完整世界编译流水线 |
| `docs/development/TASK_WORLD_START_STATE_AND_TASK_RUNTIME_SPLIT_2026_05_26.md` | 给 code agent 的执行任务文档：用不可误解的顺序指挥粗粒度代码改造，覆盖 contracts/root_mount/execution_loop/prompting/takeover/snapshot 与三组关键测试 |
| `docs/development/WORLD_TREE_AGENT_WORKFLOW_CURRENT_VS_TARGET_2026_05_26.md` | 世界树 Agent 当前工作逻辑 vs 目标工作逻辑：从世界树 agent 视角整理“父节点强编排、child 回编排父节点、有限线性轨迹、awaiting-approval 收口”的正式目标链路 |
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
| `docs/research/technical-analysis/g4-real-task-window-parity-rerun-log-audit-2026-05-16.md` | 4M 真实任务保留日志重跳记录 |
| `docs/research/technical-analysis/memory-tree-agent-work-breakdown-2026-05-16.md` | 记忆树 Agent 全工作拆分研究：26 个最小可推进子任务 |
| `docs/research/roadmaps/memory-tree-agent-executable-roadmap-2026-05-16.md` | 记忆树 Agent 可执行路线图 |
| `docs/research/completion-reports/P2_VERIFICATION_AND_P3_DELIVERY_2026_05_17.md` | P2 执行结果验证与 P3 完成报告 |
| `docs/research/technical-analysis/runtime-two-failures-summary-2026-05-17.md` | 运行时两个失败用例摘要 |
| `docs/research/project-assessments/memory-tree-effect-report-2026-05-17.md` | 记忆树效果详细报告 |
| `docs/research/specifications/concepts/` | Agent / 记忆树中文系统设计文档集合 |
| `docs/research/archive/future-planning/` | 不进入当前 Gate 承诺范围的前瞻研究草案 |
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
| 任务执行的核心逻辑（含记忆树物化检索、memory-write 标签写树与窗口重启主循环） | `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop.py` |
| LLM 调用与模型路由 | `packages/python-sdk/src/yggdrasil_sdk/llm_runtime.py` |
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
| 前端页面 | `apps/web/app/<page>/page.tsx` |
| 评测套件定义 | `evaluation/suites/*.json` |
| 质量基线与延迟门禁值 | `docs/QUALITY_BASELINE.md` |
| 架构决策理由 | `docs/adr/ADR-<number>-*.md` |
| CI 工作流定义 | `.github/workflows/{pr,ci,release-check}.yml` |
| Alembic 迁移一致性检查 | `scripts/check_migrations.sh` |
| 端到端冒烟测试 | `scripts/smoke_test.sh` |
