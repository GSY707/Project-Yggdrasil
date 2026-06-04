"use client";

import Link from "next/link";
import { useDeferredValue, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";

import type { ApplicationCatalogItem, TaskLaunchAttachment, TaskSummaryRecord } from "@yggdrasil/frontend-sdk";

import { useApiResource } from "../lib/use-api-resource";
import { TaskLaunchPanel } from "./task-launch-panel";
import { EmptyState, ErrorState, LoadingState, PageHeader, StatusBadge, Surface, formatTimestamp } from "./workbench-primitives";

type TasksResponse = {
  tasks: TaskSummaryRecord[];
};

type ApplicationsResponse = {
  activeAppId: string;
  applications: ApplicationCatalogItem[];
};

export function TasksPage() {
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
    return <LoadingState title="正在读取任务编排视图" />;
  }

  if (error) {
    return <ErrorState detail={error} />;
  }

  return (
    <div>
      <PageHeader
        eyebrow="任务"
        title="任务创建、启动与运行总览"
        summary={<>先从应用模板创建任务并启动；已运行任务仍可在这里进入详情、查看恢复状态和运行记录。</>}
        actions={<button className="ghost-button" onClick={reload} type="button">刷新任务视图</button>}
      />

      {applications.error ? <ErrorState title="应用模板不可用" detail={applications.error} /> : null}
      {!applications.isLoading && applications.data ? (
        <TaskLaunchPanel
          applications={applications.data.applications}
          defaultAppId={searchParams.get("appId") ?? applications.data.activeAppId}
          initialAttachments={initialAttachments}
        />
      ) : null}

      <Surface>
        <p className="section-kicker">筛选</p>
        <h3 className="section-title">查找任务</h3>
        <div className="search-row">
          <input
            className="search-input"
            onChange={(event) => setQuery(event.target.value)}
            placeholder="按标题、目标、当前重点或编号搜索"
            value={query}
          />
          {availableStatuses.map((status) => (
            <button
              key={status}
              className={`filter-chip${statusFilter === status ? " active" : ""}`}
              onClick={() => setStatusFilter(status)}
              type="button"
            >
              {status}
            </button>
          ))}
        </div>
        <p className="meta-copy">共 {filteredTasks.length} 个任务符合当前筛选。</p>
      </Surface>

      <div className="record-list">
        {filteredTasks.length === 0 ? (
          <EmptyState title="没有匹配的任务" detail="调整搜索关键字或状态筛选后重试。" />
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
                  <p className="meta-label">任务编号</p>
                  <p className="meta-copy mono">{task.id}</p>
                </div>
                <div className="kv-item">
                  <p className="meta-label">记忆分支</p>
                  <p className="meta-copy mono">{String(task.branchId ?? "-")}</p>
                </div>
                <div className="kv-item">
                  <p className="meta-label">当前重点</p>
                  <p className="meta-copy">{String(task.currentFocus ?? "-")}</p>
                </div>
                <div className="kv-item">
                  <p className="meta-label">更新时间</p>
                  <p className="meta-copy">{formatTimestamp(task.updatedAt ?? task.createdAt)}</p>
                </div>
              </div>
            </article>
          ))
        )}
      </div>
    </div>
  );
}
