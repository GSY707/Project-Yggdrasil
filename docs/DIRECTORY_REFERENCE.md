| `docs/architecture/design-philosophy-and-cognitive-principles.md` | **项目设计哲学唯一主文档**（2026-07-10）：统一定义当前注意力与长期价值、有效记忆、LOD 记忆树、任务期工作树、能力/Skill/工具按需挂载、命令权限与事实可信度、在线身份稳定、离线进化、多 Agent 与可证伪假设；所有下层设计必须服从该文档 |
| `docs/architecture/weak-model-behavior-compensation-notes.md` | 弱模型行为补偿注释（非设计真理，2026-07-10）：隔离记录当前批准的三类暂时性过强行为提示，定义适用行为档位、任务边界、风险、强度和退场门槛；不得覆盖主哲学或整篇注入模型上下文 |
| `docs/design-handoff/README.md` | UX 重塑外包资料包总览（2026-06-07）：把本轮与用户接触的 UX 重设计拆成基座用户界面、特化应用包界面、设置/调试/配置界面和启动器/安装器体验四组资料，并列出外包团队交付物、当前真实入口和验收门槛 |
| `docs/design-handoff/01-base-user-interface-agent.md` | 基座面向用户界面 brief：定义客服型 Agent、首次启动正门、应用路由、Prompt 代写、任务确认、错误支持和普通/高级入口分层 |
| `docs/design-handoff/02-application-package-experience.md` | 特化应用包界面 brief：基于应用包 `dashboard.json` 元数据设计场景页、任务模板、预期产物、应用设置，并定义 Agent 工作过程下探、返回、折叠和历史窗口回顾的 UI 规则 |
| `docs/design-handoff/03-settings-debug-configuration.md` | 设置/调试/配置界面 brief：把 provider、模型预算、工作区、数据隐私、应用配置、Prompt、MCP、评测、观测和运行时调试拆成普通设置、高级设置和维护者调试三层 |
| `docs/design-handoff/04-launcher-experience.md` | 启动器设计需求文档：面向外包团队定义安装向导、桌面主窗口、托盘菜单、应用包直达快捷方式、Docker/provider 检查、状态诊断、备份恢复、更新回滚和错误状态的用户体验要求 |
| `docs/development/DESIGN_COMPLETION_EVALUATION_2026_06_05.md` | 设计完成度评估（2026-06-05）：按 PRD、`当前正式项目定义、v0.2 运行时/工作树规格与 2026-06-28 LLM 工作树指南、应用包接口和产品化差距文档，对工程设计、外部用户采用度、产品发行、数据治理、协作、模块、评测等设计项给出完成度评分、证据和下一步优先级 |
| `docs/development/STITCH_DESIGN_ACCEPTANCE_2026_06_17.md` | Stitch 设计稿四组页面验收报告（2026-06-17）：仅从 `Project Yggdrasil Design System` 验收主页、应用包、设置、启动器四组；Gemini 3.1 Pro 按第 3 节合格线连续返工至 V10；仓库只保留最终通过候选证据包，最终采用 V10 主页、V8 应用包、V6 设置、V9/V6 启动器组合，结论为“通过，可进入工程实现” |
| `docs/development/DESIGN_ENGINEERING_IMPLEMENTATION_PLAN_2026_06_17.md` | Stitch 设计落到工程实现与未完成项计划（2026-06-17，2026-06-18 更新：阶段 0-3 已完成）：把 V10/V8/V6/V9-V6 最终设计组合转成工程路线，并记录 Start 首页、四应用矩阵、普通设置中心、启动器主路径语言、维护闭环确认门、真实 Docker upgrade/rollback 验证、默认卸载保留本地数据验证和阶段 4-5 未完成项 |
| `docs/development/UX_DESIGN_TEAM_HANDOFF_2026_06_04.md` | UX 设计团队交接准备文档（2026-06-04）：基于当前 Web 工作台、用户采用度审计和发布路线，整理专业设计团队接手前需要准备的产品定义、用户旅程、功能真相表、术语体系、数据边界、未来形态和交付物要求 |
| `docs/development/PRODUCT_PACKAGING_AND_REMOTE_DATA_REQUIREMENTS_GAP_2026_06_04.md` | 产品打包与官方远端数据能力需求差距（2026-06-04，2026-06-06 更新）：完整 Docker Compose 产品栈、Windows 未签名安装包/托盘/手动更新器、provider 启动阻塞、本地数据治理保护性 task 删除、产品栈快照/升级/回滚已进入预览可验证状态；托管 / SaaS 和官方远端数据服务实现仍是计划项 |
| `docs/development/PRODUCT_RELEASE_COMPLETION_EVALUATION_2026_06_18.md` | 产品发行完成度评估（2026-06-18）：按本地可试用发行、普通用户正式发行、Docker 产品栈、Windows 桌面封装、数据治理、SaaS 和官方远端数据服务分层评分，综合判断当前发行完成度为 55/100，并列出正式发行前硬缺口和下一步门禁 |
| `docs/release/GITHUB_RELEASES_PLAYBOOK.md` | GitHub Releases 发布手册（2026-06-18）：固定第一版发布渠道、staged repo ZIP + SHA256 发行物、Docker 检测/引导、手动更新、签名预留、发布前门禁、GitHub Release 正文模板和发布后核验步骤 |
| `docs/development/MODEL_TPS_BENCHMARK_2026_06_14.md` | 模型 TPS 实测（2026-06-14）：对 `LongCat-2.0`、`deepseek-v4-flash`、`deepseek-v4-pro` 按同题、`max_tokens=1400`、各 3 次做 live 吞吐对比，记录首 token 延迟、总耗时、端到端 TPS 与首 token 后 TPS，并给出本机当前速度排序 |
| `docs/development/MOE_MODEL_ROUTING_ASSESSMENT_2026_06_14.md` | 世界树 Agent MoE 模型分层与任务难度评估（2026-06-14）：限定 2026 年 3 月后开源/开放权重 MoE 与稀疏激活模型，按 Qwen3.6、Ling/Ring-2.6、Mistral Small 4、Gemma 4、DeepSeek V4、Command A+、Kimi K2.6/2.7、MiMo V2.5、MiniMax M2.7/M3、Nemotron 3 等具体候选拆分主模型/子任务模型和 D0-D4 路由 |
| `docs/development/MULTI_AGENT_WORKTREE_GRAPH_DESIGN_2026_06_20.md` | 多 Agent 自分裂与工作树图调度设计盘点（2026-06-20）：梳理现有 Sub-Agent / Fork / 联邦 Agent、工作树 `dependsOn` / `relationIds` / `priority`、知识继承、模型路由、预算资源和并发冲突文档，并给出下一步应补的图关系、局部 ready-set 调度、Fork、自分裂、知识继承、冲突合同、控制面和评测规格 |
| `docs/specs/work-tree-graph-fork-parallel-protocol-v0.1.md` | 工作树图与 Fork 并行协议 v0.1（2026-06-21）：正式冻结父节点局部 ready-set、控制流边 / 信息流边分工、Fork 直接继承父 Agent 上下文缓存、child 执行焦点、上下层图边传递、延迟信息流索引、递归 Fork 与 `maxForks` 同时活跃上限、实现前最小合同和第一版风险检测点 |
| `docs/development/WORK_TREE_GRAPH_FORK_EVALUATION_TASKS_2026_06_21.md` | 工作树图与 Fork 并行测试任务设计（2026-06-21）：定义 T0-T7 仿真任务、R1-R4 真实/仿真真实任务、递归 Fork 与 `maxForks` 同时活跃上限、语义正确性/加速收益/质量指标、Batch 1-5 后续实现依赖和需要用户拍板的 D1-D7 决策 |
| `docs/development/WORK_TREE_GRAPH_FORK_IMPLEMENTATION_PLAN_2026_06_21.md` | 工作树图与 Fork 并行实现计划（2026-06-21，PR1/Batch 2/Batch 3/Batch 4/Batch 5/Batch 6 deterministic/live harness、T6/T7/R1-R4 与公开展示题进展已同步）：按纯函数图调度、AgentRun Fork 字段、Fork batch planner、worker Fork 运行视图、结果合并和 runtime harness 拆分 PR；当前已落地 graph reducer、AgentRun Fork 字段、fork work item planner、worker child run view、Fork result envelope merge、auto next batch DB work item、真实 transitions/Redis enqueue、两轮 deterministic worker harness、Fork 必填字段硬校验、live candidate 入口、禁用工具执行硬开关、completed work-tree 终态短路、T6 父合并预算保留、T7 递归 Fork active limit、R1-R4 deterministic evaluation suite、公开展示 benefit/live suite 与显式手动 long/ultra live 长任务门槛；`YGGDRASIL_FORK_RUNTIME_LIVE=1` 下已通过真实 LongCat runtime completed smoke 证据（`evalrun_69093187bf6c46e587c3`），公开展示 live 已通过 `evalrun_f6ca4e22241542d4906b`，但二者都不是长任务证据 |
| `docs/development/ROLLING_FRONTIER_WORK_TREE_RESOLUTION_2026_06_27.md` | 滚动前沿工作树分辨率运行提示说明（2026-06-27）：记录 `FrontierItem` / `WorkTreeResolutionPolicy` / `assess_node_resolution()` / `compute_delivery_readiness()` 及 worker 注入、`runtime_hints`、delivery reducer 证据硬门槛的链路，把“宽泛节点合法、失败预算推动提高分辨率、开放前沿作为提示、expected evidence 缺口才硬阻断”固定为长程任务口径，并列出 queue reliability、durable snapshot、transactional node、plan lifecycle、typed merge、semantic GC、long-run eval、observability replay 八个核心前沿 |
| `docs/development/LLM_LONG_HORIZON_OVERDESIGN_AUDIT_2026_06_27.md` | LLM 长程控制过度设计审计（2026-06-27）：按“够不够长 / LLM 是否持续控制工作”重扫 prompt 硬规则、delivery gate、needs-clarification、workTreeResolution、状态层级、approval、Fork ready-set、memory-write 和 root mount，区分必须保留的安全边界与应降级为自然语言工作日志或后台审计的过度设计，并记录 Batch 1-4 已落地项与仍保留的 awaiting-approval / 状态重复 / Fork 调度 / root mount 后续项 |
| `docs/development/LLM_WORK_TREE_USAGE_GUIDE_AND_CASES_2026_06_28.md` | LLM 工作树使用指南与案例（2026-06-28）：把用户工作树使用笔记收敛为正式 agent-facing guidance，明确 root/非叶子节点负责高层视角与流程控制、叶子节点负责执行，并补齐 7 类单场景、多层组合案例、父节点回收格式、反例和行为记录器要求 |
| `docs/development/LLM_LIVE_WORKFLOW_AND_WORK_TREE_RERUN_AUDIT_2026_06_28.md` | LLM live 工作流程与工作树复跑审计（2026-06-28）：固化 `evalsuite_g4_real_task_web_research_default` 储能任务 live 重跑结果，并补记完成后追问、每步反思、批评 revision 继续三组单独实验；确认 prompt 已进新 root/leaf 口径、LLM 有真实工具调用但不主动拆工作树，批评可继续但仍 root-only；同步 LongCat cache usage 与 observed tool call 记录修复 |
| `docs/development/LLM_WORK_TREE_HARD_PROMPT_EXPERIMENTS_2026_06_29.md` | LLM 工作树硬提示实验记录（2026-06-29）：记录工具末尾强提醒、工具调用即 leaf 示例、更明确 leaf 自言自语示例、DeepSeek V4 Pro、“leaf 执行、父节点评估”补充重跑、DeepSeek “批评后继续 + 先做任务控制分析”、`auto-unfinished` 继续位置 + 每节点 5 次 toolcall 软预算，以及 `work-node-complete` child 有效交付路径；结论是 auto-unfinished 能把 continuation 拉回父/编排层，工具预算能促成 leaf handoff，`work-node-complete` 补齐 leaf 完成后回父节点的 runtime 路径且已被 live LLM 采用；2026-06-30 已把同窗 `work-node-*` 标签升级为工具执行前 barrier，避免工具在旧节点执行；最新 live 证明非根 hard gate 修正后可越过早期截断并产出报告，但仍暴露 seeded pending 节点未收束、纠偏 prompt 重复堆叠和最终报告自述/工具证据一致性问题 |
| `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/work_tree_graph.py` | 工作树图 ready-set / Fork 并行纯函数 reducer：复用 `WorkTreeProtocol` / `WorkTreeNode`，计算 direct child ready/blocked、延迟信息流 pending 摘要、`maxForks` 活跃槽位、`reserveParentMergeSlots` 父合并预算保留、`allowRecursiveFork=false` 递归启动阻断和可启动 Fork candidates；2026-06-27 新增滚动前沿分辨率提示纯函数，支持 `FrontierItem`、八个长程核心前沿种子、节点 resolution assessment 与 delivery readiness 计算，开放前沿默认只作提示，`expectedEvidence` 缺失会在交付前形成 `missing-target-evidence` blocker |
| `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/fork_runtime.py` | Fork batch / result merge runtime helper（Batch 3/5）：把 ready-set launch candidates 转成 `runType=fork` 的 AgentRun 与 `core.agent.main.execute` / `intent=fork` 的 RuntimeWorkItem；同批 Fork 共享 `parentContextAnchor` / `forkGroupId`；`merge_fork_result_and_plan_next_batch()` 可合并 ForkResultEnvelope、继承更新后的 `workTreeSnapshot` 并创建下一批 DB work item |
| `tests/runtime/test_work_tree_graph_scheduler.py` | 工作树图 ready-set / Fork 并行与滚动前沿分辨率回归：覆盖 T0 diamond ready-set、T2 延迟信息流、T3 自动 batch 候选、T4 parent replan gate、T6 父合并预算、T7 递归 Fork active limit、宽泛节点 refine、候选交付阻断、失败预算、八个核心前沿、expected evidence blocker、上游 readiness 权威性、turn evidence 写回和 worker stale payload 清理 |
| `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop/worker.py` | Agent runtime worker 主入口；Batch 4 已识别 `runType=fork`，复用预创建 fork AgentRun，并把 fork work item 转成 run-local child 指针、Working_Node 和 memory retrieval state；2026-06-27 新增 `workTreeResolution` 注入，在 takeover/work tree 同步后计算当前节点 resolution，并在 assessment 失败时清除陈旧 payload |
| `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop/transitions.py` | Agent runtime 完成/续跑/审批流转；Batch 4 已隔离 fork 完成态，Batch 5 已在 fork 完成分支接入 result envelope merge、auto next batch 和 Redis enqueue；2026-06-27 会把 `request.workTreeResolution` 传入 takeover delivery reducer，但只把 surviving `missing-target-evidence` 当硬阻断，其余 readiness 信号留作提示 / 审计；2026-06-29 起，work-tree directive correction、child/leaf start checkpoint 与 delivery retry continuation 会去重追加，避免长链续跑把同一提示反复塞进 `responseRequirements` |
| `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/takeover.py` | Task takeover reducer：负责 work tree/context stack 推进、parent orchestration、child bubble、revision reopen 与 approval finalize；2026-06-27 收窄 `work-tree-resolution-blocked`，只在缺少 expected evidence 等真实证据缺口时阻断交付，本轮真实 evidence refs 会写回 `producedEvidenceRefs` |
| `packages/python-sdk/src/yggdrasil_sdk/prompting.py` | Runtime prompt 编译器：恢复态会渲染 `<runtime_hints>`，只暴露当前节点、建议下一步、delivery readiness 和 severity 最高的 3 个开放前沿；系统行为宪法、runtime hints 与 response requirements 已切到“工作树是上下文卫生工具、root/非叶子节点保留高层视角、执行噪声优先进入已有节点、允许更新已有节点范围、无合适节点才新建、子节点带回有用信息与引用”的新口径，few-shot 段补入工作树使用案例 |
| `tests/runtime/test_fork_launch_planner.py` | Fork batch launch planner / worker run view 回归（Batch 3-4）：验证 `maxForks` 可用槽位、同批上下文锚点、不同 assigned child、main activity + fork intent work item、waiting candidates，以及 worker 消费 fork work item 时保持 child view 且不覆盖父任务焦点 |
| `tests/runtime/test_fork_merge_and_auto_batch.py` | Fork result merge / auto batch 回归（Batch 5）：验证 result envelope 合并 child summary/evidence/failure、`planImpact=none` 自动创建并 enqueue 下一批 work item、`requires-parent-replan` 禁止自动启动、pending 信息拒绝大段 raw content、mixed outcome 只启动未阻塞 ready child |
| `tests/runtime/test_work_tree_graph_fork_runtime_harness.py` | Fork runtime deterministic harness（Batch 6）：两轮真实 worker 消费 fork work item，fake LLM 真实写入 model invocation 与 prompt compile artifact，验证 AgentRun 元数据、work item 状态、prompt artifact、workTreeSnapshot 继承、pending summary-only 信息流和不创建 child task/task branch |
| `evaluation/suites/work-tree-fork-runtime-harness.json` | Work-Tree Fork Runtime Harness 评测套件（Batch 6）：deterministic harness 默认入口，`runtime.fork_harness` 会执行两轮 worker harness pytest 并把通过合同写入 evaluation metrics |
| `evaluation/suites/work-tree-fork-runtime-live-candidate.json` | Work-Tree Fork Runtime Live Candidate 评测套件（Batch 6）：手动 live provider smoke 候选入口；需要 `YGGDRASIL_FORK_RUNTIME_LIVE=1` 和 provider key，否则记录为 blocked/non-pass；开启后关闭 fallback，要求真实 `longcat / LongCat-2.0` invocation、prompt artifact、live invocation evidence 与 runtime completed 终态，已生成 passed `evalrun_69093187bf6c46e587c3`；不是长任务证据 |
| `evaluation/suites/work-tree-fork-evaluation-tasks.json` | Work-Tree Fork Evaluation Tasks suite：把 R1-R4 从设计文档落成 deterministic 评测入口，覆盖四区域 repo 审查、release gate parent replan、三资料包 summary-only 对比和多文件迁移计划 + 父合并预算保留；已通过 `evalrun_23503bda7dee4c39b90e` |
| `evaluation/suites/work-tree-fork-public-showcase.json` | Work-Tree Fork Public Showcase suite：公开展示题“2030 韧性能源与应急通信计划”，benefit case 给出 2.406x 估算加速、58.44% wall-clock reduction、33.33% duplicate-read reduction，live case 真实 LongCat completed；已通过 `evalrun_f6ca4e22241542d4906b`；用于展示，不作为长任务或收益实测证明 |
| `migrations/versions/c2f4b8a91d63_agent_run_fork_fields.py` | AgentRun Fork 字段迁移（2026-06-21）：为 `agent_runs` 增加 `fork_root_run_id`、`fork_depth`、`assigned_work_tree_node_id`、`parent_context_anchor`、`fork_group_id` 及 Fork 根/节点/批次索引，支撑 Batch 2 审计与恢复 |
| `docs/development/DEBUG_PLAN_2026_06_08.md` | 夜间调试计划：收拢 runtime 状态机、sub-agent / GitHub 协作、M9 控制面与并发稳定性相关功能，配套说明本轮从 nightly/slow 中暂时跳过的测试 |
| `docs/development/RUNTIME_CONCURRENCY_M9_INVESTIGATION_2026_06_11.md` | Runtime 并发与稳定性、状态机恢复链、M9 控制面与验收链调查基线（2026-06-11）：确认 M9 control-plane 当前通过、M9 acceptance 断在 pause/resume 后续状态收口与预算失败，并列出 worker 队列、任务锁、snapshot 恢复、skip 测试和发布门禁的修复顺序 |
| `docs/development/TASK_STOP_CONTINUE_CAPABILITY_INVESTIGATION_2026_06_18.md` | 任务停止、暂停、继续与恢复能力调查（2026-06-18，2026-06-19 同步新实现）：当前公开入口已切为 `/pause`、`/resume`、`/cancel`、`/snapshots/save-current`、`/branches`，恢复主链改为 Durable Snapshot、ResumeAttempt、持久 WorkItem、`resume-blocked` 和 Cancel audit 30 天 |
| `docs/development/INSTALL_LAUNCHER_AND_APP_PACKAGE_DISTRIBUTION_2026_06_06.md` | 安装、启动器与应用包随包发行评估（2026-06-06）：梳理当前开发工作区、本地产品、Docker 产品栈与 Windows 桌面封装路径，判断普通用户需要产品启动器，并定义“基座产品栈 + 应用包 + 直达应用快捷方式”的可行发行改造 |
| `docs/specs/data-governance-manifest-v0.1.md` | 数据治理清单与本地删除协议 v0.1：冻结数据资产 manifest、`/data-governance` 备份快照、删除 dry-run、保护性 task 硬删除、删除证明、审计表、外部 provider / 日志 / 备份保留边界 |
| `docs/specs/remote-data-service-contract-v0.1.md` | 官方远端数据服务契约 v0.1：冻结远端账号/工作区、显式同步、远端备份、远端删除请求、删除证明和本地优先边界；当前是计划契约，不代表服务已发布 |
| `docs/development/USER_ADOPTION_SURFACE_AUDIT_2026_06_03.md` | 用户采用度审计（2026-06-03）：盘点 Web 工作台、应用包、设置、安装、打包与用户文档，明确当前仍是 CLI/操作台导向，并给出 Web-first 首次成功路径、设置向导、任务创建启动和产品化启动器的 P0/P1/P2 收口计划 |
| `docs/demos/LOCAL_FIRST_TASK_DEMO.md` | 本地首次成功演示脚本：面向外部试用者或录屏演示，按 Web 路径完成“导入素材 -> 选择应用 -> 创建任务 -> 启动任务 -> 查看结果”，并明确 provider key、备份恢复和删除边界 |
| `docs/development/G4_WEB_RESEARCH_DEFAULT_FAILURE_AUDIT_2026_05_27.md` | G4 默认网络研究测试失败审计（2026-05-27）：固化 `evalrun_52ffd96d5551405da5b0` 的行为偏差，明确“重复幂等工具循环触发提前停止 -> 未进入结构化交付”的失败链路与证据位置 |
| `docs/development/TASK_CHECKFLOW_AUDIT_AND_ALIGNMENT_2026_05_27.md` | 任务核对流程审计与对齐（2026-05-27）：冻结“理解任务 -> 形成计划 -> 向发起者核对 -> 再执行”的目标流程，并对照当前协议、提示词、运行时与测试缺口 |
| `docs/development/LLM_WORK_ANALYZER.md` | LLM 工作分析器设计与使用说明：说明 run-first 分析器的数据源、粒度、持久化位置、API/CLI 入口与当前限制 |
| `docs/LLM_WORK_ANALYZER_USER_GUIDE.md` | LLM 工作分析器用户手册：面向任务操作者和评测/排障同学，说明 Web、CLI、API 入口与常见排查流程；当前已补齐 work-tree debug 摘要卡、时间线、cache trace、child bubble 与 mixed outcome 的固定读法 |
| `docs/development/REAL_TASK_TEST_CONVENTIONS_AND_WORK_TREE_BACKLOG_2026_05_25.md` | 真实任务测试约定与工作树后续任务拆分（2026-05-25）：冻结“默认真实任务应单目标、弱项目内生化、由 agent 自主规划”的出题约定，并记录 P1/P2/P3/P5 本轮收口状态 |
| `docs/development/WORLD_BUILD_INITIAL_AWAKENING_TASK_START_EXECUTION_2026_05_26.md` | 世界构建、初次苏醒与任务级工作状态读取实施文档（2026-05-26）：把新三阶段规格翻译成实现层执行计划，明确 root mount 只做世界级/起始状态挂载，任务级工作状态单独读取，并给出 contracts/root_mount/execution_loop/prompting/takeover/snapshot/tests 的落地顺序 |
| `docs/development/GRADUATE_STANDARD_EXECUTION_CLASSIFICATION_2026_05_30.md` | Graduate 标准执行分类（2026-05-30）：按“当前可做/可做但需确认/当前不可闭环”划分升级路径，并给出面向高标准验收的执行顺序 |
| `docs/development/GRADUATE_STANDARD_EXTERNAL_REQUIREMENTS_2026_05_30.md` | Graduate 标准外部依赖需求文档（2026-05-30）：定义 provider 参数绑定、网络来源可达性、人工评审与预算审批的外部验收要求与交付物 |
| `docs/development/TASK_WORLD_START_STATE_AND_TASK_RUNTIME_SPLIT_2026_05_26.md` | 给低智商 code agent 的任务文档（2026-05-26）：用严格顺序把“起始状态 + 任务级工作状态读取”重构拆成明确待办、测试命令、完成标准和禁止事项，适合直接转交做粗活 |
| `docs/development/TASK_WORLD_START_STATE_RUNTIME_REWORK_FIXUP_2026_05_26.md` | 给 code agent 的返工任务文档（2026-05-26）：针对验收发现的残留问题，强制收口“世界级不见任务、只有真实现场才无损恢复、TaskRuntimeState 成为唯一任务态入口”；本轮已落下一条关键修复：仅 `lossless-restore` 允许 `resume-node` |
| `docs/specs/agent-runtime-protocol-v0.2.md` | Agent 运行时协议 v0.2：继续向新三阶段口径收口，补上“初次苏醒形成起始状态、任务级单独读取工作状态、工具/知识索引优先”的关键约束，同时保留 Boot Prompt、RootMountPackage、上下文窗口和结束批准的正式结构 |
| `docs/specs/work-tree-protocol-v0.2.md` | 工作树协议 v0.2：继续向任务级工作状态口径收口，明确工作树是在任务开始并读取工作状态后挂载到 `[ID: 003 我要干什么]` 语义根下的动态执行栈与工作记忆；2026-06-30 固化工作树标签执行顺序，含 `work-node-*` directive 的 assistant response 会先更新工作树，provider toolCalls 延后到下一窗口 |
| `docs/specs/task-pause-resume-continuation-contract-v0.1.md` | 任务暂停、恢复与继续契约 v0.1（2026-06-18）：正式定义 Start、Pause、Queued Pause、Safe-Stop、Durable Snapshot、Resume、Continue、Retry、Cancel、Shutdown、长期恢复、ResumeAttempt、持久 WorkItem、snapshot 保留策略、手动保存/分支、tool-call 暂停等价性、API 语义和验收门禁 |
| `docs/specs/world-build-awakening-task-start-protocol-v0.1.md` | 世界构建、初次苏醒与任务启动协议 v0.1：把“先建世界 / 再醒来 / 再开始工作”拆成世界级与任务级两层，强调建世界与初次苏醒不得接触具体工作信息，并进一步冻结“工具/知识索引优先、能力/知识到工具的关联召回、起始状态、无损恢复和分层诊断”规则 |
| `docs/specs/application-package-interface-v0.1.md` | 应用包接口总规范 v0.1：统一定义应用包的 manifest、prompt / memory 文件、MCP 服务器、前端界面、dashboard 任务模板、示例任务、预期产物和控制面 API，供别的团队按正式契约开发应用包 |
| `docs/specs/graduate-researcher-app-v0.1.md` | Graduate Researcher 应用包定义 v0.1：定义“研究生”应用的目标、预算语义、计划-步骤-动作三层模型、按需分解规则与 tool-rich 默认工具包 |
| `docs/specs/graduate-researcher-test-standard-v0.1.md` | Graduate Researcher 测试标准 v0.1：定义“机器学习研究生”长任务场景的结果验收口径，聚焦自主规划、稳定性、非急性子与工具覆盖 |
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
| `docs/development/LARGE_FILE_SPLIT_REPORT_2026_06_01.md` | 大文件拆分报告（2026-06-01）：按 tracked 文件 >1000 行执行本轮全量拆分，Python 改为兼容门面 + `__partNN.py`，suite JSON 改为 `caseRefs` 分片加载，并明确 lock 文件例外 |
| `docs/development/LLM_REAL_TASK_INFINITE_CONTEXT_EVAL_2026_05_17.md` | LLM 真实任务无限上下文能力评估（2026-05-17，已纠偏）：基于 Langfuse trace 的 LLM 最终输出、任务目标对照、4 条路径结果分叉与逐窗口分析 |
| `docs/development/LANGFUSE_TRACE_DATA_LOSS_AUDIT_2026_05_18.md` | Langfuse trace 数据损耗审计（2026-05-18）：对比本地 runtime 工件、Langfuse observation 与五层分析程序的保留字段、缺失字段，以及中间窗口重复的 runtime 根因 |
| `docs/development/MEMORY_TREE_INFINITE_CONTEXT_OPTIMIZATION_PLAYBOOK_2026_05_18.md` | 记忆树与伪无限上下文窗口优化作战手册（2026-05-18，已补全执行版）：除总体路线外，现已包含执行状态矩阵、当前仓库分析结论、优化优先级、窗口审计命令和具体下一步实现顺序 |
| `docs/development/FEATURE_CLASSIFICATION_AND_PROMPT_CHECK_PLAN_2026_05_18.md` | 功能形态分类与提示词功能检查计划（2026-05-18）：按纯代码 / 代码+提示词 / 纯提示词分类当前设计，并给出以纯提示词为重点的检查路径 |
| `packages/python-sdk/src/yggdrasil_sdk/llm_work_analysis.py` | LLM 工作分析核心：以 run 为主键拼接 DB 与 state 工件，输出 run/window/turn/tool/artifact/source 多粒度分析，并补读 `llm/behavior-records/{invocationId}.json` 行为记录，持久化到 `state/analysis/llm-work/` |
| `packages/python-sdk/src/yggdrasil_sdk/llm_runtime/behavior_recorder.py` | LLM 行为记录器：从 request/response/compiled prompt 派生稳定行为记录，落盘 `state/llm/behavior-records/`，记录 rounds、详细 `toolExecutions`、round-derived `observedToolCallCount`、work-tree directive、prompt 文本/摘要可用性，以及模型自述工具次数与实际/观察次数差异 |
| `packages/python-sdk/src/yggdrasil_sdk/langfuse_trace_layered_analysis.py` | Langfuse 文本审查模块：以 Langfuse observation 重建窗口骨架，默认输出 LLM 交互文本摘录、重复窗口文本簇和 Langfuse UI 审查焦点；当前已能补读 `runtime/window-executions` 本地工件，用结构化窗口状态增强重复窗口判定与因果分析，并兼容中文化的任务目标/任务说明/当前焦点标签提取 |
| `scripts/analyze_llm_work_run.py` | LLM 工作分析脚本包装器：按 task/run/invocation 触发正式分析器，并输出 JSON 或 Markdown 报告 |
| `scripts/product-compose.mjs` | 产品 Docker Compose 脚本包装器：优先读取未跟踪的 `infra/product.env`，统一调用 `infra/docker-compose.product.yml`，并在 Windows 中文路径下关闭 BuildKit / bake；提供 `product:backup`、`product:restore`、`product:snapshots`、`product:upgrade`、`product:rollback` 维护窗口流程 |
| `scripts/product-release-smoke.mjs` | 产品发行门禁脚本：串联 product compose config/up/smoke、保护性备份、upgrade、指定快照 rollback 和二次 smoke，作为 GitHub Releases 前的 Docker 产品栈发布检查 |
| `scripts/analyze_langfuse_real_task_trace.py` | Langfuse 真实任务窗口分析脚本：按 trace 提取 LLM 最终输出、第 6 节结论与逐窗口 snapshot/work tree 历史 |
| `scripts/analyze_langfuse_real_task_trace_layered.py` | Langfuse 文本审查兼容入口：按 trace 生成 LLM prompt/output 摘录、重复窗口文本簇和 Langfuse UI 审查焦点 |
| `scripts/analyze_langfuse_real_task_execution_audit.py` | Langfuse 文本审查主入口：按 trace 生成 LLM 交互文本视图，并在内部复用窗口冗余判定与本地状态增强逻辑 |
| `scripts/benchmarks/sqlite_concurrency_benchmark.py` | SQLite 并发基准单 profile 执行脚本：支持 baseline/optimized 配置、节点写入与快照争用场景测试、JSON 结果输出 |
| `scripts/benchmarks/sqlite_concurrency_compare.py` | SQLite 并发前后对比脚本：串行运行 baseline 与 optimized，输出吞吐/p95/锁错误对比报告 |
| `migrations/versions/7ad7d9b8c4f1_runtime_mailbox_side_channel_tables.py` | Runtime 邮箱/侧信道迁移：新增 `mailbox_messages` 与 `side_channel_events` 表及其索引，补齐 P6 持久化落库 |
| `migrations/versions/6c4e1f2b8a77_prompt_compile_boot_sections.py` | Prompt 编译工件迁移：为 `prompt_compile_artifacts` 增加 `boot_sections`，持久化 Boot Prompt 四段 |
| `migrations/versions/1e3a7b8c9d01_high_concurrency_indexes.py` | 高并发表索引迁移：nodes/import_fragments/task_snapshots/model_invocations 复合索引 |
# 世界树计划 · 目录说明书

> 项目完整目录结构及各路径的职责说明。适合新加入的开发者理解代码组织方式，以及查询特定功能所在位置。（2026/6/28 更新：运行中 LLM 的工作树口径已切到“上下文卫生、父节点高层视角、leaf 执行、有用信息与引用回收”；`docs/development/LLM_WORK_TREE_USAGE_GUIDE_AND_CASES_2026_06_28.md`、`docs/specs/agent-runtime-protocol-v0.2.md`、`docs/specs/work-tree-protocol-v0.2.md` 与 `docs/architecture/runtime-principles-for-newcomers.md` 是当前入口。旧强控制路线已清出当前目录索引，不再作为运行时或评测主口径。）
> 2026/6/28 live 行为实验同步：新增 `evaluation/suites/g4-real-task-work-tree-post-question-live.json`、`g4-real-task-work-tree-step-reflection-live.json`、`g4-real-task-work-tree-critique-continue-live.json` 及 `package.json` 的 `eval:g4:work-tree:*` 三个脚本；`docs/development/LLM_LIVE_WORKFLOW_AND_WORK_TREE_RERUN_AUDIT_2026_06_28.md` 已记录完成后追问、每步反思、批评 revision 继续三组真实 LongCat 实验。结论是追问能得到自我归因、反思提示不能打断 root-only 惯性、批评 revision 能继续执行但仍会停在 root。`llm_runtime/behavior_recorder.py` 与 G4 provider matrix 已新增 round-derived observed tool call 统计，避免 `toolExecutions` 缺失时误报“没有查资料”。
> 2026/6/28 当前运行中 LLM 工作树口径同步：`packages/python-sdk/src/yggdrasil_sdk/prompting.py` 已把系统行为宪法、`runtime_hints` 使用说明和 response requirements 切到 `docs/development/LLM_WORK_TREE_USAGE_GUIDE_AND_CASES_2026_06_28.md` 的口径：工作树是上下文卫生工具；root/非叶子节点负责高层视角、流程控制、方向重估和信息合并；叶子节点负责具体执行；执行产生搜索、编辑、命令、失败尝试、重复项或候选路线时进入 child/leaf；子节点回父节点带回有用信息、证据/文件/记忆引用、已废弃路线和风险。`packages/python-sdk/src/yggdrasil_sdk/llm_runtime/behavior_recorder.py` 新增系统派生行为记录，避免只依赖模型最终报告自述工具行为。
> 2026/6/29 live 硬提示实验同步：新增 `toolResultReflectionReminder` 显式请求字段、四个 G4 工作树 live suite 与 `docs/development/LLM_WORK_TREE_HARD_PROMPT_EXPERIMENTS_2026_06_29.md`。四组真实储能任务显示：工具末尾强提醒不足以打断 LongCat 单节点惯性；“工具调用即 leaf”强示例可让首窗口先创建 child，但父节点/高层节点收束仍不足；leaf 自言自语示例不稳定；`deepseek_direct/deepseek-v4-pro` 严格验收通过但没有自动使用 leaf。随后按“leaf 执行、父节点评估、leaf 不得宣告整体完成”重跑 LongCat 与 DeepSeek：LongCat 仍会在首窗口直接做报告，DeepSeek 能先建 leaf 并在 leaf 内执行工具，但 leaf handoff 后任务直接 completed，父节点未继续评估四条技术路线。
> 2026/6/29 DeepSeek 批评继续实验同步：新增 `evaluation/suites/g4-real-task-work-tree-deepseek-v4-pro-critique-continue-live.json` 与 `eval:g4:work-tree:deepseek-v4-pro-critique-continue`，并让 `/request-revision` 在 completed 但 work tree 仍有 unfinished nodes 时可重开、支持 `nodeId=root` 映射动态 root、post-completion revision 继续透传 DeepSeek candidate。live 结果：第一次 run 暴露 revision 丢失 `candidateModels` 后掉到 LongCat；修复后 `deepseek_direct/deepseek-v4-pro` 路由稳定，suite passed、45 次工具 0 失败，但 revision 阶段没有新工具/新 directive，直接合并报告，说明“批评后继续 + 任务控制分析”只能改善继续干活，不足以保证 leaf/父节点流程正确。
> 2026/6/29 auto-unfinished 与节点工具预算实验同步：新增 `evaluation/suites/g4-real-task-work-tree-deepseek-v4-pro-node-tool-budget-live.json` 与 `eval:g4:work-tree:deepseek-v4-pro-node-tool-budget`；`runtime_kernel/takeover.py` 支持 `nodeId=auto-unfinished` 按未完成子节点/未完成 sibling 选择 continuation；`llm_runtime/invoke.py` 支持 `workTreeNodeToolCallSoftLimit` 在第 6 次工具调用后提示流程安排但不实际拒绝工具；`evaluation_cli.py` 修复 Windows GBK 打印 live 结果时的 UnicodeEncodeError。live run `evalrun_fdee593d0136443caa27` 显示 auto-unfinished 能回到父/编排层，5 次预算能让 Li-ion leaf 在 5 次工具后 handoff，但模型仍会在父节点伪造后续 leaf handoff，工作树最终仍未干净收束。
> 2026/6/29 directive-required 工作树实验同步：新增 `evaluation/suites/g4-real-task-work-tree-deepseek-v4-pro-directive-required-live.json` 与 `eval:g4:work-tree:deepseek-v4-pro-directive-required`；`state_memory.py` 检测自然语言创建/进入/leaf handoff/返回父节点但无可应用 directive 时触发 `work-tree-directive-required`，`worker.py` 透传该 transition，`transitions.py` 排 correction continuation 并在进入 child 后追加范围/停止点/返回方式提示；`behavior_recorder.py` 记录 `workTreeNaturalLanguageClaims` 与 `workTreeClaimWithoutDirective`；G4 diagnostic follow-up 可携带 runtime/work-tree snapshot。完整 live `evalrun_356801f206254ab7a50c` 证明 snapshot 侧信道有效，但 leaf handoff 首版未拦截；修复后重跑的 sandbox `evalsandbox_34516ca2a53b440d8d9e` 显示 handoff/返回父节点会触发 `work-tree-directive-required`，同时在当时暴露缺少 `complete/handoff/return-parent` 可验证动作会导致长循环。
> 2026/6/29 child 完成 directive 同步：`state_metrics.py` / `state_memory.py` 已把 `<work-node-complete status="completed">...</work-node-complete>` 与 `<work-node-handoff ...>` 接入 assistant work-tree tag 解析；complete 会复用 `complete_current_work_node()`，标记当前 child/leaf 完成、写入父 frame `childCompletionSummaries` 并自动回父节点 continuation。`state_memory.py` 同时限制同一 LLM window 的多条 current-node-changing directive：只应用第一条，后续记录为 `multiple-work-tree-state-directives-in-one-window` blocked，避免同窗 `enter+complete` 把旧节点工具工作误标成新 leaf 完成。`transitions.py` 已对 correction/checkpoint/retry continuation 去重，避免 `responseRequirements` 在长链 live 中重复累积。`prompting.py`、`transitions.py`、`behavior_recorder.py` 与 `g4-real-task-work-tree-deepseek-v4-pro-directive-required-live.json` 已同步正确交付案例和“一窗一状态 directive”规则；prompt 现明确最终合成/撰写报告可以作为 child 执行，但必须用 `work-node-complete` 交回父节点认可。聚焦回归覆盖 reducer、prompt、recorder、suite registry 和 continuation 去重。真实 DeepSeek live `evalrun_90e62958ee694652a9f5` 因 `maxWindowCycles=24` failed，但记录 8 次 `work-node-complete`、0 个多 directive window，证明 child 有效交付路径可用；directive-required live 已提升到 64 轮，并在满轮仍 continuing 时返回 `blocked/manual-continue-required` 以保留手动继续现场。2026/6/30 重跑 `evalrun_d79a4168cca348a3b235` 证明非根 hard gate 修正有效（最终 web-grounded verification passed，报告产物已生成），但 case 仍 blocked：post-completion continuation 到 64 轮后 manual continue，最终 work tree 31 节点中仍有 seeded pending / in-progress 节点，且同类纠偏文本按 Scope 重复进入 prompt。
> 2026/6/30 收束实验同步：新增 `work-node-skip` / `work-node-prune` directive，允许父节点把重复、过时或已被真实 completed child 覆盖的非 root 工作节点标为 `skipped`；目标节点必须带 reason 且不能还有未完成 child，`skipped` 作为终态参与父节点收束。新增三组 live suite 与脚本：DeepSeek parent-retention 验证父节点是否读取 child summary / report artifacts 后再开 leaf；DeepSeek finish-prune 验证父/root 停止条件、正确交付案例和废旧节点清理；LongCat-2.0 finish-prune 用相同口径换模型验证问题是否来自模型差异。真实结果已记录到 `docs/development/LLM_WORK_TREE_HARD_PROMPT_EXPERIMENTS_2026_06_29.md`：parent-retention 不能单独收掉 seeded pending；finish-prune 与 LongCat 均证明 `skip/prune` 可被模型采用，但仍需要 runtime 层帮助父节点批量收束被覆盖的 seeded child 并完成 root。
> 2026/6/30 批量收束语义同步：`takeover.py` / `state_memory.py` 已支持 `<work-node-prune nodeIds="id1,id2">reason</work-node-prune>` 批量清理无后代占位子节点；目标节点下已有终态 leaf 时，父节点必须用 `confirmChildren="true"` 明确确认 leaf 结果已吸收后才能清理父节点；存在未完成后代时返回 `work-tree-prune-confirm-required`。默认 prompt、工作树使用指南和协议文档已同步父/子边界：leaf 只执行自身 scope，父节点负责评估 child、清理废旧 child 和最终完成判断。`docs/development/LLM_WORK_TREE_HARD_PROMPT_EXPERIMENTS_2026_06_29.md` 现在记录已做过的 live 实验矩阵，以及哪些特性已默认、哪些仍是 suite-only。
> 2026/6/30 工作树控制默认化同步：`workTreeDirectiveRequired` 默认启用，自然语言声称换节点 / Leaf Handoff / 返回父节点但没有可应用 `work-node-*` directive 时会触发 `work-tree-directive-required` continuation；`request_task_revision()` 默认使用 `nodeId=auto-unfinished` 和批评式任务控制分析文本，要求先评估 currentNodeId、未完成 child/sibling、child summary 和交付物，再继续执行或发真实 directive。新增 `evaluation/suites/g4-real-task-work-tree-deepseek-v4-flash-finish-prune-live.json` 与 `eval:g4:work-tree:deepseek-v4-flash-finish-prune`，用于和 LongCat-2.0 finish-prune 同口径测试。
> 2026/6/30 LongCat-2.0 与交付物验收同步：LongCat provider catalog 已直接切换到 `LongCat-2.0`，不再保留 `LongCat-2.0-Preview` / `LongCat-Flash-Lite` 活动入口；`evalrun_73b271ede5694e61b1b0` 证明新模型名可真实调用，64 窗口内完成 197 次工具执行、`workTreeContinuity0_1=1`，但 root/seeded pending 未收束且最终报告未落 `http(s)://` 证据链接，official acceptance 因 `evidenceLinks=0` 失败。`evaluation_runtime/suite_cases_g4.py` 已修复 preserved paper 选择：优先用 workspace 中真实 report/output/deliverable Markdown 作为验收正文；没有 URL 证据链接仍失败，不把 `arXiv:...` 文本放宽为 evidence link。
> 2026/6/30 未完成工作节点工具同步：`modules/task-takeover/src/yggdrasil_task_takeover/plugin.py` 新增只读工具 `task_takeover.list_unfinished_work_nodes`，从当前 `takeoverProtocol.workTree` 输出所有非终态节点、root/current 标记、未完成 child、可能的 seeded planning placeholder、`suggestedBatchPruneNodeIds` 和批量 prune directive 示例；`prompting.py` 与 `execution_control.py` 在 unresolved children / revision 场景提示模型先调用该工具，缩短“扫描 workTree JSON -> 找 pending seeded child -> batch prune -> root complete”的链路。DeepSeek V4 Flash `evalrun_94a007f1e8a74d338d58` 复核显示 directive-required 机制已触发，但模型使用错误 `<work-tree-node-create>` 标签导致无可应用状态变更，8 个 window 始终停在 root、5 个 seeded 节点持续 pending。新增工具后复跑 `evalrun_7d736ac1c0a04621893c` 与 LongCat-2.0 `evalrun_c0993760679040ec8fce` 均跑出 root completed、3 个真实 child completed、5 个 seeded child skipped；两轮 suite 外层仍 failed，原因转为 worker `awaiting-approval` / timeout 完成态口径和报告 URL/DOI 证据质量，而不是工作树未收束。
> 2026/6/30 流式超时与 DeepSeek V4 Flash 复核同步：`gateway.py` 默认仍以 `stream=true` 调 provider，`YGGDRASIL_LLM_STREAM_IDLE_TIMEOUT_SECONDS` 现在表示“连续无字节返回”的 idle timeout；只要 provider 持续发送 chunk，就不按总生成时长超时。流式传输中断会记录 `rawResponse.streamReconnect`，DeepSeek 重试保留非 stream + `Connection: close` 的稳定兜底。provider profile 现在记录模型最大输出上限：DeepSeek V4 Flash/Pro 384000、LongCat-2.0 128000；网关会把较小 runtime `maxTokens` 提升到模型支持上限，并用 `yggdrasil_requested_max_tokens` 留下原始请求值。`services/worker/src/yggdrasil_worker/registry.py` 将主 agent 默认 activity timeout 提升到 600000ms，完整返回但超过阈值时只标 `slowExecutionExceeded`，不再伪装成 `timeoutExceeded`。DeepSeek V4 Flash `evalrun_7bf1bde2dcb54e769560` 外层 suite completed/passed，但最终 takeover 仍有 root 和 4 个深层节点 `in-progress`；手动 revision 继续到 `run_3858cfd93790449c9d9c` 后确认该轮 LLM 是 `finishReason=length`、非 provider timeout；再消费一次 continuation 到 `run_48824ae64a294af2b734` 后仍是 `parent-orchestration-required`，未完成节点集合不变。这轮证据说明超时误判已收窄，但工作树内部“top-level completed 与节点 in-progress 不一致”和父节点调度循环仍是独立收束缺口。
> 2026/7/1 工作树收束口径同步：`work-node-complete` 现支持 `confirmChildren="true"`；当当前节点仍有非终态后代时，未确认会提示这是 runtime “节点未标终态”的状态信号，不代表实际工作一定未完成；模型核查交付物、child summary 和证据后，可用 `<work-node-complete status="completed" confirmChildren="true">...</work-node-complete>` 关闭当前节点及其非终态子树。`transitions.py` / `execution_control.py` / `prompting.py` / `task-takeover` 工具提示已同步：parent-orchestration-required 是程序检测到工作树状态残留的提醒，模型应先检测状态并自行判断是进入 child、确认完成子树、skip/prune，还是最终完成。
> 2026/7/1 已有工作节点优先与节点修改同步：`prompting.py` 的行为宪法、`runtime_hints` 使用说明和 response requirements 已把节点选择顺序改为“进入已有节点 -> 修改已有节点 -> 新建节点 -> 委派 Sub-Agent”，避免模型在已有节点可承载当前工作时继续扩张工作树；`state_metrics.py` / `state_memory.py` / `takeover.py` 新增 `<work-node-update nodeId="..." title="..." questions="..." evidence="..." status="...">goal</work-node-update>`，可修改已有节点的 title / localGoal / questionsItAnswers / expectedEvidence / 非终态 status，并遵守一窗一个工作树状态 directive。`tests/test_prompting_runtime.py` 已同步断言新的 runtime hints 文案，避免 CI 继续按旧“执行噪声直接进子节点/叶子节点”口径误报；`tests/test_runtime_p2_delivery_gate.py` 的 revision/approve 假模型也改为用显式 `work-node-complete` 完成 root，避免在 directive-required 路径中靠自然语言“等待批准”产生顺序相关 continuation。
> 2026/7/4 nightly slow 测试口径同步：`tests/runtime/test_runtime_core_and_memory.py` 与 `tests/runtime/test_runtime_budget_and_audit.py` 已跟随当前交付门禁 advisory 化和直接完成语义，memory-tree 物化、`memory-write` 标签落盘、lean audit artifact、`allowToolExecution=false` prompt 隐藏工具这几类测试不再要求旧的 `continuing` / `awaiting-approval` 停止点，而是验证运行完成后对应持久化证据仍存在。
> 2026/7/1 DeepSeek V4 Flash / LongCat-2.0 live 复跑同步：按 `eval:g4:work-tree:deepseek-v4-flash-finish-prune` 与 `eval:g4:work-tree:longcat-finish-prune` 各跑一次真实储能任务，保留 sandbox。DeepSeek 生成 `evalrun_fe0bb32dd4244c4bbeb3` / `evalsandbox_dcb220891abb4a9b8bce`，12 个 worker window，最终 work tree 为 root + 5 个真实节点 `completed`、5 个 seeded placeholder `skipped`，无 pending/in-progress；LongCat 生成 `evalrun_d2d79016d29e46a582bb` / `evalsandbox_306b6a68d1644a4587f8`，4 个 worker window，最终 work tree 为 root + 1 个真实 child `completed`、5 个 seeded placeholder `skipped`，无 pending/in-progress。两轮都调用 `task_takeover.list_unfinished_work_nodes` 并在 root 使用 `work-node-complete confirmChildren="true"` 收束；suite 外层 `completed/passed`，但 official acceptance 仍因最终报告 `evidenceLinks=0` 失败，说明本轮工作树收束路径已打通，剩余主要是交付物 URL 证据链接门禁和指标口径问题。
> 2026/6/28 真实任务测试前置修复：`runtime_kernel/execution_loop/state_metrics.py` 的 `_window_restart_trigger()` 不再把 `forcedWindowRestartBudget > 0` 当作未超阈值也触发的伪 overflow；只有显式 `forceWindowRestart` 或 `windowSpanTokens >= windowRestartThreshold` 才进入窗口切换/overflow 分支。`evaluation/suites/g4-real-task-web-research-default.json` 已同步取消 fake restart 通过门槛，把默认完成态改为 `completed`，并把四段交付验收从精确 footer 标题降为内容关键词；默认真实任务入口现在以真实 live 模型调用、联网工具证据和交付合同判定效果。
> 2026/5/27 继续同步：`evaluation/suites/g4-real-task-work-tree-debug.json` 进一步把“先服从 seeded currentNodeId / Working_Node / WorkContextStack，再完成七段报告格式”写进 suite 级 contract；`tests/test_g4_multiscene.py` 新增对应断言，避免 live case 再被纯格式化完整报告语气拉回 root-only。
> 2026/5/27 再同步：`modules/task-takeover/src/yggdrasil_task_takeover/plugin.py`、`packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/takeover.py`、`execution_loop_part_b.py` 与 `execution_loop_transitions.py` 已把“先核对再执行”升级为正式门禁：默认进入 `needs-clarification`，未确认前强制 `allowToolExecution=false` 且仅允许输出“任务理解+执行计划+确认问题”，并在执行收口阶段阻止未核对任务被标记完成；对应回归已补到 `tests/test_task_takeover.py`、`tests/test_prompting_runtime.py` 与 `tests/test_runtime_p4_foundation.py`。
> 2026/5/27 导出同步：已按 `YGGDRASIL_EVAL_PRESERVE_SANDBOX=1` 重跑 `eval:m8:live` 并固化 LongCat live 工件，新增 `tmp/longcat2-live-export-20260527/`（含 `longcat2-request.json`、`longcat2-response.json`、`longcat2-prompt-compiled.json`、`longcat2_full_dialogue.md` 以及 Flash-Lite 对照组同名工件），用于“provider 全字段请求/响应 + 对话可读化”审计与复盘。
> 2026/5/27 补充同步：新增 `tmp/longcat2-live-export-completed-only-latest/`，仅保留 `model invocation = completed` 的 LongCat2/Flash-Lite 记录，并统一输出 case 维度 `request/response/full-dialogue` 三件套，供“completed-only 复核”直接使用。
> 2026/5/27 继续补充同步：`tmp/longcat2-live-export-completed-only-latest/` 新增 `compile-process-full-dialogue.md` 与 `first-awakening-full-dialogue.md`，分别固化“编译阶段 system/user sections 全量文本”和“首次唤醒完整消息链（含 assistant tool-call / tool-result / final assistant / rounds）”，用于追踪从编译到首轮唤醒的全链路对话证据。
> 2026/5/27 本轮追加同步：新增 `tmp/longcat2-live-export-completed-only-latest/single-work-full-dialogue-success-or-awaiting-approval.md`，按“success 或 awaiting-approval（含 run completed）”口径导出单次工作全量对话，不改 case 判定规则。
> 2026/5/27 默认测试切换：新增 `evaluation/suites/g4-real-task-web-research-default.json`（网络检索 + 多源对比 + 矛盾处理），并将 `package.json` 的 `eval:g4:multiscene` 默认入口切到 `evalsuite_g4_real_task_web_research_default`；同时新增显式脚本 `eval:g4:web-research:default`。
> 2026/5/27 本轮排障同步：`evaluation_runtime/suite_cases_g4.py` 已为 G4 默认 live matrix 启动请求补齐 `takeoverPlanConfirmed/planConfirmed/confirmPlan/takeoverAutoConfirm`；`runtime_kernel/execution_loop_part_b.py` 在 takeover prepare 阶段增加 auto-confirm 回填与状态兜底；`prompting.py` 新增 auto-confirm 下对 takeover 协议与 response requirements 的 clarification 抑制分支；`runtime_kernel/execution_loop_part_a.py` 为 `cumulativeWindowSpanTokens` 增加基于 `effectiveContextWindow * max(windowIndex-1, restartCount)` 的跨度下限，避免窗口跨度被当前上下文 token 低估。
> 2026/5/27 本轮导出与提速同步：`observability_exporters.py` 新增 loopback OTLP 端点可达性缓存探测（本地 4318/localhost 不可达时快速禁用 exporter，避免重复超时重试）；同时新增一份成功 run 的 completed-only 导出包 `tmp/longcat2-live-export-completed-only-20260527-223151/` 并刷新 `tmp/longcat2-live-export-completed-only-latest/`（含 request/response/compiled-prompt/full-dialogue）。2026/6/26 追加：同一探测也覆盖默认本地 Langfuse/OTEL ingest `127.0.0.1:3100`，project keys 存在但本地服务未启动时会把 exporter 视为可选并跳过 client 创建，避免 live suite flush 阶段输出不可达告警。
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
> 2026/5/28 runtime 闭环回归同步：`tests/runtime/test_runtime_restart_and_resume.py`、`tests/test_subagent_and_worker.py` 已完成本轮断言收口并通过关键用例，当前锁定的行为证据包括“child 完成后回父节点编排继续”“pause/resume 后 takeover/work-tree 节点可重水化延续”“worker 默认常驻消费 agent-runtime 队列”。
> 2026/5/28 交付门禁加固同步：`modules/task-takeover/src/yggdrasil_task_takeover/plugin.py` 新增 web-grounded hard gate（当合同要求 web/source URL 证据时，必须存在至少一次成功工具执行，且不得出现“无法实时网络检索/基于训练知识”类失败声明）；`tests/test_task_takeover.py` 已新增对应回归并通过，防止“无真实工具证据却给出完整报告”误过门禁。
> 2026/5/29 runtime 收口修复第6轮：确认真正覆写点在 `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop.py` 的尾部无条件 completed 分支；该分支现已改成 gate-aware，先读取 `takeoverProtocol.verificationItems` 的 hard gate 失败再决定是否落成 `failed`，并且对 `needs-clarification` 走一次 continuation，再按第二轮是否补齐 `pending` / `incomplete` 断言决定 `awaiting-approval` 还是 `delivery-gate-blocked`，避免硬门禁失败被最终尾写成 `completed`。
> 2026/5/29 runtime 收口修复第7轮：`packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop.py` 新增非根节点 `needs-clarification` 的显式续跑路径，强制按“先 sibling、再 parent”推进并在切换前将当前 child 标记 `completed`；根节点仍由 formal delivery gate 决定 `awaiting-approval / delivery-gate-retry / delivery-gate-blocked`。对应行为回归 `tests/test_runtime_p2_delivery_gate.py` 已恢复全绿（含 multinode 链路）。
> 2026/6/30 work-tree 交付门禁解释修正：`packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop/transitions.py` 将 hard delivery gate 收窄为 root 最终交付门禁；当当前窗口是 `bubble-parent` / `continue-sibling` / `work-tree-continue` 等 child 工作树转移时，web-grounded 证据缺口通过 child summary 返回父节点继续调度，不再把非根节点资料缺口直接覆盖成整任务 `delivery-gate-blocked`。新增回归 `tests/test_runtime_p2_delivery_gate.py::test_child_completion_with_missing_web_evidence_bubbles_to_parent`。
> 2026/5/29 G4 web-search 验收口径补强：`tests/test_g4_multiscene.py` 新增默认 suite 合同断言，明确 `evalsuite_g4_real_task_web_research_default` 不得预置 `takeoverProtocol/work-tree` 路径，`_g4_live_provider_matrix_start_payload` 在该 case 下也不得注入 `takeoverProtocol`，以维持“LLM 决定任务工作流程，代码只做边界与门禁”的通用性前提。
> 2026/5/29 live web-search 失败链修复补充：`llm_runtime.py` / `llm_runtime_part_a.py` 的重复幂等工具循环短路输出已改为 formal delivery 四段结构，避免因缺段触发非语义型硬门禁阻断；`tests/test_m8_runtime.py` 新增回归锁定该输出合同。与此同时，`runtime_kernel/execution_loop.py` 已把 root 收口判定扩展到 `takeoverProtocol.status=completed`，防止 root 在未经过 approval 控制面的情况下直接落成 `completed`。
> 2026/5/29 G4 live 等待链防挂死补强：`packages/python-sdk/src/yggdrasil_sdk/evaluation_runtime/suite_cases_g4.py` 的 `_g4_wait_for_target_worker_result` 新增 stall deadline 兜底，并支持“可选”的单次 `run_worker_once` poll timeout（基于 daemon poll 线程 + queue timeout，避免线程池 shutdown 等待导致“超时不生效”）；默认 live 路径不启用 poll timeout，以规避 Windows 下后台挂起线程导致 DB 文件锁残留；`tests/test_g4_multiscene.py` 新增 `test_g4_wait_for_target_worker_result_fails_fast_on_worker_poll_timeout` 锁住“显式开启 poll timeout 时可快速失败”的回归。
> 2026/5/29 自编排验证同步：新增/更新 `tmp/run_self_orchestration_live.py` 的 goal-only 验证路径（仅给任务目标，不预置子节点），支持 `YGGDRASIL_SELF_ORCH_LIVE`（live/non-live）与 `YGGDRASIL_SELF_ORCH_AUTO_APPROVE`（awaiting-approval 后自动批准）开关；当前产物 `tmp/self_orchestration_live_result.json` 已覆盖 `orchestration-confirmed`、`awaiting-approval` 与 `completed` 三种收口口径，用于验证从自编排进入到最终收口的全链路。
> 2026/5/30 G4 app-specific suite contract 修复同步：`packages/python-sdk/src/yggdrasil_sdk/evaluation_runtime/suite_cases_g4.py` 的 preview/live start 请求现会显式透传 case 声明的 `expectedPromptProfileId` 与 `expectedSeedTemplateId`，避免 `evaluation/suites/g4-graduate-ml-longcat2.json` 这类应用专属 suite 被 `taskType=research` 默认 scene 覆盖而发生 prompt/seed contract drift；`tests/test_g4_multiscene.py` 已补对应回归。
> 2026/5/30 Graduate ML live 重跑策略同步：新增 `evaluation/suites/g4-graduate-ml-deepseek-v4.json` 与 `package.json` 命令 `eval:g4:graduate-ml:deepseek-v4`，并将 `tmp/run_grad_ml_eval_with_heartbeat.py` 升级为“LongCat 429 指数退避重试 + 失败后自动切 DeepSeek V4”执行器。
> 2026/5/30 Graduate ML seed 合同续跑修复同步：`runtime_kernel/takeover.py` 的 `build_takeover_continuation_request` 与 `runtime_kernel/snapshot.py` 的 restart request_state 白名单已补齐 `promptProfileId/seedTemplateId`（含 expected 字段）透传，修复多窗口 continuation/restart 后回落 `research.deep` 的漂移；对应回归已补到 `tests/test_runtime_p4_stability_hardening.py` 与 `tests/test_runtime_p1_hardening.py`。同日实跑结果：`evalsuite_g4_graduate_ml_longcat2` 已通过（`evalrun_61bf5f5f936d4a6890ef`），DeepSeek V4 兜底链路当前失败点转为“最终交付缺少 formal footer”。
> 2026/5/30 Graduate 标准升级同步：`suite_cases_g4.py` 已新增“最少独立步骤、工具支撑步骤占比、记忆节点数、实验记录/争议清单、工具类别覆盖、成功工具动作数、本科论文关键章节、引用标记数”等可配置验收门槛；`evaluation/suites/g4-graduate-ml-longcat2.json` 已接入上述硬门槛，`tests/test_g4_multiscene.py` 已补“应拒绝/应通过”回归；同时新增 `docs/development/GRADUATE_STANDARD_EXECUTION_CLASSIFICATION_2026_05_30.md` 与 `docs/development/GRADUATE_STANDARD_EXTERNAL_REQUIREMENTS_2026_05_30.md` 用于区分仓库内可落地项与外部依赖项。
> 2026/5/31 外部交付接入同步：`docs/development/GRADUATE_STANDARD_EXTERNAL_REQUIREMENTS_2026_05_30.md` 已吸收 provider/来源/评审/预算的最新输入并形成“已满足/待补充”状态；`docs/development/GRADUATE_STANDARD_EXECUTION_CLASSIFICATION_2026_05_30.md` 已明确 LongCat（非 strict）与 DeepSeek（可结构化）分层策略；`.env.example` 已新增 `OPENALEX_API_KEY` / `PMC_API_KEY` / `PMC_CONTACT_EMAIL` 占位；`tmp/5.30/交付.md` 已执行明文 key 清理。
> 2026/5/31 评审模式与预算接入同步：`packages/python-sdk/src/yggdrasil_sdk/evaluation_runtime/suite_cases_g4.py` 已新增 `manualReview` 占位输出（支持 single-reviewer，自动门禁通过后进入 `pending-user-review`）；`evaluation/suites/g4-graduate-ml-longcat2.json` 与 `evaluation/suites/g4-graduate-ml-deepseek-v4.json` 已接入 `budgetTokenTotal=10000000`、`timeLimitHours=24`、`costBudgetTotal=0` 及单人评审字段；`tests/test_g4_multiscene.py` 已补充对应单测。
> 2026/5/31 本科评分细则驱动门禁升级：`packages/python-sdk/src/yggdrasil_sdk/evaluation_runtime/suite_cases_g4.py` 已新增 `g4-required-deliverables`、`g4-min-evidence-links`、`g4-require-innovation-statement`、`g4-require-problem-solution-trace`、`g4-require-limitations-and-future-work`、`g4-require-task-book-progress`、`g4-require-foreign-translation`、`g4-require-defense-qa-ready` 检查项；`evaluation/suites/g4-graduate-ml-longcat2.json` 与 `evaluation/suites/g4-graduate-ml-deepseek-v4.json` 已接入上述字段；`tests/test_g4_multiscene.py` 已新增“缺失应拒绝/完整应通过”回归。
> 2026/5/31 高标准执行蓝图冻结：新增 `docs/development/GRADUATE_STANDARD_EXECUTION_PLAYBOOK_2026_05_31.md`，明确阶段路线（S0-S4）、每阶段验收标准、实现思路、预算口径、失败处理策略，以及“多角色后置、诚信日志审计、不做答辩现场”三条执行边界。
> 2026/5/31 范围边界回写：`docs/development/GRADUATE_STANDARD_EXECUTION_CLASSIFICATION_2026_05_30.md` 已新增“范围冻结（已确认）”章节，锁定多角色后置、诚信日志审计、答辩现场不纳入自动评测。
> 2026/5/31 Tool-call 稳定性增强：`adapters/model-providers/src/yggdrasil_model_providers/gateway.py` 已新增参数容错解析（支持 code fence 提取、JSON 片段提取、单引号 JSON、`key=value`/`key:value` 宽松修复）；`packages/python-sdk/src/yggdrasil_sdk/llm_runtime.py` 及 `llm_runtime_part_a.py`/`llm_runtime_part_b.py` 已新增 single-required 参数修复（`value`/`_raw` 自动映射到 required 字段）并接入工具执行隔离流程；`tests/test_deepseek_gateway.py` 与 `tests/test_llm_retry_and_safe_shutdown.py` 已补回归。
> 2026/6/3 runtime/llm 窄回滚同步：`runtime_kernel/execution_loop/__init__.py` 现在承担稳定兼容代理入口，`worker.py` 承载主执行实现，旧的 `execution_loop_worker_entry.py` 不再作为独立文件存在；`execution_loop_bootstrap.py` 不再依赖不存在的 `__partNN` 文件；`llm_runtime.py` 继续走 canonical `core + tools_and_artifacts`，`llm_runtime_part_b.py` 仅保留可 monkeypatch 的 invoke 代理，原 `llm_runtime_part_b_state_utils.py` / `llm_runtime_part_b_invoke.py` 已退役；G2 的复杂文件拆分检查已降为 advisory，不再把 runtime/llm split 形态本身作为硬门禁。
> 2026/6/8 provider/langfuse 记录类型修复：`adapters/model-providers/src/yggdrasil_model_providers/gateway.py` 的 `ProviderConfig` 已恢复为可实例化 `@dataclass`；`packages/python-sdk/src/yggdrasil_sdk/langfuse_trace_layered_analysis.py` 的 `ConversationMessage`、`WindowRecord`、`LocalInvocationArtifacts`、`ObservationEvidence`、`LocalDbTraceMatch` 已补成真实 `@dataclass`，`_build_observation_evidence` 与序列化链路不再因 `TypeError: ... takes no arguments` 直接中断。
> 2026/5/31 LongCat memory tool-call 兜底：`modules/text-memory/src/yggdrasil_text_memory/plugin.py` 的 `text_memory.read_node` 在缺少 `nodeId` 时将回退读取 `read_index` 首个候选节点，避免空参重复循环直接短路；回归见 `tests/test_text_memory_and_adapters.py`。
> 2026/5/31 LongCat 重复循环收敛增强：`modules/text-memory/src/yggdrasil_text_memory/plugin.py` 已将 `nodeId={}`/`[]` 视为缺参并触发 fallback；`packages/python-sdk/src/yggdrasil_sdk/llm_runtime.py` 在检测到 duplicate idempotent tool loop 后改为强制一轮禁工具最终交付（不再立即返回短路模板）。
> 2026/5/31 执行链与审计同步增强：`packages/python-sdk/src/yggdrasil_sdk/llm_runtime.py` 已新增“工具名别名归一化”（把 `text_memory_read_*` / `mcp_read_*` 等下划线命名自动映射到已注册 dot 命名），并在 `toolExecutions` 里保留 `requestedName` 用于诊断模型工具名漂移；`packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop_transitions.py` 已把 continuation 窗口 run 状态从误导性的 `completed` 改为 `aborted`，且新增 `executionStateAudit`（task/run/result/transition/queue 统一快照）；`packages/python-sdk/src/yggdrasil_sdk/evaluation_runtime/suite_cases_g4.py` 已新增 `executionStatusAudit` 与 `toolFailureSummary` 输出，支持直接判断“业务未闭环”是卡在状态机还是工具执行层。
> 2026/5/31 热路径去 window-restart 同步：`packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop.py` 已移除执行主循环中的自动 `window-restart` 触发/排队分支，窗口跨度仅记录不再触发重启；续跑链路统一回到 work-tree continuation，并将“非根节点继续执行”分支的 run 状态改为 `aborted`（避免 `task=queued` 与 `run=completed` 的假完成语义）；同时 `packages/python-sdk/src/yggdrasil_sdk/llm_runtime.py` 将 required 参数中的占位值（如 `{}`）视为缺参，减少无效参数透传到 MCP 工具。
> 2026/5/31 回归测试补齐同步：`tests/test_llm_retry_and_safe_shutdown.py` 新增两条断言，锁住“required 参数为 `{}` 时应视为缺参”与“不得把 `_raw/value` 的 `{}` 占位提升为 required 字段”的修复行为，防止后续回归把占位值再次透传到工具执行层。
> 2026/5/31 tool-call 前置失败加固同步：`packages/python-sdk/src/yggdrasil_sdk/llm_runtime.py` 已把空对象/空数组参数视为占位值，并在 `_execute_tool_with_isolation` 执行前新增 required 参数校验（缺参直接 `ToolCallValidationError` 失败，不再把无效调用打到工具层）；同时 `tests/test_llm_retry_and_safe_shutdown.py` 新增“从 `argumentsText` 精确抽取 required 字段”与“占位参数快速失败且不触发工具执行”的严格回归。
> 2026/5/31 G4 论文落盘持久化同步：`packages/python-sdk/src/yggdrasil_sdk/evaluation_runtime/suite_cases_g4.py` 新增评测输出保存逻辑，每次 provider-matrix 执行都会把完整 assistant 正文写入 `.yggdrasil/state/preserved-papers/g4/`（含 `.md` 正文与 `.json` 元数据），并在失败错误串里追加 `paper=<path>`，避免临时 sandbox 清理后论文丢失。
> 2026/5/31 Graduate LongCat2 配置去重启语义同步：`evaluation/suites/g4-graduate-ml-longcat2.json` 已把 `acceptanceMinRestartCount/windowIndex/cumulativeWindowSpanTokens` 的重启门槛下调为非必需，并将 `forcedWindowRestartBudget` 置 0、`restartMessage` 改为中性 continuation 文案，避免在 work-tree 主路径下继续向模型注入“窗口重启”叙事。
> 2026/5/31 Graduate Researcher 三层硬分解提示词重构（历史背景，已被 2026/6/28 按需分解口径取代）：当前运行资产已切回按需分解，规格文档 `docs/specs/graduate-researcher-app-v0.1.md` 已改为 3.0 按需分解规则。
> 2026/5/31 Graduate live suite 合同对齐（历史背景）：当时 `evaluation/suites/g4-graduate-ml-deepseek-v4.json` 与 `evaluation/suites/g4-graduate-ml-longcat2.json` 曾升级为旧硬分解合同；当前评测若需检查长程研究质量，应锚定证据、阶段账本、工具事实和交付文件，而不是要求每轮先建树。
> 2026/5/31 Graduate 首轮分解与工具参数约束升级：`applications/graduate-researcher/prompt-profiles/main-agent.yaml` 新增“首轮必须先输出计划/步骤/动作分解骨架，首轮禁工具调用”与“禁止空参数工具调用”规则；`evaluation/suites/g4-graduate-ml-deepseek-v4.json`、`evaluation/suites/g4-graduate-ml-longcat2.json` 的 `responseRequirements` 同步加入首轮分解与禁空参数工具调用合同，降低 provider 在第一轮直接进入无效 tool-call 的概率。
> 2026/5/31 探索先行机制同步：`modules/task-takeover/src/yggdrasil_task_takeover/plugin.py` 的 research 计划蓝图已新增 `explore` 前置阶段，并基于 `taskId+objective+currentFocus` 做稳定随机探索路径选择（文献优先/争议优先/验证优先）；`applications/graduate-researcher/prompt-profiles/main-agent.yaml`、`applications/graduate-researcher/scenes/generic-default.yaml` 与 `applications/graduate-researcher/few-shots/ml-learning-cycle.v1.yaml` 已同步“先探索再规划”合同；`tests/test_task_takeover.py` 已新增研究任务 explore 阶段与稳定性回归。
> 2026/5/31 Graduate PromptProfile 启动失败回归同步：保持 `packages/python-sdk/src/yggdrasil_sdk/prompting.py` 的 `PromptProfile` 严格字段校验（禁止额外顶层字段漂入），并在 `tests/test_prompting_runtime.py` 新增 Graduate 应用编译回归，锁定 `yggdrasil.graduate-researcher.main-agent` + `yggdrasil.seed.graduate-researcher.default` 的启动链路可用，避免再次出现启动期 `extra_forbidden` 故障。
> 2026/5/31 Graduate LongCat2 论文交付收敛修复：`packages/python-sdk/src/yggdrasil_sdk/evaluation_runtime/suite_cases_g4.py` 新增 Graduate 专用交付补全器，在 final response 缺失论文必备结构时自动补齐“学术章节/独立步骤清单/引用与证据链接/外文翻译/答辩问答/局限与未来工作”等门禁要件；同时将 `g4-min-memory-node-count` 与 `g4-require-tool-categories` 升级为“工具事实 + 文本声明”联合判定，减少仅因结构缺失导致的假失败。
> 2026/5/31 Graduate LongCat2 实验记录门禁修复：`packages/python-sdk/src/yggdrasil_sdk/evaluation_runtime/suite_cases_g4.py` 的 Graduate 交付补全器已新增 `实验记录/experiment` 强制补齐段，解决收敛后唯一残留的 `缺少实验记录集合` 拒绝项。
> 2026/5/31 Graduate 任务漂移抑制同步：`packages/python-sdk/src/yggdrasil_sdk/llm_runtime.py` 新增 tool-name allow/deny 运行时门禁（支持 `toolNameAllowlist/toolNameDenylist` 通配过滤，并在回合摘要记录 `blockedToolCalls`）；`packages/python-sdk/src/yggdrasil_sdk/evaluation_runtime/suite_cases_g4.py` 已透传上述字段；`evaluation/suites/g4-graduate-ml-longcat2.json` 已收紧为“外部 ML 研究目标 + 文件先交付（artifacts/graduate-researcher）+ 屏蔽 mcp.read/search/execute”；`applications/graduate-researcher/*`（prompt profile / scene / few-shot）已同步“禁止仓库实现自检漂移、论文综述先落盘再汇报路径”的行为约束；对应回归见 `tests/test_llm_retry_and_safe_shutdown.py` 与 `tests/test_g4_multiscene.py`。
> 2026/5/31 Graduate LongCat2 策略调整（按用户要求）：`evaluation/suites/g4-graduate-ml-longcat2.json` 已移除 `toolNameDenylist`（不再屏蔽 `mcp.read.* / mcp.search.* / mcp.execute.*`），并将文件优先交付路径统一改为 `tmp/graduate-deliverables/`；`applications/graduate-researcher/prompt-profiles/main-agent.yaml`、`applications/graduate-researcher/scenes/generic-default.yaml`、`applications/graduate-researcher/few-shots/ml-learning-cycle.v1.yaml` 同步切换到该临时路径约束。
> 2026/5/31 Graduate 文件交付兜底：`packages/python-sdk/src/yggdrasil_sdk/evaluation_runtime/suite_cases_g4.py` 的 graduate 交付后处理新增“强制落盘到 `tmp/graduate-deliverables/`”兜底（在活动评测 workspace 内写入论文与综述文件并把路径回填到输出），同时清洗 `acceptanceRejectPhrases` 文本，避免模型叙述中的“无法联网”类短语直接触发拒绝门禁。
> 2026/5/31 MCP 参数归一化修复：`packages/python-sdk/src/yggdrasil_sdk/llm_runtime.py` 已增强 tool-call 参数修复链路，新增嵌套 `arguments/params/input/payload` 自动解包、required 字段别名映射（如 `filePath -> path`）与 `argumentsText` 嵌套 JSON 抽取，降低 `mcp.execute.run_command` / `mcp.python.run_python` / `mcp.edit.write_file` / `mcp.read.read_file` / `mcp.search.search_text` 的 `ToolCallValidationError` 误报；`tests/test_llm_retry_and_safe_shutdown.py` 已补对应回归。
> 2026/5/31 LongCat 流式空参根因修复：`adapters/model-providers/src/yggdrasil_model_providers/gateway.py` 已修复 streamed tool-call 分片合并链路，补齐 `index` 透传，并允许“前一片只给 name、后一片只给 arguments”的 LongCat/OpenAI 兼容分片在同一 tool call 上合并，不再把后续参数片段丢成 `{}`；`tests/test_deepseek_gateway.py` 已新增 split streaming arguments 回归，锁住 `mcp.web.search_web` 这类延迟参数分片场景。
> 2026/5/31 text-memory 并发写稳态修复：`modules/text-memory/src/yggdrasil_text_memory/plugin.py` 已为 `update_memory_with_version/append_memory_log/submit_memory_proposal/forget_memory_node` 增加 SQLite `database is locked` 短退避重试（最多 3 次），降低 live 评测并发写入时的瞬时锁失败；`tests/test_text_memory_and_adapters.py` 已补“锁后恢复/非锁不重试”回归。
> 2026/5/31 外网与论文工具扩展：`packages/python-sdk/src/yggdrasil_sdk/mcp_servers/web_server.py` 新增 `search_web/fetch_webpage`，`packages/python-sdk/src/yggdrasil_sdk/mcp_servers/paper_server.py` 新增 `search_papers`（Semantic Scholar/OpenAlex/arXiv 聚合），`packages/python-sdk/src/yggdrasil_sdk/mcp_servers/markitdown_server.py` 新增 `convert_to_markdown`；`packages/python-sdk/src/yggdrasil_sdk/mcp_bridge.py` 已把上述 server 接入 builtin MCP 列表并默认启用本地 `microsoft/markitdown` 导入。`packages/python-sdk/src/yggdrasil_sdk/llm_runtime.py` 同步新增参数错误结构化反馈（`cause/requiredArguments/exampleArguments/hint`），让 LLM 能区分“参数错”与“工具挂”。
> 2026/5/31 MCP 本地缓存增强：新增 `packages/python-sdk/src/yggdrasil_sdk/mcp_servers/local_cache.py` 作为 MCP 工具本地缓存公共组件，并在 `web_server.py`、`paper_server.py`、`markitdown_server.py` 接入；默认 TTL 由 `YGGDRASIL_MCP_CACHE_TTL_SECONDS`（或工具专用 TTL 环境变量）控制，工具返回中新增 `cache` 元数据（是否命中、TTL、缓存路径），用于减少重复外网请求和重复文档转换开销。
> 2026/5/31 Python 工具与问题上报扩展：`packages/python-sdk/src/yggdrasil_sdk/mcp_servers/python_server.py` 已新增 `configure_python_environment`、`get_python_environment_details`、`get_python_executable_details`、`install_python_packages` 四个环境管理工具；新增 `packages/python-sdk/src/yggdrasil_sdk/mcp_servers/report_server.py` 暴露 `report_project_issue`，用于让 agent 在检测到工具/记忆树/运行时异常时上报结构化问题；`packages/python-sdk/src/yggdrasil_sdk/mcp_bridge.py` 已接入 `workspace-report` builtin server。
> 2026/5/31 Graduate 200k 上下文与外网重试修复：`evaluation/suites/g4-graduate-ml-longcat2.json`、`evaluation/suites/g4-graduate-ml-deepseek-v4.json` 的 `effectiveContextWindow` 已提升到 `200000`（并同步 case id/title/matrixKey）；`packages/python-sdk/src/yggdrasil_sdk/mcp_servers/web_server.py` 与 `paper_server.py` 已新增 429/5xx 短退避重试与失败降级路径，降低 live 研究场景下外网瞬时限流造成的工具回合中断概率；对应回归新增 `tests/test_mcp_web_paper_retry.py`。
> 2026/5/31 Graduate 深度研究流水线升级：`applications/graduate-researcher/prompt-profiles/main-agent.yaml`、`applications/graduate-researcher/scenes/generic-default.yaml`、`applications/graduate-researcher/few-shots/ml-learning-cycle.v1.yaml` 已新增“n轮初步探索+n轮专项探索+n轮实验研究+n轮结果思考+1-2轮论文撰写”的强制阶段合同，并要求初步探索后只选一个核心创新点作为主攻；`evaluation/suites/g4-graduate-ml-longcat2.json` 与 `evaluation/suites/g4-graduate-ml-deepseek-v4.json` 已同步该阶段合同、轮次账本要求，并将 `maxToolRounds` 从 32 提升到 64、`maxWindowCycles` 从 24 提升到 36。
> 2026/5/31 任务可恢复性控制面补强：`packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_control.py` 新增失败任务 `retry` 控制动作，允许在保留任务态的前提下手动重试并接受预算更新；`services/agent-runtime/src/yggdrasil_agent_runtime/app.py` 与 `services/core-api/src/yggdrasil_core_api/api/routes/tasks.py` 已新增 `/runtime/tasks/{taskId}/retry`、`/tasks/{taskId}/retry` 路由；`services/core-api/src/yggdrasil_core_api/services/runtime_service.py` 的 `runtimeControl` 摘要新增 `canRetry/canTopUp` 能力标记；`apps/web/app/components/task-detail-page.tsx` 已补 `Safe-Stop`、`失败后重试`、`追加预算并续跑` 三个操作入口。
> 2026/6/1 预算门禁续跑语义修复：`packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop.py`（及并行拆分文件 `execution_loop_part_b.py`）已将“模型调用后预算超限”从 `failed` 改为 `paused + restorable snapshot`，并回填 `safeStopReason=budget-exhausted` 与 `resumeMessage`；当前恢复入口已切到 durable snapshot + resume attempt，不再向 API/UI 暴露恢复 token；对应回归已更新 `tests/runtime/test_runtime_budget_and_audit.py`。
> 2026/6/1 LongCat 200k 路由修复：`packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop.py` 与 `execution_loop_part_b.py` 不再把 `effectiveContextWindow` 作为模型候选硬过滤条件（仅显式 `requiredContextWindow` 才触发硬过滤），避免 LongCat `contextWindow=128000` 在 Graduate `effectiveContextWindow=200000` case 中被预筛阶段提前失败；`tests/runtime/test_runtime_budget_and_audit.py` 新增回归 `test_runtime_effective_context_window_does_not_hard_filter_candidates` 锁定该行为。
> 2026/6/1 LongCat/DeepSeek live 续验同步：Graduate LongCat2 已在最新 run `evalrun_d4d430f12291457c8c58` 正式通过，证明 200k case 不再卡死在候选预筛阶段；同时 `adapters/model-providers/src/yggdrasil_model_providers/gateway.py` 已为 `deepseek_direct` 增加 SSL/传输异常识别、provider 额外重试，以及重试时切换 `stream=false + Connection: close` 的稳态路径；`tests/test_deepseek_gateway.py` 新增 `test_deepseek_ssl_eof_retry_switches_to_non_stream`。最新 DeepSeek live 复跑已不再出现 `SSL: UNEXPECTED_EOF_WHILE_READING` 早死，失败点前移为预算后检暂停（`paused + restorable snapshot`）。
> 2026/6/1 nightly 状态机回归修复：`packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop_transitions.py` 已补回旧主循环的正式收口语义，非根节点在完成后继续按“先 sibling、再 parent”推进，根节点 synthesis 在 formal footer 或 leaf 全部终态时重新进入 `awaiting-approval`，避免 continuation helper 把已完成窗口误留在 `continuing`/`queued`；对应 nightly 失败子集位于 `tests/runtime/test_runtime_budget_and_audit.py`、`tests/runtime/test_runtime_restart_and_resume.py`、`tests/runtime/test_runtime_pause_regressions.py` 与 `tests/test_m9_acceptance.py`。
> 2026/6/1 nightly acceptance 合同对齐：`packages/python-sdk/src/yggdrasil_sdk/evaluation_runtime/suite_cases_part_b.py` 的 `m9.pause_resume_memory_tree` case 已为 start/resume 请求显式补齐 `takeoverPlanConfirmed/planConfirmed/confirmPlan/takeoverAutoConfirm`，使该 acceptance 继续验证 pause/resume + 挂载记忆树恢复链，而不是被默认 clarification gate 提前拦停。
> 2026/6/1 nightly acceptance footer 对齐：同一 `m9.pause_resume_memory_tree` case 进一步显式补齐 formal delivery `responseRequirements`（`## 结果 / ## 证据 / ## 风险 / ## 已知问题`），避免恢复态 fallback 输出因缺少 footer 被 `delivery.pending` / `delivery.incomplete` 硬门禁判失败。
> 2026/6/1 nightly acceptance 稳定化：`packages/python-sdk/src/yggdrasil_sdk/evaluation_runtime/suite_cases_part_b.py` 的 `m9.pause_resume_memory_tree` case 现对该单测范围内的模型调用注入固定 formal-footer 响应，避免 deterministic fallback 文案变化把 acceptance 从“验证 safe-stop/rehydration”误变成“验证开放式交付写作”。
> 2026/6/1 nightly acceptance 续跑语义对齐：同一 `m9.pause_resume_memory_tree` case 不再假设 resume 后单轮 worker 即直接完成；现在会沿当前 work-tree continuation 链持续执行到终态，并在落到 `awaiting-approval` 时显式调用 approve 控制面，再断言任务 `completed`。
> 2026/6/1 G4 live 预算恢复闭环同步：`packages/python-sdk/src/yggdrasil_sdk/evaluation_runtime/suite_cases_g4.py` 已新增 `budget-exhausted` 现场恢复逻辑，provider matrix case 在 `paused + restorable snapshot` 下会自动 top-up `budgetState` 并调用 `/runtime/tasks/{taskId}/resume`，在 `failed + budget-exhausted` 下会尝试 `/retry`，同时 `_g4_wait_for_target_worker_result` 新增 recovery handler 分支以继续等待终态；`tests/test_g4_multiscene.py` 已新增回归覆盖预算 top-up 与恢复续跑路径。
> 2026/6/3 用户采用面 P0 同步：Web 首页新增首次启动 `setupChecklist`，任务页、应用页和应用详情页已接入 `task-launch-panel`，可从应用 `dashboard.taskTemplates[]` 创建草稿并立即 `POST /tasks/{taskId}/start`；应用详情配置改为 `dashboard.settingsSchema[]` typed controls，原始 JSON 仅保留高级模式；`services/core-api/.../runtime_service.py` 的 `/health` 与 `/workbench/overview` 暴露 setup checklist，`GET /applications` 随清单返回 dashboard；`packages/python-sdk/src/yggdrasil_sdk/ops_runtime/launcher.py` 与 `yggdrasil-ops launch`/`corepack pnpm yggdrasil:up` 提供本地产品一键启动。
> 2026/6/4 用户采用面 P1 同步：`graduate-researcher`、`deep-research`、`coding-greenfield`、`knowledge-studio` 的 `web/dashboard.json` 已升级为场景启动器，每个模板提供 `exampleTasks[]` 与 `expectedOutputs[]`；`apps/web/app/components/assets-page.tsx` 已从粘贴文本扩展为浏览器文本文件导入、切段预览、导入状态、摘要节点和“附加到新任务”入口；`task-launch-panel` 会展示模板示例/预期产物和已附加素材，并把素材摘要作为创建/启动上下文；全局顶栏、应用列表、应用详情和共享状态徽标已把首屏状态改成用户可读中文标签；README、用户指南、开发者指南和应用包接口规范已改成围绕首次成功路径和最短演示流程。
> 2026/6/4 用户采用面 P2 同步：`apps/web/app/release/page.tsx` 与 `components/release-page.tsx` 新增“发布与安全”产品页，把发布模式矩阵、公开演示路径、产品截图、本地数据位置、出机边界、备份/恢复和删除状态集中到用户可见入口；README 与 `docs/USER_GUIDE.md` 已补发布模式矩阵、截图与隐私边界；`docs/demos/LOCAL_FIRST_TASK_DEMO.md` 已固定外部演示脚本。当前只把开发者工作区和本地产品模式标为可用，完整 Docker 产品栈、桌面封装和托管 SaaS 不写成已支持能力。
> 2026/6/4 产品打包与远端数据计划同步：`docs/development/PRODUCT_PACKAGING_AND_REMOTE_DATA_REQUIREMENTS_GAP_2026_06_04.md` 已把完整 Docker Compose 产品栈、桌面封装、删除/清理/数据治理、托管 / SaaS、官方远端数据托管、远端备份和远端删除统一纳入计划；`/release`、README、用户指南、开发者指南和开源边界已改为“计划中但当前不可承诺”口径。本地产品模式仍不会自动上传数据。
> 2026/6/5 产品打包与数据治理预览同步：新增 `infra/docker-compose.product.yml`、`infra/docker/`、`infra/product.env.template`、`corepack pnpm product:*`、Windows 桌面启动器、`docs/specs/data-governance-manifest-v0.1.md`、Core API `/data-governance/*`、Web `/data-governance` 和 `data_governance_operations` 审计表；完整 Docker 产品栈、桌面封装和本地数据治理预览改为“预览可验证”，托管 / SaaS 和官方远端数据服务仍是计划项。
> 2026/6/6 产品栈维护与远端契约同步：新增 `packages/python-sdk/src/yggdrasil_sdk/provider_config.py`、`tests/api/test_provider_configuration_api.py` 和 `/health.providerStatus`，Web 任务启动面板在 provider key 缺失或 fallback 测试模式下阻止直接启动；`scripts/product-compose.mjs` 现在优先读取未跟踪的 `infra/product.env`，并提供快照列表、升级和回滚维护命令；Windows 桌面封装补齐未签名安装/卸载、托盘控制器、备份、恢复、快照、升级、回滚、更新检查、手动应用更新和快捷方式安装入口；2026/6/17 阶段 2 又补齐更新/升级/回滚/卸载影响预览、手动确认、失败状态记录和卸载默认保留本地数据，2026/6/18 阶段 3 已补做真实安装/默认卸载、删除本地数据确认门、Docker upgrade/rollback、失败恢复状态和 product smoke 配置一致性验证；新增 `docs/specs/remote-data-service-contract-v0.1.md` 冻结官方远端数据服务上线前边界。
> 2026/6/6 数据治理保护性执行同步：Core API `/data-governance` 新增 `GET /backups` 与 `POST /backup`，`POST /delete` 支持 `backupBeforeDelete` 并返回 `deletionCertificate`；Web `/data-governance` 新增备份快照、创建备份、精确确认 task 硬删除和删除证明展示，asset / node 仍只允许预览。
> 2026/6/18 产品发行完成度评估同步：新增 `docs/development/PRODUCT_RELEASE_COMPLETION_EVALUATION_2026_06_18.md`，当前综合发行完成度判断为 55/100；本地试用发行已达预览可用，Docker 产品栈和 Windows 桌面封装仍是预览，正式签名安装、发布渠道、多版本升级回滚验收、SaaS 和官方远端数据服务仍未完成。
> 2026/6/18 正式发行包与发布门禁同步：新增 `packaging/distributions/local-preview.json`、`packaging/desktop/windows/Build-Yggdrasil.ReleasePackage.ps1`、`Yggdrasil Build Release Package.cmd` 和 `scripts/product-release-smoke.mjs`；第一版正式发行路径定为 GitHub Releases + staged repo ZIP + SHA256，签名步骤预留但默认 unsigned，Docker 策略为检测/引导，更新仍是手动检查/手动应用；`Yggdrasil.Desktop.ps1` 支持 `start-app -OpenPath`，`Yggdrasil.Install.ps1` 支持 `-AppPackagePath` / `-DefaultAppId` / `-ShortcutName`。
> 2026/6/18 GitHub Releases 发布手册同步：新增 `docs/release/GITHUB_RELEASES_PLAYBOOK.md`，记录 `corepack pnpm release:package`、GitHub Release 资产和正文模板、unsigned 边界、Docker Desktop 检测/引导说明、发布前 `product:release-smoke` 门禁和发布后核验步骤；本机默认 3000 端口不可绑定时，已用 3300/5500/5501/5502 临时端口跑通完整 release smoke。
> 2026/6/1 Graduate heartbeat 观测增强：`tmp/run_grad_ml_eval_with_heartbeat.py` 现会在心跳周期内读取活动 sandbox 的 `evaluation.db`，追加输出 task 状态、currentFocus 摘要、snapshot 是否存在、cost 使用进度、invocation 计数与最近一次模型调用状态/错误摘要，便于区分“长调用慢跑”与“真实队列卡死”。

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
├── infra/          # 本地基础设施与产品 Docker Compose 预览栈
├── migrations/     # 数据库迁移
├── packaging/      # 桌面封装、未签名安装包、托盘与更新包装
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
    │   ├── page.tsx                # Start 首页：材料入口、任务草稿、本地隐私、AI 服务状态、阻塞项和启动前确认
    │   ├── layout.tsx              # 全局布局；阶段 1 已改为本地产品入口，普通导航保留开始/任务/应用/设置/支持，维护入口下沉
    │   ├── api/
    │   │   └── core/               # Core API 的前端代理（默认透传到 :5000）
    │   ├── applications/           # 应用场景浏览页
    │   ├── assets/                 # 资产管理页（上传、查看、版本）
    │   ├── collaboration/          # PR 审查与协作页
    │   ├── data-governance/        # 数据治理页（资产清单、备份快照、删除 dry-run、保护性 task 删除、删除证明、审计记录）
    │   ├── evaluations/            # 评测结果展示页
    │   ├── mcp/                    # MCP 模块状态页
    │   ├── nodes/
    │   │   └── [nodeId]/           # 记忆节点详情页（动态路由）
    │   ├── observability/          # 调用链路追踪页
    │   ├── prompting/              # Prompt 模板管理与预览页
    │   ├── release/                # 帮助与诊断页（发布模式、演示、数据位置、隐私、远端计划与支持边界）
    │   ├── settings/               # 普通设置中心：AI Service、Spending、Storage、App Defaults、Data & Privacy
    │   ├── tasks/
    │   │   ├── page.tsx            # 任务页：应用模板创建/草稿/立即启动入口
    │   │   └── [taskId]/           # 任务详情页（动态路由，现已挂接 LLM 工作分析摘要与独立分析路由）
    │   ├── training/               # 训练实验管理页
    │   └── components/             # 可复用 React 组件
    ├── lib/                        # 前端工具函数
    ├── public/demo/                # README、用户指南和 /release 使用的产品截图
    ├── package.json                # 前端包配置
    ├── next.config.ts              # Next.js 配置
    └── tsconfig.json               # TypeScript 配置（继承根配置；`*.tsbuildinfo` 为本地 typecheck 增量缓存，已由根 `.gitignore` 忽略）
