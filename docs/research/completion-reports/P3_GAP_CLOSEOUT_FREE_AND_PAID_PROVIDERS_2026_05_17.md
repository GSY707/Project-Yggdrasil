# 世界树计划 · P3 缺口收口：Free 默认与少量 Paid Provider（2026-05-17）

- 文档状态：Gap Closeout
- 日期：2026-05-17
- 范围：收口 P3 剩余工程缺口，使真实任务 parity 具备多 provider 复跑能力，同时保持 free 默认、paid 受控。

---

## 1. 缺口定义

P3 原始工程接线已经完成，但还有两处发布级缺口：

1. paid provider 仍只受全局环境变量 `YGGDRASIL_ALLOW_PAID_MODELS` 控制，评测 case 不能显式声明“批准少量 paid”。这会导致 live parity 复跑要么全局放开 paid，要么完全不可用。
2. `realTaskWindowParity` 聚合会把所有 short-window 行与所有 long-window 行直接混算；一旦把 DeepSeek paid case 加进来，LongCat 与 DeepSeek 的样本会被错误平均成一个 parity 结论。

---

## 2. 本次收口

### 2.1 Case 级 paid 批准

- 文件：`packages/python-sdk/src/yggdrasil_sdk/evaluation_runtime/bootstrap.py`
- 文件：`packages/python-sdk/src/yggdrasil_sdk/evaluation_runtime/suite_runner.py`

变更：

- `isolated_runtime_environment` 与 `local_evaluation_runtime_environment` 现在显式管理 `YGGDRASIL_ALLOW_PAID_MODELS`，避免持久终端里的历史环境变量泄漏到评测沙箱。
- suite case 新增 `allowPaidModels`，只有声明该字段的 case 才会在隔离环境中打开 paid catalog。

结论：评测默认保持 free-only；paid provider 变成显式批准的局部例外，而不是全局副作用。

### 2.2 Multi-provider parity 分组

- 文件：`packages/python-sdk/src/yggdrasil_sdk/evaluation_runtime/scorer.py`

变更：

- 新增 `realTaskWindowParityGroups`。
- parity 汇总现在按 `parityPairKey + provider + model` 分组后再分别计算 short/long parity。
- 当只有一组时，仍保留兼容的 `realTaskWindowParity` 单对象输出；当有多组时，`realTaskWindowParity` 变成 group summary，总体通过条件是全部 group 都通过。

结论：LongCat free 与 DeepSeek paid 不再被混成一条虚假的平均 parity。

### 2.3 真实任务 parity suite 扩展

- 文件：`evaluation/suites/g4-real-task-window-parity.json`

变更：

- 保留现有 LongCat free `64k/128k` 对照。
- 新增 DeepSeek paid-approved `64k/128k` 对照。
- DeepSeek case 显式声明 `allowPaidModels=true` 与小额 `costBudgetTotal=2.0`。

结论：当前官方 parity suite 已具备 “free 默认 + 少量 paid” 的双 provider 复跑结构。

---

## 3. 验证

执行命令：

```powershell
uv run pytest -q tests/test_g4_multiscene.py
```

结果：`14 passed`。

本次新增/覆盖验证点：

1. `evalsuite_g4_real_task_window_parity` 现在包含 4 个 case：2 个 LongCat free、2 个 DeepSeek paid-approved。
2. 隔离评测环境会主动清理遗留 `YGGDRASIL_ALLOW_PAID_MODELS`，只有 `allowPaidModels=true` 才会重新打开。
3. parity 聚合会按 provider group 分开输出，不再混算。

---

## 4. 结论

P3 的剩余工程缺口已经收口。当前仓库已经具备：

1. free provider 为默认基线。
2. paid provider 仅在 case 级被显式批准时进入 live parity 路径。
3. real-task parity 可以在多 provider 下输出不混淆的正式结论。

还未完成的部分不再是工程接线，而是 live 结果本身是否达到严格 acceptance 与 parity 门槛。