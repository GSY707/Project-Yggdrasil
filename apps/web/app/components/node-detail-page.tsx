"use client";

import type { NodeDetailResponse } from "@yggdrasil/frontend-sdk";

import { useApiResource } from "../lib/use-api-resource";
import { localizedText } from "../i18n";
import { ErrorState, LoadingState, PageHeader, StatusBadge, Surface, formatTimestamp } from "./workbench-primitives";
import { useLocale } from "./locale-provider";

export function NodeDetailPage({ nodeId }: { nodeId: string }) {
  const { locale } = useLocale();
  const { data, error, isLoading } = useApiResource<NodeDetailResponse>(`/nodes/${encodeURIComponent(nodeId)}`);

  if (isLoading) {
    return <LoadingState title={localizedText(locale, "正在读取节点详情", "Loading node details")} />;
  }

  if (error || !data || !data.node) {
    return <ErrorState detail={error ?? localizedText(locale, "节点详情不可用。", "Node details are unavailable.")} />;
  }

  const versions = data.versions ?? [];
  const annotations = data.annotations ?? [];
  const outgoingEdges = data.outgoingEdges ?? [];
  const incomingEdges = data.incomingEdges ?? [];

  return (
    <div>
      <PageHeader eyebrow={localizedText(locale, "节点详情", "Node detail")} title={data.node.title} summary={<>{localizedText(locale, "节点类型", "Node type")}: {data.node.nodeType}</>} />

      <section className="detail-hero">
        <div className="record-head">
          <div>
            <p className="meta-label">{localizedText(locale, "节点 ID", "Node ID")}</p>
            <p className="meta-copy mono">{data.node.id}</p>
          </div>
          <StatusBadge value={data.node.status} />
        </div>
        <div className="kv-grid">
          <div className="kv-item">
            <p className="meta-label">{localizedText(locale, "分支", "Branch")}</p>
            <p className="meta-copy mono">{data.node.branchId}</p>
          </div>
          <div className="kv-item">
            <p className="meta-label">{localizedText(locale, "父节点", "Parent")}</p>
            <p className="meta-copy mono">{String(data.node.parentId ?? "-")}</p>
          </div>
          <div className="kv-item">
            <p className="meta-label">{localizedText(locale, "重要性", "Importance")}</p>
            <p className="meta-copy">{String(data.node.importance ?? "-")}</p>
          </div>
          <div className="kv-item">
            <p className="meta-label">{localizedText(locale, "更新", "Updated")}</p>
            <p className="meta-copy">{formatTimestamp(data.node.updatedAt ?? data.node.createdAt, locale)}</p>
          </div>
        </div>
        <div className="kv-item" style={{ marginTop: 12 }}>
          <p className="meta-label">{localizedText(locale, "内容", "Content")}</p>
          <p className="detail-body">{data.node.content}</p>
        </div>
      </section>

      <div className="content-grid tight">
        <Surface>
          <p className="section-kicker">{localizedText(locale, "版本", "Versions")}</p>
          <h3 className="section-title">{localizedText(locale, "版本历史", "Version history")}</h3>
          <div className="record-list">
            {versions.map((version) => (
              <article className="record-card" key={version.id}>
                <div className="record-head">
                  <div>
                    <h4 className="record-title">v{version.versionNo}</h4>
                    <p className="meta-copy">{version.changeReason}</p>
                  </div>
                  <span className="inline-chip">{formatTimestamp(version.createdAt, locale)}</span>
                </div>
                <p className="detail-body">{version.contentSnapshot}</p>
              </article>
            ))}
          </div>
        </Surface>

        <Surface>
          <p className="section-kicker">{localizedText(locale, "标注", "Annotations")}</p>
          <h3 className="section-title">{localizedText(locale, "来源标注", "Provenance annotations")}</h3>
          <div className="record-list">
            {annotations.map((annotation) => (
              <article className="record-card" key={annotation.id}>
                <div className="record-head">
                  <div>
                    <h4 className="record-title">{annotation.sourceType}</h4>
                    <p className="meta-copy">{annotation.inferenceSummary ?? annotation.excerpt ?? "-"}</p>
                  </div>
                  <span className="inline-chip">{localizedText(locale, "置信度", "confidence")} {annotation.confidence}</span>
                </div>
              </article>
            ))}
          </div>
        </Surface>
      </div>

      <Surface>
        <p className="section-kicker">{localizedText(locale, "关系", "Relations")}</p>
        <h3 className="section-title">{localizedText(locale, "关系边", "Relation edges")}</h3>
        <div className="content-grid tight">
          <div>
            <p className="meta-label">{localizedText(locale, "出边", "Outgoing")}</p>
            <div className="record-list">
              {outgoingEdges.map((edge) => (
                <article className="record-card" key={edge.id}>
                  <h4 className="record-title">{edge.relationType}</h4>
                  <p className="meta-copy mono">{localizedText(locale, "到", "to")} {edge.toNodeId}</p>
                  <p className="meta-copy">{edge.reason}</p>
                </article>
              ))}
            </div>
          </div>
          <div>
            <p className="meta-label">{localizedText(locale, "入边", "Incoming")}</p>
            <div className="record-list">
              {incomingEdges.map((edge) => (
                <article className="record-card" key={edge.id}>
                  <h4 className="record-title">{edge.relationType}</h4>
                  <p className="meta-copy mono">{localizedText(locale, "来自", "from")} {edge.fromNodeId}</p>
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
