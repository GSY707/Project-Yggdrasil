"use client";

import type { NodeDetailResponse } from "@yggdrasil/frontend-sdk";

import { useApiResource } from "../lib/use-api-resource";
import { ErrorState, LoadingState, PageHeader, StatusBadge, Surface, formatTimestamp } from "./workbench-primitives";

export function NodeDetailPage({ nodeId }: { nodeId: string }) {
  const { data, error, isLoading } = useApiResource<NodeDetailResponse>(`/nodes/${encodeURIComponent(nodeId)}`);

  if (isLoading) {
    return <LoadingState title="正在读取节点详情" />;
  }

  if (error || !data) {
    return <ErrorState detail={error ?? "节点详情不可用。"} />;
  }

  return (
    <div>
      <PageHeader eyebrow="Node Detail" title={data.node.title} summary={<>节点类型：{data.node.nodeType}</>} />

      <section className="detail-hero">
        <div className="record-head">
          <div>
            <p className="meta-label">Node ID</p>
            <p className="meta-copy mono">{data.node.id}</p>
          </div>
          <StatusBadge value={data.node.status} />
        </div>
        <div className="kv-grid">
          <div className="kv-item">
            <p className="meta-label">Branch</p>
            <p className="meta-copy mono">{data.node.branchId}</p>
          </div>
          <div className="kv-item">
            <p className="meta-label">Parent</p>
            <p className="meta-copy mono">{String(data.node.parentId ?? "-")}</p>
          </div>
          <div className="kv-item">
            <p className="meta-label">Importance</p>
            <p className="meta-copy">{String(data.node.importance ?? "-")}</p>
          </div>
          <div className="kv-item">
            <p className="meta-label">Updated</p>
            <p className="meta-copy">{formatTimestamp(data.node.updatedAt ?? data.node.createdAt)}</p>
          </div>
        </div>
        <div className="kv-item" style={{ marginTop: 12 }}>
          <p className="meta-label">Content</p>
          <p className="detail-body">{data.node.content}</p>
        </div>
      </section>

      <div className="content-grid tight">
        <Surface>
          <p className="section-kicker">Versions</p>
          <h3 className="section-title">版本历史</h3>
          <div className="record-list">
            {data.versions.map((version) => (
              <article className="record-card" key={version.id}>
                <div className="record-head">
                  <div>
                    <h4 className="record-title">v{version.versionNo}</h4>
                    <p className="meta-copy">{version.changeReason}</p>
                  </div>
                  <span className="inline-chip">{formatTimestamp(version.createdAt)}</span>
                </div>
                <p className="detail-body">{version.contentSnapshot}</p>
              </article>
            ))}
          </div>
        </Surface>

        <Surface>
          <p className="section-kicker">Annotations</p>
          <h3 className="section-title">来源标注</h3>
          <div className="record-list">
            {data.annotations.map((annotation) => (
              <article className="record-card" key={annotation.id}>
                <div className="record-head">
                  <div>
                    <h4 className="record-title">{annotation.sourceType}</h4>
                    <p className="meta-copy">{annotation.inferenceSummary ?? annotation.excerpt ?? "-"}</p>
                  </div>
                  <span className="inline-chip">confidence {annotation.confidence}</span>
                </div>
              </article>
            ))}
          </div>
        </Surface>
      </div>

      <Surface>
        <p className="section-kicker">Relations</p>
        <h3 className="section-title">关系边</h3>
        <div className="content-grid tight">
          <div>
            <p className="meta-label">Outgoing</p>
            <div className="record-list">
              {data.outgoingEdges.map((edge) => (
                <article className="record-card" key={edge.id}>
                  <h4 className="record-title">{edge.relationType}</h4>
                  <p className="meta-copy mono">to {edge.toNodeId}</p>
                  <p className="meta-copy">{edge.reason}</p>
                </article>
              ))}
            </div>
          </div>
          <div>
            <p className="meta-label">Incoming</p>
            <div className="record-list">
              {data.incomingEdges.map((edge) => (
                <article className="record-card" key={edge.id}>
                  <h4 className="record-title">{edge.relationType}</h4>
                  <p className="meta-copy mono">from {edge.fromNodeId}</p>
                  <p className="meta-copy">{edge.reason}</p>
                </article>
              ))}
            </div>
          </div>
        </div>
      </Surface>
    </div>
  );
}