"use client";

import type { TaskDetailResponse } from "@yggdrasil/frontend-sdk";

import { useApiResource } from "../lib/use-api-resource";
import { ErrorState, LoadingState, PageHeader, StatusBadge, Surface, formatTimestamp } from "./workbench-primitives";

export function TaskDetailPage({ taskId }: { taskId: string }) {
  const { data, error, isLoading } = useApiResource<TaskDetailResponse>(`/tasks/${encodeURIComponent(taskId)}`);

  if (isLoading) {
    return <LoadingState title="正在装配任务详情" />;
  }

  if (error || !data) {
    return <ErrorState detail={error ?? "任务详情不可用。"} />;
  }

  return (
    <div>
      <PageHeader
        eyebrow="Task Detail"
        title={data.task.title}
        summary={<>目标：{data.task.goal}</>}
      />

      <section className="detail-hero">
        <div className="record-head">
          <div>
            <p className="meta-label">Task ID</p>
            <p className="meta-copy mono">{data.task.id}</p>
          </div>
          <StatusBadge value={data.task.status} />
        </div>
        <div className="kv-grid">
          <div className="kv-item">
            <p className="meta-label">Current Objective</p>
            <p className="meta-copy">{String(data.task.currentObjective ?? "-")}</p>
          </div>
          <div className="kv-item">
            <p className="meta-label">Current Focus</p>
            <p className="meta-copy">{String(data.task.currentFocus ?? "-")}</p>
          </div>
          <div className="kv-item">
            <p className="meta-label">Branch</p>
            <p className="meta-copy mono">{String(data.task.branchId ?? "-")}</p>
          </div>
          <div className="kv-item">
            <p className="meta-label">Updated</p>
            <p className="meta-copy">{formatTimestamp(data.task.updatedAt ?? data.task.createdAt)}</p>
          </div>
        </div>
      </section>

      <div className="content-grid tight">
        <Surface>
          <p className="section-kicker">Agent Runs</p>
          <h3 className="section-title">运行轨迹</h3>
          <div className="record-list">
            {data.agentRuns.map((run) => (
              <article className="record-card" key={run.id}>
                <div className="record-head">
                  <div>
                    <h4 className="record-title">{run.runType}</h4>
                    <p className="meta-copy mono">{run.id}</p>
                  </div>
                  <StatusBadge value={run.status} />
                </div>
                <div className="pill-row">
                  <span className="inline-chip">model {run.selectedModel}</span>
                  <span className="inline-chip">provider {String(run.selectedProvider ?? "-")}</span>
                  <span className="inline-chip">start {formatTimestamp(run.startedAt)}</span>
                </div>
              </article>
            ))}
          </div>
        </Surface>

        <Surface>
          <p className="section-kicker">Snapshots</p>
          <h3 className="section-title">快照与恢复点</h3>
          <div className="record-list">
            {data.snapshots.map((snapshot) => (
              <article className="record-card" key={snapshot.id}>
                <div className="record-head">
                  <div>
                    <h4 className="record-title">{snapshot.resumeMessage ?? "Safe Stop Snapshot"}</h4>
                    <p className="meta-copy mono">{snapshot.id}</p>
                  </div>
                  <StatusBadge value={snapshot.status} />
                </div>
                <div className="pill-row">
                  <span className="inline-chip">created {formatTimestamp(snapshot.createdAt)}</span>
                  <span className="inline-chip">consumed {formatTimestamp(snapshot.consumedAt)}</span>
                  <span className="inline-chip">resumeToken {String(snapshot.resumeToken ?? "-")}</span>
                </div>
              </article>
            ))}
          </div>
        </Surface>
      </div>

      <Surface>
        <p className="section-kicker">Routing</p>
        <h3 className="section-title">模型路由决策</h3>
        <div className="record-list">
          {data.routeDecisions.map((decision) => (
            <article className="record-card" key={decision.id}>
              <div className="record-head">
                <div>
                  <h4 className="record-title">{decision.selectedModel}</h4>
                  <p className="meta-copy">{decision.reason}</p>
                </div>
                <span className="inline-chip">policy {decision.routePolicyVersion}</span>
              </div>
              <div className="pill-row">
                <span className="inline-chip">provider {String(decision.selectedProvider ?? "-")}</span>
                <span className="inline-chip">created {formatTimestamp(decision.createdAt)}</span>
              </div>
            </article>
          ))}
        </div>
      </Surface>

      <Surface>
        <p className="section-kicker">LLM Invocations</p>
        <h3 className="section-title">模型调用记录</h3>
        <div className="record-list">
          {data.modelInvocations.length === 0 ? (
            <div className="empty-state">
              <h4 className="subsection-title">还没有模型调用</h4>
              <p className="empty-copy">M8 执行链会把真实调用、fallback、trace 与 token/cost 记录写到这里。</p>
            </div>
          ) : (
            data.modelInvocations.map((invocation) => (
              <article className="record-card" key={invocation.id}>
                <div className="record-head">
                  <div>
                    <h4 className="record-title">{invocation.resolvedModel}</h4>
                    <p className="meta-copy mono">{invocation.id}</p>
                  </div>
                  <StatusBadge value={invocation.status} />
                </div>
                <div className="pill-row">
                  <span className="inline-chip">provider {String(invocation.resolvedProvider ?? invocation.requestedProvider ?? "-")}</span>
                  <span className="inline-chip">input {invocation.inputTokensUsed}</span>
                  <span className="inline-chip">output {invocation.outputTokensUsed}</span>
                  <span className="inline-chip">latency {String(invocation.latencyMs ?? "-")} ms</span>
                  <span className="inline-chip">cost {invocation.costUsed.toFixed(4)} USD</span>
                </div>
                <div className="kv-grid">
                  <div className="kv-item">
                    <p className="meta-label">Request Ref</p>
                    <p className="meta-copy mono">{String(invocation.requestRef?.locator ?? "-")}</p>
                  </div>
                  <div className="kv-item">
                    <p className="meta-label">Response Ref</p>
                    <p className="meta-copy mono">{String(invocation.responseRef?.locator ?? "-")}</p>
                  </div>
                  <div className="kv-item">
                    <p className="meta-label">Trace</p>
                    <p className="meta-copy mono">{String(invocation.traceId ?? "-")}</p>
                  </div>
                  <div className="kv-item">
                    <p className="meta-label">Started</p>
                    <p className="meta-copy">{formatTimestamp(invocation.startedAt)}</p>
                  </div>
                </div>
                {invocation.errorSummary ? <p className="code-block mono">{invocation.errorSummary}</p> : null}
              </article>
            ))
          )}
        </div>
      </Surface>
    </div>
  );
}