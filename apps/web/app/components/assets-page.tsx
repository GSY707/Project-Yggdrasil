"use client";

import Link from "next/link";
import { useState } from "react";

import type { AssetIngestResponse, AssetRecord, AssetSegmentRecord } from "@yggdrasil/frontend-sdk";

import { postApiJson, useApiResource } from "../lib/use-api-resource";
import { EmptyState, ErrorState, LoadingState, PageHeader, StatusBadge, Surface, formatTimestamp } from "./workbench-primitives";

type AssetsResponse = { assets: AssetRecord[] };
type SegmentPreview = Pick<AssetSegmentRecord, "ordinal" | "startOffset" | "endOffset" | "textExcerpt">;

const MAX_BROWSER_IMPORT_CHARS = 240_000;

function inferMediaType(fileName: string): string {
  const lower = fileName.toLowerCase();
  if (lower.endsWith(".png") || lower.endsWith(".jpg") || lower.endsWith(".jpeg") || lower.endsWith(".webp")) {
    return "image";
  }
  if (lower.endsWith(".mp3") || lower.endsWith(".wav") || lower.endsWith(".m4a")) {
    return "audio";
  }
  if (lower.endsWith(".mp4") || lower.endsWith(".mov") || lower.endsWith(".webm")) {
    return "video";
  }
  return "document";
}

function mediaTypeLabel(value: string | undefined): string {
  const labels: Record<string, string> = {
    audio: "音频",
    document: "文档",
    image: "图像",
    video: "视频",
  };
  return labels[value ?? ""] ?? value ?? "素材";
}

function previewSegments(text: string, targetChars = 220): SegmentPreview[] {
  const compact = text.replace(/\s+/g, " ").trim();
  if (!compact) {
    return [];
  }
  const segments: SegmentPreview[] = [];
  for (let start = 0; start < compact.length; start += targetChars) {
    const textExcerpt = compact.slice(start, start + targetChars);
    segments.push({
      ordinal: segments.length + 1,
      startOffset: start,
      endOffset: start + textExcerpt.length,
      textExcerpt,
    });
  }
  return segments;
}

function shortText(value: string | undefined, maxLength = 280): string | undefined {
  if (!value) {
    return undefined;
  }
  const compact = value.replace(/\s+/g, " ").trim();
  return compact.length > maxLength ? `${compact.slice(0, maxLength)}...` : compact;
}

function taskLinkForAsset({
  assetId,
  label,
  sourceUri,
  summary,
  summaryNodeId,
  segmentCount,
}: {
  assetId: string;
  label?: string;
  sourceUri?: string;
  summary?: string;
  summaryNodeId?: string;
  segmentCount?: number;
}): string {
  const params = new URLSearchParams({ assetId });
  if (label) {
    params.set("assetLabel", label);
  }
  if (sourceUri) {
    params.set("sourceUri", sourceUri);
  }
  if (summary) {
    params.set("summary", summary);
  }
  if (summaryNodeId) {
    params.set("summaryNodeId", summaryNodeId);
  }
  if (segmentCount !== undefined) {
    params.set("segmentCount", String(segmentCount));
  }
  return `/tasks?${params.toString()}`;
}

