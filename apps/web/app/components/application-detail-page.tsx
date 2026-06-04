"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import type {
  ApplicationCatalogItem,
  ApplicationConfigBinding,
  ApplicationDashboard,
  ApplicationManifestSummary,
  ApplicationMemoryAssetRecord,
  ApplicationSettingsField,
} from "@yggdrasil/frontend-sdk";

import { postApiJson, useApiResource } from "../lib/use-api-resource";
import { TaskLaunchPanel } from "./task-launch-panel";
import { EmptyState, ErrorState, LoadingState, PageHeader, Surface, StatusBadge } from "./workbench-primitives";

type ApplicationDetailResponse = {
  application: ApplicationManifestSummary;
  configBinding: ApplicationConfigBinding;
  effectiveConfig: Record<string, unknown>;
  applicationMemoryAssets: Array<ApplicationMemoryAssetRecord>;
  dashboard?: Record<string, unknown> | null;
};

const DEFAULT_SETTINGS_SCHEMA: ApplicationSettingsField[] = [
  {
    key: "provider",
    label: "模型供应商",
    type: "select",
    description: "默认模型供应商。",
    options: [
      { label: "LongCat", value: "longcat" },
      { label: "OpenRouter", value: "openrouter" },
      { label: "DeepSeek Direct", value: "deepseek_direct" },
      { label: "VectorEngine", value: "vectorengine" },
    ],
  },
  { key: "model", label: "默认模型", type: "text", description: "默认模型名称。" },
  { key: "tokenBudgetTotal", label: "Token 总预算", type: "number", description: "任务默认 token 总预算。" },
  { key: "costBudgetTotal", label: "成本预算", type: "number", description: "任务默认成本预算，单位 USD。" },
  { key: "workspace", label: "工作区", type: "text", description: "任务默认工作区或资料目录。" },
  { key: "outputStyle", label: "输出风格", type: "textarea", description: "默认输出风格要求。" },
  { key: "memoryNamespace", label: "记忆命名空间", type: "text", description: "运行记忆命名空间。" },
  {
    key: "toolPermissions",
    label: "工具权限",
    type: "select",
    description: "默认工具权限强度。",
    options: [
      { label: "保守", value: "conservative" },
      { label: "工具丰富", value: "tool-rich" },
      { label: "不限制", value: "unrestricted" },
    ],
  },
];

function asRecord(value: unknown): Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value) ? (value as Record<string, unknown>) : {};
}

function dashboardPayload(value: Record<string, unknown> | null | undefined): ApplicationDashboard {
  return asRecord(value) as ApplicationDashboard;
}

function settingsSchema(dashboard: ApplicationDashboard): ApplicationSettingsField[] {
  return Array.isArray(dashboard.settingsSchema) && dashboard.settingsSchema.length > 0 ? dashboard.settingsSchema : DEFAULT_SETTINGS_SCHEMA;
}

function settingValue(config: Record<string, unknown>, field: ApplicationSettingsField): string | number | boolean {
  const raw = config[field.key] ?? field.defaultValue ?? "";
  if (field.type === "boolean") {
    return Boolean(raw);
  }
  if (field.type === "number") {
    return raw === "" || raw === null || raw === undefined ? "" : Number(raw);
  }
  return String(raw ?? "");
}

function parseSettingsDraft(fields: ApplicationSettingsField[], draft: Record<string, string | number | boolean>): Record<string, unknown> {
  const parsed: Record<string, unknown> = {};
  for (const field of fields) {
    const value = draft[field.key];
    if (field.required && (value === "" || value === undefined || value === null)) {
      throw new Error(`${field.label} 是必填项。`);
    }
    if (value === "" || value === undefined || value === null) {
      continue;
    }
    if (field.type === "number") {
      const numeric = Number(value);
      if (!Number.isFinite(numeric)) {
        throw new Error(`${field.label} 必须是数字。`);
      }
      parsed[field.key] = numeric;
    } else if (field.type === "boolean") {
      parsed[field.key] = Boolean(value);
    } else {
      parsed[field.key] = String(value);
    }
  }
  return parsed;
}

