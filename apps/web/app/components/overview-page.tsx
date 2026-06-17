"use client";

import Link from "next/link";

import type { ApplicationCatalogItem, SetupChecklistItem, WorkbenchOverview } from "@yggdrasil/frontend-sdk";

import { useApiResource } from "../lib/use-api-resource";
import { TaskLaunchPanel } from "./task-launch-panel";
import { EmptyState, ErrorState, LoadingState, PageHeader, StatCard, StatusBadge, Surface, formatTimestamp } from "./workbench-primitives";

type ApplicationsResponse = { activeAppId: string; applications: ApplicationCatalogItem[] };

function UserActionChecklist({ items }: { items: SetupChecklistItem[] }) {
  const visibleItems = items.length > 0
    ? items
    : [
        {
          id: "materials",
          label: "添加材料",
          status: "warning" as const,
          detail: "先导入资料，或直接在任务目标里写清背景。",
        },
        {
          id: "approval",
          label: "启动前确认",
          status: "ready" as const,
          detail: "创建草稿后再决定是否立即启动。",
        },
      ];
  const blocked = visibleItems.filter((item) => item.status === "blocked").length;

  return (
    <Surface className="start-checklist">
      <div className="record-head">
        <div>
          <p className="section-kicker">准备情况</p>
          <h3 className="section-title">需要先处理什么</h3>
          <p className="section-copy">这里只显示会影响首次任务的事项。维护细节放在帮助与诊断里。</p>
        </div>
        <StatusBadge value={blocked > 0 ? "blocked" : "ready"} />
      </div>
      <div className="setup-grid">
        {visibleItems.map((item) => (
          <article className="setup-item" key={item.id}>
            <div className="record-head">
              <div>
                <h4 className="record-title">{checklistLabel(item)}</h4>
                <p className="meta-copy">{checklistDetail(item)}</p>
              </div>
              <StatusBadge value={item.status} />
            </div>
          </article>
        ))}
      </div>
    </Surface>
  );
}

function checklistLabel(item: SetupChecklistItem): string {
  const labels: Record<string, string> = {
    "core-api": "本地服务",
    database: "本地数据",
    redis: "后台协调",
    "worker-queue": "任务执行器",
    "model-provider": "AI 服务",
    "workspace-path": "工作区",
    "state-root": "本地存储",
  };
  return labels[item.id] ?? item.label;
}

function checklistDetail(item: SetupChecklistItem): string {
  if (item.status === "ready") {
    if (["core-api", "database", "redis", "workspace-path", "state-root"].includes(item.id)) {
      return "已准备好。";
    }
    if (item.id === "model-provider") {
      return "AI 服务已连接。";
    }
  }
  if (item.id === "worker-queue") {
    return "如需执行任务，请从桌面启动器或帮助与诊断确认后台执行器。";
  }
  if (item.id === "model-provider") {
    return "请在设置里连接 AI 服务后再启动任务。";
  }
  return item.status === "blocked" ? "需要先处理这个问题。" : item.detail;
}

function providerSummary(status: WorkbenchOverview["health"]["providerStatus"]): string {
  if (!status) {
    return "启动任务前需要确认 AI 服务连接。";
  }
  if (status.status === "ready") {
    return "AI 服务已连接，可以创建并启动任务。";
  }
  if (status.status === "warning") {
    return "AI 服务连接需要确认，建议先创建草稿。";
  }
  return "请先在设置里连接 AI 服务。";
}

