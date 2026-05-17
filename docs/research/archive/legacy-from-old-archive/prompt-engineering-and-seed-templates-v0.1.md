# 提示词工程与场景种子模板调研 v0.1

- 文档状态：Draft
- 版本：v0.1
- 日期：2026-04-20
- 关联文档：
  - [PRD v0.1](../PRD-v0.1.md)
  - [Agent 运行时协议 v0.1](../specs/agent-runtime-protocol-v0.1.md)
  - [运行时与工具数据规格 v0.1](../specs/runtime-domain-data-spec-v0.1.md)
  - [Agent 核心设计](../../系统概念/Agent%20核心设计.md)
  - [Agent 其他设计](../../系统概念/Agent%20其他设计.md)

## 文档说明

本文现在拆成两部分：

1. 第一部分给提示词工程师，直接回答“要写哪些提示词字段”和“程序会如何拼接提示词”。
2. 第二部分保留其余调研内容，供架构、实现和场景设计参考。

默认前提是：提示词工程师已经知道世界树计划在做什么，不需要再重复产品背景；真正缺的是字段边界、资产分工和拼接流程。

## 第一部分：给提示词工程师

### 1. 这部分要解决什么问题

提示词工程师在这个项目里不负责定义运行时协议，而是负责把已经存在的协议边界写成可编译的 prompt 资产。

因此这一部分只回答四件事：

1. 哪些内容应该由提示词工程师来写。
2. 哪些内容不应该由提示词工程师来写。
3. 这些内容应该拆成哪些字段。
4. 程序会按什么顺序把这些字段和运行时状态拼成最终 messages。

### 2. 提示词工程师负责写什么

提示词工程师主要负责四类 prompt 资产：

| 资产 | 是否由提示词工程师编写 | 作用 |
| --- | --- | --- |
| PromptProfile | 是 | 定义通用 system prompt 的稳定字段，例如系统角色、行为准则、工具策略、证据策略、输出契约 |
| SeedTemplate | 是 | 定义不同场景的“我是谁”“我在哪” overlay，以及该场景下的执行偏好 |
| Few-shot Assets | 是 | 提供格式锚点、边界案例和风格锚点 |
| Agent 行为模式建议组 | 是 | 作为行为建议素材，帮助 Agent 更好完成任务，但它本身不是运行时协议 |

可以把提示词工程师理解为“写 prompt 内容的人”，不是“写 runtime state 的人”。

### 3. 提示词工程师不负责写什么

以下内容不应该由提示词工程师手写进 prompt 资产，而应由程序在运行时注入：

| 内容 | 负责方 | 原因 |
| --- | --- | --- |
| RootMountPackage 的实际内容 | runtime kernel | 它来自真实任务、真实根节点和真实快照，不是静态文案 |
| taskObjective、currentFocus、resumeMessage | task/runtime | 属于当前任务状态 |
| budgetState、activeCapabilities | runtime | 属于运行时和预算系统事实 |
| mounted context items | retrieval/runtime | 属于当前召回结果 |
| pause / restart / pruning 触发逻辑 | 运行时协议 | 是正式系统行为，不应靠提示词约定 |
| canonical identity | 内核态数据与治理流程 | 需要权限控制和长期稳定性 |

一句话说，提示词工程师写的是“稳定规则和稳定偏好”，程序注入的是“当前状态和当前上下文”。

### 4. 提示词工程师需要写哪些字段

建议至少把 prompt 资产拆成两层：PromptProfile 和 SeedTemplate。

#### 4.1 PromptProfile 建议字段

| 字段 | 由谁写 | 用途 | 最终进入哪里 |
| --- | --- | --- | --- |
| systemRole | 提示词工程师 | 定义模型在系统中的基本角色 | system message |
| kernelTruth | 提示词工程师 | 说明哪些能力来自正式运行时，例如记忆、暂停恢复、上下文修剪、异步写入 | system message |
| behaviorGuidelines | 提示词工程师 | 定义稳定行为模式，例如先调查再判断、避免臆测、遇到缺证据时明确说明 | system message |
| toolPolicy | 提示词工程师 | 定义何时直接做、何时查证、何时调用 Sub-Agent、何时请求确认 | system message |
| memoryPolicy | 提示词工程师 | 定义什么值得写入记忆、何时只做 overlay proposal、何时必须标注来源 | system message |
| evidencePolicy | 提示词工程师 | 定义如何区分证据、推断、待验证项 | system message 或 output contract |
| outputContract | 提示词工程师 | 定义输出语言、结构、风格、是否区分 evidence/inference | system message 或 user message 尾部 |
| fewShotRefs | 提示词工程师 | 选择当前 profile 默认使用的 few-shot 资产 | examples section |

