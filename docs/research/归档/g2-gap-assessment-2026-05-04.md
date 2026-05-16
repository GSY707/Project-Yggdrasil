# 世界树计划 · Gate 2 差距测试与成因分析（2026-05-04）

> 目的：基于当前仓库的实际测试结果、现有实现与文档状态，判断项目距离 Gate 2（受控自治）还差什么，为什么会产生这些差距，以及如何以最短路径达到 Gate 2 标准。

---

## 1. 本次测试范围

本次结论以“当前仓库现状 + 当场执行验证”为依据，而不是沿用旧结论。

### 1.1 当场执行的验证

1. `uv run pytest -q`
   - 结果：`102 passed, 102 warnings in 114.41s`
   - 结论：Python 主体功能当前处于健康状态，新增 G2 相关改动未破坏回归。
2. `corepack pnpm web:typecheck`
   - 结果：通过
   - 结论：前端类型层当前无新增阻塞。
3. `corepack pnpm eval:regression`
   - 结果：`3/3 passed`, `passRate = 1.0`
   - 结论：M4-M6 基础回归稳定。
4. `corepack pnpm real-user:scorecard --csv .\evaluation\fixtures\real-user-validation\scorecard-2026-05-04.csv`
   - 结果：
     - 样本数：3
     - 总体验收通过率：100%
     - 人工接管中位数：0
     - 用户澄清回合中位数：0
       - 计划质量样本数：0
       - 返工次数样本数：0
       - 返工率样本数：0
     - 恢复成功率：100%
    - 结论：当前可生成 G2 基线摘要，且 scorecard 已支持计划质量 / 返工指标汇总；但冻结样本尚未回填这些列，样本量也仍不足以证明 Gate 2 已闭合。
5. `corepack pnpm eval:m8:live`
   - 结果：`2/2 passed`
   - runId：`evalrun_fa0009a3cb4140449737`
   - 结论：当前环境已经恢复真实 live provider 调用能力；当前剩余缺口切换为“真实任务卡尚未在同一 provider 下重跑”。

### 1.2 本次检查的仓库维度

- G2 路线定义与出口标准：`docs/research/final-goal-roadmap-2026-04-30.md`
- 当前阶段与待办：`todo.md`
- 当前 G2 推进状态：`docs/research/归档/g2-stage-progress-2026-05-04.md`
- 性能与质量基线：`docs/QUALITY_BASELINE.md`
- 运行时与提示词实现：`packages/python-sdk/src/yggdrasil_sdk/`、`applications/`
- 真实用户验证材料：`evaluation/fixtures/real-user-validation/`

---

## 2. Gate 2 标准

根据路线文档，Gate 2 的目标不是“再做更多功能”，而是把窄路径闭环产品化为“受控自治”。

### 2.1 Gate 2 能力定义

1. 固化任务接管协议：目标解析、约束抽取、计划生成、执行、验证、交付。
2. 把大文件 / 复杂文件拆分做成正式能力，而不是临场发挥。
3. 明确 Sub-Agent 可见性策略，默认隐藏内部实现细节，只在风险升级、权限申请或结果合并时露出。
4. 交付阶段有稳定模板，至少区分结果、验证证据、待确认项、未完成项。
5. 正式采集“首次有效输出、计划质量、返工率、人工接管、澄清回合”等指标。

### 2.2 Gate 2 出口标准

1. 同一批窄路径任务重复执行时，验收通过率稳定，人工接管中位数下降。
2. 用户澄清回合显著减少，技术选型不再依赖用户驱动。
3. 大文件 / 复杂文件拆分进入固定回归集，而不是临时任务。

---

## 3. 当前项目距离 Gate 2 的差距

### 3.1 差距矩阵

