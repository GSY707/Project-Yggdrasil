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
import { localizedText } from "../i18n";
import { ErrorState, LoadingState, PageHeader, StatCard, StatusBadge, Surface, formatTimestamp } from "./workbench-primitives";
import { useLocale } from "./locale-provider";

function jsonSnippet(value: unknown): string {
  return JSON.stringify(value ?? {}, null, 2);
}

function unknownRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" ? (value as Record<string, unknown>) : {};
}

function PlanPreview({ plan }: { plan: DataGovernanceDeletionPlan }) {
  const { locale } = useLocale();
  const l = (zhCN: string, english: string) => localizedText(locale, zhCN, english);
  const tableRows = plan.database?.tables ?? [];
  return (
    <Surface>
      <div className="record-head">
        <div>
          <p className="section-kicker">{localizedText(locale, "删除预览", "Deletion preview")}</p>
          <h2 className="section-title">{plan.scopeKind} / {plan.scopeId}</h2>
          <p className="section-copy">{localizedText(locale, "目标", "target")} {String(plan.target?.title ?? plan.target?.mediaType ?? plan.target?.nodeType ?? "-")}</p>
        </div>
        <StatusBadge value={plan.blockers && plan.blockers.length > 0 ? "blocked" : "preview"} />
      </div>
      <section className="stat-grid compact">
        <StatCard label={l("数据库记录", "DB rows")} value={plan.database?.totalRows ?? tableRows.reduce((sum, row) => sum + row.count, 0)} copy={localizedText(locale, "预览会影响的数据库记录数。", "Database records affected by this preview.")} />
        <StatCard label={l("状态文件", "State files")} value={plan.stateFileCount ?? 0} copy={`${plan.stateFileBytes ?? 0} bytes`} />
        <StatCard label={l("阻塞项", "Blockers")} value={plan.blockers?.length ?? 0} copy={localizedText(locale, "阻塞项为 0 才允许后端确认执行。", "Execution requires zero blockers.")} />
        <StatCard label={l("警告", "Warnings")} value={plan.warnings?.length ?? 0} copy={localizedText(locale, "保留边界和外部系统提示。", "Retention and external-system warnings.")} />
      </section>
      {plan.blockers && plan.blockers.length > 0 ? (
        <div className="record-list">
          {plan.blockers.map((item) => (
            <article className="compact-record" key={item}>
              <p className="meta-label">{localizedText(locale, "阻塞项", "Blocker")}</p>
              <p className="meta-copy">{item}</p>
            </article>
          ))}
        </div>
      ) : null}
      <div className="content-grid tight">
        <article className="record-card">
          <h3 className="record-title">{localizedText(locale, "数据库计划", "Database plan")}</h3>
          <div className="record-list">
            {tableRows.map((row) => (
              <div className="kv-item" key={row.table}>
                <div className="record-head">
                  <p className="meta-label">{row.table}</p>
                  <span className="inline-chip">{row.action}</span>
                </div>
                <p className="meta-copy">{row.count} {l("条记录", "rows")}</p>
                {row.sampleIds.length > 0 ? <p className="code-block mono">{row.sampleIds.slice(0, 6).join("\n")}</p> : null}
              </div>
            ))}
          </div>
        </article>
        <article className="record-card">
          <h3 className="record-title">{localizedText(locale, "保留边界", "Retained boundary")}</h3>
          <div className="record-list">
            {(plan.retainedData ?? []).map((item, index) => (
              <div className="kv-item" key={`${String(item.location ?? "retained")}-${index}`}>
                <p className="meta-label">{item.reason === "retained" ? l("保留", "Retained") : String(item.reason ?? l("保留", "Retained"))}</p>
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
  const { locale } = useLocale();
  const l = (zhCN: string, english: string) => localizedText(locale, zhCN, english);
  const certificate = result.deletionCertificate;
  return (
    <Surface>
      <div className="record-head">
        <div>
          <p className="section-kicker">{localizedText(locale, "删除证明", "Deletion certificate")}</p>
          <h2 className="section-title">{certificate ? certificate.id : result.status}</h2>
          <p className="section-copy">{localizedText(locale, "删除执行结果与保留边界摘要会进入审计记录。", "The deletion result and retained-boundary summary are written to the audit record.")}</p>
        </div>
        <StatusBadge value={result.status} />
      </div>
      {certificate ? (
        <section className="stat-grid compact">
          <StatCard label={l("已删除记录", "Deleted rows")} value={certificate.deletedRows} copy={localizedText(locale, "数据库删除证明计数。", "Database deletion certificate count.")} />
          <StatCard label={l("已删除状态文件", "State files deleted")} value={certificate.stateFiles.deleted} copy={`${certificate.stateFiles.requested} ${l("项请求", "requested")}`} />
          <StatCard label={l("失败状态文件", "State files failed")} value={certificate.stateFiles.failed} copy={localizedText(locale, "失败项需要人工处理。", "Failed items require manual handling.")} />
          <StatCard label={l("备份", "Backup")} value={certificate.backupSnapshotDir ? "ready" : "skipped"} copy={certificate.backupSnapshotDir ?? localizedText(locale, "本次未创建保护性备份。", "No protective backup was created.")} />
        </section>
      ) : null}
      <p className="code-block mono">{jsonSnippet(certificate ?? result)}</p>
    </Surface>
  );
}

export function DataGovernancePage() {
  const { locale } = useLocale();
  const l = (zhCN: string, english: string) => localizedText(locale, zhCN, english);
  const manifest = useApiResource<DataGovernanceManifest>("/data-governance/manifest");
  const operations = useApiResource<DataGovernanceOperationsResponse>("/data-governance/operations?limit=20");
  const backups = useApiResource<DataGovernanceBackupsResponse>("/data-governance/backups?limit=8");
  const [scopeKind, setScopeKind] = useState("task");
  const [scopeId, setScopeId] = useState("");
  const [reason, setReason] = useState(() => l("本地数据治理操作", "Local data governance operation"));
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
      setBackupMessage(`${localizedText(locale, "已创建保护性备份", "Protective backup created")}: ${String(backup.snapshotDir ?? backup.name ?? "snapshot")}`);
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
    return <LoadingState title={localizedText(locale, "正在读取数据治理边界", "Loading data governance boundary")} />;
  }

  if (error || !manifestData || !Array.isArray(manifestData.assets)) {
    return <ErrorState detail={error ?? localizedText(locale, "数据治理清单不可用。", "Data governance manifest is unavailable.")} />;
  }

  return (
    <div>
      <PageHeader
        eyebrow={localizedText(locale, "数据治理", "Data governance")}
        title={localizedText(locale, "本地数据资产、保护性备份、删除证明与审计", "Local data assets, backups, deletion certificates, and audit")}
        summary={<>{localizedText(locale, "统一展示本地数据位置、远端边界、删除影响预览、保护性备份和最近治理操作。task 硬删除需要无阻塞 plan 与精确确认。", "Review local data paths, remote boundaries, deletion previews, protective backups, and recent operations. Task hard-delete requires a blocker-free plan and exact confirmation.")}</>}
        actions={<button className="ghost-button" onClick={() => { manifest.reload(); operations.reload(); backups.reload(); }} type="button">{localizedText(locale, "刷新治理状态", "Refresh governance")}</button>}
      />

      <section className="stat-grid">
        <StatCard label={l("清单", "Manifest")} value={manifestData.version} copy={`${l("生成于", "Generated")} ${formatTimestamp(manifestData.generatedAt, locale)}`} />
        <StatCard label={l("资产", "Assets")} value={stats.totalAssets} copy={localizedText(locale, "任务、运行、Prompt、记忆、资产、观测、日志和备份。", "Tasks, runs, prompts, memory, assets, observability, logs, and backups.")} />
        <StatCard label={l("可执行策略", "Executable")} value={stats.executablePolicies} copy={localizedText(locale, "当前仅 task 作用域进入硬删除首批闭环。", "Only task scope is in the first hard-delete closure.")} />
        <StatCard label={l("备份", "Backups")} value={backupRows.length} copy={localizedText(locale, "最近保护性快照。", "Recent protective snapshots.")} />
        <StatCard label={l("审计事件", "Audit events")} value={operationRows.length} copy={localizedText(locale, "最近数据治理操作记录。", "Recent governance operations.")} />
      </section>

      <Surface>
        <p className="section-kicker">{l("删除预演", "Deletion dry-run")}</p>
        <h2 className="section-title">{localizedText(locale, "删除影响预览", "Deletion impact preview")}</h2>
        <div className="form-grid">
          <label className="form-field" htmlFor="governance-scope-kind">
            <span>{l("范围", "Scope")}</span>
            <select className="field-input" id="governance-scope-kind" onChange={(event) => setScopeKind(event.target.value)} value={scopeKind}>
              <option value="task">{l("任务", "Task")}</option>
              <option value="asset">{l("素材", "Asset")}</option>
              <option value="node">{l("节点", "Node")}</option>
            </select>
          </label>
          <label className="form-field" htmlFor="governance-scope-id">
            <span>{l("范围 ID", "Scope ID")}</span>
            <input className="field-input" id="governance-scope-id" onChange={(event) => setScopeId(event.target.value)} value={scopeId} />
          </label>
          <label className="form-field" htmlFor="governance-reason">
            <span>{l("原因", "Reason")}</span>
            <input className="field-input" id="governance-reason" onChange={(event) => setReason(event.target.value)} value={reason} />
          </label>
          <label className="form-field inline-check" htmlFor="governance-state-files">
            <input id="governance-state-files" checked={includeStateFiles} onChange={(event) => setIncludeStateFiles(event.target.checked)} type="checkbox" />
            <span>{l("包括状态文件", "Include state files")}</span>
          </label>
        </div>
        <div className="button-row">
          <button className="action-button" disabled={isSubmitting || scopeId.trim().length === 0} onClick={() => void submitPlan()} type="button">
            {localizedText(locale, "生成预览", "Generate preview")}
          </button>
        </div>
        {submitError ? <p className="error-copy">{submitError}</p> : null}
      </Surface>

      {plan ? <PlanPreview plan={plan} /> : null}

      {plan ? (
        <Surface>
          <div className="record-head">
            <div>
              <p className="section-kicker">{l("受保护执行", "Protected execution")}</p>
              <h2 className="section-title">{localizedText(locale, "执行 task 硬删除", "Execute task hard-delete")}</h2>
              <p className="section-copy">{localizedText(locale, "后端会在执行前重新生成 plan；运行中任务、asset 和 node 仍会被阻塞。", "The backend regenerates the plan before execution; running tasks, assets, and nodes remain blocked.")}</p>
            </div>
            <StatusBadge value={canExecuteDelete ? "ready" : "locked"} />
          </div>
          <div className="form-grid">
            <label className="form-field" htmlFor="governance-confirm-scope-id">
              <span>{l("确认范围 ID", "Confirm scope ID")}</span>
              <input className="field-input" id="governance-confirm-scope-id" onChange={(event) => setConfirmScopeId(event.target.value)} value={confirmScopeId} />
            </label>
            <label className="form-field inline-check" htmlFor="governance-backup-before-delete">
              <input id="governance-backup-before-delete" checked={backupBeforeDelete} onChange={(event) => setBackupBeforeDelete(event.target.checked)} type="checkbox" />
              <span>{localizedText(locale, "先创建保护性备份", "Create a protective backup first")}</span>
            </label>
          </div>
          <div className="button-row">
            <button className="action-button" disabled={!canExecuteDelete || isExecutingDelete} onClick={() => void executeDelete()} type="button">
              {isExecutingDelete ? localizedText(locale, "执行中", "Executing") : `${localizedText(locale, "删除", "Delete")} ${plan.scopeId}`}
            </button>
            <button className="ghost-button" disabled={isCreatingBackup} onClick={() => void createProtectiveBackup()} type="button">
              {isCreatingBackup ? localizedText(locale, "创建中", "Creating") : localizedText(locale, "创建保护性备份", "Create protective backup")}
            </button>
          </div>
          {plan.scopeKind !== "task" ? <p className="meta-copy">{localizedText(locale, "当前作用域只允许预览；本阶段不执行", "This scope is preview-only; this stage does not execute")} {plan.scopeKind} {localizedText(locale, "硬删除。", "hard-delete.")}</p> : null}
          {planBlockers.length > 0 ? <p className="error-copy">{localizedText(locale, "存在 blocker 时不会创建删除前备份，也不会执行删除。", "A pre-delete backup and deletion are blocked while blockers exist.")}</p> : null}
          {deleteError ? <p className="error-copy">{deleteError}</p> : null}
          {backupError ? <p className="error-copy">{backupError}</p> : null}
          {backupMessage ? <p className="meta-copy">{backupMessage}</p> : null}
        </Surface>
      ) : null}

      {deleteResult ? <DeletionResultSummary result={deleteResult} /> : null}

      <Surface>
        <div className="record-head">
          <div>
            <p className="section-kicker">{l("备份", "Backups")}</p>
            <h2 className="section-title">{l("保护性快照", "Protective snapshots")}</h2>
            <p className="section-copy mono">{backups.data?.backupRoot ?? manifestData.backupRoot}</p>
          </div>
          <button className="ghost-button" disabled={isCreatingBackup} onClick={() => void createProtectiveBackup()} type="button">
            {isCreatingBackup ? localizedText(locale, "创建中", "Creating") : localizedText(locale, "创建备份", "Create backup")}
          </button>
        </div>
        <div className="record-list">
          {backupRows.length === 0 ? (
            <p className="meta-copy">{localizedText(locale, "暂无保护性快照。", "No protective snapshots.")}</p>
          ) : (
            backupRows.map((backup) => (
              <article className="record-card" key={backup.snapshotDir}>
                <div className="record-head">
                  <div>
                    <h3 className="record-title">{backup.name}</h3>
                    <p className="meta-copy">{formatTimestamp(backup.createdAt ?? null, locale)}</p>
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
        <p className="section-kicker">{l("清单", "Manifest")}</p>
        <h2 className="section-title">{localizedText(locale, "数据资产清单", "Data asset manifest")}</h2>
        <div className="record-list">
          {manifestData.assets.map((item) => (
            <article className="record-card" key={item.id}>
              <div className="record-head">
                <div>
                  <h3 className="record-title">{item.label}</h3>
                  <p className="meta-copy">{l("敏感级别", "Sensitivity")} {item.sensitivity}</p>
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
          <p className="section-kicker">{l("路径", "Paths")}</p>
        <h2 className="section-title">{localizedText(locale, "本地边界", "Local boundary")}</h2>
          <div className="record-list">
            <div className="kv-item">
              <p className="meta-label">{l("状态根", "State root")}</p>
              <p className="meta-copy mono">{manifestData.stateRoot}</p>
            </div>
            <div className="kv-item">
              <p className="meta-label">{l("产品日志", "Product logs")}</p>
              <p className="meta-copy mono">{manifestData.productLogRoot}</p>
            </div>
            <div className="kv-item">
              <p className="meta-label">{l("备份", "Backups")}</p>
              <p className="meta-copy mono">{manifestData.backupRoot}</p>
            </div>
          </div>
        </Surface>

        <Surface>
          <p className="section-kicker">{l("远端边界", "Remote boundary")}</p>
        <h2 className="section-title">{localizedText(locale, "远端边界", "Remote boundary")}</h2>
          <p className="code-block mono">{jsonSnippet(manifestData.remoteBoundary)}</p>
        </Surface>
      </div>

      <Surface>
        <p className="section-kicker">{l("审计", "Audit")}</p>
        <h2 className="section-title">{localizedText(locale, "最近治理操作", "Recent governance operations")}</h2>
        <div className="record-list">
          {operationRows.length === 0 ? (
            <p className="meta-copy">{localizedText(locale, "暂无治理操作。", "No governance operations.")}</p>
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
                  <span className="inline-chip">{l("预演", "Dry run")} {String(operation.dryRun)}</span>
                  <span className="inline-chip">{formatTimestamp(operation.createdAt, locale)}</span>
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