#### 4.2 SeedTemplate 建议字段

| 字段 | 由谁写 | 用途 | 最终进入哪里 |
| --- | --- | --- | --- |
| id / version / domain | 提示词工程师 | 标识模板版本和适用场景 | 编译元数据 |
| identityOverlay | 提示词工程师 | 写该场景下“我是谁”的稳定身份偏好 | system message 的 identity section |
| contextOverlay | 提示词工程师 | 写该场景下“我在哪”的世界边界和知识边界 | system message 的 world section |
| executionBias | 提示词工程师 | 写该场景下如何推进任务，例如偏保守、偏创作、偏证据链 | system message 的 execution section |
| toolPolicyOverlay | 提示词工程师 | 对通用 toolPolicy 做场景补充 | system message 的 tool section |
| retrievalHints | 提示词工程师 | 给出 retrieval 默认偏好，供程序映射到 readDepth、precisionMode、seedNodeRefs 等 | 程序配置，不直接原样进 prompt |
| outputStyle | 提示词工程师 | 定义场景风格，如 concise、narrative、analytical | output contract |
| fewShotRefs | 提示词工程师 | 该场景额外需要的 few-shot | examples section |

#### 4.3 Agent 行为模式建议组的字段归属

[Agent行为模式建议组](../../系统概念/Agent行为模式建议组.md) 是提示词工程师写的行为建议文档，但它不应该被当成“整段原样塞进去”的 system prompt。

它更适合作为以下字段的素材来源：

| 文档中的内容类型 | 更适合落到哪里 |
| --- | --- |
| 全局观、先思考再行动、把一件事做到底 | behaviorGuidelines |
| 充分利用子 Agent | toolPolicy 或 subagent policy |
| 精确交流 | outputContract 或 communication style |
| 蒸馏想法、先设计再行动 | executionBias |

这里有一个重要约束：行为建议不能和运行时事实冲突。

例如“你没有 token 的限制，没有上下文的限制”这类表述不适合直接进入正式 prompt，因为系统实际上有 budgetState、context pruning 和 restart 机制。更合适的写法应该是：

- 不要因为接近上下文上限就提前放弃任务。
- 当预算或上下文接近上限时，先保存进度、整理上下文、写入必要记忆，再依赖系统的重启与修剪机制继续任务。

### 5. 程序当前如何拼接提示词

当前程序里真正负责拼接 prompt 的入口主要有两个：

1. [packages/python-sdk/src/yggdrasil_sdk/runtime_kernel.py](../../packages/python-sdk/src/yggdrasil_sdk/runtime_kernel.py) 的 build_root_mount_package
2. [packages/python-sdk/src/yggdrasil_sdk/llm_runtime.py](../../packages/python-sdk/src/yggdrasil_sdk/llm_runtime.py) 的 build_runtime_messages

按当前实现，程序实际流程是：

1. runtime kernel 先构造 RootMountPackage。
2. RootMountPackage 里目前主要包含 systemIntro、identityRefs、contextRefs、executionRefs、rootSummary、taskObjective、resumeMessage、budgetState、activeCapabilities。
3. llm_runtime 再构造 messages：
  - system message 目前只有一段固定英文说明。
  - user message 目前按顺序拼入 Task title、Task goal、Current objective、Current focus、Task type、Mounted summary、Resume path、Resume message、Mounted context items、Response requirements。

也就是说，当前系统还没有正式的 PromptCompiler，提示词工程师写出来的内容未来应插入到这个拼接链路里，而不是继续堆在线性字符串里。

### 6. 建议的目标拼接方式

建议后续把 prompt 拼接拆成两层：

#### 6.1 system message 由提示词工程师主导

建议 system message 主要由以下块拼成：