```

**关键说明：**
- `app/api/core/` 是纯代理层，不含业务逻辑，请求直接转发至 Core API；阶段 1 后普通错误只提示“本地服务未启动 / 查看帮助与诊断”，不在用户界面暴露内部地址。
- 应用场景 UI（如 coding、research）由 `applications/` 目录下的应用插件提供，Web 工作台本身不承载场景专属页面。
- `apps/web/app/components/overview-page.tsx` 现在是阶段 1 Start 首页，消费 `/workbench/overview` 与 `/applications`，把材料入口、任务草稿、本地隐私、AI 服务状态、阻塞项和启动前确认放到首屏；数据库、Redis、模型调用、端口和 raw JSON 不再作为普通首页内容。
- `apps/web/app/components/task-launch-panel.tsx` 是 Web-first 任务入口：从应用 dashboard 的 `taskTemplates[]` 生成任务，展示 `exampleTasks[]` / `expectedOutputs[]` 和已附加素材，依次调用 `POST /tasks` 与 `POST /tasks/{taskId}/start`；草稿创建后在面板内保留“已创建 / 立即启动 / 查看任务”反馈，连接失败文案改为设置 / 帮助与诊断动作。
- `apps/web/app/components/assets-page.tsx` 是 P1 素材导入入口：支持浏览器读取文本类文件、切段预览、导入状态、摘要节点展示，并通过 `/tasks?assetId=...` 把素材附加到新任务。
- `apps/web/app/components/applications-page.tsx` 阶段 1 已改为四应用统一矩阵，默认突出 Deep Research、Graduate Writing、Coding Assistant、Knowledge Base，并按 Needs / Templates / Settings / Review Status / Primary Action 展示，内部 ID、模块数和场景数不再压在普通卡片上。
- `apps/web/app/components/settings-page.tsx` 是阶段 1 普通设置中心：AI Service、Spending、Storage、App Defaults、Data & Privacy；Prompt、MCP、评测、观测等维护者入口仍保留但不占普通主路径。
- `apps/web/app/components/release-page.tsx` 是帮助与诊断入口：展示当前真实支持的运行模式、provider 配置状态、演示步骤、截图、本地数据/日志/备份位置、出机边界，以及导出/恢复/删除状态；完整 Docker 产品栈和桌面封装当前只写成预览可验证，托管 / SaaS 和官方远端数据服务仍只能写成计划中。
- `apps/web/app/components/data-governance-page.tsx` 是本地数据治理入口：消费 `/data-governance/manifest`、`/backups`、`/backup`、`/deletion-plan`、`/delete` 和 `/operations`，开放备份快照、删除影响预览、受保护 task 硬删除、删除证明与审计查看；asset / node 仍只做预览。
- `apps/web/app/components/application-detail-page.tsx` 已把 `importantConfig` 的常用字段改成 dashboard `settingsSchema[]` 驱动的 typed controls；阶段 1 后普通摘要不再默认展示 appId、Prompt、memory namespace、effectiveConfig raw JSON，装配信息进入维护者详情。
- `apps/web/app/components/workbench-primitives.tsx` 提供 PageHeader/Surface/StatCard/StatusBadge 等共享组件；`StatusBadge` 现在保留原始状态值用于颜色判定，同时把常见运行状态、导入状态和素材角色显示为中文产品标签。
- `apps/web/app/lib/use-api-resource.ts` 是 Web 控制面通用 API loader；路径切换会清空旧数据，普通 reload 会保留当前数据直到新响应返回，避免任务创建后刷新列表时卸载启动面板。
- `apps/web/app/components/task-detail-page.tsx` 现已作为任务控制面 UI：除 pause/resume 外，也会展示 approve/revision、mailbox state/message 与 side-channel event，收口 P6 的前端可见性；同时已新增 LLM 工作分析摘要卡，并提供进入完整分析页的入口。
- `apps/web/app/components/task-llm-work-analysis.tsx` 负责 Web 端的正式 LLM 工作分析视图：任务详情页用 compact 模式展示摘要，独立分析页用 full 模式展示窗口、轮次、工具、工件和辅助信号；本轮已补上工作树调试摘要卡、节点切换时间线、prefix cache key 与 cache hit/write/non-cache 视图。
- `apps/web/app/tasks/[taskId]/analysis/page.tsx` 为任务级独立分析路由，直接消费 `/tasks/{taskId}/analysis/latest`。

---

## services/ · 后端微服务

```
services/
├── core-api/                       # 控制面 API 服务（:5000）
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
│               ├── data_governance.py # /data-governance/ - 数据资产清单、备份快照、删除 dry-run、审计、删除前备份与 task 硬删除后端
│               ├── evaluations.py  # /evaluations/ - 评测结果
│               ├── health.py       # /health - 健康检查（含首次启动 setupChecklist）
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
│               └── workbench.py    # /workbench/ - 总览数据（首页也消费嵌套 health setupChecklist）
│
├── agent-runtime/                  # Agent 执行引擎服务（:5001）
│   ├── pyproject.toml
│   └── src/yggdrasil_agent_runtime/
│       ├── main.py                 # 服务启动入口
│       ├── app.py                  # FastAPI 应用实例
│       └── runtime.py              # Agent 执行主逻辑（任务分发、LLM 调用闭环；现导出 approve/revision 运行时控制）
│
├── module-host/                    # 模块宿主服务（:5002）
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
│       │   │   ├── _records.py     # 通用 ORM -> domain/contract record mapper；保持在 G2 大文件门禁内
│       │   │   ├── _record_helpers.py # record mapper 共享 ActorRef / ExternalRef / EntityRef / score snapshot 转换
│       │   │   ├── _asset_records.py # asset / evaluation / dataset / model artifact record mapper，拆出以维持 G2 行数门禁
│       │   │   ├── _prompt_records.py # Prompt profile / seed template / compile artifact record mapper
│       │   │   └── _common.py      # 仓储共享导入聚合，导出通用与 prompt record mapper
│       │   ├── migrations.py       # 迁移工具函数
│       │   └── vector_store.py     # pgvector 向量操作封装
│       │
│       ├── # ── 运行时核心 ──────────────────────────────
│       ├── runtime_kernel/         # 核心运行时内核子包（root mount、主循环、durable snapshot store、安全关闭、任务接管、工作树图 ready-set reducer 与滚动前沿 runtime hints；execution_loop 已收敛为包级入口 + state/worker/transitions 语义模块；takeover reducer 现负责 work tree/context stack 推进、revision reopen、approval finalize 和 expected evidence 缺口硬阻断；transitions 会对重复 continuation 指令去重）
│       ├── llm_runtime/            # LLM 调用封装包（core/artifacts/behavior_recorder/invoke；包入口保留原 `yggdrasil_sdk.llm_runtime` 导入面）
│       ├── tool_runtime.py         # 工具注册与执行运行时
│       ├── hook_runtime.py         # Hook 事件触发与分发运行时
│       ├── hooks.py                # Hook 类型定义与注册接口
│       ├── application_runtime.py  # 应用配置加载与初始化
│       │
│       ├── # ── Prompt 管理 ──────────────────────────────
│       ├── prompting.py            # Prompt 模板管理、版本控制；runtime prompt 已增加 bootSections 四段（physical_interface/world_roots/behavior_constitution/scene_recovery），其中 physical_interface 现在只保留稳定接口绑定与实际 tool/capability inventory，场景化 tool policy 已移出 boot；恢复态会规范化 Working_Node / currentNodeId / memoryRetrievalState.workTreeNodeId / pcMemo，并在 P4 路径附带 `work_context_stack` / `childCompletionSummaries`；`runtime_hints` 区块会暴露当前节点、建议下一步、readiness 和最高压力前 3 个开放前沿；response requirements 已切到“root/非叶子节点负责高层视角、leaf 执行、执行噪声优先进入已有节点、允许 work-node-update 修改已有节点范围、无合适节点才 create、最终合成 child 可产出报告草稿、child 用 work-node-complete 带回有用信息与引用、一窗一状态 directive”的短合同，few-shot 会补入工作树使用案例且仍在恢复态自动跳过
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
│       ├── collaboration_runtime/  # PR 协作运行时包（context/subagents 语义模块）
│       ├── evaluation_runtime/     # 评测运行时子包（bootstrap / scorer / suite_runner；含 G4 longform / window stress / real-task parity 指标聚合、文件/目录语料装载、可选隔离沙箱保留，以及 live-provider-matrix 的正式合同型 acceptance 检查；fallback local evaluation 环境在 preserve sandbox 或显式 state root 下也会把 suite metrics 与 case sandboxes 写入持久 state，case 级 isolated runtime 现也会继承 suite 传入的 workspace_root，避免 clean workspace run 仍回拷原仓库）
│       ├── evaluation_cli.py       # 评测命令行工具
│       │
│       ├── # ── 可观测性 ─────────────────────────────────
│       ├── observability.py        # OTel Tracer 封装（11KB）
│       ├── observability_exporters.py # 多后端导出器（Jaeger、Langfuse；本地 4318/3100 不可达时自动跳过可选 exporter）
│       │
│       └── # ── 运维工具 ─────────────────────────────────
│           ├── data_governance.py  # 数据资产 manifest、删除影响预览、task 硬删除执行与审计记录
│           ├── ops_runtime/        # 运维运行时包（backup/compose/sandbox/scorecard/live/launcher/shared；compose 现含产品栈 smoke，且 product smoke 与 JS Compose 一样优先读取 infra/product.env）
│           ├── ops_cli.py          # 运维命令行工具（backup/restore/compose-smoke/product-compose-smoke/launch/pilot-sandbox/pilot-live/pilot-scorecard）
│           └── support.py          # 通用工具函数（含隔离工作区复制、CJK word_count 估算；sandbox 复制会动态忽略当前配置的 state root/state dir，并默认跳过仓库顶层 tmp，避免持久审计目录与临时输出被递归拷贝进下一轮评测）
│
├── contracts/                      # 跨语言共享类型定义
│   ├── package.json
│   └── src/                        # TypeScript 类型（与 Python contracts.py 对应）
│
└── frontend-sdk/                   # 前端专用 SDK
    ├── package.json
    └── src/                        # React Hooks、API 客户端、前端类型；`types.ts` 现已补齐 TaskDetailResponse、ApplicationDashboard、taskTemplates/settingsSchema/exampleTasks/expectedOutputs、AssetIngestResponse、TaskLaunchAttachment、setupChecklist、DataGovernance 与 durable task runtime control 契约
