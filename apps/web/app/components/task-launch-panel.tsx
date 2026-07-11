"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import type {
  ApplicationCatalogItem,
  ApplicationDashboard,
  ApplicationTaskTemplate,
  ProviderConfigurationStatus,
  ServiceHealthSnapshot,
  TaskLaunchAttachment,
  TaskCreateResponse,
  TaskControlActionResponse,
} from "@yggdrasil/frontend-sdk";

import type { TranslationKey, TranslationValues } from "../i18n";
import { postApiJson, useApiResource } from "../lib/use-api-resource";
import { useTranslation } from "./locale-provider";
import { EmptyState, ErrorState, StatusBadge, Surface } from "./workbench-primitives";

type TaskLaunchPanelProps = {
  applications: ApplicationCatalogItem[];
  defaultAppId?: string | null;
  title?: string;
  compact?: boolean;
  initialAttachments?: TaskLaunchAttachment[];
};

type LaunchTemplate = ApplicationTaskTemplate & {
  appId: string;
};

type Translator = (key: TranslationKey, values?: TranslationValues) => string;

function dashboardFor(item: ApplicationCatalogItem): ApplicationDashboard {
  return item.dashboard ?? {};
}

function templatesFor(item: ApplicationCatalogItem, t: Translator): LaunchTemplate[] {
  const manifest = item.application;
  const dashboard = dashboardFor(item);
  const templates = Array.isArray(dashboard.taskTemplates) ? dashboard.taskTemplates : [];
  if (templates.length > 0) {
    return templates.map((template) => ({
      ...template,
      appId: manifest.appId,
    }));
  }

  return [
    {
      id: "default",
      appId: manifest.appId,
      title: t("taskLaunch.defaultTemplateTitle", { name: manifest.displayName }),
      goal: dashboard.hero?.summary ?? manifest.description ?? t("taskLaunch.defaultTemplateGoal", { name: manifest.displayName }),
      description: t("taskLaunch.defaultTemplateDescription"),
      currentFocus: "first-task",
      currentObjective: dashboard.hero?.title ?? manifest.displayName,
      taskType: "general",
      startPayload: {},
    },
  ];
}

function asRecord(value: unknown): Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value) ? (value as Record<string, unknown>) : {};
}

function stringValue(value: unknown): string | undefined {
  return typeof value === "string" && value.trim().length > 0 ? value.trim() : undefined;
}

function stringList(value: unknown): string[] {
  return Array.isArray(value)
    ? value.map((item) => String(item ?? "").trim()).filter((item) => item.length > 0)
    : [];
}

function attachmentContext(attachments: TaskLaunchAttachment[]) {
  return attachments.map((attachment) => ({
    assetId: attachment.assetId,
    label: attachment.label,
    sourceUri: attachment.sourceUri,
    summaryNodeId: attachment.summaryNodeId,
    segmentCount: attachment.segmentCount,
    summary: attachment.summary,
  }));
}

function goalWithAttachments(goal: string, attachments: TaskLaunchAttachment[], t: Translator): string {
  if (attachments.length === 0) {
    return goal;
  }
  const lines = attachments.map((attachment, index) => {
    const label = attachment.label ?? attachment.sourceUri ?? attachment.assetId;
    const summary = attachment.summary ? t("taskLaunch.attachmentSummary", { summary: attachment.summary }) : "";
    const node = attachment.summaryNodeId ? t("taskLaunch.attachmentNode", { node: attachment.summaryNodeId }) : "";
    return t("taskLaunch.attachmentLine", { index: index + 1, label, assetId: attachment.assetId, node, summary });
  });
  return `${goal}\n\n${t("taskLaunch.attachmentsHeading")}\n${lines.join("\n")}`;
}

function buildStartPayload(item: ApplicationCatalogItem, template: LaunchTemplate, attachments: TaskLaunchAttachment[]) {
  const importantConfig = asRecord(item.configBinding.importantConfig);
  const startPayload = asRecord(template.startPayload);
  const provider = stringValue(importantConfig.provider) ?? stringValue(importantConfig.selectedProvider) ?? stringValue(startPayload.selectedProvider);
  const model = stringValue(importantConfig.model) ?? stringValue(importantConfig.selectedModel) ?? stringValue(startPayload.selectedModel);
  const activeCapabilities = Array.isArray(startPayload.activeCapabilities)
    ? startPayload.activeCapabilities
    : item.application.capabilityModuleIds;

  return {
    ...startPayload,
    appId: item.application.appId,
    taskType: template.taskType ?? startPayload.taskType ?? asRecord(item.configBinding.importantConfig).defaultTaskType ?? "general",
    activeCapabilities,
    currentFocus: template.currentFocus ?? startPayload.currentFocus,
    currentObjective: template.currentObjective ?? template.goal,
    selectedProvider: provider,
    selectedModel: model,
    attachedAssets: attachmentContext(attachments),
    requestedBy: { type: "user", id: "web-workbench" },
    reason: "web-first-task-launch",
  };
}

