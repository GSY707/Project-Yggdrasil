# 资产、导入导出与评测数据规格 v0.1

- 文档状态：Candidate
- 版本：v0.1
- 日期：2026-04-16

## 1. 范围

本规格覆盖以下对象：

- Asset
- AssetSegment
- AssetEmbedding
- ProjectPackageManifest
- PackageImportRecord
- EvaluationSuite
- EvaluationCase
- EvaluationRun
- DatasetVersion
- ModelArtifact

## 2. Asset

```yaml
Asset:
  id: string
  projectId: string
  spaceId: string
  branchId: string
  ownerNodeId: string|null
  mediaType: string
  role: original | derived | preview | thumbnail | transcript
  storageKey: string
  checksum: string
  sourceRef: ExternalRef|null
  durationMs: integer|null
  width: integer|null
  height: integer|null
  createdAt: datetime
  createdBy: ActorRef
```

## 3. AssetSegment

```yaml
AssetSegment:
  id: string
  assetId: string
  ordinal: integer
  startOffset: integer
  endOffset: integer
  textExcerpt: string|null
  summary: string|null
  embeddingId: string|null
  createdAt: datetime
```

## 4. AssetEmbedding

```yaml
AssetEmbedding:
  id: string
  ownerKind: asset | asset-segment | node
  ownerId: string
  model: string
  dimension: integer
  vectorRef: ExternalRef
  createdAt: datetime
```

### 4.1 说明

- AssetEmbedding 是第一版需要预留的正式对象，即使多模态模块在第二版交付。

## 5. ProjectPackageManifest

### 5.1 目标

定义项目级导出包的正式清单结构。

### 5.2 结构

```yaml
ProjectPackageManifest:
  id: string
  packageKind: project-export
  packageVersion: string
  projectId: string
  branchId: string
  schemaVersion: string
  includes:
    nodes: boolean
    edges: boolean
    versions: boolean
    sourceAnnotations: boolean
    assets: boolean
    snapshots: boolean
  checksumMap: object
  exportedAt: datetime
  exportedBy: ActorRef
```

### 5.3 冻结决策

- package 的最小正式粒度是项目级，不是任务级。

## 6. PackageImportRecord

```yaml
PackageImportRecord:
  id: string
  packageId: string
  targetProjectId: string
  status: accepted | validated | materialized | failed
  conflictPolicy: fail | overwrite | rebind
  createdAt: datetime
  finishedAt: datetime|null
```

## 7. EvaluationSuite

```yaml
EvaluationSuite:
  id: string
  name: string
  domain: trpg | coding | writing | research | generic
  metricRefs: [string]
  createdAt: datetime
```

## 8. EvaluationCase

```yaml
EvaluationCase:
  id: string
  suiteId: string
  inputRef: ExternalRef
  expectedRef: ExternalRef|null
  tags: [string]
  difficulty: easy | medium | hard
  createdAt: datetime
```

## 9. EvaluationRun

```yaml
EvaluationRun:
  id: string
  suiteId: string
  projectId: string
  subjectKind: module | model | retrieval-policy | workflow
  subjectRef: string
  status: queued | running | completed | failed
  metricsRef: ExternalRef|null
  startedAt: datetime|null
  endedAt: datetime|null
  createdAt: datetime
```

## 10. DatasetVersion

```yaml
DatasetVersion:
  id: string
  datasetName: string
  version: string
  sourceFilter: object
  storageKey: string
  rowCount: integer
  createdAt: datetime
```

## 11. ModelArtifact

```yaml
ModelArtifact:
  id: string
  baseModel: string
  tuningMethod: sft | dpo | distillation | adapter
  datasetVersionId: string
  metricsRef: ExternalRef|null
  storageKey: string
  status: staged | validated | promoted | retired
  createdAt: datetime
```

## 12. 第一版与第二版边界

- 第一版要完整支持 ProjectPackageManifest、EvaluationSuite、EvaluationRun。
- 第一版预留 AssetEmbedding、DatasetVersion、ModelArtifact，但不要求完整业务流程全部上线。