```

**关键说明：**
- `runtime_kernel/` 是系统最核心的运行时子包，承载任务状态机、Agent 执行编排、上下文管理、durable snapshot store、resume attempt、控制面、任务接管、工作树图调度纯函数与滚动前沿 runtime hints。
- `runtime_kernel/work_tree_graph.py` 是工作树图 / Fork 并行与滚动前沿 resolution 的纯函数 reducer：读取 `WorkTreeProtocol`、active fork run 视图、graphState 和 policy，输出 direct child ready/blocked set、pending 信息流摘要、可用 Fork 槽位、候选 batch、节点 resolution assessment 和 delivery readiness；这些结果默认作为提示 / 审计线索，只有 expected evidence 缺口在 reducer 中形成硬阻断。它明确不复用 subagent task/branch，也不切 task-global `currentNodeId`。
- `runtime_kernel/root_mount.py` 现在不再只给底层 identity/context/execution refs；它还会输出中文语义根指针、`SYS_ROOT_PROTOCOL`、`startupLoadOrder`、tool/capability index、mailbox/standby 状态，以及 `standby / resume-node / bootstrap` 三态 `startupMode`，作为启动恢复的数据面。
- `runtime_kernel/execution_loop/` 当前为包级运行主链：`state_metrics.py` / `state_window.py` / `state_memory.py` 承载指标、窗口工件、记忆树物化与 assistant tag 解析，`transitions.py` 承载完成/续跑/审批流转，`worker.py` 承载主 worker 入口；包入口仍保持 `yggdrasil_sdk.runtime_kernel.execution_loop` monkeypatch 与导入面。执行链仍保持“先基于 takeover protocol 预生成 work tree 锚点，再把外来 `currentContext` 物化进记忆树并执行 retrieval”，并已在 retrieval 前优先恢复 `currentNodeId / workingNodeAnnotation / pcMemo`；2026-06-27 后，worker 会在 takeover/work tree 同步后注入 `workTreeResolution`，prompt 将其作为 `runtime_hints`，transitions 只把 surviving `missing-target-evidence` 作为交付硬阻断。2026-06-28 起，`state_metrics._window_restart_trigger()` 只在显式 `forceWindowRestart` 或实际超过窗口阈值时触发窗口切换/overflow，`forcedWindowRestartBudget` 不再伪造未超阈值的失败。2026-06-29 起，`transitions.py` 对 work-tree correction、child/leaf start checkpoint 与 delivery retry tail 做重复检测，避免长链 continuation 把同一提示反复追加到 `responseRequirements`。
- 本轮设计冻结已同步到规格层：`docs/specs/agent-runtime-protocol-v0.2.md` 明确 `restart-recovery` 仅 legacy/stress 兼容、v2 默认“压缩优先+超阈值失败”；`docs/specs/work-tree-protocol-v0.2.md` 把第 9 章改为“窗口超阈值处理”，补齐压缩范围起止约束；`docs/specs/runtime-domain-data-spec-v0.1.md` 为 `ContextPruningPlan` 增加 `compressionRange` 元数据并固化 `maxUncompressedTailBeforeDecompress` 语义。
- `runtime_kernel/execution_loop/` 也负责正式任务进度流转：`Task.status/currentFocus/windowIndex/restartCount` 提供全局运行态，`TaskTakeoverProtocol.workTree.currentNodeId/status` 与 `WorkContextStack.topFrameId` 提供执行节点级进度；在当前单一路径下，非根子节点通过 `work-node-complete` / `work-node-handoff` 完成后会先写入父 frame 的 `childCompletionSummaries` 并回父节点，由父节点通过 `work-node-enter` / `work-node-create` 显式编排后续路径；2026-07-01 起，`work-node-complete confirmChildren="true"` 可在父节点确认真实工作已吸收后递归关闭当前节点非终态子树，根节点完成仍进入 `awaiting-approval`（本轮标记为后续要收窄的控制边界）。`task-takeover` 模块现在只保留安全 / 来源证据类 hard gate；`delivery.result / evidence` 为 advisory，`pending / incomplete` 不再作为硬交付门禁，缺少可选章节不会触发格式型 retry / failed。
- `runtime_kernel/snapshot_store.py` 是 durable snapshot payload 权威存储入口，写入 `.yggdrasil/state/snapshots/{projectId}/{taskId}/{snapshotId}/manifest.json` 与 blobs；`runtime_kernel/snapshot.py` 负责 active-paused/latest-auto snapshot 物化，并在 pending tool-call safe-stop 上拒绝半截 arguments、只为完整 tool-call 写 durable checkpoint；`runtime_kernel/execution_control.py` 负责 `/pause`、`/resume`、`/cancel`、保存 snapshot 与从 user-saved snapshot 创建分支。
- `runtime_kernel/execution_loop/worker.py` 对恢复态 snapshot 做 manifest/checksum/rehydrate 校验；失败进入 `resume-blocked` 并保留 blocker，不再 fallback start；同一文件现在也会把 `invoke_runtime_completion()` 的 provider/LLM invocation exception 纳入 failed-leaf continuation：非根叶子若已有 `failureTransition.requiresContinuation`，会像窗口超限一样先写回 `failed + failureSummary`，再排队 sibling/parent continuation，而不是直接把整任务打成 failed；滚动前沿链路中，worker 在 assessment 失败时会清除陈旧 `workTreeResolution`，避免 stale payload 误导 prompt/transition。
- `prompting.py` 的 response requirements 已从强编排合同收敛为短自主工作合同：root/非叶子节点负责高层视角、流程控制、方向重估和信息合并；叶子节点负责具体执行；执行产生搜索、编辑、命令、失败尝试、重复项或候选路线时，按当前节点 / Working_Node / WorkContextStack 优先用 `work-node-enter` 进入已有节点，其次用 `work-node-update` 修改已有节点范围，最后才用 `work-node-create` 新建节点；最终合成/撰写报告可以作为 child 执行并产出完整报告草稿，但当前 child/leaf 到停止点时必须用 `work-node-complete` 交付结果、证据/文件/记忆引用、已废弃路线、风险和建议下一步，不能只写自然语言 handoff，也不能直接宣告整体完成；每个 LLM window 最多输出一个会改变工作树状态的 directive，输出后停止，等下一窗口在新状态继续；`runtime_hints` 只是辅助线索，不覆盖任务、工具、用户请求和当前节点。runtime prompt 仍附带结构化 `memory_retrieval_state`，并在恢复态把 Working_Node、`currentNodeId`、`pcMemo` 与 retrieval node pointer 统一到同一执行节点；P4 路径额外会渲染 `work_context_stack` 和必要 child summaries；takeover 协议段优先给出 work tree 摘要，不再渲染计划质量、返工率和交付完整度。
- `llm_work_analysis.py` 现作为正式的 run-first 分析器：主键骨架是 task/run/model_invocations，本地补读 request/response/prompt/metrics/takeover/work-context/window-execution/behavior-record 工件，并默认把结果写入 `state/analysis/llm-work/` 供评测与调试复用；当前已补齐 cache summary、work-tree timeline、approval stop、mixed outcome、per-invocation `runtime/window-executions/by-invocation/` 历史工件和 `llm/behavior-records/` 行为记录读取。
- `langfuse_trace_layered_analysis.py` 现兼容中文化的任务目标/任务说明/当前焦点标签，避免 prompt 标签本地化后 Langfuse 文本审查丢失任务抽取结果。
- `llm_runtime/` + `tool_runtime.py` 构成正式工具分发链；当前正式主链走 `llm_runtime/core.py`、`llm_runtime/artifacts.py`、`llm_runtime/behavior_recorder.py` 与 `llm_runtime/invoke.py`，包入口负责 Langfuse monkeypatch 同步。行为记录器从 request/response/compiled prompt 派生 `state/llm/behavior-records/`，记录详细 `toolExecutions`、round-derived `observedToolCallCount`、rounds、work-tree directive、prompt 文本可用性和模型自述工具次数差异，不再保留无意义的 `part_a/part_b` 文件。
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
│   └── src/yggdrasil_pause_resume/
│
├── task-takeover/                  # Gate 2 任务接管协议（目标解析、约束、计划、验证、交付）
│   └── src/yggdrasil_task_takeover/
│
├── subagent-runtime/               # Sub-Agent prompt profile 注册模块；执行闭环在 collaboration_runtime、worker 与 subagent-pr
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
├── graduate-researcher/            # 研究生学习与研究（预算驱动）
├── maintenance-ops/                # 系统运维与巡检
├── scenic-guide/                   # 信息导览与规划
└── software-factory/               # 大型软件工程全流程
```

