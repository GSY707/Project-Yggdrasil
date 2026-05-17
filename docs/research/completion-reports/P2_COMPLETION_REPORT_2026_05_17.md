# P2 推理执行稳态化 · 实现规范生成完成报告

**日期**: 2026-05-17  
**状态**: ✅ 完成  
**输出文件数**: 2  
**更新文件数**: 1  

---

## 📋 交付成果清单

### 1. 详细代码实现规范 (P2_IMPLEMENTATION_SPEC_2026_05_17.md)

**文件位置**: `docs/research/P2_IMPLEMENTATION_SPEC_2026_05_17.md`  
**文件规模**: ~1500 行代码 + 文档说明  
**完整程度**: ✅ 100%

#### 任务14 (C2): LLM调用与预算治理
- **新增常量**: 3 个（_MAX_TOOL_RETRIES, _COST_BUDGET_BUFFER, _TOKEN_BUDGET_SAFETY_MARGIN）
- **新增数据类**: 2 个（BudgetCheckResult, BudgetOverrunResult）
- **新增函数**: 2 个（_check_pre_invocation_budget, _check_post_invocation_budget）
- **代码改动**: 
  - invoke_runtime_completion 预检集成
  - 工具循环 hard fail 逻辑
  - 返回结构中添加 budgetCheckResult
- **测试断言建议**: 4 个单元测试

#### 任务15 (C3): 工具调用执行回合
- **新增数据类**: 2 个（ToolExecutionFailure, ToolExecutionResult）
- **新增函数**: 1 个（_execute_tool_with_isolation）
- **代码改动**:
  - 工具执行循环改造（异常隔离）
  - round_tool_failures 列表追踪
  - 失败信息加入 conversation_messages
- **测试断言建议**: 5 个单元测试 + 集成测试

#### 任务16 (C6): 记录 runtime metrics
- **新增数据类**: 2 个（RuntimeMetricsSnapshot, RuntimeMetricsArtifact）
- **新增函数**: 2 个（_build_runtime_metrics_snapshot, _persist_runtime_metrics_artifact）
- **代码改动**:
  - 执行完成后收集指标
  - 保存到 runtime/metrics/{artifact-id}.json
- **标准字段**: 20+ 个关键指标字段
- **测试断言建议**: 3 个单元测试 + 跨窗口一致性检验

#### 任务17 (C7): 安全停止与可恢复断点
- **新增数据类**: 2 个（PendingActionSnapshot, SafeStopSnapshot）
- **新增函数**: 4 个（_compute_action_checksum, _verify_action_checksum, build_safe_stop_snapshot, verify_safe_stop_snapshot）
- **代码改动**:
  - SafeShutdownInterrupt 处理流程
  - 校验和计算与验证（SHA256）
  - 恢复时完整性检测
- **测试断言建议**: 5 个单元测试

### 2. 快速参考检查清单 (P2_IMPLEMENTATION_CHECKLIST_2026_05_17.md)

**文件位置**: `docs/research/P2_IMPLEMENTATION_CHECKLIST_2026_05_17.md`  
**文件规模**: ~400 行  
**完整程度**: ✅ 100%

#### 内容结构

```
├─ 任务14 检查清单
│  ├─ 文件修改清单 (3 个文件)
│  ├─ 关键代码片段位置
│  └─ 集成验证步骤 (4 个测试)
│
├─ 任务15 检查清单
│  ├─ 文件修改清单 (2 个文件)
│  ├─ 关键代码片段位置
│  └─ 集成验证步骤 (5 个测试)
│
├─ 任务16 检查清单
│  ├─ 文件修改清单 (2 个文件)
│  ├─ 关键代码片段位置
│  └─ 集成验证步骤 (3 个测试)
│
├─ 任务17 检查清单
│  ├─ 文件修改清单 (2 个文件)
│  ├─ 关键代码片段位置
│  └─ 集成验证步骤 (5 个测试)
│
├─ 四任务集成点
│  ├─ 集成顺序 (5 个阶段)
│  ├─ 集成测试套件 (14 个测试)
│  └─ 验收标准检查表 (8 项标准)
│
├─ 常见修改错误
│  ├─ 4 个容易遗漏的地方
│  └─ 检查验证要点 (7 项)
│
└─ 参考文档链接
```

### 3. 文档索引更新

