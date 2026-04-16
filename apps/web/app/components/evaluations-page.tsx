"use client";

import { useState } from "react";

import type { EvaluationRunRecord, EvaluationSuiteRecord } from "@yggdrasil/frontend-sdk";

import { postApiJson, useApiResource } from "../lib/use-api-resource";
import { EmptyState, ErrorState, LoadingState, PageHeader, StatusBadge, Surface, formatTimestamp } from "./workbench-primitives";

type SuitesResponse = { evaluationSuites: EvaluationSuiteRecord[] };
type RunsResponse = { evaluationRuns: EvaluationRunRecord[] };

function recordArray(value: unknown): Array<Record<string, unknown>> {
  return Array.isArray(value) ? value.filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === "object") : [];
}

export function EvaluationsPage() {
  const suites = useApiResource<SuitesResponse>("/evaluations/suites");
  const runs = useApiResource<RunsResponse>("/evaluations/runs?limit=40");
  const [runningSuiteId, setRunningSuiteId] = useState<string | null>(null);
  const [runError, setRunError] = useState<string | null>(null);

  async function handleRunSuite(suiteId: string) {
    setRunningSuiteId(suiteId);
    setRunError(null);
    try {
      await postApiJson(`/evaluations/suites/${encodeURIComponent(suiteId)}/run`);
      suites.reload();
      runs.reload();
    } catch (error) {
      setRunError(error instanceof Error ? error.message : String(error));
    } finally {
      setRunningSuiteId(null);
    }
  }

  if (suites.isLoading || runs.isLoading) {
    return <LoadingState title="正在读取评测与回归面板" />;
  }

  if (suites.error || runs.error) {
    return <ErrorState detail={suites.error ?? runs.error ?? "评测数据不可用。"} />;
  }

  const suiteList = suites.data?.evaluationSuites ?? [];
  const runList = runs.data?.evaluationRuns ?? [];

  return (
    <div>
      <PageHeader
        eyebrow="Evaluations"
        title="M4-M8 回归与基准套件"
        summary={<>正式 suite 已落到 evaluation/suites，Web、CLI 与 live 联调共享同一套定义、baseline 对照与运行记录。</>}
      />

      {runError ? <ErrorState title="触发评测失败" detail={runError} /> : null}

      <div className="content-grid tight">
        <Surface>
          <p className="section-kicker">Suites</p>
          <h3 className="section-title">可执行回归套件</h3>
          <div className="record-list">
            {suiteList.map((suite) => (
              <article className="record-card" key={suite.id}>
                <div className="record-head">
                  <div>
                    <h4 className="record-title">{suite.name}</h4>
                    <p className="meta-copy mono">{suite.id}</p>
                  </div>
                  <button
                    className="action-button"
                    disabled={runningSuiteId === suite.id}
                    onClick={() => void handleRunSuite(suite.id)}
                    type="button"
                  >
                    {runningSuiteId === suite.id ? "运行中" : "执行 suite"}
                  </button>
                </div>
                <div className="pill-row">
                  <span className="inline-chip">domain {suite.domain}</span>
                  <span className="inline-chip">subject {suite.subjectRef}</span>
                  <span className="inline-chip">cases {suite.caseCount}</span>
                </div>
                <div className="record-list">
                  {suite.cases.map((testCase) => (
                    <article className="kv-item" key={testCase.id}>
                      <p className="meta-label">{testCase.scenario}</p>
                      <p className="meta-copy">{testCase.title}</p>
                      <div className="pill-row">
                        {testCase.tags.map((tag) => (
                          <span className="inline-chip" key={tag}>
                            {tag}
                          </span>
                        ))}
                      </div>
                    </article>
                  ))}
                </div>
              </article>
            ))}
          </div>
        </Surface>

        <Surface>
          <p className="section-kicker">Runs</p>
          <h3 className="section-title">最近执行结果</h3>
          <div className="record-list">
            {runList.length === 0 ? (
              <EmptyState title="还没有运行记录" detail="先执行 suite，随后结果会回写到数据库和指标工件。" />
            ) : (
              runList.map((run) => {
                const metrics = (run.metrics ?? {}) as Record<string, unknown>;
                return (
                  <article className="record-card" key={run.id}>
                    <div className="record-head">
                      <div>
                        <h4 className="record-title">{run.suiteId}</h4>
                        <p className="meta-copy mono">{run.id}</p>
                      </div>
                      <StatusBadge value={run.status} />
                    </div>
                    <div className="pill-row">
                      <span className="inline-chip">passRate {String(metrics.passRate ?? "-")}</span>
                      <span className="inline-chip">caseCount {String(metrics.caseCount ?? "-")}</span>
                      <span className="inline-chip">failed {String(metrics.failedCount ?? metrics.failedCaseCount ?? "-")}</span>
                      <span className="inline-chip">duration {String(metrics.totalDurationMs ?? "-")} ms</span>
                    </div>
                    {recordArray(metrics.strategyLeaderboard).length > 0 ? (
                      <div className="record-list">
                        {recordArray(metrics.strategyLeaderboard).map((row) => (
                          <article className="kv-item" key={String(row.name ?? "strategy")}> 
                            <p className="meta-label">Strategy Leaderboard</p>
                            <p className="meta-copy">{String(row.name ?? "unknown")} · score {String(row.avgCombinedScore ?? "-")}</p>
                            <div className="pill-row">
                              <span className="inline-chip">context {String(row.avgContextCoverage ?? "-")}</span>
                              <span className="inline-chip">answer {String(row.avgAnswerCoverage ?? "-")}</span>
                              <span className="inline-chip">cases {String(row.cases ?? "-")}</span>
                            </div>
                          </article>
                        ))}
                      </div>
                    ) : null}
                    {recordArray(metrics.baselineComparisons).length > 0 ? (
                      <div className="record-list">
                        {recordArray(metrics.baselineComparisons).map((comparison) => (
                          <article className="kv-item" key={String(comparison.caseId ?? "case")}> 
                            <p className="meta-label">Baseline Comparison</p>
                            <p className="meta-copy">{String(comparison.caseTitle ?? comparison.caseId ?? "case")} · top {String(comparison.topStrategy ?? "-")}</p>
                            <div className="pill-row">
                              {recordArray(comparison.strategies).map((strategy) => (
                                <span className="inline-chip" key={String(strategy.name ?? "strategy")}>
                                  {String(strategy.name ?? "strategy")} {String(strategy.combinedScore ?? "-")}
                                </span>
                              ))}
                            </div>
                          </article>
                        ))}
                      </div>
                    ) : null}
                    {recordArray(metrics.liveScenarios).length > 0 ? (
                      <div className="record-list">
                        {recordArray(metrics.liveScenarios).map((scenario) => (
                          <article className="kv-item" key={String(scenario.invocationId ?? scenario.taskId ?? "live")}> 
                            <p className="meta-label">Live Scenario</p>
                            <p className="meta-copy">{String(scenario.provider ?? "-")} / {String(scenario.model ?? "-")}</p>
                            <div className="pill-row">
                              <span className="inline-chip">status {String(scenario.invocationStatus ?? scenario.taskStatus ?? "-")}</span>
                              <span className="inline-chip">latency {String(scenario.latencyMs ?? "-")} ms</span>
                              <span className="inline-chip">tokens {String(scenario.totalTokens ?? "-")}</span>
                            </div>
                          </article>
                        ))}
                      </div>
                    ) : null}
                    <p className="meta-copy">created {formatTimestamp(run.createdAt)}</p>
                  </article>
                );
              })
            )}
          </div>
        </Surface>
      </div>
    </div>
  );
}