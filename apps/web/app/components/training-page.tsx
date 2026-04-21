"use client";

import { useState } from "react";

import type { DatasetVersionRecord, ModelArtifactRecord } from "@yggdrasil/frontend-sdk";

import { postApiJson, useApiResource } from "../lib/use-api-resource";
import { EmptyState, ErrorState, LoadingState, PageHeader, StatusBadge, Surface, formatTimestamp } from "./workbench-primitives";

type DatasetVersionsResponse = { datasetVersions: DatasetVersionRecord[] };
type ModelArtifactsResponse = { modelArtifacts: ModelArtifactRecord[] };
type PrepareDatasetResponse = {
  datasetVersion: DatasetVersionRecord;
  previewRows: Array<Record<string, unknown>>;
  summary: string;
};
type StageModelArtifactResponse = {
  modelArtifact: ModelArtifactRecord;
  validationGate: Record<string, unknown>;
  summary: string;
};

export function TrainingPage() {
  const datasetVersions = useApiResource<DatasetVersionsResponse>("/training/dataset-versions?limit=200");
  const modelArtifacts = useApiResource<ModelArtifactsResponse>("/training/model-artifacts?limit=200");
  const [datasetForm, setDatasetForm] = useState({ datasetName: "m9_control_plane_dataset", maxRows: "12", includeMemoryNodes: true });
  const [artifactForm, setArtifactForm] = useState({ datasetVersionId: "", baseModel: "gpt-5.4", tuningMethod: "distillation", minimumRows: "8" });
  const [prepareResult, setPrepareResult] = useState<PrepareDatasetResponse | null>(null);
  const [stageResult, setStageResult] = useState<StageModelArtifactResponse | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [activeForm, setActiveForm] = useState<"dataset" | "artifact" | null>(null);

  function reloadTrainingData() {
    datasetVersions.reload();
    modelArtifacts.reload();
  }

  async function handlePrepareDataset() {
    setActiveForm("dataset");
    setSubmitError(null);
    try {
      const response = await postApiJson<PrepareDatasetResponse>("/training/dataset-versions/prepare", {
        datasetName: datasetForm.datasetName.trim(),
        maxRows: Number(datasetForm.maxRows),
        includeMemoryNodes: datasetForm.includeMemoryNodes,
      });
      setPrepareResult(response);
      setArtifactForm((value) => ({ ...value, datasetVersionId: response.datasetVersion.id }));
      reloadTrainingData();
    } catch (error) {
      setSubmitError(error instanceof Error ? error.message : String(error));
    } finally {
      setActiveForm(null);
    }
  }

  async function handleStageModelArtifact() {
    setActiveForm("artifact");
    setSubmitError(null);
    try {
      const response = await postApiJson<StageModelArtifactResponse>("/training/model-artifacts/stage", {
        datasetVersionId: artifactForm.datasetVersionId.trim(),
        baseModel: artifactForm.baseModel.trim(),
        tuningMethod: artifactForm.tuningMethod,
        minimumRows: Number(artifactForm.minimumRows),
      });
      setStageResult(response);
      reloadTrainingData();
    } catch (error) {
      setSubmitError(error instanceof Error ? error.message : String(error));
    } finally {
      setActiveForm(null);
    }
  }

  if (datasetVersions.isLoading || modelArtifacts.isLoading) {
    return <LoadingState title="正在读取训练实验数据" />;
  }

  if (datasetVersions.error || modelArtifacts.error) {
    return <ErrorState detail={datasetVersions.error ?? modelArtifacts.error ?? "训练实验数据不可用。"} />;
  }

  const versionList = datasetVersions.data?.datasetVersions ?? [];
  const artifactList = modelArtifacts.data?.modelArtifacts ?? [];

  return (
    <div>
      <PageHeader
        eyebrow="Training Lab"
        title="Dataset Version 与模型制品控制面"
        summary={<>这里把 M9 的训练实验模块直接产品化为控制面，可从 prompt artifact 和记忆节点生成数据集版本，并继续 stage 模型制品。</>}
        actions={<button className="ghost-button" onClick={reloadTrainingData} type="button">刷新训练视图</button>}
      />

      {submitError ? <ErrorState title="训练实验写入失败" detail={submitError} /> : null}

      <div className="form-grid">
        <Surface>
          <p className="section-kicker">Prepare Dataset</p>
          <h3 className="section-title">生成 Dataset Version</h3>
          <form
            onSubmit={(event) => {
              event.preventDefault();
              void handlePrepareDataset();
            }}
          >
            <div className="form-field">
              <label className="meta-label" htmlFor="dataset-name">Dataset Name</label>
              <input className="field-input" id="dataset-name" onChange={(event) => setDatasetForm((value) => ({ ...value, datasetName: event.target.value }))} value={datasetForm.datasetName} />
            </div>
            <div className="form-field">
              <label className="meta-label" htmlFor="dataset-max-rows">Max Rows</label>
              <input className="field-input" id="dataset-max-rows" min={1} onChange={(event) => setDatasetForm((value) => ({ ...value, maxRows: event.target.value }))} type="number" value={datasetForm.maxRows} />
            </div>
            <label className="meta-copy">
              <input checked={datasetForm.includeMemoryNodes} onChange={(event) => setDatasetForm((value) => ({ ...value, includeMemoryNodes: event.target.checked }))} type="checkbox" /> 包含记忆节点
            </label>
            <div className="field-actions">
              <button className="action-button" disabled={activeForm !== null} type="submit">
                {activeForm === "dataset" ? "正在准备" : "生成数据集版本"}
              </button>
            </div>
          </form>
          {prepareResult ? (
            <div className="record-card">
              <div className="record-head">
                <div>
                  <h4 className="record-title">最新数据集</h4>
                  <p className="meta-copy">{prepareResult.summary}</p>
                </div>
                <StatusBadge value="completed" />
              </div>
              <div className="pill-row">
                <span className="inline-chip">version {prepareResult.datasetVersion.version}</span>
                <span className="inline-chip">rows {prepareResult.datasetVersion.rowCount}</span>
                <span className="inline-chip">storage {prepareResult.datasetVersion.storageKey}</span>
              </div>
            </div>
          ) : null}
        </Surface>

        <Surface>
          <p className="section-kicker">Stage Artifact</p>
          <h3 className="section-title">Stage Model Artifact</h3>
          <form
            onSubmit={(event) => {
              event.preventDefault();
              void handleStageModelArtifact();
            }}
          >
            <div className="form-field">
              <label className="meta-label" htmlFor="artifact-dataset-version">Dataset Version ID</label>
              <input className="field-input" id="artifact-dataset-version" onChange={(event) => setArtifactForm((value) => ({ ...value, datasetVersionId: event.target.value }))} placeholder="先生成数据集或手动填入版本 ID" value={artifactForm.datasetVersionId} />
            </div>
            <div className="form-field">
              <label className="meta-label" htmlFor="artifact-base-model">Base Model</label>
              <input className="field-input" id="artifact-base-model" onChange={(event) => setArtifactForm((value) => ({ ...value, baseModel: event.target.value }))} value={artifactForm.baseModel} />
            </div>
            <div className="form-field">
              <label className="meta-label" htmlFor="artifact-tuning-method">Tuning Method</label>
              <select className="field-input" id="artifact-tuning-method" onChange={(event) => setArtifactForm((value) => ({ ...value, tuningMethod: event.target.value }))} value={artifactForm.tuningMethod}>
                <option value="distillation">distillation</option>
                <option value="sft">sft</option>
                <option value="dpo">dpo</option>
                <option value="adapter">adapter</option>
              </select>
            </div>
            <div className="form-field">
              <label className="meta-label" htmlFor="artifact-minimum-rows">Minimum Rows</label>
              <input className="field-input" id="artifact-minimum-rows" min={1} onChange={(event) => setArtifactForm((value) => ({ ...value, minimumRows: event.target.value }))} type="number" value={artifactForm.minimumRows} />
            </div>
            <div className="field-actions">
              <button className="action-button" disabled={activeForm !== null || artifactForm.datasetVersionId.trim().length === 0} type="submit">
                {activeForm === "artifact" ? "正在 stage" : "Stage 模型制品"}
              </button>
            </div>
          </form>
          {stageResult ? (
            <div className="record-card">
              <div className="record-head">
                <div>
                  <h4 className="record-title">最新模型制品</h4>
                  <p className="meta-copy">{stageResult.summary}</p>
                </div>
                <StatusBadge value={stageResult.modelArtifact.status} />
              </div>
              <div className="pill-row">
                <span className="inline-chip">artifact {stageResult.modelArtifact.id}</span>
                <span className="inline-chip">dataset {stageResult.modelArtifact.datasetVersionId}</span>
                <span className="inline-chip">ready {String(stageResult.validationGate.readyForValidation ?? false)}</span>
              </div>
            </div>
          ) : null}
        </Surface>
      </div>

      <div className="content-grid tight">
        <Surface>
          <p className="section-kicker">Datasets</p>
          <h3 className="section-title">Dataset Versions</h3>
          {versionList.length === 0 ? (
            <EmptyState title="还没有数据集版本" detail="先生成一条 dataset version，控制台会显示 row 数、来源过滤器和存储位置。" />
          ) : (
            <div className="record-list">
              {versionList.map((version) => (
                <article className="record-card" key={version.id}>
                  <div className="record-head">
                    <div>
                      <h4 className="record-title">{version.datasetName} · {version.version}</h4>
                      <p className="meta-copy">{version.storageKey}</p>
                    </div>
                    <StatusBadge value="ready" />
                  </div>
                  <div className="pill-row">
                    <span className="inline-chip">rows {version.rowCount}</span>
                    <span className="inline-chip">created {formatTimestamp(version.createdAt)}</span>
                    <span className="inline-chip">filter {JSON.stringify(version.sourceFilter)}</span>
                  </div>
                </article>
              ))}
            </div>
          )}
        </Surface>

        <Surface>
          <p className="section-kicker">Artifacts</p>
          <h3 className="section-title">Model Artifacts</h3>
          {artifactList.length === 0 ? (
            <EmptyState title="还没有模型制品" detail="当某个 dataset version 满足最小样本阈值后，就可以在上方直接 stage 出正式 model artifact。" />
          ) : (
            <div className="record-list">
              {artifactList.map((artifact) => (
                <article className="record-card" key={artifact.id}>
                  <div className="record-head">
                    <div>
                      <h4 className="record-title">{artifact.baseModel}</h4>
                      <p className="meta-copy">{artifact.id}</p>
                    </div>
                    <StatusBadge value={artifact.status} />
                  </div>
                  <div className="pill-row">
                    <span className="inline-chip">dataset {artifact.datasetVersionId}</span>
                    <span className="inline-chip">method {artifact.tuningMethod}</span>
                    <span className="inline-chip">metrics {String(artifact.metricsRef?.locator ?? "-")}</span>
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