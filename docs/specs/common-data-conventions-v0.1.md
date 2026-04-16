# 通用数据约定 v0.1

- 文档状态：Candidate
- 版本：v0.1
- 日期：2026-04-16

## 1. 目标

定义所有正式数据对象共享的命名、作用域、时间、版本、审计和字段语义，避免模块各自发明不同风格的数据结构。

## 2. ID 规则

### 2.1 基本规则

- 所有 ID 都是不可解析的业务主键，外部模块不得依赖内部排序语义。
- 推荐使用带前缀的 ULID 字符串。
- 同一类对象必须使用固定前缀。

### 2.2 推荐前缀

- project_
- space_
- branch_
- node_
- edge_
- ver_
- srcann_
- import_
- frag_
- treeplan_
- task_
- run_
- snap_
- pr_
- review_
- modins_
- hookreg_
- evt_
- outbox_
- asset_
- aseg_
- aemb_
- pkg_
- evalsuite_
- evalcase_
- evalrun_
- dataset_
- modelart_

## 3. 作用域字段

### 3.1 一般规则

- 所有业务对象必须携带 projectId。
- 与记忆、任务、协作直接相关的对象必须同时携带 branchId。
- 第一版允许使用默认 space，但字段不能缺失。

### 3.2 默认值

- 默认项目：由宿主环境决定，不在规格里硬编码。
- 默认空间：space_default。
- 默认分支：branch_main。

## 4. 时间字段

- 所有时间一律使用 UTC。
- 格式统一为 RFC 3339 / ISO 8601 字符串。
- 字段命名统一使用 At 后缀。

示例：

- createdAt
- updatedAt
- startedAt
- finishedAt
- publishedAt

## 5. 审计字段

除明确只读的派生对象外，正式对象默认具备以下审计字段：

- createdAt
- createdBy
- updatedAt
- updatedBy

可选字段：

- deletedAt
- deletedBy
- reason

createdBy / updatedBy 使用 ActorRef 结构：

```yaml
ActorRef:
  type: user | agent | module | system
  id: string
```

## 6. 版本语义

- 资源本身的快照版本使用资源内 version 或 versionNo 表达。
- 协议版本使用文档名和 apiVersion 表达。
- 事件版本使用 eventVersion 表达。
- manifest 版本使用 semver。

## 7. 分数字段

下列分数字段统一使用 0 到 1 的闭区间实数：

- importance
- stability
- forgetRate
- feedforwardScore
- accessScore
- activityK
- floatScore
- confidence
- weight

约束：

- 0 表示最低或最弱。
- 1 表示最高或最强。
- 若对象未提供明确值，写入方必须决定默认值，不能使用 null 逃避语义。

## 8. 文本字段

- 所有文本使用 UTF-8。
- 长度约束默认以字符数计算，而不是字节数。
- 长文本不得塞进本来定义为短记忆的字段，必须转入 Asset 或外部对象引用。

## 9. 状态字段

- 状态字段统一使用小写 kebab-case 或小写单词，不使用中文枚举。
- 每个状态对象必须明确定义合法状态流转，模块不得发明未登记状态。

## 10. 引用字段

### 10.1 通用实体引用

```yaml
EntityRef:
  kind: string
  id: string
```

### 10.2 外部引用

```yaml
ExternalRef:
  type: url | file | object-storage | package-entry | citation
  locator: string
  checksum: string|null
```

## 11. 写入权限语义

字段按写入权限分为三类：

- kernel-only：只能由 Kernel 或内核态流程写入。
- controlled-write：模块可写，但必须通过正式命令或 hook。
- derived：由系统计算得出，模块不得直接写入。

如果对象没有单独说明，默认所有状态字段和主键字段属于 kernel-only。

## 12. 空值规则

- 语义上存在默认值的字段不应使用 null，应写显式默认值。
- 只有“该信息暂时不存在且允许缺席”的字段才允许为 null。

## 13. 兼容性规则

- 新增非必填字段属于向后兼容。
- 删除字段、修改字段语义、修改状态枚举都是破坏性变更。
- 破坏性变更必须先升级规格版本，再升级模块实现。

## 14. 第一版技术前提

- 模块作者不得假设系统只有一个项目，虽然第一版只运行单项目。
- 模块作者不得假设没有 pause / resume，只因为该特性在第二版交付。
- 模块作者不得假设没有共享空间，只因为第一版只开放默认空间。