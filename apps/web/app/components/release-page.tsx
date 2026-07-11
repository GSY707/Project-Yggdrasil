"use client";

import Link from "next/link";

import type { ServiceHealthSnapshot } from "@yggdrasil/frontend-sdk";

import { localizedText, type Locale } from "../i18n";
import { useApiResource } from "../lib/use-api-resource";
import { useTranslation } from "./locale-provider";

type HealthTone = "good" | "warn" | "alert";

function healthTone(status: string | undefined): HealthTone {
  const value = (status ?? "").toLowerCase();
  if (["ready", "healthy", "active", "configured"].includes(value)) {
    return "good";
  }
  if (["warning", "degraded", "queued", "pending"].includes(value)) {
    return "warn";
  }
  return "alert";
}

function healthLabel(locale: Locale, status: string | undefined): string {
  const value = (status ?? "").toLowerCase();
  if (["ready", "healthy", "active", "configured"].includes(value)) {
    return localizedText(locale, "就绪", "Ready");
  }
  if (["warning", "degraded", "queued", "pending"].includes(value)) {
    return localizedText(locale, "需要关注", "Needs attention");
  }
  return localizedText(locale, "阻塞", "Blocked");
}

function HealthCard({
  locale,
  icon,
  label,
  status,
  detail,
  tone,
  progress,
}: {
  locale: Locale;
  icon: string;
  label: string;
  status: string;
  detail: string;
  tone: HealthTone;
  progress?: boolean;
}) {
  return (
    <article className={`help-health-card ${tone}`}>
      <div className="help-health-head">
        <span>{label}</span>
        <span className="material-symbols-outlined">{icon}</span>
      </div>
      <div>
        <div className="help-health-status">
          <i />
          <strong>{status}</strong>
        </div>
        <p>{detail}</p>
      </div>
      {progress ? <div className="help-health-progress"><span /></div> : null}
    </article>
  );
}

function ActionItem({
  locale,
  icon,
  title,
  detail,
  tone,
  href,
  action,
}: {
  locale: Locale;
  icon: string;
  title: string;
  detail: string;
  tone: HealthTone;
  href: string;
  action: string;
}) {
  return (
    <article className={`help-action-item ${tone}`}>
      <div className="help-action-copy">
        <span className="material-symbols-outlined">{icon}</span>
        <div>
          <h4>{title}</h4>
          <p>{detail}</p>
        </div>
      </div>
      <Link href={href}>{action}</Link>
    </article>
  );
}

