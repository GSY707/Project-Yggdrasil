# 世界树计划开发 TODO（执行版）

## 当前阶段

- M1 到 M9、CI 门禁、质量基线、真实用户验证沙箱链路与 Gate 2 官方复跑已经完成。
- **Gate 1 已闭合，Gate 2 已闭合；当前执行锚点切换为“维持 G2 基线 + 准备 Gate 3 协议化升级”。**
- 当前正式基线见 `docs/research/g2-closeout-2026-05-15.md` 与 `evaluation/fixtures/real-user-validation/scorecard-2026-05-15-g2-complete.csv`。

## 当前优先级

1. 把 `corepack pnpm eval:g2:regression` 纳入固定发布前检查或 nightly，持续守住复杂文件拆分能力。
2. 在后续真实样本中补录 `planQualityScore0_100`、`reworkCount`、`reworkRate`，把 Gate 2 质量口径从“结果闭环”扩展到“过程质量可比较”。
3. 补首 token / 首次有效输出级别的首响观测，作为 Gate 3 的体验基线。
4. 推进工作树 / 任务接管 / 运行时数据规格之间的正式收口，为 Gate 3 做最小协议升级。

## 阶段状态

- Gate 1：已闭合。
- Gate 2：已闭合。
- 2026-05-15 官方复跑：`YGG-CI-01` 1 轮、`YGG-CG-01` 3 轮、`YGG-CG-03` 3 轮全部验收通过。
- `YGG-CG-03`：3/3 `pause_resume_success_0_1 = 1`，恢复成功率 100%。
- `corepack pnpm eval:g2:regression`：已通过。

## 技术债清理进度

> 详细规范见 `docs/ANTI_TECH_DEBT.md`。

### Gate 2 前已完成

- [x] `repositories.py` 拆为 `persistence/repositories/` 子包，并纳入 G2 固定回归。
- [x] `services.py` 拆为 `services/` 子包，并纳入 G2 固定回归。
- [x] `evaluation_runtime.py` 拆为 `evaluation_runtime/` 子包。
- [x] `runtime_kernel.py` 拆为 `runtime_kernel/` 子包。
- [x] Core API HTTP 关键路径 P50 / P95 已实测并回写 `docs/QUALITY_BASELINE.md`。

### Gate 3 前待完成

- [ ] 应用插件 fewShotRefs 补全（`base-template`、`coding-greenfield`、`deep-research`、`epic-writing`）。
- [ ] 补全缺少 `scenes/` 的应用插件。
- [ ] PostgreSQL CI 层（nightly `pytest --postgres`）。
- [ ] `packages/frontend-sdk/src/index.ts` 拆分。

## 规格入口

- `docs/PRD-v0.1.md`
- `docs/protocols/README.md`
- `docs/specs/README.md`
- `docs/specs/agent-runtime-protocol-v0.1.md`
- `docs/research/g2-closeout-2026-05-15.md`

## 明确不该现在做的事

- 不在 G2 已闭环后马上重开大规模新场景扩展；先守住固定回归和样本质量。
- 不在正式 spec 收口前，把工作树或超图推理直接写成运行时硬约束。
- 不让真实试跑回写工程仓库；所有 live 任务继续走专用沙箱。
- 不把 probe、临时脚本、一次性调试产物重新纳入正式交付面。

## 一句话原则

- Gate 2 已经证明“窄路径可稳定复现”；Gate 3 的工作应该围绕“正式对象升级、质量口径补齐、固定回归守住”展开。
