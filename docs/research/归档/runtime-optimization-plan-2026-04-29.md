# 运行时间优化总计划 2026-04-29

- 文档状态：Draft
- 日期：2026-04-29
- 目标：让本地非 LLM 开销稳定低于 LLM 时延预算，并据此决定是否需要引入 Rust 等高性能实现
- 关联分析：
  - [test-suite-cpu-time-analysis-2026-04-29.md](./test-suite-cpu-time-analysis-2026-04-29.md)
  - [tests/conftest.py](../../tests/conftest.py)
  - [packages/python-sdk/src/yggdrasil_sdk/prompting.py](../../packages/python-sdk/src/yggdrasil_sdk/prompting.py)
  - [packages/python-sdk/src/yggdrasil_sdk/tool_runtime.py](../../packages/python-sdk/src/yggdrasil_sdk/tool_runtime.py)
  - [packages/python-sdk/src/yggdrasil_sdk/app_catalog.py](../../packages/python-sdk/src/yggdrasil_sdk/app_catalog.py)
  - [packages/python-sdk/src/yggdrasil_sdk/mcp_bridge.py](../../packages/python-sdk/src/yggdrasil_sdk/mcp_bridge.py)
  - [packages/python-sdk/src/yggdrasil_sdk/llm_runtime.py](../../packages/python-sdk/src/yggdrasil_sdk/llm_runtime.py)
  - [packages/python-sdk/src/yggdrasil_sdk/persistence/module_platform.py](../../packages/python-sdk/src/yggdrasil_sdk/persistence/module_platform.py)

## 当前进展

截至 2026-04-29，阶段 0 和阶段 1 已完成第一轮落地：

1. 阶段 0：`llm_runtime.py` 和 `runtime_kernel.py` 已补入分段计时，当前会返回并落盘 prompt 编译、工具规格构造、请求写盘、模型/工具循环、响应写盘和运行时总耗时。
2. 阶段 1：协调层已支持 `YGGDRASIL_COORDINATION_BACKEND=auto|redis|memory`，并为 Redis 失败增加短 TTL 熔断；pytest 与隔离评测环境默认切到 `memory` coordination。
3. 本机 Redis 探测结果：未发现正在运行的 Windows Redis 服务、`redis-server`/`redis-cli` 可执行文件，也未发现 Docker daemon 处于可用状态；仓库内 `infra/docker-compose.yml` 定义了本地 Redis，默认端口为 `127.0.0.1:6379`。
4. 阶段 1 实测：在 `redis://127.0.0.1:6390/15` 不可达条件下，`auto` 模式单次 `flushdb()` 平均约 `209.08 ms`，`memory` 模式约 `0.00 ms`，单步清理等待基本被消除。

截至 2026-04-30，阶段 2 和阶段 3 也已完成第一轮落地：

1. 阶段 2：`app_catalog.py`、`prompting.py`、`tool_runtime.py` 已增加进程级 warm cache；`compile_runtime_prompt()` 已支持直接接收已解析的 registry 和 tool descriptors，避免单轮调用内重复发现。
2. 阶段 3：`mcp_bridge.py` 已把 snapshot 刷新收敛到显式控制路径；工具 binding miss 不再触发热路径全量 sync；builtin MCP server 默认改为 keep-alive。
3. 本机 Redis 已通过 `winget install Redis.Redis` 安装到 `C:\Program Files\Redis`，并已验证 `127.0.0.1:6379` 返回 `PONG`。

截至 2026-04-30，阶段 4 也已完成第一轮落地，并顺手修掉了一条残余回归失败：

1. 阶段 4：`llm_runtime.py` 已支持 `strict`、`default`、`lean` 三档审计级别，可通过请求体 `auditLevel` 或环境变量 `YGGDRASIL_RUNTIME_AUDIT_LEVEL` 指定。
2. `strict` 保留原有全量同步写盘语义；`default` 改为写入关键元数据、message digests、tool/round 摘要与 timings；`lean` 进一步裁剪为更紧凑的 request/response/compiled prompt 工件。
3. `tests/test_runtime_and_pruning.py` 中多轮 pause/resume 的残余失败已修复：测试不再假设不存在的 `current` snapshot status，而是改为使用 `task.active_snapshot_id` 表达“当前快照”语义。

## 最新对比测量

下面这组数值把“之前”分成两类来源：

1. 2026-04-29 已有分析文档中的历史基线。
2. 在当前代码上显式关闭 cache 或关闭 keep-alive，以模拟阶段 2/3 之前的行为。