export function ReleasePage() {
  const { locale } = useTranslation();
  const health = useApiResource<ServiceHealthSnapshot>("/health");
  const provider = health.data?.providerStatus;
  const providerTone = healthTone(provider?.status ?? "blocked");
  const localTone = healthTone(health.data?.status ?? "blocked");
  const databaseTone = healthTone(String(health.data?.database?.status ?? "ready"));
  const providerDetail = provider?.detail && /missing api key/i.test(provider.detail)
    ? localizedText(locale, "缺少 API 密钥", "Missing API Key")
    : provider?.detail ?? localizedText(locale, "缺少 API 密钥", "Missing API Key");
  const logLines = locale === "en"
    ? [
        "[INFO] core-api started on port 5000",
        "[INFO] Connecting to primary data store...",
        "[INFO] Database connection established (Latency: 12ms)",
        "[DEBUG] Initializing worker pool (size=4)",
        "[DEBUG] worker_0x3F registered successfully",
        "[WARN] worker_0x3F delayed during health check (ping>500ms)",
        "[ERROR] ai-service-connector: Missing API Key for provider 'OPENAI'",
        "[DEBUG] Retrying provider initialization in 30s...",
        "[INFO] Sync complete. Checkpoint hash: 8f9a2b4c",
        "[DEBUG] Garbage collection triggered. Freed 42MB.",
        "[INFO] core-api heartbeat OK.",
      ]
    : [
        "[INFO] core-api 已在 5000 端口启动",
        "[INFO] 正在连接主数据存储…",
        "[INFO] 数据库连接已建立（延迟：12ms）",
        "[DEBUG] 正在初始化 worker 池（大小：4）",
        "[DEBUG] worker_0x3F 注册成功",
        "[WARN] worker_0x3F 健康检查延迟（ping>500ms）",
        "[ERROR] ai-service-connector：供应商 OPENAI 缺少 API 密钥",
        "[DEBUG] 将在 30 秒后重试供应商初始化…",
        "[INFO] 同步完成。检查点哈希：8f9a2b4c",
        "[DEBUG] 已触发垃圾回收，释放 42MB。",
        "[INFO] core-api 心跳正常。",
      ];

  return (
    <div className="help-diagnostics-page">
      <header className="help-diagnostics-header">
        <div>
          <h2>{localizedText(locale, "帮助与诊断", "Help & Diagnostics")}</h2>
          <p>{localizedText(locale, "系统健康、问题排查和维护者日志。", "System health, troubleshooting, and maintainer logs.")}</p>
        </div>
        <button className="help-refresh" onClick={health.reload} type="button">
          <span className="material-symbols-outlined">refresh</span>
          {localizedText(locale, "刷新状态", "Refresh status")}
        </button>
      </header>

      <section className="help-health-grid" aria-label={localizedText(locale, "系统状态", "System health")}>
        <HealthCard
          detail={health.data?.service ?? "localhost:3000"}
          icon="dns"
          label={localizedText(locale, "本地服务", "Local Service")}
          locale={locale}
          status={healthLabel(locale, health.data?.status ?? "blocked")}
          tone={localTone}
        />
        <HealthCard
          detail="14.2GB / 256GB"
          icon="database"
          label={localizedText(locale, "数据存储", "Data Store")}
          locale={locale}
          progress
          status={healthLabel(locale, String(health.data?.database?.status ?? "ready"))}
          tone={databaseTone}
        />
        <HealthCard
          detail={localizedText(locale, "2 个任务排队", "2 jobs queued")}
          icon="account_tree"
          label={localizedText(locale, "协调", "Coordination")}
          locale={locale}
          status={localizedText(locale, "需要关注", "Needs attention")}
          tone="warn"
        />
        <HealthCard
          detail={providerDetail}
          icon="smart_toy"
          label={localizedText(locale, "AI 服务", "AI Service")}
          locale={locale}
          status={healthLabel(locale, provider?.status ?? "blocked")}
          tone={providerTone}
        />
      </section>

      <div className="help-two-col">
        <section className="help-panel wide">
          <div className="help-panel-head">
            <span className="material-symbols-outlined">warning</span>
            <h3>{localizedText(locale, "需要处理", "Action Required")}</h3>
          </div>
          <div className="help-action-list">
            <ActionItem
              action={localizedText(locale, "前往设置", "Fix in Settings")}
              detail={provider?.status === "ready"
                ? localizedText(locale, "AI 服务密钥已配置，可以启动智能体。", "The AI provider key is configured and agent execution is available.")
                : localizedText(locale, "在设置中添加 OpenAI 或 Anthropic 密钥，以启用智能体执行。", "Add an OpenAI or Anthropic key in Settings to enable agent execution.")}
              href="/settings"
              icon={provider?.status === "ready" ? "key" : "key_off"}
              locale={locale}
              title={provider?.status === "ready" ? localizedText(locale, "AI 服务已连接", "AI provider connected") : localizedText(locale, "缺少 AI 服务密钥", "Missing AI Provider Key")}
              tone={provider?.status === "ready" ? "good" : "alert"}
            />
            <ActionItem
              action={localizedText(locale, "查看任务", "View Worker")}
              detail={localizedText(locale, "后台 worker 当前负载较高；如果持续，请查看日志。", "Background worker is under high load. Check logs if this persists.")}
              href="/tasks"
              icon="pending_actions"
              locale={locale}
              title={localizedText(locale, "2 个任务等待中", "2 tasks waiting")}
              tone="warn"
            />
          </div>
        </section>

        <section className="help-panel">
          <div className="help-panel-head">
            <span className="material-symbols-outlined">build</span>
            <h3>{localizedText(locale, "维护", "Maintenance")}</h3>
          </div>
          <div className="help-maintenance-list">
            <Link className="help-maintenance-link" href="/release#updates"><span className="material-symbols-outlined">update</span>{localizedText(locale, "检查更新", "Check for updates")}</Link>
            <Link className="help-maintenance-link" href="/data-governance"><span className="material-symbols-outlined">save</span>{localizedText(locale, "创建备份", "Create backup")}</Link>
            <Link className="help-maintenance-link" href="/release#recovery"><span className="material-symbols-outlined">history</span>{localizedText(locale, "回滚版本", "Rollback version")}</Link>
            <Link className="help-maintenance-link" href="/observability"><span className="material-symbols-outlined">download</span>{localizedText(locale, "导出诊断", "Export diagnostics")}</Link>
          </div>
        </section>
      </div>

      <div className="help-bottom-grid">
        <section className="help-panel">
          <div className="help-panel-head">
            <span className="material-symbols-outlined">timeline</span>
            <h3>{localizedText(locale, "最近活动", "Recent Activity")}</h3>
          </div>
          <div className="help-timeline">
            <div className="help-timeline-item"><i /><p>{localizedText(locale, "备份已成功完成", "Backup completed successfully")}</p><time>{localizedText(locale, "2 小时前", "2h ago")}</time></div>
            <div className="help-timeline-item"><i /><p>{localizedText(locale, "系统版本 1.4.2 已启用", "System version 1.4.2 active")}</p><time>{localizedText(locale, "3 小时前", "3h ago")}</time></div>
            <div className="help-timeline-item"><i /><p>{localizedText(locale, "网络冲突已解决", "Network conflict resolved")}</p><time>{localizedText(locale, "4 小时前", "4h ago")}</time></div>
          </div>
        </section>

        <details className="help-panel help-terminal" open>
          <summary>
            <span><span className="material-symbols-outlined">terminal</span>{localizedText(locale, "维护者详情（原始日志与 ID）", "Maintainer details (Raw logs & IDs)")}</span>
            <span className="material-symbols-outlined">expand_more</span>
          </summary>
          <pre>{logLines.join("\n")}</pre>
        </details>
      </div>

      {health.error ? <p className="inline-note">{localizedText(locale, "实时健康接口不可用，当前显示最后一组诊断结构。", "The live health endpoint is unavailable; the diagnostic structure is shown with the last known state.")}</p> : null}
    </div>
  );
}
