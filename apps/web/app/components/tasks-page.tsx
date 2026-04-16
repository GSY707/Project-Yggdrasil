"use client";

import Link from "next/link";
import { useDeferredValue, useState } from "react";

import type { TaskSummaryRecord } from "@yggdrasil/frontend-sdk";

import { useApiResource } from "../lib/use-api-resource";
import { EmptyState, ErrorState, LoadingState, PageHeader, StatusBadge, Surface, formatTimestamp } from "./workbench-primitives";

type TasksResponse = {
  tasks: TaskSummaryRecord[];
};

export function TasksPage() {
  const { data, error, isLoading, reload } = useApiResource<TasksResponse>("/tasks?limit=200");
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const deferredQuery = useDeferredValue(query.trim().toLowerCase());
  const tasks = data?.tasks ?? [];
  const availableStatuses = ["all", ...new Set(tasks.map((task) => String(task.status ?? "unknown")))];
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
        eyebrow="Tasks"
        title="任务执行与安全停顿总览"
        summary={<>这里聚合 task、agent run、snapshot 和 route decision 的正式记录，用来验证 M5 主代理执行闭环。</>}
        actions={<button className="ghost-button" onClick={reload} type="button">刷新任务视图</button>}
      />

      <Surface>
        <p className="section-kicker">Filters</p>
        <h3 className="section-title">查找任务</h3>
        <div className="search-row">
          <input
            className="search-input"
            onChange={(event) => setQuery(event.target.value)}
            placeholder="按标题、目标、focus、ID 搜索"
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
                  <p className="meta-label">Task ID</p>
                  <p className="meta-copy mono">{task.id}</p>
                </div>
                <div className="kv-item">
                  <p className="meta-label">Branch</p>
                  <p className="meta-copy mono">{String(task.branchId ?? "-")}</p>
                </div>
                <div className="kv-item">
                  <p className="meta-label">Current Focus</p>
                  <p className="meta-copy">{String(task.currentFocus ?? "-")}</p>
                </div>
                <div className="kv-item">
                  <p className="meta-label">Updated</p>
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