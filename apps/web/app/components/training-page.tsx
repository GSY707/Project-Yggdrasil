"use client";

import { useState } from "react";

import type { DatasetVersionRecord, ModelArtifactRecord } from "@yggdrasil/frontend-sdk";

import { postApiJson, useApiResource } from "../lib/use-api-resource";
import { localizedText } from "../i18n";
import { EmptyState, ErrorState, LoadingState, PageHeader, StatusBadge, Surface, formatTimestamp } from "./workbench-primitives";
import { useLocale } from "./locale-provider";

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
  const { locale } = useLocale();
  const l = (zhCN: string, english: string) => localizedText(locale, zhCN, english);
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
    return <LoadingState title={localizedText(locale, "正在读取训练实验数据", "Loading training lab data")} />;
  }

  if (datasetVersions.error || modelArtifacts.error) {
    return <ErrorState detail={datasetVersions.error ?? modelArtifacts.error ?? localizedText(locale, "训练实验数据不可用。", "Training lab data is unavailable.")} />;
  }

  const versionList = datasetVersions.data?.datasetVersions ?? [];
  const artifactList = modelArtifacts.data?.modelArtifacts ?? [];

  return (
    <div>
      <PageHeader
        eyebrow={l("训练实验室", "Training lab")}
        title={localizedText(locale, "数据集与模型实验", "Dataset and model lab")}
        summary={<>{localizedText(locale, "这里从任务记录和记忆节点生成数据集版本，并管理模型制品的实验、候选和晋级状态。", "Generate dataset versions from task records and memory nodes, then manage model artifact experiments, candidates, and promotion states.")}</>}
        actions={<button className="ghost-button" onClick={reloadTrainingData} type="button">{localizedText(locale, "刷新训练视图", "Refresh lab")}</button>}
      />

      {submitError ? <ErrorState title={localizedText(locale, "训练实验写入失败", "Training write failed")} detail={submitError} /> : null}

      <div className="form-grid">
        <Surface>
          <p className="section-kicker">{l("准备数据集", "Prepare dataset")}</p>
          <h3 className="section-title">{localizedText(locale, "生成 Dataset Version", "Create dataset version")}</h3>
          <form
            onSubmit={(event) => {
              event.preventDefault();
              void handlePrepareDataset();
            }}
          >
            <div className="form-field">
              <label className="meta-label" htmlFor="dataset-name">{l("数据集名称", "Dataset name")}</label>
              <input className="field-input" id="dataset-name" onChange={(event) => setDatasetForm((value) => ({ ...value, datasetName: event.target.value }))} value={datasetForm.datasetName} />
            </div>
            <div className="form-field">
              <label className="meta-label" htmlFor="dataset-max-rows">{l("最大行数", "Max rows")}</label>
              <input className="field-input" id="dataset-max-rows" min={1} onChange={(event) => setDatasetForm((value) => ({ ...value, maxRows: event.target.value }))} type="number" value={datasetForm.maxRows} />
            </div>
            <label className="meta-copy">
              <input checked={datasetForm.includeMemoryNodes} onChange={(event) => setDatasetForm((value) => ({ ...value, includeMemoryNodes: event.target.checked }))} type="checkbox" /> {localizedText(locale, "包含记忆节点", "Include memory nodes")}
            </label>
            <div className="field-actions">
              <button className="action-button" disabled={activeForm !== null} type="submit">
                {activeForm === "dataset" ? localizedText(locale, "正在准备", "Preparing") : localizedText(locale, "生成数据集版本", "Create dataset version")}
              </button>
            </div>
          </form>
          {prepareResult ? (
            <div className="record-card">
              <div className="record-head">
                <div>
                  <h4 className="record-title">{localizedText(locale, "最新数据集", "Latest dataset")}</h4>
                  <p className="meta-copy">{prepareResult.summary}</p>
                </div>
                <StatusBadge value="completed" />
              </div>
              <div className="pill-row">
                <span className="inline-chip">{l("版本", "Version")} {prepareResult.datasetVersion.version}</span>
                <span className="inline-chip">{l("行数", "Rows")} {prepareResult.datasetVersion.rowCount}</span>
                <span className="inline-chip">{l("存储", "Storage")} {prepareResult.datasetVersion.storageKey}</span>
              </div>
            </div>
          ) : null}
        </Surface>

        <Surface>
          <p className="section-kicker">{l("暂存制品", "Stage artifact")}</p>
          <h3 className="section-title">{l("暂存模型制品", "Stage model artifact")}</h3>
          <form
            onSubmit={(event) => {
              event.preventDefault();
              void handleStageModelArtifact();
            }}
          >
            <div className="form-field">
              <label className="meta-label" htmlFor="artifact-dataset-version">{l("数据集版本 ID", "Dataset version ID")}</label>
              <input className="field-input" id="artifact-dataset-version" onChange={(event) => setArtifactForm((value) => ({ ...value, datasetVersionId: event.target.value }))} placeholder={localizedText(locale, "先生成数据集或手动填入版本 ID", "Create a dataset first or enter a version ID")} value={artifactForm.datasetVersionId} />
            </div>
            <div className="form-field">
              <label className="meta-label" htmlFor="artifact-base-model">{l("基础模型", "Base model")}</label>
              <input className="field-input" id="artifact-base-model" onChange={(event) => setArtifactForm((value) => ({ ...value, baseModel: event.target.value }))} value={artifactForm.baseModel} />
            </div>
            <div className="form-field">
              <label className="meta-label" htmlFor="artifact-tuning-method">{l("微调方法", "Tuning method")}</label>
              <select className="field-input" id="artifact-tuning-method" onChange={(event) => setArtifactForm((value) => ({ ...value, tuningMethod: event.target.value }))} value={artifactForm.tuningMethod}>
                <option value="distillation">{l("蒸馏", "Distillation")}</option>
                <option value="sft">SFT</option>
                <option value="dpo">DPO</option>
                <option value="adapter">{l("适配器", "Adapter")}</option>
              </select>
            </div>
            <div className="form-field">
              <label className="meta-label" htmlFor="artifact-minimum-rows">{l("最小行数", "Minimum rows")}</label>
              <input className="field-input" id="artifact-minimum-rows" min={1} onChange={(event) => setArtifactForm((value) => ({ ...value, minimumRows: event.target.value }))} type="number" value={artifactForm.minimumRows} />
            </div>
            <div className="field-actions">
              <button className="action-button" disabled={activeForm !== null || artifactForm.datasetVersionId.trim().length === 0} type="submit">
                {activeForm === "artifact" ? localizedText(locale, "正在 stage", "Staging") : localizedText(locale, "Stage 模型制品", "Stage model artifact")}
              </button>
            </div>
          </form>
          {stageResult ? (
            <div className="record-card">
              <div className="record-head">
                <div>
                  <h4 className="record-title">{localizedText(locale, "最新模型制品", "Latest model artifact")}</h4>
                  <p className="meta-copy">{stageResult.summary}</p>
                </div>
                <StatusBadge value={stageResult.modelArtifact.status} />
              </div>
              <div className="pill-row">
                <span className="inline-chip">{l("制品", "Artifact")} {stageResult.modelArtifact.id}</span>
                <span className="inline-chip">{l("数据集", "Dataset")} {stageResult.modelArtifact.datasetVersionId}</span>
                <span className="inline-chip">{l("可验证", "Ready")} {String(stageResult.validationGate.readyForValidation ?? false)}</span>
              </div>
            </div>
          ) : null}
        </Surface>
      </div>

      <div className="content-grid tight">
        <Surface>
          <p className="section-kicker">{l("数据集", "Datasets")}</p>
          <h3 className="section-title">{l("数据集版本", "Dataset versions")}</h3>
          {versionList.length === 0 ? (
            <EmptyState title={localizedText(locale, "还没有数据集版本", "No dataset versions yet")} detail={localizedText(locale, "先生成一条 dataset version，控制台会显示 row 数、来源过滤器和存储位置。", "Create a dataset version to see row count, source filters, and storage location.")} />
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
                    <span className="inline-chip">{l("行数", "Rows")} {version.rowCount}</span>
                    <span className="inline-chip">{l("创建", "Created")} {formatTimestamp(version.createdAt, locale)}</span>
                    <span className="inline-chip">{l("过滤器", "Filter")} {JSON.stringify(version.sourceFilter)}</span>
                  </div>
                </article>
              ))}
            </div>
          )}
        </Surface>

        <Surface>
          <p className="section-kicker">{l("制品", "Artifacts")}</p>
          <h3 className="section-title">{l("模型制品", "Model artifacts")}</h3>
          {artifactList.length === 0 ? (
            <EmptyState title={localizedText(locale, "还没有模型制品", "No model artifacts yet")} detail={localizedText(locale, "当某个 dataset version 满足最小样本阈值后，就可以在上方直接 stage 出正式 model artifact。", "Once a dataset version meets the minimum sample threshold, stage a formal model artifact above.")} />
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
                    <span className="inline-chip">{l("数据集", "Dataset")} {artifact.datasetVersionId}</span>
                    <span className="inline-chip">{l("方法", "Method")} {artifact.tuningMethod}</span>
                    <span className="inline-chip">{l("指标", "Metrics")} {String(artifact.metricsRef?.locator ?? "-")}</span>
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
