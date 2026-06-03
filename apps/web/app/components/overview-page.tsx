"use client";

import Link from "next/link";

import type { SetupChecklistItem, WorkbenchOverview } from "@yggdrasil/frontend-sdk";

import { useApiResource } from "../lib/use-api-resource";
import { ErrorState, LoadingState, PageHeader, StatCard, StatusBadge, Surface, formatTimestamp } from "./workbench-primitives";

function SetupChecklist({ items }: { items: SetupChecklistItem[] }) {
  if (items.length === 0) {
    return null;
  }
  const blocked = items.filter((item) => item.status === "blocked").length;
  const warnings = items.filter((item) => item.status === "warning").length;
  return (
    <Surface>
      <div className="record-head">
        <div>
          <p className="section-kicker">First Run</p>
          <h3 className="section-title">首次任务启动检查</h3>
          <p className="section-copy">先确认依赖、模型 key、状态目录和工作区路径。全部阻塞项清掉后，再进入任务模板创建第一任务。</p>
        </div>
        <StatusBadge value={blocked > 0 ? "blocked" : warnings > 0 ? "warning" : "ready"} />
      </div>
      <div className="setup-grid">
        {items.map((item) => (
          <article className="setup-item" key={item.id}>
            <div className="record-head">
              <div>
                <h4 className="record-title">{item.label}</h4>
                <p className="meta-copy">{item.detail}</p>
              </div>
              <StatusBadge value={item.status} />
            </div>
            {item.remediation ? <p className="meta-copy mono">{item.remediation}</p> : null}
          </article>
        ))}
      </div>
    </Surface>
  );
}

export function OverviewPage() {
  const { data, error, isLoading } = useApiResource<WorkbenchOverview>("/workbench/overview");

  if (isLoading) {
    return <LoadingState title="正在装配工作台总览" />;
  }

  if (error || !data) {
    return <ErrorState detail={error ?? "总览数据不可用。"} />;
  }

  const setupItems = data.health.setupChecklist ?? [];

  return (
    <div>
      <PageHeader
        eyebrow="Workbench Overview"
        title="从这里启动第一任务"
        summary={
          <>
            打开本地产品后，先确认启动检查，再选择应用模板创建任务。内部运行指标仍在下方，用于排查和复盘。
          </>
        }
        actions={
          <>
            <Link className="action-button" href="/tasks">
              New task
            </Link>
            <Link className="ghost-button" href="/applications">
              选择应用
            </Link>
            <Link className="ghost-button" href="/prompting">
              Prompt 控制面
            </Link>
          </>
        }
      />

      <SetupChecklist items={setupItems} />

      <section className="stat-grid">
        <StatCard label="Tasks" value={data.cards.tasks} copy={`当前累计任务 ${data.cards.tasks} 个，待处理 ${data.taskStatusCounts.queued ?? 0} 个。`} />
        <StatCard label="Nodes" value={data.cards.nodes} copy={`非根节点 ${data.cards.nodes} 个，检索请求 ${data.cards.retrievals} 次。`} />
        <StatCard label="Pull Requests" value={data.cards.pullRequests} copy={`分支 ${data.cards.branches} 条，待审 PR ${data.pullRequestStatusCounts.open ?? 0} 个。`} />
        <StatCard label="LLM Runs" value={data.cards.modelInvocations} copy={`fallback ${data.cards.llmFallbacks} 次，累计成本 ${data.cards.llmCostUsed.toFixed(4)} USD。`} />
        <StatCard label="Signals" value={data.cards.observabilityErrors} copy={`最近记录 ${data.observability.totalSpans} 个 span，错误 ${data.cards.observabilityErrors} 个。`} />
        <StatCard label="Shared Spaces" value={data.cards.sharedSpaces} copy={`挂载 ${data.cards.spaceMounts} 条，权限 tuple ${data.cards.permissionTuples} 条。`} />
        <StatCard label="Runtime Control" value={data.cards.pausedTasks} copy={`暂停中 ${data.cards.pausedTasks} 个，等待 safe-stop ${data.taskStatusCounts["pause-requested"] ?? 0} 个，可恢复快照 ${data.cards.restorableSnapshots} 个。`} />
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
            <p className="section-kicker">M9 Control</p>
            <h3 className="section-title">共享空间与恢复控制</h3>
            <div className="kv-grid">
              <div className="kv-item">
                <p className="meta-label">Shared Spaces</p>
                <p className="meta-copy">{data.cards.sharedSpaces}</p>
              </div>
              <div className="kv-item">
                <p className="meta-label">Space Mounts</p>
                <p className="meta-copy">{data.cards.spaceMounts}</p>
              </div>
              <div className="kv-item">
                <p className="meta-label">Permission Tuples</p>
                <p className="meta-copy">{data.cards.permissionTuples}</p>
              </div>
              <div className="kv-item">
                <p className="meta-label">Restorable Snapshots</p>
                <p className="meta-copy">{data.cards.restorableSnapshots}</p>
              </div>
            </div>
            <div className="pill-row">
              <span className="inline-chip">paused {data.cards.pausedTasks}</span>
              <span className="inline-chip">pause-requested {data.taskStatusCounts["pause-requested"] ?? 0}</span>
              <span className="inline-chip">shared spaces {data.cards.sharedSpaces}</span>
              <span className="inline-chip">mounts {data.cards.spaceMounts}</span>
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