| 项目 | 当前状态 | 判定 |
|------|------|------|
| 项目总体健康度 | `pytest 102 passed`、`web:typecheck` 通过、`eval:regression 3/3` 通过，且 `eval:m8:live 2/2 passed` | **工程健康，live smoke 已恢复** |
| G2 基线摘要能力 | 已支持从 scorecard 汇总通过率、接管中位数、澄清回合、恢复率，以及计划质量 / 返工率样本覆盖 | **已具备基础工具** |
| 真实 LLM 供应商调用证据 | `eval:m8:live` 已恢复真实 provider 调用，但 3 张任务卡尚未重跑 | **部分达成** |
| 重复执行证据 | 仅有 3 条试跑记录，且 `YGG-CG-01` / `YGG-CG-03` 各仅 1 次 | **未达标** |
| 澄清回合正式口径 | 已有 `user_clarification_rounds` 字段和汇总逻辑 | **已具备口径，但样本不足** |
| 任务接管协议 | 已有正式 contracts、task-takeover 模块、主循环接线与 Prompt/工件注入，并已进入 scorecard schema / 汇总 CLI；但重复执行样本与更多场景覆盖仍不足 | **部分达成** |
| 交付模板 / 自检模板 | Prompt profile 已补规则，但无独立模板资产与运行时约束 | **部分达成** |
| Sub-Agent 可见性策略 | Prompt profile 已补约束，但缺正式运行时策略与专项验证 | **部分达成** |
| 复杂文件拆分正式能力 | 已新增 `evalsuite_regression_g2_controlled_autonomy` / `corepack pnpm eval:g2:regression`，固定检查 repositories 与 core-api services 两个真实拆分样本 | **已达标** |
| Core API 性能实测 | `QUALITY_BASELINE.md` 已有 HTTP P50/P95 实测 | **已达成** |
| 首 token / 首响观测 | TODO 仍显示缺失，仓库中未见正式采集实现 | **未达标** |
| 计划质量 / 返工率 | 已有正式协议字段、scorecard 列与汇总逻辑；当前冻结样本未回填，自动采集仍待补 | **部分达成** |

### 3.2 直接证据

#### A. 重复执行证据不足

