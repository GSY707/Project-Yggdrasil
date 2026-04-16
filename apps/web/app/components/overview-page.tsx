"use client";

import Link from "next/link";

import type { WorkbenchOverview } from "@yggdrasil/frontend-sdk";

import { useApiResource } from "../lib/use-api-resource";
import { ErrorState, LoadingState, PageHeader, StatCard, StatusBadge, Surface, formatTimestamp } from "./workbench-primitives";

export function OverviewPage() {
  const { data, error, isLoading } = useApiResource<WorkbenchOverview>("/workbench/overview");

  if (isLoading) {
    return <LoadingState title="正在装配工作台总览" />;
  }

  if (error || !data) {
    return <ErrorState detail={error ?? "总览数据不可用。"} />;
  }

  return (
    <div>
      <PageHeader
        eyebrow="Workbench Overview"
        title="正式控制台已经切到运行态数据面"
        summary={
          <>
            当前工作台直接消费 core-api 的任务、节点、协作、评测与观测接口，不再依赖仓库文件扫描。
            这里展示的是 M4 到 M6 的真实运行脉冲，而不是开发说明页。
          </>
        }
        actions={
          <>
            <Link className="action-button" href="/evaluations">
              进入回归评测
            </Link>
            <Link className="ghost-button" href="/observability">
              查看观测信号
            </Link>
          </>
        }
      />

      <section className="stat-grid">
        <StatCard label="Tasks" value={data.cards.tasks} copy={`当前累计任务 ${data.cards.tasks} 个，待处理 ${data.taskStatusCounts.queued ?? 0} 个。`} />
        <StatCard label="Nodes" value={data.cards.nodes} copy={`非根节点 ${data.cards.nodes} 个，检索请求 ${data.cards.retrievals} 次。`} />
        <StatCard label="Pull Requests" value={data.cards.pullRequests} copy={`分支 ${data.cards.branches} 条，待审 PR ${data.pullRequestStatusCounts.open ?? 0} 个。`} />
        <StatCard label="LLM Runs" value={data.cards.modelInvocations} copy={`fallback ${data.cards.llmFallbacks} 次，累计成本 ${data.cards.llmCostUsed.toFixed(4)} USD。`} />
        <StatCard label="Signals" value={data.cards.observabilityErrors} copy={`最近记录 ${data.observability.totalSpans} 个 span，错误 ${data.cards.observabilityErrors} 个。`} />
      </section>

      <div className="content-grid">
        <div className="section-stack">
          <Surface>
            <p className="section-kicker">Runtime Pulse</p>
            <h3 className="section-title">系统脉冲</h3>
            <p className="section-copy">数据库、缓存、模块注册表、outbox 与回归运行都在同一屏里收口。</p>
            <div className="kv-grid">
              <div className="kv-item">
                <p className="meta-label">数据库</p>
                <p className="meta-copy mono">{JSON.stringify(data.health.database ?? {})}</p>
              </div>
              <div className="kv-item">
                <p className="meta-label">Redis</p>
                <p className="meta-copy mono">{JSON.stringify(data.health.redis ?? {})}</p>
              </div>
              <div className="kv-item">
                <p className="meta-label">模块状态</p>
                <div className="pill-row">
                  <span className="inline-chip">active {data.moduleSummary.active}</span>
                  <span className="inline-chip">degraded {data.moduleSummary.degraded}</span>
                  <span className="inline-chip">disabled {data.moduleSummary.disabled}</span>
                </div>
              </div>
              <div className="kv-item">
                <p className="meta-label">Outbox</p>
                <div className="pill-row">
                  {Object.entries(data.outboxStatusCounts).map(([status, count]) => (
                    <span className="inline-chip" key={status}>
                      {status} {count}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          </Surface>

          <Surface>
            <p className="section-kicker">Recent Tasks</p>
            <h3 className="section-title">最近任务</h3>
            <div className="record-list">
              {data.recentTasks.map((task) => (
                <article className="record-card" key={task.id}>
                  <div className="record-head">
                    <div>
                      <Link className="record-link" href={`/tasks/${encodeURIComponent(task.id)}`}>
                        <h4 className="record-title">{task.title}</h4>
                      </Link>
                      <p className="meta-copy">{task.goal}</p>
                    </div>
                    <StatusBadge value={task.status} />
                  </div>
                  <div className="record-meta">
                    <div className="kv-item">
                      <p className="meta-label">Focus</p>
                      <p className="meta-copy">{String(task.currentFocus ?? "-")}</p>
                    </div>
                    <div className="kv-item">
                      <p className="meta-label">Updated</p>
                      <p className="meta-copy">{formatTimestamp(task.updatedAt ?? task.createdAt)}</p>
                    </div>
                  </div>
                </article>
              ))}
            </div>
          </Surface>
        </div>

        <div className="section-stack">
          <Surface>
            <p className="section-kicker">Regression</p>
            <h3 className="section-title">评测与回归</h3>
            <div className="record-list">
              {data.recentEvaluationRuns.length === 0 ? (
                <div className="empty-state">
                  <h4 className="subsection-title">还没有评测运行</h4>
                  <p className="empty-copy">进入评测页即可触发 M4-M6 回归 suite，并把结果回写到正式记录里。</p>
                </div>
              ) : (
                data.recentEvaluationRuns.map((run) => {
                  const metrics = (run.metrics ?? {}) as Record<string, unknown>;
                  return (
                    <article className="record-card" key={run.id}>
                      <div className="record-head">
                        <div>
                          <h4 className="record-title">{run.suiteId}</h4>
                          <p className="meta-copy">subject {run.subjectRef}</p>
                        </div>
                        <StatusBadge value={run.status} />
                      </div>
                      <div className="pill-row">
                        <span className="inline-chip">passRate {String(metrics.passRate ?? "-")}</span>
                        <span className="inline-chip">cases {String(metrics.caseCount ?? "-")}</span>
                        <span className="inline-chip">duration {String(metrics.totalDurationMs ?? "-")} ms</span>
                      </div>
                    </article>
                  );
                })
              )}
            </div>
          </Surface>

          <Surface>
            <p className="section-kicker">Model Gateway</p>
            <h3 className="section-title">最近模型调用</h3>
            <div className="record-list">
              {data.recentModelInvocations.length === 0 ? (
                <div className="empty-state">
                  <h4 className="subsection-title">还没有模型调用记录</h4>
                  <p className="empty-copy">主执行链会在 M8 中把真实 LLM 调用、fallback 与成本全部写入这里。</p>
                </div>
              ) : (
                data.recentModelInvocations.map((invocation) => (
                  <article className="record-card" key={invocation.id}>
                    <div className="record-head">
                      <div>
                        <h4 className="record-title">{invocation.resolvedModel}</h4>
                        <p className="meta-copy">task {String(invocation.taskId ?? "-")}</p>
                      </div>
                      <StatusBadge value={invocation.status} />
                    </div>
                    <div className="pill-row">
                      <span className="inline-chip">provider {String(invocation.resolvedProvider ?? invocation.requestedProvider ?? "-")}</span>
                      <span className="inline-chip">input {invocation.inputTokensUsed}</span>
                      <span className="inline-chip">output {invocation.outputTokensUsed}</span>
                      <span className="inline-chip">cost {invocation.costUsed.toFixed(4)} USD</span>
                    </div>
                  </article>
                ))
              )}
            </div>
          </Surface>

          <Surface>
            <p className="section-kicker">Observability</p>
            <h3 className="section-title">最近信号</h3>
            <div className="record-list">
              {data.observability.serviceSummaries.map((summary) => (
                <article className="record-card" key={summary.serviceName}>
                  <div className="record-head">
                    <div>
                      <h4 className="record-title">{summary.serviceName}</h4>
                      <p className="meta-copy">last seen {formatTimestamp(summary.lastSeenAt)}</p>
                    </div>
                    <StatusBadge value={summary.errorCount > 0 ? "degraded" : "healthy"} />
                  </div>
                  <div className="pill-row">
                    <span className="inline-chip">spans {summary.spanCount}</span>
                    <span className="inline-chip">errors {summary.errorCount}</span>
                    <span className="inline-chip">avg {summary.avgDurationMs} ms</span>
                  </div>
                </article>
              ))}
            </div>
          </Surface>

          <Surface>
            <p className="section-kicker">Collaboration</p>
            <h3 className="section-title">最近 PR</h3>
            <div className="record-list">
              {data.recentPullRequests.map((pullRequest) => (
                <article className="record-card" key={pullRequest.id}>
                  <div className="record-head">
                    <div>
                      <Link className="record-link" href="/collaboration">
                        <h4 className="record-title">{pullRequest.title}</h4>
                      </Link>
                      <p className="meta-copy">{pullRequest.summary}</p>
                    </div>
                    <StatusBadge value={pullRequest.status} />
                  </div>
                  <div className="pill-row">
                    <span className="inline-chip">source {pullRequest.sourceBranchId}</span>
                    <span className="inline-chip">target {pullRequest.targetBranchId}</span>
                    <span className="inline-chip">created {formatTimestamp(pullRequest.createdAt)}</span>
                  </div>
                </article>
              ))}
            </div>
          </Surface>
        </div>
      </div>
    </div>
  );
}