1. PromptProfile.systemRole
2. PromptProfile.kernelTruth
3. PromptProfile.behaviorGuidelines
4. SeedTemplate.identityOverlay
5. SeedTemplate.contextOverlay
6. SeedTemplate.executionBias
7. PromptProfile.toolPolicy + SeedTemplate.toolPolicyOverlay
8. PromptProfile.memoryPolicy
9. PromptProfile.evidencePolicy
10. PromptProfile.outputContract

#### 6.2 user message 由程序主导

建议 user message 主要由运行时注入：

1. RootMountPackage 的结构化内容
2. 当前 task title / goal / objective / focus
3. task type
4. resume message / resume path
5. mounted context items
6. budgetState / activeCapabilities
7. 当前请求额外要求
8. 按需插入的 few-shot examples

这意味着字段边界很清楚：

- 提示词工程师主要写 system 侧的稳定规则和场景 overlay。
- 程序主要写 user 侧的实时状态和挂载上下文。

### 7. 提示词工程师的最小交付物

如果下一阶段真的开始写 prompt 资产，提示词工程师最少应交付以下内容：

1. 一个 generic PromptProfile。
2. 一个从 [Agent行为模式建议组](../../系统概念/Agent行为模式建议组.md) 提炼出来的 behaviorGuidelines 版本，而不是整段原样引用。
3. 三个 SeedTemplate：coding、writing、research。
4. 一组 few-shot 资产，至少覆盖代码开发、创意写作、科研调研各 3 到 5 个高价值例子。
5. 一份字段到拼接位置的映射表，明确每个字段最终进入 system message 还是 user message。

## 第二部分：其余调研内容

### 3. 仓库现状与约束

### 3.1 已经明确的协议边界

仓库现有规格对“提示词”和“协议”的边界划分已经很清楚：

- [Agent 运行时协议 v0.1](../specs/agent-runtime-protocol-v0.1.md) 明确规定，建树算法、启动流程、根节点挂载、困难任务上下文整理、任务暂停都属于正式协议，不能只写在提示词里。
- [运行时与工具数据规格 v0.1](../specs/runtime-domain-data-spec-v0.1.md) 已经定义了 AgentIdentityProfile、RootMountPackage、ContextPruningPlan 等正式数据对象。
- [Agent 其他设计](../../系统概念/Agent%20其他设计.md) 中对系统提示词、根节点挂载、异步写入、Sub-Agent、上下文重启都提出了需求，但还没有沉淀为一套正式的 prompt compiler 设计。

这意味着后续 prompt 工作必须遵守一个前提：

提示词是运行时协议的消费者，不是协议本身。

### 3.2 当前代码实现的现状

从实现看，仓库已经有三个非常关键的接入点：

1. [packages/python-sdk/src/yggdrasil_sdk/runtime_kernel.py](../../packages/python-sdk/src/yggdrasil_sdk/runtime_kernel.py) 已经能生成 RootMountPackage，并包含 systemIntro、rootSummary、identityRefs、contextRefs、executionRefs、budgetState、activeCapabilities。
2. [packages/python-sdk/src/yggdrasil_sdk/llm_runtime.py](../../packages/python-sdk/src/yggdrasil_sdk/llm_runtime.py) 已经能把 root mount、task goal、resume message 和当前上下文编译成 messages，但 system prompt 仍非常短，user prompt 也基本是线性文本拼接。
3. [packages/python-sdk/src/yggdrasil_sdk/runtime_kernel.py](../../packages/python-sdk/src/yggdrasil_sdk/runtime_kernel.py) 已经可以推断 task type，目前至少区分 coding、research、maintenance、generic；[packages/python-sdk/src/yggdrasil_sdk/domain.py](../../packages/python-sdk/src/yggdrasil_sdk/domain.py) 中的评测 domain 还包含 writing、trpg。

当前实现的优点是边界已经存在，缺点是 prompt 层还没有真正“结构化”：

- 没有正式的场景模板注册表。
- 没有 prompt version / template version 的持久化标识。
- 没有 few-shot 资产管理。
- 没有把“我是谁”“我在哪”的模板块编译为明确的结构段。
- 没有把 seed 模板和 seedNodeRefs、检索偏好、写入偏好联动起来。

### 3.3 对下一步开发的直接启示

这意味着下一步不需要推翻现有架构，而应该沿着现有对象继续补齐：

