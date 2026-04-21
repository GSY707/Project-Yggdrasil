"use client";

import { useEffect, useState } from "react";

import Link from "next/link";
import { useSearchParams } from "next/navigation";

import type { ApplicationConfigBinding, ApplicationManifestSummary, PromptCompileArtifactRecord, PromptProfileDefinition, SeedTemplateDefinition } from "@yggdrasil/frontend-sdk";

import { postApiJson, useApiResource } from "../lib/use-api-resource";
import { EmptyState, ErrorState, LoadingState, PageHeader, Surface, formatTimestamp } from "./workbench-primitives";

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
type PromptPreviewResponse = { appId?: string; compiledPrompt: { appId: string; messages: Array<{ role: string; content: string }>; systemSections: Record<string, string>; userSections: Record<string, string>; registeredTools: Array<Record<string, unknown>>; promptProfileId: string; seedTemplateId?: string | null; runType: string; taskType: string; scenario?: string | null }; registeredTools: Array<Record<string, unknown>> };

export function PromptingPage() {
  const searchParams = useSearchParams();
  const applications = useApiResource<ApplicationsResponse>("/applications");
  const initialAppId = searchParams.get("appId") ?? "";
  const [previewForm, setPreviewForm] = useState({
    appId: initialAppId,
    title: "Prompt Control Plane Preview",
    goal: "Preview the current runtime prompt compilation.",
    currentFocus: "prompt-ops",
    currentObjective: "Inspect the compiled runtime prompt before execution.",
    resumeMessage: "从最新的 prompt preview 继续。",
    runType: "main",
    taskType: "coding",
    activeCapabilities: "",
    responseRequirements: "强调证据边界和下一步动作。",
  });
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
            title: "Prompt Control Plane Context",
            content: "当前目标是把 PromptCompiler 的 profile、seed template、工具清单和运行态消息编译结果完整暴露给控制面。",
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
    return <LoadingState title="正在读取 Prompt 控制面数据" />;
  }

  if (applications.error || selectedApplicationDetail.error || promptProfiles.error || seedTemplates.error || registeredTools.error || compileArtifacts.error) {
    return <ErrorState detail={applications.error ?? selectedApplicationDetail.error ?? promptProfiles.error ?? seedTemplates.error ?? registeredTools.error ?? compileArtifacts.error ?? "Prompt 控制面数据不可用。"} />;
  }

  const applicationItems = applications.data?.applications ?? [];
  const selectedApp = selectedApplicationDetail.data?.application?.appId === selectedAppId
    ? selectedApplicationDetail.data.application
    : applicationItems.find((item) => item.application.appId === selectedAppId)?.application;
  const profileList = promptProfiles.data?.promptProfiles ?? [];
  const templateList = seedTemplates.data?.seedTemplates ?? [];
  const toolList = registeredTools.data?.registeredTools ?? [];
  const artifactList = compileArtifacts.data?.promptCompileArtifacts ?? [];

  return (
    <div>
      <PageHeader
        eyebrow="Prompt Operations"
        title="PromptCompiler 与 Prompt Asset 控制面"
        summary={<>这里统一展示按应用装配后的 runtime profile、seed template、已注册工具以及已落盘的 prompt compile artifact，并支持在控制台直接预览编译结果。</>}
        actions={<button className="ghost-button" onClick={reloadPromptingData} type="button">刷新 Prompt 视图</button>}
      />

      {previewError ? <ErrorState title="Prompt 预览失败" detail={previewError} /> : null}

      <Surface>
        <p className="section-kicker">Application</p>
        <h3 className="section-title">当前应用装配</h3>
        {selectedApp ? (
          <div className="record-list">
            <article className="record-card">
              <div className="record-head">
                <div>
                  <h4 className="record-title">{selectedApp.displayName}</h4>
                  <p className="meta-copy">{selectedApp.appId}</p>
                </div>
                <Link className="ghost-button" href={`/applications/${encodeURIComponent(selectedApp.appId)}`}>查看应用详情</Link>
              </div>
              <p className="meta-copy">{selectedApp.description ?? "该应用没有额外描述。"}</p>
              <div className="pill-row">
                <span className="inline-chip">profiles {profileList.length}</span>
                <span className="inline-chip">seeds {templateList.length}</span>
                <span className="inline-chip">scene modules {selectedApp.sceneModuleIds.length}</span>
                <span className="inline-chip">capability modules {selectedApp.capabilityModuleIds.length}</span>
              </div>
            </article>
          </div>
        ) : (
          <EmptyState title="没有可用应用" detail="请先在应用管理页确认应用插件已被发现。" />
        )}
      </Surface>

      <div className="form-grid">
        <Surface>
          <p className="section-kicker">Preview</p>
          <h3 className="section-title">编译 Prompt 预览</h3>
          <form
            onSubmit={(event) => {
              event.preventDefault();
              void handleCompilePreview();
            }}
          >
            <div className="form-field">
              <label className="meta-label" htmlFor="prompt-app-id">Application</label>
              <select className="field-input" id="prompt-app-id" onChange={(event) => setPreviewForm((value) => ({ ...value, appId: event.target.value, activeCapabilities: "" }))} value={selectedAppId}>
                {applicationItems.map((item) => (
                  <option key={item.application.appId} value={item.application.appId}>{item.application.displayName}</option>
                ))}
              </select>
            </div>
            <div className="form-field">
              <label className="meta-label" htmlFor="prompt-title">Task Title</label>
              <input className="field-input" id="prompt-title" onChange={(event) => setPreviewForm((value) => ({ ...value, title: event.target.value }))} value={previewForm.title} />
            </div>
            <div className="form-field">
              <label className="meta-label" htmlFor="prompt-goal">Task Goal</label>
              <input className="field-input" id="prompt-goal" onChange={(event) => setPreviewForm((value) => ({ ...value, goal: event.target.value }))} value={previewForm.goal} />
            </div>
            <div className="form-field">
              <label className="meta-label" htmlFor="prompt-run-type">Run Type</label>
              <select className="field-input" id="prompt-run-type" onChange={(event) => setPreviewForm((value) => ({ ...value, runType: event.target.value }))} value={previewForm.runType}>
                <option value="main">main</option>
                <option value="subagent">subagent</option>
              </select>
            </div>
            <div className="form-field">
              <label className="meta-label" htmlFor="prompt-task-type">Task Type</label>
              <select className="field-input" id="prompt-task-type" onChange={(event) => setPreviewForm((value) => ({ ...value, taskType: event.target.value }))} value={previewForm.taskType}>
                <option value="coding">coding</option>
                <option value="research">research</option>
                <option value="writing">writing</option>
                <option value="maintenance">maintenance</option>
                <option value="learning">learning</option>
                <option value="service">service</option>
                <option value="generic">generic</option>
              </select>
            </div>
            <div className="form-field">
              <label className="meta-label" htmlFor="prompt-focus">Current Focus</label>
              <input className="field-input" id="prompt-focus" onChange={(event) => setPreviewForm((value) => ({ ...value, currentFocus: event.target.value }))} value={previewForm.currentFocus} />
            </div>
            <div className="form-field">
              <label className="meta-label" htmlFor="prompt-objective">Current Objective</label>
              <textarea className="field-input field-textarea" id="prompt-objective" onChange={(event) => setPreviewForm((value) => ({ ...value, currentObjective: event.target.value }))} rows={4} value={previewForm.currentObjective} />
            </div>
            <div className="form-field">
              <label className="meta-label" htmlFor="prompt-resume">Resume Message</label>
              <input className="field-input" id="prompt-resume" onChange={(event) => setPreviewForm((value) => ({ ...value, resumeMessage: event.target.value }))} value={previewForm.resumeMessage} />
            </div>
            <div className="form-field">
              <label className="meta-label" htmlFor="prompt-capabilities">Active Capabilities</label>
              <input className="field-input" id="prompt-capabilities" onChange={(event) => setPreviewForm((value) => ({ ...value, activeCapabilities: event.target.value }))} value={previewForm.activeCapabilities} />
            </div>
            <div className="form-field">
              <label className="meta-label" htmlFor="prompt-response-requirements">Response Requirements</label>
              <input className="field-input" id="prompt-response-requirements" onChange={(event) => setPreviewForm((value) => ({ ...value, responseRequirements: event.target.value }))} value={previewForm.responseRequirements} />
            </div>
            <div className="field-actions">
              <button className="action-button" disabled={isSubmitting} type="submit">
                {isSubmitting ? "正在编译" : "预览编译结果"}
              </button>
            </div>
          </form>
        </Surface>

        <Surface>
          <p className="section-kicker">Result</p>
          <h3 className="section-title">最近一次编译结果</h3>
          {!preview ? (
            <EmptyState title="还没有编译结果" detail="提交左侧表单后，这里会展示 prompt profile、seed template、消息正文和工具清单。" />
          ) : (
            <div className="record-list">
              <article className="record-card">
                <div className="record-head">
                  <div>
                    <h4 className="record-title">{preview.compiledPrompt.promptProfileId}</h4>
                    <p className="meta-copy">app {preview.compiledPrompt.appId} | seed {String(preview.compiledPrompt.seedTemplateId ?? "-")}</p>
                  </div>
                </div>
                <div className="pill-row">
                  <span className="inline-chip">run {preview.compiledPrompt.runType}</span>
                  <span className="inline-chip">task {preview.compiledPrompt.taskType}</span>
                  <span className="inline-chip">scenario {String(preview.compiledPrompt.scenario ?? "-")}</span>
                  <span className="inline-chip">tools {preview.compiledPrompt.registeredTools.length}</span>
                </div>
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
          <p className="section-kicker">Profiles</p>
          <h3 className="section-title">Prompt Profiles</h3>
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
                  <span className="inline-chip">scope {profile.runScope}</span>
                  <span className="inline-chip">version {profile.version}</span>
                  <span className="inline-chip">source {profile.sourceModuleId ?? profile.sourceAppId ?? "-"}</span>
                </div>
              </article>
            ))}
          </div>
        </Surface>

        <Surface>
          <p className="section-kicker">Seeds</p>
          <h3 className="section-title">Seed Templates</h3>
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
                  <span className="inline-chip">domain {template.domain}</span>
                  <span className="inline-chip">scenario {template.scenario}</span>
                  <span className="inline-chip">version {template.version}</span>
                  <span className="inline-chip">source {template.sourceModuleId ?? template.sourceAppId ?? "-"}</span>
                </div>
              </article>
            ))}
          </div>
        </Surface>

        <Surface>
          <p className="section-kicker">Tools</p>
          <h3 className="section-title">已注册工具</h3>
          {toolList.length === 0 ? (
            <EmptyState title="还没有结构化工具" detail="当前没有激活的模块工具描述。" />
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
                    <span className="inline-chip">module {String(tool.moduleId ?? "-")}</span>
                    <span className="inline-chip">mode {String(tool.executionMode ?? "sync")}</span>
                    <span className="inline-chip">permissions {String((tool.permissionRequired as string[] | undefined)?.join(", ") ?? "none")}</span>
                  </div>
                </article>
              ))}
            </div>
          )}
        </Surface>

        <Surface>
          <p className="section-kicker">Artifacts</p>
          <h3 className="section-title">Prompt Compile Artifacts</h3>
          {artifactList.length === 0 ? (
            <EmptyState title="还没有 prompt compile artifact" detail="当运行时完成真实编译和模型调用后，这里会出现正式的 prompt 资产与运行痕迹。" />
          ) : (
            <div className="record-list">
              {artifactList.map((artifact) => (
                <article className="record-card" key={artifact.id}>
                  <div className="record-head">
                    <div>
                      <h4 className="record-title">{artifact.id}</h4>
                      <p className="meta-copy">app {artifact.appId} | task {String(artifact.taskId ?? "-")}</p>
                    </div>
                  </div>
                  <div className="pill-row">
                    <span className="inline-chip">run {artifact.runType}</span>
                    <span className="inline-chip">task type {artifact.taskType}</span>
                    <span className="inline-chip">tools {artifact.registeredTools.length}</span>
                    <span className="inline-chip">created {formatTimestamp(artifact.createdAt)}</span>
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