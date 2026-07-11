"use client";

import { useEffect, useRef, useState } from "react";

import Link from "next/link";
import { useSearchParams } from "next/navigation";

import type { ApplicationConfigBinding, ApplicationDashboard, ApplicationManifestSummary, PromptCompileArtifactRecord, PromptProfileDefinition, SeedTemplateDefinition } from "@yggdrasil/frontend-sdk";

import { postApiJson, useApiResource } from "../lib/use-api-resource";
import { localizedText } from "../i18n";
import { localizeDashboard } from "../lib/localized-dashboard";
import { EmptyState, ErrorState, LoadingState, PageHeader, Surface, formatTimestamp } from "./workbench-primitives";
import { useLocale } from "./locale-provider";

type ApplicationsResponse = { activeAppId: string; applications: Array<{ application: ApplicationManifestSummary; configBinding: ApplicationConfigBinding }> };
type ApplicationDetailResponse = {
  application: ApplicationManifestSummary;
  configBinding: ApplicationConfigBinding;
  effectiveConfig: Record<string, unknown>;
  dashboard?: Record<string, unknown> | null;
};
type PromptProfilesResponse = { appId?: string; promptProfiles: PromptProfileDefinition[] };
type SeedTemplatesResponse = { appId?: string; seedTemplates: SeedTemplateDefinition[] };
type RegisteredToolsResponse = { appId?: string; activeCapabilities: string[]; registeredTools: Array<Record<string, unknown>> };
type PromptCompileArtifactsResponse = { promptCompileArtifacts: PromptCompileArtifactRecord[] };
type PromptPreviewResponse = { appId?: string; compiledPrompt: { appId: string; messages: Array<{ role: string; content: string }>; systemSections: Record<string, string>; userSections: Record<string, string>; registeredTools: Array<Record<string, unknown>>; promptProfileId: string; seedTemplateId?: string | null; runType: string; taskType: string; scenario?: string | null; fewShotRefs: string[] }; registeredTools: Array<Record<string, unknown>> };

function promptPreviewDefaults(locale: Parameters<typeof localizedText>[0], appId: string) {
  return {
    appId,
    title: localizedText(locale, "提示词控制面预览", "Prompt control-plane preview"),
    goal: localizedText(locale, "预览当前运行时提示词编译结果。", "Preview the current runtime prompt compilation."),
    currentFocus: "prompt-ops",
    currentObjective: localizedText(locale, "执行前检查编译后的运行时提示词。", "Inspect the compiled runtime prompt before execution."),
    resumeMessage: localizedText(locale, "从最新的提示词预览继续。", "Continue from the latest prompt preview."),
    runType: "main",
    taskType: "coding",
    activeCapabilities: "",
    responseRequirements: localizedText(locale, "强调证据边界和下一步动作。", "Emphasize evidence boundaries and next actions."),
  };
}