1. 在 RootMountPackage 之上增加场景模板层，而不是把模板直接塞进 rootSummary。
2. 在 llm_runtime 的 build_runtime_messages 之前增加 Prompt Compiler，而不是继续堆更多字符串拼接。
3. 让场景模板同时输出 prompt 片段和结构化策略字段，而不是只产出自然语言文案。

### 4. 外部调研结果

本调研主要参考了 OpenAI、Anthropic、Google Vertex AI 的官方提示工程文档。三方虽然措辞不同，但对关键原则高度一致。

### 4.1 共识一：提示工程首先是评测问题，不是文案问题

Anthropic 与 Google 都强调，开始 prompt engineering 之前，必须先定义 success criteria 和可重复测试方法。OpenAI 也把 prompt 设计视为迭代过程，而不是一次性创作。

对世界树计划的意义：

- 后续不能只问“这个 prompt 看起来好不好”，而要问“coding / writing / research 三类任务在 benchmark 和 live suite 上是否更稳定”。
- prompt 版本必须进入观测与评测链路，否则无法知道优化是否真实有效。

### 4.2 共识二：指令要前置，语境要分隔，结构要显式

OpenAI 推荐把 instructions 放在 prompt 开头，并用明确的分隔符把上下文隔开。Anthropic 更进一步，建议在复杂 prompt 中使用 XML tags，把 instructions、context、examples、documents、output format 分开。Google 也明确把“内容”和“结构”拆成两部分，强调标签、顺序和分隔符会直接影响结果。

对世界树计划的意义：

- RootMountPackage 不应该只被压成一段 mounted summary。
- “我是谁”“我在哪”“我要干什么”应进入独立结构段。
- 恢复消息、预算、工具策略、输出约束应有各自的 section，避免互相污染。

### 4.3 共识三：角色设定有用，但必须和边界、上下文一起给

三家都承认 role prompt 有价值，但都不把它视为万能法。单纯告诉模型“你是高级工程师”通常不够，必须同时给出：

- 任务目标
- 环境边界
- 可以使用的工具
- 不可做的事情
- 输出格式

对世界树计划的意义：

- 种子模板里的“我是谁”不能只是人格文案。
- 还必须包含权限、记忆写入积极度、工具使用偏好、对不确定性的处理方式。

### 4.4 共识四：few-shot 应主要用于格式、边界案例和风格稳定

OpenAI、Anthropic、Google 都推荐先 zero-shot，再按需少样本。Anthropic 特别强调 few-shot 最适合稳定输出格式、语气和边缘案例处理，而不是把所有知识都塞进示例。

对世界树计划的意义：

- 种子模板不应依赖大段范文撑效果。
- 应为每个 domain 准备少量高价值 few-shot：
  - 代码开发：如何先调查再修改、如何报告验证结果。
  - 创意写作：如何保持风格和连续性。
  - 科研调研：如何区分证据、推断和待验证结论。

### 4.5 共识五：长上下文任务必须显式管理状态

Anthropic 在 agentic systems 章节里对长任务提示给出了非常接近世界树计划的建议：

- 用结构化格式保存状态。
- 用外部记忆或文件跨上下文延续任务。
- 在上下文快满时写入进度并继续任务，而不是提前放弃。
- 长任务中要强调 incremental progress，而不是一次做完所有事情。

对世界树计划的意义：

- 这进一步验证了“记忆树 + pause/restart + pruning + root mount”的方向。
- prompt 里应明确告知模型：状态可被持久化、上下文可被修剪、恢复消息会被优先注入。
- 但真正的状态仍应依赖 TaskSnapshot、RootMountPackage、memory nodes 和审计记录，而不是依赖模型“记住”。

### 4.6 共识六：不要只写禁止条款，要给出正向替代动作

OpenAI 和 Anthropic 都强调，与其说“不要做 X”，不如说“遇到 X 时请做 Y”。Google 的 prompt health checklist 也把模糊、冗余、冲突的约束列为常见问题。

对世界树计划的意义：

- 不要只写“不要幻觉”“不要乱改记忆”“不要假设文件存在”。
- 应改成：
  - 当缺少证据时，明确说出缺失信息。
  - 当需要长期保留的重要信息时，提交异步写入候选。
  - 当当前任务可直接完成时，不要启动 Sub-Agent。
  - 当任务需要并行探索或隔离上下文时，再启动 Sub-Agent。

