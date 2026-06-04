"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import type {
  ApplicationCatalogItem,
  ApplicationDashboard,
  ApplicationTaskTemplate,
  TaskLaunchAttachment,
  TaskCreateResponse,
  TaskControlActionResponse,
} from "@yggdrasil/frontend-sdk";

import { postApiJson } from "../lib/use-api-resource";
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

function dashboardFor(item: ApplicationCatalogItem): ApplicationDashboard {
  return item.dashboard ?? {};
}

function templatesFor(item: ApplicationCatalogItem): LaunchTemplate[] {
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
      title: `${manifest.displayName} task`,
      goal: dashboard.hero?.summary ?? manifest.description ?? `Run ${manifest.displayName}.`,
      description: "使用应用默认 prompt、场景和能力启动一个新任务。",
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

function goalWithAttachments(goal: string, attachments: TaskLaunchAttachment[]): string {
  if (attachments.length === 0) {
    return goal;
  }
  const lines = attachments.map((attachment, index) => {
    const label = attachment.label ?? attachment.sourceUri ?? attachment.assetId;
    const summary = attachment.summary ? `；摘要：${attachment.summary}` : "";
    const node = attachment.summaryNodeId ? `；摘要节点：${attachment.summaryNodeId}` : "";
    return `${index + 1}. ${label}（素材 ${attachment.assetId}${node}${summary}）`;
  });
  return `${goal}\n\n已附加素材：\n${lines.join("\n")}`;
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

function explainLaunchError(rawError: string, stage: "create" | "start"): string {
  const lower = rawError.toLowerCase();
  if (lower.includes("failed to fetch") || lower.includes("econnrefused") || lower.includes("connection refused")) {
    return "Core API 不可访问。请确认 `uv run yggdrasil-core-api` 正在运行，或使用 `corepack pnpm yggdrasil:up` 启动本地产品模式。";
  }
  if (lower.includes("database") || lower.includes("sqlalchemy") || lower.includes("psycopg")) {
    return "数据库不可用。请启动本地依赖并执行迁移：`corepack pnpm infra:up`，然后 `uv run alembic upgrade head`。";
  }
  if (lower.includes("redis") || lower.includes("coordination") || lower.includes("queue")) {
    return "运行队列不可用。请确认 Redis 已启动，并启动 worker：`uv run yggdrasil-worker --serve`。";
  }
  if (lower.includes("provider") || lower.includes("api key") || lower.includes("no configured")) {
    return "模型供应商未配置。请在 `.env` 设置至少一个 provider key，例如 `YGGDRASIL_LLM_API_KEY_LONGCAT` 或 `LONGCAT_API_KEY`。";
  }
  if (lower.includes("application") || lower.includes("app")) {
    return "没有可用应用或应用未正确装配。请先在应用页面激活应用，再重新启动任务。";
  }
  if (stage === "start") {
    return `任务已创建但启动失败：${rawError}。若任务长时间停在 queued，请确认 worker 正在运行。`;
  }
  return rawError;
}

export function TaskLaunchPanel({
  applications,
  defaultAppId,
  title = "新建并启动任务",
  compact = false,
  initialAttachments = [],
}: TaskLaunchPanelProps) {
  const router = useRouter();
  const [selectedAppId, setSelectedAppId] = useState(defaultAppId ?? applications.find((item) => item.configBinding.active)?.application.appId ?? applications[0]?.application.appId ?? "");
  const selectedApp = applications.find((item) => item.application.appId === selectedAppId) ?? applications[0];
  const templates = useMemo(() => (selectedApp ? templatesFor(selectedApp) : []), [selectedApp]);
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
      throw new Error("没有可启动的应用。请先激活一个应用。");
    }
    const budget = asRecord(selectedTemplate.budget);
    const effectiveGoal = taskGoal.trim() || selectedTemplate.goal;
    const effectiveObjective = selectedTemplate.currentObjective ?? effectiveGoal;
    const payload = {
      appId: selectedApp.application.appId,
      title: taskTitle.trim() || selectedTemplate.title,
      goal: goalWithAttachments(effectiveGoal, initialAttachments),
      currentFocus: selectedTemplate.currentFocus ?? "web-launch",
      currentObjective: goalWithAttachments(effectiveObjective, initialAttachments),
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
      setLaunchError(explainLaunchError(error instanceof Error ? error.message : String(error), "create"));
    } finally {
      setIsSubmitting(false);
    }
  }

  async function startTask(taskId: string) {
    if (!selectedApp || !selectedTemplate) {
      throw new Error("没有可启动的应用。请先激活一个应用。");
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
      setLaunchError(explainLaunchError(error instanceof Error ? error.message : String(error), createdTaskId ? "start" : "create"));
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
      setLaunchError(explainLaunchError(error instanceof Error ? error.message : String(error), "start"));
    } finally {
      setIsSubmitting(false);
    }
  }

  if (applications.length === 0) {
    return <EmptyState title="没有可启动应用" detail="应用目录还没有被 Core API 发现，无法创建第一任务。" />;
  }

  return (
    <Surface className={compact ? "task-launch compact" : "task-launch"}>
      <div className="record-head">
        <div>
          <p className="section-kicker">新任务</p>
          <h3 className="section-title">{title}</h3>
          <p className="section-copy">选择应用模板后创建任务。创建完成后可以立刻启动并进入任务详情页。</p>
        </div>
        {selectedApp ? <StatusBadge value={selectedApp.configBinding.active ? "active" : "available"} /> : null}
      </div>

      {launchError ? <ErrorState title="任务启动失败" detail={launchError} /> : null}

      <div className="launch-grid">
        <div className="form-field">
          <label className="meta-label" htmlFor="launch-app">应用</label>
          <select className="field-input" disabled={compact || isSubmitting} id="launch-app" onChange={(event) => setSelectedAppId(event.target.value)} value={selectedApp?.application.appId ?? ""}>
            {applications.map((item) => (
              <option key={item.application.appId} value={item.application.appId}>
                {item.application.displayName}
              </option>
            ))}
          </select>
        </div>
        <div className="form-field">
          <label className="meta-label" htmlFor="launch-template">任务模板</label>
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
          <p className="meta-label">模板说明</p>
          <p className="meta-copy">{selectedTemplate.description ?? selectedTemplate.goal}</p>
          {stringList(selectedTemplate.exampleTasks).length > 0 || stringList(selectedTemplate.expectedOutputs).length > 0 ? (
            <div className="launch-detail-grid">
              <div>
                <p className="meta-label">示例任务</p>
                <ul className="mini-list">
                  {stringList(selectedTemplate.exampleTasks).map((example) => (
                    <li key={example}>{example}</li>
                  ))}
                </ul>
              </div>
              <div>
                <p className="meta-label">预期产物</p>
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
          <p className="meta-label">已附加素材</p>
          <div className="record-list compact-list">
            {initialAttachments.map((attachment) => (
              <article className="compact-record" key={attachment.assetId}>
                <div>
                  <h4 className="record-title">{attachment.label ?? attachment.sourceUri ?? attachment.assetId}</h4>
                  <p className="meta-copy">{attachment.summary ?? "任务启动时会把这个素材作为输入上下文。"}</p>
                </div>
                <div className="pill-row">
                  <span className="inline-chip">素材 {attachment.assetId}</span>
                  {attachment.summaryNodeId ? <span className="inline-chip">摘要节点 {attachment.summaryNodeId}</span> : null}
                  {attachment.segmentCount ? <span className="inline-chip">切段 {attachment.segmentCount}</span> : null}
                </div>
              </article>
            ))}
          </div>
        </div>
      ) : null}

      <div className="form-grid">
        <div className="form-field">
          <label className="meta-label" htmlFor="launch-title">标题</label>
          <input className="field-input" disabled={isSubmitting} id="launch-title" onChange={(event) => setTaskTitle(event.target.value)} value={taskTitle} />
        </div>
        <div className="form-field">
          <label className="meta-label" htmlFor="launch-goal">目标</label>
          <textarea className="field-input field-textarea" disabled={isSubmitting} id="launch-goal" onChange={(event) => setTaskGoal(event.target.value)} value={taskGoal} />
        </div>
      </div>

      {selectedApp ? (
        <div className="pill-row">
          <span className="inline-chip">应用 {selectedApp.application.displayName}</span>
          <span className="inline-chip">模板类型 {selectedTemplate?.taskType ?? "general"}</span>
          <span className="inline-chip">能力 {selectedApp.application.capabilityModuleIds.length}</span>
        </div>
      ) : null}

      <div className="field-actions">
        <button className="action-button" disabled={isSubmitting || !selectedTemplate} onClick={() => void handleCreateAndStart()} type="button">
          {isSubmitting ? "处理中" : createdTaskId ? "启动已创建任务" : "创建并启动"}
        </button>
        <button className="ghost-button" disabled={isSubmitting || !selectedTemplate} onClick={() => void handleCreateOnly()} type="button">
          只创建草稿
        </button>
        {createdTaskId ? (
          <button className="ghost-button" disabled={isSubmitting} onClick={() => void handleStartCreated()} type="button">
            立即启动
          </button>
        ) : null}
      </div>

      {createdTaskId ? (
        <div className="field-actions">
          <p className="meta-copy mono">已创建 {createdTaskId}</p>
          <Link className="ghost-button" href={`/tasks/${encodeURIComponent(createdTaskId)}`}>查看任务</Link>
        </div>
      ) : null}
    </Surface>
  );
}
