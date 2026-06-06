"use client";

import type {
  DataGovernanceBackupResponse,
  DataGovernanceBackupsResponse,
  DataGovernanceDeletionResponse,
  DataGovernanceDeletionResult,
  DataGovernanceDeletionPlan,
  DataGovernanceDeletionPlanResponse,
  DataGovernanceManifest,
  DataGovernanceOperationsResponse,
} from "@yggdrasil/frontend-sdk";

import { useMemo, useState } from "react";

import { postApiJson, useApiResource } from "../lib/use-api-resource";
import { ErrorState, LoadingState, PageHeader, StatCard, StatusBadge, Surface, formatTimestamp } from "./workbench-primitives";

function jsonSnippet(value: unknown): string {
  return JSON.stringify(value ?? {}, null, 2);
}

function unknownRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" ? (value as Record<string, unknown>) : {};
}

function PlanPreview({ plan }: { plan: DataGovernanceDeletionPlan }) {
  const tableRows = plan.database?.tables ?? [];
  return (
    <Surface>
      <div className="record-head">
        <div>
          <p className="section-kicker">Deletion Preview</p>
          <h2 className="section-title">{plan.scopeKind} / {plan.scopeId}</h2>
          <p className="section-copy">target {String(plan.target?.title ?? plan.target?.mediaType ?? plan.target?.nodeType ?? "-")}</p>
        </div>
        <StatusBadge value={plan.blockers && plan.blockers.length > 0 ? "blocked" : "preview"} />
      </div>
      <section className="stat-grid compact">
        <StatCard label="DB Rows" value={plan.database?.totalRows ?? tableRows.reduce((sum, row) => sum + row.count, 0)} copy="预览会影响的数据库记录数。" />
        <StatCard label="State Files" value={plan.stateFileCount ?? 0} copy={`${plan.stateFileBytes ?? 0} bytes`} />
        <StatCard label="Blockers" value={plan.blockers?.length ?? 0} copy="阻塞项为 0 才允许后端确认执行。" />
        <StatCard label="Warnings" value={plan.warnings?.length ?? 0} copy="保留边界和外部系统提示。" />
      </section>
      {plan.blockers && plan.blockers.length > 0 ? (
        <div className="record-list">
          {plan.blockers.map((item) => (
            <article className="compact-record" key={item}>
              <p className="meta-label">Blocker</p>
              <p className="meta-copy">{item}</p>
            </article>
          ))}
        </div>
      ) : null}
      <div className="content-grid tight">
        <article className="record-card">
          <h3 className="record-title">Database Plan</h3>
          <div className="record-list">
            {tableRows.map((row) => (
              <div className="kv-item" key={row.table}>
                <div className="record-head">
                  <p className="meta-label">{row.table}</p>
                  <span className="inline-chip">{row.action}</span>
                </div>
                <p className="meta-copy">{row.count} rows</p>
                {row.sampleIds.length > 0 ? <p className="code-block mono">{row.sampleIds.slice(0, 6).join("\n")}</p> : null}
              </div>
            ))}
          </div>
        </article>
        <article className="record-card">
          <h3 className="record-title">Retained Boundary</h3>
          <div className="record-list">
            {(plan.retainedData ?? []).map((item, index) => (
              <div className="kv-item" key={`${String(item.location ?? "retained")}-${index}`}>
                <p className="meta-label">{String(item.reason ?? "retained")}</p>
                <p className="meta-copy mono">{String(item.location ?? "-")}</p>
              </div>
            ))}
          </div>
        </article>
      </div>
      {plan.warnings && plan.warnings.length > 0 ? (
        <ul className="mini-list">
          {plan.warnings.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      ) : null}
    </Surface>
  );
}

function DeletionResultSummary({ result }: { result: DataGovernanceDeletionResult }) {
  const certificate = result.deletionCertificate;
  return (
    <Surface>
      <div className="record-head">
        <div>
          <p className="section-kicker">Deletion Certificate</p>
          <h2 className="section-title">{certificate ? certificate.id : result.status}</h2>
          <p className="section-copy">删除执行结果与保留边界摘要会进入审计记录。</p>
        </div>
        <StatusBadge value={result.status} />
      </div>
      {certificate ? (
        <section className="stat-grid compact">
          <StatCard label="Deleted Rows" value={certificate.deletedRows} copy="数据库删除证明计数。" />
          <StatCard label="State Deleted" value={certificate.stateFiles.deleted} copy={`${certificate.stateFiles.requested} requested`} />
          <StatCard label="State Failed" value={certificate.stateFiles.failed} copy="失败项需要人工处理。" />
          <StatCard label="Backup" value={certificate.backupSnapshotDir ? "ready" : "skipped"} copy={certificate.backupSnapshotDir ?? "本次未创建保护性备份。"} />
        </section>
      ) : null}
      <p className="code-block mono">{jsonSnippet(certificate ?? result)}</p>
    </Surface>
  );
}

export function DataGovernancePage() {
  const manifest = useApiResource<DataGovernanceManifest>("/data-governance/manifest");
  const operations = useApiResource<DataGovernanceOperationsResponse>("/data-governance/operations?limit=20");
  const backups = useApiResource<DataGovernanceBackupsResponse>("/data-governance/backups?limit=8");
  const [scopeKind, setScopeKind] = useState("task");
  const [scopeId, setScopeId] = useState("");
  const [reason, setReason] = useState("local data governance operation");
  const [includeStateFiles, setIncludeStateFiles] = useState(true);
  const [backupBeforeDelete, setBackupBeforeDelete] = useState(true);
  const [confirmScopeId, setConfirmScopeId] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isCreatingBackup, setIsCreatingBackup] = useState(false);
  const [isExecutingDelete, setIsExecutingDelete] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [backupError, setBackupError] = useState<string | null>(null);
  const [backupMessage, setBackupMessage] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [plan, setPlan] = useState<DataGovernanceDeletionPlan | null>(null);
  const [deleteResult, setDeleteResult] = useState<DataGovernanceDeletionResult | null>(null);

  const isLoading = manifest.isLoading || operations.isLoading || backups.isLoading;
  const error = manifest.error ?? operations.error ?? backups.error;
  const manifestData = manifest.data;
  const operationRows = operations.data?.operations ?? [];
  const backupRows = backups.data?.snapshots ?? [];
  const stats = useMemo(() => {
    const assets = manifestData?.assets ?? [];
    return {
      totalAssets: assets.length,
      executablePolicies: assets.filter((item) => item.deletePolicy.includes("supported")).length,
      plannedPolicies: assets.filter((item) => item.deletePolicy.includes("pending") || item.deletePolicy.includes("planned")).length,
    };
  }, [manifestData?.assets]);
  const planBlockers = plan?.blockers ?? [];
  const canExecuteDelete =
    Boolean(plan) &&
    plan?.scopeKind === "task" &&
    !plan?.dryRunOnly &&
    planBlockers.length === 0 &&
    confirmScopeId.trim() === plan?.scopeId;

  async function submitPlan() {
    setIsSubmitting(true);
    setSubmitError(null);
    try {
      const response = await postApiJson<DataGovernanceDeletionPlanResponse>("/data-governance/deletion-plan", {
        scopeKind,
        scopeId: scopeId.trim(),
        reason,
        includeStateFiles,
        requestedBy: { type: "user", id: "web" },
      });
      setPlan(response.plan);
      setDeleteResult(null);
      setDeleteError(null);
      setConfirmScopeId("");
      operations.reload();
    } catch (error) {
      setSubmitError(error instanceof Error ? error.message : String(error));
    } finally {
      setIsSubmitting(false);
    }
  }

  async function createProtectiveBackup() {
    setIsCreatingBackup(true);
    setBackupError(null);
    setBackupMessage(null);
    try {
      const response = await postApiJson<DataGovernanceBackupResponse>("/data-governance/backup", {
        reason,
        requestedBy: { type: "user", id: "web" },
      });
      const backup = unknownRecord(response.backup);
      setBackupMessage(`已创建保护性备份：${String(backup.snapshotDir ?? backup.name ?? "snapshot")}`);
      backups.reload();
      operations.reload();
    } catch (error) {
      setBackupError(error instanceof Error ? error.message : String(error));
    } finally {
      setIsCreatingBackup(false);
    }
  }

  async function executeDelete() {
    if (!plan) {
      return;
    }
    setIsExecutingDelete(true);
    setDeleteError(null);
    try {
      const response = await postApiJson<DataGovernanceDeletionResponse>("/data-governance/delete", {
        scopeKind: plan.scopeKind,
        scopeId: plan.scopeId,
        confirmScopeId: confirmScopeId.trim(),
        reason,
        includeStateFiles,
        backupBeforeDelete,
        requestedBy: { type: "user", id: "web" },
      });
      setPlan(response.plan);
      setDeleteResult(response.result);
      operations.reload();
      backups.reload();
    } catch (error) {
      setDeleteError(error instanceof Error ? error.message : String(error));
    } finally {
      setIsExecutingDelete(false);
    }
  }

  if (isLoading) {
    return <LoadingState title="正在读取数据治理边界" />;
  }

  if (error || !manifestData) {
    return <ErrorState detail={error ?? "数据治理清单不可用。"} />;
  }

  return (
    <div>
      <PageHeader
        eyebrow="数据治理"
        title="本地数据资产、保护性备份、删除证明与审计"
        summary={<>统一展示本地数据位置、远端边界、删除影响预览、保护性备份和最近治理操作。task 硬删除需要无阻塞 plan 与精确确认。</>}
        actions={<button className="ghost-button" onClick={() => { manifest.reload(); operations.reload(); backups.reload(); }} type="button">刷新治理状态</button>}
      />

      <section className="stat-grid">
        <StatCard label="Manifest" value={manifestData.version} copy={`generated ${formatTimestamp(manifestData.generatedAt)}`} />
        <StatCard label="Assets" value={stats.totalAssets} copy="任务、运行、Prompt、记忆、资产、观测、日志和备份。" />
        <StatCard label="Executable" value={stats.executablePolicies} copy="当前仅 task 作用域进入硬删除首批闭环。" />
        <StatCard label="Backups" value={backupRows.length} copy="最近保护性快照。" />
        <StatCard label="Audit Events" value={operationRows.length} copy="最近数据治理操作记录。" />
      </section>

      <Surface>
        <p className="section-kicker">Deletion Dry-run</p>
        <h2 className="section-title">删除影响预览</h2>
        <div className="form-grid">
          <label className="form-field" htmlFor="governance-scope-kind">
            <span>Scope</span>
            <select className="field-input" id="governance-scope-kind" onChange={(event) => setScopeKind(event.target.value)} value={scopeKind}>
              <option value="task">task</option>
              <option value="asset">asset</option>
              <option value="node">node</option>
            </select>
          </label>
          <label className="form-field" htmlFor="governance-scope-id">
            <span>Scope ID</span>
            <input className="field-input" id="governance-scope-id" onChange={(event) => setScopeId(event.target.value)} value={scopeId} />
          </label>
          <label className="form-field" htmlFor="governance-reason">
            <span>Reason</span>
            <input className="field-input" id="governance-reason" onChange={(event) => setReason(event.target.value)} value={reason} />
          </label>
          <label className="form-field inline-check" htmlFor="governance-state-files">
            <input id="governance-state-files" checked={includeStateFiles} onChange={(event) => setIncludeStateFiles(event.target.checked)} type="checkbox" />
            <span>Include state files</span>
          </label>
        </div>
        <div className="button-row">
          <button className="action-button" disabled={isSubmitting || scopeId.trim().length === 0} onClick={() => void submitPlan()} type="button">
            生成预览
          </button>
        </div>
        {submitError ? <p className="error-copy">{submitError}</p> : null}
      </Surface>

      {plan ? <PlanPreview plan={plan} /> : null}

      {plan ? (
        <Surface>
          <div className="record-head">
            <div>
              <p className="section-kicker">Protected Execution</p>
              <h2 className="section-title">执行 task 硬删除</h2>
              <p className="section-copy">后端会在执行前重新生成 plan；运行中任务、asset 和 node 仍会被阻塞。</p>
            </div>
            <StatusBadge value={canExecuteDelete ? "ready" : "locked"} />
          </div>
          <div className="form-grid">
            <label className="form-field" htmlFor="governance-confirm-scope-id">
              <span>Confirm Scope ID</span>
              <input className="field-input" id="governance-confirm-scope-id" onChange={(event) => setConfirmScopeId(event.target.value)} value={confirmScopeId} />
            </label>
            <label className="form-field inline-check" htmlFor="governance-backup-before-delete">
              <input id="governance-backup-before-delete" checked={backupBeforeDelete} onChange={(event) => setBackupBeforeDelete(event.target.checked)} type="checkbox" />
              <span>先创建保护性备份</span>
            </label>
          </div>
          <div className="button-row">
            <button className="action-button" disabled={!canExecuteDelete || isExecutingDelete} onClick={() => void executeDelete()} type="button">
              {isExecutingDelete ? "执行中" : `删除 ${plan.scopeId}`}
            </button>
            <button className="ghost-button" disabled={isCreatingBackup} onClick={() => void createProtectiveBackup()} type="button">
              {isCreatingBackup ? "创建中" : "创建保护性备份"}
            </button>
          </div>
          {plan.scopeKind !== "task" ? <p className="meta-copy">当前作用域只允许预览；本阶段不执行 {plan.scopeKind} 硬删除。</p> : null}
          {planBlockers.length > 0 ? <p className="error-copy">存在 blocker 时不会创建删除前备份，也不会执行删除。</p> : null}
          {deleteError ? <p className="error-copy">{deleteError}</p> : null}
          {backupError ? <p className="error-copy">{backupError}</p> : null}
          {backupMessage ? <p className="meta-copy">{backupMessage}</p> : null}
        </Surface>
      ) : null}

      {deleteResult ? <DeletionResultSummary result={deleteResult} /> : null}

      <Surface>
        <div className="record-head">
          <div>
            <p className="section-kicker">Backups</p>
            <h2 className="section-title">保护性快照</h2>
            <p className="section-copy mono">{backups.data?.backupRoot ?? manifestData.backupRoot}</p>
          </div>
          <button className="ghost-button" disabled={isCreatingBackup} onClick={() => void createProtectiveBackup()} type="button">
            {isCreatingBackup ? "创建中" : "创建备份"}
          </button>
        </div>
        <div className="record-list">
          {backupRows.length === 0 ? (
            <p className="meta-copy">暂无保护性快照。</p>
          ) : (
            backupRows.map((backup) => (
              <article className="record-card" key={backup.snapshotDir}>
                <div className="record-head">
                  <div>
                    <h3 className="record-title">{backup.name}</h3>
                    <p className="meta-copy">{formatTimestamp(backup.createdAt ?? null)}</p>
                  </div>
                  <StatusBadge value={backup.databaseKind ?? "snapshot"} />
                </div>
                <p className="meta-copy mono">{backup.snapshotDir}</p>
              </article>
            ))
          )}
        </div>
      </Surface>

      <Surface>
        <p className="section-kicker">Manifest</p>
        <h2 className="section-title">数据资产清单</h2>
        <div className="record-list">
          {manifestData.assets.map((item) => (
            <article className="record-card" key={item.id}>
              <div className="record-head">
                <div>
                  <h3 className="record-title">{item.label}</h3>
                  <p className="meta-copy">sensitivity {item.sensitivity}</p>
                </div>
                <StatusBadge value={item.deletePolicy.includes("supported") ? "available" : "planned"} />
              </div>
              <p className="meta-copy">{item.deletePolicy}</p>
              <p className="code-block mono">{item.locations.join("\n")}</p>
            </article>
          ))}
        </div>
      </Surface>

      <div className="content-grid tight">
        <Surface>
          <p className="section-kicker">Paths</p>
          <h2 className="section-title">本地边界</h2>
          <div className="record-list">
            <div className="kv-item">
              <p className="meta-label">state root</p>
              <p className="meta-copy mono">{manifestData.stateRoot}</p>
            </div>
            <div className="kv-item">
              <p className="meta-label">product logs</p>
              <p className="meta-copy mono">{manifestData.productLogRoot}</p>
            </div>
            <div className="kv-item">
              <p className="meta-label">backups</p>
              <p className="meta-copy mono">{manifestData.backupRoot}</p>
            </div>
          </div>
        </Surface>

        <Surface>
          <p className="section-kicker">Remote Boundary</p>
          <h2 className="section-title">远端边界</h2>
          <p className="code-block mono">{jsonSnippet(manifestData.remoteBoundary)}</p>
        </Surface>
      </div>

      <Surface>
        <p className="section-kicker">Audit</p>
        <h2 className="section-title">最近治理操作</h2>
        <div className="record-list">
          {operationRows.length === 0 ? (
            <p className="meta-copy">暂无治理操作。</p>
          ) : (
            operationRows.map((operation) => (
              <article className="record-card" key={operation.id}>
                <div className="record-head">
                  <div>
                    <h3 className="record-title">{operation.operationType}</h3>
                    <p className="meta-copy">{operation.scopeKind} / {operation.scopeId ?? "-"}</p>
                  </div>
                  <StatusBadge value={operation.status} />
                </div>
                <div className="pill-row">
                  <span className="inline-chip">dryRun {String(operation.dryRun)}</span>
                  <span className="inline-chip">{formatTimestamp(operation.createdAt)}</span>
                </div>
                {operation.errorSummary ? <p className="error-copy">{operation.errorSummary}</p> : null}
              </article>
            ))
          )}
        </div>
      </Surface>
    </div>
  );
}
