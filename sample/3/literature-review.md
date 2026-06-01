# 文献综述：大语言模型推理时计算优化

## 摘要

大语言模型（LLMs）在复杂推理任务上取得了显著进展，但如何在推理阶段高效分配计算资源仍是一个核心挑战。本文综述了推理时计算优化（Test-Time Compute Scaling）的最新进展，系统分析了链式思维推理、自适应计算分配、强化学习驱动推理等核心方法，识别了当前研究的空白，并提出了未来研究方向。

**关键词：** 大语言模型，推理时计算，链式思维，自适应计算分配，强化学习

---

## 1. 引言

近年来，大语言模型（LLMs）在自然语言处理、代码生成、数学推理等领域展现出前所未有的能力（Zhao et al., 2023; Naveed et al., 2023）。模型规模的持续扩展带来了显著的性能提升，但也伴随着巨大的推理成本。在此背景下，"推理时计算优化"（Test-Time Compute Scaling）作为一个新兴研究方向应运而生——即在推理阶段通过增加或优化计算资源来提升模型性能，而非仅仅依赖模型参数规模的扩展。

Snell et al.（2024）的研究表明，在推理阶段优化计算分配可以比单纯扩大模型参数更有效。这一发现开辟了LLM效率优化的新范式。本文旨在系统梳理该领域的最新进展，分析核心方法的优劣，并识别未来研究方向。

## 2. 背景

### 2.1 从训练时缩放到推理时缩放

传统的LLM性能提升主要依赖训练时缩放（Train-Time Scaling），即通过增加模型参数、训练数据和计算预算来提升性能（Kaplan et al., 2020）。然而，这种方法的边际收益递减，且推理成本随模型规模线性增长。

推理时缩放（Test-Time Scaling）提供了另一种思路：在推理阶段动态分配计算资源。Snell et al.（2024）证明，在FLOPs匹配条件下，小模型配合推理时计算优化可以超越14倍大的模型。

### 2.2 推理范式的演进

LLM推理范式的演进可分为三个阶段：

1. **直接推理（Direct Reasoning）：** 模型直接输出答案，无中间步骤
2. **链式思维推理（Chain-of-Thought, CoT）：** 模型生成中间推理步骤（Wei et al., 2022）
3. **结构化推理（Structured Reasoning）：** 模型使用树状、图状等复杂推理结构（Besta et al., 2025）

## 3. 核心方法

### 3.1 链式思维推理及其扩展

链式思维推理（CoT）是推理时计算优化的基础范式。通过在提示中引入"让我们一步步思考"等指令，LLMs能够生成中间推理步骤，显著提升复杂问题的解决能力。

**CoT的扩展方法包括：**
- **Self-Consistency（Wang et al., 2022）：** 生成多个推理路径，通过投票选择最一致的答案
- **Tree-of-Thought（Yao et al., 2023）：** 使用树状搜索探索多种推理路径
- **Graph-of-Thought（Besta et al., 2022）：** 使用图结构表示推理依赖关系

### 3.2 自适应计算分配

Snell et al.（2024）提出了"Compute-Optimal"测试时计算分配策略。该策略的核心思想是：不同难度的问题需要不同的计算分配。

**两种主要机制：**
1. **搜索机制：** 使用过程奖励模型（PRM）引导搜索过程
2. **自适应机制：** 根据提示难度自适应更新模型响应分布

实验表明，Compute-Optimal策略比best-of-N基线效率高4倍以上。

### 3.3 强化学习驱动推理

DeepSeek-R1（Guo et al., 2025）代表了强化学习驱动推理的最新进展。通过Group Relative Policy Optimization（GRPO）算法，模型能够在无需标注CoT数据的情况下，通过试错自动学习推理轨迹。

Kimi k1.5（2025）进一步发展了长上下文RL缩放方法，提出了Long2Short技术，使用长CoT技术改进短CoT模型，在多个基准上超越了GPT-4o和Claude Sonnet 3.5。

### 3.4 推理语言模型的模块化框架

Besta et al.（2025）提出了推理语言模型（RLM）的蓝图，将RLM组件组织为模块化框架。该框架涵盖了：
- **推理结构：** 链、树、图、嵌套
- **推理策略：** MCTS、Beam Search、Self-Consistency
- **监督方案：** 结果监督与过程监督

## 4. 研究空白与挑战

尽管推理时计算优化取得了显著进展，仍存在以下核心挑战：

### 4.1 缺乏统一的理论框架
当前方法多为经验性，缺乏统一的理论框架来指导计算分配策略的设计。如何从第一性原理推导最优计算分配策略仍是一个开放问题。

### 4.2 PRM依赖问题
现有自适应方法大多依赖过程奖励模型（PRM），但PRM的训练成本高、泛化能力有限。如何在不依赖PRM的情况下实现自适应计算分配是一个重要方向。

### 4.3 架构依赖性
现有工作几乎全部基于Transformer架构。在SSM/Mamba等新兴高效架构上，推理时计算优化的效果尚未得到系统研究。

### 4.4 多策略组合
现有方法通常使用单一策略，如何根据问题特征动态组合多种推理策略仍有待探索。

## 5. 未来研究方向

基于上述分析，本文提出以下未来研究方向：

1. **轻量级推理难度评估器：** 基于模型内部状态（如注意力熵、预测不确定性）评估问题难度，实现无PRM的自适应分配
2. **效率-质量帕累托前沿理论：** 建立推理时计算优化的理论框架，刻画效率-质量的帕累托前沿
3. **高效架构上的推理时计算：** 在SSM/Mamba等架构上探索推理时计算优化
4. **多策略自适应组合：** 根据问题特征动态组合序列扩展、并行扩展和搜索策略

## 6. 结论

推理时计算优化是LLM效率优化的重要方向。本文系统梳理了该领域的最新进展，分析了核心方法的优劣，识别了研究空白，并提出了未来研究方向。随着DeepSeek-R1、Kimi k1.5等工作的出现，推理时计算优化正在成为LLM研究的新前沿。未来的工作需要在理论框架、无PRM方法、高效架构适配等方面取得突破。

---

## 参考文献

1. Besta, M., et al. (2025). "Reasoning Language Models: A Blueprint." arXiv:2501.11223.
2. Guo, D., et al. (2025). "DeepSeek-R1 incentivizes reasoning in LLMs through reinforcement learning." Nature.
3. Kimi Team. (2025). "Kimi k1.5: Scaling Reinforcement Learning with LLMs." arXiv:2501.12599.
4. Naveed, H., et al. (2023). "A Comprehensive Overview of Large Language Models." arXiv:2307.06435.
5. Snell, C., Lee, J., Xu, K., & Kumar, A. (2024). "Scaling LLM Test-Time Compute Optimally can be More Effective than Scaling Model Parameters." arXiv:2408.03314.
6. Xu, F., et al. (2025). "Towards Large Reasoning Models: A Survey of Reinforced Reasoning with Large Language Models." arXiv:2501.09686.
7. Zhang, D., et al. (2025). "From System 1 to System 2: A Survey of Reasoning Large Language Models." IEEE TPAMI.
8. Zhao, W. X., et al. (2023). "A Survey of Large Language Models." Frontiers of Computer Science.
9. Ferrag, M. A., Tihanyi, N., & Debbah, M. (2025). "Reasoning Beyond Limits: Advances and Open Problems for LLMs." ICT Express.
10. Shojaee, P., et al. (2025). "The Illusion of Thinking."
