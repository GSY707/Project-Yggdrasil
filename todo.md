# 世界树计划开发 TODO（执行版）

## 当前阶段
- M1 到 M9、CI 门禁、质量基线和真实用户验证材料冻结已经完成。
- **Gate 1 的原闭合声明已转为“待真实任务复核”；当前 live smoke 真实性已经恢复，下一步进入“重跑 3 张任务卡 + 继续推进 Gate 2 能力固化”。**
- 核心决策：以“稳定复现”为首要目标，优先固化任务接管、恢复连续性、交付模板与关键指标采集。
- 本轮新增里程碑：LLM API 指数退避重试 + safe-shutdown/pending-tool-calls 自动恢复链路已落地并通过专项测试。

## 顶层路线
- 路线文档：`docs/research/final-goal-roadmap-2026-04-30.md`
- 当前执行锚点：推进 Gate 2，也就是“把窄路径闭环产品化为受控自治并稳定复现”。
- 在 Gate 2 闭合前，不重开大规模场景扩展。
- 提示词当前目标：稳定到 `P2`，并补齐 `P3` 所需观测口径与样本沉淀。

## 当前阶段完成度
- 按原 Gate 1 资产口径计：**4 / 4 项已完成**；按最新“真实任务级复核”口径计，**当前仍待最终重验**。
- 按 Gate 2 出口标准计：**0 / 3 项闭合**，当前处于能力固化与复跑证据补齐期。
- 当前主要缺口集中在：3 张真实任务卡的 live 复跑与 supplier-side 任务级证据、重复复跑样本、复杂文件拆分正式能力回归化、Core API 延迟实测与首响观测、计划质量/返工率真实样本回填。

## 真实用户验证执行计划（当前执行中）

### RV1 — 试跑环境与隔离
- [x] 固化专用沙箱约束：运行时必须使用专用目录，不得回写当前工程目录。
- [x] 新增 `corepack pnpm real-user:prepare`，生成真实用户试跑专用沙箱、隔离状态目录、冻结材料副本与激活脚本。
- [x] 在专用沙箱里完成 2 到 3 次内部试跑，优先选择边界清晰、工具集合更窄的任务。
- [ ] 将 Windows / MinIO 端口覆盖与环境前提补入试跑说明，避免 E2 环境复现误配。

### RV2 — 内部试跑与评分闭环
- [x] 冻结任务包与评分表：Pack A / Pack B / Pack C 与 scorecard 模板。
- [x] 冻结内部试跑基线与 DeepSeek V4 调试记录。
- [x] 执行 `YGG-CI-01`、`YGG-CG-01`、`YGG-CG-03` 内部试跑，并收集完整工件、录屏和评分表。
- [x] 将前 5 个阻塞因素按“配置 / 速度 / 体验 / 能力”分类沉淀。
- [x] 将 `planQualityScore0_100`、`reworkCount`、`reworkRate` 接入 scorecard 模板与 `pilot-scorecard summarize` 汇总链。
- [ ] 在同一 live provider 配置下重跑 `YGG-CI-01`、`YGG-CG-01`、`YGG-CG-03`，补齐任务级 supplier-side 调用记录。

### RV3 — 实测性能与质量回写
- [ ] 补 Core API HTTP 关键路径的实测 P50 / P95。
- [ ] 回写 `docs/QUALITY_BASELINE.md`，用实测值替换当前目标值。
- [ ] 补首 token / 首次有效输出级别的首响观测。

### RV4 — 外部真实用户准入
- [ ] 仅在 live provider 证据、内部试跑通过率、人工接管率和评分填写流程稳定后，再扩大到 5 到 8 名内部用户。
- [ ] 与对照组在同一材料、同一权限、同一时间盒下做首轮 A/B。
- [ ] 产出 go / no-go 建议，决定是否扩大外部真实用户测试范围。

## 当前最该做的 10 件事
1. 在 live provider 已恢复的前提下，重跑 `YGG-CI-01`、`YGG-CG-01`、`YGG-CG-03`，补齐 supplier-side 调用证据。
2. 连续 3 轮重复执行 `YGG-CG-01` + `YGG-CG-03`，统计验收通过率与人工接管中位数。
3. 在后续复跑样本中正式填写 `planQualityScore0_100`、`reworkCount`、`reworkRate` 三列。
4. 形成新一版 G2 基线报告：通过率、接管中位数、澄清回合、恢复成功率、计划质量、返工率。
5. 将“复杂文件拆分”纳入固定回归集（先落地一个真实大文件拆分样本）。
6. 实测 Core API HTTP 关键路径的 P50 / P95（TD-03）。
7. 将 HTTP 实测值回写到 `docs/QUALITY_BASELINE.md`。
8. 补首 token / 首次有效输出级别的首响观测。
9. 将任务接管协议扩展到更多 coding app 主路径并补回归断言。
10. 清理旧 shell 中手工注入的 `YGGDRASIL_STATE_ROOT=.yggdrasil/state`，避免覆盖修正后的 `.env`。

## 技术债清理进度

> 详细清理规范见 `docs/ANTI_TECH_DEBT.md`。

### P0 · 已完成（Gate 1 前）
- [x] `infra/langfuse-compose.yml` LANGFUSE_S3_MEDIA_UPLOAD_ENDPOINT 使用 localhost → 已修复为 `langfuse-minio:9000`
- [x] `observability_exporters.py`、`observability.py`、`runtime_kernel.py` 共 6 处静默 pass 吞异常 → 已替换为带日志的处理

