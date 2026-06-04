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
  if (["active", "available", "completed", "healthy", "merged", "published", "approved", "open", "ready", "running"].includes(normalized)) {
    return "good";
  }
  if (["paused", "degraded", "planned", "queued", "draft", "pending", "publishing", "warning"].includes(normalized)) {
    return "warn";
  }
  if (["failed", "error", "dead-letter", "blocked", "cancelled", "deleted", "unavailable", "unhealthy"].includes(normalized)) {
    return "alert";
  }
  return "muted";
}

function displayStatus(status: string | null | undefined): string {
  const normalized = (status ?? "").toLowerCase();
  const labels: Record<string, string> = {
    active: "已启用",
    approved: "已批准",
    available: "可用",
    blocked: "阻塞",
    cancelled: "已取消",
    completed: "已完成",
    default: "默认加载",
    deleted: "已删除",
    "dead-letter": "异常待处理",
    degraded: "需要关注",
    draft: "草稿",
    error: "错误",
    failed: "失败",
    "file-ready": "文件已读取",
    healthy: "正常",
    idle: "待导入",
    inactive: "未启用",
    importing: "导入中",
    derived: "派生",
    merged: "已合并",
    open: "待处理",
    original: "原始",
    paused: "已暂停",
    preview: "预览",
    pending: "等待中",
    planned: "计划中",
    published: "已发布",
    publishing: "发布中",
    queued: "排队中",
    ready: "就绪",
    running: "运行中",
    unavailable: "暂不可用",
    unhealthy: "异常",
    warning: "需注意",
  };
  return labels[normalized] ?? status ?? "未知";
}

export function StatusBadge({ value }: { value: string | null | undefined }) {
  return <span className={`status-badge ${toneForStatus(value)}`}>{displayStatus(value)}</span>;
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
      <p className="section-kicker">加载</p>
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
      <p className="section-kicker">错误</p>
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
