## 分册 01：总览与治理入口

> 包含：近期关键文档速览、顶层结构、开源协作与治理入口、英文版入口。

| `docs/development/WEB_RESEARCH_WORK_TREE_LONG_RUN_2026_05_28.md` | Web 搜索长任务工作树入口（2026-05-28）：新增 `evalsuite_g4_web_research_work_tree_long`，固定 LongCat live 网络搜索并强化多窗口 continuation/工作树连续性观测 |
| `docs/development/WORK_TREE_ONLY_SINGLE_TASK_DEBUG_2026_05_28.md` | 工作树单任务调试基线（2026-05-28）：将 G4 work-tree-debug case 收敛为 `activeCapabilities=[task-takeover]` 并补齐 runtime start 能力透传，用于先验证“仅工作树”执行语义 |
| `docs/development/G4_WEB_RESEARCH_DEFAULT_FAILURE_AUDIT_2026_05_27.md` | G4 默认网络研究测试失败审计（2026-05-27）：固化 `evalrun_52ffd96d5551405da5b0` 的行为偏差，明确“重复幂等工具循环触发提前停止 -> 未进入结构化交付”的失败链路与证据位置 |
| `docs/development/TASK_CHECKFLOW_AUDIT_AND_ALIGNMENT_2026_05_27.md` | 任务核对流程审计与对齐（2026-05-27）：冻结“理解任务 -> 形成计划 -> 向发起者核对 -> 再执行”的目标流程，并对照当前协议、提示词、运行时与测试缺口 |
| `docs/development/WORLD_TREE_AGENT_WORKFLOW_CURRENT_VS_TARGET_2026_05_26.md` | 世界树 Agent 当前工作逻辑 vs 目标工作逻辑（2026-05-26）：冻结“父节点强编排、child 完成/失败先回编排父节点、允许有限线性 continuation 轨迹、leaf 拆分尽量交给 LLM、根节点停在 awaiting-approval”的目标口径 |
| `docs/development/LLM_WORK_ANALYZER.md` | LLM 工作分析器设计与使用说明：说明 run-first 分析器的数据源、粒度、持久化位置、API/CLI 入口与当前限制 |
| `docs/architecture/runtime-principles-for-newcomers.md` | 项目运行原理（新人版）：纯设计视角说明世界层/任务层/窗口层、父节点强编排、续跑语义与审批收口 |
| `docs/LLM_WORK_ANALYZER_USER_GUIDE.md` | LLM 工作分析器用户手册：面向任务操作者和评测/排障同学，说明 Web、CLI、API 入口与常见排查流程；当前已补齐 work-tree debug 摘要卡、时间线、cache trace、child bubble 与 mixed outcome 的固定读法 |
| `docs/development/REAL_TASK_TEST_CONVENTIONS_AND_WORK_TREE_BACKLOG_2026_05_25.md` | 真实任务测试约定与工作树后续任务拆分（2026-05-25）：冻结“默认真实任务应单目标、弱项目内生化、由 agent 自主规划”的出题约定，并记录 P1/P2/P3/P5 本轮收口状态 |
| `docs/development/WORK_TREE_REAL_TASK_DEBUG_BASELINE_2026_05_25.md` | 工作树真实任务调试基线（2026-05-25）：把“父节点强编排”的工作树目标冻结成真实任务调试模型，并把验收重点转到 child 先回父节点、父节点再决定 sibling/leaf 的路径 |
| `docs/development/WORLD_BUILD_INITIAL_AWAKENING_TASK_START_EXECUTION_2026_05_26.md` | 世界构建、初次苏醒与任务级工作状态读取实施文档（2026-05-26）：把新三阶段规格翻译成实现层执行计划，明确 root mount 只做世界级/起始状态挂载，任务级工作状态单独读取，并给出 contracts/root_mount/execution_loop/prompting/takeover/snapshot/tests 的落地顺序 |
| `docs/development/TASK_WORLD_START_STATE_AND_TASK_RUNTIME_SPLIT_2026_05_26.md` | 给低智商 code agent 的任务文档（2026-05-26）：用严格顺序把“起始状态 + 任务级工作状态读取”重构拆成明确待办、测试命令、完成标准和禁止事项，适合直接转交做粗活 |
| `docs/development/TASK_WORLD_START_STATE_RUNTIME_REWORK_FIXUP_2026_05_26.md` | 给 code agent 的返工任务文档（2026-05-26）：针对验收发现的残留问题，强制收口“世界级不见任务、只有真实现场才无损恢复、TaskRuntimeState 成为唯一任务态入口”；本轮已落下一条关键修复：仅 `lossless-restore` 允许 `resume-node` |
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