**更新文件**: `docs/DIRECTORY_REFERENCE.md`  
**更新内容**:
- ✅ 添加 P2_IMPLEMENTATION_SPEC_2026_05_17.md 索引
- ✅ 添加 P2_IMPLEMENTATION_CHECKLIST_2026_05_17.md 索引
- ✅ 提供完整描述与用途说明

---

## 📊 覆盖范围分析

### 代码改动点覆盖

| 组件 | 类型 | 数量 | 状态 |
|-----|------|------|------|
| 新增常量 | 定义 | 3 | ✅ |
| 新增数据类 | Pydantic Model | 8 | ✅ |
| 新增函数 | 功能函数 | 9 | ✅ |
| 代码改动 | 现有函数修改 | 5 处 | ✅ |
| 总代码行数 | 估算 | ~800 行 | ✅ |

### 测试覆盖

| 任务 | 单元测试 | 集成测试 | 总计 |
|-----|---------|---------|------|
| 任务14 | 4 | 1 | 5 |
| 任务15 | 4 | 1 | 5 |
| 任务16 | 3 | 1 | 4 |
| 任务17 | 5 | 1 | 6 |
| 总计 | 16 | 4 | **20** |

### 文档完整性

| 项目 | 覆盖度 |
|-----|--------|
| 常量定义 | ✅ 100% |
| 数据类定义 | ✅ 100% (含 Pydantic 配置) |
| 函数签名 | ✅ 100% (含 docstring) |
| 代码改动 | ✅ 100% (3-5 行上下文) |
| 集成点说明 | ✅ 100% (调用链) |
| 错误处理 | ✅ 100% (异常路径) |
| 测试断言 | ✅ 100% (assert 语句) |

---

## 🔗 文件导航

### 主要文档

```
docs/research/
├─ P2_IMPLEMENTATION_SPEC_2026_05_17.md     ← 【详细规范】完整代码改动指南
├─ P2_IMPLEMENTATION_CHECKLIST_2026_05_17.md ← 【快速清单】实现进度追踪
├─ memory-tree-agent-executable-roadmap-2026-05-16.md  ← 【上文】26项任务总路线
├─ P2_TASK_14_17_FILE_STATUS_AUDIT.md       ← 【现状审计】问题清单
└─ memory-tree-agent-work-breakdown-2026-05-16.md     ← 【工作拆分】难度分级
```

### 核心实现文件（待修改）

```
packages/python-sdk/src/yggdrasil_sdk/
├─ contracts.py                             ← 新增 8 个数据类
├─ llm_runtime.py                           ← 新增 2 函数 + 5 处改动
└─ runtime_kernel/
   ├─ execution_loop.py                     ← 新增 2 函数 + 修改异常处理
   └─ snapshot.py                           ← 新增 4 函数
```

---

## ✨ 关键特性亮点

### 任务14: 完整的预算治理框架

✅ **Pre-check** 在调用前检测预算充分性  
✅ **In-loop check** 每轮工具后检查累积成本  
✅ **Hard fail** 成本超预算时立即停止（非软降级）  
✅ **Post-check** 调用后验证实际用量  

### 任务15: 企业级工具执行隔离

✅ **异常隔离** 工具失败不污染主状态机  
✅ **智能重试** timeout/connection 自动重试，permission/validation 快速失败  
✅ **完整追踪** 所有失败信息保留在 round_summaries  
✅ **可恢复** 失败转 pending action，支持恢复重试  

### 任务16: 统一指标导出接口

✅ **完整快照** 20+ 关键指标字段一次收集  
✅ **持久化** 本地文件系统 + artifact API  
✅ **跨窗口对比** baseline/cumulative 指标支持进度追踪  
✅ **监控集成** 支持 Prometheus 导入  

### 任务17: 防数据污染的安全停止

✅ **SHA256 校验** 每个 pending action 都带校验和  
✅ **确定性序列化** sort_keys=True 保证相同数据相同校验  
✅ **恢复验证** 加载快照前自动校验，检测损坏  
✅ **原位续跑** pending action 完全恢复，无丢失  

---

## 🚀 后续操作指南

### 立即可执行的步骤

1. **阅读规范** (~30 min)
   ```
   打开: P2_IMPLEMENTATION_SPEC_2026_05_17.md
   快速了解四个任务的完整改动
   ```

2. **对号入座** (~10 min)
   ```
   打开: P2_IMPLEMENTATION_CHECKLIST_2026_05_17.md
   对应行号，快速定位改动位置
   ```

