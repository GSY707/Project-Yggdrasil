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
import { localizedText } from "../i18n";
import { EmptyState, ErrorState, LoadingState, PageHeader, StatCard, Surface, StatusBadge, formatTimestamp } from "./workbench-primitives";
import { useTranslation } from "./locale-provider";

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
  const { locale } = useTranslation();
  const l = (zhCNText: string, englishText: string) => localizedText(locale, zhCNText, englishText);
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
    return <LoadingState title={mode === "compact" ? localizedText(locale, "正在生成 LLM 工作摘要", "Generating LLM work summary") : localizedText(locale, "正在装配 LLM 工作分析页", "Assembling LLM work analysis")} />;
  }

  if (error && !data) {
    return <ErrorState title={localizedText(locale, "LLM 工作分析不可用", "LLM work analysis unavailable")} detail={error} />;
  }

  if (!data || !data.analysis) {
    return <EmptyState title={localizedText(locale, "暂无 LLM 工作分析", "No LLM work analysis")} detail={localizedText(locale, "当前任务还没有可读的分析工件。", "This task has no readable analysis artifacts.")} />;
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
              <p className="section-kicker">{l("LLM 工作分析", "LLM Work Analysis")}</p>
              <h3 className="section-title">{localizedText(locale, "运行过程分析摘要", "Runtime analysis summary")}</h3>
              <p className="meta-copy">
                {localizedText(locale, "最近分析生成于", "Latest analysis generated")} {formatTimestamp(data.analysis.generatedAt, locale)}{localizedText(locale, "，用于快速查看窗口、工具和工件覆盖情况。", ", for a quick view of window, tool, and artifact coverage.")}
              </p>
            </div>
            <div className="pill-row">
              <button className="ghost-button" disabled={isRefreshing} onClick={() => void refreshAnalysis()} type="button">
                {isRefreshing ? localizedText(locale, "正在刷新分析", "Refreshing") : localizedText(locale, "刷新分析", "Refresh analysis")}
              </button>
              <Link className="action-button" href={`/tasks/${encodeURIComponent(taskId)}/analysis`}>
                {localizedText(locale, "打开完整分析页", "Open full analysis")}
              </Link>
            </div>
          </div>
          {refreshError ? <p className="error-copy">{refreshError}</p> : null}
          <section className="stat-grid">
            <StatCard label={l("窗口", "Windows")} value={summary?.windowCount ?? 0} copy={`${l("最近", "latest")} ${summary?.latestWindowIndex ?? 0}，${l("重启", "restarts")} ${summary?.restartCount ?? 0}`} />
            <StatCard label={l("轮次", "Turns")} value={summary?.turnCount ?? 0} copy={`${l("工具", "tools")} ${summary?.toolExecutionCount ?? 0}，${l("回退", "fallback")} ${summary?.fallbackInvocationCount ?? 0}`} />
            <StatCard label={l("令牌", "Tokens")} value={`${summary?.totalInputTokens ?? 0}/${summary?.totalOutputTokens ?? 0}`} copy={localizedText(locale, "输入/输出 token 总量。", "Total input/output tokens.")} />
            <StatCard label={l("工件", "Artifacts")} value={artifactStatusSummary(artifacts)} copy={`${l("请求", "request")} ${coverage?.requestArtifactsAvailable ?? 0}，${l("响应", "response")} ${coverage?.responseArtifactsAvailable ?? 0}`} />
            <StatCard label={l("缓存", "Cache")} value={cacheSummaryLabel(cacheSummary)} copy={`${l("命中/写入/非缓存", "hit/write/non-cache")}，${l("窗口", "windows")} ${cacheSummary?.cacheHitWindowCount ?? 0}`} />
            <StatCard label={l("工作树", "Work Tree")} value={workTreeDebug?.distinctNodeCount ?? 0} copy={`${l("切换", "switch")} ${workTreeDebug?.nodeSwitchCount ?? 0}，${l("审批停止", "approval")} ${workTreeDebug?.approvalStopCount ?? 0}`} />
          </section>
          <div className="pill-row">
            <span className="inline-chip">{l("分析", "analysis")} {data.analysis.analysisId}</span>
            <span className="inline-chip">{l("运行", "run")} {String(data.selector.runId ?? "-")}</span>
            <span className="inline-chip">{l("警告", "warnings")} {summary?.warningEventCount ?? 0}</span>
            <span className="inline-chip">{l("邮箱", "mailbox")} {summary?.pendingMailboxCount ?? 0}</span>
          </div>
        </Surface>

        <div className="content-grid tight">
          <Surface>
            <p className="section-kicker">{l("窗口预览", "Window Preview")}</p>
            <h3 className="section-title">{localizedText(locale, "最近窗口", "Recent windows")}</h3>
            <div className="record-list">
              {previewWindows.length === 0 ? (
                <EmptyState title={localizedText(locale, "没有窗口记录", "No window records")} detail={localizedText(locale, "当前分析结果里还没有窗口级视图。", "No window-level view is available.")} />
              ) : (
                previewWindows.map((window) => (
                  <article className="record-card" key={`${String(window.invocationId ?? "window")}-${window.windowIndex}`}>
                    <div className="record-head">
                      <div>
                        <h4 className="record-title">{l("窗口", "Window")} {window.windowIndex}</h4>
                        <p className="meta-copy">{window.assistantTextSummary ?? window.currentFocus ?? window.currentObjective ?? localizedText(locale, "暂无摘要", "No summary")}</p>
                      </div>
                      <StatusBadge value={window.finishReason ?? window.status} />
                    </div>
                    <div className="pill-row">
                      <span className="inline-chip">{l("模型", "model")} {String(window.resolvedModel ?? window.requestedModel ?? "-")}</span>
                      <span className="inline-chip">{l("工具", "tools")} {window.toolExecutionCount ?? 0}</span>
                      <span className="inline-chip">{l("轮次", "rounds")} {window.roundCount ?? 0}</span>
                      <span className="inline-chip">{l("转移", "transition")} {String(window.transitionOutcome ?? "-")}</span>
                      <span className="inline-chip">{l("缓存", "cache")} {cacheSummaryLabel(window.cacheSummary)}</span>
                    </div>
                  </article>
                ))
              )}
            </div>
          </Surface>

          <Surface>
            <p className="section-kicker">{l("工具预览", "Tool Preview")}</p>
            <h3 className="section-title">{localizedText(locale, "最近工具执行", "Recent tool executions")}</h3>
            <div className="record-list">
              {previewTools.length === 0 ? (
                <EmptyState title={localizedText(locale, "没有工具记录", "No tool records")} detail={localizedText(locale, "当前任务还没有工具级分析结果。", "This task has no tool-level analysis.")} />
              ) : (
                previewTools.map((tool) => (
                  <article className="record-card" key={tool.toolExecutionId}>
                    <div className="record-head">
                      <div>
                        <h4 className="record-title">{tool.toolName ?? "unknown-tool"}</h4>
                        <p className="meta-copy">{tool.resultPreview ?? localizedText(locale, "暂无结果摘要", "No result summary")}</p>
                      </div>
                      <StatusBadge value={tool.success ? "completed" : tool.status ?? "unknown"} />
                    </div>
                    <div className="pill-row">
                      <span className="inline-chip">{l("窗口", "window")} {tool.windowIndex}</span>
                      <span className="inline-chip">{l("轮次", "round")} {String(tool.roundIndex ?? "-")}</span>
                      <span className="inline-chip">{l("耗时", "duration")} {String(tool.durationMs ?? "-")} ms</span>
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
        title={`${localizedText(locale, "任务", "Task")} ${taskId} ${localizedText(locale, "的运行过程分析", "runtime analysis")}`}
        summary={<>{localizedText(locale, "统一查看 run、window、turn、tool 与 artifact 五层结构化结果，直接用于评测对照和 runtime 排障。", "Inspect structured run, window, turn, tool, and artifact layers for evaluation comparison and runtime debugging.")}</>}
        actions={
          <>
            <button className="ghost-button" disabled={isRefreshing} onClick={() => void refreshAnalysis()} type="button">
              {isRefreshing ? localizedText(locale, "正在刷新分析", "Refreshing") : localizedText(locale, "重新生成分析", "Regenerate analysis")}
            </button>
            <Link className="ghost-button" href={`/tasks/${encodeURIComponent(taskId)}`}>
              {localizedText(locale, "返回任务详情", "Back to task")}
            </Link>
          </>
        }
      />

      {refreshError ? <p className="error-copy">{refreshError}</p> : null}

      <section className="stat-grid">
        <StatCard label={l("窗口", "Windows")} value={summary?.windowCount ?? 0} copy={`${l("重启", "restart")} ${summary?.restartCount ?? 0}，${l("最近", "latest")} ${summary?.latestWindowIndex ?? 0}`} />
        <StatCard label={l("轮次", "Turns")} value={summary?.turnCount ?? 0} copy={`${l("调用", "invocations")} ${summary?.invocationCount ?? 0}，${l("工具", "tools")} ${summary?.toolExecutionCount ?? 0}`} />
        <StatCard label={l("令牌", "Tokens")} value={`${summary?.totalInputTokens ?? 0}/${summary?.totalOutputTokens ?? 0}`} copy={localizedText(locale, "输入 / 输出 token 总量。", "Input / output token total.")} />
        <StatCard label={l("成本", "Cost")} value={(summary?.totalCostUsed ?? 0).toFixed(4)} copy={`${l("回退", "fallback")} ${summary?.fallbackInvocationCount ?? 0}，${l("失败", "failed")} ${summary?.failedInvocationCount ?? 0}`} />
        <StatCard label={l("工件", "Artifacts")} value={artifactStatusSummary(artifacts)} copy={`${l("指标", "metrics")} ${coverage?.metricsArtifactsAvailable ?? 0}，${l("窗口执行", "window-execution")} ${coverage?.windowExecutionArtifactsAvailable ?? 0}`} />
        <StatCard label={l("信号", "Signals")} value={`${summary?.warningEventCount ?? 0}/${summary?.errorEventCount ?? 0}`} copy={`${l("待处理邮箱", "pending mailbox")} ${summary?.pendingMailboxCount ?? 0}`} />
      </section>

      <Surface>
        <p className="section-kicker">{l("工作树调试", "Work Tree Debug")}</p>
        <h3 className="section-title">{localizedText(locale, "工作树调试摘要", "Work-tree debug summary")}</h3>
        <section className="stat-grid">
          <StatCard label={l("节点切换", "Node Switches")} value={workTreeDebug?.nodeSwitchCount ?? 0} copy={`${l("帧", "frames")} ${workTreeDebug?.frameSwitchCount ?? 0}，${l("前缀", "prefix")} ${workTreeDebug?.prefixCacheChangeCount ?? 0}`} />
          <StatCard label={l("审批停止", "Approval Stops")} value={workTreeDebug?.approvalStopCount ?? 0} copy={`${l("子任务气泡", "child bubble")} ${workTreeDebug?.childBubbleCount ?? 0}，${l("混合", "mixed")} ${workTreeDebug?.mixedOutcomeWindowCount ?? 0}`} />
          <StatCard label={l("不同节点", "Distinct Nodes")} value={workTreeDebug?.distinctNodeCount ?? 0} copy={`${l("最近", "latest")} ${String(workTreeDebug?.latestNodeId ?? "-")}`} />
          <StatCard label={l("缓存追踪", "Cache Trace")} value={cacheSummaryLabel(cacheSummary)} copy={`${l("命中窗口", "hit windows")} ${cacheSummary?.cacheHitWindowCount ?? 0}，${l("写入窗口", "write windows")} ${cacheSummary?.cacheWriteWindowCount ?? 0}`} />
        </section>
        <div className="pill-row">
          {(workTreeDebug?.distinctNodeIds ?? []).map((nodeId) => (
            <span className="inline-chip" key={`node-${nodeId}`}>{l("节点", "node")} {nodeId}</span>
          ))}
        </div>
        <div className="pill-row">
          {(workTreeDebug?.continuationReasons ?? []).map((reason) => (
            <span className="inline-chip" key={`reason-${reason}`}>{l("原因", "reason")} {reason}</span>
          ))}
        </div>
        <div className="pill-row">
          <span className="inline-chip">{l("最近前缀", "latest prefix")} {String(workTreeDebug?.latestPrefixCacheKey ?? "-")}</span>
          <span className="inline-chip">{l("缓存命中率", "cache hit ratio")} {(cacheSummary?.cacheHitRatio0_1 ?? 0).toFixed(4)}</span>
          <span className="inline-chip">{l("缓存写入率", "cache write ratio")} {(cacheSummary?.cacheWriteRatio0_1 ?? 0).toFixed(4)}</span>
        </div>
      </Surface>

      <Surface>
        <p className="section-kicker">{l("覆盖率", "Coverage")}</p>
        <h3 className="section-title">{localizedText(locale, "工件覆盖率", "Artifact coverage")}</h3>
        <div className="pill-row">
          <span className="inline-chip">{l("请求", "request")} {coverage?.requestArtifactsAvailable ?? 0}</span>
          <span className="inline-chip">{l("响应", "response")} {coverage?.responseArtifactsAvailable ?? 0}</span>
          <span className="inline-chip">{l("提示词", "prompt")} {coverage?.promptArtifactsAvailable ?? 0}</span>
          <span className="inline-chip">{l("指标", "metrics")} {coverage?.metricsArtifactsAvailable ?? 0}</span>
          <span className="inline-chip">{l("详细工具", "detailed tool")} {coverage?.detailedToolRecords ?? 0}</span>
          <span className="inline-chip">{l("接管协议", "takeover")} {String(coverage?.hasTakeoverProtocol ?? false)}</span>
          <span className="inline-chip">{l("工作上下文栈", "work-context-stack")} {String(coverage?.hasWorkContextStack ?? false)}</span>
        </div>
      </Surface>

      <Surface>
        <p className="section-kicker">{l("时间线", "Timeline")}</p>
        <h3 className="section-title">{localizedText(locale, "节点切换时间线", "Node switch timeline")}</h3>
        <div className="record-list">
          {timeline.length === 0 ? (
            <EmptyState title={localizedText(locale, "没有时间线记录", "No timeline records")} detail={localizedText(locale, "当前分析结果里还没有可展示的工作树时间线。", "No work-tree timeline is available.")} />
          ) : (
            timeline.map((entry, index) => (
              <article className="record-card" key={`${String(entry.invocationId ?? "timeline")}-${entry.windowIndex}-${index}`}>
                <div className="record-head">
                  <div>
                    <h4 className="record-title">{l("窗口", "Window")} {entry.windowIndex} / {l("节点", "Node")} {String(entry.nodeId ?? "-")}</h4>
                    <p className="meta-copy">{String(entry.continuationReason ?? entry.transitionOutcome ?? localizedText(locale, "暂无 continuation 原因", "No continuation reason"))}</p>
                  </div>
                  <StatusBadge value={entry.transitionOutcome ?? "unknown"} />
                </div>
                <div className="pill-row">
                  <span className="inline-chip">{l("帧", "frame")} {String(entry.topFrameId ?? "-")}</span>
                  <span className="inline-chip">{l("前缀", "prefix")} {String(entry.topFramePrefixCacheKey ?? "-")}</span>
                  <span className="inline-chip">{l("节点变化", "node-change")} {entry.nodeChanged0_1 ?? 0}</span>
                  <span className="inline-chip">{l("帧变化", "frame-change")} {entry.frameChanged0_1 ?? 0}</span>
                  <span className="inline-chip">{l("前缀变化", "prefix-change")} {entry.prefixCacheChanged0_1 ?? 0}</span>
                </div>
                <div className="pill-row">
                  <span className="inline-chip">{l("审批", "approval")} {entry.approvalStop0_1 ?? 0}</span>
                  <span className="inline-chip">{l("气泡", "bubble")} {entry.childBubble0_1 ?? 0}</span>
                  <span className="inline-chip">{l("混合", "mixed")} {entry.mixedOutcome0_1 ?? 0}</span>
                  <span className="inline-chip">{l("返工", "rework")} {String(entry.reworkReason ?? "-")}</span>
                </div>
              </article>
            ))
          )}
        </div>
      </Surface>

      <Surface>
        <p className="section-kicker">{l("窗口", "Windows")}</p>
        <h3 className="section-title">{localizedText(locale, "窗口视图", "Window view")}</h3>
        <div className="record-list">
          {previewWindows.length === 0 ? (
            <EmptyState title={localizedText(locale, "没有窗口记录", "No window records")} detail={localizedText(locale, "当前分析结果里没有窗口级数据。", "No window-level data is available.")} />
          ) : (
            previewWindows.map((window) => (
              <article className="record-card" key={`${String(window.invocationId ?? "window")}-${window.windowIndex}`}>
                <div className="record-head">
                  <div>
                    <h4 className="record-title">{l("窗口", "Window")} {window.windowIndex}</h4>
                    <p className="meta-copy mono">{String(window.invocationId ?? "-")}</p>
                  </div>
                  <StatusBadge value={window.finishReason ?? window.status} />
                </div>
                <div className="pill-row">
                  <span className="inline-chip">{l("模型", "model")} {String(window.resolvedModel ?? window.requestedModel ?? "-")}</span>
                  <span className="inline-chip">{l("供应商", "provider")} {String(window.resolvedProvider ?? window.requestedProvider ?? "-")}</span>
                  <span className="inline-chip">{l("工具", "tools")} {window.toolExecutionCount ?? 0}</span>
                  <span className="inline-chip">{l("轮次", "rounds")} {window.roundCount ?? 0}</span>
                  <span className="inline-chip">{l("创建", "created")} {formatTimestamp(window.createdAt ?? null, locale)}</span>
                  <span className="inline-chip">{l("转移", "transition")} {String(window.transitionOutcome ?? "-")}</span>
                  <span className="inline-chip">{l("缓存", "cache")} {cacheSummaryLabel(window.cacheSummary)}</span>
                </div>
                <div className="kv-grid">
                  <div className="kv-item">
                    <p className="meta-label">{l("当前目标", "Current Objective")}</p>
                    <p className="meta-copy">{String(window.currentObjective ?? "-")}</p>
                  </div>
                  <div className="kv-item">
                    <p className="meta-label">{l("当前重点", "Current Focus")}</p>
                    <p className="meta-copy">{String(window.currentFocus ?? "-")}</p>
                  </div>
                  <div className="kv-item">
                    <p className="meta-label">{l("工作树节点", "Work Tree Node")}</p>
                    <p className="meta-copy mono">{String(window.workTreeCurrentNodeId ?? "-")}</p>
                  </div>
                  <div className="kv-item">
                    <p className="meta-label">{l("恢复锚点", "Recovery Anchor")}</p>
                    <p className="meta-copy mono">{String(window.workTreeRecoveryAnchor ?? "-")}</p>
                  </div>
                  <div className="kv-item">
                    <p className="meta-label">{l("顶部帧", "Top Frame")}</p>
                    <p className="meta-copy mono">{String(window.topFrameId ?? "-")}</p>
                  </div>
                  <div className="kv-item">
                    <p className="meta-label">{l("前缀缓存键", "Prefix Cache Key")}</p>
                    <p className="meta-copy mono">{String(window.topFramePrefixCacheKey ?? "-")}</p>
                  </div>
                  <div className="kv-item">
                    <p className="meta-label">{l("继续原因", "Continuation Reason")}</p>
                    <p className="meta-copy">{String(window.workTreeDebug?.continuationReason ?? window.resumePath ?? "-")}</p>
                  </div>
                  <div className="kv-item">
                    <p className="meta-label">{l("返工原因", "Rework Reason")}</p>
                    <p className="meta-copy">{String(window.workTreeDebug?.reworkReason ?? "-")}</p>
                  </div>
                </div>
                {window.assistantTextSummary ? <p className="meta-copy">{window.assistantTextSummary}</p> : null}
                {window.workTreeDebug ? (
                  <div className="pill-row">
                    <span className="inline-chip">{l("审批", "approval")} {window.workTreeDebug.approvalStop0_1 ?? 0}</span>
                    <span className="inline-chip">{l("气泡", "bubble")} {window.workTreeDebug.childBubble0_1 ?? 0}</span>
                    <span className="inline-chip">{l("混合", "mixed")} {window.workTreeDebug.mixedOutcome0_1 ?? 0}</span>
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
          <p className="section-kicker">{l("轮次", "Turns")}</p>
          <h3 className="section-title">{localizedText(locale, "轮次视图", "Turn view")}</h3>
          <div className="record-list">
            {previewTurns.length === 0 ? (
              <EmptyState title={localizedText(locale, "没有轮次记录", "No turn records")} detail={localizedText(locale, "当前分析结果里没有 round 级数据。", "No round-level data is available.")} />
            ) : (
              previewTurns.map((turn) => (
                <article className="record-card" key={turn.turnId}>
                  <div className="record-head">
                    <div>
                      <h4 className="record-title">{l("窗口", "Window")} {turn.windowIndex} / {l("轮次", "Round")} {turn.roundIndex}</h4>
                      <p className="meta-copy">{turn.assistantTextPreview ?? localizedText(locale, "暂无 assistant 摘要", "No assistant summary")}</p>
                    </div>
                    <StatusBadge value={turn.finishReason ?? turn.mode} />
                  </div>
                  <div className="pill-row">
                    <span className="inline-chip">{l("模式", "mode")} {String(turn.mode ?? "-")}</span>
                    <span className="inline-chip">{l("工具调用", "toolCalls")} {turn.toolCallCount ?? 0}</span>
                    <span className="inline-chip">{l("工具失败", "toolFailures")} {turn.toolFailureCount ?? 0}</span>
                    <span className="inline-chip">{l("延迟", "latency")} {String(turn.latencyMs ?? "-")} ms</span>
                  </div>
                </article>
              ))
            )}
          </div>
        </Surface>

        <Surface>
          <p className="section-kicker">{l("工具", "Tools")}</p>
          <h3 className="section-title">{localizedText(locale, "工具视图", "Tool view")}</h3>
          <div className="record-list">
            {previewTools.length === 0 ? (
              <EmptyState title={localizedText(locale, "没有工具记录", "No tool records")} detail={localizedText(locale, "当前分析结果里没有工具级数据。", "No tool-level data is available.")} />
            ) : (
              previewTools.map((tool) => (
                <article className="record-card" key={tool.toolExecutionId}>
                  <div className="record-head">
                    <div>
                      <h4 className="record-title">{tool.toolName ?? "unknown-tool"}</h4>
                      <p className="meta-copy">{tool.resultPreview ?? tool.failureSummary ?? localizedText(locale, "暂无结果摘要", "No result summary")}</p>
                    </div>
                    <StatusBadge value={tool.success ? "completed" : tool.status ?? "failed"} />
                  </div>
                  <div className="pill-row">
                    <span className="inline-chip">{l("窗口", "window")} {tool.windowIndex}</span>
                    <span className="inline-chip">{l("轮次", "round")} {String(tool.roundIndex ?? "-")}</span>
                    <span className="inline-chip">{l("耗时", "duration")} {String(tool.durationMs ?? "-")} ms</span>
                    <span className="inline-chip">{l("详情", "detail")} {String(tool.detailLevel ?? "-")}</span>
                  </div>
                  <div className="kv-grid">
                    <div className="kv-item">
                      <p className="meta-label">{l("工具调用 ID", "Tool Call ID")}</p>
                      <p className="meta-copy mono">{String(tool.toolCallId ?? "-")}</p>
                    </div>
                    <div className="kv-item">
                      <p className="meta-label">{l("来源工作树节点", "Source Work Tree Node")}</p>
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
          <p className="section-kicker">{l("工件", "Artifacts")}</p>
          <h3 className="section-title">{localizedText(locale, "工件定位", "Artifact locations")}</h3>
          <div className="record-list">
            {previewArtifacts.length === 0 ? (
              <EmptyState title={localizedText(locale, "没有工件记录", "No artifact records")} detail={localizedText(locale, "当前分析结果里没有 artifact 清单。", "No artifact manifest is available.")} />
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
                    <span className="inline-chip">{l("运行", "run")} {String(artifact.runId ?? "-")}</span>
                    <span className="inline-chip">{l("调用", "invocation")} {String(artifact.invocationId ?? "-")}</span>
                  </div>
                </article>
              ))
            )}
          </div>
        </Surface>

        <Surface>
          <p className="section-kicker">{l("来源信号", "Source Signals")}</p>
          <h3 className="section-title">{localizedText(locale, "辅助信号", "Supporting signals")}</h3>
          <div className="pill-row">
            <span className="inline-chip">{l("快照", "snapshots")} {sourceSnapshots.length}</span>
            <span className="inline-chip">{l("邮箱", "mailbox")} {sourceMailbox.length}</span>
            <span className="inline-chip">{l("侧信道", "side-channel")} {sourceSideChannel.length}</span>
          </div>
          <div className="content-grid tight">
            <div className="kv-item">
              <p className="meta-label">{l("接管协议", "Takeover Protocol")}</p>
              <p className="code-block mono">{jsonSnippet((data.sources ?? {}).takeoverProtocol)}</p>
            </div>
            <div className="kv-item">
              <p className="meta-label">{l("工作上下文栈", "Work Context Stack")}</p>
              <p className="code-block mono">{jsonSnippet((data.sources ?? {}).workContextStack)}</p>
            </div>
          </div>
        </Surface>
      </div>
    </div>
  );
}