> 项目完整目录结构及各路径的职责说明。适合新加入的开发者理解代码组织方式，以及查询特定功能所在位置。（2026/5/26 更新：`docs/new/世界树计划正式项目定义.md`、`docs/new/工作树.md`、`docs/new/元提示词.md`、`docs/specs/agent-runtime-protocol-v0.2.md`、`docs/specs/work-tree-protocol-v0.2.md`、`docs/development/WORLD_BUILD_INITIAL_AWAKENING_TASK_START_EXECUTION_2026_05_26.md`、`docs/development/WORK_TREE_REAL_TASK_DEBUG_BASELINE_2026_05_25.md` 与 `docs/development/WORLD_TREE_AGENT_WORKFLOW_CURRENT_VS_TARGET_2026_05_26.md` 已统一收口到新目标：父节点强编排、child 完成/失败先回编排父节点、允许有限线性 continuation 轨迹、leaf 拆分尽量交给 LLM、代码只做边界与警戒、根节点仍以 `awaiting-approval` 收口；同日继续落下首轮实现推进：`runtime_kernel/takeover.py` 已把 child 完成/失败后的默认路径改为先回编排父节点，`execution_loop_part_a.py` 新增 `work-node-enter` 助手标签以支持父节点显式进入已有 child，`tests/test_runtime_p4_foundation.py` 已改成锁住 `child -> parent re-orchestrate -> existing child -> parent -> awaiting-approval` 的新路径。2026/5/25 更新：测试环境默认通过 `tests/conftest.py` 关闭 `LANGFUSE_TRACING_ENABLED`，并在 `README.md` 基础验证章节补充“跑测试前先启动 OTel Collector”的备注，避免导出端点不可达带来的额外等待；同日更新：新增 `llm_work_analysis.py` 作为正式 LLM 工作分析器，按 run 拼接 DB 与 state 工件并产出 run/window/turn/tool/artifact/source 多粒度分析；`scripts/analyze_llm_work_run.py` 与 core-api `/runtime/analysis/runs`、`/tasks/{taskId}/analysis/latest` 已接入这一能力，用于评测与调试；同日继续更新：新增 `REAL_TASK_TEST_CONVENTIONS_AND_WORK_TREE_BACKLOG_2026_05_25.md`，正式冻结“默认真实任务应尽量弱项目内生化、单目标、由 agent 自主规划”的出题约定，并把工作树后续工作拆成测试合同、门禁闭环、缓存、硬化、观测五类任务包；此前 2026/5/24 更新：`runtime_kernel/takeover.py` 已从初始化器升级为正式 reducer，负责 work tree/context stack 推进、revision reopen 与 approval finalize；`execution_loop_transitions.py` 已形成完整 P4 闭环：根节点完成进入 `awaiting-approval`，并通过控制面 approve/revision 闭环；`execution_loop_part_a.py` / `execution_loop_part_b.py` 现已支持以 `work-node-create` 助手输出标签在正式主循环里动态扩树、在 retrieval 查询中优先使用 work tree 当前节点语义，并在异常/预算失败时把当前节点写回 `failed + failureSummary`；`execution_loop_transitions.py` 还会为 continuation/pause/restart 输出独立 `workContextStackRef` 栈快照引用；P5 现已补齐并发安全闭环：`tool_runtime.py` 会向正式工具透传 `sourceWorkTreeNodeId`，`modules/text-memory/` 暴露 `read_node` / `read_index` / `update_memory_with_version` / `append_memory_log` / `submit_memory_proposal` / `forget_node` 等正式记忆工具，`append_memory_log` 现通过仓储层原子追加避免并发日志静默覆盖，`prompting.py` 也已明确“正式记忆工具优先、`<memory-write>` 旁路次之”，并在宽节点或高冲突场景优先引导创建细分子节点做空间隔离；P6 已完成闭环：`collaboration_runtime_part_a.py` / `collaboration_runtime_part_b.py` 不仅为 sub-agent launch/worker/PR manifest 透传 `workTreeNodeId` 与 `subagentBudgetDecision`，还会把 child completion summary 合并回 parent work tree 与 `childCompletionSummaries`，再通过独立 `mailbox_messages` / `side_channel_events` 持久化表、对应 Alembic 迁移 `7ad7d9b8c4f1_runtime_mailbox_side_channel_tables.py`、`runtime/tasks/{taskId}/mailbox` / `side-channel` API 和 `execution_loop_part_b.py` 的 mailbox 注入路径唤醒 parent 继续汇总；`runtime_kernel/root_mount.py` 现在优先从仓储读取 mailbox state 并返回 `mailboxMessages`，`takeover.py` 也已补齐 `load_persisted_work_context_stack()` 与 parent merge helper；`services/core-api/.../tasks.py` 与 `services/agent-runtime/app.py` 新增 `approve-completion` / `request-revision` 路由，`runtime_service.py` 暴露 `canApprove/canRequestRevision/recommendedRevisionNodeId`；`packages/frontend-sdk/src/types.ts` 与 `apps/web/app/components/task-detail-page.tsx` 现已把这些运行时控制字段、mailbox state/message 和 side-channel event 正式接到任务详情页；P7 门禁已统一到单路径：`tests/test_runtime_p4_foundation.py` 覆盖显式传递与默认请求两种入口，均进入 `awaiting-approval`，不再保留 legacy `completed` 快速路径；`prompting.py` 会把 `work_context_stack` 和 `childCompletionSummaries` 暴露给模型；`contracts.py` 修复了显式 root-only v0.2 work tree 被错误包裹成自引用 root 的兼容升级问题。此前 2026/5/24 更新：`runtime_kernel/root_mount.py` 现已输出中文语义根指针、`SYS_ROOT_PROTOCOL`、启动加载顺序、tool/capability index、mailbox/standby 状态与 `startupMode`，`execution_loop_part_b.py` 在 retrieval 前优先恢复 `currentNodeId/Working_Node/pcMemo`、对无活动工作 `start` 直接走 `standby` 短路，并把损坏 snapshot 的 blocker 持久化；`execution_loop_transitions.py` 在根节点交付时切到 `awaiting-approval`，并要求 work tree 节点先写 `executionSummary`；2026/5/23 更新：补充提示词、启动流程、工作流程重做执行文档、`docs/new/` 三份新方案入口，以及 Agent 运行时/工作树 v0.2 正式规格；2026/5/18 更新：补充“功能形态分类与提示词功能检查计划”文档入口；2026/5/17 已完成开发相关大文件治理，`P2_IMPLEMENTATION_SPEC_2026_05_17.md` 已拆分为任务14/15/16/17与集成验收五份子文档；`tests/test_runtime_and_pruning.py` 已按主题拆分至 `tests/runtime/` 下 4 个文件；`tests/test_persistence_api.py` 已按 API 主题拆分至 `tests/api/` 下 3 个文件；`execution_loop.py`、`llm_runtime.py`、`ops_runtime_live.py`、`collaboration_runtime.py` 已改为兼容门面并拆分到 part 文件。）
> 2026/5/26 本轮继续同步：`prompting.py` 的 response requirements 已增强任务编排引导，明确 root 默认负责编排与最终汇总、天然可拆的任务优先下放 child、child 只处理单一局部目标并回父节点交摘要、同一节点连续恢复/重启时优先继续拆分而不是反复在 root 硬写整份交付；`tests/test_prompting_runtime.py` 已补断言锁住这些引导。此前 2026/5/26 同步：新增 `evaluation/suites/g4-real-task-unrelated-dual-live.json` 与 `eval:g4:real-task-unrelated:dual-live`，把“先用与本项目完全无关的题目观察真实执行过程”固定成正式入口；当前题面为外部 incident RCA，同题分别跑 `longcat / LongCat-2.0-Preview` 与 `deepseek_direct / deepseek-v4-flash`，并在主报告后强制追加 formal delivery footer（`## 结果` / `## 证据` / `## 风险` / `## 已知问题`），避免 unrelated live run 先被 runtime delivery gate 截断。此前 2026/5/26 同步：`execution_loop_part_b.py` 已恢复 root/single-path overflow 的 carry-forward restart snapshot 续跑，`tests/runtime/test_runtime_restart_and_resume.py` 与 `tests/test_g4_multiscene.py` 已改成锁住 `window-restart-queued` 闭环；`execution_loop_transitions.py` 现对 `delivery-gate-blocked` 增加一次限次纠偏续跑，`tests/test_runtime_p2_delivery_gate.py` 新增“误停补一轮可恢复、二次仍缺段才失败”回归。此前 2026/5/25 同步：`evaluation/suites/g4-real-task-externalized.json` 已作为默认真实任务入口，`g4-real-task-web-research-default.json` 只保留 legacy 参考，`g4-real-task-work-tree-debug.json` 明确为 `runtime-debug-harness`；`modules/task-takeover/src/yggdrasil_task_takeover/plugin.py` 已把 `delivery.pending` / `delivery.incomplete` 升级为 hard gate，`tests/test_runtime_p2_delivery_gate.py` 新增“缺字段即 delivery-gate-blocked”与“多节点链路 revision -> 复跑 -> approve”回归；`docs/LLM_WORK_ANALYZER_USER_GUIDE.md` 与两份 v0.2 协议文档也已补齐 work-tree debug 固定读法，以及 provider prefix cache 与 runtime continuation cache 的边界说明。
> 2026/5/27 同步：`packages/python-sdk/src/yggdrasil_sdk/prompting.py` 继续收紧工作树编排提示词，新增“先判定当前节点语义、child/leaf 默认先上浮、仅 root 或被父节点授权节点可做整任务最终交付、格式合同不得覆盖工作树拓扑、节点收敛后停止拆分”的硬约束；`tests/test_prompting_runtime.py` 新增对应断言，并补“task contract 优先使用 TaskRuntimeState 的 currentObjective/currentFocus”和“节点状态区块先于 response requirements”回归；`evaluation/suites/g4-real-task-work-tree-debug.json` 当前验证路径切到 `deepseek_direct / deepseek-v4-pro`（`allowPaidModels=true`）用于观察工作树强编排行为。
> 2026/5/27 继续同步：`evaluation/suites/g4-real-task-work-tree-debug.json` 进一步把“先服从 seeded currentNodeId / Working_Node / WorkContextStack，再完成七段报告格式”写进 suite 级 contract；`tests/test_g4_multiscene.py` 新增对应断言，避免 live case 再被纯格式化完整报告语气拉回 root-only。
> 2026/5/27 再同步：`modules/task-takeover/src/yggdrasil_task_takeover/plugin.py`、`packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/takeover.py`、`execution_loop_part_b.py` 与 `execution_loop_transitions.py` 已把“先核对再执行”升级为正式门禁：默认进入 `needs-clarification`，未确认前强制 `allowToolExecution=false` 且仅允许输出“任务理解+执行计划+确认问题”，并在执行收口阶段阻止未核对任务被标记完成；对应回归已补到 `tests/test_task_takeover.py`、`tests/test_prompting_runtime.py` 与 `tests/test_runtime_p4_foundation.py`。
> 2026/5/27 导出同步：已按 `YGGDRASIL_EVAL_PRESERVE_SANDBOX=1` 重跑 `eval:m8:live` 并固化 LongCat live 工件，新增 `tmp/longcat2-live-export-20260527/`（含 `longcat2-request.json`、`longcat2-response.json`、`longcat2-prompt-compiled.json`、`longcat2_full_dialogue.md` 以及 Flash-Lite 对照组同名工件），用于“provider 全字段请求/响应 + 对话可读化”审计与复盘。
> 2026/5/27 补充同步：新增 `tmp/longcat2-live-export-completed-only-latest/`，仅保留 `model invocation = completed` 的 LongCat2/Flash-Lite 记录，并统一输出 case 维度 `request/response/full-dialogue` 三件套，供“completed-only 复核”直接使用。
> 2026/5/27 继续补充同步：`tmp/longcat2-live-export-completed-only-latest/` 新增 `compile-process-full-dialogue.md` 与 `first-awakening-full-dialogue.md`，分别固化“编译阶段 system/user sections 全量文本”和“首次唤醒完整消息链（含 assistant tool-call / tool-result / final assistant / rounds）”，用于追踪从编译到首轮唤醒的全链路对话证据。
> 2026/5/27 本轮追加同步：新增 `tmp/longcat2-live-export-completed-only-latest/single-work-full-dialogue-success-or-awaiting-approval.md`，按“success 或 awaiting-approval（含 run completed）”口径导出单次工作全量对话，不改 case 判定规则。
> 2026/5/27 默认测试切换：新增 `evaluation/suites/g4-real-task-web-research-default.json`（网络检索 + 多源对比 + 矛盾处理），并将 `package.json` 的 `eval:g4:multiscene` 默认入口切到 `evalsuite_g4_real_task_web_research_default`；同时新增显式脚本 `eval:g4:web-research:default`。
> 2026/5/27 本轮排障同步：`evaluation_runtime/suite_cases_g4.py` 已为 G4 默认 live matrix 启动请求补齐 `takeoverPlanConfirmed/planConfirmed/confirmPlan/takeoverAutoConfirm`；`runtime_kernel/execution_loop_part_b.py` 在 takeover prepare 阶段增加 auto-confirm 回填与状态兜底；`prompting.py` 新增 auto-confirm 下对 takeover 协议与 response requirements 的 clarification 抑制分支；`runtime_kernel/execution_loop_part_a.py` 为 `cumulativeWindowSpanTokens` 增加基于 `effectiveContextWindow * max(windowIndex-1, restartCount)` 的跨度下限，避免窗口跨度被当前上下文 token 低估。
> 2026/5/27 本轮导出与提速同步：`observability_exporters.py` 新增 loopback OTLP 端点可达性缓存探测（本地 4318/localhost 不可达时快速禁用 exporter，避免重复超时重试）；同时新增一份成功 run 的 completed-only 导出包 `tmp/longcat2-live-export-completed-only-20260527-223151/` 并刷新 `tmp/longcat2-live-export-completed-only-latest/`（含 request/response/compiled-prompt/full-dialogue）。
> 2026/5/27 可视化同步：`tmp/longcat2-live-export-completed-only-latest/codex-worktree-viewer.html` 已新增单页审计视图，默认读取同目录 `request/response/prompt-compiled` 三件套，提供类 Codex 对话流、工作树预览、父节点返回醒目标记与节点上下文长度标签，便于快速复核真实执行路径。
> 2026/5/27 可视化修正：`codex-worktree-viewer.html` 已修复消息源字段读取（兼容 `request.messages` 与 `request.body.messages`），并新增“单节点 + 多窗口续跑”结构诊断横幅，避免把真实执行结构误判为页面漏渲染。
> 2026/5/27 可视化与导出可读性修正：`codex-worktree-viewer.html` 已新增“messages(本次调用) vs windows(任务生命周期)”口径说明，并对 system/user 消息中的重复 `## 结果/## 证据/## 风险/## 已知问题` 约束片段做折叠标注；同目录新增 `evalcase_g4_web_research_grid_storage_short64k-full-dialogue-clean.md` 作为清洗版对话记录，便于快速审阅而不丢失主干信息。
> 2026/5/27 重复提示词治理同步：`runtime_kernel/execution_loop_part_b.py` 与 `prompting.py` 已新增发送前合同文本去重（覆盖 `responseRequirements/restartMessage/resumeMessage` 与已知 footer 重复片段），避免重复约束继续进入模型上下文；新增 `scripts/find_llm_prompt_repetitions.py` 用于扫描 `.yggdrasil/state` 或 `tmp` 导出中的重复提示片段并输出 Markdown 报告；`tmp/longcat2-live-export-completed-only-latest/codex-worktree-viewer.html` 已支持目录/多文件集加载并展示任务生命周期内全部 invocation 消息流与窗口摘要。
> 2026/5/27 tmp 清理与会话聚合同步：`tmp/` 顶层已归档重整为 `tmp/_archive/<timestamp>/` + `tmp/task-conversations/` 双层结构；`llm_runtime_part_b.py` 新增 task 级会话合并写盘，运行时每次 invocation 会更新 `.yggdrasil/state/llm/task-conversations/task_<taskId>.json` 与 `index.json`，并镜像到 `tmp/task-conversations/data/`；统一 viewer 入口迁移为 `tmp/task-conversations/viewer/codex-worktree-viewer.html`，可直接消费合并记录并在单页展示整任务生命周期。
> 2026/5/27 行为修复同步：`runtime_kernel/snapshot.py` 与 `runtime_kernel/takeover.py` 已补齐 `takeoverPlanConfirmed/planConfirmed/confirmPlan/takeoverAutoConfirm` 在 restart snapshot 与 continuation payload 的透传，修复长窗口续跑时 auto-confirm 标记丢失导致再次回落 `needs-clarification` 的链路断点。
> 2026/5/27 可视化入口修复同步：`tmp/task-conversations/viewer/codex-worktree-viewer.html` 已支持从 merged index 读取并切换全部 `latestStatus=completed` 任务，默认加载最近成功任务的完整生命周期；同时新增 legacy 入口兼容页 `tmp/longcat2-live-export-completed-only-latest/codex-worktree-viewer.html` 自动跳转到新 viewer，避免旧书签失效。
> 2026/5/28 可视化解析修复同步：`tmp/task-conversations/viewer/codex-worktree-viewer.html` 已为 merged task-conversations 数据新增文本兜底解析（从 `takeover_protocol` / `scene_recovery` / `work_context_stack` 提取 `currentNodeId` 与 child 状态），修复“completed 任务显示 0 nodes、误判为前端漏渲染”的问题；同时 synthetic lifecycle 记录已补 `status` 字段，状态胶囊与生命周期条目可正确显示 `completed`。
> 2026/5/28 runtime 编排修复同步：`packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/takeover.py` 已取消非显式 takeover 的 root-only 单节点降级（改为保留 plan 生成的 work tree），并在父节点仍有未完成 child 时阻止直接交付完成，统一回到 `parent-orchestration-required` continuation；`tests/test_runtime_p1_hardening.py` 已新增回归用例锁住这两条行为。
> 2026/5/28 runtime 编排修复第2轮：`packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/takeover.py` 的 `parent-orchestration-required` 现已携带 `nextNodeId/preferredChildNodeId` 并将 `currentFocus` 收紧为“优先未完成 child”，同时在 work-context 栈写入 `cursorState=parent-orchestration-required:prioritize-child:<id>`；`tests/test_runtime_p1_hardening.py` 对应断言已补齐并通过（2 passed）。
> 2026/5/28 runtime 第3-5轮同步：`packages/python-sdk/src/yggdrasil_sdk/llm_runtime_part_b.py` 已把 `maxToolRounds` 封顶回合默认切换为 `tools=None` 最终收口模式，降低“最后回合继续工具调用 -> 超限失败”概率；`packages/python-sdk/src/yggdrasil_sdk/evaluation_runtime/suite_cases_g4.py` 已将 G4 live case 的 worker 轮询改为 `run_worker_once(..., timeout_seconds=1)` 并新增空队列超时保护（支持 `maxWorkerWaitSeconds` 与环境变量 `YGGDRASIL_G4_MAX_WORKER_WAIT_SECONDS`），避免评测在空队列上无限阻塞。

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