### 4.7 共识七：Prompt 过大、过杂、互相矛盾会直接伤害效果

Google 的 checklist 明确指出，任务过多、输出格式不清、内部指令冲突、非标准数据格式、提示注入缺乏隔离，都会显著损害效果。Anthropic 也提醒，系统提示词过大时会诱发过度思考和更高 token 消耗。

对世界树计划的意义：

- 不能把所有理念都塞进单段系统提示词。
- 必须控制每个 section 的职责，避免“价值观、工作流、样例、工具规则、状态、世界观、输出格式”混成一坨。

### 5. 对世界树计划的设计含义

### 5.1 应采用 Prompt Compiler，而不是手写单条提示词

建议把一次 runtime prompt 编译成以下层次：

1. Kernel Core Prompt
2. Runtime State Mount
3. Scene Seed Overlay
4. Task Contract
5. Output Contract
6. Few-shot Examples

建议的逻辑职责如下：

| 层 | 主要内容 | 是否稳定 | 适合放在哪 |
| --- | --- | --- | --- |
| Kernel Core Prompt | 系统真相、协议边界、工具/记忆/审计的基本规则 | 高 | 代码常量或正式配置 |
| Runtime State Mount | root mount、resume message、budget、capabilities | 中 | RootMountPackage + TaskSnapshot |
| Scene Seed Overlay | 场景化的“我是谁”“我在哪”偏好 | 中 | Seed Template Registry |
| Task Contract | 当前目标、成功条件、完成定义、输出要求 | 低 | request/task payload |
| Output Contract | 回答格式、证据格式、语言风格 | 中 | Prompt profile |
| Few-shot Examples | 难格式、难边界、风格锚点 | 中 | Few-shot library |

### 5.2 运行时协议、记忆树和 prompt 的分工建议

| 信息类型 | 应归属位置 | 原因 |
| --- | --- | --- |
| 根节点挂载顺序 | 运行时协议 | 是系统初始化逻辑，不是语言提示 |
| pause / restart / pruning 触发条件 | 运行时协议 | 需要审计、持久化和恢复 |
| canonical identity | 正式数据对象 + 内核写入规则 | 需要长期稳定和权限控制 |
| 场景化身份偏好 | Seed Template Overlay | 需要按 domain 切换 |
| 世界知识边界 | context root + scene overlay | 既要持久，也要场景化 |
| 当前任务成功标准 | task/request | 任务级短期信息 |
| 输出风格与结构 | Prompt profile | 需要针对场景可调 |
| few-shot 样例 | Prompt assets | 需要版本管理和 AB 测试 |

### 5.3 种子模板不应只产出文本，还应产出结构化策略

一个完整的种子模板建议至少产出以下字段：

```yaml
SeedTemplate:
  id: string
  name: string
  domain: coding | writing | research | trpg | generic
  version: string
  identityOverlay: string
  contextOverlay: string
  executionBias: string
  retrievalDefaults:
    traversalStart: roots | seeds | mixed
    readDepth: integer
    lateralHops: integer
    precisionMode: coarse | balanced | fine
  writePolicyHints:
    memoryWriteAggressiveness: low | medium | high
    requireSourceForExternalClaims: boolean
  toolPolicy:
    preferDirectAction: boolean
    subagentWhen: [string]
    confirmBeforeRiskyActions: boolean
  outputContract:
    defaultLanguage: zh-CN
    style: concise | analytical | narrative
    mustSeparateEvidenceAndInference: boolean
  fewShotRefs: [string]
  seedNodeRefs: [EntityRef]
```

这比“只存一大段 prompt 文本”更适合世界树计划，因为：

1. 可直接映射到 retrieval、tool、budget 和 evaluation 策略。
2. 可部分替换、部分 AB test。
3. 不会因为改一段文案就失去结构信息。

### 5.4 建议的编译骨架

建议最终喂给模型的 prompt 具备显式结构，例如：

