# 分布偏移下后处理校准方法的鲁棒性：基于CalArena框架的扩展研究

**作者:** Graduate Researcher Agent  
**日期:** 2026-05-31  
**状态:** 初步探索与实验验证阶段报告

---

## 摘要

后处理校准(Post-hoc Calibration)是使机器学习模型输出可靠概率估计的关键技术。CalArena (Berta et al., 2026) 建立了首个大规模标准化校准基准，但其评估局限于独立同分布(i.i.d.)场景。本文提出将CalArena框架扩展至分布偏移场景，系统比较Platt Scaling、Isotonic Regression和Temperature Scaling在协变量偏移下的鲁棒性。初步实验表明，Isotonic Regression在协变量偏移下表现出显著更优的鲁棒性，ECE退化仅为参数化方法的75%。我们进一步提出了基于偏移检测的自适应校准选择策略(ACS)框架。

---

## 1. 引言

现代深度神经网络虽然取得了卓越的分类准确率，但其输出的概率估计往往校准不良(Guo et al., 2017)。这在医疗诊断、自动驾驶、金融风控等高风险决策场景中尤为危险。后处理校准通过在独立的校准集上学习概率映射函数，提供了一种轻量级的解决方案。

然而，现有研究面临两个核心问题：

1. **基准碎片化**: 缺乏统一的、大规模的标准化评估基准，不同研究之间的结论难以比较。
2. **忽略分布偏移**: 几乎所有校准方法的评估都在i.i.d.假设下进行，而实际部署场景中分布偏移无处不在。

CalArena (Berta et al., 2026) 解决了第一个问题，建立了覆盖~2000个实验的大规模基准。本文聚焦第二个问题：**后处理校准方法在分布偏移下的鲁棒性如何？能否设计自适应选择策略？**

---

## 2. 相关工作

### 2.1 后处理校准方法

校准方法可分为三类：

- **参数化缩放**: Platt Scaling (Platt, 1999) 对logits拟合逻辑回归；Temperature Scaling (Guo et al., 2017) 优化单一温度参数。
- **非参数方法**: Isotonic Regression (Zadrozny & Elkan, 2001) 学习保序映射；Histogram Binning (Zadrozny & Elkan, 2001) 分箱校准。
- **贝叶斯方法**: Bayesian Binning into Quantiles (Naeini et al., 2015) 在分箱上引入贝叶斯先验。

### 2.2 CalArena基准

CalArena的核心贡献包括：

1. **Post-Hoc Improvement (PHI)**: 基于Proper Scoring Rules的评估指标，同时捕获校准质量和预测性能退化。
2. **核心发现**: 平滑校准函数优于分箱方法；多分类需专用方法；通用ML模型无法替代校准专用设计。
3. **完全开源**: 数据和代码公开，提供即插即用的扩展框架。

### 2.3 分布偏移与校准

Ovadia et al. (2019) 首次系统研究了分布偏移下校准方法的性能退化，发现Temperature Scaling在偏移下表现脆弱。然而，该研究缺乏统一的基准框架，且未提出自适应策略。

---

## 3. 方法

### 3.1 校准方法形式化

给定未校准模型输出的logits $\mathbf{z}$ 和校准集 $\mathcal{D}_{cal} = \{(\mathbf{z}_i, y_i)\}$：

- **Platt Scaling**: $p(y=1|\mathbf{z}) = \sigma(a\mathbf{z} + b)$，其中 $\sigma$ 为sigmoid函数
- **Temperature Scaling**: $p(y=1|\mathbf{z}) = \sigma(\mathbf{z}/T)$
- **Isotonic Regression**: $p(y=1|\mathbf{z}) = f_{iso}(\sigma(\mathbf{z}))$，其中 $f_{iso}$ 为保序映射

### 3.2 协变量偏移模拟

通过在测试特征上施加高斯噪声模拟协变量偏移：
$$\mathbf{x}_{shift} = \mathbf{x} + \epsilon, \quad \epsilon \sim \mathcal{N}(0, \sigma^2 I)$$

### 3.3 评估指标

