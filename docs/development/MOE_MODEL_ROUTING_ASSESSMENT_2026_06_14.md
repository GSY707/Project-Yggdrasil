# 世界树 Agent MoE 模型分层与任务难度评估（2026-06-14）

## 1. 范围与结论

本版重新限定为 2026 年 3 月后公开或明显更新的开源 / 开放权重 MoE、稀疏激活或混合稀疏架构模型。旧版里的 Qwen3-30B-A3B、Qwen3-Next、Qwen3-Coder-480B、Kimi K2、DeepSeek V3/R1、MiniMax-M1 只保留为历史参照，不再作为下一轮主候选。

对世界树 Agent 来说，模型大小不能再按 dense 总参数粗判。真正有用的判断轴是：

1. 激活参数与常驻权重的组合成本。
2. 是否有 agentic tool-use、长程执行、代码仓库任务或多工具 RL 后训练。
3. thinking / non-thinking 或 reasoning effort 是否可控。
4. 64K、128K、256K、1M 上下文下是否能保持工作树状态。
5. 是否支持稳定工具调用、结构化输出、错误反馈后自修。
6. 是否能在世界树协议里遵守父节点编排、child 上浮、暂停恢复和 `awaiting-approval`。

直接判断：

| 角色 | 激进下限 | 稳妥下限 | 高难任务候选 |
| --- | --- | --- | --- |
| 主模型 | `Qwen3.6-35B-A3B`、`Ling-2.6-flash`、`Mistral-Small-4` | `DeepSeek-V4-Flash`、`Command A+`、`MiniMax-M2.7`、`Ling-2.6-1T` | `Kimi-K2.6`、`MiMo-V2.5-Pro`、`GLM-5.1`、`DeepSeek-V4-Pro`、`Nemotron-3-Ultra`、`Ring-2.6-1T` |
| 子任务模型 | `Gemma-4-26B-A4B`、`DiffusionGemma-26B-A4B-it`、`Ling-2.6-flash` | `Qwen3.6-35B-A3B`、`Mistral-Small-4`、`Command A+` | `Kimi-K2.7-Code`、`GLM-5.1`、`MiMo-V2.5-Pro`、`DeepSeek-V4-Flash/Pro` |

当前最务实的下限不是 7B，而是“3B-8B active 的新 MoE + 强运行时约束”。但这只能覆盖 D0-D2。真正让世界树稳定处理 D3-D4 的主模型，仍然应从 10B-55B active 的 agentic MoE 里选。

## 2. 2026 年 3 月后重点候选池

本表只代表静态资料筛选，尚未在本机 provider 中完成 live 验证。