| 项目 | 之前 | 优化后 | 变化 |
| --- | ---: | ---: | ---: |
| Redis `flushdb()` 不可达基线 | 2046.80 ms | 2.81 ms | -99.86% |
| Redis `flushdb()` 阶段 1 auto 熔断 | 209.08 ms | 2.81 ms | -98.66% |
| `build_application_catalog_snapshot()` | 22.76 ms | 0.20 ms | -99.12% |
| `assemble_prompt_registry()` | 69.78 ms | 0.75 ms | -98.93% |
| `resolve_registered_tool_descriptors()` | 45.09 ms | 0.70 ms | -98.45% |
| `compile_runtime_prompt()` | 78.53 ms | 0.04 ms | -99.95% |
| `mcp.read.read_file` 重复调用 | 715.41 ms | 2.31 ms | -99.68% |

补充说明：

- `build_application_catalog_snapshot()`、`assemble_prompt_registry()`、`resolve_registered_tool_descriptors()`、`compile_runtime_prompt()` 的“之前”值，是通过每次调用前主动清空 cache 来模拟阶段 2 之前的重复装配路径。
- `mcp.read.read_file` 的“之前”值，是把 `workspace-read` 的 `keepAlive` 显式关掉后测出来的；优化后则是 builtin keep-alive 的 steady-state 平均值。
- Redis 的优化后数值使用真实本机 Redis（`127.0.0.1:6379/15`）测得，不再依赖 fallback。

阶段 4 的新增对比测量如下，`strict` 可以视为阶段 4 之前的全量同步写盘语义：

| 项目 | 之前（strict） | 优化后（default） | 变化 |
| --- | ---: | ---: | ---: |
| request 工件体积 | 21081 B | 11435 B | -45.76% |
| response 工件体积 | 1970.80 B | 1021.20 B | -48.19% |
| compiled prompt 工件体积 | 13532 B | 9309 B | -31.21% |
| `writeInitialRequestMs` | 0.49 ms | 0.48 ms | -2.04% |
| `rewriteRequestTranscriptMs` | 0.53 ms | 0.49 ms | -7.55% |
| `writeResponseMs` | 0.43 ms | 0.37 ms | -13.95% |

如果继续把 `default` 压到 `lean`，同一组样本里 response 工件还能从 `1021.20 B` 继续降到 `891.40 B`，`writeResponseMs` 从 `0.37 ms` 继续降到 `0.33 ms`。这组 fallback 样本本来就很轻，所以时间收益不算夸张；阶段 4 的核心收益是把热路径里默认同步写盘的 payload 从“全量 transcript”收敛成“摘要 + digests”。

## 1. 决策结论先写在前面

当前不建议直接进入 Rust 重写。

原因不是“Python 一定够快”，而是当前证据显示：

1. 默认测试已经关闭 live LLM，本地耗时大头并不在模型推理。
2. 已有分析表明，原始 pytest 632.33 s 中约 74.3% 是 Redis 失败连接等待，不是 CPU 计算。
3. 去掉这类等待后，剩余 163.037 s 墙钟时间里，CPU 时间约 21.922 s，说明主要问题仍是装配、I/O、子进程和同步落盘，而不是某个 Python 纯算子把 CPU 打满。
4. 当前热路径里最重的几个动作，主要是重复组装而不是复杂算法：Prompt registry 重建、工具描述解析、MCP tool inventory 同步、catalog/app catalog 重扫、请求与响应工件落盘。

因此，第一方向应当是：

- 先把本地运行时中“不该在热路径里”的同步等待与重复装配拿掉。
- 只有当热路径已经被收敛到“主要剩下稳定的纯计算热点”时，才进入 Rust 或其他高性能语言重写。

## 2. 当前瓶颈判断

从现有代码和分析文档看，当前本地耗时主要由四类东西构成。

### 2.1 明确的失败等待

- [tests/conftest.py](../../tests/conftest.py) 在每个测试里都会尝试 `RedisCoordinator(...).client().flushdb()`。
- [packages/python-sdk/src/yggdrasil_sdk/persistence/coordination.py](../../packages/python-sdk/src/yggdrasil_sdk/persistence/coordination.py) 目前的 `client()` 只是创建 Redis client，本身没有快速失败策略；真正调用时才等待 socket 失败。

这类等待对“让本地逻辑远小于 LLM 耗时”没有任何价值，必须最先消掉。

### 2.2 重复的 prompt 与工具装配

