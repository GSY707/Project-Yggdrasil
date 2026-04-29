# 世界树计划 · 冻结材料内部试跑（DeepSeek V4）

> 关联材料：
> - docs/research/real-user-validation-plan-2026-04-30.md
> - docs/research/real-user-validation-baseline-freeze-2026-04-30.md
> - evaluation/fixtures/real-user-validation/task-pack-2026-04-30.md
> - evaluation/fixtures/real-user-validation/scorecard-template-2026-04-30.csv

---

## 1. 本轮目标

本轮在冻结材料上完成 DeepSeek provider 侧更新后的内部试跑与调试，重点验证：

1. DeepSeek 直连 provider 是否已切换到 `deepseek-v4-flash` / `deepseek-v4-pro`。
2. thinking mode、`reasoning_effort`、`reasoning_content` 回传是否能支撑真实工具闭环。
3. 是否能在冻结任务卡上拿到可用的成本、首响和总耗时数据。

---

## 2. 本轮代码更新摘要

本轮先完成了如下运行时修复：

1. `adapters/model-providers/src/yggdrasil_model_providers/gateway.py`
   - DeepSeek 默认模型更新为 `deepseek-v4-flash`。
   - provider catalog 同时暴露 `deepseek-v4-flash` 与 `deepseek-v4-pro`。
   - 价格切换到官方最新表中的当前有效价，并按每千 tokens 估算。
   - 请求面接入 `thinking` 与 `reasoning_effort`。
   - 解析并返回 `reasoningContent`。
   - 对 DeepSeek 工具名做 provider 侧别名转换，避免 `mcp.search.search_text` / `text_memory.retrieve` 这类带点号的名称触发 400。
2. `packages/python-sdk/src/yggdrasil_sdk/llm_runtime.py`
   - 多轮工具循环中保留 `reasoning_content`，确保后续轮次完整回传。
   - 请求审计工件记录 `thinking` / `reasoningEffort`。
   - `rounds` 摘要新增每轮 `latencyMs` 与 `reasoningContentPresent`，便于记录首响。
3. `tests/test_deepseek_gateway.py`
   - 新增窄回归测试，覆盖 DeepSeek V4 模型清单、thinking 参数、`reasoning_content` 回传和工具名别名映射。

回归验证：

- `uv run pytest -q tests/test_deepseek_gateway.py` 通过。

---

## 3. 试跑口径

### 3.1 计入结果的试跑

本轮正式计入结果的内部试跑共 2 条，均使用冻结任务卡语义，且拿到了完整运行时工件与成本记录：

| 任务卡 | 模型 | 形态 | 首次有效输出 | 总耗时 | costUsed | 结果 |
|--------|------|------|-------------|--------|----------|------|
| YGG-CI-01 | deepseek-v4-flash | Pack B 读仓库干跑 | 5927.60 ms | 46849.12 ms | 0.057249 | 可计入，通过；但搜索轮次偏多 |
| YGG-CG-03 | deepseek-v4-flash | safe-stop / resume 工具闭环 | 4917.69 ms | 15896.98 ms | 0.014691 | 可计入，通过 |

本轮计入成本合计：`0.071940`

### 3.2 说明

- 成本取自 runtime 持久化的 `costUsed`，属于基于官方价格表的运行时估算，不是 DeepSeek 后台账单导出值。
- 首次有效输出使用 `responsePayload.rounds[0].latencyMs` 作为近似值；当前 runtime 仍未提供真正的流式首 token 观测。

---

## 4. 计入试跑详情

### 4.1 YGG-CI-01 · 当前仓库补统一 M9 acceptance 入口（读仓库干跑）

- 任务口径：基于 Pack B 当前仓库，要求先读仓库定位，再给出最小改动点与最窄验证方案；内部干跑不实际改文件。
- 真实行为：DeepSeek Flash 连续调用了 MCP 搜索与读文件工具，完成了现有 eval 入口、README 评测段落与相关文件定位。
- 结果判断：可计入，通过。