| 模型 | 公开时间窗口 | 规模与上下文 | 世界树角色判断 | 优先级 |
| --- | --- | --- | --- | --- |
| `Qwen/Qwen3.6-35B-A3B` | 2026-04 左右 | 35B total / 3B active，256 experts，8 routed + 1 shared，262K native / 约 1M extended，Apache-2.0 | 低成本主模型下限；适合 D1-D2 编排、仓库级子任务、前端/代码 leaf；必须重点测工具稳定性和工作树协议 | P0 |
| `inclusionAI/Ling-2.6-flash` | 2026-04 后 | 104B total / 7.4B active，MIT；官方强调 fast response、token efficiency、agent performance | 高频 D1-D2 子任务和轻量主模型候选；适合替代“开 thinking 但输出过长”的旧思路 | P0 |
| `mistralai/Mistral-Small-4-119B-2603` | 2026-03 | 119B total / 6.5B active，128 experts / 4 active，256K，上下文、图像输入、function call、reasoning effort | 稳健的通用主模型下限；适合 D1-D2 以及多模态/工具混合任务 | P0 |
| `google/gemma-4-26B-A4B` | 2026-04 左右 | 26B-A4B，256K，多模态，Apache-2.0 | 低成本子任务模型；适合摘要、抽取、文档理解、简单代码与视觉输入，不建议默认做 D3 主编排 | P0 |
| `google/diffusiongemma-26B-A4B-it` | 2026-06 | 25.2B total / 3.8B active，256K，8 active / 128 total experts，扩散式并行生成 | 高吞吐 D0-D1 子任务实验线；公开 benchmark 多项弱于 Gemma 4，但速度优势明显 | P1 实验 |
| `deepseek-ai/DeepSeek-V4-Flash` | 2026-03 后 | 284B total / 13B active，1M context，FP4/FP8 mixed | D2-D4 性价比主模型候选；适合长上下文、代码、工具和恢复链，但应和 Pro 分开测 | P0 |
| `MiniMaxAI/MiniMax-M2.7` | 2026-04 | 230B total / 10B active，200K，256 experts / 8 active；vLLM/SGLang 工具调用和 reasoning parser 指令明确 | D2-D3 主模型或 agentic worker；适合常规长程 agent harness | P1 |
| `CohereLabs/command-a-plus-05-2026-bf16` | 2026-05 | 218B total / 25B active，128K input，Apache-2.0，图像、工具、reasoning，W4A4 可到 2x H100 | 企业型主模型候选；强在 RAG、多语、文档、多模态和私有部署，不是最长上下文但部署现实性高 | P1 |
| `inclusionAI/Ling-2.6-1T` | 2026-05/06 | 1T 级，HF 标注 1T；vLLM recipe 写 50B active，官方强调 fast thinking、低 token overhead、复杂多步执行 | D2-D3 token-efficient 主模型候选；适合测“少想但能执行”的世界树路径 | P1 |
| `Qwen/Qwen3.5-397B-A17B` | 2026-03 | 397B total / 17B active，262K native / 约 1M extended | 属于 3 月后但不是最前沿；可作为大 Qwen 路线参照，不应压过 Qwen3.6-35B 的性价比测试 | P2 |
| `zai-org/GLM-5.1` | 2026-03 后 | 754B total；官方模型卡强调 agentic engineering、长程任务、上千工具回合，未在卡片正文明确 active 参数 | 高难 agentic engineering 主模型；适合 D3-D4 代码、实验、长会话，但本地部署成本高 | P1 |
| `moonshotai/Kimi-K2.6` | 2026-04 后 | 1T total / 32B active，384 experts / 8 selected，256K，多模态 | 高难主模型候选；特别适合 swarm/subagent、长程 coding/design、复杂工具链 | P1 |
| `moonshotai/Kimi-K2.7-Code` | 2026-05/06 | 1T total / 32B active，256K，coding-focused，宣称比 K2.6 少约 30% thinking token | 高难代码子任务模型，不建议默认做通用主编排；用于 D3-D4 仓库改造、复杂 bug 修复 | P0 for code |
| `XiaomiMiMo/MiMo-V2.5-Pro` | 2026-04 后 | 1.02T total / 42B active，1M，MIT，384 routed experts / 8 per token，MTP | D3-D4 主模型强候选；适合长上下文、复杂软件工程、上千工具调用轨迹 | P1 |
| `XiaomiMiMo/MiMo-V2.5` | 2026-04 后 | 310B total / 15B active，1M，文本/图像/视频/音频 | 多模态子任务或中高难主模型候选；适合需要音视频/图像理解的世界树应用包 | P1 实验 |
| `MiniMaxAI/MiniMax-M3` | 2026-06 | 约 428B total / 23B active，1M，原生多模态，MiniMax Sparse Attention，thinking/non-thinking | 1M 多模态长上下文主模型候选；非常新，先做专项长上下文和多模态，不直接替换稳定线 | P1 实验 |
| `nvidia/NVIDIA-Nemotron-3-Super-120B-A12B` | 2026-03-11 | 120B total / 12B active，LatentMoE，1M，thinking 可开关 | D2-D3 高吞吐 agentic/RAG 主模型候选；硬件要求偏高但工程化资料完整 | P1 |
| `nvidia/NVIDIA-Nemotron-3-Ultra-550B-A55B-NVFP4` | 2026-06 | 550B total / 55B active，LatentMoE，1M，NVIDIA Open Model License | D4 高难、长上下文、严肃 RAG 和复杂 agentic reasoning 候选；成本高，适合上限测试 | P2 |
| `deepseek-ai/DeepSeek-V4-Pro` | 2026-03 后 | 1.6T total / 49B active，1M context，FP4/FP8 mixed | D4 主模型上限候选；适合最复杂推理、代码和长程 agentic，但成本/吞吐要实测 | P2 |
| `inclusionAI/Ring-2.6-1T` | 2026-05 | 1T 级 reasoning model，128K -> 256K YaRN，high/xhigh reasoning effort | D4 reasoning 主模型候选；更像高难升级线，不适合默认高频任务 | P2 |

## 3. 主模型与子任务模型分工

### 3.1 主模型职责

主模型是世界树 Agent 的“当前节点决策器”，不是所有 leaf 工作都亲自做的万能模型。

必须稳定负责：

1. 读取任务级工作状态。
2. 判断当前 `Working_Node` 应该继续、下潜、上浮、暂停还是请求输入。
3. child 完成或失败后先回父节点，由父节点决定下一步。
4. 根据任务难度、预算、工具风险选择子任务模型。
5. 对子任务结果做验收、合并、要求返工或升级模型。
6. 保护 `awaiting-approval` 收口，不让单轮回答直接跳成完成。