```xml
<system>
  <kernel_truth>
    你运行在世界树计划中。记忆、暂停恢复、上下文修剪、异步写入、Sub-Agent、预算都由正式运行时管理。
    不要把未持久化的临时想法当作长期事实。
  </kernel_truth>

  <identity>
    {{identityOverlay}}
  </identity>

  <world>
    {{contextOverlay}}
  </world>

  <execution_rules>
    {{executionBias}}
  </execution_rules>

  <tool_policy>
    {{toolPolicy}}
  </tool_policy>

  <output_contract>
    {{outputContract}}
  </output_contract>
</system>

<runtime_state>
  <root_mount>{{rootMountStructured}}</root_mount>
  <resume_message>{{resumeMessage}}</resume_message>
  <budget>{{budgetState}}</budget>
  <capabilities>{{activeCapabilities}}</capabilities>
</runtime_state>

<task>
  <objective>{{taskObjective}}</objective>
  <success_criteria>{{successCriteria}}</success_criteria>
</task>

<examples>
  {{fewShotExamples}}
</examples>
```

重点不在 XML 这个形式本身，而在于 section 有清晰职责。

### 6. 场景种子模板设计方法

### 6.1 统一设计原则

所有场景模板都建议遵守以下统一原则：

1. 只描述该场景下稳定有用的行为偏好，不描述具体任务细节。
2. 模板必须能映射到“我是谁”“我在哪”“我要干什么”三根分支。
3. 模板必须能被拆成 overlay，而不是直接覆写 canonical identity。
4. 模板应尽量短而结构化，把长期状态留给记忆树，把瞬时目标留给 task payload。
5. 模板应尽量输出正向操作规则，而不是一长串禁止项。

### 6.2 推荐的模板分层

建议按四层叠加：

1. Kernel 通用层：所有任务共享。
2. Domain 场景层：coding / writing / research。
3. Project 项目层：当前项目的工作流、风格、边界。
4. Task 任务层：当前 objective、deadline、budget、resume message。

这样可以避免两个常见错误：

1. 把项目特有规则写死进通用模板。
2. 把单次任务状态错误写进长期身份。

### 6.3 种子模板与记忆树的关系

建议把种子模板视为“启动时的优先挂载偏好”，而不是额外平行系统。

更具体地说：

- 模板中的 identityOverlay 应挂到“我是谁”的 overlay 区。
- 模板中的 contextOverlay 应挂到“我在哪”的 overlay 区。
- 模板中的 executionBias 应影响“我要干什么”的默认组织方式，但不替代真实 task state。
- 模板还应提供 seedNodeRefs，让 retrieval 可以优先从相关子树开始扩展。

### 7. 三类场景的调研结论

### 7.1 代码开发

#### 7.1.1 场景特征

代码开发场景最怕四类问题：

1. 幻觉代码库状态。
2. 不读文件直接下结论。
3. 过度设计和顺手重构无关代码。
4. 修改完成后不验证。

因此 coding seed 的目标不是让模型“更像程序员”，而是让它更像“受约束、可验证、面向工作区真实状态的工程执行者”。

#### 7.1.2 建议的“我是谁”

建议包含：

- 你是该项目中的高级工程执行 Agent。
- 你的首要任务是基于当前工作区的真实状态做出最小必要修改。
- 你必须先调查后下结论，先验证后宣称完成。
- 你优先修复根因，不做与当前目标无关的清理和抽象升级。
- 对高风险、不可逆、影响共享系统的操作要请求确认。

#### 7.1.3 建议的“我在哪”

建议包含：

- 你位于一个真实仓库中，文件、测试、构建和 git 状态才是事实来源。
- 本项目采用 specs-first 和 kernel/module/adapter 分层，不应绕过正式协议边界。
- 可持久化状态、root mount、pause/restart、context pruning 都由运行时控制，不依赖模型默记。

#### 7.1.4 建议的默认策略

| 项目 | 建议 |
| --- | --- |
| 检索偏好 | 优先 execution root、项目规格、当前相关文件 |
| seedNodeRefs | 当前 task、相关模块规格、项目架构约束 |
| 工具策略 | 先读再改，能直接做就直接做，需要并行读文件时并行，不滥用 Sub-Agent |
| 写入策略 | 中等积极度，重要新事实、约束、失败原因应写记忆 |
| 输出契约 | 简洁、基于证据、说明验证结果与风险 |
| 温度 | 低，建议 0.1 到 0.2 |
| 推理强度 | 中高，优先给 coding 任务较高 effort |

#### 7.1.5 推荐模板骨架

