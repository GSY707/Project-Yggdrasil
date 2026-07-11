"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import type {
  ApplicationConfigBinding,
  ApplicationDashboard,
  ApplicationManifestSummary,
  ApplicationMemoryAssetRecord,
  ApplicationSettingsField,
} from "@yggdrasil/frontend-sdk";

import { localizeDashboard } from "../lib/localized-dashboard";
import { localizedText } from "../i18n";
import { postApiJson, useApiResource } from "../lib/use-api-resource";
import { useTranslation } from "./locale-provider";
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

function localizeSettingsSchema(fields: ApplicationSettingsField[], locale: string): ApplicationSettingsField[] {
  if (locale !== "en") {
    return fields;
  }
  const labels: Record<string, { label: string; description: string }> = {
    provider: { label: "AI service", description: "Default model provider." },
    model: { label: "Default model", description: "Default model name." },
    tokenBudgetTotal: { label: "Token budget", description: "Default task token budget." },
    costBudgetTotal: { label: "Spending cap", description: "Default task cost budget in USD." },
    workspace: { label: "Workspace", description: "Default workspace or material directory." },
    outputStyle: { label: "Output style", description: "Default output style requirements." },
    memoryNamespace: { label: "Knowledge scope", description: "Runtime memory namespace." },
    toolPermissions: { label: "Tool permissions", description: "Default tool permission strength." },
  };
  const optionLabels: Record<string, string> = { 保守: "Conservative", "工具丰富": "Tool-rich", 不限制: "Unrestricted" };
  return fields.map((field) => {
    const override = labels[field.key];
    return {
      ...field,
      label: override?.label ?? field.label,
      description: override?.description ?? field.description,
      options: field.options?.map((option) => ({ ...option, label: optionLabels[option.label] ?? option.label })),
    };
  });
}

