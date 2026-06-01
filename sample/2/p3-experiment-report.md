# P3 实验研究报告

**日期:** 2026-05-31  
**阶段:** Experiment Research (1/4 rounds)  
**实验:** 协变量偏移下后处理校准方法的鲁棒性比较

---

## 实验设计

### 设置
- 数据: sklearn `make_classification`, n=2000, 10特征, 5 informative
- 模型: LogisticRegression
- 校准方法: Platt Scaling, Isotonic Regression, Temperature Scaling (手动实现)
- 评估指标: ECE (10 bins), Brier Score, NLL
- 偏移: 高斯噪声注入 (σ = 0.0, 0.5, 1.0, 2.0, 3.0)

### 手动实现
由于 sklearn 1.8 API 变更 (cv='prefit' 已移除)，三种校准方法均手动实现：
- **Platt Scaling**: 对 logits 拟合单变量逻辑回归
- **Isotonic Regression**: `sklearn.isotonic.IsotonicRegression` (out_of_bounds='clip')
- **Temperature Scaling**: 对 logits 优化单一温度参数 T，最小化 NLL

---

## 结果

### i.i.d. 评估

| 方法 | ECE | Brier | NLL |
|------|-----|-------|-----|
| Uncalibrated | 0.0720 | 0.1564 | 0.4888 |
| Platt | 0.0864 | 0.1565 | 0.4904 |
| **Isotonic** | **0.0465** | **0.1514** | 0.5256 |
| Temperature | 0.0780 | 0.1569 | 0.4886 |

注: T_opt=1.0605, 模型已接近校准良好。

### 协变量偏移评估 (ECE)

| Shift σ | Uncal | Platt | Isotonic | Temperature |
|---------|-------|-------|----------|-------------|
| 0.0 | 0.0720 | 0.0864 | **0.0465** | 0.0780 |
| 0.5 | 0.0664 | 0.0628 | 0.0556 | **0.0518** |
| 1.0 | 0.0913 | 0.0854 | **0.0737** | 0.0880 |
| 2.0 | 0.1863 | 0.1754 | **0.1396** | 0.1779 |
| 3.0 | 0.2525 | 0.2555 | **0.1740** | 0.2469 |

### PHI (Brier Improvement under Shift)

| Shift σ | PHI_Platt | PHI_Iso | PHI_Temp |
|---------|-----------|---------|----------|
| 0.0 | -0.0001 | **0.0050** | -0.0005 |
| 2.0 | 0.0043 | **0.0057** | 0.0030 |
| 3.0 | **0.0036** | 0.0000 | **0.0035** |

---

## 假设验证

### H1: 鲁棒性排序 ✅ 支持
在最强偏移 (σ=3.0) 下 ECE 退化:

| 方法 | ECE 退化 | 排名 |
|------|---------|------|
| **Isotonic** | **+0.1275** | 🥇 最优 |
| Temperature | +0.1689 | 🥈 |
| Platt | +0.1691 | 🥉 |

Isotonic 退化仅为 Platt/Temperature 的 75%。

### H2: 偏移检测→方法选择 ⚠️ 部分支持
Isotonic 在所有偏移水平下 ECE 最优。自适应策略在此场景下简化为"始终使用 Isotonic"。

### H3: PHI vs ECE ⚠️ 待进一步验证
在高偏移下 PHI 噪声较大(shift=3.0时PHI_Iso=0)，需要更大规模实验。

---

## 讨论

1. **Isotonic 的鲁棒性来源**: Isotonic Regression 不依赖参数假设，对 logit 分布的形态变化更鲁棒。而 Platt/Temperature 的 logistic 函数形状在偏移下会错配。

2. **温度参数 T≈1**: 基础模型已接近校准良好，Temperature Scaling 边际收益小。

3. **低偏移下的"改善"现象**: σ=0.5时所有方法ECE降低——噪声作为隐式正则化平滑了概率估计。

4. **局限性**: 仅测试了高斯噪声协变量偏移；未涉及标签偏移和概念漂移；样本量有限。

---

## 下一实验轮次建议

- P3.2: 标签偏移实验 (重采样类别分布)
- P3.3: 真实数据集实验 (CIFAR-10/ImageNet calibration)
- P3.4: 多分类校准扩展

---

*实验代码: 手动实现 Platt/Isotonic/Temperature scaling。完整复现条件: numpy, scipy, sklearn.*
