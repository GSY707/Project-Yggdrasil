# 世界树计划 · 质量基线

> 本文档记录各关键质量维度的数字基准，作为回归门禁和趋势分析的参照点。  
> **记录日期：2026-04-29**  
> **来源阶段：Phase 4 — 质量基线固化**

---

## 1. M8 记忆策略 Benchmark 基线

**套件 ID：** `evalsuite_benchmark_m8_memory_strategies`  
**定义文件：** `evaluation/suites/m8-benchmark-memory-strategies.json`  
**运行命令：** `pnpm eval:m8:benchmark`（发布前全量检查或基线相关改动后手动执行）

### 1.1 Pass Rate

| 指标 | 最低合格线 | 说明 |
|------|-----------|------|
| passRate | **1.0** | 所有 case 的 `combinedScore` ≥ 0.5 才算通过；发布前全量检查不得出现失败 |

### 1.2 策略排行榜（Strategy Leaderboard）

`combinedScore = contextCoverage × 0.7 + answerCoverage × 0.3`

| 策略 | minAvgCombinedScore | minAvgContextCoverage | minAvgAnswerCoverage |
|------|--------------------|-----------------------|----------------------|
| `memory-tree` | **0.70** | **0.75** | **0.50** |
| `vector-flat` | **0.45** | **0.55** | **0.30** |
| `no-memory`   | 0.00 | 0.00 | 0.00 |

**排序约束：** `memory-tree` 的 `avgCombinedScore` 必须高于 `vector-flat`，体现记忆树检索相对扁平向量的结构优势。

### 1.3 单指标目标值（target）

在真实 LLM（live 模式）下，预期达到的更高目标值：

| 策略 | contextCoverage target | answerCoverage target |
|------|------------------------|-----------------------|
| `memory-tree` | 0.85 | 0.65 |
| `vector-flat` | 0.70 | 0.45 |
| `no-memory`   | 0.10 | 0.05 |

> **注意：** CI 中 fallback 模式（无真实 LLM）的基线偏保守；当前仓库不再依赖定时 nightly 维持基线。真实 LLM 目标值应在相关改动后通过专门的 live 评测与人工验证单独核对。

---

## 2. 关键 API 路径延迟基线

**测量环境：** SQLite in-process（CI 环境），非 PostgreSQL 生产环境。  
**说明：** 以下数字为 Phase 3 稳定性测试中确立的**上界（acceptance threshold）**，同时作为 P95 参照点。生产部署（PostgreSQL + 索引）预期 P50 显著低于此上界。

### 2.1 记忆节点检索（NodeRepository）

| 操作 | 数据量 | P95 上界 | 备注 |
|------|--------|---------|------|
| `list_nodes`（全量扫描） | 1 000 节点 | **5 000 ms** | Phase 3 通过阈值；覆盖 CI SQLite |
| `get_node`（单节点点查） | 50 次采样 | **5 000 ms**（50次总计） | 即单次 P95 ≤ 100 ms |
| `list_nodes`（全量扫描） | 1 000 节点 | **P50 目标 ≤ 200 ms** | PostgreSQL 生产部署目标 |

### 2.2 记忆片段导入（MemoryRepository）

| 操作 | 数据量 | 时间上界 | 内存峰值上界 |
|------|--------|---------|------------|
| `replace_import_fragments` | 1 000 片段 × ~100 词 ≈ 10 万词 | **30 000 ms** | **200 MB** |

> 生产部署（PostgreSQL + 批量 INSERT 优化）目标：≤ 5 000 ms、内存峰值 ≤ 50 MB。

### 2.3 Core API HTTP 路径（实测）

以下数字来自 2026-05-04 本机实测：`uv run yggdrasil-core-api` + Python HTTP 压测脚本（120 次采样，20 次预热，SQLite，内存协调后端）。

| 路径 | 方法 | P50 实测 | P95 实测 | 说明 |
|------|------|---------|---------|------|
| `/tasks` | GET | 25.22 ms | 32.01 ms | `limit=100`，预置 40 条任务 |
| `/nodes` | GET | 30.99 ms | 36.44 ms | `limit=200`，预置 120 个节点 |
| `/memory/retrievals` | POST | 277.73 ms | 367.36 ms | 请求体含 `queryText` 与检索深度参数 |

---

## 3. Phase 3 稳定性与并发安全门禁

