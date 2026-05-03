# 世界树计划开发 TODO（执行版）

## 当前阶段
- 当前处于 Gate 1：真实用户验证执行阶段。
- 目标是先证明“用户只给目标，系统在隔离沙箱内可稳定交付”，再决定是否扩功能面。
- 已完成里程碑与历史执行记录已归档到 `docs/research/` 与 `docs/research/归档/`。

## 顶层路线
- 路线文档：`docs/research/final-goal-roadmap-2026-04-30.md`
- 执行原则：Gate 1 未闭合前，不重开大规模功能扩展。

## 当前阶段完成度
- Gate 1 出口标准：0 / 4 项闭合。
- 当前主要缺口：内部试跑证据、Core API HTTP 实测延迟、首 token/首次有效输出观测。

## 真实用户验证执行计划（当前执行中）

### RV1 — 试跑环境与隔离
- [x] 固化专用沙箱约束（禁止回写当前工程目录）。
- [x] 新增 `corepack pnpm real-user:prepare`。
- [ ] 在专用沙箱完成 2 到 3 次内部试跑。
- [ ] 将 Windows / MinIO 端口覆盖前提补入试跑说明。

### RV2 — 内部试跑与评分闭环
- [x] 冻结任务包与评分表。
- [x] 冻结内部试跑基线与 DeepSeek V4 调试记录。
- [ ] 先执行 `YGG-CI-01` 与 `YGG-CG-01` 两条首轮内部试跑。
- [ ] 沉淀前 5 个阻塞因素（配置/速度/体验/能力）。

### RV3 — 实测性能与质量回写
- [ ] 补 Core API HTTP 关键路径 P50 / P95 实测。
- [ ] 回写 `docs/QUALITY_BASELINE.md`。
- [ ] 补首 token / 首次有效输出观测。

### RV4 — 外部真实用户准入
- [ ] 内部试跑稳定后，扩大到 5 到 8 名内部用户。
- [ ] 在同材料、同权限、同时间盒下做首轮 A/B。
- [ ] 产出 go / no-go 建议。

## 当前最该做的 10 件事
1. 在专用沙箱完成 `YGG-CI-01` 首轮内部试跑。
2. 在专用沙箱完成 `YGG-CG-01` 首轮内部试跑。
3. 补齐首轮试跑评分表、录屏、trace 与工件目录。
4. 沉淀前 5 个阻塞因素并分类。
5. 实测 Core API HTTP 关键路径 P50 / P95。
6. 将 HTTP 实测值回写到 `docs/QUALITY_BASELINE.md`。
7. 补首 token / 首次有效输出观测。
8. 在内部试跑中验证 safe-stop / resume 连续性。
9. 校验试跑脚本在 Windows 端口冲突下的可用性。
10. 输出 Gate 1 闭合评估草案。

## 技术债清理进度

> 详细规范见 `docs/ANTI_TECH_DEBT.md`。

### 统计结果（2026-05-04）
- 占位代码：0 个文件。
- 临时代码：0 个文件。
- 正式工程代码：298 个文件。

## 规格入口
- docs/PRD-v0.1.md
- docs/protocols/README.md
- docs/specs/README.md
- docs/specs/agent-runtime-protocol-v0.1.md

## 一句话原则
- 先闭合真实用户验证，再扩能力面。