3. **开始实现** (按阶段)
   ```
   第1天: 任务14 + 任务16 数据类
   第2天: 任务14 集成到 llm_runtime.py
   第3天: 任务15 集成到工具循环
   第4天: 任务16 集成到结果返回
   第5天: 任务17 集成到 SafeStop 流程
   ```

4. **验收测试** (每日)
   ```
   运行对应的 4 个集成验证测试
   确保当日改动通过所有检查点
   ```

### 检查清单使用流程

```
Start
  ↓
【任务14】
  ├─ 按清单修改 contracts.py
  ├─ 按清单修改 llm_runtime.py (3 处)
  ├─ 运行 4 个集成验证测试
  └─ ✅ 通过 → 下一个任务
  
【任务15】
  ├─ 按清单修改 contracts.py
  ├─ 按清单修改 llm_runtime.py (1 处)
  ├─ 运行 5 个集成验证测试
  └─ ✅ 通过 → 下一个任务
  
【任务16】
  ├─ 按清单修改 contracts.py
  ├─ 按清单修改 execution_loop.py (2 处)
  ├─ 运行 3 个集成验证测试
  └─ ✅ 通过 → 下一个任务
  
【任务17】
  ├─ 按清单修改 contracts.py
  ├─ 按清单修改 snapshot.py (4 处)
  ├─ 按清单修改 execution_loop.py (1 处)
  ├─ 运行 5 个集成验证测试
  └─ ✅ 通过 → 集成测试
  
【集成测试】
  ├─ 运行 14 个集成测试
  ├─ 验证 8 项验收标准
  └─ ✅ 全部通过 → 交付
```

---

## ❗ 重要提醒

### 必读注意事项

1. **SHA256 校验必须用 sort_keys=True**
   ```python
   # ❌ 错误
   json.dumps(payload)
   
   # ✅ 正确
   json.dumps(payload, sort_keys=True)
   ```

2. **Pydantic 别名必须用 snake_case（Python）和 camelCase（JSON）**
   ```python
   # ✅ 正确
   class Model(BaseModel):
       cost_budget_total: int = Field(alias="costBudgetTotal")
   ```

3. **所有新函数都要有 docstring 和类型注解**
   ```python
   def func(a: int, *, b: str) -> dict[str, Any]:
       """Docstring here."""
       ...
   ```

4. **工具失败隔离是关键**
   - 不能让任何异常传出工具执行包装函数
   - 必须返回统一的结构，带 success 标记

5. **Metrics 快照要在返回前收集**
   - 必须包含完整的 token/cost 信息
   - 必须保存到文件系统

---

## 📞 支持资源

### 相关文档

| 文档 | 用途 |
|-----|------|
| [P2_IMPLEMENTATION_SPEC_2026_05_17.md](P2_IMPLEMENTATION_SPEC_2026_05_17.md) | 完整代码规范 |
| [P2_IMPLEMENTATION_CHECKLIST_2026_05_17.md](P2_IMPLEMENTATION_CHECKLIST_2026_05_17.md) | 快速参考清单 |
| [runtime-domain-data-spec-v0.1.md](../specs/runtime-domain-data-spec-v0.1.md) | 数据规格定义 |
| [memory-tree-agent-executable-roadmap-2026-05-16.md](memory-tree-agent-executable-roadmap-2026-05-16.md) | 总体路线图 |

### 关键代码位置

- `contracts.py`: 所有 Pydantic 数据类定义
- `llm_runtime.py`: 预算检查、工具执行包装
- `execution_loop.py`: 主执行循环、SafeStop 处理
- `snapshot.py`: 校验和计算、快照构建

---

## ✅ 验收门槛

全部 4 个任务通过验收需满足：

| 项目 | 标准 | 证据 |
|-----|------|------|
| **功能完整性** | 所有 9 个新函数可调用 | 单元测试通过 |
| **数据一致性** | 所有数据类字段齐全 | 序列化/反序列化成功 |
| **错误处理** | 异常隔离无泄漏 | 工具失败不导致循环断裂 |
| **指标准确** | 跨窗口单调性 100% | metrics 对比检查 |
| **安全性** | 校验和验证通过 | 数据污染测试通过 |
| **向后兼容** | 无破坏性变更 | 现有测试仍通过 |
| **覆盖率** | 新代码测试覆盖 ≥ 90% | pytest coverage report |

---

**生成时间**: 2026-05-17  
**下一步**: 按照检查清单开始实现  
**预期交付**: 5-7 天（并行开发）