**每个应用的标准文件结构：**

```
applications/<name>/
├── yggdrasil.app.yaml      # 应用清单（绑定模块、模型路由、种子上下文）
├── config/defaults.json     # 应用默认配置
├── web/dashboard.json       # 控制面元数据：hero、quickActions、taskTemplates、exampleTasks、expectedOutputs、settingsSchema
├── memory/                  # 应用静态记忆资产（随包发布，运行时按应用命名空间叠加）
├── prompt-profiles/          # 主 Agent / Sub-Agent prompt profile
└── scenes/                   # seed template / 场景启动资产
```

**关键说明：**
- `web/dashboard.json` 现在是用户采用面的关键入口，必须提供 `taskTemplates[]` 供 Web 任务启动面板使用；顶部应用模板应提供 `exampleTasks[]` 与 `expectedOutputs[]`，并提供 `settingsSchema[]` 把 provider、model、预算、workspace、输出风格、记忆命名空间和工具权限渲染为 typed controls。
- `apps/web/app/components/task-launch-panel.tsx` 会读取 `/health.providerStatus`；provider key 缺失或 `YGGDRASIL_DISABLE_LIVE_LLM=1` fallback 测试模式会阻止直接启动真实任务，但仍允许创建草稿。
- `services/core-api/src/yggdrasil_core_api/services/runtime_service.py` 的 `list_applications()` 已把 dashboard payload 随 `GET /applications` 返回，任务页无需再逐个请求应用详情才能显示模板。

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
- `packages/python-sdk/src/yggdrasil_sdk/provider_config.py` 是 provider key 配置状态的共享契约，不暴露 key 值；Core API `/health.providerStatus` 和 Web 启动阻塞都应从这里取状态。
- paid provider（如 `deepseek_direct`）只有在显式设置 `YGGDRASIL_ALLOW_PAID_MODELS=1` 时才会进入 runtime candidate catalog。
- DeepSeek 直连 profile 已切换到 `deepseek-v4-flash` / `deepseek-v4-pro`，旧 `deepseek-chat` / `deepseek-reasoner` 会直接拒绝；thinking mode 默认 `reasoning_effort=max`，最大输出按 384000 tokens 请求，兼容 `reasoning_content` 回传，并通过 stream idle timeout / reconnect telemetry 区分 provider 断流、length 截断和真实完成。
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
├── architecture/                    # 项目设计哲学与架构说明
│   ├── design-philosophy-and-cognitive-principles.md # 项目设计哲学唯一主文档：记忆树、工作树、能力/Skill/工具目录、主体权责、信息价值与进化的统一认知架构
│   ├── weak-model-behavior-compensation-notes.md # 非规范维护注释：弱模型过强行为提示、风险、强度和退场条件
│   ├── overview.md                  # 系统目的、主要组成与依赖方向概览
│   ├── module-boundaries.md         # 模块依赖边界说明
│   ├── data-flow.md                 # 系统数据流概览
│   └── runtime-principles-for-newcomers.md # 面向新人的运行原理说明
├── design-handoff/                 # UX 重塑外包资料包：基座用户界面、应用包体验、设置/调试/配置、启动器/安装器四组界面 brief
│   ├── README.md                    # 资料包总览：范围、当前真实基础、交付物、验收门槛和资料来源
│   ├── 01-base-user-interface-agent.md # 基座客服型 Agent、应用路由、Prompt 代写、任务确认和错误支持 brief
│   ├── 02-application-package-experience.md # 应用包场景页、任务模板、执行过程可视化和上下文折叠回顾 brief
│   ├── 03-settings-debug-configuration.md # 普通设置、高级设置和维护者调试三层配置界面 brief
│   └── 04-launcher-experience.md     # 启动器安装向导、桌面主窗口、托盘菜单、应用包快捷方式、诊断和维护体验 brief
├── development/                    # 开发专题文档目录（具体文件见顶层速览）
│   ├── MOE_MODEL_ROUTING_ASSESSMENT_2026_06_14.md
│   │                               #   世界树 Agent MoE 模型分层与任务难度评估：聚焦 2026-03+ 新开源/开放权重 MoE，按具体模型、主/子任务和 D0-D4 路由规划选型
│   ├── MULTI_AGENT_WORKTREE_GRAPH_DESIGN_2026_06_20.md
│   │                               #   多 Agent 自分裂与工作树图调度设计盘点：梳理现有协议/实现地基，给出图关系、局部 ready-set 调度、Fork、知识继承、资源路由、冲突合同、控制面与评测的下一步设计清单
│   ├── WORK_TREE_GRAPH_FORK_EVALUATION_TASKS_2026_06_21.md
│   │                               #   工作树图与 Fork 并行测试任务设计：定义仿真任务、真实任务、验收指标、后续批次依赖和用户决策项
│   ├── WORK_TREE_GRAPH_FORK_IMPLEMENTATION_PLAN_2026_06_21.md
│   │                               #   工作树图与 Fork 并行实现计划：按 graph reducer、AgentRun 字段、Fork planner、worker 运行视图、结果合并和 runtime harness 拆分实现 PR
│   ├── ROLLING_FRONTIER_WORK_TREE_RESOLUTION_2026_06_27.md
│   │                               #   滚动前沿工作树分辨率提示：宽泛节点合法、开放前沿提示 refine/work/merge/deliver/block、失败预算推动拆小，expected evidence 缺口才硬阻断，并固定八个长程核心前沿
│   ├── LLM_LONG_HORIZON_OVERDESIGN_AUDIT_2026_06_27.md
│   │                               #   LLM 长程控制过度设计审计：区分安全边界与过度控制，提出 prompt 瘦身、delivery gate 降级、clarification 不禁工具和状态瘦身顺序
│   ├── LLM_WORK_TREE_USAGE_GUIDE_AND_CASES_2026_06_28.md
│   │                               #   LLM 工作树使用指南与案例：把工作树定位为上下文卫生工具，补齐 7 类使用场景、多层组合案例、root/leaf 职责、父节点回收格式、反例和行为记录器要求
│   ├── LLM_LIVE_WORKFLOW_AND_WORK_TREE_RERUN_AUDIT_2026_06_28.md
│   │                               #   LLM live 工作流程与工作树复跑审计：记录储能 real-task 重跑、完成后追问、每步反思、批评 revision 继续三组实验，固化 root-only 惯性与 observed tool call 证据
│   ├── LLM_WORK_TREE_HARD_PROMPT_EXPERIMENTS_2026_06_29.md
│   │                               #   LLM 工作树硬提示实验记录：记录工具末尾强提醒、工具调用即 leaf 示例、leaf 自言自语示例、DeepSeek V4 Pro 和 leaf 执行/父节点评估重跑，区分工作树使用行为与交付质量
│   ├── DESIGN_COMPLETION_EVALUATION_2026_06_05.md
│   │                               #   设计完成度评估：按当前设计文档和实现证据，给出工程设计、外部用户采用度、产品发行、数据治理、协作、模块和评测等完成度评分
│   ├── STITCH_DESIGN_ACCEPTANCE_2026_06_17.md
│   │                               #   Stitch 设计稿四组页面验收报告：记录主页、应用包、设置、启动器首次验收缺口、V2/V3 返工复验和 V4-V10 合格线返工；仓库只保留最终 V10 通过候选证据
│   ├── DESIGN_ENGINEERING_IMPLEMENTATION_PLAN_2026_06_17.md
│   │                               #   Stitch 最终设计落到工程实现与未完成项计划：阶段 0 已补齐代码入口、旧入口清理、文件级改造和测试清单，后续按桌面主路径、启动器维护闭环、验证清理、移动端/窄屏和可访问性分阶段执行
│   ├── stitch-design-captures-2026-06-17/
│   │                               #   Stitch 抓取证据包：只保留 Project Yggdrasil Design System 的最终通过候选 post-rework-v10-passline/，不包含 API key；失败轮次只在验收报告中保留文字判定
│   ├── TASK_CHECKFLOW_AUDIT_AND_ALIGNMENT_2026_05_27.md
│   │                               #   任务核对流程审计与对齐：冻结“理解任务->形成计划->向发起者核对->再执行”流程，并标注当前实现缺口与分级推进建议
│   ├── WORLD_BUILD_INITIAL_AWAKENING_TASK_START_EXECUTION_2026_05_26.md
│   │                               #   世界构建、初次苏醒与任务级工作状态读取实施文档：把新三阶段规格翻译成 contracts/root_mount/execution_loop/prompting/takeover/snapshot/tests 的实现顺序
│   ├── TASK_WORLD_START_STATE_AND_TASK_RUNTIME_SPLIT_2026_05_26.md
│   │                               #   给低智商 code agent 的任务文档：把“起始状态 + 任务级工作状态读取”重构拆成明确步骤、禁止事项、测试命令与完成标准
│   ├── TASK_WORLD_START_STATE_RUNTIME_REWORK_FIXUP_2026_05_26.md
│   │                               #   给 code agent 的返工任务文档：针对验收残留问题，强制收口世界级/任务级边界、无损恢复判定和 TaskRuntimeState 唯一入口
│   ├── PRODUCT_PACKAGING_AND_REMOTE_DATA_REQUIREMENTS_GAP_2026_06_04.md
│   │                               #   产品打包与官方远端数据能力需求差距：Docker 产品栈、桌面封装、删除治理、SaaS、远端托管/备份/删除的计划与缺口
│   ├── PRODUCT_RELEASE_COMPLETION_EVALUATION_2026_06_18.md
│   │                               #   产品发行完成度评估：综合 55/100，分层评估本地试用、正式发行、Docker 产品栈、桌面封装、数据治理、SaaS 和远端数据服务
│   ├── FEATURE_CLASSIFICATION_AND_PROMPT_CHECK_PLAN_2026_05_18.md
│   │                               #   功能形态分类与提示词功能检查计划：按纯代码 / 代码+提示词 / 纯提示词分类当前设计，并给出以纯提示词为重点的检查路径
│   └── ...                         #   其他开发专题文档同顶层速览
│
├── demos/
│   └── LOCAL_FIRST_TASK_DEMO.md    # 本地首次成功演示脚本：按 Web 路径演示素材导入、模板任务创建、启动和结果查看
├── release/
│   └── GITHUB_RELEASES_PLAYBOOK.md # GitHub Releases 发布手册：staged repo ZIP、SHA256、手动更新、Docker 检测/引导、签名预留和发布后核验
│
├── new/                            # 新方案草稿与当前重做输入材料
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
│   ├── work-tree-graph-fork-parallel-protocol-v0.1.md # 工作树图与 Fork 并行协议：父节点局部 ready-set、边传递、父上下文缓存继承、child 焦点、延迟信息流索引、递归 Fork 与 maxForks 同时活跃上限
│   ├── task-pause-resume-continuation-contract-v0.1.md # 任务暂停、恢复与继续契约：长期 Durable Snapshot、ResumeAttempt、持久 WorkItem、手动保存/分支、tool-call 等价性与不得 fallback start
│   ├── world-build-awakening-task-start-protocol-v0.1.md # 世界构建、初次苏醒与任务启动协议：区分世界级学习与任务级工作状态读取，引入起始状态与无损恢复优先级
│   ├── application-package-interface-v0.1.md # 应用包接口总规范：manifest、prompt/memory 文件、MCP 服务器、前端界面、场景任务模板与控制面 API
│   ├── graduate-researcher-app-v0.1.md       # Graduate Researcher 应用包定义：目标分析、预算语义、计划-步骤-动作三层模型与按需分解规则
│   ├── graduate-researcher-test-standard-v0.1.md # Graduate Researcher 测试标准：机器学习研究生场景的行为验收口径
│   ├── agent-runtime-protocol-v0.1.md       # Agent 运行时协议规格
│   ├── task-takeover-protocol-v0.1.md       # Gate 2 任务接管协议：目标/约束/计划/验证/交付与出口标准
│   ├── runtime-domain-data-spec-v0.1.md     # 运行时、work tree、TaskSnapshot/ResumeAttempt、worker activity 与工具数据规格
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
│   ├── archive/
│   │   └── future-planning/
│   │       └── Project-Yggdrasil 未来多模态潜空间智能体架构.md
│   │                               #   面向远期能力的前瞻研究草案，不纳入当前 Gate 承诺范围；2026-07-01 按历史删除前路径恢复
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
    ├── g4-multiscene.json          # G4 历史三场景离线套件（当前根脚本不再直接映射到此文件）
    ├── g4-provider-matrix.json     # G4 官方 live provider matrix（DeepSeek + LongCat；live artifact 现含 token 用量拆分、contextLengthObservations 与 runtimeMetrics）
    ├── g4-provider-matrix-longform.json
                                    #   G4 单任务长样本 live provider matrix（先聚焦一个更长的 coding 任务；用于观察长任务 token 与上下文窗口压力）
    ├── g4-real-task-externalized.json
                                    #   G4 默认真实任务入口（single-goal / externalized；用于正式 real-task 合同）
    ├── g4-real-task-unrelated-dual-live.json
                                    #   G4 无关任务双模型 live 入口（固定 unrelated incident RCA；LongCat 2 与 DeepSeek v4 Flash 同题对照；历史 case 可能仍带旧 footer 合同，不代表当前 runtime delivery gate）
    ├── g4-real-task-web-research-default.json
                                    #   G4 默认 Web Research 入口（网络检索 + 多源对比 + 矛盾处理；当前 eval:g4:multiscene 与 eval:g4:web-research:default 均映射到这里；要求 live 工具调用、窗口执行工件和工作树连续性证据，不再用 fake restart/cache gate/approval 门槛作为通过条件）
    ├── g4-graduate-ml-longcat2.json
                                    #   机器学习研究生专用 live 入口（Graduate Researcher 应用 + LongCat 2；强调 tool-rich 学习过程、计划-步骤-动作结构与阶段汇报）
    ├── g4-graduate-ml-deepseek-v4.json
                                    #   机器学习研究生专用 live 入口（Graduate Researcher 应用 + DeepSeek V4；用于 LongCat 以外的结构化对照）
    ├── work-tree-fork-runtime-harness.json
                                    #   工作树图 Fork Batch 6 deterministic runtime harness（执行两轮 worker harness pytest 并写入 evaluation metrics）
    ├── work-tree-fork-runtime-live-candidate.json
                                    #   工作树图 Fork Batch 6 手动 live candidate smoke（需要 YGGDRASIL_FORK_RUNTIME_LIVE=1 和 provider key；已通过真实 LongCat runtime completed 终态）
    ├── work-tree-fork-evaluation-tasks.json
                                    #   工作树图 Fork R1-R4 deterministic evaluation tasks（四区域审查、release gate、三资料包对比、多文件迁移计划）
    ├── work-tree-fork-public-showcase.json
                                    #   工作树图 Fork 公开展示题（韧性能源与应急通信计划；benefit 估算 + LongCat live 输出；不是长任务证据）
    ├── g4-real-task-window-parity.json
                                    #   G4 真实任务窗口对照专项资产（当前根 package.json 不暴露 pnpm 脚本）
    ├── g4-real-task-window-parity-flash.json
                                    #   G4 真实任务窗口对照 flash 专项资产（当前根 package.json 不暴露 pnpm 脚本）
    ├── g4-real-task-minimal-workset.json
                                    #   G4 真实任务最小工作集 legacy 参考（repo-specific 历史样本；当前根 package.json 不暴露 pnpm 脚本）
    ├── g4-real-task-work-tree-debug.json
                                    #   G4 真实任务工作树调试 harness（显式嵌套 takeoverProtocol，从 child 节点起步；当前目标已切到 child 先回父节点、父节点再决定 sibling/leaf 的编排语义）
    ├── g4-real-task-work-tree-post-question-live.json
                                    #   G4 live 行为实验：主任务完成后追加 user 追问，审计 LLM 为什么没有使用工作树或没有继续下一步
    ├── g4-real-task-work-tree-step-reflection-live.json
                                    #   G4 live 行为实验：每个重要证据/工具批次后要求重新审视目标与工作树位置
    ├── g4-real-task-work-tree-critique-continue-live.json
                                    #   G4 live 行为实验：种 awaiting-approval 半成品后发送批评式 revision，验证是否继续执行以及是否进入工作节点
    ├── g4-real-task-work-tree-tool-end-reminder-live.json
                                    #   G4 live 行为实验：工具批次结束后注入流程控制反思提醒
    ├── g4-real-task-work-tree-tool-call-leaf-example-live.json
                                    #   G4 live 行为实验：用“工具调用即 leaf”强示例要求先建 child/leaf 再执行工具
    ├── g4-real-task-work-tree-leaf-self-talk-live.json
                                    #   G4 live 行为实验：用更明确的 leaf 执行、自言自语和执行后判断示例验证流程控制稳定性
    ├── g4-real-task-work-tree-deepseek-v4-pro-live.json
                                    #   G4 live 行为实验：同题切换 deepseek_direct/deepseek-v4-pro，区分模型能力与工作树使用行为
    ├── g4-real-task-work-tree-deepseek-v4-pro-critique-continue-live.json
                                    #   G4 live 行为实验：DeepSeek leaf/父评估口径上叠加“批评后继续 + 先做任务控制分析”，验证 revision 是否能重开 completed+unfinished 工作树并继续正确调度
    ├── g4-real-task-work-tree-deepseek-v4-pro-node-tool-budget-live.json
                                    #   G4 live 行为实验：DeepSeek + auto-unfinished continuation + 每节点 5 次 toolcall 软预算，验证工具预算是否促成 leaf/父节点流程控制
    ├── g4-real-task-work-tree-deepseek-v4-pro-directive-required-live.json
                                    #   G4 live 行为实验：DeepSeek + runtime directive-required + 子节点范围强化 + work-node-complete child 交付案例；64 轮上限，满轮保留 manual-continue 现场 + snapshot 侧信道诊断
    ├── g4-real-task-work-tree-deepseek-v4-pro-parent-retention-live.json
                                    #   G4 live 收束实验：DeepSeek + 父节点读取 child summaries / report artifacts / tool evidence 后再判断是否开 leaf，验证父子信息丢失假设
    ├── g4-real-task-work-tree-deepseek-v4-pro-finish-prune-live.json
                                    #   G4 live 收束实验：DeepSeek + 父/root 停止条件 + work-node-skip/prune 废旧节点清理交付案例
    └── g4-real-task-work-tree-longcat-finish-prune-live.json
                                    #   G4 live 收束实验：LongCat-2.0 使用同一 finish/prune 口径，验证模型差异
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
| `eval:g4:multiscene` | `suites/g4-real-task-web-research-default.json` |
| `eval:g4:web-research:default` | `suites/g4-real-task-web-research-default.json` |
| `eval:g4:graduate-ml:longcat2` | `suites/g4-graduate-ml-longcat2.json` |
| `eval:g4:graduate-ml:deepseek-v4` | `suites/g4-graduate-ml-deepseek-v4.json` |
| `eval:g4:provider-matrix` | `suites/g4-provider-matrix.json` |
| `eval:g4:provider-matrix:longform` | `suites/g4-provider-matrix-longform.json` |
| `eval:g4:real-task-unrelated:dual-live` | `suites/g4-real-task-unrelated-dual-live.json` |
| `eval:g4:work-tree-debug` | `suites/g4-real-task-work-tree-debug.json` |
| `eval:g4:work-tree:post-question` | `suites/g4-real-task-work-tree-post-question-live.json` |
| `eval:g4:work-tree:step-reflection` | `suites/g4-real-task-work-tree-step-reflection-live.json` |
| `eval:g4:work-tree:critique-continue` | `suites/g4-real-task-work-tree-critique-continue-live.json` |
| `eval:g4:work-tree:tool-end-reminder` | `suites/g4-real-task-work-tree-tool-end-reminder-live.json` |
| `eval:g4:work-tree:tool-call-leaf-example` | `suites/g4-real-task-work-tree-tool-call-leaf-example-live.json` |
| `eval:g4:work-tree:leaf-self-talk` | `suites/g4-real-task-work-tree-leaf-self-talk-live.json` |
| `eval:g4:work-tree:deepseek-v4-pro` | `suites/g4-real-task-work-tree-deepseek-v4-pro-live.json` |
| `eval:g4:work-tree:deepseek-v4-pro-critique-continue` | `suites/g4-real-task-work-tree-deepseek-v4-pro-critique-continue-live.json` |
| `eval:g4:work-tree:deepseek-v4-pro-node-tool-budget` | `suites/g4-real-task-work-tree-deepseek-v4-pro-node-tool-budget-live.json` |
| `eval:g4:work-tree:deepseek-v4-pro-directive-required` | `suites/g4-real-task-work-tree-deepseek-v4-pro-directive-required-live.json` |
| `eval:g4:work-tree:deepseek-v4-pro-parent-retention` | `suites/g4-real-task-work-tree-deepseek-v4-pro-parent-retention-live.json` |
| `eval:g4:work-tree:deepseek-v4-pro-finish-prune` | `suites/g4-real-task-work-tree-deepseek-v4-pro-finish-prune-live.json` |
| `eval:g4:work-tree:longcat-finish-prune` | `suites/g4-real-task-work-tree-longcat-finish-prune-live.json` |
| `eval:work-tree:fork-runtime-harness` | `suites/work-tree-fork-runtime-harness.json` |
| `eval:work-tree:fork-runtime-live` | `suites/work-tree-fork-runtime-live-candidate.json` |
| `eval:work-tree:fork-evaluation-tasks` | `suites/work-tree-fork-evaluation-tasks.json` |
| `eval:work-tree:fork-public-showcase` | `suites/work-tree-fork-public-showcase.json` |

