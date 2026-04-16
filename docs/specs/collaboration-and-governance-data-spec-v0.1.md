# 协作与治理数据规格 v0.1

- 文档状态：Candidate
- 版本：v0.1
- 日期：2026-04-16

## 1. 范围

本规格覆盖以下对象：

- Project
- Space
- MemoryBranch
- SpaceMount
- PermissionTuple
- PullRequest
- ReviewComment

## 2. Project

```yaml
Project:
  id: string
  displayName: string
  status: active | archived | deleted
  exportPolicy: project-package-only
  createdAt: datetime
  createdBy: ActorRef
```

### 2.1 冻结决策

- 第一版实际运行单项目。
- 但所有正式对象都必须携带 projectId。
- 第一版导入导出的最小正式粒度是项目级 package。

## 3. Space

```yaml
Space:
  id: string
  projectId: string
  spaceType: default | personal | shared | system
  status: active | archived | deleted
  ownerSubject: string|null
  createdAt: datetime
```

### 3.1 说明

- 第一版默认只开放默认空间。
- 第二版共享空间沿用同一对象，不新造模型。

## 4. MemoryBranch

```yaml
MemoryBranch:
  id: string
  projectId: string
  spaceId: string
  name: string
  baseBranchId: string|null
  headRef: string|null
  status: active | frozen | merged | deleted
  createdAt: datetime
  createdBy: ActorRef
```

### 4.1 说明

- 第一版至少有 branch_main。
- Sub-Agent 分支、PR 分支与第二版共享空间分支统一复用 MemoryBranch。

## 5. SpaceMount

```yaml
SpaceMount:
  id: string
  projectId: string
  hostSpaceId: string
  mountedSpaceId: string
  mountMode: readonly | copy-on-write | bidirectional
  status: active | disabled | detached
  createdAt: datetime
  createdBy: ActorRef
```

### 5.1 冻结决策

- 第二版共享空间必须支持三种挂载语义：只读挂载、写时复制、双向同步。
- 因此第一版就必须保留 SpaceMount 的数据结构和 mountMode 枚举。

## 6. PermissionTuple

```yaml
PermissionTuple:
  id: string
  projectId: string
  subject: string
  relation: string
  resource: string
  condition: object|null
  effect: allow | deny
  createdAt: datetime
  createdBy: ActorRef
```

## 7. PullRequest

```yaml
PullRequest:
  id: string
  projectId: string
  sourceBranchId: string
  targetBranchId: string
  title: string
  summary: string
  status: open | approved | rejected | merged | closed
  createdBy: ActorRef
  reviewedBy: ActorRef|null
  mergedAt: datetime|null
  createdAt: datetime
```

### 7.1 约束

- Sub-Agent 不直接写主分支，必须通过 PullRequest。
- merged 之后 sourceBranchId 不自动删除，是否清理由策略决定。

## 8. ReviewComment

```yaml
ReviewComment:
  id: string
  prId: string
  author: ActorRef
  targetKind: node | edge | plan | package
  targetId: string
  body: string
  status: open | resolved | rejected
  createdAt: datetime
  resolvedAt: datetime|null
```

## 9. 第一版与第二版边界

- 第一版必须完整支持 Project、MemoryBranch、PullRequest。
- 第一版可以只开放 default space 和 main branch。
- 第二版共享空间直接在 Space、SpaceMount、PermissionTuple 上扩展，不重做模型。