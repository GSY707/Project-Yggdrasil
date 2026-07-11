"use client";

import Link from "next/link";

import type { WorkbenchOverview } from "@yggdrasil/frontend-sdk";

import { useApiResource } from "../lib/use-api-resource";
import { useTranslation } from "./locale-provider";
import { EmptyState, ErrorState, LoadingState, StatusBadge, Surface, useLocalizedTimestamp } from "./workbench-primitives";

type ApplicationsResponse = { activeAppId: string; applications: Array<{ application: { appId: string } }> };

function Icon({ children }: { children: string }) {
  return <span aria-hidden="true" className="material-symbols-outlined">{children}</span>;
}

export function OverviewPage() {
  const { t } = useTranslation();
  const formatTimestamp = useLocalizedTimestamp();
  const overview = useApiResource<WorkbenchOverview>("/workbench/overview");
  const applications = useApiResource<ApplicationsResponse>("/applications");

  if (overview.isLoading || applications.isLoading) {
    return <LoadingState title={t("loading.defaultTitle")} />;
  }

  if (overview.error) {
    return <ErrorState detail={overview.error} title={t("error.defaultTitle")} />;
  }

  if (!overview.data) {
    return <ErrorState detail={t("home.reviewCopy")} title={t("error.defaultTitle")} />;
  }

  const setupItems = overview.data.health.setupChecklist ?? [];
  const blocked = setupItems.filter((item) => item.status === "blocked").length;
  const currentDraft = overview.data.recentTasks.find((task) => task.status === "draft");
  const recentTasks = overview.data.recentTasks.slice(0, 3);
  const providerStatus = overview.data.health.providerStatus?.status ?? "unavailable";
  const taskCount = Object.values(overview.data.taskStatusCounts).reduce((total, count) => total + count, 0);

  return (
    <div className="stitch-home">
      <header className="stitch-page-title">
        <h2>{t("home.title")}</h2>
      </header>

      <section className="stitch-home-grid" aria-label={t("home.title")}>
        <Surface className="stitch-home-primary">
          <div className="stitch-home-primary-copy">
            <h3>{t("home.readyTitle")}</h3>
            <p>{t("home.readyCopy")}</p>
          </div>
          <Link className="action-button" href="/tasks">
            <Icon>play_arrow</Icon>
            {t("home.startTask")}
          </Link>
        </Surface>

        <Surface className="stitch-materials-panel">
          <Icon>note_add</Icon>
          <p>{t("home.materialsEmpty")}</p>
          <Link className="ghost-button" href="/assets">{t("home.addFiles")}</Link>
        </Surface>

        <Surface className="stitch-draft-panel">
          <div className="stitch-panel-heading">
            <Icon>edit_document</Icon>
            <h3>{t("home.currentDraft")}</h3>
          </div>
          {currentDraft ? (
            <Link className="stitch-draft-value" href={`/tasks/${encodeURIComponent(currentDraft.id)}`}>
              {currentDraft.title}
            </Link>
          ) : (
            <p className="stitch-draft-value muted">{t("home.noDraft")}</p>
          )}
        </Surface>

        <Surface className="stitch-local-panel">
          <span className="stitch-icon-block"><Icon>lock</Icon></span>
          <p>{t("home.localOnly")}</p>
        </Surface>

        <Surface className="stitch-help-panel">
          <div className="stitch-panel-heading">
            <Icon>lightbulb</Icon>
            <h3>{t("home.help")}</h3>
          </div>
          <div className="stitch-help-links">
            <Link href="/applications"><Icon>arrow_right</Icon>{t("home.helpResearch")}</Link>
            <Link href="/assets"><Icon>arrow_right</Icon>{t("home.helpMaterials")}</Link>
            <Link href="/tasks"><Icon>arrow_right</Icon>{t("home.helpGoal")}</Link>
          </div>
        </Surface>

        <Surface className="stitch-constraints-panel">
          <div className="stitch-panel-heading">
            <Icon>schedule</Icon>
            <h3>{t("home.constraints")}</h3>
          </div>
          <dl>
            <div><dt>{t("home.spendingCap")}</dt><dd>{t("home.notSet")}</dd></div>
            <div><dt>{t("home.estimatedTime")}</dt><dd>{t("home.draftFirst")}</dd></div>
          </dl>
          <Link className="ghost-button" href="/tasks"><Icon>assignment</Icon>{t("home.startTask")}</Link>
        </Surface>

        <Surface className="stitch-review-panel">
          <div className="stitch-panel-heading">
            <Icon>warning</Icon>
            <h3>{t("home.review")}</h3>
          </div>
          <p>{t("home.reviewCopy")}</p>
          <Link className="ghost-button" href={blocked > 0 ? "/settings" : "/release"}>{t("home.reviewNow")}</Link>
        </Surface>
      </section>

      <section className="stitch-home-status-row" aria-label={t("home.review")}>
        <Surface>
          <div className="stitch-panel-heading"><Icon>neurology</Icon><h3>{t("settings.aiService")}</h3></div>
          <StatusBadge value={providerStatus} />
        </Surface>
        <Surface>
          <div className="stitch-panel-heading"><Icon>assignment</Icon><h3>{t("home.recentTasks")}</h3></div>
          <p className="stitch-status-value">{taskCount}</p>
        </Surface>
        <Surface>
          <div className="stitch-panel-heading"><Icon>error</Icon><h3>{t("home.review")}</h3></div>
          <p className="stitch-status-value">{blocked}</p>
        </Surface>
      </section>

      <section className="stitch-recent-tasks">
        <div className="stitch-section-title-row">
          <div>
            <p className="section-kicker">{t("home.recentTasks")}</p>
            <h3>{t("home.continue")}</h3>
          </div>
          <Link className="ghost-button" href="/tasks">{t("home.openTasks")}</Link>
        </div>
        {recentTasks.length === 0 ? (
          <EmptyState detail={t("home.noTasks")} title={t("home.noDraft")} />
        ) : (
          <div className="stitch-recent-list">
            {recentTasks.map((task) => (
              <Link className="stitch-recent-item" href={`/tasks/${encodeURIComponent(task.id)}`} key={task.id}>
                <div>
                  <strong>{task.title}</strong>
                  <span>{formatTimestamp(task.updatedAt ?? task.createdAt)}</span>
                </div>
                <StatusBadge value={task.status} />
              </Link>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
