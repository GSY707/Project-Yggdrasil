# 世界树计划开发 TODO（执行版）

## 当前阶段

- M1 到 M9、CI 门禁、质量基线、真实用户验证沙箱链路与 Gate 2 到 Gate 4 官方基线已经完成。
- **Gate 1、Gate 2、Gate 3、Gate 4 已闭合；当前执行锚点正式切换为“伪无限上下文窗口 / Gate 4 长任务完美实现”。**
- 当前正式基线见 `docs/research/g2-closeout-2026-05-15.md`、`docs/research/g3-closeout-2026-05-15.md` 与 `docs/research/g4-closeout-2026-05-15.md`。

## 当前优先级

1. **[第一优先] 完成“伪无限上下文窗口 / Gate 4 长任务完美实现”**：
	- 冻结 `restart protocol`、`restart snapshot`、`carry-forward package`、`work tree continuity` 的正式边界。
	- 把 runtime 主循环补成真正的多次窗口重启控制器，而不是只停留在 `restartMessage` 预留位。
	- 把 `restartCount`、`compressionCount`、`cumulativeWindowSpanTokens`、`carryForwardLossCount` 纳入正式 artifact、scorecard 与 provider summary。
2. 建立官方长任务 stress 评测：
	- 手动限制有效上下文窗口，强制同一任务经历 100 次上下文窗口重启/压缩。
	- 用更长上下文窗口 reference 路径作为对照，目标是短窗口路径与长窗口路径在同一 acceptance contract 下得到相同结论。
3. 在上述主线不回退的前提下，继续维持 `corepack pnpm eval:g4:multiscene` / `release:check` 与必要的长任务 provider matrix 样本补录。
4. 仅在不阻塞上述主线时，再推进 `packages/frontend-sdk/src/index.ts` 拆分等非阻塞结构优化。

## 阶段状态

- Gate 1：已闭合。
- Gate 2：已闭合。
- Gate 3：已闭合。
- Gate 4：已闭合。
- 2026-05-15 官方复跑：`YGG-CI-01` 1 轮、`YGG-CG-01` 3 轮、`YGG-CG-03` 3 轮全部验收通过。
- `YGG-CG-03`：3/3 `pause_resume_success_0_1 = 1`，恢复成功率 100%。
- `corepack pnpm eval:g2:regression`：已通过。
- `G3-LIVE-2026-05-15-DEEPSEEK-PAID`：`YGG-CI-01`、`YGG-CG-01`、`YGG-CG-03` 全部 `completed` 且验收通过，`YGG-CG-03` 的 `pauseResumeSuccess=True`。
- `evalsuite_g4_multiscene`：`evalrun_01ac728f221e4dd7ad4c`，`10/10` 通过。
- `evalsuite_g4_provider_matrix`：`evalrun_0f00b84c7df0447e9121`，`6/6` 通过，`deepseek_direct / deepseek-v4-pro` 与 `longcat / LongCat-Flash-Lite` 全部保留正式 scene/few-shot 合同并输出 takeover 指标。

## 技术债清理进度

> 详细规范见 `docs/ANTI_TECH_DEBT.md`。

### Gate 2 前已完成

- [x] `repositories.py` 拆为 `persistence/repositories/` 子包，并纳入 G2 固定回归。
- [x] `services.py` 拆为 `services/` 子包，并纳入 G2 固定回归。
- [x] `evaluation_runtime.py` 拆为 `evaluation_runtime/` 子包。
- [x] `runtime_kernel.py` 拆为 `runtime_kernel/` 子包。
- [x] Core API HTTP 关键路径 P50 / P95 已实测并回写 `docs/QUALITY_BASELINE.md`。

### Gate 3 前待完成

- [x] 应用插件 fewShotRefs 补全（`base-template`、`coding-greenfield`、`deep-research`、`epic-writing`）。
- [x] 补全缺少 `scenes/` 的应用插件。
- [x] 发布前 PostgreSQL 回归入口已收口到手动 `release-check` workflow（`pytest --postgres -m "not slow"`）。
- [ ] `packages/frontend-sdk/src/index.ts` 拆分。

## 规格入口

- `docs/PRD-v0.1.md`
- `docs/protocols/README.md`
- `docs/specs/README.md`
- `docs/specs/agent-runtime-protocol-v0.1.md`
- `docs/research/g2-closeout-2026-05-15.md`
- `docs/research/g3-closeout-2026-05-15.md`

## 明确不该现在做的事

- 不在 G2 已闭环后马上重开大规模新场景扩展；先守住固定回归和样本质量。
- 不在“伪无限上下文窗口 / 长任务多次重启”正式闭环前，把注意力重新切回非阻塞技术债主线。
- 不在正式 spec 收口前，把工作树或超图推理直接写成运行时硬约束。
- 不让真实试跑回写工程仓库；所有 live 任务继续走专用沙箱。
- 不把 probe、临时脚本、一次性调试产物重新纳入正式交付面。

## 一句话原则

- 日常开发按改动跑受影响测试；PR / merge 只保留低成本 smoke；发布前再走手动全量检查与必要的 live provider 复核。