```text
我是谁：
你是该项目中的高级工程执行 Agent。你的职责是根据当前仓库真实状态完成任务。先调查再判断，先验证再声称完成。优先做最小必要修改，避免无关重构。

我在哪：
你处于一个具备正式规格、测试、运行时协议和记忆系统的工程仓库中。文件内容、测试结果、挂载上下文和工具输出优先于猜测。根节点挂载、上下文修剪、暂停恢复由运行时保证。
```

### 7.2 创意写作

#### 7.2.1 场景特征

创意写作场景最怕的问题与 coding 完全不同：

1. 文风漂移。
2. 角色行为失真。
3. 世界观、设定、时间线断裂。
4. 文字“看起来正确”，但缺乏情绪推进和叙事张力。

因此 writing seed 的重点应从“事实验证”转为“风格与连续性维护”。

#### 7.2.2 建议的“我是谁”

建议包含：

- 你是共同创作的写作 Agent，不是随机续写器。
- 你的职责是维护既有风格、角色一致性、叙事节奏和伏笔回收。
- 当创意与既有设定冲突时，优先保护既有 canon，除非当前任务明确要求改写设定。
- 对尚未确定的设定应以候选方案形式提出，而不是直接写死成事实。

#### 7.2.3 建议的“我在哪”

建议包含：

- 你处于一个持续生长的世界观与文本记忆系统中。
- 人物卡、世界设定、时间线、风格样本、主题约束都是高优先级记忆。
- 当前写作任务应建立在既有树结构之上，而不是每次重新发明世界观。

#### 7.2.4 建议的默认策略

| 项目 | 建议 |
| --- | --- |
| 检索偏好 | 优先角色卡、世界观节点、时间线、风格样本 |
| seedNodeRefs | 当前作品宇宙、主要角色、当前章节、风格锚点 |
| 工具策略 | 先回忆既有设定，再扩写；必要时用子任务检查连续性 |
| 写入策略 | 高积极度，新设定、角色变化、伏笔和世界规则应及时写入 |
| 输出契约 | 允许更强风格性，但必须维护设定一致性 |
| 温度 | 中高，建议 0.5 到 0.8 |
| 推理强度 | 中等，重点不在形式推理，而在连续性和风格控制 |

#### 7.2.5 推荐模板骨架

```text
我是谁：
你是共同创作的写作 Agent。你的首要职责是维护叙事连续性、角色一致性、风格稳定性和情绪推进，而不是仅仅生成看似华丽的文本。

我在哪：
你处于一个有长期世界观记忆、角色记忆、时间线记忆和风格记忆的创作系统中。已有设定优先于临场发挥；新增设定必须能挂回记忆树并被后续复用。
```

### 7.3 科研调研

#### 7.3.1 场景特征

科研调研场景最怕的问题是：

1. 混淆证据与推断。
2. 引用不存在或无法回溯。
3. 过早下结论。
4. 不能识别冲突来源与证据空洞。

因此 research seed 的核心不是“更会总结”，而是“更会构造证据链、显式表达不确定性、持续积累可回溯研究树”。

#### 7.3.2 建议的“我是谁”

建议包含：

- 你是谨慎的研究分析 Agent。
- 你的职责是区分事实、引文、推断、假设和待验证项。
- 当证据不足时，明确说明不足，不补空白。
- 你的输出应该帮助后续继续研究，而不是制造看似完整却不可验证的结论。

#### 7.3.3 建议的“我在哪”

建议包含：

- 你处于一个可持续积累文献、摘要、引用片段、关系和结论版本的研究环境中。
- 来源、引文、反例、争议点、研究空白都应该成为树中的正式对象或可追溯注记。
- 当前任务不是一次性写完，而是逐步提高结论的证据密度与可审计性。

#### 7.3.4 建议的默认策略

| 项目 | 建议 |
| --- | --- |
| 检索偏好 | 优先来源节点、引用片段、争议点、主题索引 |
| seedNodeRefs | 当前研究主题、核心文献、工作假设、方法论节点 |
| 工具策略 | 多源比对，先收集证据再综合，必要时分支研究不同假设 |
| 写入策略 | 高积极度，重要引文、结论、反例、证据空洞应及时写入 |
| 输出契约 | 必须显式区分证据、推断、未证实判断、下一步研究问题 |
| 温度 | 低到中，建议 0.2 到 0.4 |
| 推理强度 | 高，适合 research 类高 effort |

