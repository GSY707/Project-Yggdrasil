# 世界树计划 · Gate 4 评估与完美实现路线图（2026-05-15）

- 文档状态：Working Draft
- 日期：2026-05-15
- 口径说明：
  - 本文中的 G4 指 `docs/research/final-goal-roadmap-2026-04-30.md` 中的 Gate 4，也就是“多场景通用化”。
  - 它不等同于 `docs/PRD-v0.1.md` 中早期的 G4（可插拔模块平台）。前者是当前执行主线，后者已经是基座能力的一部分。
- 关联文档：
  - `docs/research/final-goal-roadmap-2026-04-30.md`
  - `docs/research/g2-closeout-2026-05-15.md`
  - `docs/research/g3-closeout-2026-05-15.md`
  - `docs/research/g4-closeout-2026-05-15.md`
  - `docs/protocols/yggdrasil-application-manifest-v0.1.md`
  - `docs/specs/task-takeover-protocol-v0.1.md`
  - `todo.md`

---

## 1. 先给结论

本路线图中的主要实现项已经完成；正式闭环证据见 `docs/research/g4-closeout-2026-05-15.md`。

最重要的判断有 4 条：

1. Gate 4 当前不能被定义为“再多做几个应用”。它的本质是：在至少 3 个高价值场景里，让用户都能获得相似的“只给目标，系统接管”的稳定体验。
2. 仓库已经有 Gate 1、Gate 2、Gate 3 的正式闭环证据，因此 Gate 4 不需要再从运行时、恢复链路或服务器隔离重新起步。
3. 当前真正卡住 Gate 4 的，不是缺场景名字，而是缺“正式装配、正式 few-shot、正式评测、正式 provider 对比、正式 CI 门禁”。
4. 如果要完美实现 Gate 4，必须先收缩范围，只认证 3 个官方场景族；不能把 10 个应用插件一起当作 Gate 4 出口标准，否则会把当前基线重新打散。

一句话版本：

> **项目已经准备好开始 Gate 4，但还没有准备好宣称 Gate 4 已成立。要把 Gate 4 做成“完美实现”，必须先补齐多场景资产装配、few-shot 执行链、场景验收器、跨 provider 质量矩阵和发布门禁。**

---

## 2. Gate 4 在当前项目里的准确定义

根据路线图，Gate 4 不是抽象的“更通用”，而是下面 5 件事同时成立：

1. 至少 3 个高价值场景族形成正式能力闭环。
2. 场景切换主要通过应用模板、SeedTemplate、toolPolicy、retrievalHints 和评分卡完成，而不是靠主循环硬编码分叉。
3. 网络检索、资料抓取、资产导入导出和功能性 Sub-Agent 成为稳定积木。
4. 不同场景下仍保持相似的任务接管体验，而不是每个场景都要求用户重新做提示词工程。
5. 至少存在一套跨 provider 的正式对比口径，能证明这是“泛化”，而不是只在单一模型上偶然成功。

因此，完美实现 Gate 4 的定义应当是：

> **以统一的任务接管协议、恢复/审计/预算基线和应用插件装配机制为前提，在编码、深度研究、长篇创作 3 个官方场景族中，稳定跑通快任务、跨会话任务和恢复类任务，并且把这些结果固化为跨 provider、可回归、可发布的正式门禁。**

---

## 3. 当前已经具备的基础

### 3.1 已闭环的共性底座

当前仓库已经完成 Gate 1、Gate 2、Gate 3 的正式闭环，这意味着 Gate 4 可以直接复用以下底座：

1. 正式任务接管协议、work tree、pause/resume、safe-stop、post-invocation budget hard fail。
2. 正式 appId 维度、应用清单、PromptCompiler、Prompt 控制面与 compile artifact。
3. 正式 provider gateway、paid-provider 门控、first token 观测、scorecard 落盘与 live task pack。
4. 正式服务器侧隔离、worker retry/requeue、execute-server 最小权限层。

这些能力说明 Gate 4 不需要先解决“能不能跑”“能不能恢复”“能不能隔离”，而是可以直接解决“能不能多场景稳定泛化”。

