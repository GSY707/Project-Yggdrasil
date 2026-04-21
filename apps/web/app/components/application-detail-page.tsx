"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import type { ApplicationConfigBinding, ApplicationManifestSummary } from "@yggdrasil/frontend-sdk";

import { postApiJson, useApiResource } from "../lib/use-api-resource";
import { EmptyState, ErrorState, LoadingState, PageHeader, Surface, StatusBadge } from "./workbench-primitives";

type ApplicationDetailResponse = {
  application: ApplicationManifestSummary;
  configBinding: ApplicationConfigBinding;
  effectiveConfig: Record<string, unknown>;
  dashboard?: Record<string, unknown> | null;
};

export function ApplicationDetailPage({ appId }: { appId: string }) {
  const detail = useApiResource<ApplicationDetailResponse>(`/applications/${encodeURIComponent(appId)}`);
  const [configDraft, setConfigDraft] = useState("{}");
  const [saveError, setSaveError] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    if (detail.data?.configBinding) {
      setConfigDraft(JSON.stringify(detail.data.configBinding.importantConfig ?? {}, null, 2));
    }
  }, [detail.data?.configBinding]);

  async function handleActivate() {
    setIsSaving(true);
    setSaveError(null);
    try {
      await postApiJson(`/applications/${encodeURIComponent(appId)}/activate`);
      detail.reload();
    } catch (error) {
      setSaveError(error instanceof Error ? error.message : String(error));
    } finally {
      setIsSaving(false);
    }
  }

  async function handleSaveConfig() {
    setIsSaving(true);
    setSaveError(null);
    try {
      const parsed = JSON.parse(configDraft) as Record<string, unknown>;
      await postApiJson(`/applications/${encodeURIComponent(appId)}/config`, { importantConfig: parsed });
      detail.reload();
    } catch (error) {
      setSaveError(error instanceof Error ? error.message : String(error));
    } finally {
      setIsSaving(false);
    }
  }

  if (detail.isLoading) {
    return <LoadingState title="正在读取应用详情" />;
  }

  if (detail.error) {
    return <ErrorState detail={detail.error} />;
  }

  if (!detail.data) {
    return <EmptyState title="应用不存在" detail="未能读取到对应应用详情。" />;
  }

  const manifest = detail.data.application;
  const binding = detail.data.configBinding;
  const dashboardHero = typeof detail.data.dashboard?.hero === "object" ? detail.data.dashboard?.hero as Record<string, unknown> : null;
  const quickActions = Array.isArray(detail.data.dashboard?.quickActions) ? detail.data.dashboard?.quickActions as Array<Record<string, unknown>> : [];

  return (
    <div>
      <PageHeader
        eyebrow={String(dashboardHero?.eyebrow ?? "Application Detail")}
        title={String(dashboardHero?.title ?? manifest.displayName)}
        summary={<>{String(dashboardHero?.summary ?? manifest.description ?? "该应用未提供额外说明。")}</>}
        actions={<Link className="ghost-button" href="/applications">返回应用清单</Link>}
      />

      {saveError ? <ErrorState title="应用管理操作失败" detail={saveError} /> : null}

      <div className="content-grid tight">
        <Surface>
          <p className="section-kicker">Identity</p>
          <h3 className="section-title">应用摘要</h3>
          <div className="record-list">
            <article className="record-card">
              <div className="record-head">
                <div>
                  <h4 className="record-title">{manifest.displayName}</h4>
                  <p className="meta-copy">{manifest.appId}</p>
                </div>
                <StatusBadge value={binding.active ? "active" : manifest.defaultLoad ? "default" : "inactive"} />
              </div>
              <div className="pill-row">
                <span className="inline-chip">version {manifest.version}</span>
                <span className="inline-chip">owner {manifest.owner ?? "-"}</span>
                <span className="inline-chip">prompt {manifest.defaultPromptProfileId ?? "-"}</span>
                <span className="inline-chip">seed {manifest.defaultSeedTemplateId ?? "-"}</span>
              </div>
            </article>
          </div>
          <div className="field-actions">
            <button className="action-button" disabled={binding.active || isSaving} onClick={() => void handleActivate()} type="button">
              {binding.active ? "当前激活" : isSaving ? "处理中" : "激活应用"}
            </button>
            <Link className="ghost-button" href={`/prompting?appId=${encodeURIComponent(manifest.appId)}`}>在 Prompt 控制面中查看</Link>
          </div>
        </Surface>

        <Surface>
          <p className="section-kicker">Modules</p>
          <h3 className="section-title">装配模块</h3>
          <div className="record-list">
            {[...manifest.capabilityModuleIds, ...manifest.sceneModuleIds].map((moduleId) => (
              <article className="record-card" key={moduleId}>
                <div className="record-head">
                  <div>
                    <h4 className="record-title">{moduleId}</h4>
                    <p className="meta-copy">module dependency</p>
                  </div>
                </div>
              </article>
            ))}
          </div>
        </Surface>

        <Surface>
          <p className="section-kicker">Config</p>
          <h3 className="section-title">重要配置管理</h3>
          <p className="meta-copy">这里写入的是基座侧 importantConfig，会覆盖应用包 defaults.json 中的同名配置。</p>
          <div className="form-field">
            <label className="meta-label" htmlFor="application-config">Important Config JSON</label>
            <textarea className="field-input field-textarea" id="application-config" onChange={(event) => setConfigDraft(event.target.value)} rows={12} value={configDraft} />
          </div>
          <div className="field-actions">
            <button className="action-button" disabled={isSaving} onClick={() => void handleSaveConfig()} type="button">
              {isSaving ? "保存中" : "保存重要配置"}
            </button>
          </div>
          <pre className="meta-copy mono">{JSON.stringify(detail.data.effectiveConfig, null, 2)}</pre>
        </Surface>

        <Surface>
          <p className="section-kicker">Dashboard</p>
          <h3 className="section-title">应用元数据</h3>
          {quickActions.length === 0 ? (
            <EmptyState title="没有 dashboard quick actions" detail="该应用仅提供了最小元数据。" />
          ) : (
            <div className="record-list">
              {quickActions.map((action, index) => (
                <article className="record-card" key={`${String(action.label ?? "action")}-${index}`}>
                  <div className="record-head">
                    <div>
                      <h4 className="record-title">{String(action.label ?? `Action ${index + 1}`)}</h4>
                      <p className="meta-copy">{String(action.href ?? "")}</p>
                    </div>
                    {typeof action.href === "string" ? <Link className="ghost-button" href={action.href}>打开</Link> : null}
                  </div>
                </article>
              ))}
            </div>
          )}
        </Surface>
      </div>
    </div>
  );
}