优点：

1. 输出聚焦到真实仓库而不是泛泛而谈。
2. 能把 `package.json`、README、目录文档三处修改点串起来。
3. 证明 DeepSeek 直连已经能稳定走通带点号的 MCP 工具名。

缺点：

1. 工具轮次明显偏多，存在重复搜索和重复读文件。
2. `finishReason=length`，说明在当前提示与工具集合下，收尾有被 token 上限截断的风险。

### 4.2 YGG-CG-03 · safe-stop / resume 工具闭环

- 任务口径：围绕冻结材料的异常恢复场景，要求先恢复已归档上下文，再给出保留摘要与后续计划。
- 真实行为：DeepSeek Flash 按顺序调用 `text_memory.retrieve` 与 `context_pruning.plan`，随后给出恢复报告。
- 结果判断：可计入，通过。

关键观察：

1. 三轮模型调用里 `reasoningContentPresent` 全为 `true`，说明 `reasoning_content` 回传链路已跑通。
2. 两个必需工具都成功执行，DeepSeek 工具名正则兼容修复有效。
3. 该场景总耗时显著低于读仓库型试跑，且结果质量更稳定。

---

## 5. 调试过程中的额外发现

### 5.1 凭证问题

初始试跑直接命中 DeepSeek 官方 401，原因是当时仓库里的 `LLM.txt` 被误当作 live 配置来源，且其中旧 DeepSeek key 无效。后续试跑改为使用会话级环境变量覆盖；当前代码已禁用 `LLM.txt` 作为凭据来源。

### 5.2 DeepSeek 工具名正则限制

初始真实工具试跑直接返回 400：

- `tools[0].function.name` 必须匹配 `^[a-zA-Z0-9_-]+$`

现有系统工具名大量采用 `module.tool` 形式，因此在 provider 侧增加了别名映射。该修复是本轮最关键的兼容性补丁之一。

### 5.3 提示约束不足会导致试跑失真

本轮有两类未计入结果的探索性尝试：

1. 非工具干跑若不给足材料边界，模型会停在“先看仓库/先补证据”阶段，信息密度不足。
2. 读仓库型性能分析若开放过多 MCP 工具且任务目标过宽，DeepSeek Pro 会出现持续搜索，最终打满工具轮次上限。

结论：

- 后续正式用户测试前，最好给 internal pilot / live eval 增加工具 allowlist 或更强的任务边界约束。

---

## 6. 未计入结果的探索性样本

以下样本保留为调试证据，不纳入本轮正式试跑统计：

| 样本 | 模型 | 结果 | 备注 |
|------|------|------|------|
| YGG-CG-01（纯材料干跑） | deepseek-v4-flash | 完成但低价值 | 输出停在“先看现场”，说明 Pack A 若未实例化为真实仓库，单靠摘要材料不足以支撑高质量回答 |
| YGG-CI-02（纯材料干跑） | deepseek-v4-pro | 完成但低价值 | 输出仍偏调查起手，未形成足够具体的证据链 |
| YGG-CI-02（读仓库干跑） | deepseek-v4-pro | 失败 | 触发 `Tool round limit exceeded`，表明热路径分析场景需要更窄工具集或更强停止条件 |

---

## 7. 当前判断

本轮可以确认：

1. DeepSeek V4 直连已经在当前仓库里跑通真实调用。
2. thinking mode + `reasoning_content` 回传链路对工具场景是有效的。
3. DeepSeek 对 dotted tool name 的兼容问题已经在 provider 侧修复。
4. 冻结材料上的内部试跑可以开始做，但要优先选择任务边界更清晰、工具集合更窄的场景。

当前仍需继续优化：

1. 读仓库型试跑的工具轮次控制。
2. Pack A / Pack C 类型材料的实例化方式，否则纯摘要干跑质量不稳定。
3. 首 token 级别的首响观测；当前只能记录首轮完成时间。