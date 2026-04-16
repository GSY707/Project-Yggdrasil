# 记忆与建树数据规格 v0.1

- 文档状态：Candidate
- 版本：v0.1
- 日期：2026-04-16

## 1. 范围

本规格覆盖以下对象：

- Node
- Edge
- NodeVersion
- SourceAnnotation
- RetrievalRequest
- RetrievalBundle
- ImportPolicy
- ImportJob
- ImportFragment
- TreePlan
- LinkProposal

## 2. Node

### 2.1 目标

Node 是记忆树的基本存储单元，承载短记忆内容而不是长原文。

### 2.2 结构

```yaml
Node:
  id: string
  projectId: string
  spaceId: string
  branchId: string
  parentId: string|null
  rootBranch: identity | context | execution | none
  nodeType: root | identity | context | task | summary | detail | temporary | system | reference
  status: active | temporary | merged | archived | deleted
  title: string
  content: string
  detailLevel: integer
  importance: number
  stability: number
  forgetRate: number
  feedforwardScore: number
  accessScore: number
  activityK: number
  floatScore: number
  latestVersionId: string
  mergedIntoNodeId: string|null
  childrenCount: integer
  edgeCount: integer
  createdAt: datetime
  createdBy: ActorRef
  updatedAt: datetime
  updatedBy: ActorRef
```

### 2.3 约束

- title 表示相对父节点的内容方向，不是随意标签。
- title 建议不超过 64 个字符。
- content 是规范化记忆内容，最大 200 个字符。
- 较长原始材料必须进入 Asset 或 ImportFragment，不允许直接塞进 Node.content。
- detailLevel 取值范围为 0 到 9。
- 除 temporary 节点外，子节点 detailLevel 必须大于父节点。
- root 节点只能有三个正式标题：我是谁、我在哪、我要干什么。
- merged 节点不可再被修改内容，只能通过 mergedIntoNodeId 指向新节点。

### 2.4 语义说明

- importance：记忆重要性。
- stability：知识稳定度。
- forgetRate：被整理和降精度的倾向。
- feedforwardScore：未来主动前馈的优先级。
- accessScore：历史访问强度。
- activityK：记忆持续参数，0 表示极稳定，1 表示每次访问都倾向建议修订。
- floatScore：记忆浮动强度，反映上浮或下沉倾向。该字段通常为 derived。

## 3. Edge

### 3.1 结构

```yaml
Edge:
  id: string
  projectId: string
  spaceId: string
  branchId: string
  fromNodeId: string
  toNodeId: string
  relationType: string
  weight: number
  reason: string
  evidenceAnnotationIds: [string]
  status: active | deprecated | deleted
  createdAt: datetime
  createdBy: ActorRef
  updatedAt: datetime
  updatedBy: ActorRef
```

### 3.2 约束

- Edge 是有向边。
- fromNodeId 和 toNodeId 不能相同，除非未来明确支持自环。
- relationType 必须来自平台注册词表或模块已登记命名空间。
- reason 是简短关联说明，建议不超过 200 个字符。

## 4. NodeVersion

### 4.1 结构

```yaml
NodeVersion:
  id: string
  nodeId: string
  versionNo: integer
  titleSnapshot: string
  contentSnapshot: string
  parentIdSnapshot: string|null
  scoreSnapshot:
    importance: number
    stability: number
    forgetRate: number
    feedforwardScore: number
    accessScore: number
    activityK: number
    floatScore: number
  changeReason: string
  derivedFromVersionId: string|null
  createdAt: datetime
  createdBy: ActorRef
```

### 4.2 约束

- 每个 NodeVersion 对同一 nodeId 的 versionNo 必须单调递增。
- 默认访问节点时返回 Node 当前版本，但系统必须支持回溯旧版本。

## 5. SourceAnnotation

### 5.1 目标

统一表达外部来源、内部引用与推理得到的信息出处。

### 5.2 结构

```yaml
SourceAnnotation:
  id: string
  projectId: string
  branchId: string
  ownerKind: node | edge | version | task | pr | package
  ownerId: string
  sourceType: external | memory | human | inference | system
  sourceRef: ExternalRef|null
  excerpt: string|null
  inferenceSummary: string|null
  evidenceRefs: [EntityRef]
  confidence: number
  createdAt: datetime
  createdBy: ActorRef
```

### 5.3 约束

