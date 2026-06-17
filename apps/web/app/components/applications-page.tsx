"use client";

import Link from "next/link";
import { useState } from "react";

import type { ApplicationCatalogItem, ApplicationTaskTemplate } from "@yggdrasil/frontend-sdk";

import { postApiJson, useApiResource } from "../lib/use-api-resource";
import { EmptyState, ErrorState, LoadingState, PageHeader, StatusBadge, Surface } from "./workbench-primitives";

type ApplicationsResponse = { activeAppId: string; applications: ApplicationCatalogItem[] };

const FEATURED_APPS = [
  {
    appId: "yggdrasil.app.deep-research",
    label: "Deep Research",
    purpose: "把开放问题变成带证据边界的研究结论。",
    needs: ["研究问题", "范围限制", "输出标准"],
    review: "证据、反方意见和不确定性会被标出。",
  },
  {
    appId: "yggdrasil.app.graduate-researcher",
    label: "Graduate Writing",
    purpose: "把学习资料、论文方向和导师要求整理成研究写作推进。",
    needs: ["已有材料", "学校或导师要求", "交付时间"],
    review: "适合先生成提纲、文献理解和开题材料。",
  },
  {
    appId: "yggdrasil.app.coding-greenfield",
    label: "Coding Assistant",
    purpose: "从产品想法、原型或约束启动可运行的软件项目。",
    needs: ["目标用户", "功能范围", "技术约束"],
    review: "启动前会明确第一版范围和验证方式。",
  },
  {
    appId: "yggdrasil.app.knowledge-studio",
    label: "Knowledge Base",
    purpose: "把资料、访谈、笔记和创作设定沉淀为可复用知识资产。",
    needs: ["主题", "已有材料", "目标读者或使用场景"],
    review: "输出结构化档案、素材索引和下一步建议。",
  },
];

function templates(item: ApplicationCatalogItem): ApplicationTaskTemplate[] {
  const dashboardTemplates = item.dashboard?.taskTemplates;
  return Array.isArray(dashboardTemplates) ? dashboardTemplates : [];
}

function settingsLabels(item: ApplicationCatalogItem): string[] {
  const labelMap: Record<string, string> = {
    provider: "AI 服务",
    model: "模型选择",
    tokenBudgetTotal: "预算上限",
    costBudgetTotal: "花费上限",
    workspace: "材料位置",
    outputStyle: "输出风格",
    memoryNamespace: "知识范围",
    toolPermissions: "工具权限",
  };
  const labels = item.dashboard?.settingsSchema?.map((field) => labelMap[field.key] ?? field.label).filter(Boolean) ?? [];
  return labels.slice(0, 3);
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
        purpose: item.dashboard?.hero?.summary ?? item.application.description ?? "使用这个应用模板启动任务。",
        needs: ["任务目标", "相关材料", "输出要求"],
        review: "启动前可以先创建草稿并检查目标。",
      },
    })),
  ];
}

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
    return <LoadingState title="正在读取应用" />;
  }

  if (applications.error) {
    return <ErrorState title="应用清单不可用" detail={applications.error} />;
  }

  const items = applications.data?.applications ?? [];
  if (items.length === 0) {
    return <EmptyState title="还没有发现应用" detail="本地应用清单为空，暂时不能创建应用任务。" />;
  }

  const featured = featuredItems(items);
  const featuredIds = new Set(featured.map(({ item }) => item.application.appId));
  const moreCount = items.filter((item) => !featuredIds.has(item.application.appId)).length;

  return (
    <div>
      <PageHeader
        eyebrow="应用"
        title="选择任务类型"
        summary={<>四个默认入口使用同一结构展示材料需求、模板、设置、审阅状态和启动动作。其他应用留在维护者详情中。</>}
        actions={
          <>
            <Link className="action-button" href="/tasks">新建任务</Link>
            <button className="ghost-button" onClick={() => applications.reload()} type="button">刷新</button>
          </>
        }
      />

      {actionError ? <ErrorState title="应用操作失败" detail={actionError} /> : null}

      <div className="app-matrix">
        {featured.map(({ item, meta }) => {
          const manifest = item.application;
          const binding = item.configBinding;
          const appTemplates = templates(item);
          const isPending = pendingAppId === manifest.appId;
          return (
            <Surface className="app-matrix-card" key={manifest.appId}>
              <div className="record-head">
                <div>
                  <p className="section-kicker">应用</p>
                  <h3 className="section-title">{meta.label}</h3>
                  <p className="meta-copy">{meta.purpose}</p>
                </div>
                <StatusBadge value={binding.active ? "active" : "available"} />
              </div>

              <div className="matrix-block">
                <p className="meta-label">需要准备</p>
                <ul className="mini-list">
                  {meta.needs.map((need) => <li key={need}>{need}</li>)}
                </ul>
              </div>

              <div className="matrix-block">
                <p className="meta-label">可用模板</p>
                <div className="pill-row">
                  {(appTemplates.length > 0 ? appTemplates.slice(0, 3).map((template) => template.title) : ["默认任务"]).map((template) => (
                    <span className="inline-chip" key={template}>{template}</span>
                  ))}
                </div>
              </div>

              <div className="matrix-block">
                <p className="meta-label">主要设置</p>
                <div className="pill-row">
                  {(settingsLabels(item).length > 0 ? settingsLabels(item) : ["预算", "输出风格", "材料位置"]).map((label) => (
                    <span className="inline-chip" key={label}>{label}</span>
                  ))}
                </div>
              </div>

              <div className="matrix-block">
                <p className="meta-label">启动前审阅</p>
                <p className="meta-copy">{meta.review}</p>
              </div>

              <div className="field-actions">
                <Link className="action-button" href={`/tasks?appId=${encodeURIComponent(manifest.appId)}`}>开始</Link>
                <Link className="ghost-button" href={`/applications/${encodeURIComponent(manifest.appId)}`}>详情</Link>
                <button className="ghost-button" disabled={binding.active || isPending} onClick={() => void handleActivate(manifest.appId)} type="button">
                  {binding.active ? "当前默认" : isPending ? "切换中" : "设为默认"}
                </button>
              </div>
            </Surface>
          );
        })}
      </div>

      {moreCount > 0 ? (
        <Surface>
          <div className="record-head">
            <div>
              <p className="section-kicker">维护者</p>
              <h3 className="section-title">其他应用</h3>
              <p className="section-copy">{moreCount} 个应用不在普通四入口中展示，可从维护者详情查看和启动。</p>
            </div>
            <Link className="ghost-button" href="/release">查看诊断</Link>
          </div>
        </Surface>
      ) : null}
    </div>
  );
}