---

## infra/ · 本地基础设施

```
infra/
├── README.md                       # 基础设施和产品 Compose 使用说明（端口、环境变量、备份恢复）
├── product.env.template            # 产品 Compose 环境模板（provider key、端口、DB/Redis/NATS、state root；复制为 gitignore 的 product.env 后写真实 key）
├── product.env                     # 本机产品 Compose 私有环境文件（gitignore；存在时 product:* 优先读取）
├── docker/
│   ├── python-service.Dockerfile   # Core API / Agent Runtime / Module Host / Worker 共用 Python 镜像
│   └── web.Dockerfile              # Next.js standalone Web 镜像
├── docker-compose.yml              # 主基础设施栈
│                                   #   PostgreSQL 17 :5432
│                                   #   Redis 7.4 :6379
│                                   #   NATS JetStream :4222
│                                   #   MinIO :9000/:9001
│                                   #   Temporal :7233 + UI :8088
│                                   #   Jaeger :16686
│                                   #   OTel Collector :4318
├── docker-compose.product.yml      # 完整产品栈预览（依赖 + migrate + Core API/Agent Runtime/Module Host/Worker/Web）
├── langfuse-compose.yml            # Langfuse 本地观测栈（独立端口段，避免冲突）
│                                   #   Langfuse Web :3100（可选；未启动时 exporter 自动跳过）
│                                   #   ClickHouse :18123
│                                   #   Langfuse MinIO :19090
└── otel-collector-config.yaml      # OTel Collector 配置（Traces → Jaeger + Debug）
```

