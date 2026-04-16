"use client";

import type { ObservabilitySummary } from "@yggdrasil/frontend-sdk";

import { useApiResource } from "../lib/use-api-resource";
import { ErrorState, LoadingState, PageHeader, StatCard, Surface, formatTimestamp } from "./workbench-primitives";

function jsonSnippet(value: unknown): string {
  return JSON.stringify(value ?? {}, null, 2);
}

function isLocalHost(value: string | null | undefined): boolean {
  if (!value) {
    return false;
  }
  return value.includes("127.0.0.1") || value.includes("localhost");
}

export function ObservabilityPage() {
  const { data, error, isLoading, reload } = useApiResource<ObservabilitySummary>("/observability/summary?limit=80");

  if (isLoading) {
    return <LoadingState title="正在聚合可观测性信号" />;
  }

  if (error || !data) {
    return <ErrorState detail={error ?? "观测数据不可用。"} />;
  }

  const localLangfuse = isLocalHost(data.exporters.langfuse.host);

  return (
    <div>
      <PageHeader
        eyebrow="Observability"
        title="HTTP、worker 与 evaluation 信号板"
        summary={<>统一展示 spans、logs、metrics 三类事件，并标出 OpenTelemetry 与 Langfuse exporter 当前连到本机还是远端实例，直接支撑 M7 工作台上的运行可见性。</>}
        actions={<button className="ghost-button" onClick={reload} type="button">刷新观测信号</button>}
      />

      <section className="stat-grid">
        <StatCard label="Spans" value={data.totalSpans} copy="记录所有 HTTP、worker、evaluation 执行区间。" />
        <StatCard label="Logs" value={data.totalLogs} copy="记录异常、状态改变与失败上下文。" />
        <StatCard label="Metrics" value={data.totalMetrics} copy="用于计数、耗时与结果聚合。" />
        <StatCard label="LLM Calls" value={data.llmSummary.totalInvocations} copy={`live ${data.llmSummary.liveInvocations}，fallback ${data.llmSummary.fallbackInvocations}。`} />
        <StatCard label="LLM Input" value={data.llmSummary.totalInputTokens} copy="累计输入 tokens。" />
        <StatCard label="LLM Output" value={data.llmSummary.totalOutputTokens} copy="累计输出 tokens。" />
        <StatCard label="LLM Cost" value={data.llmSummary.totalCostUsed.toFixed(4)} copy="已累计的模型调用成本。" />
        <StatCard label="Generated" value={formatTimestamp(data.generatedAt)} copy="工作台读取到的最近一次聚合时间。" />
      </section>

      <Surface>
        <p className="section-kicker">LLM Summary</p>
        <h3 className="section-title">模型网关摘要</h3>
        <div className="content-grid tight">
          <div className="kv-item">
            <p className="meta-label">Status Counts</p>
            <p className="code-block mono">{jsonSnippet(data.llmSummary.statusCounts)}</p>
          </div>
          <div className="kv-item">
            <p className="meta-label">Provider Counts</p>
            <p className="code-block mono">{jsonSnippet(data.llmSummary.providerCounts)}</p>
          </div>
        </div>
      </Surface>

      <Surface>
        <p className="section-kicker">Exporters</p>
        <h3 className="section-title">OpenTelemetry 与 Langfuse 接线状态</h3>
        <p className="meta-copy">
          {localLangfuse
            ? "当前 Langfuse exporter 指向本机自托管实例；若 host 为 http://127.0.0.1:3100，说明工作台默认连的是本机 Langfuse。真实写入仍依赖运行环境提供 project public/secret key。"
            : "当前 Langfuse exporter 指向远端实例；host 字段用于快速确认工作台当前写入的目标 Langfuse 环境。"}
        </p>
        <div className="content-grid tight">
          <article className="record-card">
            <div className="record-head">
              <div>
                <h4 className="record-title">OpenTelemetry</h4>
                <p className="meta-copy">{data.exporters.otel.transport ?? "otlp/http"}</p>
              </div>
              <div className="pill-row">
                <span className="inline-chip">configured {String(data.exporters.otel.configured)}</span>
                <span className="inline-chip">ready {String(data.exporters.otel.ready)}</span>
              </div>
            </div>
            <p className="code-block mono">{jsonSnippet({ traces: data.exporters.otel.tracesEndpoint, metrics: data.exporters.otel.metricsEndpoint, detail: data.exporters.otel.detail })}</p>
          </article>
          <article className="record-card">
            <div className="record-head">
              <div>
                <h4 className="record-title">Langfuse</h4>
                <p className="meta-copy">{data.exporters.langfuse.host ?? "not-configured"}</p>
              </div>
              <div className="pill-row">
                <span className="inline-chip">mode {localLangfuse ? "local" : "remote"}</span>
                <span className="inline-chip">configured {String(data.exporters.langfuse.configured)}</span>
                <span className="inline-chip">ready {String(data.exporters.langfuse.ready)}</span>
              </div>
            </div>
            <p className="code-block mono">{jsonSnippet({ host: data.exporters.langfuse.host, detail: data.exporters.langfuse.detail })}</p>
          </article>
        </div>
      </Surface>

      <Surface>
        <p className="section-kicker">Services</p>
        <h3 className="section-title">服务级摘要</h3>
        <div className="record-list">
          {data.serviceSummaries.map((summary) => (
            <article className="record-card" key={summary.serviceName}>
              <div className="record-head">
                <div>
                  <h4 className="record-title">{summary.serviceName}</h4>
                  <p className="meta-copy">last seen {formatTimestamp(summary.lastSeenAt)}</p>
                </div>
                <div className="pill-row">
                  <span className="inline-chip">spans {summary.spanCount}</span>
                  <span className="inline-chip">errors {summary.errorCount}</span>
                  <span className="inline-chip">avg {summary.avgDurationMs} ms</span>
                </div>
              </div>
              <div className="content-grid tight">
                <div className="kv-item">
                  <p className="meta-label">Counters</p>
                  <p className="code-block mono">{jsonSnippet(summary.counters)}</p>
                </div>
                <div className="kv-item">
                  <p className="meta-label">Gauges</p>
                  <p className="code-block mono">{jsonSnippet(summary.gauges)}</p>
                </div>
              </div>
            </article>
          ))}
        </div>
      </Surface>

      <div className="content-grid tight">
        <Surface>
          <p className="section-kicker">Recent LLM Calls</p>
          <h3 className="section-title">最近模型调用</h3>
          <div className="record-list">
            {data.recentModelInvocations.map((invocation) => (
              <article className="record-card" key={invocation.id}>
                <div className="record-head">
                  <div>
                    <h4 className="record-title">{invocation.resolvedModel}</h4>
                    <p className="meta-copy">provider {String(invocation.resolvedProvider ?? invocation.requestedProvider ?? "-")}</p>
                  </div>
                  <span className="inline-chip">{invocation.status}</span>
                </div>
                <div className="pill-row">
                  <span className="inline-chip">input {invocation.inputTokensUsed}</span>
                  <span className="inline-chip">output {invocation.outputTokensUsed}</span>
                  <span className="inline-chip">latency {String(invocation.latencyMs ?? "-")} ms</span>
                  <span className="inline-chip">cost {invocation.costUsed.toFixed(4)} USD</span>
                </div>
                <p className="meta-copy">trace {String(invocation.traceId ?? "-")}</p>
                {invocation.errorSummary ? <p className="code-block mono">{invocation.errorSummary}</p> : null}
              </article>
            ))}
          </div>
        </Surface>

        <Surface>
          <p className="section-kicker">Recent Spans</p>
          <h3 className="section-title">最近执行区间</h3>
          <div className="record-list">
            {data.recentSpans.map((span, index) => {
              const record = span as Record<string, unknown>;
              return (
                <article className="record-card" key={`${String(record.traceId ?? "trace")}-${index}`}>
                  <div className="record-head">
                    <div>
                      <h4 className="record-title">{String(record.serviceName ?? "unknown")}</h4>
                      <p className="meta-copy">{String(record.name ?? "operation")}</p>
                    </div>
                    <span className="inline-chip">{String(record.durationMs ?? "-")} ms</span>
                  </div>
                  <p className="code-block mono">{jsonSnippet(record.attributes)}</p>
                </article>
              );
            })}
          </div>
        </Surface>

        <Surface>
          <p className="section-kicker">Recent Logs</p>
          <h3 className="section-title">最近日志</h3>
          <div className="record-list">
            {data.recentLogs.map((log, index) => {
              const record = log as Record<string, unknown>;
              return (
                <article className="record-card" key={`${String(record.capturedAt ?? "log")}-${index}`}>
                  <div className="record-head">
                    <div>
                      <h4 className="record-title">{String(record.serviceName ?? "unknown")}</h4>
                      <p className="meta-copy">{String(record.message ?? "-")}</p>
                    </div>
                    <span className="inline-chip">{String(record.level ?? "info")}</span>
                  </div>
                  <p className="meta-copy">{formatTimestamp(record.capturedAt)}</p>
                  <p className="code-block mono">{jsonSnippet(record.attributes)}</p>
                </article>
              );
            })}
          </div>
        </Surface>
      </div>
    </div>
  );
}