- [packages/python-sdk/src/yggdrasil_sdk/prompting.py](../../packages/python-sdk/src/yggdrasil_sdk/prompting.py) 的 `assemble_prompt_registry()` 每次都会重新装配应用和模块贡献。
- 同文件里的 `compile_runtime_prompt()` 在一次调用里先重建 registry，再通过 `list_registered_agent_tools()` 触发工具描述解析。
- [packages/python-sdk/src/yggdrasil_sdk/tool_runtime.py](../../packages/python-sdk/src/yggdrasil_sdk/tool_runtime.py) 的 `resolve_registered_tool_descriptors()` 又会走一次模块目录快照和插件加载。
- [packages/python-sdk/src/yggdrasil_sdk/app_catalog.py](../../packages/python-sdk/src/yggdrasil_sdk/app_catalog.py) 当前没有像模块 catalog 那样的进程级 TTL cache。

这说明“本地主要工作只是组装提示词”这个判断只说对了一半。当前热路径实际上是在重复做：

1. 应用清单读取。
2. 模块能力选择。
3. Prompt profile 和 seed template 收集。
4. 工具 descriptor 收集。
5. 最终消息拼接。

其中真正应该在每次请求里发生的，只有最后一步和少量动态选择；前四步更适合预编译或缓存。

### 2.3 MCP bridge 的子进程与 stdio 往返

- [packages/python-sdk/src/yggdrasil_sdk/mcp_bridge.py](../../packages/python-sdk/src/yggdrasil_sdk/mcp_bridge.py) 的 `sync_mcp_bridge_servers()` 需要逐个 server 做 `list_tools()`。
- 当 snapshot 不可用或工具绑定未命中时，代码还会触发刷新。
- 这部分墙钟热点主要来自子进程启动、stdio JSON-RPC 往返和关闭，而不是 Python 本身的字符串处理。

这类问题不适合靠 Rust 重写 Python 函数来解决。真正的解法是把 discovery 从请求热路径里挪走，或者把 builtin server 改成进程内直连。

### 2.4 同步落盘与控制面视图组装

- [packages/python-sdk/src/yggdrasil_sdk/llm_runtime.py](../../packages/python-sdk/src/yggdrasil_sdk/llm_runtime.py) 在调用前后会写 prompt artifact、request JSON、response JSON。
- [packages/python-sdk/src/yggdrasil_sdk/persistence/module_platform.py](../../packages/python-sdk/src/yggdrasil_sdk/persistence/module_platform.py) 的 `sync_catalog()` 还会做模块 reconcile、状态写库与快照写盘。

这里的问题也不是 Python 语法太慢，而是同步副作用太多，导致“一个本该轻量的本地前处理”被扩展成了控制面整机工作流。

## 3. 北极星目标

后续所有优化都围绕一个统一目标：

> 在常见运行条件下，本地非 LLM 开销应远小于 LLM 时延，并且在无 LLM 模式下，本地执行路径仍然足够轻量，能够证明系统没有把大量时间浪费在控制面装配上。

建议把目标具体化成下面几个指标。

| 指标 | 目标值 | 说明 |
| --- | ---: | --- |
| 单次主 Agent 无 live LLM 调用的本地总耗时 | P50 <= 100 ms，P95 <= 300 ms | 不含真正模型等待，聚焦 runtime 自身 |
| `compile_runtime_prompt()` 预热后耗时 | P50 <= 10 ms，P95 <= 25 ms | 含动态 task/context 拼接，不含 registry 全量重建 |
| 工具 descriptor 解析 | 预热后 <= 10 ms | 不允许每次都做插件重扫 |
| MCP tool inventory 更新 | 不在请求热路径 | 应转为后台刷新或显式控制面动作 |
| 单次调用同步写盘 | <= 30 ms | 更重的审计改异步或分级 |
| 本地非 LLM 总耗时 / 代表性 LLM P50 | <= 10% | 例如 2 s LLM，则本地目标 <= 200 ms |

如果这些指标做到位，通常不需要 Rust；如果做不到，再看是否存在明确的纯计算热点值得原生化。

## 4. 执行策略

### 阶段 0：先建立可决策的测量面

目标：不要在没有分段计时的情况下做“大改再猜”。

工作项：

1. 给 runtime 主链路补分段计时。
2. 至少拆出这些区段：root mount、prompt registry、tool registry、prompt compile、MCP snapshot/load、模型调用前工件落盘、模型调用后工件落盘、写回 payload 组装、持久化提交。
3. 为三类场景建立固定 benchmark：
   - 单次 main-agent 无工具调用。
   - 单次 main-agent 含工具描述装配但不执行工具。
   - 单次 main-agent 含 MCP tool call。