### P1 · Gate 2 前（必须完成）
- [x] **TD-01** `repositories.py` 已拆为 `persistence/repositories/` 子包；Gate 2 剩余工作转为“复杂文件拆分正式回归化”
- [x] **TD-02** `services.py` 已拆为 `services/` 子包；Gate 2 剩余工作转为“按资源域回归验证与文档同步”
- [ ] **TD-03** Core API HTTP 实测压测 + 回写 `QUALITY_BASELINE.md` 第 2.3 节

### P2 · Gate 3 前
- [x] **TD-04** `evaluation_runtime.py` 已拆为 `evaluation_runtime/` 子包（bootstrap / scorer / suite_runner）
- [x] **TD-05** `runtime_kernel.py` 已拆为 `runtime_kernel/` 子包（root_mount / snapshot / execution_loop）
- [ ] **TD-06** 应用插件 fewShotRefs 补全（base-template、coding-greenfield、deep-research、epic-writing）
- [ ] **TD-07** 补全缺少 scenes/ 的 7 个应用插件

### P3 · 长期持续
- [ ] **TD-08** PostgreSQL CI 层（nightly pytest --postgres）
- [ ] **TD-09** `frontend-sdk/src/index.ts` 拆分（551 行）

## 规格入口
- docs/PRD-v0.1.md
- docs/protocols/README.md
- docs/specs/README.md
- docs/specs/agent-runtime-protocol-v0.1.md

## 代码盘点

### 统计口径
- 统计范围：仓库内 .py、.ts、.tsx、.json、.toml、.yaml、.yml、.css 正式工程与配置文件。
- 排除范围：.venv、node_modules、.next、build/dist、.git、本地临时状态目录与评测 sandbox。
- 不包含 markdown 文档，因此 docs 中的大量正式规格文档不纳入下面的代码统计。

### 分类标准
- 占位代码：接口形状已经固定，但返回的是假数据、空结果或演示值，不能承载正式业务。
- 临时代码：仅服务于一次性调试或过渡，不应长期保留。
- 正式工程代码：后续应继续沿用的服务、模块、SDK、控制面、评测和基础设施代码。

### 统计结果（2026-05-01 校准）
- 占位代码：0 个文件。
- 临时代码：0 个文件。
- 正式工程代码：298 个文件。

### 占位代码清单
- 当前无。

### 临时代码清单
- 当前无。

## 已完成资产
- [x] PRD、ADR、协议和数据规格已经形成第一版正式文档。
- [x] Monorepo 工作区、共享 SDK、服务、模块、适配器与基础设施已经形成稳定边界。
- [x] M1-M8 的正式能力已经落地并通过回归、benchmark、live、ops 验证。
- [x] M9 模块已完成：shared-memory、pause-resume、multimodal-memory、relation-discovery、memory-organizer、training-lab。
- [x] 已完成一轮低风险大文件拆分：M9 聚合测试文件已按模块拆成 5 个专项测试文件，并通过定向 pytest 验证。
- [x] Core API 已暴露 assets、training、prompting 等正式资源面。
- [x] Web 已提供资产、训练、Prompt 控制面，不再只停留在总览数字。
- [x] PromptCompiler、prompt artifact、工具注册和编译预览已经进入正式控制面。
- [x] 新增 M9 control-plane regression suite，并补齐相关 API 回归。
- [x] TypeScript baseUrl 弃用问题已经处理，前端配置已切到未来兼容写法。

## 未来工作重排

### M1-M8（已完成）
- [x] M1 清理骨架债务。
- [x] M2 持久化底座。
- [x] M3 模块宿主与事件总线。
- [x] M4 text-memory 第一条纵向链路。
- [x] M5 主 Agent 第一条闭环。
- [x] M6 Sub-Agent 与 PR 最小闭环。
- [x] M7 Web 控制台升级为正式工作台。
- [x] M8 评测与运维底座。

### M9. 第二阶段模块化能力（已完成）
- [x] 多模态记忆模块。
- [x] 自动整理与软遗忘模块。
- [x] 主动关联发现模块。
- [x] 高级权限与共享记忆空间模块。
- [x] 训练与蒸馏实验模块。
- [x] 任务暂停与无感恢复的完整产品化交付。
- [x] 正式控制面资源：assets、dataset versions、model artifacts、prompt artifacts。
- [x] 正式控制面页面：资产、训练、PromptOps。
- [x] 正式评测补充：M9 acceptance、M9 control-plane regression。
- 验收：M9 能力已经具备正式 API、正式 Web 页面、正式回归与验收链路，而不是停留在模块内部实现。

## 明确不该现在做的事
- 不要在首轮内部试跑闭合前继续扩场景、扩应用面或引入新的大模块。
- 不要为了追求”看起来更聪明”而在证据不足时写隐式推断逻辑。
- 不要让世界树运行时直接读写当前工程目录；真实试跑必须走专用沙箱。
- 不要把本地状态目录、评测 sandbox 或生成产物重新纳入正式代码盘点。
- 不要在没有评分、录屏、工件和日志闭环的前提下扩大真实用户样本。

## 一句话原则
- 当前项目已经进入”真实用户验证执行”阶段：先证明隔离试跑和任务完成率成立，再决定继续扩什么。