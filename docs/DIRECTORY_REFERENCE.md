# 世界树计划 · 目录说明书

> 主索引文件（已拆分）。
> 目标：让新人先快速定位，再进入对应分册查看细节。

## 使用方式

1. 先看本页的分册目录，确认你要找的是“结构”、“交付/运维”还是“配置速查”。
2. 进入对应分册，按章节查找具体路径与职责。
3. 修改目录说明时，优先改分册；仅在分册新增/重命名时更新本页。

## 分册目录

- [01-overview-and-governance.md](directory-reference/01-overview-and-governance.md)
  - 顶层结构、开源协作与治理入口、英文版入口
- [02-system-structure.md](directory-reference/02-system-structure.md)
  - apps/services/packages/modules/applications/adapters/docs 主体结构
- [03-delivery-and-ops.md](directory-reference/03-delivery-and-ops.md)
  - evaluation/infra/migrations/tests/scripts/.github 与交付运维相关说明
- [04-config-and-lookup.md](directory-reference/04-config-and-lookup.md)
  - 根目录配置文件、docs 技术治理补充、文件查找速查

## 维护约定

- 新增或删除目录项时，只更新受影响分册，不做整文件重排。
- 分册标题与路径保持稳定，避免外部文档引用失效。
- 若新增全新大类（例如新增顶层目录），先在分册补内容，再回到本页补导航。

## 变更记录

- 2026-05-28：将单文件目录索引拆分为 4 个分册，主文件改为导航入口。
