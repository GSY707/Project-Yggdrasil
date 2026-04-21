"use client";

import { useState } from "react";

import type { AssetRecord } from "@yggdrasil/frontend-sdk";

import { postApiJson, useApiResource } from "../lib/use-api-resource";
import { EmptyState, ErrorState, LoadingState, PageHeader, StatusBadge, Surface, formatTimestamp } from "./workbench-primitives";

type AssetsResponse = { assets: AssetRecord[] };
type AssetIngestResponse = {
  asset: AssetRecord;
  segmentCount: number;
  summary?: string;
  summaryNode?: { id: string; title: string; content: string };
};

export function AssetsPage() {
  const assets = useApiResource<AssetsResponse>("/assets?limit=200");
  const [form, setForm] = useState({
    mediaType: "document",
    sourceUri: "",
    sourceText: "",
    branchId: "branch_main",
    spaceId: "space_default",
  });
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [ingestResult, setIngestResult] = useState<AssetIngestResponse | null>(null);

  async function handleIngestAsset() {
    setIsSubmitting(true);
    setSubmitError(null);
    try {
      const response = await postApiJson<AssetIngestResponse>("/assets/ingest", {
        mediaType: form.mediaType,
        sourceUri: form.sourceUri.trim() || undefined,
        sourceText: form.sourceText.trim(),
        branchId: form.branchId.trim() || undefined,
        spaceId: form.spaceId.trim() || undefined,
      });
      setIngestResult(response);
      setForm((value) => ({ ...value, sourceUri: "", sourceText: "" }));
      assets.reload();
    } catch (error) {
      setSubmitError(error instanceof Error ? error.message : String(error));
    } finally {
      setIsSubmitting(false);
    }
  }

  if (assets.isLoading) {
    return <LoadingState title="正在读取多模态资产索引" />;
  }

  if (assets.error) {
    return <ErrorState detail={assets.error} />;
  }

  const assetList = assets.data?.assets ?? [];

  return (
    <div>
      <PageHeader
        eyebrow="Multimodal Assets"
        title="正式多模态资产控制面"
        summary={<>这里直接读取 M9 的资产记录，支持从控制台触发正式导入，并回看素材来源、空间归属和落库结果。</>}
        actions={<button className="ghost-button" onClick={assets.reload} type="button">刷新资产索引</button>}
      />

      {submitError ? <ErrorState title="资产导入失败" detail={submitError} /> : null}

      <div className="content-grid tight">
        <Surface>
          <p className="section-kicker">Ingest</p>
          <h3 className="section-title">导入多模态资产</h3>
          <form
            onSubmit={(event) => {
              event.preventDefault();
              void handleIngestAsset();
            }}
          >
            <div className="form-field">
              <label className="meta-label" htmlFor="asset-media-type">Media Type</label>
              <select className="field-input" id="asset-media-type" onChange={(event) => setForm((value) => ({ ...value, mediaType: event.target.value }))} value={form.mediaType}>
                <option value="document">document</option>
                <option value="audio">audio</option>
                <option value="image">image</option>
                <option value="video">video</option>
              </select>
            </div>
            <div className="form-field">
              <label className="meta-label" htmlFor="asset-source-uri">Source URI</label>
              <input className="field-input" id="asset-source-uri" onChange={(event) => setForm((value) => ({ ...value, sourceUri: event.target.value }))} placeholder="可选：素材来源 URL 或路径" value={form.sourceUri} />
            </div>
            <div className="form-field">
              <label className="meta-label" htmlFor="asset-space-id">Space</label>
              <input className="field-input" id="asset-space-id" onChange={(event) => setForm((value) => ({ ...value, spaceId: event.target.value }))} value={form.spaceId} />
            </div>
            <div className="form-field">
              <label className="meta-label" htmlFor="asset-branch-id">Branch</label>
              <input className="field-input" id="asset-branch-id" onChange={(event) => setForm((value) => ({ ...value, branchId: event.target.value }))} value={form.branchId} />
            </div>
            <div className="form-field">
              <label className="meta-label" htmlFor="asset-source-text">Source Text</label>
              <textarea className="field-input field-textarea" id="asset-source-text" onChange={(event) => setForm((value) => ({ ...value, sourceText: event.target.value }))} placeholder="输入文本、转录或字幕内容，模块会自动切段并生成 embedding。" rows={8} value={form.sourceText} />
            </div>
            <div className="field-actions">
              <button className="action-button" disabled={isSubmitting || form.sourceText.trim().length === 0} type="submit">
                {isSubmitting ? "正在导入" : "导入正式资产"}
              </button>
            </div>
          </form>
          {ingestResult ? (
            <div className="record-card">
              <div className="record-head">
                <div>
                  <h4 className="record-title">最近一次导入</h4>
                  <p className="meta-copy">{ingestResult.summary ?? "资产已落库。"}</p>
                </div>
                <StatusBadge value="completed" />
              </div>
              <div className="pill-row">
                <span className="inline-chip">asset {ingestResult.asset.id}</span>
                <span className="inline-chip">segments {ingestResult.segmentCount}</span>
                <span className="inline-chip">summary node {String(ingestResult.summaryNode?.id ?? "-")}</span>
              </div>
            </div>
          ) : null}
        </Surface>

        <Surface>
          <p className="section-kicker">Assets</p>
          <h3 className="section-title">资产索引</h3>
          {assetList.length === 0 ? (
            <EmptyState title="还没有资产记录" detail="可以先在左侧表单导入一条正式多模态资产，系统会自动创建资产、分段、embedding 和摘要节点。" />
          ) : (
            <div className="record-list">
              {assetList.map((asset) => (
                <article className="record-card" key={asset.id}>
                  <div className="record-head">
                    <div>
                      <h4 className="record-title">{asset.mediaType} · {asset.id}</h4>
                      <p className="meta-copy">{asset.storageKey}</p>
                    </div>
                    <StatusBadge value={asset.role} />
                  </div>
                  <div className="pill-row">
                    <span className="inline-chip">space {asset.spaceId}</span>
                    <span className="inline-chip">branch {asset.branchId}</span>
                    <span className="inline-chip">owner {String(asset.ownerNodeId ?? "-")}</span>
                    <span className="inline-chip">source {String(asset.sourceRef?.locator ?? "-")}</span>
                    <span className="inline-chip">created {formatTimestamp(asset.createdAt)}</span>
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