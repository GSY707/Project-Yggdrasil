"use client";

import Link from "next/link";
import { useState } from "react";

import type { ApplicationCatalogItem, ServiceHealthSnapshot } from "@yggdrasil/frontend-sdk";

import { localizeDashboard } from "../lib/localized-dashboard";
import { deleteApiJson, postApiJson, useApiResource } from "../lib/use-api-resource";
import { LanguageSwitcher } from "./language-switcher";
import { useTranslation } from "./locale-provider";
import { ErrorState, LoadingState, StatusBadge, Surface } from "./workbench-primitives";

type ApplicationsResponse = { activeAppId: string; applications: ApplicationCatalogItem[] };
type ProviderSettingsResponse = {
  providers: Array<{ id: string; label: string }>;
  status: ServiceHealthSnapshot["providerStatus"];
};

const DEFAULT_APP_IDS = [
  "yggdrasil.app.deep-research",
  "yggdrasil.app.graduate-researcher",
  "yggdrasil.app.coding-greenfield",
  "yggdrasil.app.knowledge-studio",
];

function Icon({ children }: { children: string }) {
  return <span aria-hidden="true" className="material-symbols-outlined">{children}</span>;
}

export function SettingsPage() {
  const { locale, t } = useTranslation();
  const health = useApiResource<ServiceHealthSnapshot>("/health");
  const applications = useApiResource<ApplicationsResponse>("/applications");
  const providerSettings = useApiResource<ProviderSettingsResponse>("/providers");
  const [selectedProvider, setSelectedProvider] = useState("longcat");
  const [apiKey, setApiKey] = useState("");
  const [providerMessage, setProviderMessage] = useState<string | null>(null);
  const [isSavingProvider, setIsSavingProvider] = useState(false);

  async function saveProvider() {
    if (apiKey.trim().length < 8) {
      return;
    }
    setIsSavingProvider(true);
    setProviderMessage(null);
    try {
      await postApiJson(`/providers/${encodeURIComponent(selectedProvider)}`, { apiKey });
      setApiKey("");
      setProviderMessage(t("settings.providerSaved"));
      health.reload();
      providerSettings.reload();
    } catch (error) {
      setProviderMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setIsSavingProvider(false);
    }
  }

  async function removeProvider(providerId: string) {
    setIsSavingProvider(true);
    setProviderMessage(null);
    try {
      await deleteApiJson(`/providers/${encodeURIComponent(providerId)}`);
      setProviderMessage(t("settings.providerRemoved"));
      health.reload();
      providerSettings.reload();
    } catch (error) {
      setProviderMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setIsSavingProvider(false);
    }
  }

  if (health.isLoading || applications.isLoading || providerSettings.isLoading) {
    return <LoadingState title={t("loading.defaultTitle")} />;
  }

  const providerStatus = health.data?.providerStatus;
  const apps = applications.data?.applications ?? [];
  const defaultApps = DEFAULT_APP_IDS.map((appId) => apps.find((item) => item.application.appId === appId)).filter(Boolean) as ApplicationCatalogItem[];
  const providerReady = providerStatus?.status === "ready";
  const visibleApps = defaultApps.length > 0 ? defaultApps : apps.slice(0, 4);

  return (
    <div className="stitch-settings">
      <header className="stitch-settings-header">
        <div>
          <h2>{t("settings.title")}</h2>
          <p>{t("settings.summary")}</p>
        </div>
        <div className="stitch-settings-header-actions">
          <button className="ghost-button" onClick={() => setApiKey("")} type="button">{t("settings.discard")}</button>
          <button className="action-button" disabled={isSavingProvider || apiKey.trim().length < 8} onClick={() => void saveProvider()} type="button">
            {isSavingProvider ? t("settings.saving") : t("settings.save")}
          </button>
        </div>
      </header>

      {health.error ? <ErrorState detail={health.error} title={t("error.defaultTitle")} /> : null}
      {applications.error ? <ErrorState detail={applications.error} title={t("error.defaultTitle")} /> : null}

      <section className="stitch-settings-grid" aria-label={t("settings.title")}>
        <Surface className="stitch-settings-card stitch-settings-language">
          <div className="stitch-settings-card-heading">
            <h3><Icon>language</Icon>{t("settings.languageRegion")}</h3>
            <span>{t("settings.saved")}</span>
          </div>
          <div className="stitch-settings-field">
            <label>{t("settings.language")}</label>
            <LanguageSwitcher />
          </div>
          <div className="stitch-settings-field">
            <label>{t("settings.timeFormat")}</label>
            <div className="stitch-segment-control" aria-label={t("settings.timeFormat")}>
              <button aria-pressed="true" type="button">{t("settings.localAuto")}</button>
              <button aria-pressed="false" type="button">{t("settings.twentyFourHour")}</button>
            </div>
          </div>
        </Surface>

        <Surface className="stitch-settings-card stitch-settings-ai">
          <div className="stitch-settings-card-heading">
            <h3><Icon>psychology</Icon>{t("settings.aiService")}</h3>
          </div>
          <div className="stitch-ai-status">
            <span className="stitch-ai-orb"><Icon>neurology</Icon></span>
            <h4>{providerReady ? t("settings.serviceConnected") : t("settings.serviceUnavailable")}</h4>
            <p>{providerReady ? t("settings.serviceNormal") : t("settings.serviceNeedsSetup")}</p>
          </div>
          <label className="stitch-settings-field">
            <span>{t("settings.provider")}</span>
            <select className="field-input" onChange={(event) => setSelectedProvider(event.target.value)} value={selectedProvider}>
              {(providerSettings.data?.providers ?? []).map((provider) => (
                <option key={provider.id} value={provider.id}>{provider.label}</option>
              ))}
            </select>
          </label>
          <label className="stitch-settings-field">
            <span>{t("settings.apiKey")}</span>
            <input
              autoComplete="new-password"
              className="field-input"
              onChange={(event) => setApiKey(event.target.value)}
              placeholder={t("settings.apiKeyPlaceholder")}
              type="password"
              value={apiKey}
            />
          </label>
          <button className="action-button stitch-settings-save-key" disabled={isSavingProvider || apiKey.trim().length < 8} onClick={() => void saveProvider()} type="button">
            {isSavingProvider ? t("settings.saving") : t("settings.saveKey")}
          </button>
          {providerMessage ? <p className="stitch-settings-message" role="status">{providerMessage}</p> : null}
        </Surface>

        <Surface className="stitch-settings-card stitch-settings-spending">
          <div className="stitch-settings-card-heading">
            <h3><Icon>account_balance_wallet</Icon>{t("settings.spending")}</h3>
            <StatusBadge value={providerReady ? "ready" : "warning"} />
          </div>
          <p>{t("settings.spendingCopy")}</p>
          <div className="stitch-spending-meter" aria-hidden="true"><span /></div>
          <div className="stitch-spending-labels"><span>{t("home.spendingCap")}</span><span>{t("home.notSet")}</span></div>
        </Surface>

        <Surface className="stitch-settings-card stitch-settings-storage">
          <div className="stitch-settings-card-heading">
            <h3><Icon>cloud_done</Icon>{t("settings.localStorage")}</h3>
          </div>
          <div className="stitch-storage-inner">
            <span className="stitch-icon-block"><Icon>folder_special</Icon></span>
            <div>
              <h4>{t("settings.localFirst")}</h4>
              <p>{t("settings.storageCopy")}</p>
            </div>
            <Link className="ghost-button" href="/data-governance"><Icon>backup</Icon>{t("settings.openDataControl")}</Link>
          </div>
        </Surface>

        <Surface className="stitch-settings-card stitch-settings-defaults">
          <div className="stitch-settings-card-heading">
            <h3><Icon>app_registration</Icon>{t("settings.appDefaults")}</h3>
          </div>
          <p>{t("settings.appDefaultsCopy")}</p>
          <div className="stitch-default-app-list">
            {visibleApps.map((item) => {
              const dashboard = item.dashboard ? localizeDashboard(item.dashboard, locale) : undefined;
              return (
                <Link href={`/applications/${encodeURIComponent(item.application.appId)}`} key={item.application.appId}>
                  <span>{item.application.displayName}</span>
                  <small>{dashboard?.hero?.summary ?? t("settings.configure")}</small>
                  <Icon>arrow_forward</Icon>
                </Link>
              );
            })}
          </div>
        </Surface>

        <Surface className="stitch-settings-card stitch-settings-privacy">
          <div className="stitch-settings-card-heading">
            <h3><Icon>security</Icon>{t("settings.dataPrivacy")}</h3>
          </div>
          <p>{t("settings.privacyCopy")}</p>
          <div className="stitch-privacy-list">
            <span><Icon>check</Icon>{t("settings.localFirst")}</span>
            <span><Icon>check</Icon>{t("settings.externalWithService")}</span>
            <span><Icon>warning</Icon>{t("settings.dangerNeedsConfirm")}</span>
          </div>
          <Link className="ghost-button" href="/data-governance">{t("settings.openDataControl")}</Link>
        </Surface>
      </section>

      {(providerSettings.data?.status?.configuredProviders ?? []).length > 0 ? (
        <section className="stitch-configured-providers" aria-label={t("settings.aiService")}>
          {(providerSettings.data?.status?.configuredProviders ?? []).map((provider) => (
            <article key={provider.id}>
              <div>
                <strong>{provider.label}</strong>
                <span>{provider.source === "web-settings" ? t("settings.providerSourceWeb", { hint: provider.keyHint ?? "" }) : t("settings.providerSourceEnv")}</span>
              </div>
              {provider.source === "web-settings" ? (
                <button className="ghost-button" disabled={isSavingProvider} onClick={() => void removeProvider(provider.id)} type="button">{t("settings.remove")}</button>
              ) : null}
            </article>
          ))}
        </section>
      ) : null}
    </div>
  );
}
