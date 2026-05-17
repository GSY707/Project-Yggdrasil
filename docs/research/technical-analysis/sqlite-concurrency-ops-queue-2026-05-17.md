# SQLite 并发优化研究（2026-05-17）

## 背景

运行中出现 SQLite locked 告警，说明多个写事务在同一时段竞争文件锁。当前项目存在 worker + runtime + 测试并发写路径，SQLite 在默认模式下容易触发短时写冲突。

本次改动已先落地两项低风险优化：

- 持久化层：增加 SQLite connect timeout、busy_timeout、WAL 与同步策略配置。
- 并发测试：Phase3 并发用例切换为独立数据库文件，并在锁冲突时执行短退避重试。

## 结论

### 1) 操作队列能否用于本项目

可以，且建议只在热点写路径先做“窄范围应用”，不要一刀切。

适合上队列的操作：

- 同一 taskId 的状态推进与快照写入。
- 同一 branchId/spaceId 的高频节点写入（批量导入、并发子代理写入）。
- 对一致性要求高但低延迟要求一般的审计/统计写入。

不建议上队列的操作：

- 用户同步读路径。
- 需要立即可见的强一致交互（除非采用同步确认机制）。

推荐方案：

- 采用 keyed queue（按 taskId 或 branchId 分桶）。
- 每个 key 同时仅允许 1 个 writer 执行，跨 key 允许并行。
- 保留幂等键（operationId）避免重放重复写。

预期收益：

- 显著降低同 key 锁竞争。
- 更稳定的 P95/P99 延迟。
- 降低 locked 类告警密度。

代价：

- 写入变为“排队后提交”，尾延迟在突发期上升。
- 需要额外观测指标与死信/补偿机制。

## 2) 能否使用更放开的锁策略

可以，但建议在 SQLite 场景采用“温和放开”，不建议直接切到最激进模式。

推荐顺序：

1. busy_timeout（已落地）
2. journal_mode=WAL（已落地）
3. synchronous=NORMAL（已落地）
4. 在少数热点写事务上增加应用层重试（已在并发测试验证）

不建议默认开启：

- 全局 read_uncommitted：会引入脏读风险。
- 全局 EXCLUSIVE 事务：会抑制并发。

可选增强：

- 只在写路径开始时使用 BEGIN IMMEDIATE，提前拿写锁，减少中途升级失败。
- 将 checkpoint 策略改为受控触发，避免高峰期 checkpoint 抢占 IO。

## 3) 如何缩短事务时间（包括合并操作）

可行，且是提升 SQLite 并发最直接的方法之一。

优先级建议：

1. 把事务内非数据库工作前移到事务外
- 例如格式化、序列化、模型转换、长字符串拼接等。

2. 合并细碎写入为批量写入
- 多次单行 insert/update 改为批量执行。
- 同一请求内对同一实体的多次更新合并为一次最终状态更新。

3. 减少不必要 flush 次数
- 保留必要边界，避免每一步 flush。

4. 缩短事务生命周期
- 读写分离，先读后算，最后短事务提交。

5. 引入轻量 outbox/异步化
- 把非关键同步写（审计、统计）转为异步消费。

## 4) 是否能提升数据库并发性能

能提升，但上限受 SQLite 单文件写模型约束。

阶段性收益路径：

- 阶段 A（已进行）：timeout + busy_timeout + WAL + 轻重试。
- 阶段 B（建议下一步）：热点键队列化 + 批量写 + 事务瘦身。
- 阶段 C（规模继续增长时）：将高并发表迁移到 PostgreSQL，SQLite 保留本地/评测/轻量场景。

## 5) 建议的落地计划

1. 先观测 3 天
- 指标：locked 告警频次、重试命中率、事务时长 P95、写入吞吐。

2. 选 1 条热点路径做 keyed queue 试点
- 建议从 task 快照写路径开始。

3. 对 import/批量写路径做一次事务瘦身
- 减少 flush、合并 update、批量插入。

4. 复测 Phase3 并发与 live 评测
- 对比变更前后锁冲突和耗时。

## 已实现文件

- packages/python-sdk/src/yggdrasil_sdk/persistence/settings.py
- packages/python-sdk/src/yggdrasil_sdk/persistence/database.py
- tests/test_phase3_stability_and_scale.py
