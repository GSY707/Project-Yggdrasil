"use client";

import Link from "next/link";
import { useState } from "react";

import type { ApplicationCatalogItem, ApplicationTaskTemplate } from "@yggdrasil/frontend-sdk";

import type { TranslationKey } from "../i18n";
import { localizeDashboard } from "../lib/localized-dashboard";
import { postApiJson, useApiResource } from "../lib/use-api-resource";
import { useTranslation } from "./locale-provider";
import { EmptyState, ErrorState, LoadingState, StatusBadge, Surface } from "./workbench-primitives";

type ApplicationsResponse = { activeAppId: string; applications: ApplicationCatalogItem[] };

const FEATURED_APPS = [
  {
    appId: "yggdrasil.app.deep-research",
    labelKey: "apps.deepResearch.label",
    icon: "travel_explore",
    purposeKey: "apps.deepResearch.purpose",
    needs: ["apps.deepResearch.need1", "apps.deepResearch.need2", "apps.deepResearch.need3"],
    reviewKey: "apps.deepResearch.review",
  },
  {
    appId: "yggdrasil.app.graduate-researcher",
    labelKey: "apps.graduateWriting.label",
    icon: "edit_document",
    purposeKey: "apps.graduateWriting.purpose",
    needs: ["apps.graduateWriting.need1", "apps.graduateWriting.need2", "apps.graduateWriting.need3"],
    reviewKey: "apps.graduateWriting.review",
  },
  {
    appId: "yggdrasil.app.coding-greenfield",
    labelKey: "apps.codingAssistant.label",
    icon: "code_blocks",
    purposeKey: "apps.codingAssistant.purpose",
    needs: ["apps.codingAssistant.need1", "apps.codingAssistant.need2", "apps.codingAssistant.need3"],
    reviewKey: "apps.codingAssistant.review",
  },
  {
    appId: "yggdrasil.app.knowledge-studio",
    labelKey: "apps.knowledgeBase.label",
    icon: "local_library",
    purposeKey: "apps.knowledgeBase.purpose",
    needs: ["apps.knowledgeBase.need1", "apps.knowledgeBase.need2", "apps.knowledgeBase.need3"],
    reviewKey: "apps.knowledgeBase.review",
  },
] as const;

function Icon({ children }: { children: string }) {
  return <span aria-hidden="true" className="material-symbols-outlined">{children}</span>;
}

function featuredItems(items: ApplicationCatalogItem[]) {
  const byId = new Map(items.map((item) => [item.application.appId, item]));
  const selected = FEATURED_APPS.map((meta) => {
    const item = byId.get(meta.appId);
    return item ? { meta, item } : null;
  }).filter(Boolean) as Array<{ meta: (typeof FEATURED_APPS)[number]; item: ApplicationCatalogItem }>;

  if (selected.length === 4) {
    return selected;
  }

  const usedIds = new Set(selected.map(({ item }) => item.application.appId));
  const fallback = items.filter((item) => !usedIds.has(item.application.appId)).slice(0, 4 - selected.length);
  return [
    ...selected,
    ...fallback.map((item) => ({
      item,
      meta: {
        appId: item.application.appId,
        label: item.application.displayName,
        icon: "apps",
        purposeKey: "apps.summary",
        needs: ["apps.needs", "apps.templates", "apps.settings"],
        reviewKey: "apps.reviewStatus",
      } as const,
    })),
  ];
}