主模型优先测：

- 协议服从。
- 状态保持。
- 失败恢复。
- 工具错误后的策略调整。
- 子任务委派和结果验收。
- thinking token 是否可控。

### 3.2 子任务模型职责

子任务模型只负责局部 leaf 或专项能力，不负责全局方向。

适合交给子任务模型的工作：

1. 信息抽取、格式转换、摘要。
2. 单文件或小范围代码修改。
3. Web / paper / file 工具调用。
4. 测试失败日志归因。
5. 文档段落生成或校对。
6. 低风险批处理。
7. 图像、视频、音频等多模态理解。

子任务模型必须被限制：

- 工具白名单。
- 输出 schema。
- 最大工具回合数。
- 最大预算。
- 可验证验收项。
- 失败时上浮，而不是自己无限循环。

## 4. 任务难度分级与具体模型

| 等级 | 任务形态 | 主模型建议 | 子任务模型建议 | 验收重点 |
| --- | --- | --- | --- | --- |
| D0 | 纯格式、分类、短摘要、固定字段抽取 | 不需要强主模型；可由路由器直接派发 | `DiffusionGemma-26B-A4B-it`、`Gemma-4-26B-A4B`、`Ling-2.6-flash` | JSON/schema 正确率、低延迟 |
| D1 | 单节点任务，少量工具，结果可直接验证 | `Qwen3.6-35B-A3B`、`Ling-2.6-flash`、`Mistral-Small-4` | `Gemma-4-26B-A4B`、`Qwen3.6-35B-A3B`、`Mistral-Small-4` | 工具参数正确率、一次完成率 |
| D2 | 标准世界树任务，多步骤、多工具、需要 child 上浮 | `DeepSeek-V4-Flash`、`Command A+`、`MiniMax-M2.7`、`Ling-2.6-1T`、`Qwen3.6-35B-A3B` | `Ling-2.6-flash`、`Qwen3.6-35B-A3B`、`Mistral-Small-4`、`Gemma-4-26B-A4B` | 父节点编排、上浮摘要、`awaiting-approval` |
| D3 | 长任务、跨来源证据、失败恢复、预算续跑、代码改动 | `Kimi-K2.6`、`GLM-5.1`、`MiMo-V2.5-Pro`、`DeepSeek-V4-Flash`、`Command A+` | 代码用 `Kimi-K2.7-Code`；多模态用 `MiMo-V2.5` / `MiniMax-M3`；批处理用 `Ling-2.6-flash` | 恢复链、工具失败后重编排、测试反馈闭环 |
| D4 | Graduate、开放研究、复杂软件工程、20+ 工具回合、1M 上下文 | `DeepSeek-V4-Pro`、`MiMo-V2.5-Pro`、`Nemotron-3-Ultra`、`Kimi-K2.6`、`Ring-2.6-1T`、`GLM-5.1` | 多子任务模型并行；代码优先 `Kimi-K2.7-Code`；长上下文可用 `MiniMax-M3` / `DeepSeek-V4-Pro` | 长程一致性、证据质量、人工评审、成本控制 |

难度判断不应只看用户题目长度。应至少看：

1. 是否需要外部工具证据。
2. 是否需要写文件或改代码。
3. 是否需要跨窗口恢复。
4. 是否有不可逆动作或数据治理风险。
5. 是否需要多 child 汇总。
6. 是否需要人工批准或评审。
7. 是否超过 5、20、50 个工具调用级别。

## 5. 推荐路由策略

### 5.1 默认策略

1. D0-D1：默认用 `Ling-2.6-flash`、`Gemma-4-26B-A4B`、`DiffusionGemma-26B-A4B-it` 或 `Qwen3.6-35B-A3B`，限制工具回合。
2. D2：默认主模型从 `DeepSeek-V4-Flash`、`Command A+`、`MiniMax-M2.7`、`Ling-2.6-1T` 中选；子任务用 `Qwen3.6-35B-A3B`、`Ling-2.6-flash`、`Mistral-Small-4`。
3. D3：主模型升级到 `Kimi-K2.6`、`GLM-5.1`、`MiMo-V2.5-Pro` 或 `DeepSeek-V4-Flash`；代码子任务优先 `Kimi-K2.7-Code`。
4. D4：主模型用 `DeepSeek-V4-Pro`、`MiMo-V2.5-Pro`、`Nemotron-3-Ultra`、`Kimi-K2.6`、`Ring-2.6-1T`；必须有人工或自动验收门槛。

### 5.2 thinking 使用规则