function parseSettingsDraft(fields: ApplicationSettingsField[], draft: Record<string, string | number | boolean>, locale: string): Record<string, unknown> {
  const parsed: Record<string, unknown> = {};
  for (const field of fields) {
    const value = draft[field.key];
    if (field.required && (value === "" || value === undefined || value === null)) {
      throw new Error(`${field.label}${localizedText(locale as "zh-CN" | "en", " 是必填项。", " is required.")}`);
    }
    if (value === "" || value === undefined || value === null) {
      continue;
    }
    if (field.type === "number") {
      const numeric = Number(value);
      if (!Number.isFinite(numeric)) {
        throw new Error(`${field.label}${localizedText(locale as "zh-CN" | "en", " 必须是数字。", " must be a number.")}`);
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

function settingLabel(field: ApplicationSettingsField, locale: string): string {
  if (locale !== "en") {
    return field.label;
  }
  const labels: Record<string, string> = {
    provider: "AI service",
    model: "Default model",
    tokenBudgetTotal: "Token budget",
    costBudgetTotal: "Spending cap",
    workspace: "Workspace",
    outputStyle: "Output style",
    memoryNamespace: "Knowledge scope",
    toolPermissions: "Tool permissions",
  };
  return labels[field.key] ?? field.label;
}

export function ApplicationDetailPage({ appId }: { appId: string }) {
  const { locale, t } = useTranslation();
  const detail = useApiResource<ApplicationDetailResponse>(`/applications/${encodeURIComponent(appId)}`);
  const [configDraft, setConfigDraft] = useState("{}");
  const [settingsDraft, setSettingsDraft] = useState<Record<string, string | number | boolean>>({});
  const [advancedConfigOpen, setAdvancedConfigOpen] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    if (detail.data?.configBinding) {
      setConfigDraft(JSON.stringify(detail.data.configBinding.importantConfig ?? {}, null, 2));
      const dashboard = localizeDashboard(dashboardPayload(detail.data.dashboard), locale);
      const fields = localizeSettingsSchema(settingsSchema(dashboard), locale);
      const sourceConfig = {
        ...asRecord(detail.data.effectiveConfig),
        ...asRecord(detail.data.configBinding.importantConfig),
      };
      setSettingsDraft(Object.fromEntries(fields.map((field) => [field.key, settingValue(sourceConfig, field)])));
    }
  }, [detail.data?.configBinding, detail.data?.dashboard, detail.data?.effectiveConfig, locale]);

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
      const fields = localizeSettingsSchema(settingsSchema(dashboard), locale);
      const advancedConfig = JSON.parse(configDraft) as Record<string, unknown>;
      const typedConfig = parseSettingsDraft(fields, settingsDraft, locale);
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
    return <LoadingState title={t("applicationDetail.loading")} />;
  }

  if (detail.error) {
    return <ErrorState detail={detail.error} title={t("applicationDetail.errorTitle")} />;
  }

  if (!detail.data) {
    return <EmptyState title={t("applicationDetail.missingTitle")} detail={t("applicationDetail.missingDetail")} />;
  }

  const manifest = detail.data.application;
  const binding = detail.data.configBinding;
  const memoryAssets = detail.data.applicationMemoryAssets ?? [];
  const dashboard = localizeDashboard(dashboardPayload(detail.data.dashboard), locale);
  const fields = localizeSettingsSchema(settingsSchema(dashboard), locale);
  const dashboardHero = typeof dashboard.hero === "object" ? dashboard.hero as Record<string, unknown> : null;
  const quickActions = Array.isArray(dashboard.quickActions) ? dashboard.quickActions as Array<Record<string, unknown>> : [];
  return (
    <div className="application-detail-page">
      <PageHeader
        eyebrow={String(dashboardHero?.eyebrow ?? t("applicationDetail.eyebrow"))}
        title={String(dashboardHero?.title ?? manifest.displayName)}
        summary={<>{String(dashboardHero?.summary ?? manifest.description ?? t("applicationDetail.heroFallback"))}</>}
        actions={
          <>
            <Link className="action-button" href={`/tasks?appId=${encodeURIComponent(manifest.appId)}`}>{t("applicationDetail.startTask")}</Link>
            <Link className="ghost-button" href="/applications">{t("applicationDetail.back")}</Link>
          </>
        }
      />

      {saveError ? <ErrorState title={t("applicationDetail.saveError")} detail={saveError} /> : null}

      <div className="content-grid tight">
        <Surface>
          <p className="section-kicker">{t("applicationDetail.eyebrow")}</p>
          <h3 className="section-title">{t("applicationDetail.prerequisites")}</h3>
          <div className="record-list">
            <article className="record-card">
              <div className="record-head">
                <div>
                  <h4 className="record-title">{manifest.displayName}</h4>
                  <p className="meta-copy">{manifest.description ?? dashboard.hero?.summary ?? t("applicationDetail.heroFallback")}</p>
                </div>
                <StatusBadge value={binding.active ? "active" : manifest.defaultLoad ? "default" : "inactive"} />
              </div>
              <div className="pill-row">
                <span className="inline-chip">{locale === "en" ? "Version" : "版本"} {manifest.version}</span>
                <span className="inline-chip">{t("applicationDetail.templates")} {dashboard.taskTemplates?.length ?? 0}</span>
                <span className="inline-chip">{locale === "en" ? "Settings" : "默认设置"} {fields.length}</span>
                <span className="inline-chip">{t("applicationDetail.memory")} {manifest.memoryAssetFiles.length}</span>
              </div>
            </article>
          </div>
          <div className="field-actions">
            <button className="action-button" disabled={binding.active || isSaving} onClick={() => void handleActivate()} type="button">
              {binding.active ? t("applicationDetail.active") : isSaving ? t("applicationDetail.processing") : t("applicationDetail.activate")}
            </button>
            <Link className="ghost-button" href={`/tasks?appId=${encodeURIComponent(manifest.appId)}`}>{t("applicationDetail.createDraft")}</Link>
            <Link className="ghost-button" href="/settings">{t("nav.settings.label")}</Link>
          </div>
        </Surface>

        <Surface className="application-how-it-works">
          <p className="section-kicker">{t("applicationDetail.howItWorks")}</p>
          <h3 className="section-title">{t("applicationDetail.howItWorks")}</h3>
          <ol className="application-step-list">
            {["applicationDetail.step1", "applicationDetail.step2", "applicationDetail.step3", "applicationDetail.step4"].map((key, index) => (
              <li key={key}><span>{index + 1}</span>{t(key as "applicationDetail.step1" | "applicationDetail.step2" | "applicationDetail.step3" | "applicationDetail.step4")}</li>
            ))}
          </ol>
          <Link className="ghost-button" href={`/tasks?appId=${encodeURIComponent(manifest.appId)}`}>{t("applicationDetail.createDraft")}</Link>
        </Surface>

        <Surface>
          <p className="section-kicker">{t("applicationDetail.maintainer")}</p>
          <h3 className="section-title">{t("applicationDetail.modules")}</h3>
          <p className="section-copy">{t("applicationDetail.maintainerCopy")}</p>
          <div className="record-list">
            {[...manifest.capabilityModuleIds, ...manifest.sceneModuleIds].map((moduleId) => (
              <article className="record-card" key={moduleId}>
                <div className="record-head">
                  <div>
                    <h4 className="record-title">{moduleId}</h4>
                      <p className="meta-copy">{t("applicationDetail.modules")}</p>
                  </div>
                </div>
              </article>
            ))}
          </div>
        </Surface>

        <Surface>
          <p className="section-kicker">{t("settings.appDefaults")}</p>
          <h3 className="section-title">{t("applicationDetail.configuration")}</h3>
          <p className="meta-copy">{t("applicationDetail.configurationCopy")}</p>
          <div className="settings-grid">
            {fields.map((field) => (
              <div className="form-field" key={field.key}>
                <label className="meta-label" htmlFor={`setting-${field.key}`}>{settingLabel(field, locale)}</label>
                {field.type === "select" ? (
                  <select
                    className="field-input"
                    id={`setting-${field.key}`}
                    onChange={(event) => setSettingsDraft((current) => ({ ...current, [field.key]: event.target.value }))}
                    value={String(settingsDraft[field.key] ?? "")}
                  >
                    <option value="">{t("applicationDetail.notSet")}</option>
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
                    <span>{Boolean(settingsDraft[field.key]) ? t("applicationDetail.enabled") : t("applicationDetail.disabled")}</span>
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
            {advancedConfigOpen ? t("applicationDetail.maintainer") : t("applicationDetail.maintainer")}
          </button>
          {advancedConfigOpen ? (
            <div className="form-field">
              <label className="meta-label" htmlFor="application-config">{t("applicationDetail.maintainer")}</label>
              <textarea className="field-input field-textarea" id="application-config" onChange={(event) => setConfigDraft(event.target.value)} rows={12} value={configDraft} />
            </div>
          ) : null}
          <div className="field-actions">
            <button className="action-button" disabled={isSaving} onClick={() => void handleSaveConfig()} type="button">
              {isSaving ? t("applicationDetail.saving") : t("applicationDetail.saveSettings")}
            </button>
          </div>
        </Surface>

        <Surface>
          <p className="section-kicker">{t("applicationDetail.memory")}</p>
          <h3 className="section-title">{t("applicationDetail.memory")}</h3>
          <p className="meta-copy">{t("applicationDetail.maintainerCopy")}</p>
          <div className="pill-row">
            <span className="inline-chip">{t("applicationDetail.memory")} {manifest.memoryAssetFiles.length}</span>
          </div>
          {manifest.memoryAssetFiles.length === 0 ? (
            <EmptyState title={t("applicationDetail.noMemory")} detail={t("applicationDetail.noMemoryCopy")} />
          ) : (
            <div className="record-list">
              {manifest.memoryAssetFiles.map((filePath) => (
                <article className="record-card" key={filePath}>
                  <div className="record-head">
                    <div>
                      <h4 className="record-title">{filePath}</h4>
                      <p className="meta-copy">{t("applicationDetail.memory")}</p>
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
          <p className="section-kicker">{t("applicationDetail.quickActions")}</p>
          <h3 className="section-title">{t("applicationDetail.quickActions")}</h3>
          {quickActions.length === 0 ? (
            <EmptyState title={t("applicationDetail.noQuickActions")} detail={t("applicationDetail.createDraft")} />
          ) : (
            <div className="record-list">
              {quickActions.map((action, index) => (
                <article className="record-card" key={`${String(action.label ?? "action")}-${index}`}>
                  <div className="record-head">
                    <div>
                      <h4 className="record-title">{String(action.label ?? `Action ${index + 1}`)}</h4>
                      <p className="meta-copy">{String(action.href ?? "")}</p>
                    </div>
                    {typeof action.href === "string" ? <Link className="ghost-button" href={action.href}>{t("applicationDetail.open")}</Link> : null}
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
