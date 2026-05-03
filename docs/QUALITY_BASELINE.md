# 世界树计划 · 质量基线

> 本文档记录各关键质量维度的数字基准，作为回归门禁和趋势分析的参照点。  
> **记录日期：2026-04-29**  
> **来源阶段：Phase 4 — 质量基线固化**

---

## 1. M8 记忆策略 Benchmark 基线

**套件 ID：** `evalsuite_benchmark_m8_memory_strategies`  
**定义文件：** `evaluation/suites/m8-benchmark-memory-strategies.json`  
**运行命令：** `pnpm eval:m8:benchmark`（nightly CI）

### 1.1 Pass Rate

| 指标 | 最低合格线 | 说明 |
|------|-----------|------|
| passRate | **1.0** | 所有 case 的 `combinedScore` ≥ 0.5 才算通过；nightly 跑零失败 |

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

> **注意：** CI 中 fallback 模式（无真实 LLM）的基线偏保守；nightly `slow` 任务现在承载并行慢集成/回归测试，真实 LLM 目标值应通过专门的 live 评测与人工验证单独核对。

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

以下阈值已固化为 `tests/test_phase3_stability_and_scale.py` 中的 `assert` 语句，CI merge 层每次运行。

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
| PR | pull_request | pytest (not slow)、web lint/typecheck/build |
| merge | push to main | pytest (not slow)、eval:regression、eval:m9:control-plane、web 构建 |
| nightly | 02:17 UTC | migration-check、smoke-test、pytest (slow，parallel)、**eval:m8:benchmark**（此文档所记录的基线） |

---

## 5. 更新协议

- 每次 nightly `eval:m8:benchmark` 连续 3 轮结果稳定高于当前基线 0.05 以上时，更新本文档中的 `min` 值。  
- 计划在 PostgreSQL 压测环境可用后补一轮同口径复测，并追加 PostgreSQL 实测栏位。  
- 本文档由 `docs/DIRECTORY_REFERENCE.md` 索引，变更须同步更新目录。
