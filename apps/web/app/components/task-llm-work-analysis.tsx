"use client";

import Link from "next/link";
import { useState } from "react";

import type {
  LlmWorkAnalysisArtifactRecord,
  LlmWorkAnalysisCacheSummary,
  LlmWorkAnalysisResponse,
  LlmWorkAnalysisSummaryWorkTreeDebug,
} from "@yggdrasil/frontend-sdk";

import { postApiJson, useApiResource } from "../lib/use-api-resource";
import { EmptyState, ErrorState, LoadingState, PageHeader, StatCard, Surface, StatusBadge, formatTimestamp } from "./workbench-primitives";

function jsonSnippet(value: unknown): string {
  return JSON.stringify(value ?? {}, null, 2);
}

function buildAnalysisPath(taskId: string, mode: "compact" | "full"): string {
  const encodedTaskId = encodeURIComponent(taskId);
  if (mode === "compact") {
    return `/tasks/${encodedTaskId}/analysis/latest?granularity=run,window,tool,artifact`;
  }
  return `/tasks/${encodedTaskId}/analysis/latest?granularity=all`;
}

function buildRefreshPayload(taskId: string, mode: "compact" | "full") {
  return {
    taskId,
    persist: true,
    granularity: mode === "compact" ? "run,window,tool,artifact" : "all",
  };
}

function artifactStatusSummary(artifacts: LlmWorkAnalysisArtifactRecord[]): string {
  const available = artifacts.filter((artifact) => artifact.exists).length;
  return `${available}/${artifacts.length}`;
}

function cacheSummaryLabel(cacheSummary: LlmWorkAnalysisCacheSummary | null | undefined): string {
  if (!cacheSummary) {
    return "0/0/0";
  }
  return `${cacheSummary.cacheHitInputTokens ?? 0}/${cacheSummary.cacheWriteInputTokens ?? 0}/${cacheSummary.nonCacheInputTokens ?? 0}`;
}