4. 对 `tests/test_runtime_and_pruning.py`、`tests/test_module_host_eventing.py`、`tests/test_persistence_api.py` 建立可重复的 profile 命令。

交付物：

- 一份基准命令清单。
- 一份分段耗时基线表。
- 一张火焰图或等价 profile 输出。

### 阶段 1：消除确定性的无效等待

目标：先清掉“每次都知道不值得等”的部分。

工作项：

1. 给协调层增加显式 backend 选择，例如 `redis` / `memory`。
2. 测试默认直接走 memory coordination，而不是连一个已知不可达的 Redis 再失败。
3. 即使仍允许 Redis，也要把 connect timeout 和 command timeout 收缩到非常小的量级，并对失败结果做短 TTL 熔断，避免连续重试。
4. 检查 worker、测试夹具、评测环境里是否还存在类似的阻塞等待。

退出条件：

- pytest 总时长先掉一大截。
- 再跑 profile 时，不再看到明显的 2 秒级重复失败等待。

### 阶段 2：把 prompt 装配变成“预编译 + 小增量”

目标：把真正需要每次运行的动作压缩到动态差量。

工作项：

1. 给 [packages/python-sdk/src/yggdrasil_sdk/app_catalog.py](../../packages/python-sdk/src/yggdrasil_sdk/app_catalog.py) 增加与模块 catalog 对齐的进程级缓存和失效机制。
2. 给 `assemble_prompt_registry()` 增加缓存，key 至少包含 appId、activeCapabilities、应用配置版本、模块 profile 版本。
3. 让 `compile_runtime_prompt()` 接收已解析的 registry 与 tool descriptors，避免同一轮调用里重复发现。
4. 把静态部分预编译成 runtime bundle：
   - Prompt profiles
   - Seed templates
   - 已过滤的 module contribution
   - Tool descriptors
   - 应用重要配置
5. 每次运行只做：
   - 选择 profile/template
   - 注入 task/root mount/current context
   - 拼接最终 messages

退出条件：

- warm path 下 prompt compile 与 tool resolve 基本不再依赖目录扫描和插件加载。
- 火焰图里 `assemble_prompt_registry()` 与 `resolve_registered_tool_descriptors()` 热度明显下降。

### 阶段 3：把 MCP bridge 从热路径里拿出去

目标：请求执行时只消费结果，不做 discovery。

工作项：

1. 把 MCP snapshot 刷新改成以下触发源：
   - 服务启动。
   - 配置变更。
   - 显式管理命令。
   - 后台 TTL 刷新。
2. 工具执行路径不再因为 binding miss 就同步全量 refresh；最多只刷新单个 server，且要可控。
3. 对 builtin MCP server，优先评估进程内直连或长期 keep-alive session，避免每次 stdio 启停。
4. 如果 builtin server 本质上只是仓库读写/搜索/Python 执行，优先把“本地模式”直接走 in-process adapter，而不是再套一层 stdio MCP。

退出条件：

- runtime 与 module-host 的主要墙钟热点不再是 `_reader_loop()`、`readline()`、子进程关闭等待。

### 阶段 4：降低同步审计与序列化成本

目标：保留可观测性，但不要在热路径里把所有审计都做成强同步。

工作项：

1. 区分审计级别：`strict`、`default`、`lean`。
2. 本地 benchmark 与常规开发模式优先用 `default` 或 `lean`。
3. prompt/request/response artifact 改为可异步、批量或按采样写入。
4. JSON 序列化优先引入更快的边界层实现，例如 `orjson` 或 `msgspec`，但只限于稳定的文件/网络边界。
5. 减少热路径里的 `model_validate` / `model_dump` 往返，内部尽量保留原始 dict 或轻量结构。

退出条件：

- 单次无 LLM 调用的本地路径主要只剩少量 DB 写入和必要状态更新。

### 阶段 5：再看 Python 级微优化

只有在前四个阶段做完后，Python 微优化才有意义。

工作项：

1. 减少重复的 YAML 读取与 schema 规范化。
2. 减少重复的字符串拼接与大对象拷贝。
3. 把内部热点数据结构从 Pydantic 模型切到更轻的 dataclass、TypedDict 或裸 dict。
4. 针对明确热点做定点优化，而不是全仓库统一“去 Pydantic”或“去 SQLAlchemy”。

## 5. Rust 或其他高性能语言的决策门槛

只有同时满足下面三个条件，才建议进入原生重写：

