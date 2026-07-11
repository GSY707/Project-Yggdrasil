"use client";

import { useCallback } from "react";
import type { PropsWithChildren, ReactNode } from "react";

import { DEFAULT_LOCALE, type Locale, type TranslationKey } from "../i18n";
import { useLocale, useTranslation } from "./locale-provider";

export function formatTimestamp(value: unknown, locale: Locale = DEFAULT_LOCALE): string {
  if (typeof value !== "string" || value.length === 0) {
    return "-";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat(locale, {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

export function toneForStatus(status: string | null | undefined): "good" | "warn" | "alert" | "muted" {
  const normalized = (status ?? "").toLowerCase();
  if (["active", "allow", "available", "completed", "created", "enabled", "executed", "flushed", "handled", "healthy", "materialized", "merged", "passed", "prepared", "published", "approved", "open", "present", "promoted", "ready", "resolved", "restorable", "running", "success", "validated", "verified", "delivered", "accepted", "acknowledged", "closed"].includes(normalized)) {
    return "good";
  }
  if (["paused", "degraded", "planned", "queued", "draft", "pending", "pending-sync", "publishing", "committing", "in-progress", "leased", "restoring", "recovering", "summarizing", "warning", "info", "snapshot", "consumed", "cancelling", "draining", "executing", "initializing", "materializing", "mounting", "needs-clarification", "pausing", "pre-reading", "preprocessing", "proposed", "reclaimable", "restart-requested", "restarting", "standby", "suspended", "temporary", "waiting-tool", "fallback"].includes(normalized)) {
    return "warn";
  }
  if (["failed", "error", "dead-letter", "blocked", "cancelled", "deleted", "deny", "disabled", "copied-disabled", "invalid", "locked", "missing", "not-applicable", "not-run", "skipped", "superseded", "archived", "aborted", "deprecated", "detached", "expired", "quarantined", "rejected", "resume-blocked", "retired", "unavailable", "unhealthy"].includes(normalized)) {
    return "alert";
  }
  return "muted";
}

const STATUS_LABEL_KEYS: Record<string, TranslationKey> = {
  active: "status.active",
  allow: "status.allow",
  aborted: "status.aborted",
  accepted: "status.accepted",
  acknowledged: "status.acknowledged",
  archived: "status.archived",
  "awaiting-approval": "status.awaiting-approval",
  approved: "status.approved",
  available: "status.available",
  blocked: "status.blocked",
  cancelled: "status.cancelled",
  cancelling: "status.cancelling",
  closed: "status.closed",
  committing: "status.committing",
  completed: "status.completed",
  consumed: "status.consumed",
  "copied-disabled": "status.copied-disabled",
  created: "status.created",
  disabled: "status.disabled",
  default: "status.default",
  deleted: "status.deleted",
  "dead-letter": "status.dead-letter",
  degraded: "status.degraded",
  delivered: "status.delivered",
  deprecated: "status.deprecated",
  detached: "status.detached",
  deny: "status.deny",
  draft: "status.draft",
  error: "status.error",
  enabled: "status.enabled",
  draining: "status.draining",
  executed: "status.executed",
  executing: "status.executing",
  expired: "status.expired",
  fallback: "status.fallback",
  failed: "status.failed",
  "file-ready": "status.file-ready",
  flushed: "status.flushed",
  healthy: "status.healthy",
  handled: "status.handled",
  idle: "status.idle",
  "in-progress": "status.in-progress",
  inactive: "status.inactive",
  importing: "status.importing",
  initializing: "status.initializing",
  invalid: "status.invalid",
  leased: "status.leased",
  locked: "status.locked",
  missing: "status.missing",
  materialized: "status.materialized",
  materializing: "status.materializing",
  mounting: "status.mounting",
  derived: "status.derived",
  merged: "status.merged",
  "not-applicable": "status.not-applicable",
  "not-run": "status.not-run",
  "needs-clarification": "status.needs-clarification",
  open: "status.open",
  original: "status.original",
  paused: "status.paused",
  pausing: "status.pausing",
  "pending-sync": "status.pending-sync",
  preview: "status.preview",
  pending: "status.pending",
  planned: "status.planned",
  passed: "status.passed",
  "pre-reading": "status.pre-reading",
  prepared: "status.prepared",
  preprocessing: "status.preprocessing",
  present: "status.present",
  promoted: "status.promoted",
  proposed: "status.proposed",
  published: "status.published",
  publishing: "status.publishing",
  quarantined: "status.quarantined",
  reclaimable: "status.reclaimable",
  queued: "status.queued",
  ready: "status.ready",
  restorable: "status.restorable",
  restoring: "status.restoring",
  recovering: "status.recovering",
  rejected: "status.rejected",
  resolved: "status.resolved",
  "restart-requested": "status.restart-requested",
  restarting: "status.restarting",
  "resume-blocked": "status.resume-blocked",
  retired: "status.retired",
  running: "status.running",
  skipped: "status.skipped",
  staged: "status.staged",
  standby: "status.standby",
  snapshot: "status.snapshot",
  superseded: "status.superseded",
  summarizing: "status.summarizing",
  success: "status.success",
  suspended: "status.suspended",
  temporary: "status.temporary",
  "unknown-tool": "status.unknown-tool",
  unknown: "status.unknown",
  unavailable: "status.unavailable",
  unhealthy: "status.unhealthy",
  validated: "status.validated",
  verified: "status.verified",
  warning: "status.warning",
  "waiting-tool": "status.waiting-tool",
  info: "status.info",
};

export function StatusBadge({ value }: { value: string | null | undefined }) {
  const { t } = useTranslation();
  return <span className={`status-badge ${toneForStatus(value)}`}>{statusLabel(value, t)}</span>;
}

export function statusLabel(value: string | null | undefined, translate: (key: TranslationKey) => string): string {
  const normalized = (value ?? "").toLowerCase();
  const labelKey = STATUS_LABEL_KEYS[normalized];
  return labelKey ? translate(labelKey) : normalized.length > 0 ? value ?? translate("status.unknown") : translate("status.unknown");
}

export function useLocalizedTimestamp() {
  const { locale } = useLocale();
  return useCallback((value: unknown) => formatTimestamp(value, locale), [locale]);
}

export function PageHeader({
  eyebrow,
  title,
  summary,
  actions,
}: {
  eyebrow: string;
  title: string;
  summary: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <header className="page-header">
      <div>
        <p className="page-eyebrow">{eyebrow}</p>
        <h2 className="page-title">{title}</h2>
        <div className="page-summary">{summary}</div>
      </div>
      {actions ? <div className="page-actions">{actions}</div> : null}
    </header>
  );
}

export function Surface({ children, className = "" }: PropsWithChildren<{ className?: string }>) {
  return <section className={`surface${className ? ` ${className}` : ""}`}>{children}</section>;
}

export function StatCard({ label, value, copy }: { label: string; value: ReactNode; copy: ReactNode }) {
  return (
    <article className="stat-card">
      <p className="stat-label">{label}</p>
      <p className="stat-value">{value}</p>
      <p className="stat-copy">{copy}</p>
    </article>
  );
}

export function LoadingState({ title }: { title?: string }) {
  const { t } = useTranslation();
  return (
    <div className="loading-state">
      <p className="section-kicker">{t("loading.section")}</p>
      <h3 className="section-title">{title ?? t("loading.defaultTitle")}</h3>
      <div className="loading-grid">
        <div className="loading-card" />
        <div className="loading-card" />
        <div className="loading-card" />
      </div>
    </div>
  );
}

export function ErrorState({ title, detail }: { title?: string; detail: string }) {
  const { t } = useTranslation();
  return (
    <div className="error-state">
      <p className="section-kicker">{t("error.section")}</p>
      <h3 className="section-title">{title ?? t("error.defaultTitle")}</h3>
      <p className="error-copy">{detail}</p>
    </div>
  );
}

export function EmptyState({ title, detail }: { title: string; detail: string }) {
  return (
    <div className="empty-state">
      <h3 className="subsection-title">{title}</h3>
      <p className="empty-copy">{detail}</p>
    </div>
  );
}