export function AssetsPage() {
  const assets = useApiResource<AssetsResponse>("/assets?limit=200");
  const [form, setForm] = useState({
    mediaType: "document",
    sourceUri: "",
    sourceText: "",
    branchId: "branch_main",
    spaceId: "space_default",
  });
  const [selectedFileName, setSelectedFileName] = useState<string | null>(null);
  const [parsedSegments, setParsedSegments] = useState<SegmentPreview[]>([]);
  const [importStatus, setImportStatus] = useState<"idle" | "file-ready" | "importing" | "completed" | "failed">("idle");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [ingestResult, setIngestResult] = useState<AssetIngestResponse | null>(null);

  async function handleFileSelected(file: File | null) {
    setSubmitError(null);
    setIngestResult(null);
    if (!file) {
      setSelectedFileName(null);
      setParsedSegments([]);
      setImportStatus("idle");
      return;
    }
    try {
      const text = await file.text();
      const normalized = text.trim();
      if (!normalized) {
        throw new Error("文件没有可导入的文本内容。");
      }
      if (normalized.length > MAX_BROWSER_IMPORT_CHARS) {
        throw new Error(`当前浏览器导入单次最多 ${MAX_BROWSER_IMPORT_CHARS.toLocaleString("zh-CN")} 个字符，请先拆分文件。`);
      }
      const nextSegments = previewSegments(normalized);
      setSelectedFileName(file.name);
      setParsedSegments(nextSegments);
      setForm((value) => ({
        ...value,
        mediaType: inferMediaType(file.name),
        sourceUri: file.name,
        sourceText: normalized,
      }));
      setImportStatus("file-ready");
    } catch (error) {
      setSelectedFileName(file.name);
      setParsedSegments([]);
      setImportStatus("failed");
      setSubmitError(error instanceof Error ? error.message : String(error));
    }
  }

  async function handleIngestAsset() {
    setIsSubmitting(true);
    setSubmitError(null);
    setImportStatus("importing");
    try {
      const response = await postApiJson<AssetIngestResponse>("/assets/ingest", {
        mediaType: form.mediaType,
        sourceUri: form.sourceUri.trim() || undefined,
        sourceText: form.sourceText.trim(),
        branchId: form.branchId.trim() || undefined,
        spaceId: form.spaceId.trim() || undefined,
      });
      setIngestResult(response);
      setParsedSegments(response.segments ?? parsedSegments);
      setImportStatus("completed");
      setForm((value) => ({ ...value, sourceUri: "", sourceText: "" }));
      setSelectedFileName(null);
      assets.reload();
    } catch (error) {
      setImportStatus("failed");
      setSubmitError(error instanceof Error ? error.message : String(error));
    } finally {
      setIsSubmitting(false);
    }
  }

  if (assets.isLoading) {
    return <LoadingState title="正在读取素材索引" />;
  }

  if (assets.error) {
    return <ErrorState detail={assets.error} />;
  }

  const assetList = assets.data?.assets ?? [];

  return (
    <div>
      <PageHeader
        eyebrow="素材"
        title="导入素材并用于新任务"
        summary={<>选择文本类文件或粘贴资料，系统会切段、生成摘要节点，并允许把导入素材直接附加到新任务。</>}
        actions={<button className="ghost-button" onClick={assets.reload} type="button">刷新资产索引</button>}
      />

      {submitError ? <ErrorState title="素材导入失败" detail={submitError} /> : null}

      <div className="content-grid tight">
        <Surface>
          <p className="section-kicker">导入</p>
          <h3 className="section-title">导入素材</h3>
          <form
            onSubmit={(event) => {
              event.preventDefault();
              void handleIngestAsset();
            }}
          >
            <div className="form-field">
              <label className="meta-label" htmlFor="asset-file">选择文件</label>
              <input
                accept=".txt,.md,.markdown,.csv,.json,.jsonl,.yaml,.yml,.xml,.html,.log,.rst,.text,text/*,application/json"
                className="field-input"
                id="asset-file"
                onChange={(event) => void handleFileSelected(event.target.files?.[0] ?? null)}
                type="file"
              />
              <p className="meta-copy">当前浏览器导入支持可直接读取的文本类文件；图片、音频和 PDF 请先提供转录或摘录文本。</p>
            </div>
            <div className="form-field">
              <label className="meta-label" htmlFor="asset-media-type">素材类型</label>
              <select className="field-input" id="asset-media-type" onChange={(event) => setForm((value) => ({ ...value, mediaType: event.target.value }))} value={form.mediaType}>
                <option value="document">文档</option>
                <option value="audio">音频</option>
                <option value="image">图像</option>
                <option value="video">视频</option>
              </select>
            </div>
            <div className="form-field">
              <label className="meta-label" htmlFor="asset-source-uri">来源 / 文件名</label>
              <input className="field-input" id="asset-source-uri" onChange={(event) => setForm((value) => ({ ...value, sourceUri: event.target.value }))} placeholder="可选：素材来源 URL 或路径" value={form.sourceUri} />
            </div>
            <div className="form-field">
              <label className="meta-label" htmlFor="asset-space-id">记忆空间</label>
              <input className="field-input" id="asset-space-id" onChange={(event) => setForm((value) => ({ ...value, spaceId: event.target.value }))} value={form.spaceId} />
            </div>
            <div className="form-field">
              <label className="meta-label" htmlFor="asset-branch-id">记忆分支</label>
              <input className="field-input" id="asset-branch-id" onChange={(event) => setForm((value) => ({ ...value, branchId: event.target.value }))} value={form.branchId} />
            </div>
            <div className="form-field">
              <label className="meta-label" htmlFor="asset-source-text">正文</label>
              <textarea className="field-input field-textarea" id="asset-source-text" onChange={(event) => setForm((value) => ({ ...value, sourceText: event.target.value }))} placeholder="输入文本、转录或字幕内容，系统会自动切段并生成摘要节点。" rows={8} value={form.sourceText} />
            </div>
            <div className="pill-row">
              <StatusBadge value={importStatus} />
              {selectedFileName ? <span className="inline-chip">文件 {selectedFileName}</span> : null}
              {parsedSegments.length > 0 ? <span className="inline-chip">预览切段 {parsedSegments.length}</span> : null}
            </div>
            <div className="field-actions">
              <button className="action-button" disabled={isSubmitting || form.sourceText.trim().length === 0} type="submit">
                {isSubmitting ? "正在导入" : "导入素材"}
              </button>
            </div>
          </form>

          {parsedSegments.length > 0 ? (
            <div className="segment-list">
              <p className="meta-label">切段预览</p>
              {parsedSegments.slice(0, 8).map((segment) => (
                <article className="segment-card" key={segment.ordinal}>
                  <span className="inline-chip">#{segment.ordinal}</span>
                  <p className="meta-copy">{segment.textExcerpt}</p>
                </article>
              ))}
              {parsedSegments.length > 8 ? <p className="meta-copy">还有 {parsedSegments.length - 8} 个切段会一并导入。</p> : null}
            </div>
          ) : null}

          {ingestResult ? (
            <div className="record-card">
              <div className="record-head">
                <div>
                  <h4 className="record-title">最近一次导入</h4>
                  <p className="meta-copy">{shortText(ingestResult.summaryNode?.content ?? ingestResult.summary) ?? "素材已导入并生成摘要节点。"}</p>
                </div>
                <StatusBadge value="completed" />
              </div>
              <div className="pill-row">
                <span className="inline-chip">素材 {ingestResult.asset.id}</span>
                <span className="inline-chip">切段 {ingestResult.segmentCount}</span>
                <span className="inline-chip">摘要节点 {String(ingestResult.summaryNode?.id ?? "-")}</span>
              </div>
              <div className="field-actions">
                <Link
                  className="action-button"
                  href={taskLinkForAsset({
                    assetId: ingestResult.asset.id,
                    label: `${mediaTypeLabel(ingestResult.asset.mediaType)}素材`,
                    sourceUri: ingestResult.asset.sourceRef?.locator ?? ingestResult.asset.storageKey,
                    summary: shortText(ingestResult.summaryNode?.content ?? ingestResult.summary),
                    summaryNodeId: ingestResult.summaryNode?.id,
                    segmentCount: ingestResult.segmentCount,
                  })}
                >
                  用这个素材创建任务
                </Link>
              </div>
            </div>
          ) : null}
        </Surface>

        <Surface>
          <p className="section-kicker">素材</p>
          <h3 className="section-title">资产索引</h3>
          {assetList.length === 0 ? (
            <EmptyState title="还没有资产记录" detail="可以先在左侧表单导入一条素材，系统会自动创建资产、切段和摘要节点。" />
          ) : (
            <div className="record-list">
              {assetList.map((asset) => (
                <article className="record-card" key={asset.id}>
                  <div className="record-head">
                    <div>
                      <h4 className="record-title">{mediaTypeLabel(asset.mediaType)} · {asset.id}</h4>
                      <p className="meta-copy">{asset.storageKey}</p>
                    </div>
                    <StatusBadge value={asset.role} />
                  </div>
                  <div className="pill-row">
                    <span className="inline-chip">空间 {asset.spaceId}</span>
                    <span className="inline-chip">分支 {asset.branchId}</span>
                    <span className="inline-chip">归属 {String(asset.ownerNodeId ?? "-")}</span>
                    <span className="inline-chip">来源 {String(asset.sourceRef?.locator ?? "-")}</span>
                    <span className="inline-chip">创建 {formatTimestamp(asset.createdAt)}</span>
                  </div>
                  <div className="field-actions">
                    <Link
                      className="ghost-button"
                      href={taskLinkForAsset({
                        assetId: asset.id,
                        label: `${mediaTypeLabel(asset.mediaType)} · ${asset.id}`,
                        sourceUri: asset.sourceRef?.locator ?? asset.storageKey,
                      })}
                    >
                      附加到新任务
                    </Link>
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
