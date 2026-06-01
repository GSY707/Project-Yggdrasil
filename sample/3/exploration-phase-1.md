# 初步探索阶段报告 - ML研究热点扫描 2024-2025

## 探索路径：文献优先
**选择理由：** 作为学习循环起点，文献优先能快速建立领域全景认知，识别研究热点与空白，为后续聚焦提供可审计证据。

## 探索发现

### 方向1：LLM推理时计算优化（Test-Time Compute Scaling）
- **DeepSeek-R1** (Nature 2025, 被引501): 通过强化学习激励LLM推理能力，代表"推理时扩展"范式突破
- **"Reasoning beyond limits: Advances and open problems for LLMs"** (ICT Express 2025): 综述推理能力边界
- **"The Illusion of Thinking"** (2025, 被引109): 反思推理模型的真实推理能力
- **关键问题：** 如何在推理阶段动态分配计算资源以提升复杂推理任务性能

### 方向2：高效架构设计 - 状态空间模型（SSM/Mamba）
- **Mamba** (arXiv 2023, 被引993): 线性时间序列建模，选择性状态空间
- **Vision Mamba** (arXiv 2024, 被引392): 视觉状态空间模型
- **VMamba** (arXiv 2024, 被引362): 视觉状态空间模型改进
- **ChangeMamba** (IEEE TGRS 2024, 被引265): 遥感变化检测
- **FusionMamba** (2024, 被引181): 多模态图像融合
- **关键问题：** SSM能否在长序列任务上替代Transformer，同时保持效率优势

### 方向3：LLM高效微调与参数高效方法
- **LlamaFactory** (ACL 2024 Demos, 被引287): 统一100+模型微调框架
- **"A survey on LoRA of large language models"** (2024, 被引77): LoRA方法综述
- **Qwen3 Technical Report** (arXiv 2025, 被引61): 最新大模型技术报告
- **关键问题：** 如何在极低参数预算下保持全量微调性能

### 方向4：上下文学习（In-Context Learning）机制
- **"A Survey on In-context Learning"** (EMNLP 2024, 被引488): ICL系统综述
- **关键问题：** ICL的内在机制是什么，它与微调的关系如何

### 方向5：可解释性与AI安全对齐
- **"XAI 2.0: A manifesto of open challenges"** (Information Fusion 2024, 被引457)
- **"Explainability for Large Language Models: A Survey"** (ACM TIST 2024, 被引528)
- **"Dissociating language and thought in large language models"** (Trends in Cognitive Sciences 2024, 被引285)
- **关键问题：** 如何为黑盒模型提供可靠的可解释性保证

### 方向6：小语言模型（SLM）与边缘部署
- **"State of the Art and Future Directions of Small Language Models"** (2025): SLM系统综述
- **"Knowledge distillation and dataset distillation of LLMs"** (2025): 蒸馏综述
- **"Deploying AI on Edge"** (2025): 边缘智能进展
- **关键问题：** 如何在资源受限场景下保持模型能力

## 初步判断

**最具创新潜力方向：** "推理时计算优化" × "高效架构设计" 的交叉点

**理由：**
1. **潜在贡献：** 将推理时动态计算分配与高效SSM架构结合，可能突破当前Transformer的效率瓶颈
2. **可验证性：** 可通过标准推理基准（GSM8K, MATH等）和效率指标（FLOPs, 延迟）验证
3. **风险可控：** 两个方向各自有成熟基础，交叉创新风险适中
4. **证据可获得性：** 两个方向文献丰富，开源代码多

## 未解疑问
1. SSM架构上的推理时计算优化是否有先行研究？
2. 推理时计算优化的理论框架是否已经建立？
3. 如何量化"推理效率"与"推理质量"的帕累托前沿？

## 搜索限制说明
- Semantic Scholar遇到429速率限制
- 部分arXiv搜索超时
- Web搜索未返回结果
- 主要依赖OpenAlex数据源