以下阈值已固化为 `tests/test_phase3_stability_and_scale.py` 中的 `assert` 语句，发布前全量检查必须通过。

| 测试项 | 指标 | 门禁值 |
|--------|------|-------|
| 1000 节点全量检索（`list_nodes`） | 耗时 | < 5.0 s |
| 50 次 `get_node` 点查 | 总耗时 | < 5.0 s |
| 10 万词片段导入 | 耗时 | < 30.0 s |
| 10 万词片段导入 | 内存峰值 | < 200 MB |
| 2 Worker 并发 pause 同一 Task | 活跃快照数 | ≤ 1 |
| 4 Sub-agent 并发写同一 Space | 节点丢失数 | = 0 |
| 故障 Hook 隔离 | 其他模块正常执行 | ✓（不传播异常） |

---

## 4. CI 门禁对照表

| 层级 | 触发 | 包含质量门禁 |
|------|------|------------|
| PR | pull_request | Python 语法 smoke、web lint/typecheck/build |
| merge | push to main | Python 语法 smoke、web lint/typecheck/build |
| release-check | workflow_dispatch | migration-check、smoke-test、`pytest -q`、`pytest --postgres -m "not slow"`、`eval:regression`、`eval:m8:benchmark`、`eval:m9:control-plane`、`eval:g2:regression`、web lint/typecheck/build |

---

## 5. 更新协议

- 仅在 benchmark 相关实现发生变更时，才需要手动复跑 `eval:m8:benchmark`；若连续 3 轮结果稳定高于当前基线 0.05 以上，再更新本文档中的 `min` 值。  
- 计划在 PostgreSQL 压测环境可用后补一轮同口径复测，并追加 PostgreSQL 实测栏位。  
- 本文档由 `docs/DIRECTORY_REFERENCE.md` 索引，变更须同步更新目录。

---

## 6. 长任务与伪无限上下文评测口径（2026-05-16 规划）

> 本节是当前项目第一优先级方向的正式评测规划，不代表这些指标已经达成；它定义的是接下来应冻结的官方测量口径。

### 6.1 评测原则

1. 无法直接评测“无限次上下文窗口重启”，因此正式评测采用“受控多次”逼近。
2. 评测不以单次 prompt 更长为目标，而以“短窗口路径与长窗口路径的最终效果是否一致”为目标。
3. official stress path 应通过运行时显式限制 `effectiveContextWindow`，强制系统经历大量 context pruning / window restart。
4. official reference path 使用更长上下文窗口或更宽松阈值，在同一任务、同一 acceptance contract 下提供质量对照。

### 6.2 官方 stress 口径

| 指标 | 目标口径 | 说明 |
|------|----------|------|
| `effectiveContextWindow` | 固定写入 artifact | 人工限制后的有效窗口大小，用于制造稳定压力 |
| `restartCount` | `100` | 官方 stress path 要求同一任务链完成 100 次窗口重启或等价窗口轮换 |
| `compressionCount` | 强制记录 | 不允许通过只压缩不重启来隐藏窗口轮换成本 |
| `cumulativeWindowSpanTokens` | `>= 100 × effectiveContextWindow` | 证明这不是单窗口内的伪长任务 |
| `maxContextLengthTokens` | 持续低于 hard restart 阈值 | 防止 silent overflow |
| `restartSuccessRate0_1` | `1.0` 目标 | 每次 restart 都必须成功接续到下一窗口 |
| `finalAcceptanceParity0_1` | `1` 目标 | short-window 与 long-window 在同一任务上得到相同验收结论 |
| `deliveryEquivalence0_1` | `1` 目标 | 两条路径满足相同的交付 contract |
| `qualityDeltaToLongWindow0_100` | 越接近 `0` 越好 | 正式数值门槛在 restart loop 实装后的 3 轮稳定复跑中冻结 |
| `carryForwardLossCount` | `0` 目标 | 不允许因为摘要、引用或状态丢失而出现显式断裂 |

### 6.3 通过标准的核心定义

“伪无限上下文窗口”方向的正式目标不是总 token 更大，而是：

1. 短窗口路径与长窗口路径在同一任务上得到相同 acceptance 结论。
2. 差异主要允许出现在时延与成本，而不是最终质量、证据完整性和交付连续性。
3. 只要这三条成立，就可以认为系统正在逼近“记忆树为主体、上下文窗口为工作集”的正式工程能力。
