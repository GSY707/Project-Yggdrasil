# Infra

这个目录承载本地联调所需的基础设施，以及 M8 收口阶段新增的观测与 smoke 入口。

当前 compose 文件提供：

- PostgreSQL
- Redis
- NATS JetStream
- MinIO
- Temporal
- Temporal UI
- Jaeger UI
- OpenTelemetry Collector

另外提供一份独立的 Langfuse 本地自托管 compose：

- `infra/langfuse-compose.yml`
- `pnpm infra:langfuse:up`
- `pnpm infra:langfuse:down`
- `pnpm infra:langfuse:logs`

启动与停止：

- `pnpm infra:up`
- `pnpm infra:down`
- `pnpm infra:smoke`

如果本机已有端口占用，可以在执行前覆盖宿主端口，例如：

- `YGGDRASIL_MINIO_CONSOLE_PORT=19001`
- `YGGDRASIL_TEMPORAL_UI_PORT=18088`
- `YGGDRASIL_JAEGER_UI_PORT=16687`
- `YGGDRASIL_OTEL_COLLECTOR_HTTP_PORT=14318`

建议的本地环境变量：

- `YGGDRASIL_OTEL_EXPORTER_OTLP_ENDPOINT=http://127.0.0.1:4318`

如果使用 Langfuse Cloud：

- `LANGFUSE_PUBLIC_KEY=...`
- `LANGFUSE_SECRET_KEY=...`
- `LANGFUSE_BASE_URL=https://cloud.langfuse.com`

如果使用本机自托管 Langfuse：

- `LANGFUSE_BASE_URL=http://127.0.0.1:3100`
- `LANGFUSE_PUBLIC_KEY=pk-lf-yggdrasil-local`
- `LANGFUSE_SECRET_KEY=sk-lf-yggdrasil-local-secret`

其中 OpenTelemetry 走 OTLP/HTTP，Collector 会把 traces 转给 Jaeger，并把 traces/metrics 同时输出到 debug exporter；Langfuse 继续作为真实 generation 的正式观测出口。

Langfuse 本机自托管说明：

- 默认 UI 地址：`http://127.0.0.1:3100`
- 默认登录账号：`admin@example.com`
- 默认登录密码：`LangfuseLocal123!`
- 默认项目 public key：`pk-lf-yggdrasil-local`
- 默认项目 secret key：`sk-lf-yggdrasil-local-secret`

注意区分两类 key：

- 本机自托管 Langfuse 本身不需要企业 license key，也不需要额外的 instance management API key。
- 但如果要让世界树运行时把 traces / generations 写进 Langfuse，仍然需要 Langfuse 项目的 public/secret key。上面这组默认值已经通过 headless init 预置好了，本地联调可以直接使用。

Langfuse 默认还会拉起自己的一组依赖：PostgreSQL、Redis、ClickHouse、MinIO、web、worker。为了避免和世界树现有 infra 冲突，这组服务使用单独的 compose 文件和单独的本机端口，默认如下：

- web：`3100`
- worker：`3130`
- postgres：`15432`
- redis：`16379`
- clickhouse http：`18123`
- clickhouse native：`19092`
- minio api：`19090`
- minio console：`19091`

如有端口冲突，可以覆盖对应环境变量：

- `YGGDRASIL_LANGFUSE_WEB_PORT`
- `YGGDRASIL_LANGFUSE_WORKER_PORT`
- `YGGDRASIL_LANGFUSE_POSTGRES_PORT`
- `YGGDRASIL_LANGFUSE_REDIS_PORT`
- `YGGDRASIL_LANGFUSE_CLICKHOUSE_HTTP_PORT`
- `YGGDRASIL_LANGFUSE_CLICKHOUSE_NATIVE_PORT`
- `YGGDRASIL_LANGFUSE_MINIO_API_PORT`
- `YGGDRASIL_LANGFUSE_MINIO_CONSOLE_PORT`

备份与恢复：

- `pnpm ops:backup` 会创建一个新的运行时快照，默认落到 `./.yggdrasil-backups/<timestamp>`。
- `pnpm ops:restore` 会恢复最近一次快照；需要恢复指定快照时，改用 `uv run python -m yggdrasil_sdk.ops_cli backup restore --snapshot <path>`。

备份内容包括：

- SQLite 数据库文件，或 PostgreSQL 的 `pg_dump` SQL dump
- 整个 state-root
- 一份 `metadata.json`

注意事项：

- PostgreSQL 备份恢复依赖本机可用的 `pg_dump` 和 `psql`。
- 应用服务本身不强制放入 compose；当前 smoke 只验证基础设施、OTel Collector 和 Jaeger 是否在本地可达。