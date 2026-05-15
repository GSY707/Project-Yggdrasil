# 世界树计划开发 TODO（执行版）

## 当前阶段

- M1 到 M9、CI 门禁、质量基线、真实用户验证沙箱链路与 Gate 2 官方复跑已经完成。
- **Gate 1、Gate 2、Gate 3 已闭合；当前执行锚点切换为“维持 G3 基线 + 推进 Gate 4 provider/质量扩展”。**
- 当前正式基线见 `docs/research/g2-closeout-2026-05-15.md` 与 `docs/research/g3-closeout-2026-05-15.md`。

## 当前优先级

1. 固化“按改动跑受影响测试、发布前才跑全量”的测试原则：日常不再跑 nightly，全量检查统一走手动 `release-check`。
2. 把 `corepack pnpm eval:g2:regression`、PostgreSQL 回归与 Gate 3 paid-provider live rerun 收口到固定发布前检查入口。
3. 补录跨 provider 的 `planQualityScore0_100`、`reworkCount`、`reworkRate`、`first_token_seconds` 样本，形成正式对比口径。
4. 完成 Gate 3 后遗留技术债：应用插件 fewShotRefs、缺失 `scenes/`、`packages/frontend-sdk/src/index.ts` 拆分。

## 阶段状态

- Gate 1：已闭合。
- Gate 2：已闭合。
- Gate 3：已闭合。
- 2026-05-15 官方复跑：`YGG-CI-01` 1 轮、`YGG-CG-01` 3 轮、`YGG-CG-03` 3 轮全部验收通过。
- `YGG-CG-03`：3/3 `pause_resume_success_0_1 = 1`，恢复成功率 100%。
- `corepack pnpm eval:g2:regression`：已通过。
- `G3-LIVE-2026-05-15-DEEPSEEK-PAID`：`YGG-CI-01`、`YGG-CG-01`、`YGG-CG-03` 全部 `completed` 且验收通过，`YGG-CG-03` 的 `pauseResumeSuccess=True`。

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
- 不在正式 spec 收口前，把工作树或超图推理直接写成运行时硬约束。
- 不让真实试跑回写工程仓库；所有 live 任务继续走专用沙箱。
- 不把 probe、临时脚本、一次性调试产物重新纳入正式交付面。

## 一句话原则

- 日常开发按改动跑受影响测试；PR / merge 只保留低成本 smoke；发布前再走手动全量检查与必要的 live provider 复核。
