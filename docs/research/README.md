# 研究文档组织 (docs/research)

本目录包含世界树计划的所有研究、评估和设计文档。文档已按用途分类组织。

## 📚 目录结构说明

### 🗺️ [roadmaps/](./roadmaps) - 路线图与计划
涵盖项目的战略路线和执行计划。用于理解项目的总体方向和阶段规划。

**关键文档**：
- `final-goal-roadmap-2026-04-30.md` - 最终目标的完整路线图，包含6条设计原则和执行策略
- `memory-tree-agent-executable-roadmap-2026-05-16.md` - 内存树代理的可执行路线
- `pseudo-infinite-context-window-roadmap-2026-05-16.md` - 伪无限上下文窗口实现路线
- `real-user-validation-plan-2026-04-30.md` - 真实用户验证的计划与基线

**推荐阅读**：开发者应从 `final-goal-roadmap-2026-04-30.md` 开始了解项目方向。

---

### 📊 [project-assessments/](./project-assessments) - 项目评估与基线
包含对项目各阶段的评估、差距分析和性能基线。用于验证项目目标达成情况。

**关键文档**：
- `memory-tree-theory-gap-assessment-2026-05-17.md` - 记忆树理论实现情况与差距评估（最新）
- `g4-assessment-and-roadmap-2026-05-15.md` - G4阶段评估和后续路线
- `memory-tree-effect-report-2026-05-17.md` - 记忆树效果评估报告
- `g4-long-task-window-restart-baseline-2026-05-15.md` - 长任务窗口重启基线数据

**用途**：用于跟踪项目进度、验证目标达成度，以及标杆管理。

---

### ✅ [completion-reports/](./completion-reports) - 完成报告与验收
记录各阶段、各功能点的完成情况、验证结果和交付成果。

**关键文档**：
- `P2_COMPLETION_REPORT_2026_05_17.md` - P2阶段完成报告（详细成果清单）
- `P2_COMPLETION_SUMMARY_2026_05_17.md` - P2阶段完成摘要
- `P2_VERIFICATION_AND_P3_DELIVERY_2026_05_17.md` - P2验证与P3交付策略
- `P3_GAP_CLOSEOUT_FREE_AND_PAID_PROVIDERS_2026_05_17.md` - P3差距补齐（免费/付费供应商）
- `P4_COMPLETION_VERIFICATION_2026_05_17.md` - P4完成验证

**用途**：快速了解各阶段的交付物和验收标准。

---

### 📋 [specifications/](./specifications) - 规范、设计与参考
包含系统设计、实现规范、协议定义和核心理念文档。

**子目录和关键文档**：
- `P2_IMPLEMENTATION_SPEC_2026_05_17.md` - P2详细实现规范（~1500行）
- `P2_IMPLEMENTATION_CHECKLIST_2026_05_17.md` - P2实现检查清单
- `P2_QUICK_START_2026_05_17.md` - P2快速启动指南
- `hypergraph-reasoning-protocol-draft-2026-05-05.md` - 超图推理协议草案
- `work-tree-protocol-draft-2026-05-05.md` - 工作树协议草案
- `系统核心理念.md` - 系统的核心设计理念
- **[concepts/](./specifications/concepts)** - 系统概念和设计文档
  - Agent 核心设计、Agent 其他设计
  - 记忆树核心设计、记忆树其他设计
  - Agent行为模式建议组

**推荐**：实现者应参考 `P2_IMPLEMENTATION_SPEC_2026_05_17.md` 进行开发。

---

### 🔬 [technical-analysis/](./technical-analysis) - 技术分析与调查
包含技术问题的深度分析、调试日志、性能数据和工程问题的解决方案。

**关键文档**：
- `memory-tree-agent-work-breakdown-2026-05-16.md` - 内存树代理工作分解
- `memory-tree-theory-gap-assessment-2026-05-17.md` - 记忆树理论差距评估（技术详解）
- `g4-real-task-window-parity-rerun-log-audit-2026-05-16.md` - G4真实任务窗口奇偶性审计
- `runtime-two-failures-summary-2026-05-17.md` - 运行时双重故障分析
- `sqlite-concurrency-ops-queue-2026-05-17.md` - SQLite并发操作队列设计

**用途**：调试问题、理解技术决策、学习复杂系统设计。

---

### 📦 [archive/](./archive) - 历史文档与已完成阶段
包含已完成的项目阶段（G1-G4）、过时或历史参考价值的文档。

