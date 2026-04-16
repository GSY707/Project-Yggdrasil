"use client";

import type { BranchRecord, PullRequestRecord } from "@yggdrasil/frontend-sdk";

import { useApiResource } from "../lib/use-api-resource";
import { ErrorState, LoadingState, PageHeader, StatusBadge, Surface, formatTimestamp } from "./workbench-primitives";

type BranchesResponse = { branches: BranchRecord[] };
type PullRequestsResponse = { pullRequests: PullRequestRecord[] };

export function CollaborationPage() {
  const branches = useApiResource<BranchesResponse>("/collaboration/branches?limit=200");
  const pullRequests = useApiResource<PullRequestsResponse>("/collaboration/pull-requests?limit=200");

  if (branches.isLoading || pullRequests.isLoading) {
    return <LoadingState title="正在读取协作流数据" />;
  }

  if (branches.error || pullRequests.error) {
    return <ErrorState detail={branches.error ?? pullRequests.error ?? "协作数据不可用。"} />;
  }

  const branchList = branches.data?.branches ?? [];
  const pullRequestList = pullRequests.data?.pullRequests ?? [];

  return (
    <div>
      <PageHeader
        eyebrow="Collaboration"
        title="分支与 PR 协作台"
        summary={<>这里对应 M6 子代理协作闭环，统一查看分支、PR 及其外部引用状态。</>}
      />

      <div className="content-grid tight">
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