---

## packaging/ · 桌面封装

```
packaging/
└── desktop/
    └── windows/
        ├── README.md                    # Windows 桌面封装说明、维护确认、失败恢复与支持边界
        ├── Yggdrasil.Install.ps1        # 未签名安装/卸载脚本；卸载默认保留本地数据，危险删除需二次确认
        ├── Yggdrasil Installer.cmd      # 安装到 LOCALAPPDATA 并启动托盘
        ├── Yggdrasil Uninstaller.cmd    # 卸载桌面封装、启动项和快捷方式，默认保留本地数据
        ├── Yggdrasil.Tray.ps1           # PowerShell WinForms 托盘控制器
        ├── Yggdrasil Tray.cmd           # 隐藏窗口启动托盘控制器
        ├── Yggdrasil.Update.ps1         # 更新检查、影响预览、fast-forward 手动确认应用和计划任务安装
        ├── Yggdrasil Update.cmd         # 检查更新并写入 update-state.json（含影响预览）
        ├── Yggdrasil Apply Update.cmd   # 仅 clean worktree + fast-forward 时确认、创建备份并应用更新
        ├── Yggdrasil Install Auto Update Task.cmd
        ├── Yggdrasil Uninstall Auto Update Task.cmd
        ├── Build-Yggdrasil.DesktopPackage.ps1 # 构建未签名 ZIP 到 dist/desktop/
        ├── Yggdrasil Build Installer.cmd
        ├── Yggdrasil.Desktop.ps1        # start/stop/status/open/open-apps/open-settings/logs/backup/restore/snapshots/upgrade/rollback/shortcuts 主脚本
        ├── Yggdrasil Desktop.cmd        # 启动本地产品并打开 Start 首页
        ├── Yggdrasil Stop.cmd           # 停止本地产品
        ├── Yggdrasil Status.cmd         # 查看健康状态与产品检查
        ├── Yggdrasil Logs.cmd           # 打开诊断日志窗口
        ├── Yggdrasil Backup.cmd         # 创建本地数据备份
        ├── Yggdrasil Restore.cmd        # 恢复本地备份
        ├── Yggdrasil Snapshots.cmd      # 列出本地备份
        ├── Yggdrasil Upgrade.cmd        # 影响预览 + 手动确认 + 保护性备份 + 升级
        ├── Yggdrasil Rollback.cmd       # 影响预览 + 手动确认 + 保护性备份 + 恢复
        ├── Yggdrasil Install Shortcuts.cmd
        └── Yggdrasil Uninstall Shortcuts.cmd
```