### 3.2 已经存在的场景骨架

当前仓库已经有：

1. 10 个应用插件：`base-template`、`coding-greenfield`、`coding-inherit`、`deep-research`、`epic-writing`、`knowledge-studio`、`learning-coach`、`maintenance-ops`、`scenic-guide`、`software-factory`。
2. 7 个场景模块：`scene-coding-new-project`、`scene-coding-inherit-project`、`scene-research-deep`、`scene-writing-epic`、`scene-learning-coach`、`scene-maintenance-default`、`scene-scenic-guide`。
3. PromptCompiler 已能按 app、runType、taskType、seed template 进行装配，说明 Gate 4 的装配入口已经存在，不需要另起新链路。

### 3.3 已经存在的指标底座

当前 scorecard 与 live task pack 已经支持或至少记录了以下关键字段：

1. `first_token_seconds`
2. `first_useful_output_seconds`
3. `planQualityScore0_100`
4. `reworkCount`
5. `reworkRate`
6. `human_takeover_count`
7. `user_clarification_rounds`

这意味着 Gate 4 缺的不是“没有指标容器”，而是“没有围绕多场景和跨 provider 把这些指标做成正式门禁”。

---

## 4. 当前阻塞 Gate 4 的硬缺口

### 4.1 场景资产已经存在，但装配边界不干净

当前 specialized app 的 manifest 多数采用下面这种形态：

1. `sceneModules` 指向正式场景模块。
2. `seedTemplateFiles` 却是空数组。
3. 同时应用目录下又存在本地 `scenes/generic-default.yaml`。

这说明当前仓库存在一个明确漂移：

- **真正进入执行链的是 scene module 里的 seed template。**
- **应用目录里的本地 scenes 资产多数没有进入正式装配。**

如果不先收口这个边界，Gate 4 的问题会从“缺场景能力”退化成“同一个场景到底以哪份资产为准”。

### 4.2 few-shot 仍然停留在“字段存在”，还不是“执行能力”

当前状态是：

1. 多个主 PromptProfile 已经声明了 `fewShotRefs`。
2. 所有正式 scene module 的 seed template 里，`fewShotRefs` 仍然是空数组。
3. PromptCompiler 当前会加载 `fewShotRefs` 字段，但 `compile_runtime_prompt()` 只编译 system/user sections，没有真正把 few-shot 内容注入 `messages`。

这意味着 Gate 4 目前还没有真正的“场景化 few-shot 执行链”。

这不是小问题，而是 Gate 4 的核心缺口之一，因为多场景泛化不能只靠 profile 文风切换，必须靠 few-shot 把场景化工作方式钉住。

### 4.3 评测层仍然主要是 G2/G3 与基础能力，不是 G4 多场景验收

当前正式 suite 只有：

1. `regression-m4-m6`
2. `m8-benchmark-memory-strategies`
3. `m8-live-llm`
4. `m9-control-plane`
5. `m9-acceptance`
6. `g2-regression`

当前没有任何一个正式 suite 可以回答下面这几个 Gate 4 关键问题：

1. 编码、研究、写作 3 个场景是否都稳定通过。
2. 同一个 provider 在不同场景下是否存在明显偏科。
3. 场景切换是否会把上一场景的默认行为错误带入下一场景。
4. 场景特有验收器是否真的能发现问题，而不是只看通用“任务完成”。

### 4.4 provider 已经有闭环证据，但还没有正式泛化矩阵

当前正式强证据主要集中在：

1. `deepseek_direct / deepseek-v4-pro` 的 Gate 2、Gate 3 官方复跑。
2. `longcat / LongCat-2.0-Preview` 的 M8 live smoke（并保留 `LongCat-Flash-Lite` 作为对照项）。

但这还不是 Gate 4 所需的“跨 provider 泛化矩阵”。

当前缺口是：

1. 没有同一批多场景任务在多个 provider 下的统一对比样本。
2. 没有正式的 provider 可用性 / 质量矩阵文档。
3. 没有明确定义“官方验收 provider”和“成本对照 provider”的角色分工。

