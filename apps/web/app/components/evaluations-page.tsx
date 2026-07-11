"use client";

import { useState } from "react";

import type { EvaluationRunRecord, EvaluationSuiteRecord } from "@yggdrasil/frontend-sdk";

import { postApiJson, useApiResource } from "../lib/use-api-resource";
import { localizedText } from "../i18n";
import { EmptyState, ErrorState, LoadingState, PageHeader, StatusBadge, Surface, formatTimestamp } from "./workbench-primitives";
import { useLocale } from "./locale-provider";

type SuitesResponse = { evaluationSuites: EvaluationSuiteRecord[] };
type RunsResponse = { evaluationRuns: EvaluationRunRecord[] };

function recordArray(value: unknown): Array<Record<string, unknown>> {
  return Array.isArray(value) ? value.filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === "object") : [];
}

export function EvaluationsPage() {
  const { locale } = useLocale();
  const l = (zhCN: string, english: string) => localizedText(locale, zhCN, english);
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
    return <LoadingState title={localizedText(locale, "正在读取评测与回归面板", "Loading evaluation and regression board")} />;
  }

  if (suites.error || runs.error) {
    return <ErrorState detail={suites.error ?? runs.error ?? localizedText(locale, "评测数据不可用。", "Evaluation data is unavailable.")} />;
  }

  const suiteList = suites.data?.evaluationSuites ?? [];
  const runList = runs.data?.evaluationRuns ?? [];

  return (
    <div>
      <PageHeader
        eyebrow={l("评测", "Evaluations")}
        title={localizedText(locale, "M4-M8 回归与基准套件", "M4–M8 regression and benchmark suites")}
        summary={<>{localizedText(locale, "正式 suite 已落到 evaluation/suites，Web、CLI 与 live 联调共享同一套定义、baseline 对照与运行记录。", "Canonical suites live under evaluation/suites; Web, CLI, and live runs share definitions, baselines, and records.")}</>}
      />

      {runError ? <ErrorState title={localizedText(locale, "触发评测失败", "Evaluation run failed")} detail={runError} /> : null}

      <div className="content-grid tight">
        <Surface>
          <p className="section-kicker">{l("套件", "Suites")}</p>
          <h3 className="section-title">{localizedText(locale, "可执行回归套件", "Runnable regression suites")}</h3>
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
                    {runningSuiteId === suite.id ? localizedText(locale, "运行中", "Running") : localizedText(locale, "执行 suite", "Run suite")}
                  </button>
                </div>
                <div className="pill-row">
                  <span className="inline-chip">{l("领域", "Domain")} {suite.domain}</span>
                  <span className="inline-chip">{l("主题", "Subject")} {suite.subjectRef}</span>
                  <span className="inline-chip">{l("用例", "Cases")} {suite.caseCount}</span>
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
          <p className="section-kicker">{l("运行", "Runs")}</p>
          <h3 className="section-title">{localizedText(locale, "最近执行结果", "Recent runs")}</h3>
          <div className="record-list">
            {runList.length === 0 ? (
              <EmptyState title={localizedText(locale, "还没有运行记录", "No runs yet")} detail={localizedText(locale, "先执行 suite，随后结果会回写到数据库和指标工件。", "Run a suite to write results back to the database and metric artifacts.")} />
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
                      <span className="inline-chip">{l("通过率", "Pass rate")} {String(metrics.passRate ?? "-")}</span>
                      <span className="inline-chip">{l("用例数", "Case count")} {String(metrics.caseCount ?? "-")}</span>
                      <span className="inline-chip">{l("失败", "Failed")} {String(metrics.failedCount ?? metrics.failedCaseCount ?? "-")}</span>
                      <span className="inline-chip">{l("耗时", "Duration")} {String(metrics.totalDurationMs ?? "-")} ms</span>
                    </div>
                    {recordArray(metrics.strategyLeaderboard).length > 0 ? (
                      <div className="record-list">
                        {recordArray(metrics.strategyLeaderboard).map((row) => (
                          <article className="kv-item" key={String(row.name ?? "strategy")}> 
                            <p className="meta-label">{l("策略排行榜", "Strategy leaderboard")}</p>
                            <p className="meta-copy">{String(row.name ?? l("未知", "Unknown"))} · {l("得分", "score")} {String(row.avgCombinedScore ?? "-")}</p>
                            <div className="pill-row">
                              <span className="inline-chip">{l("上下文", "Context")} {String(row.avgContextCoverage ?? "-")}</span>
                              <span className="inline-chip">{l("回答", "Answer")} {String(row.avgAnswerCoverage ?? "-")}</span>
                              <span className="inline-chip">{l("用例", "Cases")} {String(row.cases ?? "-")}</span>
                            </div>
                          </article>
                        ))}
                      </div>
                    ) : null}
                    {recordArray(metrics.baselineComparisons).length > 0 ? (
                      <div className="record-list">
                        {recordArray(metrics.baselineComparisons).map((comparison) => (
                          <article className="kv-item" key={String(comparison.caseId ?? "case")}> 
                            <p className="meta-label">{l("基线对比", "Baseline comparison")}</p>
                            <p className="meta-copy">{String(comparison.caseTitle ?? comparison.caseId ?? l("用例", "Case"))} · {l("最佳", "Top")} {String(comparison.topStrategy ?? "-")}</p>
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
                            <p className="meta-label">{l("实时场景", "Live scenario")}</p>
                            <p className="meta-copy">{String(scenario.provider ?? "-")} / {String(scenario.model ?? "-")}</p>
                            <div className="pill-row">
                              <span className="inline-chip">{l("状态", "Status")} {String(scenario.invocationStatus ?? scenario.taskStatus ?? "-")}</span>
                              <span className="inline-chip">{l("延迟", "Latency")} {String(scenario.latencyMs ?? "-")} ms</span>
                              <span className="inline-chip">{l("令牌", "Tokens")} {String(scenario.totalTokens ?? "-")}</span>
                            </div>
                          </article>
                        ))}
                      </div>
                    ) : null}
                    <p className="meta-copy">{l("创建于", "Created")} {formatTimestamp(run.createdAt, locale)}</p>
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