export function ApplicationDetailPage({ appId }: { appId: string }) {
  const detail = useApiResource<ApplicationDetailResponse>(`/applications/${encodeURIComponent(appId)}`);
  const [configDraft, setConfigDraft] = useState("{}");
  const [settingsDraft, setSettingsDraft] = useState<Record<string, string | number | boolean>>({});
  const [advancedConfigOpen, setAdvancedConfigOpen] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    if (detail.data?.configBinding) {
      setConfigDraft(JSON.stringify(detail.data.configBinding.importantConfig ?? {}, null, 2));
      const dashboard = dashboardPayload(detail.data.dashboard);
      const fields = settingsSchema(dashboard);
      const sourceConfig = {
        ...asRecord(detail.data.effectiveConfig),
        ...asRecord(detail.data.configBinding.importantConfig),
      };
      setSettingsDraft(Object.fromEntries(fields.map((field) => [field.key, settingValue(sourceConfig, field)])));
    }
  }, [detail.data?.configBinding, detail.data?.dashboard, detail.data?.effectiveConfig]);

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
      const dashboard = dashboardPayload(detail.data?.dashboard);
      const fields = settingsSchema(dashboard);
      const advancedConfig = JSON.parse(configDraft) as Record<string, unknown>;
      const typedConfig = parseSettingsDraft(fields, settingsDraft);
      const parsed = {
        ...advancedConfig,
        ...typedConfig,
      };
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
  const memoryAssets = detail.data.applicationMemoryAssets ?? [];
  const dashboard = dashboardPayload(detail.data.dashboard);
  const fields = settingsSchema(dashboard);
  const dashboardHero = typeof dashboard.hero === "object" ? dashboard.hero as Record<string, unknown> : null;
  const quickActions = Array.isArray(dashboard.quickActions) ? dashboard.quickActions as Array<Record<string, unknown>> : [];
  const launchItem: ApplicationCatalogItem = {
    application: manifest,
    configBinding: binding,
    dashboard,
  };

  return (
    <div>
      <PageHeader
        eyebrow={String(dashboardHero?.eyebrow ?? "Application Detail")}
        title={String(dashboardHero?.title ?? manifest.displayName)}
        summary={<>{String(dashboardHero?.summary ?? manifest.description ?? "该应用未提供额外说明。")}</>}
        actions={
          <>
            <Link className="action-button" href={`/tasks?appId=${encodeURIComponent(manifest.appId)}`}>新建任务</Link>
            <Link className="ghost-button" href="/applications">返回应用清单</Link>
          </>
        }
      />

      {saveError ? <ErrorState title="应用管理操作失败" detail={saveError} /> : null}

      <div className="content-grid tight">
        <Surface>
          <p className="section-kicker">应用身份</p>
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
                <span className="inline-chip">版本 {manifest.version}</span>
                <span className="inline-chip">负责人 {manifest.owner ?? "-"}</span>
                <span className="inline-chip">Prompt {manifest.defaultPromptProfileId ?? "-"}</span>
                <span className="inline-chip">种子模板 {manifest.defaultSeedTemplateId ?? "-"}</span>
                <span className="inline-chip">记忆 {manifest.memoryNamespace ?? manifest.appId}</span>
                <span className="inline-chip">出厂记忆 {manifest.memoryAssetFiles.length}</span>
              </div>
            </article>
          </div>
          <div className="field-actions">
            <button className="action-button" disabled={binding.active || isSaving} onClick={() => void handleActivate()} type="button">
              {binding.active ? "当前激活" : isSaving ? "处理中" : "激活应用"}
            </button>
            <Link className="ghost-button" href={`/tasks?appId=${encodeURIComponent(manifest.appId)}`}>从模板新建任务</Link>
            <Link className="ghost-button" href={`/prompting?appId=${encodeURIComponent(manifest.appId)}`}>查看高级 Prompt</Link>
          </div>
        </Surface>

        <TaskLaunchPanel applications={[launchItem]} compact defaultAppId={manifest.appId} title="从这个应用启动任务" />

        <Surface>
          <p className="section-kicker">模块</p>
          <h3 className="section-title">装配模块</h3>
          <div className="record-list">
            {[...manifest.capabilityModuleIds, ...manifest.sceneModuleIds].map((moduleId) => (
              <article className="record-card" key={moduleId}>
                <div className="record-head">
                  <div>
                    <h4 className="record-title">{moduleId}</h4>
                      <p className="meta-copy">应用装配依赖</p>
                  </div>
                </div>
              </article>
            ))}
          </div>
        </Surface>

        <Surface>
          <p className="section-kicker">配置</p>
          <h3 className="section-title">用户级重要设置</h3>
          <p className="meta-copy">这里写入基座侧 importantConfig，会覆盖应用包 defaults.json。常用字段使用可验证控件，原始 JSON 放在高级模式。</p>
          <div className="settings-grid">
            {fields.map((field) => (
              <div className="form-field" key={field.key}>
                <label className="meta-label" htmlFor={`setting-${field.key}`}>{field.label}</label>
                {field.type === "select" ? (
                  <select
                    className="field-input"
                    id={`setting-${field.key}`}
                    onChange={(event) => setSettingsDraft((current) => ({ ...current, [field.key]: event.target.value }))}
                    value={String(settingsDraft[field.key] ?? "")}
                  >
                    <option value="">未设置</option>
                    {(field.options ?? []).map((option) => (
                      <option key={option.value} value={option.value}>{option.label}</option>
                    ))}
                  </select>
                ) : field.type === "boolean" ? (
                  <label className="toggle-row">
                    <input
                      checked={Boolean(settingsDraft[field.key])}
                      id={`setting-${field.key}`}
                      onChange={(event) => setSettingsDraft((current) => ({ ...current, [field.key]: event.target.checked }))}
                      type="checkbox"
                    />
                    <span>{Boolean(settingsDraft[field.key]) ? "已启用" : "已关闭"}</span>
                  </label>
                ) : field.type === "textarea" ? (
                  <textarea
                    className="field-input field-textarea"
                    id={`setting-${field.key}`}
                    onChange={(event) => setSettingsDraft((current) => ({ ...current, [field.key]: event.target.value }))}
                    value={String(settingsDraft[field.key] ?? "")}
                  />
                ) : (
                  <input
                    className="field-input"
                    id={`setting-${field.key}`}
                    onChange={(event) => setSettingsDraft((current) => ({ ...current, [field.key]: event.target.value }))}
                    type={field.type === "number" ? "number" : "text"}
                    value={String(settingsDraft[field.key] ?? "")}
                  />
                )}
                {field.description ? <p className="meta-copy">{field.description}</p> : null}
              </div>
            ))}
          </div>
          <button className="ghost-button advanced-toggle" onClick={() => setAdvancedConfigOpen((value) => !value)} type="button">
            {advancedConfigOpen ? "收起高级 JSON" : "高级 JSON"}
          </button>
          {advancedConfigOpen ? (
            <div className="form-field">
              <label className="meta-label" htmlFor="application-config">高级配置 JSON</label>
              <textarea className="field-input field-textarea" id="application-config" onChange={(event) => setConfigDraft(event.target.value)} rows={12} value={configDraft} />
            </div>
          ) : null}
          <div className="field-actions">
            <button className="action-button" disabled={isSaving} onClick={() => void handleSaveConfig()} type="button">
              {isSaving ? "保存中" : "保存重要配置"}
            </button>
          </div>
          <pre className="meta-copy mono">{JSON.stringify(detail.data.effectiveConfig, null, 2)}</pre>
        </Surface>

        <Surface>
          <p className="section-kicker">记忆</p>
          <h3 className="section-title">应用出厂记忆</h3>
          <p className="meta-copy">运行时记忆按命名空间隔离，出厂记忆放在应用包内，二者共同组成混合记忆方案。</p>
          <div className="pill-row">
            <span className="inline-chip">命名空间 {manifest.memoryNamespace ?? manifest.appId}</span>
            <span className="inline-chip">出厂文件 {manifest.memoryAssetFiles.length}</span>
          </div>
          {manifest.memoryAssetFiles.length === 0 ? (
            <EmptyState title="没有声明应用记忆资产" detail="这个应用包尚未提供 memory/ 下的静态记忆文件。" />
          ) : (
            <div className="record-list">
              {manifest.memoryAssetFiles.map((filePath) => (
                <article className="record-card" key={filePath}>
                  <div className="record-head">
                    <div>
                      <h4 className="record-title">{filePath}</h4>
                      <p className="meta-copy">应用出厂记忆</p>
                    </div>
                  </div>
                </article>
              ))}
            </div>
          )}
          {memoryAssets.length === 0 ? null : (
            <div className="record-list" style={{ marginTop: 16 }}>
              {memoryAssets.map((asset) => (
                <article className="record-card" key={asset.id}>
                  <div className="record-head">
                    <div>
                      <h4 className="record-title">{asset.name}</h4>
                      <p className="meta-copy">{asset.id} · {asset.version}{asset.sourcePath ? ` · ${asset.sourcePath}` : ""}</p>
                    </div>
                  </div>
                  <pre className="meta-copy mono" style={{ whiteSpace: "pre-wrap" }}>{asset.content}</pre>
                </article>
              ))}
            </div>
          )}
        </Surface>

        <Surface>
          <p className="section-kicker">应用面板</p>
          <h3 className="section-title">应用元数据</h3>
          {quickActions.length === 0 ? (
            <EmptyState title="没有快捷动作" detail="该应用仅提供了最小元数据。" />
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
