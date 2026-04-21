"use client";

import { useState } from "react";

import type { BranchRecord, PermissionTupleRecord, PullRequestRecord, SpaceMountRecord, SpaceRecord } from "@yggdrasil/frontend-sdk";

import { postApiJson, useApiResource } from "../lib/use-api-resource";
import { ErrorState, LoadingState, PageHeader, StatusBadge, Surface, formatTimestamp } from "./workbench-primitives";

type SpacesResponse = { spaces: SpaceRecord[] };
type BranchesResponse = { branches: BranchRecord[] };
type SpaceMountsResponse = { spaceMounts: SpaceMountRecord[] };
type PermissionTuplesResponse = { permissionTuples: PermissionTupleRecord[] };
type PullRequestsResponse = { pullRequests: PullRequestRecord[] };
type CreateSpaceResponse = { space: SpaceRecord };
type CreateSpaceMountResponse = { spaceMount: SpaceMountRecord };
type CreatePermissionTupleResponse = { permissionTuple: PermissionTupleRecord };

export function CollaborationPage() {
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
      setSubmitMessage(`共享空间 ${response.space.id} 已创建。`);
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
      setSubmitMessage(`空间挂载 ${response.spaceMount.id} 已创建。`);
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
      setSubmitMessage(`权限 tuple ${response.permissionTuple.id} 已创建。`);
      setPermissionForm((value) => ({ ...value, id: "" }));
      reloadCollaborationData();
    } catch (error) {
      setSubmitError(error instanceof Error ? error.message : String(error));
    } finally {
      setActiveForm(null);
    }
  }

  if (spaces.isLoading || branches.isLoading || spaceMounts.isLoading || permissionTuples.isLoading || pullRequests.isLoading) {
    return <LoadingState title="正在读取协作流数据" />;
  }

  if (spaces.error || branches.error || spaceMounts.error || permissionTuples.error || pullRequests.error) {
    return <ErrorState detail={spaces.error ?? branches.error ?? spaceMounts.error ?? permissionTuples.error ?? pullRequests.error ?? "协作数据不可用。"} />;
  }

  const spaceList = spaces.data?.spaces ?? [];
  const branchList = branches.data?.branches ?? [];
  const mountList = spaceMounts.data?.spaceMounts ?? [];
  const permissionTupleList = permissionTuples.data?.permissionTuples ?? [];
  const pullRequestList = pullRequests.data?.pullRequests ?? [];

  return (
    <div>
      <PageHeader
        eyebrow="Collaboration"
        title="分支与 PR 协作台"
        summary={<>这里把 M6 分支协作和 M9 共享空间、挂载与权限 tuple 统一收口到正式控制面。</>}
        actions={<button className="ghost-button" onClick={reloadCollaborationData} type="button">刷新协作视图</button>}
      />

      {submitError ? <ErrorState title="协作写入失败" detail={submitError} /> : null}
      {submitMessage ? <p className="meta-copy">{submitMessage}</p> : null}

      <div className="form-grid">
        <Surface>
          <p className="section-kicker">Create Space</p>
          <h3 className="section-title">创建共享空间</h3>
          <form
            onSubmit={(event) => {
              event.preventDefault();
              void handleCreateSpace();
            }}
          >
            <div className="form-field">
              <label className="meta-label" htmlFor="space-id">Space ID</label>
              <input className="field-input" id="space-id" onChange={(event) => setSpaceForm((value) => ({ ...value, id: event.target.value }))} placeholder="留空则自动生成" value={spaceForm.id} />
            </div>
            <div className="form-field">
              <label className="meta-label" htmlFor="space-owner">Owner Subject</label>
              <input className="field-input" id="space-owner" onChange={(event) => setSpaceForm((value) => ({ ...value, ownerSubject: event.target.value }))} placeholder="team:design" value={spaceForm.ownerSubject} />
            </div>
            <div className="field-actions">
              <button className="action-button" disabled={activeForm !== null} type="submit">
                {activeForm === "space" ? "正在创建" : "创建共享空间"}
              </button>
            </div>
          </form>
        </Surface>

        <Surface>
          <p className="section-kicker">Create Mount</p>
          <h3 className="section-title">创建空间挂载</h3>
          <form
            onSubmit={(event) => {
              event.preventDefault();
              void handleCreateMount();
            }}
          >
            <div className="form-field">
              <label className="meta-label" htmlFor="mount-id">Mount ID</label>
              <input className="field-input" id="mount-id" onChange={(event) => setMountForm((value) => ({ ...value, id: event.target.value }))} placeholder="留空则自动生成" value={mountForm.id} />
            </div>
            <div className="form-field">
              <label className="meta-label" htmlFor="mount-host-space">Host Space</label>
              <input className="field-input" id="mount-host-space" onChange={(event) => setMountForm((value) => ({ ...value, hostSpaceId: event.target.value }))} placeholder="space_default" value={mountForm.hostSpaceId} />
            </div>
            <div className="form-field">
              <label className="meta-label" htmlFor="mount-target-space">Mounted Space</label>
              <input className="field-input" id="mount-target-space" onChange={(event) => setMountForm((value) => ({ ...value, mountedSpaceId: event.target.value }))} placeholder="space_shared_design" value={mountForm.mountedSpaceId} />
            </div>
            <div className="form-field">
              <label className="meta-label" htmlFor="mount-mode">Mount Mode</label>
              <select className="field-input" id="mount-mode" onChange={(event) => setMountForm((value) => ({ ...value, mountMode: event.target.value }))} value={mountForm.mountMode}>
                <option value="readonly">readonly</option>
                <option value="copy-on-write">copy-on-write</option>
                <option value="bidirectional">bidirectional</option>
              </select>
            </div>
            <div className="field-actions">
              <button className="action-button" disabled={activeForm !== null} type="submit">
                {activeForm === "mount" ? "正在创建" : "创建空间挂载"}
              </button>
            </div>
          </form>
        </Surface>

        <Surface>
          <p className="section-kicker">Create Permission</p>
          <h3 className="section-title">创建权限 Tuple</h3>
          <form
            onSubmit={(event) => {
              event.preventDefault();
              void handleCreatePermissionTuple();
            }}
          >
            <div className="form-field">
              <label className="meta-label" htmlFor="permission-id">Tuple ID</label>
              <input className="field-input" id="permission-id" onChange={(event) => setPermissionForm((value) => ({ ...value, id: event.target.value }))} placeholder="留空则自动生成" value={permissionForm.id} />
            </div>
            <div className="form-field">
              <label className="meta-label" htmlFor="permission-subject">Subject</label>
              <input className="field-input" id="permission-subject" onChange={(event) => setPermissionForm((value) => ({ ...value, subject: event.target.value }))} placeholder="team:design" value={permissionForm.subject} />
            </div>
            <div className="form-field">
              <label className="meta-label" htmlFor="permission-relation">Relation</label>
              <input className="field-input" id="permission-relation" onChange={(event) => setPermissionForm((value) => ({ ...value, relation: event.target.value }))} placeholder="memory.read" value={permissionForm.relation} />
            </div>
            <div className="form-field">
              <label className="meta-label" htmlFor="permission-resource">Resource</label>
              <input className="field-input" id="permission-resource" onChange={(event) => setPermissionForm((value) => ({ ...value, resource: event.target.value }))} placeholder="space:space_shared_design" value={permissionForm.resource} />
            </div>
            <div className="form-field">
              <label className="meta-label" htmlFor="permission-effect">Effect</label>
              <select className="field-input" id="permission-effect" onChange={(event) => setPermissionForm((value) => ({ ...value, effect: event.target.value }))} value={permissionForm.effect}>
                <option value="allow">allow</option>
                <option value="deny">deny</option>
              </select>
            </div>
            <div className="form-field">
              <label className="meta-label" htmlFor="permission-condition">Condition JSON</label>
              <textarea className="field-input field-textarea" id="permission-condition" onChange={(event) => setPermissionForm((value) => ({ ...value, conditionText: event.target.value }))} placeholder='{"mountMode":"readonly"}' rows={4} value={permissionForm.conditionText} />
            </div>
            <div className="field-actions">
              <button className="action-button" disabled={activeForm !== null} type="submit">
                {activeForm === "permission" ? "正在创建" : "创建权限 Tuple"}
              </button>
            </div>
          </form>
        </Surface>
      </div>

      <div className="content-grid tight">
        <Surface>
          <p className="section-kicker">Spaces</p>
          <h3 className="section-title">记忆空间</h3>
          <div className="record-list">
            {spaceList.map((space) => (
              <article className="record-card" key={space.id}>
                <div className="record-head">
                  <div>
                    <h4 className="record-title">{space.id}</h4>
                    <p className="meta-copy">type {space.spaceType}</p>
                  </div>
                  <StatusBadge value={space.status} />
                </div>
                <div className="pill-row">
                  <span className="inline-chip">project {space.projectId}</span>
                  <span className="inline-chip">owner {String(space.ownerSubject ?? "-")}</span>
                  <span className="inline-chip">created {formatTimestamp(space.createdAt)}</span>
                </div>
              </article>
            ))}
          </div>
        </Surface>

        <Surface>
          <p className="section-kicker">Mounts</p>
          <h3 className="section-title">空间挂载</h3>
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
                  <span className="inline-chip">mode {mount.mountMode}</span>
                  <span className="inline-chip">project {mount.projectId}</span>
                  <span className="inline-chip">created {formatTimestamp(mount.createdAt)}</span>
                </div>
              </article>
            ))}
          </div>
        </Surface>

        <Surface>
          <p className="section-kicker">Permissions</p>
          <h3 className="section-title">权限 Tuple</h3>
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
                  <span className="inline-chip">project {permissionTuple.projectId}</span>
                  <span className="inline-chip">created {formatTimestamp(permissionTuple.createdAt)}</span>
                  <span className="inline-chip">condition {JSON.stringify(permissionTuple.condition ?? {})}</span>
                </div>
              </article>
            ))}
          </div>
        </Surface>

        <Surface>
          <p className="section-kicker">Branches</p>
          <h3 className="section-title">分支</h3>
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
                  <span className="inline-chip">base {String(branch.baseBranchId ?? "-")}</span>
                  <span className="inline-chip">head {String(branch.headRef ?? "-")}</span>
                  <span className="inline-chip">created {formatTimestamp(branch.createdAt)}</span>
                </div>
              </article>
            ))}
          </div>
        </Surface>

        <Surface>
          <p className="section-kicker">Pull Requests</p>
          <h3 className="section-title">PR 列表</h3>
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
                  <span className="inline-chip">source {pullRequest.sourceBranchId}</span>
                  <span className="inline-chip">target {pullRequest.targetBranchId}</span>
                  <span className="inline-chip">created {formatTimestamp(pullRequest.createdAt)}</span>
                  {pullRequest.externalUrl ? (
                    <a className="inline-chip" href={pullRequest.externalUrl} rel="noreferrer" target="_blank">
                      external
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