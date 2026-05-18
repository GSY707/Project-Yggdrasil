# 世界树计划 · 两个失败用例摘要报告（2026-05-17）

- 文档状态：Failure Summary（已完成）
- 日期：2026-05-17
- 范围：仅描述 `tests/test_runtime_and_pruning.py` 中两个失败用例的错误现象与大致原因。

---

## 1. 失败用例一

- 用例：`test_main_agent_runtime_pause_resume_closed_loop`
- 失败断言：`task.budget.token_budget_used > 0`
- 实际现象：`token_budget_used == 0`，触发断言失败。
- 相关位置：
  - 断言位置：`tests/test_runtime_and_pruning.py`
  - 预算检查逻辑：`packages/python-sdk/src/yggdrasil_sdk/llm_runtime.py`
  - 预算回写逻辑：`packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop.py`

### 大致原因（高层）

本轮执行很可能在模型调用前就进入了 pre-invocation budget-check 分支，导致本轮实际 token 使用没有累加到任务预算；但执行链仍继续进入 pause 路径，最终表现为“任务暂停成功但 budget used 仍为 0”。

---

## 2. 失败用例二

- 用例：`test_main_agent_runtime_fails_when_actual_usage_exceeds_budget`
- 失败断言：`processed["result"]["status"] == "failed"`
- 实际现象：返回状态是 `completed`，断言失败。
- 相关位置：
  - 断言位置：`tests/test_runtime_and_pruning.py`
  - pre/post 预算检查：`packages/python-sdk/src/yggdrasil_sdk/llm_runtime.py`
  - 状态机分支：`packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop.py`

### 大致原因（高层）

该用例期望覆盖“模型调用后超预算失败”的分支，但实际运行更可能先触发了 pre-invocation budget-check，未进入预期的后置超预算失败语义；而当前运行时主循环对 budget-check 结果处理路径没有把该场景统一落到 `failed`，最终任务状态落成了 `completed`。

---

## 3. 复现命令与结果

执行命令：

```powershell
uv run pytest -q tests/test_runtime_and_pruning.py::test_main_agent_runtime_pause_resume_closed_loop tests/test_runtime_and_pruning.py::test_main_agent_runtime_fails_when_actual_usage_exceeds_budget
```

结果：`2 failed`，与上述现象一致。

---

## 4. 结论

这两个失败都集中在“预算检查与状态机落态的一致性”问题上：

1. 预算预检分支会影响预算累积与后续断言预期。
2. 用例期望的后置超预算失败路径，与实际进入的分支存在偏差。
3. 当前状态回写语义对 `budget-check` 场景仍有不一致表现。