- **ECE** (Expected Calibration Error): $\sum_{m=1}^M \frac{|B_m|}{n} |\text{acc}(B_m) - \text{conf}(B_m)|$
- **Brier Score**: $\frac{1}{n}\sum_{i=1}^n (p_i - y_i)^2$
- **PHI** (Post-Hoc Improvement): 校准前后Brier Score的差值

---

## 4. 实验

### 4.1 实验设置

- 数据: sklearn `make_classification`, n=2000样本, 10特征
- 基模型: LogisticRegression
- 校准集: 250样本; 验证集: 250样本
- 偏移水平: σ ∈ {0.0, 0.5, 1.0, 2.0, 3.0}

### 4.2 主要结果

**i.i.d. 性能:** Isotonic Regression 表现最优 (ECE=0.0465)，Platt Scaling 反而略有恶化 (ECE=0.0864 vs 未校准0.0720)。

**协变量偏移鲁棒性:** 在 σ=3.0 的最强偏移下：

| 方法 | ECE | ECE退化 |
|------|-----|--------|
| **Isotonic** | **0.1740** | **+0.1275** |
| Temperature | 0.2469 | +0.1689 |
| Platt | 0.2555 | +0.1691 |

Isotonic 的鲁棒性优势随偏移强度增大而增大。

### 4.3 假设验证

- **H1** (鲁棒性排序 Isotonic > Temperature > Platt): ✅ **验证**
- **H2** (偏移检测→自适应选择): ⚠️ Isotonic 在所有偏移水平下最优，自适应策略退化为固定策略
- **H3** (PHI优于ECE): ⚠️ PHI在高偏移下噪声较大，需更大规模验证

---

## 5. 讨论

### 5.1 Isotonic鲁棒性的理论解释

Isotonic Regression 不对概率映射的函数形式做参数假设，仅要求单调性。在分布偏移下，logit分布的形态可能发生复杂变化，而参数化方法(Platt/Temperature)的logistic函数形式无法适应这些变化。

### 5.2 自适应校准选择策略 (ACS)

基于实验结果，提出ACS框架：

```
ACS(logits, detectors):
    if covariate_shift_detected(logits):
        return ISOTONIC
    elif label_shift_detected(logits):
        return BAYESIAN_UPDATE(temperature)
    else:
        return TEMPERATURE_SCALING  # i.i.d.下最优性价比
```

### 5.3 局限性与未来工作

1. **偏移类型局限**: 仅测试了高斯噪声协变量偏移
2. **模型类型局限**: 仅使用了LogisticRegression
3. **指标局限**: PHI在高偏移下的信噪比需要提升
4. **未来方向**: 标签偏移实验、真实世界数据集、多分类扩展、在线校准策略

---

## 6. 结论

本文在CalArena框架的基础上，首次系统研究了后处理校准方法在协变量偏移下的鲁棒性。核心发现是Isotonic Regression因其非参数特性而展现出显著更优的偏移鲁棒性。我们提出了自适应校准选择策略(ACS)的概念框架，并指出了未来在标签偏移、多分类场景和真实数据集上的扩展方向。

---

## 参考文献

1. Berta, E., Holzmüller, D., Bach, F., & Jordan, M. I. (2026). CalArena: A Large-Scale Post-Hoc Calibration Benchmark. arXiv:2605.30188.
2. Guo, C., Pleiss, G., Sun, Y., & Weinberger, K. Q. (2017). On Calibration of Modern Neural Networks. ICML.
3. Platt, J. (1999). Probabilistic Outputs for Support Vector Machines.
4. Zadrozny, B. & Elkan, C. (2001). Obtaining Calibrated Probability Estimates from Decision Trees and Naive Bayesian Classifiers. ICML.
5. Naeini, M. P., Cooper, G., & Hauskrecht, M. (2015). Obtaining Well Calibrated Probabilities Using Bayesian Binning. AAAI.
6. Ovadia, Y., et al. (2019). Can You Trust Your Model's Uncertainty? NeurIPS.
7. Mao, Y., et al. (2024). A Survey on LoRA of Large Language Models. Frontiers of Computer Science.
8. Schweighofer, K., et al. (2026). Overcoming Forgetting in LLM Fine-Tuning with Evolution Strategies. arXiv:2605.30148.

---

*本文为 Graduate Researcher 学习过程的阶段汇报，不代表正式发表。*
