"use client";

import Link from "next/link";
import { useState } from "react";

import type { TaskControlActionResponse, TaskDetailResponse } from "@yggdrasil/frontend-sdk";

import { postApiJson, useApiResource } from "../lib/use-api-resource";
import { useTranslation } from "./locale-provider";
import { ErrorState, LoadingState, PageHeader, StatusBadge, Surface, formatTimestamp, statusLabel } from "./workbench-primitives";
import { TaskLlmWorkAnalysisView } from "./task-llm-work-analysis";

type BudgetStatePayload = {
  tokenBudgetTotal?: number | null;
  tokenBudgetUsed?: number;
  costBudgetTotal?: number | null;
  costBudgetUsed?: number;
  [key: string]: unknown;
};

function normalizeBudgetState(task: TaskDetailResponse["task"]): BudgetStatePayload {
  const budgetCandidate = task.budgetState ?? task.budget;
  if (!budgetCandidate || typeof budgetCandidate !== "object" || Array.isArray(budgetCandidate)) {
    return {};
  }
  return { ...(budgetCandidate as BudgetStatePayload) };
}

function parseOptionalInt(value: string): number | null {
  const trimmed = value.trim();
  if (trimmed.length === 0) {
    return null;
  }
  const parsed = Number.parseInt(trimmed, 10);
  return Number.isFinite(parsed) ? parsed : null;
}

function parseOptionalFloat(value: string): number | null {
  const trimmed = value.trim();
  if (trimmed.length === 0) {
    return null;
  }
  const parsed = Number.parseFloat(trimmed);
  return Number.isFinite(parsed) ? parsed : null;
}