- 外部事实必须至少有一个 external 类型 SourceAnnotation。
- 复杂推理结果必须至少有一个 inference 类型 SourceAnnotation，并填写 inferenceSummary。
- excerpt 建议不超过 500 个字符。

## 6. RetrievalRequest

### 6.1 结构

```yaml
RetrievalRequest:
  id: string
  projectId: string
  spaceId: string
  branchId: string
  queryText: string|null
  seedNodeRefs: [EntityRef]
  traversalStart: roots | seeds | mixed
  expansionMode: parallel | serial
  readDepth: integer
  lateralHops: integer
  maxRelatedNodes: integer
  maxLeafNodes: integer
  precisionMode: coarse | balanced | fine
  includeNaturalLanguageSummary: boolean
  includeChildNames: boolean
  includeRelatedNames: boolean
  tokenBudget: integer|null
  createdAt: datetime
```

### 6.2 约束

- RetrievalRequest 至少提供 queryText 或 seedNodeRefs 之一。
- 系统返回节点内容时，默认必须同时返回子节点名与关联节点名。
- 当 seedNodeRefs 为空时，默认从三个根分支开始扩展。
- 默认 expansionMode 为 parallel，用于覆盖原始设计中的并发读取要求。

## 7. RetrievalBundle

### 7.1 结构

```yaml
RetrievalBundle:
  requestId: string
  matchedNodeRefs: [EntityRef]
  nodePayloads: [object]
  childNameMap: object
  relatedNameMap: object
  sourceAnnotationRefs: [string]
  naturalLanguageSummary: string|null
  truncated: boolean
  generatedAt: datetime
```

## 8. ImportPolicy

### 8.1 结构

```yaml
ImportPolicy:
  segmentTargetChars: integer
  allowDiscardLowValue: boolean
  preferredBuilderModel: string|null
  treePreferencePrompt: string|null
  linkStrategy: [vector | ppr | keyword | hybrid]
  mergePolicy: conservative | balanced | aggressive
```

### 8.2 说明

- treePreferencePrompt 用于承载原始设计中的“建树任务 Prompt”，暴露主模型的建树偏好。
- 它属于正式策略数据，不是随意散落在提示词里的临时说明。

## 9. ImportJob

### 9.1 结构

```yaml
ImportJob:
  id: string
  projectId: string
  branchId: string
  sourceKind: file | stream | package | clipboard
  status: accepted | preprocessing | pre-reading | planning | materializing | completed | failed | cancelled
  importPolicy: ImportPolicy
  requestedBy: ActorRef
  tokenBudget: integer|null
  costBudget: number|null
  failureReason: string|null
  startedAt: datetime|null
  finishedAt: datetime|null
  createdAt: datetime
```

### 9.2 状态语义

- preprocessing：切分、清洗、标准化。
- pre-reading：Sub-Agent 或辅助流程预读与建立全局概览。
- planning：生成 TreePlan 和 LinkProposal。
- materializing：把临时节点与关联写入主存储。

## 10. ImportFragment

### 10.1 结构

```yaml
ImportFragment:
  id: string
  importJobId: string
  ordinal: integer
  rawRef: ExternalRef
  normalizedText: string
  approxTokens: integer
  relatedHints: [string]
  createdAt: datetime
```

## 11. TreePlan

### 11.1 结构

```yaml
TreePlan:
  id: string
  importJobId: string
  status: proposed | accepted | materialized | rejected | superseded
  candidateNodePayloads: [object]
  candidateEdgePayloads: [object]
  discardedFragmentRefs: [string]
  rationale: string
  proposedBy: ActorRef
  createdAt: datetime
```

### 11.2 约束

- TreePlan 是建树候选方案，不等于最终树。
- 根据当前冻结决策，大规模重排、合并、删减不要求人工审批。
- 但所有 materialized 结果都必须有版本和审计记录。

## 12. LinkProposal

### 12.1 结构

```yaml
LinkProposal:
  id: string
  importJobId: string
  fromCandidateRef: EntityRef
  toCandidateRef: EntityRef
  relationType: string
  score: number
  rationale: string
  algorithmSource: vector | ppr | keyword | hybrid | llm
  createdAt: datetime
```

## 13. 第一版与第二版边界

- 第一版必须完整支持 Node、Edge、NodeVersion、SourceAnnotation、RetrievalRequest、ImportJob。
- 第二版自动整理与主动关联发现会继续使用相同对象，不允许再造一套平行数据模型。