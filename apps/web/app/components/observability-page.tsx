"use client";

import type { ObservabilitySummary } from "@yggdrasil/frontend-sdk";

import { useApiResource } from "../lib/use-api-resource";
import { localizedText } from "../i18n";
import { ErrorState, LoadingState, PageHeader, StatCard, Surface, formatTimestamp } from "./workbench-primitives";
import { useLocale } from "./locale-provider";

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
  const { locale } = useLocale();
  const l = (zhCN: string, english: string) => localizedText(locale, zhCN, english);
  const { data, error, isLoading, reload } = useApiResource<ObservabilitySummary>("/observability/summary?limit=80");

  if (isLoading) {
    return <LoadingState title={localizedText(locale, "正在聚合可观测性信号", "Aggregating observability signals")} />;
  }

  if (error || !data || !data.exporters?.otel || !data.exporters?.langfuse || !data.llmSummary) {
    return <ErrorState detail={error ?? localizedText(locale, "观测数据不可用。", "Observability data is unavailable.")} />;
  }

  const serviceSummaries = data.serviceSummaries ?? [];
  const recentModelInvocations = data.recentModelInvocations ?? [];
  const recentSpans = data.recentSpans ?? [];
  const recentLogs = data.recentLogs ?? [];

  const localLangfuse = isLocalHost(data.exporters.langfuse.host);

  return (
    <div>
      <PageHeader
        eyebrow={l("观测", "Observability")}
        title={localizedText(locale, "HTTP、worker 与 evaluation 信号板", "HTTP, worker, and evaluation signal board")}
        summary={<>{localizedText(locale, "统一展示 spans、logs、metrics 三类事件，并标出 OpenTelemetry 与 Langfuse exporter 当前连到本机还是远端实例，直接支撑 M7 工作台上的运行可见性。", "Unify spans, logs, and metrics while showing whether OpenTelemetry and Langfuse exporters target local or remote instances.")}</>}
        actions={<button className="ghost-button" onClick={reload} type="button">{localizedText(locale, "刷新观测信号", "Refresh signals")}</button>}
      />

      <section className="stat-grid">
        <StatCard label={l("执行区间", "Spans")} value={data.totalSpans} copy={localizedText(locale, "记录所有 HTTP、worker、evaluation 执行区间。", "All HTTP, worker, and evaluation spans.")} />
        <StatCard label={l("日志", "Logs")} value={data.totalLogs} copy={localizedText(locale, "记录异常、状态改变与失败上下文。", "Errors, state changes, and failure context.")} />
        <StatCard label={l("指标", "Metrics")} value={data.totalMetrics} copy={localizedText(locale, "用于计数、耗时与结果聚合。", "Counts, latency, and result aggregates.")} />
        <StatCard label={l("LLM 调用", "LLM calls")} value={data.llmSummary.totalInvocations} copy={`${l("实时", "Live")} ${data.llmSummary.liveInvocations}，${l("回退", "fallback")} ${data.llmSummary.fallbackInvocations}。`} />
        <StatCard label={l("LLM 输入", "LLM input")} value={data.llmSummary.totalInputTokens} copy={localizedText(locale, "累计输入 tokens。", "Total input tokens.")} />
        <StatCard label={l("LLM 输出", "LLM output")} value={data.llmSummary.totalOutputTokens} copy={localizedText(locale, "累计输出 tokens。", "Total output tokens.")} />
        <StatCard label={l("LLM 成本", "LLM cost")} value={data.llmSummary.totalCostUsed.toFixed(4)} copy={localizedText(locale, "已累计的模型调用成本。", "Accumulated model call cost.")} />
        <StatCard label={l("生成时间", "Generated")} value={formatTimestamp(data.generatedAt, locale)} copy={localizedText(locale, "工作台读取到的最近一次聚合时间。", "Last aggregation read by the workbench.")} />
      </section>

      <Surface>
        <p className="section-kicker">{l("LLM 摘要", "LLM summary")}</p>
        <h3 className="section-title">{localizedText(locale, "模型网关摘要", "Model gateway summary")}</h3>
        <div className="content-grid tight">
          <div className="kv-item">
            <p className="meta-label">{localizedText(locale, "状态计数", "Status counts")}</p>
            <p className="code-block mono">{jsonSnippet(data.llmSummary.statusCounts)}</p>
          </div>
          <div className="kv-item">
            <p className="meta-label">{localizedText(locale, "供应商计数", "Provider counts")}</p>
            <p className="code-block mono">{jsonSnippet(data.llmSummary.providerCounts)}</p>
          </div>
        </div>
      </Surface>

      <Surface>
        <p className="section-kicker">{l("导出器", "Exporters")}</p>
        <h3 className="section-title">{localizedText(locale, "OpenTelemetry 与 Langfuse 接线状态", "OpenTelemetry and Langfuse wiring")}</h3>
        <p className="meta-copy">
          {localLangfuse
            ? localizedText(locale, "当前 Langfuse exporter 指向本机自托管实例；若 host 为 http://127.0.0.1:3100，说明工作台默认连的是本机 Langfuse。真实写入仍依赖运行环境提供 project public/secret key。", "Langfuse currently targets a local self-hosted instance. A host of http://127.0.0.1:3100 means the workbench defaults to local Langfuse; writes still require project public/secret keys.")
            : localizedText(locale, "当前 Langfuse exporter 指向远端实例；host 字段用于快速确认工作台当前写入的目标 Langfuse 环境。", "Langfuse currently targets a remote instance; the host confirms the environment receiving workbench events.")}
        </p>
        <div className="content-grid tight">
          <article className="record-card">
            <div className="record-head">
              <div>
                <h4 className="record-title">OpenTelemetry</h4>
                <p className="meta-copy">{data.exporters.otel.transport ?? "otlp/http"}</p>
              </div>
              <div className="pill-row">
                <span className="inline-chip">{localizedText(locale, "已配置", "configured")} {String(data.exporters.otel.configured)}</span>
                <span className="inline-chip">{localizedText(locale, "就绪", "ready")} {String(data.exporters.otel.ready)}</span>
              </div>
            </div>
            <p className="code-block mono">{jsonSnippet({ traces: data.exporters.otel.tracesEndpoint, metrics: data.exporters.otel.metricsEndpoint, detail: data.exporters.otel.detail })}</p>
          </article>
          <article className="record-card">
            <div className="record-head">
              <div>
                <h4 className="record-title">Langfuse</h4>
                <p className="meta-copy">{data.exporters.langfuse.host ?? l("未配置", "Not configured")}</p>
              </div>
              <div className="pill-row">
                <span className="inline-chip">{localizedText(locale, "模式", "Mode")} {localLangfuse ? l("本机", "Local") : l("远端", "Remote")}</span>
                <span className="inline-chip">{localizedText(locale, "已配置", "configured")} {String(data.exporters.langfuse.configured)}</span>
                <span className="inline-chip">{localizedText(locale, "就绪", "ready")} {String(data.exporters.langfuse.ready)}</span>
              </div>
            </div>
            <p className="code-block mono">{jsonSnippet({ host: data.exporters.langfuse.host, detail: data.exporters.langfuse.detail })}</p>
          </article>
        </div>
      </Surface>

      <Surface>
        <p className="section-kicker">{l("服务", "Services")}</p>
        <h3 className="section-title">{localizedText(locale, "服务级摘要", "Service summary")}</h3>
        <div className="record-list">
          {serviceSummaries.map((summary) => (
            <article className="record-card" key={summary.serviceName}>
              <div className="record-head">
                <div>
                  <h4 className="record-title">{summary.serviceName}</h4>
                  <p className="meta-copy">{localizedText(locale, "最近出现", "Last seen")} {formatTimestamp(summary.lastSeenAt, locale)}</p>
                </div>
                <div className="pill-row">
                  <span className="inline-chip">{l("区间", "Spans")} {summary.spanCount}</span>
                  <span className="inline-chip">{l("错误", "Errors")} {summary.errorCount}</span>
                  <span className="inline-chip">{l("平均", "Avg")} {summary.avgDurationMs} ms</span>
                </div>
              </div>
              <div className="content-grid tight">
                <div className="kv-item">
                  <p className="meta-label">{localizedText(locale, "计数器", "Counters")}</p>
                  <p className="code-block mono">{jsonSnippet(summary.counters)}</p>
                </div>
                <div className="kv-item">
                  <p className="meta-label">{localizedText(locale, "仪表", "Gauges")}</p>
                  <p className="code-block mono">{jsonSnippet(summary.gauges)}</p>
                </div>
              </div>
            </article>
          ))}
        </div>
      </Surface>

      <div className="content-grid tight">
        <Surface>
          <p className="section-kicker">{l("最近 LLM 调用", "Recent LLM calls")}</p>
          <h3 className="section-title">{localizedText(locale, "最近模型调用", "Recent model calls")}</h3>
          <div className="record-list">
            {recentModelInvocations.map((invocation) => (
              <article className="record-card" key={invocation.id}>
                <div className="record-head">
                  <div>
                    <h4 className="record-title">{invocation.resolvedModel}</h4>
                    <p className="meta-copy">{localizedText(locale, "供应商", "provider")} {String(invocation.resolvedProvider ?? invocation.requestedProvider ?? "-")}</p>
                  </div>
                  <span className="inline-chip">{invocation.status}</span>
                </div>
                <div className="pill-row">
                  <span className="inline-chip">{l("输入", "Input")} {invocation.inputTokensUsed}</span>
                  <span className="inline-chip">{l("输出", "Output")} {invocation.outputTokensUsed}</span>
                  <span className="inline-chip">{l("延迟", "Latency")} {String(invocation.latencyMs ?? "-")} ms</span>
                  <span className="inline-chip">{l("成本", "Cost")} {invocation.costUsed.toFixed(4)} USD</span>
                </div>
                <p className="meta-copy">{l("追踪", "Trace")} {String(invocation.traceId ?? "-")}</p>
                {invocation.errorSummary ? <p className="code-block mono">{invocation.errorSummary}</p> : null}
              </article>
            ))}
          </div>
        </Surface>

        <Surface>
          <p className="section-kicker">{l("最近执行区间", "Recent spans")}</p>
          <h3 className="section-title">{localizedText(locale, "最近执行区间", "Recent spans")}</h3>
          <div className="record-list">
            {recentSpans.map((span, index) => {
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
          <p className="section-kicker">{l("最近日志", "Recent logs")}</p>
          <h3 className="section-title">{localizedText(locale, "最近日志", "Recent logs")}</h3>
          <div className="record-list">
            {recentLogs.map((log, index) => {
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
                  <p className="meta-copy">{formatTimestamp(record.capturedAt, locale)}</p>
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
