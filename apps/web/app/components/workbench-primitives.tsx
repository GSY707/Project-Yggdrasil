import type { PropsWithChildren, ReactNode } from "react";

export function formatTimestamp(value: unknown): string {
  if (typeof value !== "string" || value.length === 0) {
    return "-";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

export function toneForStatus(status: string | null | undefined): "good" | "warn" | "alert" | "muted" {
  const normalized = (status ?? "").toLowerCase();
  if (["active", "completed", "healthy", "merged", "published", "approved", "open", "running"].includes(normalized)) {
    return "good";
  }
  if (["paused", "degraded", "queued", "draft", "pending", "publishing"].includes(normalized)) {
    return "warn";
  }
  if (["failed", "error", "dead-letter", "cancelled", "deleted", "unhealthy"].includes(normalized)) {
    return "alert";
  }
  return "muted";
}

export function StatusBadge({ value }: { value: string | null | undefined }) {
  return <span className={`status-badge ${toneForStatus(value)}`}>{value ?? "unknown"}</span>;
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

export function LoadingState({ title = "加载中" }: { title?: string }) {
  return (
    <div className="loading-state">
      <p className="section-kicker">Loading</p>
      <h3 className="section-title">{title}</h3>
      <div className="loading-grid">
        <div className="loading-card" />
        <div className="loading-card" />
        <div className="loading-card" />
      </div>
    </div>
  );
}

export function ErrorState({ title = "加载失败", detail }: { title?: string; detail: string }) {
  return (
    <div className="error-state">
      <p className="section-kicker">Error</p>
      <h3 className="section-title">{title}</h3>
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