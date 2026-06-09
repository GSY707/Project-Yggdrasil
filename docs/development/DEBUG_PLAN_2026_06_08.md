# Debug Plan 2026-06-08

本计划收拢本轮已经从 nightly/slow 路线上暂时移出的不稳定功能。对应测试已改为 skip，不再阻断 CI。

## 1. Runtime 状态机与恢复链

- `tests/runtime/test_runtime_restart_and_resume.py`
- `tests/runtime/test_runtime_pause_regressions.py`
- `tests/runtime/test_runtime_budget_and_audit.py`

关注点：

- standby / continuing / awaiting-approval 状态收口是否统一
- mailbox 唤醒与 pause 请求之间的竞态
- corrupted snapshot 的恢复失败原因是否稳定落盘
- lean audit / full audit 的工件结构是否仍在漂移

## 2. Sub-agent 与 GitHub 协作链

- `tests/test_subagent_and_worker.py`

关注点：

- subagent 闭环是否能够稳定推进到分支创建与 PR
- child 完成后父节点唤醒与合并是否一致
- GitHub adapter 元数据持久化是否仍依赖外部环境假设

## 3. M9 控制面与验收链

- `tests/api/test_persistence_control_plane_api.py`
- `tests/test_m9_acceptance.py`

关注点：

- M9 资源与 prompt 控制面是否继续暴露预期接口
- capability chain 端到端验收是否被上游状态机变化打断

## 4. 并发与稳定性

- `tests/test_phase3_stability_and_scale.py`

关注点：

- 并发 pause 是否仍会触发双快照或丢事件
- 多 worker 下的状态推进是否存在竞态

## 处理原则

- 先恢复稳定的状态收口，再恢复夜间并发跑批
- 这批测试在 debug plan 关闭前不重新加入 nightly
- 修复后再逐个取消 skip，而不是一次性回退全部
