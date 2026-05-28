# G4 默认网络研究测试失败审计（2026-05-27）

## 范围
- suite: `evalsuite_g4_real_task_web_research_default`
- run: `evalrun_52ffd96d5551405da5b0`
- case: `evalcase_g4_web_research_grid_storage_short64k`
- traceId: `daf482a95425a345238bfa7e5ec09f92`

## 目标态（期望工作流）
- `start` -> `执行网络检索` -> `多源对比与矛盾处理` -> `形成结构化交付`
- 交付必须包含：`## 结果`、`## 证据`、`## 风险`、`## 已知问题`
- 文本必须出现至少一个来源/对比判断短语：`http://` / `https://` / `来源` / `source` / `矛盾` / `contradiction`

## 实际态（本次 run）
- `start` -> `工具回合进入重复幂等循环防护` -> `停止重复工具执行` -> `提前结束`
- case 返回摘要为：
  - `Detected a repeated idempotent tool loop and stopped further duplicate tool execution. Hand off to external verification using the files already written in the workspace.`
- 因为提前结束，最终交付没有进入“多源对比报告”阶段。

## 偏差清单（行为 vs 预期）
1. 交付结构缺失：未产出四段正式报告头。
2. 证据表达缺失：未出现来源链接/来源词/矛盾分析词。
3. 工作流过早止损：停在“去重保护”而非“汇总交付”。
4. 长窗口指标不达标：`cumulativeWindowSpanTokens=1709`，低于阈值 `>=100000`。

## 结论
- 这次失败不是“主题不适配”，而是“执行流程被重复幂等检测提前截断”，导致模型没有进入最终交付节点。
- 当前默认测试已成功切换到“网络检索+多源对比”方向，但运行时还需要保证“去重保护后仍能完成收敛交付”。

## 证据位置
- 运行结果：`.yggdrasil/state/evaluations/evalrun_52ffd96d5551405da5b0.json`
- 观测日志：`.yggdrasil/state/observability/logs.jsonl`
- 关键日志时间点：`2026-05-27T13:31:28+00:00`