export function TaskLlmWorkAnalysisView({ taskId, mode }: { taskId: string; mode: "compact" | "full" }) {
  const { data, error, isLoading, reload } = useApiResource<LlmWorkAnalysisResponse>(buildAnalysisPath(taskId, mode));
  const [refreshError, setRefreshError] = useState<string | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);

  async function refreshAnalysis() {
    setIsRefreshing(true);
    setRefreshError(null);
    try {
      await postApiJson<LlmWorkAnalysisResponse>("/runtime/analysis/runs", buildRefreshPayload(taskId, mode));
      reload();
    } catch (actionError) {
      setRefreshError(actionError instanceof Error ? actionError.message : String(actionError));
    } finally {
      setIsRefreshing(false);
    }
  }

  if (isLoading && !data) {
    return <LoadingState title={mode === "compact" ? "正在生成 LLM 工作摘要" : "正在装配 LLM 工作分析页"} />;
  }

  if (error && !data) {
    return <ErrorState title="LLM 工作分析不可用" detail={error} />;
  }

  if (!data) {
    return <EmptyState title="暂无 LLM 工作分析" detail="当前任务还没有可读的分析工件。" />;
  }

  const summary = data.summary;
  const coverage = data.coverage;
  const windows = data.windows ?? [];
  const turns = data.turns ?? [];
  const tools = data.tools ?? [];
  const artifacts = data.artifacts ?? [];
  const previewWindows = mode === "compact" ? windows.slice(0, 3) : windows;
  const previewTurns = mode === "compact" ? turns.slice(0, 4) : turns;
  const previewTools = mode === "compact" ? tools.slice(0, 4) : tools;
  const previewArtifacts = mode === "compact" ? artifacts.slice(0, 6) : artifacts;
  const cacheSummary = summary?.cacheSummary ?? null;
  const workTreeDebug = (summary?.workTreeDebug ?? null) as LlmWorkAnalysisSummaryWorkTreeDebug | null;
  const timeline = workTreeDebug?.timeline ?? [];
  const sourceSnapshots = Array.isArray((data.sources ?? {}).snapshots) ? ((data.sources ?? {}).snapshots as Array<Record<string, unknown>>) : [];
  const sourceMailbox = Array.isArray((data.sources ?? {}).mailboxMessages) ? ((data.sources ?? {}).mailboxMessages as Array<Record<string, unknown>>) : [];
  const sourceSideChannel = Array.isArray((data.sources ?? {}).sideChannelEvents) ? ((data.sources ?? {}).sideChannelEvents as Array<Record<string, unknown>>) : [];

  if (mode === "compact") {
    return (
      <div>
        <Surface>
          <div className="record-head">
            <div>
              <p className="section-kicker">LLM Work Analysis</p>
              <h3 className="section-title">运行过程分析摘要</h3>
              <p className="meta-copy">
                最近分析生成于 {formatTimestamp(data.analysis.generatedAt)}，用于快速查看窗口、工具和工件覆盖情况。
              </p>
            </div>
            <div className="pill-row">
              <button className="ghost-button" disabled={isRefreshing} onClick={() => void refreshAnalysis()} type="button">
                {isRefreshing ? "正在刷新分析" : "刷新分析"}
              </button>
              <Link className="action-button" href={`/tasks/${encodeURIComponent(taskId)}/analysis`}>
                打开完整分析页
              </Link>
            </div>
          </div>
          {refreshError ? <p className="error-copy">{refreshError}</p> : null}
          <section className="stat-grid">
            <StatCard label="Windows" value={summary?.windowCount ?? 0} copy={`latest ${summary?.latestWindowIndex ?? 0}，restarts ${summary?.restartCount ?? 0}`} />
            <StatCard label="Turns" value={summary?.turnCount ?? 0} copy={`tools ${summary?.toolExecutionCount ?? 0}，fallback ${summary?.fallbackInvocationCount ?? 0}`} />
            <StatCard label="Tokens" value={`${summary?.totalInputTokens ?? 0}/${summary?.totalOutputTokens ?? 0}`} copy="input/output token 总量。" />
            <StatCard label="Artifacts" value={artifactStatusSummary(artifacts)} copy={`request ${coverage?.requestArtifactsAvailable ?? 0}，response ${coverage?.responseArtifactsAvailable ?? 0}`} />
            <StatCard label="Cache" value={cacheSummaryLabel(cacheSummary)} copy={`hit/write/non-cache，windows ${cacheSummary?.cacheHitWindowCount ?? 0}`} />
            <StatCard label="Work Tree" value={workTreeDebug?.distinctNodeCount ?? 0} copy={`switch ${workTreeDebug?.nodeSwitchCount ?? 0}，approval ${workTreeDebug?.approvalStopCount ?? 0}`} />
          </section>
          <div className="pill-row">
            <span className="inline-chip">analysis {data.analysis.analysisId}</span>
            <span className="inline-chip">run {String(data.selector.runId ?? "-")}</span>
            <span className="inline-chip">warnings {summary?.warningEventCount ?? 0}</span>
            <span className="inline-chip">mailbox {summary?.pendingMailboxCount ?? 0}</span>
          </div>
        </Surface>

        <div className="content-grid tight">
          <Surface>
            <p className="section-kicker">Window Preview</p>
            <h3 className="section-title">最近窗口</h3>
            <div className="record-list">
              {previewWindows.length === 0 ? (
                <EmptyState title="没有窗口记录" detail="当前分析结果里还没有窗口级视图。" />
              ) : (
                previewWindows.map((window) => (
                  <article className="record-card" key={`${String(window.invocationId ?? "window")}-${window.windowIndex}`}>
                    <div className="record-head">
                      <div>
                        <h4 className="record-title">Window {window.windowIndex}</h4>
                        <p className="meta-copy">{window.assistantTextSummary ?? window.currentFocus ?? window.currentObjective ?? "暂无摘要"}</p>
                      </div>
                      <StatusBadge value={window.finishReason ?? window.status} />
                    </div>
                    <div className="pill-row">
                      <span className="inline-chip">model {String(window.resolvedModel ?? window.requestedModel ?? "-")}</span>
                      <span className="inline-chip">tools {window.toolExecutionCount ?? 0}</span>
                      <span className="inline-chip">rounds {window.roundCount ?? 0}</span>
                      <span className="inline-chip">transition {String(window.transitionOutcome ?? "-")}</span>
                      <span className="inline-chip">cache {cacheSummaryLabel(window.cacheSummary)}</span>
                    </div>
                  </article>
                ))
              )}
            </div>
          </Surface>

          <Surface>
            <p className="section-kicker">Tool Preview</p>
            <h3 className="section-title">最近工具执行</h3>
            <div className="record-list">
              {previewTools.length === 0 ? (
                <EmptyState title="没有工具记录" detail="当前任务还没有工具级分析结果。" />
              ) : (
                previewTools.map((tool) => (
                  <article className="record-card" key={tool.toolExecutionId}>
                    <div className="record-head">
                      <div>
                        <h4 className="record-title">{tool.toolName ?? "unknown-tool"}</h4>
                        <p className="meta-copy">{tool.resultPreview ?? "暂无结果摘要"}</p>
                      </div>
                      <StatusBadge value={tool.success ? "completed" : tool.status ?? "unknown"} />
                    </div>
                    <div className="pill-row">
                      <span className="inline-chip">window {tool.windowIndex}</span>
                      <span className="inline-chip">round {String(tool.roundIndex ?? "-")}</span>
                      <span className="inline-chip">duration {String(tool.durationMs ?? "-")} ms</span>
                    </div>
                  </article>
                ))
              )}
            </div>
          </Surface>
        </div>
      </div>
    );
  }

  return (
    <div>
      <PageHeader
        eyebrow="LLM Work Analysis"
        title={`任务 ${taskId} 的运行过程分析`}
        summary={<>统一查看 run、window、turn、tool 与 artifact 五层结构化结果，直接用于评测对照和 runtime 排障。</>}
        actions={
          <>
            <button className="ghost-button" disabled={isRefreshing} onClick={() => void refreshAnalysis()} type="button">
              {isRefreshing ? "正在刷新分析" : "重新生成分析"}
            </button>
            <Link className="ghost-button" href={`/tasks/${encodeURIComponent(taskId)}`}>
              返回任务详情
            </Link>
          </>
        }
      />

      {refreshError ? <p className="error-copy">{refreshError}</p> : null}

      <section className="stat-grid">
        <StatCard label="Windows" value={summary?.windowCount ?? 0} copy={`restart ${summary?.restartCount ?? 0}，latest ${summary?.latestWindowIndex ?? 0}`} />
        <StatCard label="Turns" value={summary?.turnCount ?? 0} copy={`invocations ${summary?.invocationCount ?? 0}，tools ${summary?.toolExecutionCount ?? 0}`} />
        <StatCard label="Tokens" value={`${summary?.totalInputTokens ?? 0}/${summary?.totalOutputTokens ?? 0}`} copy="输入 / 输出 token 总量。" />
        <StatCard label="Cost" value={(summary?.totalCostUsed ?? 0).toFixed(4)} copy={`fallback ${summary?.fallbackInvocationCount ?? 0}，failed ${summary?.failedInvocationCount ?? 0}`} />
        <StatCard label="Artifacts" value={artifactStatusSummary(artifacts)} copy={`metrics ${coverage?.metricsArtifactsAvailable ?? 0}，window-execution ${coverage?.windowExecutionArtifactsAvailable ?? 0}`} />
        <StatCard label="Signals" value={`${summary?.warningEventCount ?? 0}/${summary?.errorEventCount ?? 0}`} copy={`pending mailbox ${summary?.pendingMailboxCount ?? 0}`} />
      </section>

      <Surface>
        <p className="section-kicker">Work Tree Debug</p>
        <h3 className="section-title">工作树调试摘要</h3>
        <section className="stat-grid">
          <StatCard label="Node Switches" value={workTreeDebug?.nodeSwitchCount ?? 0} copy={`frames ${workTreeDebug?.frameSwitchCount ?? 0}，prefix ${workTreeDebug?.prefixCacheChangeCount ?? 0}`} />
          <StatCard label="Approval Stops" value={workTreeDebug?.approvalStopCount ?? 0} copy={`child bubble ${workTreeDebug?.childBubbleCount ?? 0}，mixed ${workTreeDebug?.mixedOutcomeWindowCount ?? 0}`} />
          <StatCard label="Distinct Nodes" value={workTreeDebug?.distinctNodeCount ?? 0} copy={`latest ${String(workTreeDebug?.latestNodeId ?? "-")}`} />
          <StatCard label="Cache Trace" value={cacheSummaryLabel(cacheSummary)} copy={`hit windows ${cacheSummary?.cacheHitWindowCount ?? 0}，write windows ${cacheSummary?.cacheWriteWindowCount ?? 0}`} />
        </section>
        <div className="pill-row">
          {(workTreeDebug?.distinctNodeIds ?? []).map((nodeId) => (
            <span className="inline-chip" key={`node-${nodeId}`}>node {nodeId}</span>
          ))}
        </div>
        <div className="pill-row">
          {(workTreeDebug?.continuationReasons ?? []).map((reason) => (
            <span className="inline-chip" key={`reason-${reason}`}>reason {reason}</span>
          ))}
        </div>
        <div className="pill-row">
          <span className="inline-chip">latest prefix {String(workTreeDebug?.latestPrefixCacheKey ?? "-")}</span>
          <span className="inline-chip">cache hit ratio {(cacheSummary?.cacheHitRatio0_1 ?? 0).toFixed(4)}</span>
          <span className="inline-chip">cache write ratio {(cacheSummary?.cacheWriteRatio0_1 ?? 0).toFixed(4)}</span>
        </div>
      </Surface>

      <Surface>
        <p className="section-kicker">Coverage</p>
        <h3 className="section-title">工件覆盖率</h3>
        <div className="pill-row">
          <span className="inline-chip">request {coverage?.requestArtifactsAvailable ?? 0}</span>
          <span className="inline-chip">response {coverage?.responseArtifactsAvailable ?? 0}</span>
          <span className="inline-chip">prompt {coverage?.promptArtifactsAvailable ?? 0}</span>
          <span className="inline-chip">metrics {coverage?.metricsArtifactsAvailable ?? 0}</span>
          <span className="inline-chip">detailed tool {coverage?.detailedToolRecords ?? 0}</span>
          <span className="inline-chip">takeover {String(coverage?.hasTakeoverProtocol ?? false)}</span>
          <span className="inline-chip">work-context-stack {String(coverage?.hasWorkContextStack ?? false)}</span>
        </div>
      </Surface>

      <Surface>
        <p className="section-kicker">Timeline</p>
        <h3 className="section-title">节点切换时间线</h3>
        <div className="record-list">
          {timeline.length === 0 ? (
            <EmptyState title="没有时间线记录" detail="当前分析结果里还没有可展示的工作树时间线。" />
          ) : (
            timeline.map((entry, index) => (
              <article className="record-card" key={`${String(entry.invocationId ?? "timeline")}-${entry.windowIndex}-${index}`}>
                <div className="record-head">
                  <div>
                    <h4 className="record-title">Window {entry.windowIndex} / Node {String(entry.nodeId ?? "-")}</h4>
                    <p className="meta-copy">{String(entry.continuationReason ?? entry.transitionOutcome ?? "暂无 continuation 原因")}</p>
                  </div>
                  <StatusBadge value={entry.transitionOutcome ?? "unknown"} />
                </div>
                <div className="pill-row">
                  <span className="inline-chip">frame {String(entry.topFrameId ?? "-")}</span>
                  <span className="inline-chip">prefix {String(entry.topFramePrefixCacheKey ?? "-")}</span>
                  <span className="inline-chip">node-change {entry.nodeChanged0_1 ?? 0}</span>
                  <span className="inline-chip">frame-change {entry.frameChanged0_1 ?? 0}</span>
                  <span className="inline-chip">prefix-change {entry.prefixCacheChanged0_1 ?? 0}</span>
                </div>
                <div className="pill-row">
                  <span className="inline-chip">approval {entry.approvalStop0_1 ?? 0}</span>
                  <span className="inline-chip">bubble {entry.childBubble0_1 ?? 0}</span>
                  <span className="inline-chip">mixed {entry.mixedOutcome0_1 ?? 0}</span>
                  <span className="inline-chip">rework {String(entry.reworkReason ?? "-")}</span>
                </div>
              </article>
            ))
          )}
        </div>
      </Surface>

      <Surface>
        <p className="section-kicker">Windows</p>
        <h3 className="section-title">窗口视图</h3>
        <div className="record-list">
          {previewWindows.length === 0 ? (
            <EmptyState title="没有窗口记录" detail="当前分析结果里没有窗口级数据。" />
          ) : (
            previewWindows.map((window) => (
              <article className="record-card" key={`${String(window.invocationId ?? "window")}-${window.windowIndex}`}>
                <div className="record-head">
                  <div>
                    <h4 className="record-title">Window {window.windowIndex}</h4>
                    <p className="meta-copy mono">{String(window.invocationId ?? "-")}</p>
                  </div>
                  <StatusBadge value={window.finishReason ?? window.status} />
                </div>
                <div className="pill-row">
                  <span className="inline-chip">model {String(window.resolvedModel ?? window.requestedModel ?? "-")}</span>
                  <span className="inline-chip">provider {String(window.resolvedProvider ?? window.requestedProvider ?? "-")}</span>
                  <span className="inline-chip">tools {window.toolExecutionCount ?? 0}</span>
                  <span className="inline-chip">rounds {window.roundCount ?? 0}</span>
                  <span className="inline-chip">created {formatTimestamp(window.createdAt ?? null)}</span>
                  <span className="inline-chip">transition {String(window.transitionOutcome ?? "-")}</span>
                  <span className="inline-chip">cache {cacheSummaryLabel(window.cacheSummary)}</span>
                </div>
                <div className="kv-grid">
                  <div className="kv-item">
                    <p className="meta-label">Current Objective</p>
                    <p className="meta-copy">{String(window.currentObjective ?? "-")}</p>
                  </div>
                  <div className="kv-item">
                    <p className="meta-label">Current Focus</p>
                    <p className="meta-copy">{String(window.currentFocus ?? "-")}</p>
                  </div>
                  <div className="kv-item">
                    <p className="meta-label">Work Tree Node</p>
                    <p className="meta-copy mono">{String(window.workTreeCurrentNodeId ?? "-")}</p>
                  </div>
                  <div className="kv-item">
                    <p className="meta-label">Recovery Anchor</p>
                    <p className="meta-copy mono">{String(window.workTreeRecoveryAnchor ?? "-")}</p>
                  </div>
                  <div className="kv-item">
                    <p className="meta-label">Top Frame</p>
                    <p className="meta-copy mono">{String(window.topFrameId ?? "-")}</p>
                  </div>
                  <div className="kv-item">
                    <p className="meta-label">Prefix Cache Key</p>
                    <p className="meta-copy mono">{String(window.topFramePrefixCacheKey ?? "-")}</p>
                  </div>
                  <div className="kv-item">
                    <p className="meta-label">Continuation Reason</p>
                    <p className="meta-copy">{String(window.workTreeDebug?.continuationReason ?? window.resumePath ?? "-")}</p>
                  </div>
                  <div className="kv-item">
                    <p className="meta-label">Rework Reason</p>
                    <p className="meta-copy">{String(window.workTreeDebug?.reworkReason ?? "-")}</p>
                  </div>
                </div>
                {window.assistantTextSummary ? <p className="meta-copy">{window.assistantTextSummary}</p> : null}
                {window.workTreeDebug ? (
                  <div className="pill-row">
                    <span className="inline-chip">approval {window.workTreeDebug.approvalStop0_1 ?? 0}</span>
                    <span className="inline-chip">bubble {window.workTreeDebug.childBubble0_1 ?? 0}</span>
                    <span className="inline-chip">mixed {window.workTreeDebug.mixedOutcome0_1 ?? 0}</span>
                  </div>
                ) : null}
                {window.workTreeDebug?.recentChildCompletionSummaries?.length ? <p className="code-block mono">{jsonSnippet(window.workTreeDebug.recentChildCompletionSummaries)}</p> : null}
                {window.memoryRetrievalState ? <p className="code-block mono">{jsonSnippet(window.memoryRetrievalState)}</p> : null}
              </article>
            ))
          )}
        </div>
      </Surface>

      <div className="content-grid tight">
        <Surface>
          <p className="section-kicker">Turns</p>
          <h3 className="section-title">轮次视图</h3>
          <div className="record-list">
            {previewTurns.length === 0 ? (
              <EmptyState title="没有轮次记录" detail="当前分析结果里没有 round 级数据。" />
            ) : (
              previewTurns.map((turn) => (
                <article className="record-card" key={turn.turnId}>
                  <div className="record-head">
                    <div>
                      <h4 className="record-title">Window {turn.windowIndex} / Round {turn.roundIndex}</h4>
                      <p className="meta-copy">{turn.assistantTextPreview ?? "暂无 assistant 摘要"}</p>
                    </div>
                    <StatusBadge value={turn.finishReason ?? turn.mode} />
                  </div>
                  <div className="pill-row">
                    <span className="inline-chip">mode {String(turn.mode ?? "-")}</span>
                    <span className="inline-chip">toolCalls {turn.toolCallCount ?? 0}</span>
                    <span className="inline-chip">toolFailures {turn.toolFailureCount ?? 0}</span>
                    <span className="inline-chip">latency {String(turn.latencyMs ?? "-")} ms</span>
                  </div>
                </article>
              ))
            )}
          </div>
        </Surface>

        <Surface>
          <p className="section-kicker">Tools</p>
          <h3 className="section-title">工具视图</h3>
          <div className="record-list">
            {previewTools.length === 0 ? (
              <EmptyState title="没有工具记录" detail="当前分析结果里没有工具级数据。" />
            ) : (
              previewTools.map((tool) => (
                <article className="record-card" key={tool.toolExecutionId}>
                  <div className="record-head">
                    <div>
                      <h4 className="record-title">{tool.toolName ?? "unknown-tool"}</h4>
                      <p className="meta-copy">{tool.resultPreview ?? tool.failureSummary ?? "暂无结果摘要"}</p>
                    </div>
                    <StatusBadge value={tool.success ? "completed" : tool.status ?? "failed"} />
                  </div>
                  <div className="pill-row">
                    <span className="inline-chip">window {tool.windowIndex}</span>
                    <span className="inline-chip">round {String(tool.roundIndex ?? "-")}</span>
                    <span className="inline-chip">duration {String(tool.durationMs ?? "-")} ms</span>
                    <span className="inline-chip">detail {String(tool.detailLevel ?? "-")}</span>
                  </div>
                  <div className="kv-grid">
                    <div className="kv-item">
                      <p className="meta-label">Tool Call ID</p>
                      <p className="meta-copy mono">{String(tool.toolCallId ?? "-")}</p>
                    </div>
                    <div className="kv-item">
                      <p className="meta-label">Source Work Tree Node</p>
                      <p className="meta-copy mono">{String(tool.sourceWorkTreeNodeId ?? "-")}</p>
                    </div>
                  </div>
                </article>
              ))
            )}
          </div>
        </Surface>
      </div>

      <div className="content-grid tight">
        <Surface>
          <p className="section-kicker">Artifacts</p>
          <h3 className="section-title">工件定位</h3>
          <div className="record-list">
            {previewArtifacts.length === 0 ? (
              <EmptyState title="没有工件记录" detail="当前分析结果里没有 artifact 清单。" />
            ) : (
              previewArtifacts.map((artifact, index) => (
                <article className="record-card" key={`${artifact.kind}-${artifact.locator ?? index}`}>
                  <div className="record-head">
                    <div>
                      <h4 className="record-title">{artifact.kind}</h4>
                      <p className="meta-copy mono">{String(artifact.locator ?? "-")}</p>
                    </div>
                    <StatusBadge value={artifact.exists ? "completed" : "missing"} />
                  </div>
                  <div className="pill-row">
                    <span className="inline-chip">run {String(artifact.runId ?? "-")}</span>
                    <span className="inline-chip">invocation {String(artifact.invocationId ?? "-")}</span>
                  </div>
                </article>
              ))
            )}
          </div>
        </Surface>

        <Surface>
          <p className="section-kicker">Source Signals</p>
          <h3 className="section-title">辅助信号</h3>
          <div className="pill-row">
            <span className="inline-chip">snapshots {sourceSnapshots.length}</span>
            <span className="inline-chip">mailbox {sourceMailbox.length}</span>
            <span className="inline-chip">side-channel {sourceSideChannel.length}</span>
          </div>
          <div className="content-grid tight">
            <div className="kv-item">
              <p className="meta-label">Takeover Protocol</p>
              <p className="code-block mono">{jsonSnippet((data.sources ?? {}).takeoverProtocol)}</p>
            </div>
            <div className="kv-item">
              <p className="meta-label">Work Context Stack</p>
              <p className="code-block mono">{jsonSnippet((data.sources ?? {}).workContextStack)}</p>
            </div>
          </div>
        </Surface>
      </div>
    </div>
  );
}