- 当前 scorecard 只有 3 条记录，见 `evaluation/fixtures/real-user-validation/scorecard-2026-05-04.csv`。
- 当前 G2 进展文档已明确指出“当前基线不能替代同一批窄路径任务重复执行证据”，见 [docs/research/归档/g2-stage-progress-2026-05-04.md](docs/research/归档/g2-stage-progress-2026-05-04.md#L12)。
- 当前 TODO 第 1 项仍是“连续 3 轮重复执行 `YGG-CG-01` + `YGG-CG-03`”，见 [todo.md](todo.md#L45)。

#### A-1. 真实 LLM 调用证据已经恢复到 smoke 级

- 运行入口已自动加载仓库根 `.env`，`eval:m8:live` 不再依赖手工导环境。
- 正式成功 run 为 `evalrun_fa0009a3cb4140449737`，`2/2 passed`。
- task case 与 tool case 都落下了 `provider=longcat`、`model=LongCat-Flash-Lite` 的真实调用记录。
- 当前缺口不再是“没有 supplier-side 记录”，而是“真实任务卡缺少同批 live 复跑资产”。

#### B. 任务接管协议已进入正式实现，评分链已打通到 scorecard 汇总

- 路线文档明确要求固化“目标解析、约束抽取、计划生成、执行、验证、交付”，见 [docs/research/final-goal-roadmap-2026-04-30.md](docs/research/final-goal-roadmap-2026-04-30.md#L168)。
- 当前仓库已新增正式协议对象与实现链路：
   - `contracts.py` 中新增 `TaskTakeoverProtocol` 及相关对象。
   - `modules/task-takeover/` 提供 `task.takeover.*` hook 实现。
   - `runtime_kernel/execution_loop.py` 已在 prompt 编译前生成协议、在执行记录前完成验证与落盘。
   - `prompting.py` 与 LLM request transcript 已携带 `takeoverProtocol`。
- 当前剩余缺口不再是“没有实现”，而是“现有冻结样本尚未回填计划质量 / 返工率，且重复执行证据仍不足”。

#### C. 复杂文件拆分能力已进入正式回归

- 实际代码形态显示 `repositories` 和 `services` 已经按子包拆分，而不是单个大文件：
  - `packages/python-sdk/src/yggdrasil_sdk/persistence/repositories/`
  - `services/core-api/src/yggdrasil_core_api/services/`
- 实际拆分后关键文件规模：
  - `runtime_kernel/execution_loop.py`：584 行
  - `runtime_kernel/snapshot.py`：277 行
  - `evaluation_runtime/bootstrap.py`：439 行
  - `evaluation_runtime/scorer.py`：251 行
  - `evaluation_runtime/suite_runner.py`：130 行
  - `task_service.py`：119 行
  - `memory_service.py`：472 行
  - `repositories/task.py`：250 行
  - `repositories/memory.py`：404 行
- 当前已新增 `evaluation/suites/g2-regression.json`，并通过 `g2.complex_file_split_regression` 场景固定验证：
  - 旧 `repositories.py` / `services.py` monolith 不复活。
  - 拆分子文件保持在 600 行以内。
  - API route 层不绕过 Service 直接导入 Repository。
  - TODO / 技术债文档持续承认该能力是固定回归，而不是一次性拆包。

#### D. 观测指标仍有关键空洞

- `QUALITY_BASELINE.md` 已有 Core API HTTP P50/P95 实测，见 [docs/QUALITY_BASELINE.md](docs/QUALITY_BASELINE.md#L66)。
- `scorecard` 已有 `first_useful_output_at` / `first_useful_output_seconds` 字段，见 `evaluation/fixtures/real-user-validation/scorecard-2026-05-04.csv` 首行。
- TODO 仍显示“补首 token / 首次有效输出级别的首响观测”为未完成，见 [todo.md](todo.md#L37)。
- 当前仓库已支持 `human_takeover_count`、`user_clarification_rounds`、`plan_quality_score_0_100`、`rework_count`、`rework_rate` 的汇总，见 `ops_runtime.py` 中 `summarize_real_user_scorecard()`。
- 但当前冻结 scorecard 样本尚未回填计划质量 / 返工字段，且尚未见“首 token latency”的正式采集实现。

---

## 4. 为什么会产生这些差距

### 4.1 先闭 G1 的策略导致 G2 的“产品化能力”延后

当前仓库的演进路径是先把 G1 闭合，再转向 G2。这个策略本身是合理的，因为 G1 关注“能做成”，G2 才关注“能稳定复现”。

后果是：

- 仓库中先落地的是恢复链路、试跑隔离、评分表、证据闭环、LLM 重试、安全关闭等“先保证任务能跑通”的基础设施。
- G2 需要的“任务接管协议”“正式交付模板”“复杂文件拆分评测化”“计划质量指标”等，则被推迟到 G1 闭合之后。

这不是工程失控，而是阶段性取舍的自然结果。

### 4.2 当前仓库存在“实现先于看板更新”的文档漂移

本次检查发现，至少两项技术债在实际代码层已经完成拆包，但 TODO / 反技术债文档仍保持旧描述：

- `repositories.py` 实际上已经拆成 `repositories/` 子包。
- `core-api services.py` 实际上已经拆成 `services/` 子包。

这会造成两个误判：

1. 让人以为 G2 最大缺口还是“单纯的大文件还没拆”。
2. 掩盖了真正更关键的缺口：拆分虽然做过，但没有变成“正式能力 + 回归任务 + 评测入口”。

### 4.3 当前指标体系是“能记账”，还不是“能判质”

现在已经具备：

- 完成率
- 接管次数
- 澄清回合数
- 恢复成功率
- 首次有效输出时间
- HTTP P50/P95

但 Gate 2 想证明的是“受控自治”，这需要的不只是结果数据，还需要更接近“自治质量”的指标，例如：

- 计划质量是否稳定
- 技术选型是否还依赖用户推动
- 返工率是否下降
- 复杂文件拆分后的语义与文档一致性是否稳定

这些指标当前缺失，所以即便现有分数很好，也还不能证明 Gate 2 闭合。

### 4.4 当前样本量太小，不足以证明“稳定复现”

当前 scorecard 结果看起来非常好：通过率 100%、接管中位数 0、澄清回合中位数 0、恢复成功率 100%。

问题在于样本只包含：

- YGG-CI-01：1 次
- YGG-CG-01：1 次
- YGG-CG-03：1 次

这只能证明“在这一轮能成功”，不能证明“同一批任务多次重复时仍稳定”。这正是 G2 和 G1 的根本区别。

---

## 5. 当前项目与 G2 的真实关系

### 5.1 已经达到的部分

1. **项目整体健康度足够支撑冲 G2**
   - 回归测试通过
   - 前端类型检查通过
   - 基础评测回归通过
2. **G2 的基础设施已经有了**
   - scorecard 汇总
   - 澄清回合口径
   - CJK `word_count` 工具
   - safe-stop / resume 自动恢复
   - LLM 指数退避重试
   - Windows Unicode 路径执行修复
3. **Prompt 侧已开始收敛到 G2 约束**
   - 限制无意义澄清
   - 要求交付时区分结果 / 证据 / 待确认项 / 未完成项
   - Sub-Agent 默认隐藏内部实现细节

### 5.2 尚未达到的部分

1. **没有重复执行的稳定性证据**
2. **任务接管协议虽已进入评分链，但尚未积累足够正式样本**
3. **复杂文件拆分固定回归集已补齐，但仍需持续执行**
4. **没有完整的 G2 质量指标体系**
5. **文档/待办与实际代码状态存在漂移，影响判断与排程**

因此，当前项目状态应定义为：

> **工程主体健康，live smoke 真实性已恢复，已具备继续冲 Gate 2 的基础条件；但真实任务卡的 live 复跑证据尚未补齐，因此 G1 仍需最终复核，Gate 2 也尚未闭合。**

---

## 6. 如何达到 G2 标准

### 6.1 最短达标路径

如果目标是尽快达到 Gate 2，而不是顺手做一堆未来工作，最短路径是下面 4 步。

#### 第 1 步：补齐真实任务卡与重复执行证据

目标：闭合 G2 出口标准第 1、2 条所需的最小样本。

动作：

1. 先在同一 live provider 配置下重跑 `YGG-CI-01`、`YGG-CG-01`、`YGG-CG-03`。
2. 再连续 3 轮重复执行 `YGG-CG-01` 和 `YGG-CG-03`。
3. 每轮都记录到同一 scorecard 体系中，并输出汇总结果。

验收：

- 至少新增 6 条记录（3 轮 × 2 任务）。
- 可直接生成：
  - 通过率
  - 人工接管中位数
  - 用户澄清回合中位数
  - 恢复成功率
- 能回答“是否稳定复现”，而不是只回答“曾经成功过”。

#### 第 2 步：把任务接管协议接入评分链与更宽场景

目标：把已经落地的协议层，从“代码里存在”推进到“能被评分、能被复跑、能跨场景复用”。

动作：

1. 在后续重复执行样本中正式填写 `planQualityScore0_100`、`reworkCount`、`reworkRate`，并保持 scorecard 汇总持续输出。
2. 为 coding 窄路径至少补 1 组“协议存在性 + 评分存在性 + 交付完整性”回归样本。
3. 把该协议扩展到除 base app 外的 coding-greenfield / software-factory 主路径。

验收：

- 至少一个 coding 窄路径任务完整走通这 6 个阶段并被 scorecard 记录。
- 能输出结构化计划与交付摘要。
- 能分离“未确认项”和“未完成项”。

#### 第 3 步：把复杂文件拆分能力正式化（已落地）

目标：闭合 G2 出口标准第 3 条。

动作：

1. 不再把“拆分大文件”仅视为技术债，而是视为正式任务类型。
2. 选择一个真实大文件作为样本，建立：
   - 输入任务卡
   - 验收条件
   - 定向测试
   - 回归入口
3. 至少让一个真实样本进入固定回归集。

验收：

- 仓库中已出现固定回归任务，而不是手工一次性拆分。
- 能验证拆分后的：
  - 语义一致性
  - 测试通过率
  - 文档一致性

#### 第 4 步：补齐 G2 缺失指标

目标：让 Gate 2 的“稳定复现”可被量化证明。

动作：

1. 正式定义并采集：
   - 首 token latency
   - 首次有效输出
   - 计划质量（schema 已就绪，需形成真实样本与自动回填）
   - 返工率（schema 已就绪，需形成真实样本与自动回填）
2. 把现有 scorecard、运行时事件、质量基线连接起来。
3. 回写 `QUALITY_BASELINE.md` 与 G2 进展文档。

验收：

- 观测不再只停留在“总完成时间 + 主观打分”。
- 可以解释任务失败到底来自：
  - 模型
  - 环境
  - 工具
  - 接管协议
  - 计划质量

---

## 7. 建议的优先级顺序

### P0：必须先做

1. 连续 3 轮复跑 `YGG-CG-01` + `YGG-CG-03`
2. 固化 scorecard 汇总与基线报告
3. 修正文档漂移，避免继续拿过时待办当现状

### P1：直接决定能否闭 G2

1. 显式任务接管协议 + 评分样本沉淀
2. 复杂文件拆分固定回归集
3. 首响 / 计划质量 / 返工率指标

### P2：可在 G2 后继续做

1. 扩大到更多场景
2. 应用插件 few-shot 全面补齐
3. 更大范围的大文件拆分
4. PostgreSQL CI 层

---

## 8. 最终判断

### 当前结论

- 当前项目**不是**离 Gate 2 很远。
- 当前项目也**还没有**达到 Gate 2。
- 当前状态最准确的描述是：

> **基础设施已基本具备，复杂文件拆分回归化已落地；核心缺口集中在“重复执行证据”“任务接管样本沉淀”“G2 指标体系完整化”三项。**

### 是否可以继续冲 G2

可以，而且现在正是适合冲 G2 的时间点。

原因：

1. 基础回归和评测状态是健康的。
2. G1 已闭合，不再需要继续为“能否交付”兜底。
3. 当前最关键的差距已被明确定位，不再模糊。
4. 剩余工作量主要是“产品化与证据化”，而不是重新造底座。

### 什么时候可以宣告 G2 达标

只有当下面三件事同时发生时：

1. `YGG-CG-01` / `YGG-CG-03` 形成 3 轮以上重复执行样本，并显示稳定通过率与低接管中位数。
2. 至少一个复杂文件拆分任务进入固定回归集。当前已由 `evalsuite_regression_g2_controlled_autonomy` 覆盖，后续需持续纳入复跑清单。
3. 任务接管协议与关键观测指标变成正式实现，而不是仅停留在 Prompt / TODO / 口头约定层。

在此之前，项目状态应保持为：

> **Gate 2 进行中，尚未闭合。**
