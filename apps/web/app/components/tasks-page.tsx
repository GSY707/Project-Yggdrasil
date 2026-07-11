"use client";

import Link from "next/link";
import { useDeferredValue, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";

import type { ApplicationCatalogItem, TaskLaunchAttachment, TaskSummaryRecord } from "@yggdrasil/frontend-sdk";

import { useApiResource } from "../lib/use-api-resource";
import { TaskLaunchPanel } from "./task-launch-panel";
import { useTranslation } from "./locale-provider";
import { EmptyState, ErrorState, LoadingState, PageHeader, StatusBadge, Surface, formatTimestamp, statusLabel } from "./workbench-primitives";

type TasksResponse = {
  tasks: TaskSummaryRecord[];
};

type ApplicationsResponse = {
  activeAppId: string;
  applications: ApplicationCatalogItem[];
};

export function TasksPage() {
  const { locale, t } = useTranslation();
  const searchParams = useSearchParams();
  const { data, error, isLoading, reload } = useApiResource<TasksResponse>("/tasks?limit=200");
  const applications = useApiResource<ApplicationsResponse>("/applications");
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const deferredQuery = useDeferredValue(query.trim().toLowerCase());
  const tasks = data?.tasks ?? [];
  const availableStatuses = ["all", ...new Set(tasks.map((task) => String(task.status ?? "unknown")))];
  const initialAttachments = useMemo<TaskLaunchAttachment[]>(() => {
    const assetId = searchParams.get("assetId");
    if (!assetId) {
      return [];
    }
    const segmentCount = Number(searchParams.get("segmentCount") ?? "");
    return [
      {
        assetId,
        label: searchParams.get("assetLabel") ?? undefined,
        sourceUri: searchParams.get("sourceUri") ?? undefined,
        summary: searchParams.get("summary") ?? undefined,
        summaryNodeId: searchParams.get("summaryNodeId") ?? undefined,
        segmentCount: Number.isFinite(segmentCount) ? segmentCount : undefined,
      },
    ];
  }, [searchParams]);
  const filteredTasks = tasks.filter((task) => {
    const statusMatches = statusFilter === "all" || task.status === statusFilter;
    const queryMatches =
      deferredQuery.length === 0 ||
      [task.title, task.goal, String(task.currentFocus ?? ""), String(task.currentObjective ?? ""), task.id]
        .join(" ")
        .toLowerCase()
        .includes(deferredQuery);
    return statusMatches && queryMatches;
  });

  if (isLoading) {
    return <LoadingState title={t("tasks.loading")} />;
  }

  if (error) {
    return <ErrorState detail={error} />;
  }

  return (
    <div className="task-hub-page">
      <PageHeader
        eyebrow={t("tasks.eyebrow")}
        title={t("tasks.title")}
        summary={<>{t("tasks.summary")}</>}
        actions={<button className="ghost-button" onClick={reload} type="button">{t("tasks.reload")}</button>}
      />

      {applications.error ? <ErrorState title={t("tasks.applicationsUnavailable")} detail={applications.error} /> : null}

      <div className="task-hub-layout">
        <div className="task-hub-main">
          <Surface className="task-hub-filters">
            <p className="section-kicker">{t("tasks.filters")}</p>
            <h3 className="section-title">{t("tasks.find")}</h3>
            <div className="search-row">
              <input
                className="search-input"
                onChange={(event) => setQuery(event.target.value)}
                placeholder={t("tasks.searchPlaceholder")}
                value={query}
              />
              {availableStatuses.map((status) => (
                <button
                  key={status}
                  className={`filter-chip${statusFilter === status ? " active" : ""}`}
                  onClick={() => setStatusFilter(status)}
                  type="button"
                >
                  {status === "all" ? t("tasks.all") : statusLabel(status, t)}
                </button>
              ))}
            </div>
            <p className="meta-copy">{t("tasks.count", { count: filteredTasks.length })}</p>
          </Surface>

          <div className="record-list task-hub-list">
        {filteredTasks.length === 0 ? (
          <EmptyState title={t("tasks.noMatches")} detail={t("tasks.noMatchesDetail")} />
        ) : (
          filteredTasks.map((task) => (
            <article className="record-card" key={task.id}>
              <div className="record-head">
                <div>
                  <Link className="record-link" href={`/tasks/${encodeURIComponent(task.id)}`}>
                    <h3 className="record-title">{task.title}</h3>
                  </Link>
                  <p className="meta-copy">{task.goal}</p>
                </div>
                <StatusBadge value={task.status} />
              </div>
              <div className="record-meta">
                <div className="kv-item">
                  <p className="meta-label">{t("tasks.id")}</p>
                  <p className="meta-copy mono">{task.id}</p>
                </div>
                <div className="kv-item">
                  <p className="meta-label">{t("tasks.branch")}</p>
                  <p className="meta-copy mono">{String(task.branchId ?? "-")}</p>
                </div>
                <div className="kv-item">
                  <p className="meta-label">{t("tasks.currentFocus")}</p>
                  <p className="meta-copy">{String(task.currentFocus ?? "-")}</p>
                </div>
                <div className="kv-item">
                  <p className="meta-label">{t("tasks.updatedAt")}</p>
                  <p className="meta-copy">{formatTimestamp(task.updatedAt ?? task.createdAt, locale)}</p>
                </div>
              </div>
            </article>
          ))
        )}
          </div>
        </div>

        {!applications.isLoading && applications.data ? (
          <aside className="task-hub-create-panel">
            <TaskLaunchPanel
              applications={applications.data.applications}
              defaultAppId={searchParams.get("appId") ?? applications.data.activeAppId}
              initialAttachments={initialAttachments}
            />
          </aside>
        ) : null}
      </div>
    </div>
  );
}
