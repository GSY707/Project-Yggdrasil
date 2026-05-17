# 高并发表使用与迁移说明

## 目标

本文档说明本仓库高并发表的推荐使用方式、已实施的迁移和并发优化策略，以及上线前后的验证方法。

## 高并发表清单

当前按写入频次与并发冲突风险识别出的高并发表：

- nodes
- node_versions
- task_snapshots
- import_fragments
- model_invocations

## 已实施优化

### 1) 操作队列（keyed operation queue）

- 新增进程内 keyed 写队列，按业务 key 串行化热点写入。
- 开关：YGGDRASIL_OPERATION_QUEUE_ENABLED（默认开启）。

键策略：

- nodes 相关写入：nodes:{branch_id}
- task snapshot 相关写入：task-snapshot:{task_id}
- import fragments 替换：import-fragments:{import_job_id}
- workspace bootstrap：workspace:default / workspace:branch:{branch_id}

### 2) SQLite 锁等待与重试

- connect timeout
- busy_timeout
- WAL + synchronous=NORMAL
- SQLITE_BUSY/locked 轻量重试

### 3) 事务瘦身

- workspace bootstrap 去掉中间不必要 flush，减少事务内阻塞时间。
- replace_import_fragments 改为批量 insert（executemany 语义），减少 ORM 对象构造与 flush 开销。

### 4) 高并发表索引迁移

迁移脚本：migrations/versions/1e3a7b8c9d01_high_concurrency_indexes.py

新增索引：

- ix_nodes_branch_created_at
- ix_import_fragments_job_created
- ix_task_snapshots_task_status_created
- ix_task_snapshots_task_created
- ix_model_invocations_task_created
- ix_model_invocations_run_created

## 特殊使用方式（必须遵守）

### task_snapshots

- 并发写必须尽量按 taskId 聚合，避免多线程跨 task 混写同一事务。
- 同一 task 的 create_snapshot/supersede_snapshots 通过同一个 queue key 执行。
- 读取最新快照优先使用 task_id + created_at 或 task_id + status + created_at 的查询路径。

### nodes / node_versions

- 同一 branch 的高频写入应在同一 queue key 内提交，减少 parent/child 计数更新冲突。
- 尽量避免事务内做长文本拼接、复杂计算、网络调用。
- 批量导入优先走批量写接口，不要在单请求内大量逐条 flush。

### import_fragments

- 推荐使用 replace_import_fragments 的批量替换路径。
- 不建议多个线程并发替换同一个 import_job_id。

### model_invocations

- 写入阶段以 append 为主，更新阶段尽量只做必要字段。
- 查询统计时应命中 task_id/agent_run_id + created_at 复合索引。

## 迁移执行建议

1. 在低峰窗口执行 Alembic 迁移。
2. 迁移后立即执行并发基准对比脚本。
3. 观察 lock 告警、p95 延迟、吞吐量至少 24 小时。

## 基准脚本

- scripts/benchmarks/sqlite_concurrency_benchmark.py
- scripts/benchmarks/sqlite_concurrency_compare.py

推荐命令：

- uv run python scripts/benchmarks/sqlite_concurrency_compare.py --workers 6 --iterations 40

输出目录默认：

- .yggdrasil/state/benchmarks/sqlite-concurrency/