export function OverviewPage() {
  const overview = useApiResource<WorkbenchOverview>("/workbench/overview");
  const applications = useApiResource<ApplicationsResponse>("/applications");

  if (overview.isLoading || applications.isLoading) {
    return <LoadingState title="正在准备开始页" />;
  }

  if (overview.error) {
    return <ErrorState title="本地服务未就绪" detail={overview.error} />;
  }

  if (!overview.data) {
    return <ErrorState title="本地服务未就绪" detail="暂时无法读取开始页状态。请打开帮助与诊断查看本地产品状态。" />;
  }

  const setupItems = overview.data.health.setupChecklist ?? [];
  const appItems = applications.data?.applications ?? [];
  const recentDrafts = overview.data.recentTasks.filter((task) => task.status === "draft").slice(0, 3);
  const recentTasks = overview.data.recentTasks.slice(0, 4);
  const providerStatus = overview.data.health.providerStatus;
  const providerValue = providerStatus?.status === "ready" ? "已连接" : providerStatus?.status === "warning" ? "需确认" : "未连接";
  const blockedCount = setupItems.filter((item) => item.status === "blocked").length;

  return (
    <div>
      <PageHeader
        eyebrow="开始"
        title="启动第一任务"
        summary={<>添加材料，选择一个应用模板，确认预算和目标后再启动。所有数据默认留在本机。</>}
        actions={
          <>
            <Link className="action-button" href="/assets">
              添加材料
            </Link>
            <Link className="ghost-button" href="/applications">
              选择应用
            </Link>
            <Link className="ghost-button" href="/settings">
              打开设置
            </Link>
          </>
        }
      />

      <section className="stat-grid">
        <StatCard label="AI 服务" value={providerValue} copy={providerSummary(providerStatus)} />
        <StatCard label="需要处理" value={blockedCount} copy={blockedCount > 0 ? "先处理阻塞项，再启动任务。" : "当前没有阻塞首次任务的事项。"} />
        <StatCard label="任务草稿" value={overview.data.taskStatusCounts.draft ?? 0} copy="可以先保存草稿，再启动执行。" />
        <StatCard label="本地数据" value="保留" copy="任务材料、结果和备份默认保存在本机。" />
      </section>

      <div className="start-layout">
        <div className="section-stack">
          {applications.error ? <ErrorState title="应用清单不可用" detail={applications.error} /> : null}
          {appItems.length > 0 ? (
            <TaskLaunchPanel applications={appItems} title="创建任务草稿" />
          ) : (
            <EmptyState title="没有可启动应用" detail="应用清单暂不可用，无法创建首次任务。" />
          )}

          <Surface>
            <div className="record-head">
              <div>
                <p className="section-kicker">草稿</p>
                <h3 className="section-title">待确认任务</h3>
                <p className="section-copy">草稿不会自动执行。确认目标、材料和预算后再启动。</p>
              </div>
              <Link className="ghost-button" href="/tasks">查看全部</Link>
            </div>
            {recentDrafts.length === 0 ? (
              <EmptyState title="还没有任务草稿" detail="从上方模板创建草稿后，会在这里继续确认。" />
            ) : (
              <div className="record-list">
                {recentDrafts.map((task) => (
                  <article className="record-card" key={task.id}>
                    <div className="record-head">
                      <div>
                        <Link className="record-link" href={`/tasks/${encodeURIComponent(task.id)}`}>
                          <h4 className="record-title">{task.title}</h4>
                        </Link>
                        <p className="meta-copy">{task.goal}</p>
                      </div>
                      <StatusBadge value={task.status} />
                    </div>
                  </article>
                ))}
              </div>
            )}
          </Surface>
        </div>

        <div className="section-stack">
          <UserActionChecklist items={setupItems} />

          <Surface>
            <p className="section-kicker">隐私</p>
            <h3 className="section-title">本地优先</h3>
            <p className="section-copy">材料、任务状态、运行结果和备份默认保存在本机。只有启动真实 AI 服务时，任务目标和相关上下文才会发送给所选服务。</p>
            <div className="field-actions">
              <Link className="ghost-button" href="/settings">查看数据与隐私</Link>
              <Link className="ghost-button" href="/data-governance">备份与删除</Link>
            </div>
          </Surface>

          <Surface>
            <p className="section-kicker">最近任务</p>
            <h3 className="section-title">继续处理</h3>
            {recentTasks.length === 0 ? (
              <EmptyState title="还没有任务" detail="创建第一任务后，会在这里继续跟进。" />
            ) : (
              <div className="record-list">
                {recentTasks.map((task) => (
                  <article className="record-card" key={task.id}>
                    <div className="record-head">
                      <div>
                        <Link className="record-link" href={`/tasks/${encodeURIComponent(task.id)}`}>
                          <h4 className="record-title">{task.title}</h4>
                        </Link>
                        <p className="meta-copy">{formatTimestamp(task.updatedAt ?? task.createdAt)}</p>
                      </div>
                      <StatusBadge value={task.status} />
                    </div>
                  </article>
                ))}
              </div>
            )}
          </Surface>
        </div>
      </div>
    </div>
  );
}