export function ApplicationsPage() {
  const { locale, t } = useTranslation();
  const applications = useApiResource<ApplicationsResponse>("/applications");
  const [pendingAppId, setPendingAppId] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  async function handleActivate(appId: string) {
    setPendingAppId(appId);
    setActionError(null);
    try {
      await postApiJson(`/applications/${encodeURIComponent(appId)}/activate`);
      applications.reload();
    } catch (error) {
      setActionError(error instanceof Error ? error.message : String(error));
    } finally {
      setPendingAppId(null);
    }
  }

  if (applications.isLoading) {
    return <LoadingState title={t("loading.defaultTitle")} />;
  }

  if (applications.error) {
    return <ErrorState detail={applications.error} title={t("apps.errorTitle")} />;
  }

  const items = applications.data?.applications ?? [];
  if (items.length === 0) {
    return <EmptyState detail={t("apps.noneDetail")} title={t("apps.noneTitle")} />;
  }

  const featured = featuredItems(items);
  const featuredIds = new Set(featured.map(({ item }) => item.application.appId));
  const moreCount = items.filter((item) => !featuredIds.has(item.application.appId)).length;

  return (
    <div className="stitch-applications">
      <header className="stitch-applications-header">
        <div>
          <p className="section-kicker">{t("apps.eyebrow")}</p>
          <h2>{t("apps.title")}</h2>
          <p>{t("apps.summary")}</p>
        </div>
        <button className="ghost-button" onClick={() => applications.reload()} type="button">{t("apps.refresh")}</button>
      </header>

      {actionError ? <ErrorState detail={actionError} title={t("apps.actionErrorTitle")} /> : null}

      <section className="stitch-app-matrix" aria-label={t("apps.title")}>
        {featured.map(({ item, meta }) => {
          const manifest = item.application;
          const binding = item.configBinding;
          const dashboard = item.dashboard ? localizeDashboard(item.dashboard, locale) : undefined;
          const templates: ApplicationTaskTemplate[] = dashboard?.taskTemplates ?? [];
          const settings = dashboard?.settingsSchema?.slice(0, 2) ?? [];
          const settingRows: Array<{ key: string; label: string; defaultValue?: string | number | boolean | null }> = settings.length > 0
            ? settings
            : [
                { key: "provider", label: t("apps.settingAI"), defaultValue: null },
                { key: "model", label: t("apps.settingModel"), defaultValue: null },
              ];
          const isPending = pendingAppId === manifest.appId;
          return (
            <article className="stitch-app-card" key={manifest.appId}>
              <div className="stitch-app-card-content">
                <header className="stitch-app-card-heading">
                  <div>
                    <h3>{"labelKey" in meta ? t(meta.labelKey as TranslationKey) : meta.label}</h3>
                    <p>{t(meta.purposeKey)}</p>
                  </div>
                  <Icon>{meta.icon}</Icon>
                </header>

                <section className="stitch-app-card-section">
                  <h4>{t("apps.needs")}</h4>
                  <div className="stitch-app-needs">
                    {meta.needs.map((need) => (
                      <span key={need}><Icon>check_box</Icon>{t(need)}</span>
                    ))}
                  </div>
                </section>

                <section className="stitch-app-card-section">
                  <h4>{t("apps.templates")}</h4>
                  <div className="stitch-app-template-list">
                    {(templates.length > 0 ? templates.slice(0, 3) : [{ id: "default", title: t("apps.defaultTask") }]).map((template, index) => (
                      <Link
                        className={index === 0 ? "selected" : ""}
                        href={`/tasks?appId=${encodeURIComponent(manifest.appId)}`}
                        key={template.id}
                      >
                        {index === 0 ? <Icon>check</Icon> : null}
                        {template.title}
                      </Link>
                    ))}
                  </div>
                </section>

                <section className="stitch-app-card-section">
                  <h4>{t("apps.settings")}</h4>
                  <div className="stitch-app-settings">
                    {settingRows.map((setting) => (
                      <div key={setting.key}>
                        <span>{setting.label}</span>
                        <span>{setting.defaultValue ? String(setting.defaultValue) : "—"}</span>
                      </div>
                    ))}
                  </div>
                </section>
              </div>

              <footer className="stitch-app-card-footer">
                <div className="stitch-app-review-row">
                  <span>{t("apps.reviewStatus")}</span>
                  <StatusBadge value={binding.active ? "ready" : "available"} />
                </div>
                <p>{t(meta.reviewKey)}</p>
                <Link className="action-button" href={`/tasks?appId=${encodeURIComponent(manifest.appId)}`}>
                  {t("apps.start")} <Icon>arrow_forward</Icon>
                </Link>
                <div className="stitch-app-secondary-actions">
                  <Link href={`/applications/${encodeURIComponent(manifest.appId)}`}>{t("apps.details")}</Link>
                  <button disabled={binding.active || isPending} onClick={() => void handleActivate(manifest.appId)} type="button">
                    {binding.active ? t("apps.currentDefault") : isPending ? t("apps.switching") : t("apps.setDefault")}
                  </button>
                </div>
              </footer>
            </article>
          );
        })}
      </section>

      {moreCount > 0 ? (
        <Surface className="stitch-other-applications">
          <div>
            <p className="section-kicker">{t("apps.maintainer")}</p>
            <h3>{t("apps.moreTitle")}</h3>
            <p>{t("apps.moreSummary", { count: moreCount })}</p>
          </div>
          <Link className="ghost-button" href="/release">{t("apps.openDiagnostics")}</Link>
        </Surface>
      ) : null}
    </div>
  );
}
