# 世界树计划 · 记忆树理论目标差距评估（2026-05-17）

- 文档状态：Assessment
- 日期：2026-05-17
- 评估目标：衡量当前实现与“模型全部记忆存在于记忆树，当前上下文窗口仅承载一次最小子任务工作内容”之间的差距。

---

## 1. 目标定义（理论口径）

目标可拆为两条硬约束：

1. 全量记忆主存放在记忆树：恢复、推理、交付依赖可检索结构化记忆，而非窗口残留文本。
2. 当前窗口只承载最小子任务工作集：每轮仅保留执行指针、必要证据和当前动作输入，不携带大规模仓库原文。

理论来源见：

- `docs/research/pseudo-infinite-context-window-roadmap-2026-05-16.md`
- `docs/research/系统核心理念.md`

---

## 2. 已实现能力（正向）

1. 运行时会把 currentContext 物化为节点，并写入 sourceWindowIndex/sourceWorkTreeNodeId/sourceRunId。
2. 检索链会把 retrieval 结果回填到 currentContext，并同步 memoryRetrievalState 到 request/root mount。
3. restart snapshot 已保留 responseRequirements/restartMessage/takeoverProtocol/memoryRetrievalState 等关键合同字段。
4. carry-forward package 有 token 上限与重复信息去重机制。
5. context pruning 已有合同字段保护策略（responseRequirements/restartMessage/workTree/takeoverProtocol）。
6. G4 评测已包含 restartCount/windowIndex/cumulativeWindowSpanTokens 与 acceptance contract 检查。

关键实现入口：

- `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop.py`
- `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/snapshot.py`
- `modules/text-memory/src/yggdrasil_text_memory/plugin.py`
- `modules/context-pruning/src/yggdrasil_context_pruning/plugin.py`
- `packages/python-sdk/src/yggdrasil_sdk/evaluation_runtime/suite_cases_g4.py`

---

## 3. 主要差距（反向）

## 3.1 高优先级差距

1. 当前窗口仍是事实主载体，而非严格最小子任务工作集。
   - 证据：execution loop 在恢复后仍直接读取/合并 currentContext，并将其作为后续主输入。
2. carry-forward 仍主要是自然语言摘要包，不是“执行指针 + 结构化最小证据”的强约束包。
   - 证据：carry-forward 由 currentContextState 摘要拼接生成，允许语义损失。
3. 真实任务 parity 用例本身仍可注入大量文件/glob 语料，不符合“窗口仅最小子任务”实验设计。
   - 证据：g4-real-task-web-research-default 用例包含大规模 currentContextFiles 与 currentContextGlobs。
4. 评测读取链存在语料类型鲁棒性缺陷（.pyc 当文本读取），导致 parity 结论可被装载错误阻断。
   - 证据：suite_cases_g4 直接按文本解码 currentContextFiles，遇二进制会失败。

## 3.2 中优先级差距

1. 检索排序仍是 token overlap + 规则加权，缺少更强语义召回，导致为避免漏召回而倾向保留更大上下文。
2. pruning 的合同保护依赖 id/kind/title 关键词命中，属于软识别策略，不是协议级硬绑定。
3. memory-write 机制是能力可用而非执行强制，仍允许不写树路径完成回合。

## 3.3 低优先级差距

1. 运行时审计产物与对话 digest 仍并存于工件体系，尚未统一映射到记忆树节点图谱。
2. 在跨 provider parity 上，技术闭环证据强于交付等价证据，发布口径仍需持续冻结。

---

## 4. 量化评分

采用 5 维评分（0-100，越高越接近目标）：

1. 记忆写入与持久化完备度：78
2. 基于记忆树的检索与恢复连续性：70
3. 窗口最小化（仅最小子任务工作集）：42
4. 交付级 parity 与验收稳定性：55
5. 评测与语料链鲁棒性：50

综合完成度（加权）= 59/100。

对应差距 = 41/100。

---

## 5. 结论

一句话结论：

当前项目在“记忆树 + 多窗口重启技术闭环”上已经达到可用水平，但距离“全部记忆上树、窗口仅保留一次最小子任务工作集”的目标仍有明显工程差距，当前可量化差距约为 41%。

这 41% 里，最大缺口不是“有没有 restart”，而是“窗口最小化与交付等价是否被硬约束并被稳定验证”。

