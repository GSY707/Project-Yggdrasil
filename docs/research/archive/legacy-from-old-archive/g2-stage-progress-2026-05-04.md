# 世界树计划 · G2 阶段推进记录（2026-05-04）

> 归档说明：本文档已归档。当前以 `docs/research/g2-closeout-2026-05-15.md` 作为 Gate 2 正式闭环结论。

> 目的：承接 G1 闭合结果，持续跟踪 Gate 2（受控自治）能力达成情况。

补充说明：当前的正式闭环结论见 `g2-closeout-2026-05-15.md`；原始差距分析已归档到 `归档/g2-gap-assessment-2026-05-04.md`。

---

## 1. 当前判定

- G1：已闭合（在 `deepseek_direct / deepseek-v4-pro` 下完成 2026-05-15 官方复跑，`YGG-CI-01`、`YGG-CG-01`、`YGG-CG-03` 全部验收通过）。
- G2：已闭合（同一 provider 配置下完成 1 轮全量 + 2 轮稳定性复跑；`YGG-CG-01` / `YGG-CG-03` 连续 3 轮全部通过，人工接管中位数 0，用户澄清回合中位数 0，恢复成功率 100%，`corepack pnpm eval:g2:regression` 通过）。

当前已可从评分表直接生成 G2 基线摘要（`pilot-scorecard summarize`）：

- 现有样本数：7
- 总体验收通过率：100%
- 人工接管中位数：0
- 用户澄清回合中位数：0
- 计划质量样本数：0（schema 与汇总已支持，当前冻结样本未回填）
- `YGG-CG-01` 平均总分：100
- `YGG-CG-03` 平均总分：97.67
- 恢复成功率：100%
- 真实供应商调用样本数：7（官方复跑 3 轮，共 7 条 live scorecard 行）

上述结果已经覆盖 Gate 2 所要求的“同一批窄路径任务重复执行”与“真实任务卡任务级资产”证据，当前可作为正式闭环基线。

本轮正式证据文件：

- `evaluation/fixtures/real-user-validation/live-task-pack-g2-r2.json`
- `evaluation/fixtures/real-user-validation/live-task-pack-g2-r3-stability.json`
- `evaluation/fixtures/real-user-validation/live-task-pack-g2-r4-stability.json`
- `evaluation/fixtures/real-user-validation/scorecard-2026-05-15-g2-complete.csv`

Gate 2 出口标准（来自路线图）：

1. 同一批窄路径任务重复执行时，验收通过率稳定，人工接管中位数下降。
2. 用户澄清回合显著减少，技术选型不再依赖用户驱动。
3. 大文件/复杂文件拆分进入固定回归集，而不是临时任务。

---

## 2. 阻塞项清理状态（承接 G1 Top 5）

| # | 阻塞项 | 分类 | 当前状态 | 证据 |
|---|---|---|---|---|
| 1 | 沙箱初始化需手动执行 `real-user:prepare` | 配置 | 已部分清理 | `ops_runtime.py` 已输出 `activationCommands`，降低路径/命令拼接摩擦；仍未 CI 自动化 |
| 2 | eval 依赖外部 LLM API，超时导致不稳定 | 速度 | 已部分清理 | `gateway.py` 已支持 429/5xx 指数退避重试 |
| 3 | safe-stop 快照纯文本，resume 需人工比对 | 体验 | 已清理 | `SafeShutdownInterrupt` + `pending-tool-calls` 快照恢复链路 |
| 4 | `word_count` 对中文统计偏差 | 能力 | 已部分清理 | `support.py` 新增统一 `estimate_word_count()` 口径与回归测试；试跑复跑仍需验证实际采用情况 |
| 5 | Windows 中文路径下 `-c` 输出截断 | 配置 | 已清理 | `mcp_servers/python_server.py` 已切到临时 `.py` 文件执行，规避 `python -c` + Unicode 路径问题 |

---

## 3. 本轮已落地能力

- LLM 调用新增指数退避重试：支持 429/5xx，环境变量可调重试次数和 backoff。
- Worker 支持安全关闭信号：`SIGTERM` / `SIGINT` 触发 graceful shutdown。
- 在 tool-call 执行前支持“安全中断并保存”：保存 `pending-tool-calls` 检查点。
- 下次恢复时自动续跑未执行 tool-call，继续 Agent 循环。
- 新增跨平台脚本：`scripts/safe_shutdown.sh` 与 `scripts/safe_shutdown.ps1`。
- 新增 G2 指标汇总能力：`pilot-scorecard summarize --csv <scorecard.csv>` 可直接统计通过率、接管中位数、澄清回合、恢复率，以及计划质量 / 返工次数 / 返工率的样本覆盖与汇总值。
- 新增统一 CJK `word_count` 口径工具：`estimate_word_count()`，避免中文被 `split()` 低估。
- 新增正式任务接管协议：`task-takeover` 模块已接入主循环、Prompt 元数据、执行记录和独立工件，开始正式产出 objective / constraints / plan / delivery / verification / metrics。
- 运行入口已统一自动加载仓库根 `.env`，`evaluation_cli`、`ops_cli` 与服务/worker main 入口不再依赖手工导环境。
- 修复 `YGGDRASIL_STATE_ROOT` 示例配置，live suite 工件重新落回标准目录 `.yggdrasil/state/`。
- `eval:m8:live` 已在标准目录通过，正式 runId 为 `evalrun_fa0009a3cb4140449737`，证明 live smoke 真实性已恢复。
- 新增 G2 固定回归套件：`evalsuite_regression_g2_controlled_autonomy` / `corepack pnpm eval:g2:regression`，覆盖 `persistence/repositories/` 与 `core-api services/` 复杂文件拆分样本，检查旧 monolith 不复活、拆分子文件行数、路由层 Service 边界和文档同步。

---

## 4. G2 后续非阻塞动作

1. 在后续样本中补录 `planQualityScore0_100`、`reworkCount`、`reworkRate`，把 Gate 2 评分口径从“结果闭环”扩展到“过程质量可比较”。
2. 持续把 `corepack pnpm eval:g2:regression` 纳入 nightly 或发布前检查，避免复杂文件拆分能力回退成一次性人工修复。
3. 补齐首 token / 首次有效输出级别的首响观测，作为后续 Gate 3 的速度基线。
4. 如需扩展 provider，对照当前 `deepseek_direct / deepseek-v4-pro` 基线补录 provider 可用性矩阵，而不是覆盖现有闭环证据。

---

## 5. 风险与约束

- 外部 LLM API 不稳定仍是主要不确定性，当前通过重试降低波动，但不能替代本地可控评测样本。
- 真实 provider 任务包复跑会把隔离仓库和任务材料发送到外部模型服务；执行前必须获得对该外部传输的明确批准。
- 当前官方复跑已完成并形成 supplier-side 调用证据，但 provider 波动、额度和上下文预算仍是后续扩大样本时的运营风险。
- G2 以“稳定复现”为主，不建议在出口标准前并行扩展新场景面。
- 所有试跑保持专用沙箱隔离，禁止回写工程仓库。