function explainLaunchError(rawError: string, stage: "create" | "start", t: Translator): string {
  const lower = rawError.toLowerCase();
  if (lower.includes("failed to fetch") || lower.includes("econnrefused") || lower.includes("connection refused")) {
    return t("taskLaunch.errorService");
  }
  if (lower.includes("database") || lower.includes("sqlalchemy") || lower.includes("psycopg")) {
    return t("taskLaunch.errorDatabase");
  }
  if (lower.includes("redis") || lower.includes("coordination") || lower.includes("queue")) {
    return t("taskLaunch.errorQueue");
  }
  if (lower.includes("provider") || lower.includes("api key") || lower.includes("no configured")) {
    return t("taskLaunch.errorProvider");
  }
  if (lower.includes("application") || lower.includes("app")) {
    return t("taskLaunch.errorApplication");
  }
  if (stage === "start") {
    return t("taskLaunch.errorStart");
  }
  return t("taskLaunch.errorCreate");
}

function ProviderReadiness({ error, isLoading, status }: { error?: string | null; isLoading?: boolean; status?: ProviderConfigurationStatus }) {
  const { t } = useTranslation();
  if (isLoading) {
    return (
      <div className="launch-template">
        <div className="record-head">
          <div>
          <p className="meta-label">{t("taskLaunch.provider")}</p>
          <h4 className="record-title">{t("taskLaunch.providerChecking")}</h4>
          <p className="meta-copy">{t("taskLaunch.providerCheckingCopy")}</p>
          </div>
          <StatusBadge value="pending" />
        </div>
      </div>
    );
  }
  if (error) {
    return (
      <div className="launch-template">
        <div className="record-head">
          <div>
          <p className="meta-label">{t("taskLaunch.provider")}</p>
          <h4 className="record-title">{t("taskLaunch.providerUnavailable")}</h4>
          <p className="meta-copy">{t("taskLaunch.providerUnavailableCopy")}</p>
          </div>
          <StatusBadge value="blocked" />
        </div>
      </div>
    );
  }
  if (!status) {
    return null;
  }
  const configuredLabels = status.configuredProviders.map((provider) => provider.label);
  const statusCopy =
    status.status === "ready"
      ? t("taskLaunch.providerReady")
      : status.status === "warning"
        ? t("taskLaunch.providerWarning")
        : t("taskLaunch.providerBlocked");
  return (
    <div className="launch-template">
      <div className="record-head">
        <div>
          <p className="meta-label">{t("taskLaunch.provider")}</p>
          <h4 className="record-title">
            {status.status === "ready" ? t("taskLaunch.providerReadyTitle") : status.status === "warning" ? t("taskLaunch.providerWarningTitle") : t("taskLaunch.providerBlockedTitle")}
          </h4>
          <p className="meta-copy">{statusCopy}</p>
        </div>
        <StatusBadge value={status.status} />
      </div>
      {configuredLabels.length > 0 ? (
        <div className="pill-row">
          {configuredLabels.map((label) => (
            <span className="inline-chip" key={label}>
              {label}
            </span>
          ))}
        </div>
      ) : (
        <p className="meta-copy">{t("taskLaunch.providerNoConfigured")}</p>
      )}
      {status.remediation ? <p className="meta-copy">{status.remediation}</p> : null}
    </div>
  );
}

