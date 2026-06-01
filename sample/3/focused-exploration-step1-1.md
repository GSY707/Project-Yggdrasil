# 专项探索 Step 1.1 - 推理时计算优化核心文献地图

## 核心创新点：推理时计算优化（Test-Time Compute Scaling）

## 方法分类与关键文献

### 类别1：链式思维推理（Chain-of-Thought Reasoning）
| 论文 | 年份 | 来源 | 被引 | 核心贡献 |
|------|------|------|------|----------|
| DeepSeek-R1: Incentivizes reasoning in LLMs through RL | 2025 | Nature | 501 | 通过纯RL激励推理能力，无需标注CoT数据 |
| s1: Simple test-time scaling | 2025 | EMNLP | 33 | 简单的测试时缩放方法 |
| Qwen3 Technical Report | 2025 | arXiv | 61 | 最新大模型推理能力技术报告 |
| Qwen2.5 Technical Report | 2024 | arXiv | 71 | Qwen系列推理能力演进 |
| WizardMath: Empowering Mathematical Reasoning via Reinforced Evol-Instruct | 2023 | arXiv | 27 | 强化进化指令提升数学推理 |
| ReFT: Reasoning with Reinforced Fine-Tuning | 2024 | ACL | 25 | 强化微调推理方法 |

### 类别2：推理综述与理论框架
| 论文 | 年份 | 来源 | 被引 | 核心贡献 |
|------|------|------|------|----------|
| Towards Large Reasoning Models: A Survey of Reinforced Reasoning | 2025 | arXiv | 16 | 强化推理大模型综述 |
| From System 1 to System 2: A Survey of Reasoning LLMs | 2025 | IEEE TPAMI | 11 | 从系统1到系统2的推理LLM综述 |
| Reasoning beyond limits: Advances and Open Problems for LLMs | 2025 | ICT Express | 11 | 推理能力边界与开放问题 |
| The Illusion of Thinking | 2025 | - | 109 | 反思推理模型的真实推理能力 |
| Dissociating language and thought in LLMs | 2024 | Trends in Cognitive Sciences | 285 | 语言与思维的分离 |

### 类别3：奖励模型与验证
| 论文 | 年份 | 来源 | 被引 | 核心贡献 |
|------|------|------|------|----------|
| A Survey on LLM-as-a-Judge | 2024 | arXiv | 25 | LLM作为评判者的综述 |

### 类别4：推理时计算分配（核心方向）
| 论文 | 年份 | 来源 | 被引 | 核心贡献 |
|------|------|------|------|----------|
| s1: Simple test-time scaling | 2025 | EMNLP | 33 | 测试时计算缩放 |
| DeepSeek-R1 | 2025 | Nature | 501 | RL驱动的推理时扩展 |

### 类别5：多模态与Agent推理
| 论文 | 年份 | 来源 | 被引 | 核心贡献 |
|------|------|------|------|----------|
| A survey on LLM-based autonomous agents | 2024 | Frontiers of Computer Science | 1087 | LLM自主Agent综述 |
| AI Agents vs. Agentic AI | 2025 | Information Fusion | 97 | Agent与Agentic AI概念分类 |

## 关键发现

### 1. 推理时计算优化的三种范式
- **范式A：序列扩展（Sequential Scaling）** - 通过更长的CoT链增加推理深度
- **范式B：并行扩展（Parallel Scaling）** - 通过Self-Consistency等集成方法增加推理广度
- **范式C：自适应扩展（Adaptive Scaling）** - 根据问题难度动态分配推理计算

### 2. 核心研究空白
- **空白1：** 缺乏统一的推理时计算理论框架来指导计算分配
- **空白2：** 自适应计算分配的效率-质量帕累托前沿尚未系统研究
- **空白3：** 推理时计算优化与高效架构（如SSM）的结合研究几乎空白
- **空白4：** 缺乏轻量级的推理难度评估器来指导计算分配

### 3. 可验证的实验基准
- GSM8K（数学推理）
- MATH（竞赛数学）
- AIME（竞赛数学）
- HumanEval / MBPP（代码推理）
- ARC（科学推理）

## 下一步行动
- Step 1.2: 深入分析关键方法的技术细节
- Step 1.3: 识别具体可创新点并设计实验方案
