"use client";

import Link from "next/link";
import { useState } from "react";

import type { ApplicationCatalogItem } from "@yggdrasil/frontend-sdk";

import { postApiJson, useApiResource } from "../lib/use-api-resource";
import { EmptyState, ErrorState, LoadingState, PageHeader, Surface, StatusBadge, formatTimestamp } from "./workbench-primitives";

type ApplicationsResponse = { activeAppId: string; applications: ApplicationCatalogItem[] };

export function ApplicationsPage() {
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
    return <LoadingState title="正在读取应用插件清单" />;
  }

  if (applications.error) {
    return <ErrorState detail={applications.error} />;
  }

  const items = applications.data?.applications ?? [];
  if (items.length === 0) {
    return <EmptyState title="还没有发现应用" detail="请先在仓库的 applications 目录下注册 yggdrasil.app.yaml。" />;
  }

  return (
    <div>
      <PageHeader
        eyebrow="Applications"
        title="应用入口与任务模板"
        summary={<>应用现在是新任务的入口。选择一个应用后，可以直接用它的模板创建第一任务，配置仍保存在基座状态里。</>}
        actions={
          <>
            <Link className="action-button" href={`/tasks?appId=${encodeURIComponent(applications.data?.activeAppId ?? "")}`}>New task</Link>
            <button className="ghost-button" onClick={() => applications.reload()} type="button">刷新应用清单</button>
          </>
        }
      />

      {actionError ? <ErrorState title="应用操作失败" detail={actionError} /> : null}

      <div className="content-grid tight">
        {items.map((item) => {
          const manifest = item.application;
          const binding = item.configBinding;
          const templateCount = Array.isArray(item.dashboard?.taskTemplates) ? item.dashboard.taskTemplates.length : 0;
          const isPending = pendingAppId === manifest.appId;
          return (
            <Surface key={manifest.appId}>
              <div className="record-head">
                <div>
                  <p className="section-kicker">{manifest.owner ?? "application"}</p>
                  <h3 className="section-title">{manifest.displayName}</h3>
                  <p className="meta-copy">{manifest.appId}</p>
                </div>
                <StatusBadge value={binding.active ? "active" : manifest.defaultLoad ? "default" : "inactive"} />
              </div>
              <p className="meta-copy">{manifest.description ?? "该应用未提供额外说明。"}</p>
              <div className="pill-row">
                <span className="inline-chip">version {manifest.version}</span>
                <span className="inline-chip">modules {manifest.moduleDependencies.length}</span>
                <span className="inline-chip">scenes {manifest.sceneModuleIds.length}</span>
                <span className="inline-chip">templates {templateCount}</span>
                <span className="inline-chip">updated {formatTimestamp(binding.updatedAt)}</span>
              </div>
              <div className="field-actions">
                <Link className="action-button" href={`/tasks?appId=${encodeURIComponent(manifest.appId)}`}>新建任务</Link>
                <Link className="ghost-button" href={`/applications/${encodeURIComponent(manifest.appId)}`}>查看详情</Link>
                <button className="action-button" disabled={binding.active || isPending} onClick={() => void handleActivate(manifest.appId)} type="button">
                  {binding.active ? "当前激活" : isPending ? "切换中" : "激活应用"}
                </button>
              </div>
            </Surface>
          );
        })}
      </div>
    </div>
  );
}
