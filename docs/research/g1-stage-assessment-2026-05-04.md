# 世界树计划 · G1 阶段闭合评估报告（2026-05-04）【待真实任务复核】

> 评估目的：依据最新自动化测试与内部试跑证据，判定 Gate 1（G1）是否已经达到闭合标准。  
> 判定依据：`docs/research/final-goal-roadmap-2026-04-30.md` 中 Gate 1 出口标准。  
> **当前结论：原“Gate 1 已闭合（4 / 4）”声明已暂停，状态改为“待真实任务复核”。**  
> 原判定时间：2026-05-04T02:58:37Z  
> 复核更新时间：2026-05-04T03:49:06Z

> 复核说明：当前 `eval:m8:live` 已在标准状态目录通过，正式 runId 为 `evalrun_fa0009a3cb4140449737`，说明 live provider 与 supplier-side 调用证据已经恢复。当前剩余问题不再是“打不到真实供应商”，而是“`YGG-CI-01` / `YGG-CG-01` / `YGG-CG-03` 尚未在同一 live provider 下重跑并补齐任务级资产”。

---

## 1. 本次执行与测试结果

### 1.1 自动化测试

1. `uv run pytest -q`
   - 结果：`102 passed, 102 warnings in 114.41s`
2. `corepack pnpm eval:regression`
   - 结果：`3/3 passed`，`passRate = 1.0`
   - runId：`evalrun_b60f0e2b6d794b2b86c7`
3. `corepack pnpm eval:m9:control-plane`
   - 结果：`2/2 passed`，`passRate = 1.0`
   - runId：`evalrun_5390076e022e4e55a274`
4. `corepack pnpm eval:m8:live`
   - 结果：`2/2 passed`，`passRate = 1.0`
   - runId：`evalrun_fa0009a3cb4140449737`

### 1.2 G1 前置能力复核

5. `corepack pnpm real-user:prepare`
   - 结果：成功创建专用沙箱，`workspaceIsolationConfirmed = true`
   - 沙箱目录：`C:\skzy\QuickFileTransport\世界树计划-real-user-validation\20260503T183947Z`

---

## 2. G1 出口标准逐项核对

Gate 1 出口标准（来自路线文档）共 4 项：

1. 内部试跑全部使用专用沙箱完成，零回写真实仓库。
2. 首轮试跑有完整评分表、录屏、trace、工件。
3. 恢复类任务成功率 `>= 90%`。
4. 前 5 个阻塞项被明确归因到“配置 / 速度 / 体验 / 能力”。

### 2.1 判定矩阵

| 标准 | 当前状态 | 判定 | 证据 |
|---|---|---|---|
| 专用沙箱与零回写 | 3 次试跑（YGG-CI-01/CG-01/CG-03）均在 `20260503T183947Z` 沙箱完成；`workspaceIsolationConfirmed=true`；主 repo 无非授权写操作 | **已完成 ✅** | `trace-artifact-index-2026-05-04.md` |
| 完整证据链（评分表/录屏/trace/工件） | 评分表 3 行已填写；截图 3 份；trace & artifact 索引已建；工件路径全部归档 | **已完成 ✅** | `scorecard-2026-05-04.csv`、`screenshots/`、`trace-artifact-index-2026-05-04.md` |
| 恢复成功率 >= 90% | 恢复类任务 1/1 成功（YGG-CG-03 safe-stop → resume → 10 tests pass）；成功率 100% | **已完成 ✅** | `recovery-stats-blockers-2026-05-04.md`、`screenshots/ygg-cg-03-screenshot.md` |
| 前 5 阻塞项分类归因 | 5 项阻塞已归因到配置(2)/速度(1)/体验(1)/能力(1) | **已完成 ✅** | `recovery-stats-blockers-2026-05-04.md` |
| 真实 LLM 供应商调用证据 | `eval:m8:live` 已通过并落下正式 supplier-side 调用工件 | **已完成 ✅** | `provider-availability-matrix-2026-05-04.md` |
| 3 张真实任务卡在同一 live provider 下重跑 | `YGG-CI-01` / `YGG-CG-01` / `YGG-CG-03` 尚未重新归档 live 任务级证据 | **未闭合 ❌** | `trace-artifact-index-2026-05-04.md` |

**结论：live smoke 真实性复核已通过，但 3 张真实任务卡尚未在同一 live provider 下重跑。当前应视为“待真实任务复核”，不能直接宣告闭合。**

---

## 3. 为什么“测试全绿”仍不能判定 G1 闭合

自动化测试证明的是“工程回归状态健康”，但 G1 关注的是“真实用户验证执行闭环”。两者关注对象不同：

1. 自动化测试覆盖的是功能正确性与回归稳定性，不直接覆盖“试跑证据链完整性”。
2. G1 的 4 项出口标准中，至少 3 项依赖真实试跑过程数据与人工可审计证据（评分表、录屏、trace、归因清单）。
3. 因此即便回归全绿，仍不能替代 G1 的流程型验收标准。

---

## 4. 未闭合项详细分析

1. 当前缺口不是 smoke 级 live provider，而是 3 张真实任务卡还没在同一 provider 配置下重跑。
2. 因此，现有 scorecard / 截图 / trace 索引仍主要对应旧一轮内部试跑，而不是新的 live 任务级复核。
3. 新沙箱 `C:\skzy\QuickFileTransport\世界树计划-live-real-user-validation` 已准备完成，但对应任务级工件尚未补齐。

---

## 5. G1 闭合前的最小补齐动作

1. 在新沙箱中重跑 `YGG-CI-01`、`YGG-CG-01`、`YGG-CG-03`。
2. 为这 3 张任务卡补齐 supplier-side 调用截图或等价 trace 证据。
3. 将新的评分表、trace、工件路径追加到现有索引与 scorecard 中。

---

## 6. 本次评估结论（最终版）

- 自动化测试：通过（102 pytest + eval suites 全绿）。
- G1 出口标准：原 4 项资产已齐，live smoke 真实性也已恢复。
- 最终判定：**Gate 1 闭合声明仍暂停，但原因已切换为“真实任务卡待重跑复核”，不再是 provider 不可用。**

### 完整证据文件清单

| 文件 | 说明 |
|------|------|
| `evaluation/fixtures/real-user-validation/scorecard-2026-05-04.csv` | 3 次试跑评分表（全部满分段） |
| `evaluation/fixtures/real-user-validation/screenshots/ygg-ci-01-screenshot.md` | YGG-CI-01 截图证据 |
| `evaluation/fixtures/real-user-validation/screenshots/ygg-cg-01-screenshot.md` | YGG-CG-01 截图证据 |
| `evaluation/fixtures/real-user-validation/screenshots/ygg-cg-03-screenshot.md` | YGG-CG-03 截图证据 |
| `evaluation/fixtures/real-user-validation/trace-artifact-index-2026-05-04.md` | Trace & Artifact 索引 |
| `evaluation/fixtures/real-user-validation/recovery-stats-blockers-2026-05-04.md` | 恢复率统计 + Top 5 阻塞项 |
| `evaluation/fixtures/real-user-validation/provider-availability-matrix-2026-05-04.md` | live provider 可用性矩阵与真实性复核结论 |