### 4.5 当前测试策略已经收缩，但 Gate 4 门禁还没补齐

当前仓库已经开始按“日常只跑受影响测试、发布前才跑全量”的原则收口：

1. PR / merge 只保留低成本 smoke，不再承担全仓 Python 回归、benchmark 或定时 nightly 的职责。
2. PostgreSQL 回归、固定评测回归与 benchmark 已收口到手动 `release-check`。

这解决了 CI 与看板的旧漂移，但 Gate 4 仍有一个剩余缺口：

1. 当前发布前门禁还没有正式纳入 G4 多场景 suite。
2. provider 对比 smoke 也还没有升级成 G4 级别的正式矩阵入口。

因此，Gate 4 下一步不该再争论 nightly，而是直接补齐“发布前检查里缺哪些 G4 正式门禁”。

---

## 5. 我对“完美实现 Gate 4”的定义

为了避免路线图越写越大，Gate 4 的完美实现必须先明确“什么算范围内，什么不算”。

### 5.1 官方认证的 3 个场景族

我建议 Gate 4 的正式出口只认证 3 个官方场景族：

1. **编码族**：以 `yggdrasil.app.coding-greenfield` 为主应用，`software-factory` 与 `coding-inherit` 作为后续扩展。
2. **研究族**：以 `yggdrasil.app.deep-research` 为主应用，`knowledge-studio` 作为后续扩展。
3. **创作族**：以 `yggdrasil.app.epic-writing` 为主应用，`scenic-guide`、`learning-coach`、`maintenance-ops` 不纳入 Gate 4 正式出口。

理由很直接：

1. 这 3 个场景族与路线图原始目标完全一致。
2. 当前仓库已经分别有对应场景模块，可直接进入资产收口。
3. 如果把其余应用也一起纳入 Gate 4，范围会从“通用化验证”失控成“全产品线齐套化”。

### 5.2 Gate 4 完美状态下必须同时成立的 8 条标准

1. 3 个官方场景族都具有正式主应用、正式 scene module、正式 PromptProfile、正式 SeedTemplate、正式 few-shot 资产。
2. few-shot 资产是真正进入运行时编译和 artifact 的，不只是 YAML 里挂了一个引用。
3. 场景差异主要体现在 profile、seed、tool policy、retrieval hints、output contract 和验收器，而不是 runtime 硬编码分叉。
4. 网络检索、资料抓取、资产导入导出、上下文清理、结构重组等功能性 Sub-Agent 已成为可复用能力模块。
5. 每个官方场景族至少有一组快任务、一组跨会话任务、一组恢复类任务的正式评测包。
6. 同一批任务在至少 2 个 provider 档位下具备可比较 scorecard。
7. CI / 发布前检查已经把 G2 固定回归、G4 多场景回归和 provider 对比 smoke 纳入正式门禁。
8. 文档、目录说明、运行手册和看板对 Gate 4 的口径一致，不再出现“代码已做、待办还显示未做”这种排程漂移。

---

## 6. 完美实现 Gate 4 必须完成的事项

### 6.1 事项 A：冻结 Gate 4 官方范围

必须做的动作：

1. 明确 3 个官方场景族与各自主应用。
2. 明确哪些应用属于 Gate 4 正式出口，哪些属于 Gate 4 之后的扩展项。
3. 明确官方验收 provider 与成本对照 provider。

如果不先冻结这一步，后面所有 few-shot、评测和回归都会失去边界。

### 6.2 事项 B：收口场景资产来源

必须做的动作：

1. 统一 `SeedTemplate` 的单一事实来源。
2. 对 specialized app，明确采用“scene module 提供正式 seed template”还是“应用目录本地 seedTemplateFiles 提供正式 seed template”，不能两条链路并存。
3. 对当前应用目录里未正式接线的 `scenes/generic-default.yaml` 做二选一：要么补 manifest 接线，要么删除以避免假资产。

这是 Gate 4 最先要清理的工程债，因为它直接影响“到底是哪套场景资产在生效”。

### 6.3 事项 C：把 few-shot 升级为正式运行时资产

必须做的动作：

