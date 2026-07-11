"use client";

import Link from "next/link";
import { useDeferredValue, useState } from "react";

import type { NodeSummaryRecord } from "@yggdrasil/frontend-sdk";

import { useApiResource } from "../lib/use-api-resource";
import { localizedText } from "../i18n";
import { useLocale } from "./locale-provider";
import { EmptyState, ErrorState, LoadingState, PageHeader, StatusBadge, Surface, formatTimestamp } from "./workbench-primitives";

type NodesResponse = {
  nodes: NodeSummaryRecord[];
};

function summarizeContent(content: string): string {
  if (content.length <= 160) {
    return content;
  }
  return `${content.slice(0, 160)}...`;
}

export function NodesPage() {
  const { locale } = useLocale();
  const { data, error, isLoading, reload } = useApiResource<NodesResponse>("/nodes?limit=240");
  const [query, setQuery] = useState("");
  const [typeFilter, setTypeFilter] = useState("all");
  const deferredQuery = useDeferredValue(query.trim().toLowerCase());
  const nodes = data?.nodes ?? [];
  const availableTypes = ["all", ...new Set(nodes.map((node) => node.nodeType))];
  const filteredNodes = nodes.filter((node) => {
    const typeMatches = typeFilter === "all" || node.nodeType === typeFilter;
    const queryMatches =
      deferredQuery.length === 0 ||
      [node.title, node.content, node.id, node.branchId, node.nodeType].join(" ").toLowerCase().includes(deferredQuery);
    return typeMatches && queryMatches;
  });

  if (isLoading) {
    return <LoadingState title={localizedText(locale, "正在读取节点图谱", "Loading memory graph")} />;
  }

  if (error) {
    return <ErrorState detail={error} />;
  }

  return (
    <div>
      <PageHeader
        eyebrow="Memory Nodes"
        title={localizedText(locale, "节点、版本与来源标注", "Nodes, versions, and provenance")}
        summary={<>{localizedText(locale, "这里展示 M4 导入与后续执行写入形成的正式节点面，便于直接检查内容、类型与分支归属。", "Inspect the canonical node surface created by M4 imports and runtime writes, with content, type, and branch provenance in one place.")}</>}
        actions={<button className="ghost-button" onClick={reload} type="button">{localizedText(locale, "刷新节点视图", "Refresh nodes")}</button>}
      />

      <Surface>
        <p className="section-kicker">{localizedText(locale, "筛选", "Filters")}</p>
        <h3 className="section-title">{localizedText(locale, "查找节点", "Find nodes")}</h3>
        <div className="search-row">
          <input className="search-input" onChange={(event) => setQuery(event.target.value)} placeholder={localizedText(locale, "按标题、内容、分支、ID 搜索", "Search title, content, branch, or ID")} value={query} />
          {availableTypes.map((type) => (
            <button
              key={type}
              className={`filter-chip${typeFilter === type ? " active" : ""}`}
              onClick={() => setTypeFilter(type)}
              type="button"
            >
              {type}
            </button>
          ))}
        </div>
      </Surface>

      <div className="record-list">
        {filteredNodes.length === 0 ? (
          <EmptyState title={localizedText(locale, "没有匹配节点", "No matching nodes")} detail={localizedText(locale, "可以调整关键字或节点类型筛选。", "Adjust the query or node type filter.")} />
        ) : (
          filteredNodes.map((node) => (
            <article className="record-card" key={node.id}>
              <div className="record-head">
                <div>
                  <Link className="record-link" href={`/nodes/${encodeURIComponent(node.id)}`}>
                    <h3 className="record-title">{node.title}</h3>
                  </Link>
                  <p className="meta-copy">{summarizeContent(node.content)}</p>
                </div>
                <StatusBadge value={node.status} />
              </div>
              <div className="pill-row">
                <span className="inline-chip">{localizedText(locale, "类型", "type")} {node.nodeType}</span>
                <span className="inline-chip">{localizedText(locale, "分支", "branch")} {node.branchId}</span>
                <span className="inline-chip">{localizedText(locale, "更新", "updated")} {formatTimestamp(node.updatedAt ?? node.createdAt, locale)}</span>
              </div>
            </article>
          ))
        )}
      </div>
    </div>
  );
}