不要所有任务都开 thinking。

| 场景 | thinking 策略 |
| --- | --- |
| D0 格式化 / 抽取 | 关闭或用 fast-thinking / non-thinking |
| D1 简单工具调用 | 默认关闭，失败后重试可打开 |
| D2 编排 / 恢复 / 多 child | 打开，但设置预算上限 |
| D3-D4 高难任务 | 打开，并记录 thinking token / cost |
| 高吞吐批处理 | 关闭，除非错误率超过阈值 |

### 5.3 升级与降级

升级触发条件：

1. 连续两次 tool-call 参数错误。
2. child 输出无法通过 schema / hard gate。
3. 当前节点两轮内没有推进状态。
4. 发现任务需要跨来源证据或代码执行反馈。
5. 恢复后模型丢失 `currentNodeId`、父节点摘要或 approval 语义。
6. 低 active 模型开始输出过长思考但没有有效行动。

降级触发条件：

1. 当前任务进入稳定批处理。
2. 子任务 schema 明确且可自动验证。
3. 工具调用少于 3 次且没有写入动作。
4. 只需要摘要、翻译、格式转换或日志清洗。
5. 高难模型输出过长，成本高但验收收益不增加。

## 6. 世界树专项评测设计

MoE 选型不能只看公开 benchmark。需要补世界树自己的路由评测。

| 评测组 | 目的 | 通过标准 |
| --- | --- | --- |
| `model-routing-d0-format` | 测结构化输出和低延迟 | JSON/schema 正确率 >= 99%，无多余解释 |
| `model-routing-d1-tool` | 测单工具 / 少工具调用 | required 参数错误率 <= 2%，失败后可自修 |
| `model-routing-d2-worktree` | 测工作树协议 | child 完成后回父节点，根节点停 `awaiting-approval` |
| `model-routing-d3-recovery` | 测 pause/resume、预算耗尽、工具失败 | 恢复后 current node 不漂移，能继续推进到终态 |
| `model-routing-d3-coding` | 测代码子任务 | 能改代码、跑测试、基于失败日志修复 |
| `model-routing-d4-graduate` | 测高标准研究任务 | 证据、实验记录、引用、阶段账本、人工评审入口齐全 |

建议新增指标：

1. `toolCallValidRate`
2. `nodeTransitionCorrectRate`
3. `parentReorchestrationRate`
4. `resumeStateRetentionRate`
5. `deliveryGatePassRate`
6. `tokensToAcceptedResult`
7. `costToAcceptedResult`
8. `humanInterventionCount`
9. `modelEscalationCount`
10. `subtaskMergeRejectRate`

## 7. 微调与蒸馏方向

世界树微调重点不是让模型“更聪明”，而是让它更像稳定运行时成员。

优先数据：

1. 工作树节点推进轨迹：root -> child -> parent -> sibling -> root -> awaiting-approval。
2. 工具调用成功 / 失败 / 自修三元组。
3. pause/resume 后的恢复样本。
4. 子任务上浮摘要和父节点验收样本。
5. 失败后请求用户、升级模型、缩小任务范围的样本。
6. 反例：直接跳完成、忽略父节点、无限工具循环、伪造工具证据。

训练路线：

1. SFT：先学协议、格式、工具 schema 和上浮语义。
2. 偏好优化：偏好“可验证推进”，惩罚“看似完整但无证据”。
3. 可验证 RL：对 D0-D3 任务用自动门禁奖励，尤其是工具参数、测试通过、状态转换正确。
4. 蒸馏：用 `DeepSeek-V4-Pro`、`MiMo-V2.5-Pro`、`Kimi-K2.6`、`GLM-5.1`、`Nemotron-3-Ultra` 生成高质量轨迹，再蒸馏到 `Qwen3.6-35B-A3B`、`Ling-2.6-flash`、`Mistral-Small-4`。

## 8. 当前推荐考察顺序

第一批先测“低 active 参数 MoE 是否足够驱动世界树 D0-D2”：

1. `Qwen/Qwen3.6-35B-A3B`
2. `inclusionAI/Ling-2.6-flash`
3. `mistralai/Mistral-Small-4-119B-2603`
4. `google/gemma-4-26B-A4B`
5. `google/diffusiongemma-26B-A4B-it`

第二批测“稳妥主模型和可控成本 D2-D3”：

1. `deepseek-ai/DeepSeek-V4-Flash`
2. `MiniMaxAI/MiniMax-M2.7`
3. `CohereLabs/command-a-plus-05-2026-bf16`
4. `inclusionAI/Ling-2.6-1T`
5. `nvidia/NVIDIA-Nemotron-3-Super-120B-A12B`