export function PromptingPage() {
  const { locale } = useLocale();
  const l = (zhCN: string, english: string) => localizedText(locale, zhCN, english);
  const searchParams = useSearchParams();
  const applications = useApiResource<ApplicationsResponse>("/applications");
  const initialAppId = searchParams.get("appId") ?? "";
  const [previewForm, setPreviewForm] = useState(() => promptPreviewDefaults(locale, initialAppId));
  const previousLocale = useRef(locale);
  const selectedAppId = previewForm.appId || applications.data?.activeAppId || "";
  const selectedApplicationDetail = useApiResource<ApplicationDetailResponse>(
    selectedAppId ? `/applications/${encodeURIComponent(selectedAppId)}` : null,
  );
  const registeredTools = useApiResource<RegisteredToolsResponse>(
    selectedAppId ? `/prompting/registered-tools?appId=${encodeURIComponent(selectedAppId)}` : "/prompting/registered-tools",
  );
  const promptProfiles = useApiResource<PromptProfilesResponse>(
    selectedAppId ? `/prompting/prompt-profiles?appId=${encodeURIComponent(selectedAppId)}` : "/prompting/prompt-profiles",
  );
  const seedTemplates = useApiResource<SeedTemplatesResponse>(
    selectedAppId ? `/prompting/seed-templates?appId=${encodeURIComponent(selectedAppId)}` : "/prompting/seed-templates",
  );
  const compileArtifacts = useApiResource<PromptCompileArtifactsResponse>(
    selectedAppId ? `/prompting/compile-artifacts?limit=200&appId=${encodeURIComponent(selectedAppId)}` : "/prompting/compile-artifacts?limit=200",
  );
  const [preview, setPreview] = useState<PromptPreviewResponse | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (!previewForm.appId && applications.data?.activeAppId) {
      setPreviewForm((value) => ({ ...value, appId: applications.data?.activeAppId ?? value.appId }));
    }
  }, [applications.data?.activeAppId, previewForm.appId]);

  useEffect(() => {
    const priorLocale = previousLocale.current;
    if (priorLocale === locale) {
      return;
    }
    setPreviewForm((value) => {
      const before = promptPreviewDefaults(priorLocale, value.appId);
      const after = promptPreviewDefaults(locale, value.appId);
      return {
        ...value,
        title: value.title === before.title ? after.title : value.title,
        goal: value.goal === before.goal ? after.goal : value.goal,
        currentObjective: value.currentObjective === before.currentObjective ? after.currentObjective : value.currentObjective,
        resumeMessage: value.resumeMessage === before.resumeMessage ? after.resumeMessage : value.resumeMessage,
        responseRequirements: value.responseRequirements === before.responseRequirements ? after.responseRequirements : value.responseRequirements,
      };
    });
    previousLocale.current = locale;
  }, [locale]);

  useEffect(() => {
    if (
      !selectedAppId
      || !selectedApplicationDetail.data
      || selectedApplicationDetail.data.application.appId !== selectedAppId
    ) {
      return;
    }

    const effectiveConfig = selectedApplicationDetail.data.effectiveConfig;
    const promptPreviewDefaults =
      typeof effectiveConfig.promptPreviewDefaults === "object" && effectiveConfig.promptPreviewDefaults !== null
        ? effectiveConfig.promptPreviewDefaults as Record<string, unknown>
        : {};

    setPreviewForm((value) => ({
      ...value,
      runType:
        typeof effectiveConfig.defaultRunType === "string" && effectiveConfig.defaultRunType.trim().length > 0
          ? effectiveConfig.defaultRunType
          : "main",
      taskType:
        typeof effectiveConfig.defaultTaskType === "string" && effectiveConfig.defaultTaskType.trim().length > 0
          ? effectiveConfig.defaultTaskType
          : value.taskType,
      activeCapabilities: "",
      responseRequirements:
        typeof promptPreviewDefaults.responseRequirements === "string" && promptPreviewDefaults.responseRequirements.trim().length > 0
          ? promptPreviewDefaults.responseRequirements
          : value.responseRequirements,
    }));
  }, [selectedAppId, selectedApplicationDetail.data]);

  function reloadPromptingData() {
    applications.reload();
    selectedApplicationDetail.reload();
    promptProfiles.reload();
    seedTemplates.reload();
    registeredTools.reload();
    compileArtifacts.reload();
  }

  async function handleCompilePreview() {
    setIsSubmitting(true);
    setPreviewError(null);
    try {
      const capabilityList = previewForm.activeCapabilities
        .split(",")
        .map((item) => item.trim())
        .filter(Boolean);
      const response = await postApiJson<PromptPreviewResponse>("/prompting/compile-preview", {
        appId: selectedAppId,
        runType: previewForm.runType,
        taskType: previewForm.taskType,
        activeCapabilities: capabilityList,
        task: {
          title: previewForm.title,
          goal: previewForm.goal,
          currentFocus: previewForm.currentFocus,
          currentObjective: previewForm.currentObjective,
          resumeMessage: previewForm.resumeMessage,
          appId: selectedAppId,
        },
        request: {
          appId: selectedAppId,
          currentFocus: previewForm.currentFocus,
          currentObjective: previewForm.currentObjective,
          resumeMessage: previewForm.resumeMessage,
          responseRequirements: previewForm.responseRequirements,
        },
        currentContext: [
          {
            id: "prompt-preview-context",
            title: l("提示词控制面上下文", "Prompt control-plane context"),
            content: l("当前目标是把 PromptCompiler 的 profile、seed template、工具清单和运行态消息编译结果完整暴露给控制面。", "Expose the PromptCompiler profile, seed template, tool list, and compiled runtime messages to the control plane."),
            rootBranch: "context",
          },
        ],
      });
      setPreview(response);
      compileArtifacts.reload();
    } catch (error) {
      setPreviewError(error instanceof Error ? error.message : String(error));
    } finally {
      setIsSubmitting(false);
    }
  }

  if (
    applications.isLoading
    || promptProfiles.isLoading
    || seedTemplates.isLoading
    || registeredTools.isLoading
    || compileArtifacts.isLoading
    || (Boolean(selectedAppId) && selectedApplicationDetail.isLoading)
  ) {
    return <LoadingState title={localizedText(locale, "正在读取 Prompt 控制面数据", "Loading Prompt control-plane data")} />;
  }

  if (applications.error || selectedApplicationDetail.error || promptProfiles.error || seedTemplates.error || registeredTools.error || compileArtifacts.error) {
    return <ErrorState detail={applications.error ?? selectedApplicationDetail.error ?? promptProfiles.error ?? seedTemplates.error ?? registeredTools.error ?? compileArtifacts.error ?? localizedText(locale, "Prompt 控制面数据不可用。", "Prompt control-plane data is unavailable.")} />;
  }

  const applicationItems = applications.data?.applications ?? [];
  const selectedApp = selectedApplicationDetail.data?.application?.appId === selectedAppId
    ? selectedApplicationDetail.data.application
    : applicationItems.find((item) => item.application.appId === selectedAppId)?.application;
  const selectedDashboard = selectedApplicationDetail.data?.dashboard
    ? localizeDashboard(selectedApplicationDetail.data.dashboard as ApplicationDashboard, locale)
    : undefined;
  const profileList = promptProfiles.data?.promptProfiles ?? [];
  const templateList = seedTemplates.data?.seedTemplates ?? [];
  const toolList = registeredTools.data?.registeredTools ?? [];
  const artifactList = compileArtifacts.data?.promptCompileArtifacts ?? [];

  return (
    <div>
      <PageHeader
        eyebrow={l("提示词运维", "Prompt operations")}
        title={localizedText(locale, "PromptCompiler 与 Prompt Asset 控制面", "PromptCompiler and prompt assets")}
        summary={<>{localizedText(locale, "这里统一展示按应用装配后的 runtime profile、seed template、已注册工具以及已落盘的 prompt compile artifact，并支持在控制台直接预览编译结果。", "View assembled runtime profiles, seed templates, registered tools, and persisted compile artifacts, with an in-console compile preview.")}</>}
        actions={<button className="ghost-button" onClick={reloadPromptingData} type="button">{localizedText(locale, "刷新 Prompt 视图", "Refresh Prompt view")}</button>}
      />

      {previewError ? <ErrorState title={localizedText(locale, "Prompt 预览失败", "Prompt preview failed")} detail={previewError} /> : null}

      <Surface>
        <p className="section-kicker">{l("应用", "Application")}</p>
        <h3 className="section-title">{localizedText(locale, "当前应用装配", "Current application assembly")}</h3>
        {selectedApp ? (
          <div className="record-list">
            <article className="record-card">
              <div className="record-head">
                <div>
                  <h4 className="record-title">{selectedApp.displayName}</h4>
                  <p className="meta-copy">{selectedApp.appId}</p>
                </div>
                <Link className="ghost-button" href={`/applications/${encodeURIComponent(selectedApp.appId)}`}>{localizedText(locale, "查看应用详情", "View application")}</Link>
              </div>
              <p className="meta-copy">{selectedDashboard?.hero?.summary ?? selectedApp.description ?? localizedText(locale, "该应用没有额外描述。", "This application has no additional description.")}</p>
              <div className="pill-row">
                <span className="inline-chip">{l("配置档", "Profiles")} {profileList.length}</span>
                <span className="inline-chip">{l("种子模板", "Seeds")} {templateList.length}</span>
                <span className="inline-chip">{l("场景模块", "Scene modules")} {selectedApp.sceneModuleIds.length}</span>
                <span className="inline-chip">{l("能力模块", "Capability modules")} {selectedApp.capabilityModuleIds.length}</span>
              </div>
            </article>
          </div>
        ) : (
          <EmptyState title={localizedText(locale, "没有可用应用", "No applications available")} detail={localizedText(locale, "请先在应用管理页确认应用插件已被发现。", "Confirm that application plugins are discovered on the applications page first.")} />
        )}
      </Surface>

      <div className="form-grid">
        <Surface>
          <p className="section-kicker">{l("预览", "Preview")}</p>
          <h3 className="section-title">{localizedText(locale, "编译 Prompt 预览", "Compile Prompt preview")}</h3>
          <form
            onSubmit={(event) => {
              event.preventDefault();
              void handleCompilePreview();
            }}
          >
            <div className="form-field">
              <label className="meta-label" htmlFor="prompt-app-id">{l("应用", "Application")}</label>
              <select className="field-input" id="prompt-app-id" onChange={(event) => setPreviewForm((value) => ({ ...value, appId: event.target.value, activeCapabilities: "" }))} value={selectedAppId}>
                {applicationItems.map((item) => (
                  <option key={item.application.appId} value={item.application.appId}>{item.application.displayName}</option>
                ))}
              </select>
            </div>
            <div className="form-field">
              <label className="meta-label" htmlFor="prompt-title">{l("任务标题", "Task title")}</label>
              <input className="field-input" id="prompt-title" onChange={(event) => setPreviewForm((value) => ({ ...value, title: event.target.value }))} value={previewForm.title} />
            </div>
            <div className="form-field">
              <label className="meta-label" htmlFor="prompt-goal">{l("任务目标", "Task goal")}</label>
              <input className="field-input" id="prompt-goal" onChange={(event) => setPreviewForm((value) => ({ ...value, goal: event.target.value }))} value={previewForm.goal} />
            </div>
            <div className="form-field">
              <label className="meta-label" htmlFor="prompt-run-type">{l("运行类型", "Run type")}</label>
              <select className="field-input" id="prompt-run-type" onChange={(event) => setPreviewForm((value) => ({ ...value, runType: event.target.value }))} value={previewForm.runType}>
                <option value="main">{l("主任务", "Main")}</option>
                <option value="subagent">{l("子智能体", "Sub-agent")}</option>
              </select>
            </div>
            <div className="form-field">
              <label className="meta-label" htmlFor="prompt-task-type">{l("任务类型", "Task type")}</label>
              <select className="field-input" id="prompt-task-type" onChange={(event) => setPreviewForm((value) => ({ ...value, taskType: event.target.value }))} value={previewForm.taskType}>
                <option value="coding">{l("编程", "Coding")}</option>
                <option value="research">{l("研究", "Research")}</option>
                <option value="writing">{l("写作", "Writing")}</option>
                <option value="maintenance">{l("维护", "Maintenance")}</option>
                <option value="learning">{l("学习", "Learning")}</option>
                <option value="service">{l("服务", "Service")}</option>
                <option value="generic">{l("通用", "Generic")}</option>
              </select>
            </div>
            <div className="form-field">
              <label className="meta-label" htmlFor="prompt-focus">{l("当前重点", "Current focus")}</label>
              <input className="field-input" id="prompt-focus" onChange={(event) => setPreviewForm((value) => ({ ...value, currentFocus: event.target.value }))} value={previewForm.currentFocus} />
            </div>
            <div className="form-field">
              <label className="meta-label" htmlFor="prompt-objective">{l("当前目标", "Current objective")}</label>
              <textarea className="field-input field-textarea" id="prompt-objective" onChange={(event) => setPreviewForm((value) => ({ ...value, currentObjective: event.target.value }))} rows={4} value={previewForm.currentObjective} />
            </div>
            <div className="form-field">
              <label className="meta-label" htmlFor="prompt-resume">{l("继续消息", "Resume message")}</label>
              <input className="field-input" id="prompt-resume" onChange={(event) => setPreviewForm((value) => ({ ...value, resumeMessage: event.target.value }))} value={previewForm.resumeMessage} />
            </div>
            <div className="form-field">
              <label className="meta-label" htmlFor="prompt-capabilities">{l("已激活能力", "Active capabilities")}</label>
              <input className="field-input" id="prompt-capabilities" onChange={(event) => setPreviewForm((value) => ({ ...value, activeCapabilities: event.target.value }))} value={previewForm.activeCapabilities} />
            </div>
            <div className="form-field">
              <label className="meta-label" htmlFor="prompt-response-requirements">{l("回答要求", "Response requirements")}</label>
              <input className="field-input" id="prompt-response-requirements" onChange={(event) => setPreviewForm((value) => ({ ...value, responseRequirements: event.target.value }))} value={previewForm.responseRequirements} />
            </div>
            <div className="field-actions">
              <button className="action-button" disabled={isSubmitting} type="submit">
                {isSubmitting ? localizedText(locale, "正在编译", "Compiling") : localizedText(locale, "预览编译结果", "Preview compile")}
              </button>
            </div>
          </form>
        </Surface>

        <Surface>
          <p className="section-kicker">{l("结果", "Result")}</p>
          <h3 className="section-title">{localizedText(locale, "最近一次编译结果", "Latest compile result")}</h3>
          {!preview ? (
            <EmptyState title={localizedText(locale, "还没有编译结果", "No compile result yet")} detail={localizedText(locale, "提交左侧表单后，这里会展示 prompt profile、seed template、消息正文和工具清单。", "Submit the form to see the prompt profile, seed template, messages, and tool list.")} />
          ) : (
            <div className="record-list">
              <article className="record-card">
                <div className="record-head">
                  <div>
                    <h4 className="record-title">{preview.compiledPrompt.promptProfileId}</h4>
                    <p className="meta-copy">{l("应用", "App")} {preview.compiledPrompt.appId} | {l("种子", "Seed")} {String(preview.compiledPrompt.seedTemplateId ?? "-")}</p>
                  </div>
                </div>
                <div className="pill-row">
                  <span className="inline-chip">{l("运行", "Run")} {preview.compiledPrompt.runType}</span>
                  <span className="inline-chip">{l("任务", "Task")} {preview.compiledPrompt.taskType}</span>
                  <span className="inline-chip">{l("场景", "Scenario")} {String(preview.compiledPrompt.scenario ?? "-")}</span>
                  <span className="inline-chip">{l("少样本", "Few-shot")} {preview.compiledPrompt.fewShotRefs.length}</span>
                  <span className="inline-chip">{l("工具", "Tools")} {preview.compiledPrompt.registeredTools.length}</span>
                </div>
                {preview.compiledPrompt.fewShotRefs.length > 0 ? (
                  <pre className="meta-copy mono">{preview.compiledPrompt.fewShotRefs.join("\n")}</pre>
                ) : null}
              </article>
              {preview.compiledPrompt.messages.map((message, index) => (
                <article className="record-card" key={`${message.role}-${index}`}>
                  <div className="record-head">
                    <div>
                      <h4 className="record-title">{message.role}</h4>
                    </div>
                  </div>
                  <pre className="meta-copy mono">{message.content}</pre>
                </article>
              ))}
            </div>
          )}
        </Surface>
      </div>

      <div className="content-grid tight">
        <Surface>
          <p className="section-kicker">{l("配置档", "Profiles")}</p>
          <h3 className="section-title">{l("提示词配置档", "Prompt profiles")}</h3>
          <div className="record-list">
            {profileList.map((profile) => (
              <article className="record-card" key={profile.id}>
                <div className="record-head">
                  <div>
                    <h4 className="record-title">{profile.name}</h4>
                    <p className="meta-copy">{profile.id}</p>
                  </div>
                </div>
                <div className="pill-row">
                  <span className="inline-chip">{l("范围", "Scope")} {profile.runScope}</span>
                  <span className="inline-chip">{l("版本", "Version")} {profile.version}</span>
                  <span className="inline-chip">{l("少样本", "Few-shot")} {profile.fewShotRefs.length}</span>
                  <span className="inline-chip">{l("来源", "Source")} {profile.sourceModuleId ?? profile.sourceAppId ?? "-"}</span>
                </div>
                {profile.fewShotRefs.length > 0 ? <pre className="meta-copy mono">{profile.fewShotRefs.join("\n")}</pre> : null}
              </article>
            ))}
          </div>
        </Surface>

        <Surface>
          <p className="section-kicker">{l("种子模板", "Seeds")}</p>
          <h3 className="section-title">{l("种子模板", "Seed templates")}</h3>
          <div className="record-list">
            {templateList.map((template) => (
              <article className="record-card" key={template.id}>
                <div className="record-head">
                  <div>
                    <h4 className="record-title">{template.name}</h4>
                    <p className="meta-copy">{template.id}</p>
                  </div>
                </div>
                <div className="pill-row">
                  <span className="inline-chip">{l("领域", "Domain")} {template.domain}</span>
                  <span className="inline-chip">{l("场景", "Scenario")} {template.scenario}</span>
                  <span className="inline-chip">{l("版本", "Version")} {template.version}</span>
                  <span className="inline-chip">{l("少样本", "Few-shot")} {template.fewShotRefs.length}</span>
                  <span className="inline-chip">{l("来源", "Source")} {template.sourceModuleId ?? template.sourceAppId ?? "-"}</span>
                </div>
                {template.fewShotRefs.length > 0 ? <pre className="meta-copy mono">{template.fewShotRefs.join("\n")}</pre> : null}
              </article>
            ))}
          </div>
        </Surface>

        <Surface>
          <p className="section-kicker">{l("工具", "Tools")}</p>
          <h3 className="section-title">{localizedText(locale, "已注册工具", "Registered tools")}</h3>
          {toolList.length === 0 ? (
            <EmptyState title={localizedText(locale, "还没有结构化工具", "No structured tools")} detail={localizedText(locale, "当前没有激活的模块工具描述。", "No active module tool descriptions.")} />
          ) : (
            <div className="record-list">
              {toolList.map((tool) => (
                <article className="record-card" key={String(tool.name)}>
                  <div className="record-head">
                    <div>
                      <h4 className="record-title">{String(tool.name)}</h4>
                      <p className="meta-copy">{String(tool.description ?? tool.displayName ?? "")}</p>
                    </div>
                  </div>
                  <div className="pill-row">
                    <span className="inline-chip">{l("模块", "Module")} {String(tool.moduleId ?? "-")}</span>
                    <span className="inline-chip">{l("方式", "Mode")} {String(tool.executionMode ?? "sync")}</span>
                    <span className="inline-chip">{l("权限", "Permissions")} {String((tool.permissionRequired as string[] | undefined)?.join(", ") ?? l("无", "None"))}</span>
                  </div>
                </article>
              ))}
            </div>
          )}
        </Surface>

        <Surface>
          <p className="section-kicker">{l("工件", "Artifacts")}</p>
          <h3 className="section-title">{l("提示词编译工件", "Prompt compile artifacts")}</h3>
          {artifactList.length === 0 ? (
            <EmptyState title={localizedText(locale, "还没有 prompt compile artifact", "No prompt compile artifacts")} detail={localizedText(locale, "当运行时完成真实编译和模型调用后，这里会出现正式的 prompt 资产与运行痕迹。", "Formal prompt assets and runtime traces appear after a real compile and model call.")} />
          ) : (
            <div className="record-list">
              {artifactList.map((artifact) => (
                <article className="record-card" key={artifact.id}>
                  <div className="record-head">
                    <div>
                      <h4 className="record-title">{artifact.id}</h4>
                      <p className="meta-copy">{l("应用", "App")} {artifact.appId} | {l("任务", "Task")} {String(artifact.taskId ?? "-")}</p>
                    </div>
                  </div>
                  <div className="pill-row">
                    <span className="inline-chip">{l("运行", "Run")} {artifact.runType}</span>
                    <span className="inline-chip">{l("任务类型", "Task type")} {artifact.taskType}</span>
                    <span className="inline-chip">{l("工具", "Tools")} {artifact.registeredTools.length}</span>
                    <span className="inline-chip">{l("创建", "Created")} {formatTimestamp(artifact.createdAt, locale)}</span>
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