1. 阶段 1 到阶段 4 完成后，火焰图里仍有稳定、可复现、纯计算型热点。
2. 该热点占本地非 LLM 时间至少 30%，或者单次调用 P95 仍然大于 50 ms。
3. 该热点具有清晰、窄边界输入输出，可以脱离数据库、HTTP、子进程、框架上下文独立运行。

### 5.1 值得考虑原生化的候选

- context pruning 的评分或排序核。
- relation discovery 的批量相似度或图构建核。
- 大批量 JSON 规范化或 schema 映射。
- 若后续证明确实存在超大 prompt 模板渲染瓶颈，则可考虑 prompt rendering kernel。

### 5.2 不值得先原生化的部分

- Redis 连接失败等待。
- MCP stdio 往返。
- FastAPI 路由分发。
- SQLAlchemy 仓储 CRUD。
- 应用清单与模块清单扫描。
- 请求/响应审计文件写盘。

这些问题的主要矛盾是执行模型，而不是语言运行时。

### 5.3 如果要做原生化，优先选型

首选：Rust + PyO3 + maturin。

原因：

1. 可以保留 Python 作为编排层。
2. 适合把小而热的纯计算核嵌回当前运行时。
3. 不需要把整个服务边界和部署模型一起重写。

不建议的起手式：

- 直接把 runtime kernel、llm_runtime、module_platform 整体迁到 Rust。
- 为了“追求性能”引入跨进程重写，反而增加 IPC 成本。

## 6. 如果阶段 1 到阶段 5 后仍然不够快，说明该做架构重构

如果优化后仍然达不到“本地远小于 LLM”的目标，问题基本就不是 Python 解释器，而是当前架构把太多控制面动作放进了执行热路径。

这时应按下面的方向做架构调整。

### 6.1 预编译运行时装配包

把这些内容变成应用或模块变更时生成的 bundle，而不是运行时按次装配：

- 应用 manifest 解析结果。
- Prompt registry。
- Tool registry。
- Scene/module capability 过滤结果。
- 应用重要配置合并结果。

运行时只读取 bundle 并注入 task-specific delta。

### 6.2 把 MCP 变成常驻网关，而不是按需 discovery

让 MCP bridge 更像 sidecar/gateway：

- 长期维持 server session。
- 持有最新 tool inventory。
- 向 runtime 暴露只读快照与稳定调用接口。

### 6.3 把审计从“主路径强同步”改成“主路径最小同步 + 异步补全”

保留关键状态强同步：

- 任务状态。
- budget。
- snapshot 指针。

其余内容改成异步或批量：

- 大 JSON artifact。
- 详细工具执行原始输出。
- 可观测性扩展字段。

## 7. 建议的执行顺序

建议按下面顺序做，而不是并行大改。

1. 阶段 0：补可观测与 benchmark。
2. 阶段 1：先消掉 Redis 这类确定性无效等待。
3. 阶段 2：收敛 prompt/tool 装配。
4. 阶段 3：把 MCP discovery 拿出热路径。
5. 阶段 4：削减同步审计与序列化。
6. 复测一次。如果本地非 LLM 时长已经进入目标区间，停止，不做 Rust。
7. 如果仍存在稳定纯计算热点，再对单独 kernel 做 Rust PoC。
8. 如果热点依然主要是 orchestration / I/O / subprocess，则转入架构重构，不做语言迁移。

## 8. 立即执行清单

下一轮实际工作建议直接做下面 8 项。

1. 给 runtime 主链路补分段计时和 profile 命令。
2. 为 coordination 增加 memory backend 直通模式，并让测试默认启用。
3. 给 app catalog 增加进程级缓存和失效钩子。
4. 给 prompt registry 与 tool descriptor 增加 warm cache。
5. 重构 `compile_runtime_prompt()`，避免一次调用里重复发现 registry 和 tools。
6. 把 MCP snapshot refresh 改成后台或显式控制面动作。
7. 给 LLM 审计工件增加 `lean` 模式，允许本地 benchmark 关闭大对象同步落盘。
8. 复跑基准，并用结果决定是否需要 Rust kernel PoC。

## 9. 最终判断标准

如果本地主要工作真的是“组装提示词”，那么在优化完成后，单次无 LLM 路径的耗时曲线应表现为：

- 少量状态读取。
- 少量动态上下文选择。
- 一次轻量 prompt 拼接。
- 最小必要状态提交。

而不应表现为：

- 目录重扫。
- 插件重载。
- MCP 子进程工具发现。
- 多份大 JSON 同步落盘。
- 控制面全量快照重算。

只要火焰图里仍以后者为主，方向就应该是继续削减装配和同步副作用，而不是先把 Python 改写成 Rust。