第三批测“高难、长程、复杂代码和 1M 上下文”：

1. `moonshotai/Kimi-K2.6`
2. `moonshotai/Kimi-K2.7-Code`
3. `XiaomiMiMo/MiMo-V2.5-Pro`
4. `zai-org/GLM-5.1`
5. `MiniMaxAI/MiniMax-M3`
6. `deepseek-ai/DeepSeek-V4-Pro`
7. `nvidia/NVIDIA-Nemotron-3-Ultra-550B-A55B-NVFP4`
8. `inclusionAI/Ring-2.6-1T`

降级为历史参照：

1. `Qwen3-30B-A3B-2507`
2. `Qwen3-Next-80B-A3B`
3. `Qwen3-Coder-480B-A35B`
4. `Kimi K2`
5. `DeepSeek-V3 / DeepSeek-R1`
6. `MiniMax-M1`
7. `gpt-oss`，因为不在本轮 2026 年 3 月后筛选窗口内。

## 9. 风险

1. MoE 激活参数低不等于部署成本低；总权重仍要常驻内存。
2. 长上下文标称值不等于世界树状态可稳定恢复；必须跑恢复链评测。
3. thinking 模式会显著增加 token 和延迟，低难任务不应默认打开。
4. 公开 tool-use benchmark 不等于能遵守世界树工作树协议。
5. Coder 模型适合代码子任务，不一定适合作为长期主编排模型。
6. Provider 线上模型可能静默升级，必须把模型版本、上下文、token 用量和工具错误写入观测。
7. 2026 年新模型更新极快，模型卡中的 tool parser、chat template 和量化要求可能比模型名称更重要。
8. 部分模型许可不是 Apache/MIT，进入商业或客户数据场景前要单独过许可证和数据边界。

## 10. 资料来源

优先使用官方模型卡或厂商资料：

- Qwen3.6-35B-A3B：<https://huggingface.co/Qwen/Qwen3.6-35B-A3B>
- Qwen3.5-397B-A17B：<https://huggingface.co/Qwen/Qwen3.5-397B-A17B>
- Mistral Small 4：<https://huggingface.co/mistralai/Mistral-Small-4-119B-2603>
- Gemma 4 26B-A4B：<https://huggingface.co/google/gemma-4-26B-A4B>
- DiffusionGemma 26B-A4B：<https://huggingface.co/google/diffusiongemma-26B-A4B-it>
- DeepSeek V4：<https://huggingface.co/deepseek-ai/DeepSeek-V4-Pro>
- MiniMax M2.7：<https://developer.nvidia.com/blog/minimax-m2-7-advances-scalable-agentic-workflows-on-nvidia-platforms-for-complex-ai-applications/>
- MiniMax M3：<https://huggingface.co/MiniMaxAI/MiniMax-M3>
- Command A+：<https://huggingface.co/CohereLabs/command-a-plus-05-2026-bf16>
- Cohere Command A+ 发布说明：<https://cohere.com/blog/command-a-plus>
- GLM-5.1：<https://huggingface.co/zai-org/GLM-5.1>
- Kimi K2.6：<https://huggingface.co/moonshotai/Kimi-K2.6>
- Kimi K2.7 Code：<https://huggingface.co/moonshotai/Kimi-K2.7-Code>
- MiMo-V2.5-Pro：<https://huggingface.co/XiaomiMiMo/MiMo-V2.5-Pro>
- MiMo-V2.5：<https://huggingface.co/XiaomiMiMo/MiMo-V2.5>
- Ling-2.6-flash：<https://huggingface.co/inclusionAI/Ling-2.6-flash>
- Ling-2.6-1T：<https://huggingface.co/inclusionAI/Ling-2.6-1T>
- Ring-2.6-1T：<https://huggingface.co/inclusionAI/Ring-2.6-1T>
- Nemotron 3 Super：<https://build.nvidia.com/nvidia/nemotron-3-super-120b-a12b/modelcard>
- Nemotron 3 Ultra：<https://huggingface.co/nvidia/NVIDIA-Nemotron-3-Ultra-550B-A55B-NVFP4>

## 11. 未完成

本文件完成了 2026 年 3 月后 MoE / 稀疏激活候选池刷新、主/子模型分工、D0-D4 任务难度路由和初步考察顺序。尚未完成：

1. 没有跑本地 live 模型评测。
2. 没有新增 evaluation suite。
3. 没有接入自动模型路由实现。
4. 没有更新 provider 配置 UI。
5. 没有验证各模型在本机 provider 上是否可用。
6. 没有对许可证、商用限制、训练数据声明做法律级审查。