1. 新增正式 few-shot 资产目录与加载规则。
2. 让 `PromptProfile.fewShotRefs` 与 `SeedTemplate.fewShotRefs` 不再只是字段，而是进入实际编译消息。
3. 在 compile artifact、request transcript 和 Prompt 控制面中显式记录最终生效的 few-shot refs。
4. 为编码、研究、创作 3 个官方场景族各补至少 2 组高价值 few-shot。

如果这一步不做，Gate 4 最终只会得到“profile 文风切换”，而不是“工作方式切换”。

### 6.4 事项 D：把功能性 Sub-Agent 做成稳定积木

必须做的动作：

1. 把“显式协作型 Sub-Agent”和“隐式功能型 Sub-Agent”分开建模。
2. 先固化 4 类跨场景通用能力：资料导入、批量阅读、上下文清理、结构重组。
3. 再补 3 类场景验收型能力：编码验证、研究证据审查、创作连续性审查。
4. 每个能力都要有权限边界、审计记录、失败语义和回归样本。

Gate 4 不是靠主 Agent 一个人变聪明，而是靠可复用功能积木减少不同场景下的重复临场发挥。

### 6.5 事项 E：补齐网络与资产导入导出链路

必须做的动作：

1. 为外部资料抓取、网页导入、资产导入导出建立正式能力边界。
2. 明确默认禁用、按任务申请、按应用模板授权的权限策略。
3. 确保这些能力在研究族与创作族里都有正式验收样本，而不是只在编码链路里存在。

这一步是 Gate 4 区别于 Gate 2、Gate 3 的关键之一，因为多场景泛化一定会用到更丰富的外部信息入口。

### 6.6 事项 F：新增 Gate 4 正式评测套件

必须做的动作：

1. 新增至少 1 个 Gate 4 汇总 suite，或 3 个按场景拆分 suite。
2. 每个官方场景族至少有 3 类任务：快任务、跨会话任务、恢复类任务。
3. 为每个场景补场景特有验收器，而不是只看通用 pass/fail。
4. 把 `planQualityScore0_100`、`reworkCount`、`reworkRate`、`first_token_seconds`、`first_useful_output_seconds` 作为正式比较口径。

没有 Gate 4 suite，就没有 Gate 4 的工程出口。

### 6.7 事项 G：建立跨 provider 正式矩阵

必须做的动作：

1. 明确 1 个官方验收 provider，例如 `deepseek_direct / deepseek-v4-pro`。
2. 明确 1 个成本对照 provider，例如 `longcat / LongCat-Flash-Lite`（与默认 `longcat / LongCat-2.0-Preview` 同任务对照）。
3. 在同一批多场景任务下生成统一 scorecard 对比，不允许不同 provider 跑不同任务。
4. 形成正式 provider 质量矩阵文档，至少比较：通过率、澄清回合、接管次数、计划质量、返工率、首 token、首次有效输出。

Gate 4 的“泛化”必须包含 provider 维度，否则很容易把模型特性误判成系统能力。

### 6.8 事项 H：把 Gate 4 纳入 CI / 发布前检查

必须做的动作：

1. 把 `eval:g2:regression` 纳入固定发布前检查，先守住 G2 不回退。
2. 把 Gate 4 多场景 suite 纳入 `release-check`；日常开发仍按改动只跑受影响测试。
3. 把 paid-provider live rerun 做成标准化 workflow，并保持 `workflow_dispatch` 的手动复核入口。
4. 把 Gate 4 closeout 需要的工件目录、评分表和 provider matrix 固化为标准输出。

如果 Gate 4 没进入流水线，它就永远只是一份研究计划，不是正式工程能力。

---

## 7. 一条可行且明确的路线图

下面这条路线图按依赖顺序排列，不按愿望排序。

### Phase 0：范围冻结与盘点校正

**目标**

先把“Gate 4 到底要闭什么”说清楚，避免一边开发一边改靶。

**动作**

