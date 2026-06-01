# P2 专项探索阶段报告

**日期:** 2026-05-31  
**阶段:** Focused Exploration (3/3 rounds complete)  
**核心创新点:** 分布偏移下后处理校准方法的系统性比较与自适应选择策略

---

## P2.1 CalArena 基准深度理解

### 基准组成
- **规模:** ~2000 个实验
- **领域:** 表格数据 + 计算机视觉
- **分类设置:** 二分类、多分类、大规模分类
- **模型谱系:** 经典ML模型 → 现代深度学习架构 → 基础模型(foundation models)

### PHI 指标 (Post-Hoc Improvement)
- 基于 Proper Scoring Rules（如 Brier Score, Log Loss）
- 同时捕获: ① 校准质量 ② 预测性能是否退化
- **设计理念:** 传统校准误差(ECE, MCE)只测量校准本身，PHI确保校准不会以牺牲判别性能为代价

### 被比较的校准方法谱系
| 类别 | 方法 |
|------|------|
| 参数化缩放 | Platt Scaling, Temperature Scaling, Beta Calibration |
| 非参数 isotonic | Isotonic Regression |
| 分箱法 | Histogram Binning, Bayesian Binning into Quantiles (BBQ) |
| 多分类专用 | Matrix Scaling, Vector Scaling, Dirichlet Calibration |
| 现代方法 | 各种基于NN的校准器 |

### 核心发现
1. **平滑校准函数 > 分箱方法:** 平滑方法在各领域一致优于分箱
2. **多分类需专用方法:** 高维设置下通用二分类扩展到多类效果差
3. **校准需专用设计:** 通用ML模型(直接做校准)不如校准专用方法
4. **数据+代码完全开源:** 提供了即插即用的基准框架

### 可扩展点（创新空间）
1. ❌ 当前未覆盖: **分布偏移场景** (协变量偏移、标签偏移、概念漂移)
2. ❌ 当前未覆盖: **基础模型的原生校准** (in-context calibration)
3. ❌ 当前未覆盖: **在线/持续校准** ( streaming data)

---

## P2.2 分布偏移下校准方法文献梳理

### 关键概念
- **协变量偏移 (Covariate Shift):** P(X) 变化, P(Y|X) 不变
- **标签偏移 (Label Shift):** P(Y) 变化, P(X|Y) 不变  
- **概念漂移 (Concept Drift):** P(Y|X) 变化
- **已知问题:** Temperature Scaling 在分布偏移下校准性能显著退化 (Ovadia et al., 2019)

### 方法分类
| 偏移类型 | 挑战 | 潜在方案 |
|---------|------|---------|
| 协变量偏移 | 校准集不能代表测试分布 | 重要性加权校准、领域自适应校准 |
| 标签偏移 | 先验概率变化导致校准失效 | 贝叶斯更新校准参数 |
| 概念漂移 | P(Y|X)本身改变 | 在线校准更新、检测+重校准 |

### 文献空白
- 缺乏**统一基准**比较不同校准方法在不同偏移类型下的鲁棒性
- 缺乏**自适应选择策略**: 如何根据检测到的偏移类型自动选择最佳校准方法
- CalArena的PHI框架可以填补这一空白

---

## P2.3 自适应选择策略假设形成

### 研究假设 (H1-H3)

**H1 (鲁棒性排序):** 
不同校准方法在分布偏移下存在可预测的鲁棒性排序。
- 预测: Isotonic Regression > Temperature Scaling > Platt Scaling (在协变量偏移下)
- 预测: Bayesian方法 (BBQ) > 频率派方法 (在标签偏移下)

**H2 (偏移检测 → 方法选择):**
可以通过检测偏移类型来自动选择最优校准方法。
- 检测器: MMD (协变量偏移), 混淆矩阵变化 (标签偏移)
- 策略: IF covariate_shift_detected THEN use_isotonic ELSE use_temperature

**H3 (PHI优于ECE):**
PHI在分布偏移下比ECE更能区分校准方法的实际效用。
- 预期: ECE在偏移下可能低估校准退化(因为仅测量平均校准)
- PHI通过proper scoring rules同时捕获校准+性能退化

### 实验设计概览

1. **基准扩展:** 在CalArena数据上引入合成分布偏移
   - 协变量偏移: 对输入特征施加已知变换
   - 标签偏移: 重采样类别分布
   
2. **评估指标:** PHI (primary) + ECE + Accuracy

3. **自适应策略评估:** 比较固定策略 vs 自适应选择 vs Oracle上界

---

*本报告综合了arXiv摘要检索、OpenAlex文献搜索和校准领域基础知识。*
*CalArena代码: 预期托管在GitHub (论文声明"release all data, code, and evaluation tools")。*