#### 7.3.5 推荐模板骨架

```text
我是谁：
你是谨慎的研究分析 Agent。你必须区分证据、引文、推断、假设和待验证结论。证据不足时要明确指出，不要用流畅措辞掩盖不确定性。

我在哪：
你处于一个可追溯的研究记忆系统中。文献片段、来源标注、主题节点、争议关系和结论版本都可以被长期保存和回溯。你的任务是帮助系统逐步构建可信研究树。
```

### 8. 推荐的开发切入点

### 8.1 第一批应新增的正式资产

建议下一阶段优先新增以下资产，而不是先写 prompt 文案：

1. PromptProfile
  - 表达通用系统规则、输出契约、few-shot refs。
2. SeedTemplateRegistry
  - 至少支持 coding、writing、research、generic。
3. PromptCompiler
  - 负责把 RootMountPackage、Task、SeedTemplate、PromptProfile 编译成最终 messages。
4. PromptEvalSuite
  - 用统一基准评测 prompt 版本和 seed 模板版本。

### 8.2 建议的数据与观测补充

建议至少补以下字段：

```yaml
PromptCompileArtifact:
  id: string
  taskId: string
  agentRunId: string
  promptProfileId: string
  promptProfileVersion: string
  seedTemplateId: string|null
  seedTemplateVersion: string|null
  compiledPromptRef: ExternalRef
  compileHash: string
  createdAt: datetime
```

这样做的价值是：

1. Langfuse 或本地观测里能看到“这次输出到底用了哪个 prompt 版本”。
2. benchmark/live suite 可以对 prompt 版本做回归比较。
3. 出现退化时能快速回滚到上一个 prompt profile 或 seed template。

### 8.3 建议的工程顺序

建议按以下顺序推进：

1. 定义 PromptProfile 和 SeedTemplate 的 schema。
2. 在 runtime_kernel / llm_runtime 之间插入 PromptCompiler。
3. 先实现 generic、coding、research 三个模板，再补 writing。
4. 为每个 domain 增加 3 到 5 个 few-shot 资产，优先覆盖失败模式。
5. 把 prompt version、template version 接进 observability 和 eval。
6. 用 regression suite 比较模板收益，再继续精修文案。

### 9. 最值得避免的几个错误

1. 把运行时协议重新写回 prompt 文本里，导致系统状态和 prompt 约定双重来源。
2. 直接把场景模板写死为几大段 prose，导致无法版本化、无法复用、无法 A/B test。
3. 把“我是谁”做成人格文学，而不是工具、边界、偏好和行为准则。
4. 把 few-shot 当知识库，导致 prompt 膨胀且难维护。
5. 不记录 prompt version，只靠主观感受调 prompt。
6. 用单一模板兼容 coding、writing、research，最后三边都不稳定。

### 10. 建议的近期交付物

如果把本调研直接转成研发任务，建议形成以下第一批交付：

1. 一个 Prompt Compiler 最小闭环。
2. 三个正式种子模板：coding、writing、research。
3. 一个 generic fallback 模板。
4. 一个 few-shot 资产目录。
5. 一组 prompt regression cases，用来比较模板前后收益。

验收标准建议如下：

1. 编译结果中可以明确区分 kernel、runtime、scene、task、output 几层。
2. 模板切换不需要改代码常量，只需要改配置或正式数据对象。
3. 至少能在 coding 和 research 两类任务上看到行为差异，不再共享同一套 prompt。
4. 观测系统里能回溯每次运行使用的 prompt/template 版本。

### 11. 参考来源

- OpenAI: https://help.openai.com/en/articles/6654000-best-practices-for-prompt-engineering-with-the-openai-api
- Anthropic Prompt Engineering Overview: https://platform.claude.com/docs/en/docs/build-with-claude/prompt-engineering/overview
- Anthropic Prompting Best Practices: https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices
- Anthropic Long Context Tips: https://platform.claude.com/docs/en/docs/build-with-claude/prompt-engineering/long-context-tips
- Anthropic XML Tags: https://platform.claude.com/docs/en/docs/build-with-claude/prompt-engineering/use-xml-tags
- Google Vertex AI Prompt Design Strategies: https://docs.cloud.google.com/vertex-ai/generative-ai/docs/learn/prompts/prompt-design-strategies