1. 冻结 3 个官方场景族与主应用。
2. 冻结 2 个 provider 档位：官方验收 provider + 成本对照 provider。
3. 清点 specialized app 的 `seedTemplateFiles`、`sceneModules`、本地 `scenes/` 资产，明确单一事实来源。
4. 修正文档与看板漂移，至少统一 README、TODO、目录说明和后续 closeout 文档口径。

**交付物**

1. Gate 4 官方场景清单。
2. 场景资产来源矩阵。
3. Gate 4 provider 角色说明。

**出口标准**

所有后续开发都能明确回答“这是哪个官方场景族”“由哪份 seed 资产生效”“用哪两个 provider 做正式比较”。

### Phase 1：Prompt 资产与 few-shot 闭环

**目标**

让场景化 prompt 真正进入执行链，而不是停留在 schema。

**动作**

1. 新增 few-shot 资产发现与加载机制。
2. 在 PromptCompiler 中把生效的 few-shot 编译到 `messages`。
3. 在 compile artifact、Prompt 控制面和 request transcript 中暴露最终 few-shot refs。
4. 为编码、研究、创作 3 个官方场景族各补 2 到 4 个高价值 few-shot。
5. 把 scene module 里的 `fewShotRefs` 从空数组补成正式引用。

**交付物**

1. few-shot 资产目录结构。
2. 编译链接线。
3. 3 个官方场景族的第一批 few-shot 包。

**出口标准**

在 Prompt 控制面中切换 app 后，除了 `promptProfileId`、`seedTemplateId` 变化之外，还能看到不同 few-shot refs 进入正式编译结果。

### Phase 2：官方场景族装配闭环

**目标**

把 3 个官方场景族做成真正可运行的应用模板，而不是只有名字和一份 profile。

**动作**

1. 为 `coding-greenfield`、`deep-research`、`epic-writing` 完成正式主应用装配。
2. 为每个主应用固定默认工具、默认检索、默认输出风格和默认场景模块。
3. 明确 secondary app 的继承关系：
   - 编码族：`software-factory`、`coding-inherit`
   - 研究族：`knowledge-studio`
   - 创作族：暂不把 `scenic-guide`、`learning-coach` 纳入正式出口
4. 清理 specialized app 目录中的孤儿 `scenes/` 资产或补上正式接线。

**交付物**

1. 3 个官方主应用的稳定 manifest。
2. 3 套正式场景模板。
3. 场景切换后的 Prompt 预览与工具装配快照。

**出口标准**

切换 3 个官方主应用时，运行时的默认工作方式、默认工具清单和默认输出合同都发生稳定且可解释的变化。

### Phase 3：功能性 Sub-Agent 与外部资料能力闭环

**目标**

把多场景都需要的“能力积木”从临时技巧升级为正式模块。

**动作**

1. 固化跨场景通用能力模块：资料导入、批量阅读、上下文清理、结构重组。
2. 固化场景验收型能力模块：编码验证、研究证据审查、创作连续性审查。
3. 明确哪些能力默认隐式运行，哪些能力必须显式暴露给用户。
4. 补齐网络抓取、资产导入导出、来源记录和权限申请链路。

**交付物**

1. 功能性 Sub-Agent 模块清单。
2. 能力级工具契约。
3. 权限与审计说明。

**出口标准**

至少 2 个官方场景族能共享同一批功能性能力模块，而不需要为每个场景重新造一套隐式工具。

### Phase 4：Gate 4 正式评测与 provider 矩阵

**目标**

把“多场景泛化”做成可以证伪的正式门禁。

**动作**

1. 新增 Gate 4 正式套件：建议拆为 `g4-coding`、`g4-research`、`g4-writing`，再补一个汇总 `g4-multiscene`。
2. 每个场景族都补 3 类任务：
   - 快任务
   - 跨会话任务
   - 恢复类任务
3. 在官方验收 provider 与成本对照 provider 上跑同一批任务。
4. 产出 provider 质量矩阵与场景差异分析。

**交付物**

1. Gate 4 suite 定义文件。
2. 多场景 scorecard 模板。
3. provider 质量矩阵报告。

**出口标准**

1. 官方验收 provider 在 3 个官方场景族上的正式样本全部通过。
2. 成本对照 provider 至少达到可接受通过率，且不存在静默破坏任务合同的情况。
3. 场景切换污染测试通过，不会把上一场景默认行为错误带入下一场景。