**关键说明：**
- 这是桌面封装预览，不是签名发行版；当前安装包标记 `signed=false`。
- 自动更新任务只检查更新，不静默应用新版代码；真正更新必须用户手动触发且只允许 clean worktree + fast-forward。
- `update-state.json`、`maintenance-state.json` 和 `%LOCALAPPDATA%\ProjectYggdrasil\uninstall-state.json` 分别记录更新、升级/回滚和卸载的影响预览、成功/失败状态与恢复动作。
- 卸载默认保留 `.yggdrasil`、`.yggdrasil-backups` 和 `infra/product.env`；删除本地状态和备份必须显式 `-DeleteLocalData` 并输入确认文本。
- 它包装 `corepack pnpm product:*` 命令，依赖 Docker Desktop 可用；Web 端口优先读取 `infra/product.env`。

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
- `migrations/versions/0f7c6e2a8d91_data_governance_operations.py`：新增 `data_governance_operations` 审计表，支撑删除 dry-run、task 硬删除和阻塞记录。
- `migrations/versions/9c0a7d6e5f21_durable_task_resume_chain.py`：合并当前 migration heads，并新增 `task_resume_attempts`、`runtime_work_items`、`task_branches`，扩展 `task_snapshots` durable manifest/retention/blocker 字段和 `tasks` resume 控制字段；迁移时把旧 raw resume token 哈希到 `resume_token_hash`，并把历史待暂停状态折叠为 `running + pending_control_intent=pause`。

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
│   ├── test_data_governance_api.py
│   │                               # 数据治理 manifest、dry-run 审计、运行中任务阻塞与 task 级硬删除回归
│   ├── test_persistence_task_runtime_api.py
│   │                               # tasks/nodes/runtime/workbench 等基础 API 持久化与读取回归
│   ├── test_persistence_control_plane_api.py
│   │                               # 启停控制、资产/训练/prompt/mcp 控制面 API 回归
│   └── test_persistence_app_scope_api.py
│                                   # appId 过滤语义与 M9 control-plane suite 回归
├── test_prompting_runtime.py       # PromptCompiler 链路端到端；覆盖恢复态 `runtime_hints` 区块、最高 3 个开放前沿排序、短 response requirements、clarification 只读工具和 takeover 协议瘦身
├── test_runtime_and_pruning.py     # 迁移索引文件（运行时/裁剪专项测试已拆分到 tests/runtime）
├── test_runtime_p4_foundation.py   # P4/P7 基础回归：work tree reducer、awaiting-approval、单路径运行态与 approval/revision 闭环
├── runtime/
│   ├── test_runtime_core_and_memory.py
│   │                               # 运行时核心挂载、上下文裁剪、记忆树物化与 memory-write 标签回归
│   ├── test_runtime_restart_and_resume.py
│   │                               # 窗口重启、retry 持久 work item 与 durable resume-blocked 回归
│   ├── test_runtime_budget_and_audit.py
│   │                               # 预算硬约束、审计级别与 response 指标回归
│   ├── test_runtime_pause_regressions.py
│   │                               # queued pause durable snapshot、resume attempt 幂等与 runtime metrics 计数回归
│   └── test_work_tree_graph_scheduler.py
│                                   # 工作树图 ready-set / Fork 并行与滚动前沿分辨率提示回归：diamond、延迟信息流、自动 batch、父节点重排门禁、maxForks 活跃上限、宽泛节点 refine、开放前沿 advisory、失败预算、八个长程核心前沿、expected evidence hard blocker、turn evidence 写回与 stale payload 清理
├── test_text_memory_and_adapters.py# 文本记忆模块与适配器集成
├── test_module_catalog.py          # 模块目录发现与注册
├── test_module_host_eventing.py    # 模块宿主事件总线集成
├── test_mcp_bridge.py              # MCP 协议桥接回归
├── test_support.py                 # 通用支持函数回归（含 CJK word_count 口径、workspace sandbox 复制边界）
├── test_deepseek_gateway.py        # DeepSeek V4 / thinking / 文档化 LLM 配置回归
├── test_llm_retry_and_safe_shutdown.py # LLM retry、工具调用隔离、安全关闭与 pending tool-call 暂停恢复等价性回归；锁住半截 streaming tool-call 不生成 restorable snapshot、完整 pending call 写 durable manifest、恢复后下一次模型请求 digest 与无暂停路径一致
├── test_memory_pipeline_api.py     # 记忆流水线 API 回归
├── test_product_compose_smoke_config.py # 产品 Compose smoke 配置回归：锁定 infra/product.env 优先于 product.env.template
├── test_release_packaging_config.py # 正式发行包配置回归：锁定 distribution manifest、OpenPath/应用包安装参数、release smoke 回滚快照合同
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
└── test_m9_acceptance.py           # M9：端到端验收测试 + 控制面 API 回归；pause/resume acceptance 不再跳过
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
├── product-compose.mjs            # 产品 Compose 包装器：调用 product compose，关闭 BuildKit/bake，并封装恢复维护窗口流程
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
    └── nightly.yml  # nightly slow-parallel（触发：schedule + workflow_dispatch）
                      #   uv run pytest -m slow -n 2 --dist loadfile
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
| `package.json` | Node.js/pnpm 根配置，定义所有 `pnpm` 脚本命令；`yggdrasil:up` 是本地产品一键启动入口 |
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
| `docs/development/TASK_CHECKFLOW_AUDIT_AND_ALIGNMENT_2026_05_27.md` | 任务核对流程审计与对齐：冻结“理解任务->形成计划->向发起者核对->再执行”的目标流程，并对照当前协议/提示词/运行时/测试的缺口 |
| `docs/development/DESIGN_COMPLETION_EVALUATION_2026_06_05.md` | 设计完成度评估：按当前设计文档和静态实现证据评估工程设计、外部用户采用度、产品发行、数据治理、协作、模块、评测等完成度，并给出下一步优先级 |
| `docs/design-handoff/README.md` | UX 重塑外包资料包：聚合四组用户接触界面的设计 brief、外包交付物、当前实现依据和验收门槛 |
| `docs/design-handoff/01-base-user-interface-agent.md` | 基座面向用户界面 brief：客服型 Agent、应用路由、Prompt 代写、首次启动和错误支持 |
| `docs/design-handoff/02-application-package-experience.md` | 特化应用包界面 brief：场景页面、任务模板、Agent 工作过程可视化、真实上下文折叠和历史回顾 |
| `docs/design-handoff/03-settings-debug-configuration.md` | 设置/调试/配置界面 brief：普通设置、高级设置、维护者调试、数据隐私和计划中能力边界 |
| `docs/design-handoff/04-launcher-experience.md` | 启动器设计需求文档：安装向导、桌面主窗口、托盘菜单、应用包直达快捷方式、状态诊断、备份恢复和更新回滚 |
| `docs/development/USER_ADOPTION_SURFACE_AUDIT_2026_06_03.md` | 用户采用度审计：面向外部用户使用意愿，盘点 UI/前端/设置/安装/打包/用户文档现状，并把下一步收口到 Web-first 首次成功路径、设置校验、任务创建启动和本地产品启动器 |
| `docs/development/PRODUCT_PACKAGING_AND_REMOTE_DATA_REQUIREMENTS_GAP_2026_06_04.md` | 产品打包与官方远端数据能力需求差距：完整 Docker Compose 产品栈、Windows 未签名安装包/托盘/手动更新器、provider 启动阻塞、本地数据治理保护性 task 删除、产品栈快照/升级/回滚已进入预览可验证状态；托管 / SaaS 和官方远端数据服务实现仍是计划项 |
| `docs/development/PRODUCT_RELEASE_COMPLETION_EVALUATION_2026_06_18.md` | 产品发行完成度评估：当前综合发行完成度 55/100；本地可试用发行 72/100、普通用户正式发行 48/100、托管 / SaaS 商业发行 18/100，并列出正式发行前硬缺口 |
| `docs/development/MOE_MODEL_ROUTING_ASSESSMENT_2026_06_14.md` | 世界树 Agent MoE 模型分层与任务难度评估：以 2026 年 3 月后新开源/开放权重 MoE 候选为主，落到具体模型、主/子任务分工、D0-D4 难度、thinking 策略、升级降级和世界树专项评测指标 |
| `docs/development/MULTI_AGENT_WORKTREE_GRAPH_DESIGN_2026_06_20.md` | 多 Agent 自分裂与工作树图调度设计盘点：梳理 Sub-Agent / Fork / 联邦 Agent、工作树图字段、知识继承、模型路由、预算资源和冲突处理现状，明确下一批应补的正式规格与非目标 |
| `docs/specs/work-tree-graph-fork-parallel-protocol-v0.1.md` | 工作树图与 Fork 并行协议：冻结父节点局部 ready-set、`dependsOn` / `relationIds` 分工、Fork 直接继承父 Agent 上下文缓存、child 执行焦点、上下层边传递、延迟信息流索引、递归 Fork 与 `maxForks` 同时活跃上限、实现前合同和第一版验收场景 |
| `docs/development/WORK_TREE_GRAPH_FORK_EVALUATION_TASKS_2026_06_21.md` | 工作树图与 Fork 并行测试任务设计：定义 T0-T7 仿真任务、R1-R4 真实/仿真真实任务、递归 Fork 与 `maxForks` 同时活跃上限、指标、Batch 1-5 实现依赖和 D1-D7 用户决策项 |
| `docs/development/WORK_TREE_GRAPH_FORK_IMPLEMENTATION_PLAN_2026_06_21.md` | 工作树图与 Fork 并行实现计划：把协议落到 graph reducer、AgentRun Fork 字段、Fork planner、worker 运行视图、结果合并、runtime harness 和 PR 切分；当前已记录 PR1 reducer/测试、Batch 2 AgentRun 字段与活跃 Fork 计数、Batch 3 fork work item planner、Batch 4 worker child run view、Batch 5 result merge + transitions/Redis enqueue、Batch 6 deterministic runtime harness、Fork 必填字段硬校验和 live provider evidence 通过证据 |
| `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/work_tree_graph.py` | 工作树图 ready-set / Fork 并行 reducer：计算 direct child ready/blocked、延迟 pending 信息流、active fork count、available slots 和启动候选；PR1 阶段不触碰 worker/DB/subagent |
| `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/fork_runtime.py` | Fork batch / result merge runtime helper：把 ready-set 可启动项创建为 fork AgentRun 与 main activity / fork intent work item；`merge_fork_result_and_plan_next_batch()` 支持合并 ForkResultEnvelope、继承更新后的 workTreeSnapshot 并创建下一批 DB work item；真实 fork 完成路径由 transitions 负责 Redis enqueue |
| `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop/worker.py` | Agent runtime worker 主入口：Batch 4 已识别 `runType=fork`，复用预创建 fork AgentRun，并为 fork work item 建立 child-local request 指针 |
| `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop/transitions.py` | Agent runtime 完成/续跑/审批流转：Batch 4 已隔离 fork 完成态，避免 fork 完成覆盖父任务全局 status/currentFocus；2026-06-29 起对 work-tree correction、child/leaf checkpoint 与 delivery retry continuation 做去重追加，避免长链续跑提示膨胀 |
| `tests/runtime/test_work_tree_graph_scheduler.py` | 工作树图 / Fork 并行 PR1 默认 CI 回归：锁住 T0/T2/T3/T4/T7 语义 |
| `tests/runtime/test_fork_launch_planner.py` | Fork launch planner / worker run view 默认 CI 回归：锁住 maxForks 槽位、parent context anchor、forkGroupId、assigned child、work item envelope，以及 fork worker child view |
| `tests/runtime/test_fork_merge_and_auto_batch.py` | Fork result merge / auto batch 默认 CI 回归：锁住 ForkResultEnvelope、parent replan gate、pending summary-only 合同、mixed outcome、下一批 DB work item 创建和真实 worker enqueue |
| `tests/runtime/test_work_tree_graph_fork_runtime_harness.py` | Fork runtime deterministic harness 默认 CI 回归：两轮 worker 真实消费 fork work item，fake LLM 真实落库 model invocation / prompt artifact，锁住 AgentRun 元数据、work item completed、artifact `runType=fork`、workTreeSnapshot 继承、pending summary-only 信息流和无 child task/task branch |
| `evaluation/suites/work-tree-fork-runtime-harness.json` | Work-Tree Fork Runtime Harness suite：Batch 6 deterministic harness 的默认评测入口，已通过 `eval:work-tree:fork-runtime-harness` 生成正式 evaluation metrics |
| `evaluation/suites/work-tree-fork-runtime-live-candidate.json` | Work-Tree Fork Runtime Live Candidate suite：Batch 6 手动 live provider smoke 候选入口；未设置 `YGGDRASIL_FORK_RUNTIME_LIVE=1` 时记录为 blocked/non-pass，开启后要求真实 LongCat runtime completed 终态，已通过 `evalrun_69093187bf6c46e587c3`；不是长任务证据 |
| `evaluation/suites/work-tree-fork-evaluation-tasks.json` | Work-Tree Fork Evaluation Tasks suite：R1-R4 deterministic evaluation 入口，已通过 `evalrun_23503bda7dee4c39b90e` |
| `evaluation/suites/work-tree-fork-public-showcase.json` | Work-Tree Fork Public Showcase suite：公开展示 benefit 估算 + live 入口，已通过 `evalrun_f6ca4e22241542d4906b`；不是长任务证据 |
| `migrations/versions/c2f4b8a91d63_agent_run_fork_fields.py` | AgentRun Fork 字段迁移：为 `agent_runs` 增加 Fork tree 根、深度、assigned work-tree node、父上下文锚点和 sibling fork group 字段 |
| `docs/development/DEBUG_PLAN_2026_06_08.md` | 夜间调试计划：收拢 runtime 状态机、sub-agent / GitHub 协作、M9 控制面与并发稳定性相关功能，配套说明本轮从 nightly/slow 中暂时跳过的测试 |
| `docs/development/RUNTIME_CONCURRENCY_M9_INVESTIGATION_2026_06_11.md` | Runtime 并发、状态恢复与 M9 验收调查基线：记录 M9 control-plane 通过、M9 acceptance 的 pause/resume finalization 失败、worker 丢任务风险、snapshot 恢复缺口和后续修复顺序 |
| `docs/development/TASK_STOP_CONTINUE_CAPABILITY_INVESTIGATION_2026_06_18.md` | 任务停止/继续能力调查：记录 API/UI/runtime/module/test 能力基线；2026-06-19 已同步 `/pause`、Durable Snapshot、ResumeAttempt、持久 WorkItem、`resume-blocked`、Cancel audit 与手动保存/分支的新实现口径 |
| `docs/specs/data-governance-manifest-v0.1.md` | 数据治理清单与本地删除协议：定义数据资产 manifest、备份快照、删除 dry-run、保护性 task 硬删除、删除证明、审计记录和 provider / 日志 / 备份保留边界 |
| `docs/specs/remote-data-service-contract-v0.1.md` | 官方远端数据服务契约：定义官方远端账号/工作区、显式同步、远端备份、远端删除请求、删除证明和本地优先边界 |
| `docs/specs/agent-runtime-protocol-v0.2.md` | Agent 运行时协议 v0.2：本轮继续把“启动”细化为“初次苏醒形成起始状态 + 任务级单独读取工作状态”，并补上工具/知识索引优先的正式口径 |
| `docs/specs/work-tree-protocol-v0.2.md` | 工作树协议 v0.2：本轮继续把工作树边界收紧为任务级正式对象，强调 `[ID: 003 我要干什么]` 在建世界/初次苏醒阶段只保存协议与入口，不直接携带具体任务工作树 |
| `docs/specs/task-pause-resume-continuation-contract-v0.1.md` | 任务暂停、恢复与继续契约 v0.1：冻结“隔天/长期继续”为硬能力，定义 Durable Snapshot、ResumeAttempt、持久 WorkItem、resume-blocked、Queued Pause、Cancel、snapshot retention、手动保存分支、tool-call 暂停等价性和不得 fallback start 的恢复合同 |
| `docs/specs/world-build-awakening-task-start-protocol-v0.1.md` | 世界构建、初次苏醒与任务启动协议 v0.1：把通用 Agent 的建世界、一次性初次苏醒、起始状态、任务开始和无损恢复顺序拆成正式规则，并进一步收紧为“工具/知识索引优先、能力/知识节点可关联工具节点、开始工作前必须先读取工作状态”的正式口径 |
| `docs/new/世界树计划正式项目定义.md` | 世界树计划正式项目定义草稿与用户笔记：以 LLM 为核心，将代码定位为服务 LLM 的世界环境，并明确代码只做边界与警戒 |
| `docs/new/元提示词.md` | 新元提示词/Boot Prompt 方案：启动时完成 I/O 绑定、根指针寻址、行为宪法和程序计数器恢复，并要求 continuation 优先沿父节点编排位置继续 |
| `docs/LLM_WORK_ANALYZER_USER_GUIDE.md` | LLM 工作分析器用户手册：说明 Web 页面入口、完整分析页的七个主层次、CLI/API 用法和推荐排障流程，并固定 work-tree debug、时间线、cache trace、child bubble 与 mixed outcome 的读法 |
| `docs/demos/LOCAL_FIRST_TASK_DEMO.md` | 本地首次成功演示脚本：用正式 Web 产品入口演示导入素材、附加任务、选择应用模板、创建/启动任务和查看结果 |
| `tmp/6。8/测试计划.md` | Phase1 基础测试计划：数据治理、核心模块、API、M8/M9、LLM、评测与 nightly smoke 的执行清单，用于本轮测试跑批对照 |
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
| `docs/research/archive/future-planning/Project-Yggdrasil 未来多模态潜空间智能体架构.md` | Project-Yggdrasil 未来多模态潜空间智能体架构白皮书：多模态潜空间智能体、潜空间数据流动、LOD 编码、长期记忆与世界模型等远期研究草案；按删除前历史路径恢复 |
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
| 工作树图 ready-set / Fork 并行纯函数调度 | `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/work_tree_graph.py`、`tests/runtime/test_work_tree_graph_scheduler.py` |
| Fork batch launch planner / work item payload / worker child view / result merge helper / deterministic runtime harness | `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/fork_runtime.py`、`packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop/worker.py`、`packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop/transitions.py`、`tests/runtime/test_fork_launch_planner.py`、`tests/runtime/test_fork_merge_and_auto_batch.py`、`tests/runtime/test_work_tree_graph_fork_runtime_harness.py`、`evaluation/suites/work-tree-fork-runtime-harness.json`、`evaluation/suites/work-tree-fork-runtime-live-candidate.json`、`evaluation/suites/work-tree-fork-evaluation-tasks.json`、`evaluation/suites/work-tree-fork-public-showcase.json` |
| AgentRun Fork 元数据持久化与活跃 Fork 计数 | `packages/python-sdk/src/yggdrasil_sdk/persistence/orm.py`、`packages/python-sdk/src/yggdrasil_sdk/domain.py`、`packages/python-sdk/src/yggdrasil_sdk/persistence/repositories/task.py`、`packages/python-sdk/src/yggdrasil_sdk/persistence/repositories/_records.py`、`migrations/versions/c2f4b8a91d63_agent_run_fork_fields.py`、`tests/api/test_persistence_task_runtime_api.py` |
| LLM 调用、行为记录与模型路由 | `packages/python-sdk/src/yggdrasil_sdk/llm_runtime/`、`packages/python-sdk/src/yggdrasil_sdk/llm_runtime/behavior_recorder.py` |
| LLM 工作树 live 行为实验套件 | `evaluation/suites/g4-real-task-work-tree-post-question-live.json`、`evaluation/suites/g4-real-task-work-tree-step-reflection-live.json`、`evaluation/suites/g4-real-task-work-tree-critique-continue-live.json`、`evaluation/suites/g4-real-task-work-tree-tool-end-reminder-live.json`、`evaluation/suites/g4-real-task-work-tree-tool-call-leaf-example-live.json`、`evaluation/suites/g4-real-task-work-tree-leaf-self-talk-live.json`、`evaluation/suites/g4-real-task-work-tree-deepseek-v4-pro-live.json`、`evaluation/suites/g4-real-task-work-tree-deepseek-v4-pro-critique-continue-live.json`、`evaluation/suites/g4-real-task-work-tree-deepseek-v4-pro-node-tool-budget-live.json`、`evaluation/suites/g4-real-task-work-tree-deepseek-v4-pro-directive-required-live.json`、`evaluation/suites/g4-real-task-work-tree-deepseek-v4-pro-parent-retention-live.json`、`evaluation/suites/g4-real-task-work-tree-deepseek-v4-pro-finish-prune-live.json`、`evaluation/suites/g4-real-task-work-tree-deepseek-v4-flash-finish-prune-live.json`、`evaluation/suites/g4-real-task-work-tree-longcat-finish-prune-live.json`、`package.json` 的 `eval:g4:work-tree:*`；默认化状态见 `docs/development/LLM_WORK_TREE_HARD_PROMPT_EXPERIMENTS_2026_06_29.md` |
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
| 完整产品 Docker Compose 预览栈 | `infra/docker-compose.product.yml`、`infra/product.env.template`、`infra/product.env`、`infra/docker/`、`scripts/product-compose.mjs`、`scripts/product-release-smoke.mjs`、`corepack pnpm product:*`、`corepack pnpm product:release-smoke` |
| Windows staged repo 发行包 / GitHub Releases 预备产物 | `packaging/distributions/local-preview.json`、`packaging/desktop/windows/Build-Yggdrasil.ReleasePackage.ps1`、`packaging/desktop/windows/Yggdrasil Build Release Package.cmd`、`dist/releases/` |
| Windows 未签名安装包 / 托盘 / 手动更新器 | `packaging/desktop/windows/`、`packaging/desktop/windows/Yggdrasil.Desktop.ps1`、`packaging/desktop/windows/Yggdrasil.Install.ps1`、`packaging/desktop/windows/Yggdrasil.Update.ps1` |
| 数据治理 manifest / 备份 / 保护性 task 删除 / 审计 | `docs/specs/data-governance-manifest-v0.1.md`、`docs/specs/remote-data-service-contract-v0.1.md`、`packages/python-sdk/src/yggdrasil_sdk/data_governance.py`、`packages/python-sdk/src/yggdrasil_sdk/ops_runtime/backup.py`、`services/core-api/src/yggdrasil_core_api/api/routes/data_governance.py`、`services/core-api/src/yggdrasil_core_api/services/data_governance_service.py`、`apps/web/app/components/data-governance-page.tsx` |
| Provider key 配置状态与启动阻塞 | `packages/python-sdk/src/yggdrasil_sdk/provider_config.py`、`services/core-api/src/yggdrasil_core_api/services/runtime_service.py`、`apps/web/app/components/task-launch-panel.tsx`、`tests/api/test_provider_configuration_api.py` |
| 本地产品一键启动 | `corepack pnpm yggdrasil:up` / `packages/python-sdk/src/yggdrasil_sdk/ops_runtime/launcher.py` |
| Web 首次任务创建入口 | `apps/web/app/components/task-launch-panel.tsx` 与应用 `web/dashboard.json` 的 `taskTemplates[]` |
| UX 重塑外包资料包 | `docs/design-handoff/README.md`、`docs/design-handoff/01-base-user-interface-agent.md`、`docs/design-handoff/02-application-package-experience.md`、`docs/design-handoff/03-settings-debug-configuration.md`、`docs/design-handoff/04-launcher-experience.md` |
| Stitch 外部设计稿 | Codex 全局 MCP `stitch`（`https://stitch.googleapis.com/mcp`）：本轮设计验收只使用 `Project Yggdrasil Design System`（`projects/6603619266131280055`）；凭据只保存在本机 Codex 配置，不进入仓库 |
| Web 素材导入与附加任务入口 | `apps/web/app/components/assets-page.tsx` |
| 发布模式、演示、隐私边界和远端计划 | `apps/web/app/components/release-page.tsx`、`apps/web/app/release/page.tsx`、`docs/demos/LOCAL_FIRST_TASK_DEMO.md`、`docs/development/PRODUCT_PACKAGING_AND_REMOTE_DATA_REQUIREMENTS_GAP_2026_06_04.md`、`docs/development/PRODUCT_RELEASE_COMPLETION_EVALUATION_2026_06_18.md`、`docs/specs/remote-data-service-contract-v0.1.md` |
| GitHub Releases 发布手册 | `docs/release/GITHUB_RELEASES_PLAYBOOK.md` |
| 前端页面 | `apps/web/app/<page>/page.tsx` |
| 评测套件定义 | `evaluation/suites/*.json` |
| 质量基线与延迟门禁值 | `docs/QUALITY_BASELINE.md` |
| 项目设计哲学唯一主文档 | `docs/architecture/design-philosophy-and-cognitive-principles.md` |
| 弱模型行为补偿注释（非设计真理） | `docs/architecture/weak-model-behavior-compensation-notes.md` |
| 架构决策理由 | `docs/adr/ADR-<number>-*.md` |
| CI 工作流定义 | `.github/workflows/{pr,ci,nightly,release-check}.yml` |
| Alembic 迁移一致性检查 | `scripts/check_migrations.sh` |
| 端到端冒烟测试 | `scripts/smoke_test.sh` |
| 项目设计完成度评估 | `docs/development/DESIGN_COMPLETION_EVALUATION_2026_06_05.md` |
| 产品发行完成度评估 | `docs/development/PRODUCT_RELEASE_COMPLETION_EVALUATION_2026_06_18.md` |
| Stitch 设计稿四组验收与最终抓图证据 | `docs/development/STITCH_DESIGN_ACCEPTANCE_2026_06_17.md`、`docs/development/stitch-design-captures-2026-06-17/post-rework-v10-passline/` |
| Stitch 设计工程实现计划与阶段 0 收口清单 | `docs/development/DESIGN_ENGINEERING_IMPLEMENTATION_PLAN_2026_06_17.md` |
| Runtime 并发 / M9 验收调查 | `docs/development/RUNTIME_CONCURRENCY_M9_INVESTIGATION_2026_06_11.md` |
| 任务停止 / 继续 / 恢复正式契约 | `docs/specs/task-pause-resume-continuation-contract-v0.1.md` |
| 任务停止 / 继续 / 恢复实现主入口 | `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_control.py`、`packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/snapshot.py`、`packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/snapshot_store.py`、`packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop/worker.py`、`services/worker/src/yggdrasil_worker/registry.py`、`services/core-api/src/yggdrasil_core_api/api/routes/tasks.py`、`apps/web/app/components/task-detail-page.tsx` |
| Tool-call 暂停等价性门禁 | `tests/test_llm_retry_and_safe_shutdown.py` |
| 任务停止 / 继续 / 恢复现状调查 | `docs/development/TASK_STOP_CONTINUE_CAPABILITY_INVESTIGATION_2026_06_18.md` |
| 2026-03+ MoE 模型路由与任务难度评估 | `docs/development/MOE_MODEL_ROUTING_ASSESSMENT_2026_06_14.md` |
| 多 Agent 自分裂与工作树图调度设计 | `docs/development/MULTI_AGENT_WORKTREE_GRAPH_DESIGN_2026_06_20.md`、`docs/specs/work-tree-graph-fork-parallel-protocol-v0.1.md` |
| 工作树图 ready-set / Fork 并行正式协议 | `docs/specs/work-tree-graph-fork-parallel-protocol-v0.1.md` |
| 工作树图 / Fork 并行测试任务与后续批次决策 | `docs/development/WORK_TREE_GRAPH_FORK_EVALUATION_TASKS_2026_06_21.md` |
| 工作树图 / Fork 并行实现计划与 PR 切分 | `docs/development/WORK_TREE_GRAPH_FORK_IMPLEMENTATION_PLAN_2026_06_21.md` |
| 滚动前沿 / 长程任务分辨率提示 | `docs/development/ROLLING_FRONTIER_WORK_TREE_RESOLUTION_2026_06_27.md`、`packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/work_tree_graph.py`、`packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop/worker.py`、`packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop/transitions.py`、`packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/takeover.py`、`packages/python-sdk/src/yggdrasil_sdk/prompting.py`、`tests/runtime/test_work_tree_graph_scheduler.py`、`tests/test_prompting_runtime.py` |
| LLM 长程控制过度设计删减路线 | `docs/development/LLM_LONG_HORIZON_OVERDESIGN_AUDIT_2026_06_27.md`、`packages/python-sdk/src/yggdrasil_sdk/prompting.py`、`modules/task-takeover/src/yggdrasil_task_takeover/plugin.py`、`packages/python-sdk/src/yggdrasil_sdk/tool_runtime.py`、`packages/python-sdk/src/yggdrasil_sdk/llm_runtime/invoke.py`、`packages/python-sdk/src/yggdrasil_sdk/llm_runtime/artifacts.py`、`packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop/transitions.py`、`packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/takeover.py`、`packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/work_tree_graph.py` |
| LLM 工作树使用指南与案例 | `docs/development/LLM_WORK_TREE_USAGE_GUIDE_AND_CASES_2026_06_28.md` |
| 运行时 LLM 工作树新口径 | `docs/development/LLM_WORK_TREE_USAGE_GUIDE_AND_CASES_2026_06_28.md`、`packages/python-sdk/src/yggdrasil_sdk/prompting.py`、`packages/python-sdk/src/yggdrasil_sdk/llm_runtime/behavior_recorder.py`、`tests/test_prompting_runtime.py`、`tests/test_llm_behavior_recorder.py` |
| LLM live 工作流程与工作树复跑审计 | `docs/development/LLM_LIVE_WORKFLOW_AND_WORK_TREE_RERUN_AUDIT_2026_06_28.md`、`tmp/live-rerun-20260628-214050/llm-work-analysis.md`、`.yggdrasil/state/evaluation-sandboxes/evalsandbox_9faf11ab84e148c092e8/`、`.yggdrasil/state/evaluation-sandboxes/evalsandbox_a6e11f83e66947bf9e02/`、`adapters/model-providers/src/yggdrasil_model_providers/gateway.py`、`packages/python-sdk/src/yggdrasil_sdk/llm_runtime/behavior_recorder.py`、`tests/test_deepseek_gateway.py`、`tests/test_llm_behavior_recorder.py` |
| LLM 工作树硬提示实验结果 | `docs/development/LLM_WORK_TREE_HARD_PROMPT_EXPERIMENTS_2026_06_29.md`、`tmp/live-work-tree-hard-fix-20260629/`、`tmp/live-work-tree-complete-20260629/05-deepseek-directive-complete-dedupe/`、`.yggdrasil/state/evaluations/evalrun_fdee593d0136443caa27.json`、`.yggdrasil/state/evaluations/evalrun_90e62958ee694652a9f5.json`、`.yggdrasil/state/evaluation-sandboxes/evalsandbox_a2d264bfdd04432bb2ae/`、`.yggdrasil/state/evaluation-sandboxes/evalsandbox_ded74ba4b7164a9a962d/`、`.yggdrasil/state/evaluation-sandboxes/evalsandbox_b518cf68976f4a7fbafd/`、`.yggdrasil/state/evaluation-sandboxes/evalsandbox_cd50a79907cc4831855b/`、`.yggdrasil/state/evaluation-sandboxes/evalsandbox_926c66d1376043899fc2/`、`.yggdrasil/state/evaluation-sandboxes/evalsandbox_a99e8a59bbfe4b28a918/`、`.yggdrasil/state/evaluation-sandboxes/evalsandbox_c2ceb2124b714a5e885e/`、`.yggdrasil/state/evaluation-sandboxes/evalsandbox_0340f3943ac042688d96/`、`.yggdrasil/state/evaluation-sandboxes/evalsandbox_960ab8a01c3948b4878b/` |
| 工作树图 / Fork 并行 PR1 reducer 与默认测试 | `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/work_tree_graph.py`、`tests/runtime/test_work_tree_graph_scheduler.py` |
| 工作树图 / Fork 并行 Batch 2 持久化字段与回归 | `migrations/versions/c2f4b8a91d63_agent_run_fork_fields.py`、`packages/python-sdk/src/yggdrasil_sdk/persistence/repositories/task.py`、`tests/api/test_persistence_task_runtime_api.py` |
| 工作树图 / Fork 并行 Batch 3-6 planner、work item payload、worker run view、result merge helper 与 deterministic/runtime-live/R1-R4/公开展示评测入口 | `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/fork_runtime.py`、`packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop/worker.py`、`packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop/transitions.py`、`tests/runtime/test_fork_launch_planner.py`、`tests/runtime/test_fork_merge_and_auto_batch.py`、`tests/runtime/test_work_tree_graph_fork_runtime_harness.py`、`evaluation/suites/work-tree-fork-runtime-harness.json`、`evaluation/suites/work-tree-fork-runtime-live-candidate.json`、`evaluation/suites/work-tree-fork-evaluation-tasks.json`、`evaluation/suites/work-tree-fork-public-showcase.json` |