export function TaskLaunchPanel({
  applications,
  defaultAppId,
  title,
  compact = false,
  initialAttachments = [],
}: TaskLaunchPanelProps) {
  const { t } = useTranslation();
  const router = useRouter();
  const health = useApiResource<ServiceHealthSnapshot>("/health");
  const providerStatus = health.data?.providerStatus;
  const providerStartBlocked = providerStatus?.status !== "ready";
  const [selectedAppId, setSelectedAppId] = useState(defaultAppId ?? applications.find((item) => item.configBinding.active)?.application.appId ?? applications[0]?.application.appId ?? "");
  const selectedApp = applications.find((item) => item.application.appId === selectedAppId) ?? applications[0];
  const templates = useMemo(() => (selectedApp ? templatesFor(selectedApp, t) : []), [selectedApp, t]);
  const [selectedTemplateId, setSelectedTemplateId] = useState(templates[0]?.id ?? "");
  const selectedTemplate = templates.find((template) => template.id === selectedTemplateId) ?? templates[0];
  const [taskTitle, setTaskTitle] = useState(selectedTemplate?.title ?? "");
  const [taskGoal, setTaskGoal] = useState(selectedTemplate?.goal ?? "");
  const [createdTaskId, setCreatedTaskId] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [launchError, setLaunchError] = useState<string | null>(null);

  useEffect(() => {
    const nextAppId = defaultAppId ?? applications.find((item) => item.configBinding.active)?.application.appId ?? applications[0]?.application.appId ?? "";
    if (nextAppId && nextAppId !== selectedAppId && !applications.some((item) => item.application.appId === selectedAppId)) {
      setSelectedAppId(nextAppId);
    }
  }, [applications, defaultAppId, selectedAppId]);

  useEffect(() => {
    const nextTemplate = templates.find((template) => template.id === selectedTemplateId) ?? templates[0];
    if (!nextTemplate) {
      setSelectedTemplateId("");
      setTaskTitle("");
      setTaskGoal("");
      return;
    }
    setSelectedTemplateId(nextTemplate.id);
    setTaskTitle(nextTemplate.title);
    setTaskGoal(nextTemplate.goal);
  }, [selectedTemplateId, templates]);

  async function createTask(): Promise<string> {
    if (!selectedApp || !selectedTemplate) {
      throw new Error(t("taskLaunch.errorApplication"));
    }
    const budget = asRecord(selectedTemplate.budget);
    const effectiveGoal = taskGoal.trim() || selectedTemplate.goal;
    const effectiveObjective = selectedTemplate.currentObjective ?? effectiveGoal;
    const payload = {
      appId: selectedApp.application.appId,
      title: taskTitle.trim() || selectedTemplate.title,
      goal: goalWithAttachments(effectiveGoal, initialAttachments, t),
      currentFocus: selectedTemplate.currentFocus ?? "web-launch",
      currentObjective: goalWithAttachments(effectiveObjective, initialAttachments, t),
      budget: budget,
      status: "draft",
    };
    const response = await postApiJson<TaskCreateResponse>("/tasks", payload);
    const taskId = response.task.id;
    setCreatedTaskId(taskId);
    return taskId;
  }

  async function handleCreateOnly() {
    setIsSubmitting(true);
    setLaunchError(null);
    try {
      await createTask();
    } catch (error) {
      setLaunchError(explainLaunchError(error instanceof Error ? error.message : String(error), "create", t));
    } finally {
      setIsSubmitting(false);
    }
  }

  async function startTask(taskId: string) {
    if (!selectedApp || !selectedTemplate) {
      throw new Error(t("taskLaunch.errorApplication"));
    }
    await postApiJson<TaskControlActionResponse>(`/tasks/${encodeURIComponent(taskId)}/start`, buildStartPayload(selectedApp, selectedTemplate, initialAttachments));
    router.push(`/tasks/${encodeURIComponent(taskId)}`);
  }

  async function handleCreateAndStart() {
    setIsSubmitting(true);
    setLaunchError(null);
    try {
      const taskId = createdTaskId ?? await createTask();
      await startTask(taskId);
    } catch (error) {
      setLaunchError(explainLaunchError(error instanceof Error ? error.message : String(error), createdTaskId ? "start" : "create", t));
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleStartCreated() {
    if (!createdTaskId) {
      return;
    }
    setIsSubmitting(true);
    setLaunchError(null);
    try {
      await startTask(createdTaskId);
    } catch (error) {
      setLaunchError(explainLaunchError(error instanceof Error ? error.message : String(error), "start", t));
    } finally {
      setIsSubmitting(false);
    }
  }

  if (applications.length === 0) {
    return <EmptyState title={t("taskLaunch.noApps")} detail={t("taskLaunch.noAppsDetail")} />;
  }

  return (
    <Surface className={compact ? "task-launch compact" : "task-launch"}>
      <div className="record-head">
        <div>
          <p className="section-kicker">{t("taskLaunch.eyebrow")}</p>
          <h3 className="section-title">{title ?? t("taskLaunch.title")}</h3>
          <p className="section-copy">{t("taskLaunch.summary")}</p>
        </div>
        {selectedApp ? <StatusBadge value={selectedApp.configBinding.active ? "active" : "available"} /> : null}
      </div>

      <ProviderReadiness error={health.error} isLoading={health.isLoading} status={providerStatus} />

      {launchError ? <ErrorState title={t("taskLaunch.failed")} detail={launchError} /> : null}

      <div className="launch-grid">
        <div className="form-field">
          <label className="meta-label" htmlFor="launch-app">{t("taskLaunch.application")}</label>
          <select className="field-input" disabled={compact || isSubmitting} id="launch-app" onChange={(event) => setSelectedAppId(event.target.value)} value={selectedApp?.application.appId ?? ""}>
            {applications.map((item) => (
              <option key={item.application.appId} value={item.application.appId}>
                {item.application.displayName}
              </option>
            ))}
          </select>
        </div>
        <div className="form-field">
          <label className="meta-label" htmlFor="launch-template">{t("taskLaunch.template")}</label>
          <select className="field-input" disabled={isSubmitting} id="launch-template" onChange={(event) => setSelectedTemplateId(event.target.value)} value={selectedTemplate?.id ?? ""}>
            {templates.map((template) => (
              <option key={template.id} value={template.id}>
                {template.title}
              </option>
            ))}
          </select>
        </div>
      </div>

      {selectedTemplate ? (
        <div className="launch-template">
          <p className="meta-label">{t("taskLaunch.templateDescription")}</p>
          <p className="meta-copy">{selectedTemplate.description ?? selectedTemplate.goal}</p>
          {stringList(selectedTemplate.exampleTasks).length > 0 || stringList(selectedTemplate.expectedOutputs).length > 0 ? (
            <div className="launch-detail-grid">
              <div>
                <p className="meta-label">{t("taskLaunch.exampleTasks")}</p>
                <ul className="mini-list">
                  {stringList(selectedTemplate.exampleTasks).map((example) => (
                    <li key={example}>{example}</li>
                  ))}
                </ul>
              </div>
              <div>
                <p className="meta-label">{t("taskLaunch.expectedOutputs")}</p>
                <ul className="mini-list">
                  {stringList(selectedTemplate.expectedOutputs).map((output) => (
                    <li key={output}>{output}</li>
                  ))}
                </ul>
              </div>
            </div>
          ) : null}
        </div>
      ) : null}

      {initialAttachments.length > 0 ? (
        <div className="launch-template">
          <p className="meta-label">{t("taskLaunch.attachments")}</p>
          <div className="record-list compact-list">
            {initialAttachments.map((attachment) => (
              <article className="compact-record" key={attachment.assetId}>
                <div>
                  <h4 className="record-title">{attachment.label ?? attachment.sourceUri ?? attachment.assetId}</h4>
                  <p className="meta-copy">{attachment.summary ?? t("taskLaunch.attachmentFallback")}</p>
                </div>
                <div className="pill-row">
                  <span className="inline-chip">{t("taskLaunch.asset", { id: attachment.assetId })}</span>
                {attachment.summaryNodeId ? <span className="inline-chip">{t("taskLaunch.summaryCreated")}</span> : null}
                  {attachment.segmentCount ? <span className="inline-chip">{t("taskLaunch.segmentCount", { count: attachment.segmentCount })}</span> : null}
                </div>
              </article>
            ))}
          </div>
        </div>
      ) : null}

      <div className="form-grid">
        <div className="form-field">
          <label className="meta-label" htmlFor="launch-title">{t("taskLaunch.taskTitle")}</label>
          <input className="field-input" disabled={isSubmitting} id="launch-title" onChange={(event) => setTaskTitle(event.target.value)} value={taskTitle} />
        </div>
        <div className="form-field">
          <label className="meta-label" htmlFor="launch-goal">{t("taskLaunch.goal")}</label>
          <textarea className="field-input field-textarea" disabled={isSubmitting} id="launch-goal" onChange={(event) => setTaskGoal(event.target.value)} value={taskGoal} />
        </div>
      </div>

      {selectedApp ? (
        <div className="pill-row">
          <span className="inline-chip">{t("taskLaunch.appChip", { name: selectedApp.application.displayName })}</span>
          <span className="inline-chip">{t("taskLaunch.templateChip", { name: selectedTemplate?.title ?? t("taskLaunch.defaultTemplate") })}</span>
          <span className="inline-chip">{t("taskLaunch.preStartConfirm")}</span>
        </div>
      ) : null}

      <div className="field-actions">
        <button className="action-button" disabled={isSubmitting || !selectedTemplate || providerStartBlocked} onClick={() => void handleCreateAndStart()} type="button">
          {isSubmitting ? t("taskLaunch.processing") : createdTaskId ? t("taskLaunch.startCreated") : t("taskLaunch.createAndStart")}
        </button>
        <button className="ghost-button" disabled={isSubmitting || !selectedTemplate} onClick={() => void handleCreateOnly()} type="button">
          {t("taskLaunch.createDraft")}
        </button>
        {createdTaskId ? (
          <button className="ghost-button" disabled={isSubmitting || providerStartBlocked} onClick={() => void handleStartCreated()} type="button">
            {t("taskLaunch.startNow")}
          </button>
        ) : null}
      </div>

      {createdTaskId ? (
        <div className="field-actions">
          <p className="meta-copy mono">{t("taskLaunch.created", { id: createdTaskId })}</p>
          <Link className="ghost-button" href={`/tasks/${encodeURIComponent(createdTaskId)}`}>{t("taskLaunch.viewTask")}</Link>
        </div>
      ) : null}
    </Surface>
  );
}