export function TaskDetailPage({ taskId }: { taskId: string }) {
  const { locale, t } = useTranslation();
  const { data, error, isLoading, reload } = useApiResource<TaskDetailResponse>(`/tasks/${encodeURIComponent(taskId)}`);
  const [controlError, setControlError] = useState<string | null>(null);
  const [controlMessage, setControlMessage] = useState<string | null>(null);
  const [activeAction, setActiveAction] = useState<"pause" | "safe-stop" | "resume" | "retry" | "top-up" | "approve" | "revise" | "cancel" | "save-snapshot" | "branch" | null>(null);
  const [budgetTopUp, setBudgetTopUp] = useState<{ tokenDelta: string; costDelta: string }>({ tokenDelta: "", costDelta: "" });

  if (isLoading) {
    return <LoadingState title={t("taskDetail.loading")} />;
  }

  if (error || !data || !data.task) {
    return <ErrorState detail={error ?? t("taskDetail.unavailable")} />;
  }

  const taskDetail = data;
  const latestUserSavedSnapshot = taskDetail.snapshots.find(
    (snapshot) => snapshot.retentionClass === "user-saved" && snapshot.status === "restorable",
  );

  async function submitPauseRequest() {
    setActiveAction("pause");
    setControlError(null);
    setControlMessage(null);
    try {
      const response = await postApiJson<TaskControlActionResponse>(`/tasks/${encodeURIComponent(taskId)}/pause`, {
        reason: "operator-requested-pause",
        waitForSafeStop: true,
        resumeMessage: taskDetail.runtimeControl.recommendedResumeMessage ?? taskDetail.task.resumeMessage ?? null,
      });
      setControlMessage(t("taskDetail.pauseSubmitted", { status: statusLabel(response.task.status ?? response.status, t) }));
      reload();
    } catch (actionError) {
      setControlError(actionError instanceof Error ? actionError.message : String(actionError));
    } finally {
      setActiveAction(null);
    }
  }

  async function submitSafeStopRequest() {
    setActiveAction("safe-stop");
    setControlError(null);
    setControlMessage(null);
    try {
      const response = await postApiJson<TaskControlActionResponse>(`/tasks/${encodeURIComponent(taskId)}/pause`, {
        reason: "operator-safe-stop",
        pauseMode: "safe-stop",
        waitForSafeStop: true,
        resumeMessage: taskDetail.runtimeControl.recommendedResumeMessage ?? taskDetail.task.resumeMessage ?? null,
      });
      setControlMessage(t("taskDetail.safeStopSubmitted", { status: statusLabel(response.task.status ?? response.status, t) }));
      reload();
    } catch (actionError) {
      setControlError(actionError instanceof Error ? actionError.message : String(actionError));
    } finally {
      setActiveAction(null);
    }
  }

  async function submitResumeRequest() {
    setActiveAction("resume");
    setControlError(null);
    setControlMessage(null);
    try {
      const response = await postApiJson<TaskControlActionResponse>(`/tasks/${encodeURIComponent(taskId)}/resume`, {
        resumeMessage: taskDetail.runtimeControl.recommendedResumeMessage ?? taskDetail.task.resumeMessage ?? null,
      });
      setControlMessage(t("taskDetail.resumeQueued", { depth: String(response.queueDepth ?? "-") }));
      reload();
    } catch (actionError) {
      setControlError(actionError instanceof Error ? actionError.message : String(actionError));
    } finally {
      setActiveAction(null);
    }
  }

  async function submitCancelRequest() {
    setActiveAction("cancel");
    setControlError(null);
    setControlMessage(null);
    try {
      const response = await postApiJson<TaskControlActionResponse>(`/tasks/${encodeURIComponent(taskId)}/cancel`, {
        reason: "operator-cancelled",
      });
      setControlMessage(t("taskDetail.cancelled", { status: statusLabel(response.task.status ?? response.status, t) }));
      reload();
    } catch (actionError) {
      setControlError(actionError instanceof Error ? actionError.message : String(actionError));
    } finally {
      setActiveAction(null);
    }
  }

  async function submitSaveSnapshot() {
    setActiveAction("save-snapshot");
    setControlError(null);
    setControlMessage(null);
    try {
      const response = await postApiJson<TaskControlActionResponse>(`/tasks/${encodeURIComponent(taskId)}/snapshots/save-current`, {
        label: `manual-save-${new Date().toISOString()}`,
      });
      const snapshot = response.snapshot as { id?: string } | undefined;
      setControlMessage(t("taskDetail.snapshotSaved", { id: String(snapshot?.id ?? "") }));
      reload();
    } catch (actionError) {
      setControlError(actionError instanceof Error ? actionError.message : String(actionError));
    } finally {
      setActiveAction(null);
    }
  }

  async function submitBranchFromSavedSnapshot() {
    if (!latestUserSavedSnapshot) {
      setControlError(t("taskDetail.noSavedSnapshot"));
      return;
    }
    setActiveAction("branch");
    setControlError(null);
    setControlMessage(null);
    try {
      const response = await postApiJson<TaskControlActionResponse>(`/tasks/${encodeURIComponent(taskId)}/branches`, {
        snapshotId: latestUserSavedSnapshot.id,
        label: latestUserSavedSnapshot.savedLabel ?? "user-saved branch",
      });
      const childTask = response.childTask as { id?: string } | undefined;
      setControlMessage(t("taskDetail.branchCreated", { id: String(childTask?.id ?? "") }));
      reload();
    } catch (actionError) {
      setControlError(actionError instanceof Error ? actionError.message : String(actionError));
    } finally {
      setActiveAction(null);
    }
  }

  async function submitApproveCompletion() {
    setActiveAction("approve");
    setControlError(null);
    setControlMessage(null);
    try {
      const response = await postApiJson<TaskControlActionResponse>(`/tasks/${encodeURIComponent(taskId)}/approve-completion`, {
        currentFocus: "completed",
      });
      setControlMessage(t("taskDetail.approved", { status: statusLabel(response.task.status ?? response.status, t) }));
      reload();
    } catch (actionError) {
      setControlError(actionError instanceof Error ? actionError.message : String(actionError));
    } finally {
      setActiveAction(null);
    }
  }

  async function submitRetryRequest(extraPayload?: Record<string, unknown>) {
    setActiveAction("retry");
    setControlError(null);
    setControlMessage(null);
    try {
      const response = await postApiJson<TaskControlActionResponse>(`/tasks/${encodeURIComponent(taskId)}/retry`, {
        reason: "manual-retry",
        resumeMessage: taskDetail.runtimeControl.recommendedResumeMessage ?? taskDetail.task.resumeMessage ?? null,
        ...extraPayload,
      });
      setControlMessage(t("taskDetail.retryQueued", { depth: String(response.queueDepth ?? "-") }));
      reload();
    } catch (actionError) {
      setControlError(actionError instanceof Error ? actionError.message : String(actionError));
    } finally {
      setActiveAction(null);
    }
  }

  async function submitRevisionRequest() {
    setActiveAction("revise");
    setControlError(null);
    setControlMessage(null);
    try {
      const response = await postApiJson<TaskControlActionResponse>(`/tasks/${encodeURIComponent(taskId)}/request-revision`, {
        nodeId: taskDetail.runtimeControl.recommendedRevisionNodeId ?? undefined,
        reason: `operator-revision:${taskDetail.runtimeControl.recommendedRevisionNodeId ?? "root"}`,
      });
      setControlMessage(t("taskDetail.revisionQueued", { depth: String(response.queueDepth ?? "-") }));
      reload();
    } catch (actionError) {
      setControlError(actionError instanceof Error ? actionError.message : String(actionError));
    } finally {
      setActiveAction(null);
    }
  }

  async function submitBudgetTopUpAndContinue() {
    setActiveAction("top-up");
    setControlError(null);
    setControlMessage(null);
    try {
      const tokenDelta = parseOptionalInt(budgetTopUp.tokenDelta);
      const costDelta = parseOptionalFloat(budgetTopUp.costDelta);
      if ((tokenDelta ?? 0) <= 0 && (costDelta ?? 0) <= 0) {
        throw new Error(t("taskDetail.budgetInvalid"));
      }

      const currentBudget = normalizeBudgetState(taskDetail.task);
      const tokenUsed = Number(currentBudget.tokenBudgetUsed ?? 0);
      const costUsed = Number(currentBudget.costBudgetUsed ?? 0);
      const tokenTotal =
        typeof currentBudget.tokenBudgetTotal === "number" ? currentBudget.tokenBudgetTotal : null;
      const costTotal = typeof currentBudget.costBudgetTotal === "number" ? currentBudget.costBudgetTotal : null;

      const nextTokenTotal =
        (tokenDelta ?? 0) > 0 ? Math.max(tokenTotal ?? tokenUsed, tokenUsed) + Number(tokenDelta) : tokenTotal;
      const nextCostTotal =
        (costDelta ?? 0) > 0 ? Math.max(costTotal ?? costUsed, costUsed) + Number(costDelta) : costTotal;

      const nextBudgetState: BudgetStatePayload = {
        ...currentBudget,
        tokenBudgetTotal: nextTokenTotal,
        costBudgetTotal: nextCostTotal,
      };

      if (taskDetail.runtimeControl.canResume) {
        const response = await postApiJson<TaskControlActionResponse>(`/tasks/${encodeURIComponent(taskId)}/resume`, {
          resumeMessage: taskDetail.runtimeControl.recommendedResumeMessage ?? taskDetail.task.resumeMessage ?? null,
          budgetState: nextBudgetState,
        });
        setControlMessage(
          t("taskDetail.budgetResumed", {
            token: String(nextTokenTotal ?? t("taskDetail.unlimited")),
            cost: String(nextCostTotal ?? t("taskDetail.unlimited")),
            depth: String(response.queueDepth ?? "-"),
          }),
        );
      } else if (taskDetail.runtimeControl.canRetry) {
        await submitRetryRequest({ budgetState: nextBudgetState, reason: "manual-budget-top-up-retry" });
      } else {
        throw new Error(t("taskDetail.budgetUnsupported"));
      }

      setBudgetTopUp({ tokenDelta: "", costDelta: "" });
      reload();
    } catch (actionError) {
      setControlError(actionError instanceof Error ? actionError.message : String(actionError));
    } finally {
      setActiveAction(null);
    }
  }

  return (
    <div className="task-detail-page">
      <PageHeader
        eyebrow={t("taskDetail.eyebrow")}
        title={taskDetail.task.title}
        summary={<>{t("taskDetail.goal", { goal: taskDetail.task.goal })}</>}
        actions={
          <>
            <Link className="ghost-button" href={`/tasks/${encodeURIComponent(taskId)}/analysis`}>
              {t("taskDetail.analysis")}
            </Link>
            {taskDetail.runtimeControl.canRequestPause ? (
              <button className="action-button" disabled={activeAction !== null} onClick={() => void submitSafeStopRequest()} type="button">
                {activeAction === "safe-stop" ? t("taskDetail.stoppingSafely") : t("taskDetail.safeStop")}
              </button>
            ) : null}
            {taskDetail.runtimeControl.canRequestPause ? (
              <button className="ghost-button" disabled={activeAction !== null} onClick={() => void submitPauseRequest()} type="button">
                {activeAction === "pause" ? t("taskDetail.pausing") : t("taskDetail.requestPause")}
              </button>
            ) : null}
            {taskDetail.runtimeControl.canResume ? (
              <button className="action-button" disabled={activeAction !== null} onClick={() => void submitResumeRequest()} type="button">
                {activeAction === "resume" ? t("taskDetail.resuming") : t("taskDetail.resumeSnapshot")}
              </button>
            ) : null}
            {taskDetail.runtimeControl.canSaveSnapshot ? (
              <button className="ghost-button" disabled={activeAction !== null} onClick={() => void submitSaveSnapshot()} type="button">
                {activeAction === "save-snapshot" ? t("taskDetail.saving") : t("taskDetail.saveSnapshot")}
              </button>
            ) : null}
            {taskDetail.runtimeControl.canBranch ? (
              <button className="ghost-button" disabled={activeAction !== null} onClick={() => void submitBranchFromSavedSnapshot()} type="button">
                {activeAction === "branch" ? t("taskDetail.branching") : t("taskDetail.branchSnapshot")}
              </button>
            ) : null}
            {taskDetail.runtimeControl.canCancel ? (
              <button className="ghost-button" disabled={activeAction !== null} onClick={() => void submitCancelRequest()} type="button">
                {activeAction === "cancel" ? t("taskDetail.cancelling") : t("taskDetail.cancelTask")}
              </button>
            ) : null}
            {taskDetail.runtimeControl.canRequestRevision ? (
              <button className="ghost-button" disabled={activeAction !== null} onClick={() => void submitRevisionRequest()} type="button">
                {activeAction === "revise" ? t("taskDetail.requestingRevision") : t("taskDetail.requestRevision")}
              </button>
            ) : null}
            {taskDetail.runtimeControl.canRetry ? (
              <button className="ghost-button" disabled={activeAction !== null} onClick={() => void submitRetryRequest()} type="button">
                {activeAction === "retry" ? t("taskDetail.retrying") : t("taskDetail.retryAfterFailure")}
              </button>
            ) : null}
            {taskDetail.runtimeControl.canApprove ? (
              <button className="action-button" disabled={activeAction !== null} onClick={() => void submitApproveCompletion()} type="button">
                {activeAction === "approve" ? t("taskDetail.approving") : t("taskDetail.approveCompletion")}
              </button>
            ) : null}
          </>
        }
      />

      <section className="detail-hero">
        <div className="record-head">
          <div>
            <p className="meta-label">{t("taskDetail.taskId")}</p>
            <p className="meta-copy mono">{taskDetail.task.id}</p>
          </div>
          <StatusBadge value={taskDetail.task.status} />
        </div>
        <div className="kv-grid">
          <div className="kv-item">
            <p className="meta-label">{t("taskDetail.currentObjective")}</p>
            <p className="meta-copy">{String(taskDetail.task.currentObjective ?? "-")}</p>
          </div>
          <div className="kv-item">
            <p className="meta-label">{t("taskDetail.currentFocus")}</p>
            <p className="meta-copy">{String(taskDetail.task.currentFocus ?? "-")}</p>
          </div>
          <div className="kv-item">
            <p className="meta-label">{t("taskDetail.branch")}</p>
            <p className="meta-copy mono">{String(taskDetail.task.branchId ?? "-")}</p>
          </div>
          <div className="kv-item">
            <p className="meta-label">{t("taskDetail.updated")}</p>
            <p className="meta-copy">{formatTimestamp(taskDetail.task.updatedAt ?? taskDetail.task.createdAt, locale)}</p>
          </div>
        </div>
      </section>

      <TaskLlmWorkAnalysisView mode="compact" taskId={taskId} />

      <details className="maintainer-disclosure">
        <summary>{t("taskDetail.rawRuntimeDetails")}</summary>
        <div className="maintainer-disclosure-body">

      <Surface>
        <p className="section-kicker">{t("taskDetail.runtimeControl")}</p>
        <h3 className="section-title">{t("taskDetail.runtimeControlTitle")}</h3>
        {controlMessage ? <p className="meta-copy">{controlMessage}</p> : null}
        {controlError ? <p className="error-copy">{controlError}</p> : null}
        <div className="kv-grid">
          <div className="kv-item">
            <p className="meta-label">{t("taskDetail.resumeStatus")}</p>
            <p className="meta-copy">{statusLabel(taskDetail.runtimeControl.resumeStatus, t)}</p>
          </div>
          <div className="kv-item">
            <p className="meta-label">{t("taskDetail.pauseIntent")}</p>
            <p className="meta-copy">{String(taskDetail.runtimeControl.pauseRequested)}</p>
          </div>
          <div className="kv-item">
            <p className="meta-label">{t("taskDetail.activeSnapshot")}</p>
            <p className="meta-copy mono">{String(taskDetail.runtimeControl.activeSnapshotId ?? "-")}</p>
          </div>
          <div className="kv-item">
            <p className="meta-label">{t("taskDetail.lastSafeStop")}</p>
            <p className="meta-copy">{formatTimestamp(taskDetail.runtimeControl.lastSafeStopAt ?? null, locale)}</p>
          </div>
          <div className="kv-item">
            <p className="meta-label">{t("taskDetail.activeAttempt")}</p>
            <p className="meta-copy mono">{String(taskDetail.runtimeControl.activeResumeAttemptId ?? "-")}</p>
          </div>
          <div className="kv-item">
            <p className="meta-label">{t("taskDetail.recommendedResumeMessage")}</p>
            <p className="meta-copy">{String(taskDetail.runtimeControl.recommendedResumeMessage ?? "-")}</p>
          </div>
          <div className="kv-item">
            <p className="meta-label">{t("taskDetail.resumeBlocker")}</p>
            <p className="meta-copy">{String(taskDetail.runtimeControl.blocker?.message ?? taskDetail.runtimeControl.resumeBlockedReason ?? "-")}</p>
          </div>
        </div>
        <div className="pill-row">
          <span className="inline-chip">{t("taskDetail.snapshotChip", { count: taskDetail.runtimeControl.snapshotCount })}</span>
          <span className="inline-chip">{t("taskDetail.restorableChip", { count: taskDetail.runtimeControl.restorableSnapshotCount })}</span>
          <span className="inline-chip">{t("taskDetail.consumedChip", { count: taskDetail.runtimeControl.consumedSnapshotCount })}</span>
          <span className="inline-chip">{t("taskDetail.canResumeChip", { value: String(taskDetail.runtimeControl.canResume) })}</span>
          <span className="inline-chip">{t("taskDetail.canPauseChip", { value: String(taskDetail.runtimeControl.canRequestPause) })}</span>
          <span className="inline-chip">{t("taskDetail.canRetryChip", { value: String(taskDetail.runtimeControl.canRetry ?? false) })}</span>
          <span className="inline-chip">{t("taskDetail.canCancelChip", { value: String(taskDetail.runtimeControl.canCancel ?? false) })}</span>
          <span className="inline-chip">{t("taskDetail.canSaveChip", { value: String(taskDetail.runtimeControl.canSaveSnapshot ?? false) })}</span>
          <span className="inline-chip">{t("taskDetail.canBranchChip", { value: String(taskDetail.runtimeControl.canBranch ?? false) })}</span>
          <span className="inline-chip">{t("taskDetail.canTopUpChip", { value: String(taskDetail.runtimeControl.canTopUp ?? false) })}</span>
          <span className="inline-chip">{t("taskDetail.canApproveChip", { value: String(taskDetail.runtimeControl.canApprove) })}</span>
          <span className="inline-chip">{t("taskDetail.canReviseChip", { value: String(taskDetail.runtimeControl.canRequestRevision) })}</span>
          <span className="inline-chip">{t("taskDetail.mailboxChip", { count: taskDetail.mailboxState.pendingCount })}</span>
        </div>
        {taskDetail.runtimeControl.canTopUp ? (
          <form
            onSubmit={(event) => {
              event.preventDefault();
              void submitBudgetTopUpAndContinue();
            }}
          >
            <p className="section-kicker">{t("taskDetail.budgetTopUp")}</p>
            <h4 className="subsection-title">{t("taskDetail.budgetTopUpTitle")}</h4>
            <div className="kv-grid">
              <label className="kv-item" htmlFor="task-token-topup">
                <p className="meta-label">{t("taskDetail.tokenTopUp")}</p>
                <input
                  className="field-input"
                  id="task-token-topup"
                  min={0}
                  onChange={(event) => setBudgetTopUp((value) => ({ ...value, tokenDelta: event.target.value }))}
                  placeholder={t("taskDetail.tokenPlaceholder")}
                  type="number"
                  value={budgetTopUp.tokenDelta}
                />
              </label>
              <label className="kv-item" htmlFor="task-cost-topup">
                <p className="meta-label">{t("taskDetail.costTopUp")}</p>
                <input
                  className="field-input"
                  id="task-cost-topup"
                  min={0}
                  onChange={(event) => setBudgetTopUp((value) => ({ ...value, costDelta: event.target.value }))}
                  placeholder={t("taskDetail.costPlaceholder")}
                  step="0.1"
                  type="number"
                  value={budgetTopUp.costDelta}
                />
              </label>
            </div>
            <div className="field-actions">
              <button className="action-button" disabled={activeAction !== null} type="submit">
                {activeAction === "top-up" ? t("taskDetail.toppingUp") : t("taskDetail.topUpAndContinue")}
              </button>
            </div>
          </form>
        ) : null}
        <div className="kv-grid">
          <div className="kv-item">
            <p className="meta-label">{t("taskDetail.recommendedRevisionNode")}</p>
            <p className="meta-copy mono">{String(taskDetail.runtimeControl.recommendedRevisionNodeId ?? "-")}</p>
          </div>
          <div className="kv-item">
            <p className="meta-label">{t("taskDetail.mailboxStatus")}</p>
            <p className="meta-copy">{statusLabel(taskDetail.mailboxState.status, t)}</p>
          </div>
          <div className="kv-item">
            <p className="meta-label">{t("taskDetail.pendingMailboxMessages")}</p>
            <p className="meta-copy">{String(taskDetail.mailboxState.pendingCount ?? 0)}</p>
          </div>
          <div className="kv-item">
            <p className="meta-label">{t("taskDetail.wakeOnMessage")}</p>
            <p className="meta-copy">{String(taskDetail.mailboxState.wakeOnMessage ?? false)}</p>
          </div>
        </div>
      </Surface>

      <div className="content-grid tight">
        <Surface>
          <p className="section-kicker">{t("taskDetail.agentRuns")}</p>
          <h3 className="section-title">{t("taskDetail.runHistory")}</h3>
          <div className="record-list">
            {taskDetail.agentRuns.map((run) => (
              <article className="record-card" key={run.id}>
                <div className="record-head">
                  <div>
                    <h4 className="record-title">{run.runType}</h4>
                    <p className="meta-copy mono">{run.id}</p>
                  </div>
                  <StatusBadge value={run.status} />
                </div>
                <div className="pill-row">
                  <span className="inline-chip">{t("taskDetail.modelChip", { value: run.selectedModel })}</span>
                  <span className="inline-chip">{t("taskDetail.providerChip", { value: String(run.selectedProvider ?? "-") })}</span>
                  <span className="inline-chip">{t("taskDetail.startedChip", { value: formatTimestamp(run.startedAt, locale) })}</span>
                </div>
              </article>
            ))}
          </div>
        </Surface>

        <Surface>
          <p className="section-kicker">{t("taskDetail.snapshots")}</p>
          <h3 className="section-title">{t("taskDetail.snapshotsTitle")}</h3>
          <div className="record-list">
            {taskDetail.snapshots.map((snapshot) => (
              <article className="record-card" key={snapshot.id}>
                <div className="record-head">
                  <div>
                    <h4 className="record-title">{snapshot.resumeMessage ?? t("taskDetail.safeStopSnapshot")}</h4>
                    <p className="meta-copy mono">{snapshot.id}</p>
                  </div>
                  <StatusBadge value={snapshot.status} />
                </div>
                <div className="pill-row">
                  <span className="inline-chip">{t("taskDetail.createdChip", { value: formatTimestamp(snapshot.createdAt, locale) })}</span>
                  <span className="inline-chip">{t("taskDetail.consumedAtChip", { value: formatTimestamp(snapshot.consumedAt, locale) })}</span>
                  <span className="inline-chip">{t("taskDetail.retentionChip", { value: String(snapshot.retentionClass ?? "-") })}</span>
                  <span className="inline-chip">{t("taskDetail.expiresChip", { value: formatTimestamp(snapshot.expiresAt ?? null, locale) })}</span>
                  <span className="inline-chip">{t("taskDetail.labelChip", { value: String(snapshot.savedLabel ?? "-") })}</span>
                  {snapshot.blockerCode || snapshot.blockerMessage ? (
                    <span className="inline-chip">{t("taskDetail.blockerChip", { value: String(snapshot.blockerCode ?? snapshot.blockerMessage) })}</span>
                  ) : null}
                </div>
              </article>
            ))}
          </div>
        </Surface>
      </div>

      <Surface>
        <p className="section-kicker">{t("taskDetail.routing")}</p>
        <h3 className="section-title">{t("taskDetail.routingTitle")}</h3>
        <div className="record-list">
          {taskDetail.routeDecisions.map((decision) => (
            <article className="record-card" key={decision.id}>
              <div className="record-head">
                <div>
                  <h4 className="record-title">{decision.selectedModel}</h4>
                  <p className="meta-copy">{decision.reason}</p>
                </div>
                <span className="inline-chip">{t("taskDetail.policyChip", { value: decision.routePolicyVersion })}</span>
              </div>
              <div className="pill-row">
                <span className="inline-chip">{t("taskDetail.providerChip", { value: String(decision.selectedProvider ?? "-") })}</span>
                <span className="inline-chip">{t("taskDetail.createdChip", { value: formatTimestamp(decision.createdAt, locale) })}</span>
              </div>
            </article>
          ))}
        </div>
      </Surface>

      <Surface>
        <p className="section-kicker">{t("taskDetail.modelInvocations")}</p>
        <h3 className="section-title">{t("taskDetail.modelInvocationsTitle")}</h3>
        <div className="record-list">
          {taskDetail.modelInvocations.length === 0 ? (
            <div className="empty-state">
              <h4 className="subsection-title">{t("taskDetail.noModelInvocations")}</h4>
              <p className="empty-copy">{t("taskDetail.noModelInvocationsCopy")}</p>
            </div>
          ) : (
            taskDetail.modelInvocations.map((invocation) => (
              <article className="record-card" key={invocation.id}>
                <div className="record-head">
                  <div>
                    <h4 className="record-title">{invocation.resolvedModel}</h4>
                    <p className="meta-copy mono">{invocation.id}</p>
                  </div>
                  <StatusBadge value={invocation.status} />
                </div>
                <div className="pill-row">
                  <span className="inline-chip">{t("taskDetail.providerChip", { value: String(invocation.resolvedProvider ?? invocation.requestedProvider ?? "-") })}</span>
                  <span className="inline-chip">{t("taskDetail.inputChip", { value: invocation.inputTokensUsed })}</span>
                  <span className="inline-chip">{t("taskDetail.outputChip", { value: invocation.outputTokensUsed })}</span>
                  <span className="inline-chip">{t("taskDetail.latencyChip", { value: String(invocation.latencyMs ?? "-") })}</span>
                  <span className="inline-chip">{t("taskDetail.costChip", { value: invocation.costUsed.toFixed(4) })}</span>
                </div>
                <div className="kv-grid">
                  <div className="kv-item">
                    <p className="meta-label">{t("taskDetail.requestRef")}</p>
                    <p className="meta-copy mono">{String(invocation.requestRef?.locator ?? "-")}</p>
                  </div>
                  <div className="kv-item">
                    <p className="meta-label">{t("taskDetail.responseRef")}</p>
                    <p className="meta-copy mono">{String(invocation.responseRef?.locator ?? "-")}</p>
                  </div>
                  <div className="kv-item">
                    <p className="meta-label">{t("taskDetail.trace")}</p>
                    <p className="meta-copy mono">{String(invocation.traceId ?? "-")}</p>
                  </div>
                  <div className="kv-item">
                    <p className="meta-label">{t("taskDetail.started")}</p>
                    <p className="meta-copy">{formatTimestamp(invocation.startedAt, locale)}</p>
                  </div>
                </div>
                {invocation.errorSummary ? <p className="code-block mono">{invocation.errorSummary}</p> : null}
              </article>
            ))
          )}
        </div>
      </Surface>

      <div className="content-grid tight">
        <Surface>
          <p className="section-kicker">{t("taskDetail.mailbox")}</p>
          <h3 className="section-title">{t("taskDetail.mailboxTitle")}</h3>
          <div className="record-list">
            {taskDetail.mailboxMessages.length === 0 ? (
              <div className="empty-state">
                <h4 className="subsection-title">{t("taskDetail.noMailbox")}</h4>
                <p className="empty-copy">{t("taskDetail.noMailboxCopy")}</p>
              </div>
            ) : (
              taskDetail.mailboxMessages.map((message) => (
                <article className="record-card" key={message.id}>
                  <div className="record-head">
                    <div>
                      <h4 className="record-title">{message.subject}</h4>
                      <p className="meta-copy mono">{message.id}</p>
                    </div>
                    <StatusBadge value={message.status} />
                  </div>
                  <p className="meta-copy">{message.body}</p>
                  <div className="pill-row">
                    <span className="inline-chip">{t("taskDetail.kindChip", { value: message.messageKind })}</span>
                    <span className="inline-chip">{t("taskDetail.senderChip", { value: String(message.sender?.id ?? "-") })}</span>
                    <span className="inline-chip">{t("taskDetail.nodeChip", { value: String(message.workTreeNodeId ?? "-") })}</span>
                    <span className="inline-chip">{t("taskDetail.createdChip", { value: formatTimestamp(message.createdAt, locale) })}</span>
                  </div>
                </article>
              ))
            )}
          </div>
        </Surface>

        <Surface>
          <p className="section-kicker">{t("taskDetail.sideChannel")}</p>
          <h3 className="section-title">{t("taskDetail.sideChannelTitle")}</h3>
          <div className="record-list">
            {taskDetail.sideChannelEvents.length === 0 ? (
              <div className="empty-state">
                <h4 className="subsection-title">{t("taskDetail.noSideChannel")}</h4>
                <p className="empty-copy">{t("taskDetail.noSideChannelCopy")}</p>
              </div>
            ) : (
              taskDetail.sideChannelEvents.map((event) => (
                <article className="record-card" key={event.id}>
                  <div className="record-head">
                    <div>
                      <h4 className="record-title">{event.eventKind}</h4>
                      <p className="meta-copy mono">{event.id}</p>
                    </div>
                    <StatusBadge value={event.level} />
                  </div>
                  <p className="meta-copy">{event.summary}</p>
                  <div className="pill-row">
                    <span className="inline-chip">{t("taskDetail.sourceChip", { value: String(event.source?.id ?? "-") })}</span>
                    <span className="inline-chip">{t("taskDetail.nodeChip", { value: String(event.workTreeNodeId ?? "-") })}</span>
                    <span className="inline-chip">{t("taskDetail.createdChip", { value: formatTimestamp(event.createdAt, locale) })}</span>
                  </div>
                </article>
              ))
            )}
          </div>
        </Surface>
      </div>
        </div>
      </details>
    </div>
  );
}
