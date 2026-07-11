"use client";

import { useState } from "react";

import type { BranchRecord, PermissionTupleRecord, PullRequestRecord, SpaceMountRecord, SpaceRecord } from "@yggdrasil/frontend-sdk";

import { postApiJson, useApiResource } from "../lib/use-api-resource";
import { localizedText } from "../i18n";
import { ErrorState, LoadingState, PageHeader, StatusBadge, Surface, formatTimestamp } from "./workbench-primitives";
import { useLocale } from "./locale-provider";

type SpacesResponse = { spaces: SpaceRecord[] };
type BranchesResponse = { branches: BranchRecord[] };
type SpaceMountsResponse = { spaceMounts: SpaceMountRecord[] };
type PermissionTuplesResponse = { permissionTuples: PermissionTupleRecord[] };
type PullRequestsResponse = { pullRequests: PullRequestRecord[] };
type CreateSpaceResponse = { space: SpaceRecord };
type CreateSpaceMountResponse = { spaceMount: SpaceMountRecord };
type CreatePermissionTupleResponse = { permissionTuple: PermissionTupleRecord };

export function CollaborationPage() {
  const { locale } = useLocale();
  const l = (zhCN: string, english: string) => localizedText(locale, zhCN, english);
  const spaces = useApiResource<SpacesResponse>("/collaboration/spaces?limit=200");
  const branches = useApiResource<BranchesResponse>("/collaboration/branches?limit=200");
  const spaceMounts = useApiResource<SpaceMountsResponse>("/collaboration/space-mounts?limit=200");
  const permissionTuples = useApiResource<PermissionTuplesResponse>("/collaboration/permission-tuples?limit=200");
  const pullRequests = useApiResource<PullRequestsResponse>("/collaboration/pull-requests?limit=200");
  const [spaceForm, setSpaceForm] = useState({ id: "", ownerSubject: "team:design" });
  const [mountForm, setMountForm] = useState({ id: "", hostSpaceId: "space_default", mountedSpaceId: "", mountMode: "readonly" });
  const [permissionForm, setPermissionForm] = useState({
    id: "",
    subject: "team:design",
    relation: "memory.read",
    resource: "",
    effect: "allow",
    conditionText: '{"mountMode":"readonly"}',
  });
  const [activeForm, setActiveForm] = useState<"space" | "mount" | "permission" | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitMessage, setSubmitMessage] = useState<string | null>(null);

  function reloadCollaborationData() {
    spaces.reload();
    branches.reload();
    spaceMounts.reload();
    permissionTuples.reload();
    pullRequests.reload();
  }

  async function handleCreateSpace() {
    setActiveForm("space");
    setSubmitError(null);
    setSubmitMessage(null);
    try {
      const response = await postApiJson<CreateSpaceResponse>("/collaboration/spaces", {
        id: spaceForm.id.trim() || undefined,
        projectId: "project_default",
        spaceType: "shared",
        ownerSubject: spaceForm.ownerSubject.trim() || null,
      });
      setSubmitMessage(`${localizedText(locale, "共享空间", "Shared space")} ${response.space.id} ${localizedText(locale, "已创建。", "created.")}`);
      setSpaceForm((value) => ({ ...value, id: "" }));
      reloadCollaborationData();
    } catch (error) {
      setSubmitError(error instanceof Error ? error.message : String(error));
    } finally {
      setActiveForm(null);
    }
  }

  async function handleCreateMount() {
    setActiveForm("mount");
    setSubmitError(null);
    setSubmitMessage(null);
    try {
      const response = await postApiJson<CreateSpaceMountResponse>("/collaboration/space-mounts", {
        id: mountForm.id.trim() || undefined,
        projectId: "project_default",
        hostSpaceId: mountForm.hostSpaceId.trim(),
        mountedSpaceId: mountForm.mountedSpaceId.trim(),
        mountMode: mountForm.mountMode,
        createdBy: { type: "user", id: "web-console" },
      });
      setSubmitMessage(`${localizedText(locale, "空间挂载", "Space mount")} ${response.spaceMount.id} ${localizedText(locale, "已创建。", "created.")}`);
      setMountForm((value) => ({ ...value, id: "" }));
      reloadCollaborationData();
    } catch (error) {
      setSubmitError(error instanceof Error ? error.message : String(error));
    } finally {
      setActiveForm(null);
    }
  }

  async function handleCreatePermissionTuple() {
    setActiveForm("permission");
    setSubmitError(null);
    setSubmitMessage(null);
    try {
      const trimmedCondition = permissionForm.conditionText.trim();
      const condition = trimmedCondition.length === 0 ? null : JSON.parse(trimmedCondition);
      const response = await postApiJson<CreatePermissionTupleResponse>("/collaboration/permission-tuples", {
        id: permissionForm.id.trim() || undefined,
        projectId: "project_default",
        subject: permissionForm.subject.trim(),
        relation: permissionForm.relation.trim(),
        resource: permissionForm.resource.trim(),
        effect: permissionForm.effect,
        condition,
        createdBy: { type: "user", id: "web-console" },
      });
      setSubmitMessage(`${localizedText(locale, "权限 tuple", "Permission tuple")} ${response.permissionTuple.id} ${localizedText(locale, "已创建。", "created.")}`);
      setPermissionForm((value) => ({ ...value, id: "" }));
      reloadCollaborationData();
    } catch (error) {
      setSubmitError(error instanceof Error ? error.message : String(error));
    } finally {
      setActiveForm(null);
    }
  }

  if (spaces.isLoading || branches.isLoading || spaceMounts.isLoading || permissionTuples.isLoading || pullRequests.isLoading) {
    return <LoadingState title={localizedText(locale, "正在读取协作流数据", "Loading collaboration streams")} />;
  }

  if (spaces.error || branches.error || spaceMounts.error || permissionTuples.error || pullRequests.error) {
    return <ErrorState detail={spaces.error ?? branches.error ?? spaceMounts.error ?? permissionTuples.error ?? pullRequests.error ?? localizedText(locale, "协作数据不可用。", "Collaboration data is unavailable.")} />;
  }

  const spaceList = spaces.data?.spaces ?? [];
  const branchList = branches.data?.branches ?? [];
  const mountList = spaceMounts.data?.spaceMounts ?? [];
  const permissionTupleList = permissionTuples.data?.permissionTuples ?? [];
  const pullRequestList = pullRequests.data?.pullRequests ?? [];

  return (
    <div>
      <PageHeader
        eyebrow={l("协作", "Collaboration")}
        title={localizedText(locale, "分支与 PR 协作台", "Branches and PR collaboration")}
        summary={<>{localizedText(locale, "这里管理共享空间、分支、访问规则和协作提交，适合多人或多 Agent 共同维护同一批记忆。", "Manage shared spaces, branches, access rules, and collaborative submissions for people and Agents maintaining the same memory.")}</>}
        actions={<button className="ghost-button" onClick={reloadCollaborationData} type="button">{localizedText(locale, "刷新协作视图", "Refresh collaboration")}</button>}
      />

      {submitError ? <ErrorState title={localizedText(locale, "协作写入失败", "Collaboration write failed")} detail={submitError} /> : null}
      {submitMessage ? <p className="meta-copy">{submitMessage}</p> : null}

      <div className="form-grid">
        <Surface>
          <p className="section-kicker">{l("创建空间", "Create space")}</p>
          <h3 className="section-title">{localizedText(locale, "创建共享空间", "Create shared space")}</h3>
          <form
            onSubmit={(event) => {
              event.preventDefault();
              void handleCreateSpace();
            }}
          >
            <div className="form-field">
              <label className="meta-label" htmlFor="space-id">{l("空间 ID", "Space ID")}</label>
              <input className="field-input" id="space-id" onChange={(event) => setSpaceForm((value) => ({ ...value, id: event.target.value }))} placeholder={localizedText(locale, "留空则自动生成", "Leave blank to generate")} value={spaceForm.id} />
            </div>
            <div className="form-field">
              <label className="meta-label" htmlFor="space-owner">{l("所有者主体", "Owner subject")}</label>
              <input className="field-input" id="space-owner" onChange={(event) => setSpaceForm((value) => ({ ...value, ownerSubject: event.target.value }))} placeholder="team:design" value={spaceForm.ownerSubject} />
            </div>
            <div className="field-actions">
              <button className="action-button" disabled={activeForm !== null} type="submit">
                {activeForm === "space" ? localizedText(locale, "正在创建", "Creating") : localizedText(locale, "创建共享空间", "Create shared space")}
              </button>
            </div>
          </form>
        </Surface>

        <Surface>
          <p className="section-kicker">{l("创建挂载", "Create mount")}</p>
          <h3 className="section-title">{localizedText(locale, "创建空间挂载", "Create space mount")}</h3>
          <form
            onSubmit={(event) => {
              event.preventDefault();
              void handleCreateMount();
            }}
          >
            <div className="form-field">
              <label className="meta-label" htmlFor="mount-id">{l("挂载 ID", "Mount ID")}</label>
              <input className="field-input" id="mount-id" onChange={(event) => setMountForm((value) => ({ ...value, id: event.target.value }))} placeholder={localizedText(locale, "留空则自动生成", "Leave blank to generate")} value={mountForm.id} />
            </div>
            <div className="form-field">
              <label className="meta-label" htmlFor="mount-host-space">{l("宿主空间", "Host space")}</label>
              <input className="field-input" id="mount-host-space" onChange={(event) => setMountForm((value) => ({ ...value, hostSpaceId: event.target.value }))} placeholder="space_default" value={mountForm.hostSpaceId} />
            </div>
            <div className="form-field">
              <label className="meta-label" htmlFor="mount-target-space">{l("被挂载空间", "Mounted space")}</label>
              <input className="field-input" id="mount-target-space" onChange={(event) => setMountForm((value) => ({ ...value, mountedSpaceId: event.target.value }))} placeholder="space_shared_design" value={mountForm.mountedSpaceId} />
            </div>
            <div className="form-field">
              <label className="meta-label" htmlFor="mount-mode">{l("挂载方式", "Mount mode")}</label>
              <select className="field-input" id="mount-mode" onChange={(event) => setMountForm((value) => ({ ...value, mountMode: event.target.value }))} value={mountForm.mountMode}>
                <option value="readonly">{l("只读", "Read-only")}</option>
                <option value="copy-on-write">{l("写时复制", "Copy-on-write")}</option>
                <option value="bidirectional">{l("双向", "Bidirectional")}</option>
              </select>
            </div>
            <div className="field-actions">
              <button className="action-button" disabled={activeForm !== null} type="submit">
                {activeForm === "mount" ? localizedText(locale, "正在创建", "Creating") : localizedText(locale, "创建空间挂载", "Create space mount")}
              </button>
            </div>
          </form>
        </Surface>

        <Surface>
          <p className="section-kicker">{l("创建权限", "Create permission")}</p>
          <h3 className="section-title">{localizedText(locale, "创建权限 Tuple", "Create permission tuple")}</h3>
          <form
            onSubmit={(event) => {
              event.preventDefault();
              void handleCreatePermissionTuple();
            }}
          >
            <div className="form-field">
              <label className="meta-label" htmlFor="permission-id">{l("权限元组 ID", "Tuple ID")}</label>
              <input className="field-input" id="permission-id" onChange={(event) => setPermissionForm((value) => ({ ...value, id: event.target.value }))} placeholder={localizedText(locale, "留空则自动生成", "Leave blank to generate")} value={permissionForm.id} />
            </div>
            <div className="form-field">
              <label className="meta-label" htmlFor="permission-subject">{l("主体", "Subject")}</label>
              <input className="field-input" id="permission-subject" onChange={(event) => setPermissionForm((value) => ({ ...value, subject: event.target.value }))} placeholder="team:design" value={permissionForm.subject} />
            </div>
            <div className="form-field">
              <label className="meta-label" htmlFor="permission-relation">{l("关系", "Relation")}</label>
              <input className="field-input" id="permission-relation" onChange={(event) => setPermissionForm((value) => ({ ...value, relation: event.target.value }))} placeholder="memory.read" value={permissionForm.relation} />
            </div>
            <div className="form-field">
              <label className="meta-label" htmlFor="permission-resource">{l("资源", "Resource")}</label>
              <input className="field-input" id="permission-resource" onChange={(event) => setPermissionForm((value) => ({ ...value, resource: event.target.value }))} placeholder="space:space_shared_design" value={permissionForm.resource} />
            </div>
            <div className="form-field">
              <label className="meta-label" htmlFor="permission-effect">{l("效果", "Effect")}</label>
              <select className="field-input" id="permission-effect" onChange={(event) => setPermissionForm((value) => ({ ...value, effect: event.target.value }))} value={permissionForm.effect}>
                <option value="allow">{l("允许", "Allow")}</option>
                <option value="deny">{l("拒绝", "Deny")}</option>
              </select>
            </div>
            <div className="form-field">
              <label className="meta-label" htmlFor="permission-condition">{l("条件 JSON", "Condition JSON")}</label>
              <textarea className="field-input field-textarea" id="permission-condition" onChange={(event) => setPermissionForm((value) => ({ ...value, conditionText: event.target.value }))} placeholder='{"mountMode":"readonly"}' rows={4} value={permissionForm.conditionText} />
            </div>
            <div className="field-actions">
              <button className="action-button" disabled={activeForm !== null} type="submit">
                {activeForm === "permission" ? localizedText(locale, "正在创建", "Creating") : localizedText(locale, "创建权限 Tuple", "Create permission tuple")}
              </button>
            </div>
          </form>
        </Surface>
      </div>

      <div className="content-grid tight">
        <Surface>
          <p className="section-kicker">{l("空间", "Spaces")}</p>
          <h3 className="section-title">{localizedText(locale, "记忆空间", "Memory spaces")}</h3>
          <div className="record-list">
            {spaceList.map((space) => (
              <article className="record-card" key={space.id}>
                <div className="record-head">
                  <div>
                    <h4 className="record-title">{space.id}</h4>
                    <p className="meta-copy">{l("类型", "Type")} {space.spaceType}</p>
                  </div>
                  <StatusBadge value={space.status} />
                </div>
                <div className="pill-row">
                  <span className="inline-chip">{l("项目", "Project")} {space.projectId}</span>
                  <span className="inline-chip">{l("所有者", "Owner")} {String(space.ownerSubject ?? "-")}</span>
                  <span className="inline-chip">{l("创建", "Created")} {formatTimestamp(space.createdAt, locale)}</span>
                </div>
              </article>
            ))}
          </div>
        </Surface>

        <Surface>
          <p className="section-kicker">{l("挂载", "Mounts")}</p>
          <h3 className="section-title">{localizedText(locale, "空间挂载", "Space mounts")}</h3>
          <div className="record-list">
            {mountList.map((mount) => (
              <article className="record-card" key={mount.id}>
                <div className="record-head">
                  <div>
                    <h4 className="record-title">{mount.hostSpaceId} → {mount.mountedSpaceId}</h4>
                    <p className="meta-copy mono">{mount.id}</p>
                  </div>
                  <StatusBadge value={mount.status} />
                </div>
                <div className="pill-row">
                  <span className="inline-chip">{l("方式", "Mode")} {mount.mountMode}</span>
                  <span className="inline-chip">{l("项目", "Project")} {mount.projectId}</span>
                  <span className="inline-chip">{l("创建", "Created")} {formatTimestamp(mount.createdAt, locale)}</span>
                </div>
              </article>
            ))}
          </div>
        </Surface>

        <Surface>
          <p className="section-kicker">{l("权限", "Permissions")}</p>
          <h3 className="section-title">{localizedText(locale, "权限 Tuple", "Permission tuples")}</h3>
          <div className="record-list">
            {permissionTupleList.map((permissionTuple) => (
              <article className="record-card" key={permissionTuple.id}>
                <div className="record-head">
                  <div>
                    <h4 className="record-title">{permissionTuple.subject}</h4>
                    <p className="meta-copy">{permissionTuple.relation} {permissionTuple.resource}</p>
                  </div>
                  <StatusBadge value={permissionTuple.effect} />
                </div>
                <div className="pill-row">
                  <span className="inline-chip">{l("项目", "Project")} {permissionTuple.projectId}</span>
                  <span className="inline-chip">{l("创建", "Created")} {formatTimestamp(permissionTuple.createdAt, locale)}</span>
                  <span className="inline-chip">{l("条件", "Condition")} {JSON.stringify(permissionTuple.condition ?? {})}</span>
                </div>
              </article>
            ))}
          </div>
        </Surface>

        <Surface>
          <p className="section-kicker">{l("分支", "Branches")}</p>
          <h3 className="section-title">{localizedText(locale, "分支", "Branches")}</h3>
          <div className="record-list">
            {branchList.map((branch) => (
              <article className="record-card" key={branch.id}>
                <div className="record-head">
                  <div>
                    <h4 className="record-title">{branch.name}</h4>
                    <p className="meta-copy mono">{branch.id}</p>
                  </div>
                  <StatusBadge value={branch.status} />
                </div>
                <div className="pill-row">
                  <span className="inline-chip">{l("基线", "Base")} {String(branch.baseBranchId ?? "-")}</span>
                  <span className="inline-chip">{l("头部", "Head")} {String(branch.headRef ?? "-")}</span>
                  <span className="inline-chip">{l("创建", "Created")} {formatTimestamp(branch.createdAt, locale)}</span>
                </div>
              </article>
            ))}
          </div>
        </Surface>

        <Surface>
          <p className="section-kicker">{l("拉取请求", "Pull requests")}</p>
          <h3 className="section-title">{localizedText(locale, "PR 列表", "Pull requests")}</h3>
          <div className="record-list">
            {pullRequestList.map((pullRequest) => (
              <article className="record-card" key={pullRequest.id}>
                <div className="record-head">
                  <div>
                    <h4 className="record-title">{pullRequest.title}</h4>
                    <p className="meta-copy">{pullRequest.summary}</p>
                  </div>
                  <StatusBadge value={pullRequest.status} />
                </div>
                <div className="pill-row">
                  <span className="inline-chip">{l("来源", "Source")} {pullRequest.sourceBranchId}</span>
                  <span className="inline-chip">{l("目标", "Target")} {pullRequest.targetBranchId}</span>
                  <span className="inline-chip">{l("创建", "Created")} {formatTimestamp(pullRequest.createdAt, locale)}</span>
                  {pullRequest.externalUrl ? (
                    <a className="inline-chip" href={pullRequest.externalUrl} rel="noreferrer" target="_blank">
                      {l("外部链接", "External")}
                    </a>
                  ) : null}
                </div>
              </article>
            ))}
          </div>
        </Surface>
      </div>
    </div>
  );
}
