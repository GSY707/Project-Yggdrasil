# 研究文档组织 (docs/research)

本目录包含世界树计划的所有研究、评估和设计文档。文档已按用途分类组织。

## 当前唯一设计哲学入口

- `../architecture/design-philosophy-and-cognitive-principles.md` - **项目设计哲学唯一主文档**：统一定义当前注意力与长期价值、有效记忆、LOD 记忆树、任务期工作树、能力/Skill/工具按需挂载、主体权责、身份与离线进化。所有研究、协议和实现都必须服从该文档。
- `../architecture/weak-model-behavior-compensation-notes.md` - 弱模型行为补偿注释；只供维护者记录暂时性过强提示、风险和退场门槛，不是第二套哲学。

当前仍有效的下层应用文档：

- `../development/LLM_WORK_TREE_USAGE_GUIDE_AND_CASES_2026_06_28.md` - 工作树 agent-facing 使用指南。
- `../specs/work-tree-protocol-v0.2.md` - 工作树运行协议。
- `../specs/world-build-awakening-task-start-protocol-v0.1.md` - 世界、能力索引与任务启动协议。

以下文件只保留为历史思想来源，不再定义当前项目哲学：

- `../new/世界树计划正式项目定义.md`
- `../new/元提示词.md`
- `specifications/系统核心理念.md`
- `specifications/concepts/*.md`

阅读顺序固定为：主哲学文档 -> 与任务直接相关的协议/指南 -> 历史来源或研究证据。历史来源与主哲学冲突时，无条件以主哲学为准。

## 📚 目录结构说明

### 🗺️ [roadmaps/](./roadmaps) - 路线图与计划
涵盖项目的战略路线和执行计划。用于理解项目的总体方向和阶段规划。

**关键文档**：
- `final-goal-roadmap-2026-04-30.md` - 最终目标的完整路线图，包含6条设计原则和执行策略
- `memory-tree-agent-executable-roadmap-2026-05-16.md` - 内存树代理的可执行路线
- `pseudo-infinite-context-window-roadmap-2026-05-16.md` - 伪无限上下文窗口实现路线
- `real-user-validation-plan-2026-04-30.md` - 真实用户验证的计划与基线

**推荐阅读**：开发者应先读 `../architecture/design-philosophy-and-cognitive-principles.md`，再把 `final-goal-roadmap-2026-04-30.md` 当作历史路线与研究来源。

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
包含历史核心理念、早期概念稿和研究协议草案，不是当前工程规格入口。

**子目录和关键文档**：
- `hypergraph-reasoning-protocol-draft-2026-05-05.md` - 超图推理协议草案
- `work-tree-protocol-draft-2026-05-05.md` - 工作树协议草案
- `系统核心理念.md` - 历史核心假设来源，已由主哲学文档纠偏
- **[concepts/](./specifications/concepts)** - 历史 Agent / 记忆树概念稿
  - Agent 核心设计、Agent 其他设计
  - 记忆树核心设计、记忆树其他设计
  - Agent行为模式建议组
- `archive/P2_*.md` - 已归档的 P2 实现与验收历史材料

**推荐**：当前设计先读主哲学；当前工程规格从 [`../specs/README.md`](../specs/README.md) 进入。本目录内容只作为研究来源和历史证据。

---

### 🔬 [technical-analysis/](./technical-analysis) - 技术分析与调查
包含技术问题的深度分析、调试日志、性能数据和工程问题的解决方案。

**关键文档**：
- `memory-tree-agent-work-breakdown-2026-05-16.md` - 内存树代理工作分解
- `memory-tree-theory-gap-assessment-2026-05-17.md` - 记忆树理论差距评估（技术详解）
- `../development/G4_WEB_RESEARCH_DEFAULT_FAILURE_AUDIT_2026_05_27.md` - G4 web research 默认入口失败审计
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

-- 旧归档目录已清理，历史阶段文档仅保留当前 archive 根目录内仍被维护的条目。

**注意**：这些文档主要用于历史参考和上下文理解。对于当前开发，重点参考 roadmaps 和 specifications。

---

## 📖 使用指南

### 我是...

#### 新加入开发者
1. 首先阅读：[世界树计划完整设计哲学](../architecture/design-philosophy-and-cognitive-principles.md)
2. 再按任务阅读当前协议、架构文档和指南。
3. 历史系统概念只作为来源参考：[specifications/concepts/](./specifications/concepts)
4. 查看当前规格索引：[docs/specs README](../specs/README.md)
5. 查看架构入口：[Architecture Overview](../architecture/overview.md)

#### 项目管理者
1. 阅读完成报告：[completion-reports/](./completion-reports)
2. 查看评估数据：[project-assessments/](./project-assessments)
3. 参考路线图：[roadmaps/](./roadmaps)

#### 系统架构师
1. 先读唯一主文档：[世界树计划完整设计哲学](../architecture/design-philosophy-and-cognitive-principles.md)
2. 再读当前架构与协议文档。
3. 历史核心理念和 concepts 只用于理解思想来源。
4. 研究候选协议：[specifications/hypergraph-reasoning-protocol-draft-2026-05-05.md](./specifications/hypergraph-reasoning-protocol-draft-2026-05-05.md)

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

- 🎯 **项目设计哲学唯一主文档**：[世界树计划完整设计哲学](../architecture/design-philosophy-and-cognitive-principles.md)
- 🧪 **弱模型行为补偿注释**：[非设计真理](../architecture/weak-model-behavior-compensation-notes.md)
- 🛠️ **当前规格索引**：[docs/specs README](../specs/README.md)
- 📊 **最新评估**：[project-assessments/memory-tree-theory-gap-assessment-2026-05-17.md](./project-assessments/memory-tree-theory-gap-assessment-2026-05-17.md)
- ✅ **最新交付**：[completion-reports/P2_COMPLETION_REPORT_2026_05_17.md](./completion-reports/P2_COMPLETION_REPORT_2026_05_17.md)
- 🐛 **问题分析**：[technical-analysis/runtime-two-failures-summary-2026-05-17.md](./technical-analysis/runtime-two-failures-summary-2026-05-17.md)

---

## 📝 组织原则

1. **按用途分类**：文档根据其主要用途分类，便于查找
2. **历史保留**：所有历史文档都保留在 archive 中，便于参考
3. **清晰层次**：重点文档在顶级目录，补充资料在子目录
4. **命名约定**：文件名包含日期和版本标识，便于追踪
5. **可追踪性**：每个文档都有清晰的创建日期和状态标记

---

*最后更新：2026-05-23*