### Phase 5：流水线、收尾与正式 closeout

**目标**

把 Gate 4 变成可以长期守住的正式工程能力。

**动作**

1. 把 `eval:g2:regression` 纳入手动 `release-check`。
2. 把 `g4-multiscene` 纳入 `release-check`；日常开发阶段继续按改动只跑受影响测试。
3. 把 paid-provider live rerun 做成标准化 workflow 或标准操作文档。
4. 回写质量基线、目录说明、用户/开发者入口文档与 Gate 4 closeout 报告。

**交付物**

1. 更新后的 CI / release gate。
2. Gate 4 closeout 报告。
3. 更新后的质量基线与目录索引。

**出口标准**

任何一次应用资产、provider 路由、few-shot 或场景工具的改动，都能被固定回归或 live rerun 及时发现。

---

## 8. 我建议采用的正式出口标准

为了让 Gate 4 的“完美实现”可操作，我建议采用下面这组标准：

1. 3 个官方场景族都各自有一套正式 suite，并全部通过官方验收 provider 复跑。
2. 每个场景族至少覆盖快任务、跨会话任务、恢复类任务各 1 个正式样本。
3. `human_takeover_count` 的中位数为 0。
4. `user_clarification_rounds` 的中位数不高于 1，且不能出现“用户替系统做技术选型”的情况。
5. `planQualityScore0_100` 的中位数不低于 90。
6. `reworkRate` 的中位数不高于 0.25。
7. 恢复类任务在官方验收 provider 下成功率为 100%。
8. Prompt compile artifact 必须显式记录 `promptProfileId`、`seedTemplateId`、生效 few-shot refs、provider 和场景。
9. `eval:g2:regression` 与至少 1 个 Gate 4 suite 已进入正式 `release-check` 流水线。

这组标准已经足够严格，同时又建立在当前仓库已有 scorecard 和运行时能力之上，因此是可执行的。

### 8.1 2026-05-16 优先级补充

Gate 4 基础闭环完成后，当前最关键的下一步已经不是继续扩应用数量，而是把“伪无限上下文窗口 / 长任务多次窗口重启”补成 Gate 4 的完美实现要求。

当前建议新增 3 条强约束：

1. 把“记忆树是主体、上下文窗口只是工作集”明确为当前正式工程口径。
2. 把 `restart protocol + restart controller + carry-forward package + work tree continuity` 提升为 Gate 4 后续第一优先级。
3. 新增长任务 stress 评测：手动限制有效窗口，要求同一任务经历 100 次上下文窗口重启/压缩，并与更长上下文窗口 reference 路径比较最终效果。

---

## 9. 明确不该在 Gate 4 里一起做的事

为了让路线可行，下面这些事不应与 Gate 4 一起捆绑：

1. 不把 10 个应用都纳入 Gate 4 正式出口。
2. 不在 Gate 4 期间重开工作树或超图推理的大范围协议升级。
3. 不把 training-lab、prompt A/B 和自我优化闭环提前并入 Gate 4 主线；那是 Gate 5 的事。
4. 不因为 specialized app 已经有本地 `scenes/` 文件，就默认认为它们已经进入正式执行链。
5. 不让单一 provider 的好结果直接替代跨 provider 正式矩阵。

---

## 10. 最终判断

我的判断是：

> **Gate 4 现在最正确的推进方式，不是继续扩应用数量，而是把“3 个官方场景族 + few-shot 执行链 + 功能性能力模块 + 多场景评测 + 跨 provider 质量矩阵 + CI 门禁”做成同一条正式工程链。**

如果上述路线按顺序执行，Gate 4 是可行的；而且它会以当前 G3 基线为基础自然推进，不需要返工底层 runtime。

如果不按这条路线推进，而是继续同时扩更多应用、更多研究协议、更多未来能力，Gate 4 大概率会退化成“看起来很多场景都能切，但没有一个场景被正式验证”。

这就是当前仓库下，完美实现 Gate 4 的最可行路线。