**主要内容**：
- **stage-closeouts/** - 各阶段的收尾文档
  - `g2-closeout-2026-05-15.md` - G2阶段收尾
  - `g3-closeout-2026-05-15.md` - G3阶段收尾
  - `g4-closeout-2026-05-15.md` - G4阶段收尾
  
- **real-user-validation/** - 真实用户验证的历史文档
  - `real-user-validation-baseline-freeze-2026-04-30.md`
  - `real-user-validation-internal-pilot-deepseek-2026-04-30.md`

- **[future-planning/](./archive/future-planning)** - 未来规划（初期草案）
  - Agent 原生基础设施规划
  - 多模态潜空间智能体架构设想

- **[legacy-from-old-archive/](./archive/legacy-from-old-archive)** - 旧归档的合并内容
  - G1-G4早期阶段的评估和进度文档
  - 协议集成计划、优化计划等历史文档

**注意**：这些文档主要用于历史参考和上下文理解。对于当前开发，重点参考 roadmaps 和 specifications。

---

## 📖 使用指南

### 我是...

#### 新加入开发者
1. 首先阅读：[roadmaps/final-goal-roadmap-2026-04-30.md](./roadmaps/final-goal-roadmap-2026-04-30.md)
2. 了解系统概念：[specifications/concepts/](./specifications/concepts)
3. 查看实现规范：[specifications/P2_IMPLEMENTATION_SPEC_2026_05_17.md](./specifications/P2_IMPLEMENTATION_SPEC_2026-05-17.md)
4. 参考快速启动：[specifications/P2_QUICK_START_2026_05_17.md](./specifications/P2_QUICK_START_2026-05_17.md)

#### 项目管理者
1. 阅读完成报告：[completion-reports/](./completion-reports)
2. 查看评估数据：[project-assessments/](./project-assessments)
3. 参考路线图：[roadmaps/](./roadmaps)

#### 系统架构师
1. 学习核心理念：[specifications/系统核心理念.md](./specifications/系统核心理念.md)
2. 研究设计文档：[specifications/concepts/](./specifications/concepts)
3. 了解协议设计：[specifications/hypergraph-reasoning-protocol-draft-2026-05-05.md](./specifications/hypergraph-reasoning-protocol-draft-2026-05-05.md)

#### 调试工程师
1. 查看技术分析：[technical-analysis/](./technical-analysis)
2. 参考故障分析：[technical-analysis/runtime-two-failures-summary-2026-05-17.md](./technical-analysis/runtime-two-failures-summary-2026-05-17.md)
3. 研究性能基线：[project-assessments/g4-long-task-window-restart-baseline-2026-05-15.md](./project-assessments/g4-long-task-window-restart-baseline-2026-05-15.md)

---

## 📅 文档更新频率

- **roadmaps/** - 季度或重大决策后更新
- **project-assessments/** - 阶段验收时更新
- **completion-reports/** - 功能交付时更新
- **specifications/** - 需求或设计变更时更新
- **technical-analysis/** - 问题发现时更新
- **archive/** - 阶段结束时归档历史文档

---

## ⚡ 快速导航

- 🎯 **项目目标**：[roadmaps/final-goal-roadmap-2026-04-30.md](./roadmaps/final-goal-roadmap-2026-04-30.md)
- 🛠️ **实现规范**：[specifications/P2_IMPLEMENTATION_SPEC_2026_05_17.md](./specifications/P2_IMPLEMENTATION_SPEC_2026-05-17.md)
- 📊 **最新评估**：[project-assessments/memory-tree-theory-gap-assessment-2026-05-17.md](./project-assessments/memory-tree-theory-gap-assessment-2026-05-17.md)
- ✅ **最新交付**：[completion-reports/P2_COMPLETION_REPORT_2026_05_17.md](./completion-reports/P2_COMPLETION_REPORT_2026_05-17.md)
- 🐛 **问题分析**：[technical-analysis/runtime-two-failures-summary-2026-05-17.md](./technical-analysis/runtime-two-failures-summary-2026-05-17.md)

---

## 📝 组织原则

1. **按用途分类**：文档根据其主要用途分类，便于查找
2. **历史保留**：所有历史文档都保留在 archive 中，便于参考
3. **清晰层次**：重点文档在顶级目录，补充资料在子目录
4. **命名约定**：文件名包含日期和版本标识，便于追踪
5. **可追踪性**：每个文档都有清晰的创建日期和状态标记

---

*最后更新：2026-05-17*
