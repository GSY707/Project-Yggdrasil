"use client";

import { useEffect, useMemo, useState } from "react";

import type { MCPBridgeState, MCPServerDefinition, MCPSyncedServer } from "@yggdrasil/frontend-sdk";

import { postApiJson, useApiResource } from "../lib/use-api-resource";
import { localizedText } from "../i18n";
import { EmptyState, ErrorState, LoadingState, PageHeader, Surface, StatusBadge, formatTimestamp } from "./workbench-primitives";
import { useLocale } from "./locale-provider";

const MCP_SERVER_COPY: Record<string, { zh: string; en: string }> = {
  "chrome-devtools": {
    zh: "从本机配置复制的 Chrome DevTools MCP 服务定义。",
    en: "Copy of the locally configured Chrome DevTools MCP server definition.",
  },
  markitdown: {
    zh: "从本机配置复制的 MarkItDown MCP 服务定义。",
    en: "Copy of the locally configured MarkItDown MCP server definition.",
  },
  "workspace-read": {
    zh: "在项目工作区读取文件并列出目录的内建 MCP 服务。",
    en: "Builtin MCP server for reading files and listing directories in the configured project workspace.",
  },
  "workspace-edit": {
    zh: "在项目工作区创建文件并替换文本的内建 MCP 服务。",
    en: "Builtin MCP server for creating files and replacing text in the configured project workspace.",
  },
  "workspace-search": {
    zh: "在项目工作区匹配文件并搜索文本的内建 MCP 服务。",
    en: "Builtin MCP server for globbing files and searching text inside the configured project workspace.",
  },
  "workspace-execute": {
    zh: "在项目工作区运行 shell 命令的内建 MCP 服务。",
    en: "Builtin MCP server for running shell commands inside the configured project workspace.",
  },
  "workspace-python": {
    zh: "在项目工作区运行 Python 代码片段的内建 MCP 服务。",
    en: "Builtin MCP server for running Python snippets inside the configured project workspace.",
  },
  "workspace-web": {
    zh: "用于公开网络搜索和网页读取的内建 MCP 服务。",
    en: "Builtin MCP server for public web search and webpage retrieval.",
  },
  "workspace-paper": {
    zh: "通过主要公共 API 搜索学术论文的内建 MCP 服务。",
    en: "Builtin MCP server for scholarly paper search across major public APIs.",
  },
  "workspace-markitdown": {
    zh: "将 URL 或文件转换为 Markdown，并在需要时回退到 MarkItDown 的内建 MCP 服务。",
    en: "Builtin MCP server for URL/file to markdown conversion with markitdown fallback.",
  },
  "workspace-report": {
    zh: "用于报告项目、运行时和工具问题的内建 MCP 服务。",
    en: "Builtin MCP server for reporting project/runtime/tool issues.",
  },
};

function serverDescription(server: { id: string; description?: string | null }, locale: Parameters<typeof localizedText>[0], fallback: string): string {
  const copy = MCP_SERVER_COPY[server.id];
  return copy ? localizedText(locale, copy.zh, copy.en) : server.description ?? fallback;
}

export function MCPBridgePage() {
  const { locale } = useLocale();
  const l = (zhCN: string, english: string) => localizedText(locale, zhCN, english);
  const bridge = useApiResource<MCPBridgeState>("/mcp");
  const [workspaceDraft, setWorkspaceDraft] = useState("");
  const [actionError, setActionError] = useState<string | null>(null);
  const [pendingAction, setPendingAction] = useState<string | null>(null);

  useEffect(() => {
    if (!bridge.data?.projectWorkspace) {
      return;
    }
    setWorkspaceDraft(bridge.data.projectWorkspace);
  }, [bridge.data?.projectWorkspace]);

  const syncedById = useMemo(
    () => new Map((bridge.data?.syncedServers ?? []).map((server) => [server.id, server])),
    [bridge.data?.syncedServers],
  );

  async function runAction(actionId: string, request: () => Promise<void>) {
    setPendingAction(actionId);
    setActionError(null);
    try {
      await request();
      bridge.reload();
    } catch (error) {
      setActionError(error instanceof Error ? error.message : String(error));
    } finally {
      setPendingAction(null);
    }
  }

  async function handleSaveWorkspace() {
    await runAction("workspace", async () => {
      await postApiJson("/mcp/workspace", { projectWorkspace: workspaceDraft.trim() });
    });
  }

  async function handleRefreshImports() {
    await runAction("refresh-imports", async () => {
      await postApiJson("/mcp/imports/refresh");
    });
  }

  async function handleSyncAll() {
    await runAction("sync-all", async () => {
      await postApiJson("/mcp/sync", {});
    });
  }

  async function handleSyncServer(serverId: string) {
    await runAction(`sync:${serverId}`, async () => {
      await postApiJson(`/mcp/servers/${encodeURIComponent(serverId)}/sync`);
    });
  }

  async function handleToggleServer(server: MCPServerDefinition) {
    await runAction(`toggle:${server.id}`, async () => {
      await postApiJson(`/mcp/servers/${encodeURIComponent(server.id)}/${server.enabled ? "disable" : "enable"}`);
    });
  }

  if (bridge.isLoading) {
    return <LoadingState title={localizedText(locale, "正在读取 MCP bridge 状态", "Loading MCP bridge state")} />;
  }

  if (bridge.error) {
    return <ErrorState detail={bridge.error} />;
  }

  if (!bridge.data) {
    return <EmptyState title={localizedText(locale, "MCP bridge 不可用", "MCP bridge unavailable")} detail={localizedText(locale, "未能读取到 MCP bridge 状态。", "The MCP bridge state could not be read.")} />;
  }

  const tools = bridge.data.tools ?? [];
  const servers = bridge.data.servers ?? [];
  const workspaceOptions = bridge.data.workspaceOptions ?? [];
  const availableImports = bridge.data.availableImports ?? [];

  return (
    <div>
      <PageHeader
        eyebrow={l("MCP 桥接", "MCP bridge")}
        title={localizedText(locale, "MCP bridge 与项目工作区管理", "MCP bridge and project workspace")}
        summary={<>{localizedText(locale, "这里统一管理 bridge 使用的项目工作区、内建 MCP server、从本机用户配置复制进来的 MCP server，以及当前已桥接到运行时的工具。", "Manage the bridge workspace, built-in MCP servers, imported user servers, and tools currently exposed to runtime.")}</>}
        actions={
          <div className="field-actions">
            <button className="ghost-button" disabled={pendingAction !== null} onClick={() => bridge.reload()} type="button">{localizedText(locale, "刷新状态", "Refresh state")}</button>
            <button className="ghost-button" disabled={pendingAction !== null} onClick={() => void handleRefreshImports()} type="button">{localizedText(locale, "刷新本机导入源", "Refresh imports")}</button>
            <button className="action-button" disabled={pendingAction !== null} onClick={() => void handleSyncAll()} type="button">{localizedText(locale, "同步全部服务", "Sync all servers")}</button>
          </div>
        }
      />

      {actionError ? <ErrorState title={localizedText(locale, "MCP 操作失败", "MCP operation failed")} detail={actionError} /> : null}

      <div className="content-grid tight">
        <Surface>
          <p className="section-kicker">{l("工作区", "Workspace")}</p>
          <h3 className="section-title">{localizedText(locale, "项目工作区", "Project workspace")}</h3>
          <p className="meta-copy">{localizedText(locale, "read、edit、search、execute、python 这些内建 MCP server 都会以这里配置的目录作为工作区根目录。", "Built-in read, edit, search, execute, and python MCP servers use this directory as their workspace root.")}</p>
          <div className="form-field">
            <label className="meta-label" htmlFor="mcp-workspace-option">{l("快捷选项", "Quick options")}</label>
            <select
              className="field-input"
              id="mcp-workspace-option"
              onChange={(event) => setWorkspaceDraft(event.target.value)}
              value={workspaceDraft}
            >
              {workspaceOptions.map((option) => (
                <option key={`${option.source}-${option.value}`} value={option.value}>
                  {option.source === "workspace-root" ? l("当前仓库根目录", "Current repository root") : option.source === "mcp-bridge-config" ? l("当前 MCP 项目工作区", "Current MCP project workspace") : option.label}
                </option>
              ))}
            </select>
          </div>
          <div className="form-field">
            <label className="meta-label" htmlFor="mcp-workspace-path">{l("工作区路径", "Workspace path")}</label>
            <input className="field-input" id="mcp-workspace-path" onChange={(event) => setWorkspaceDraft(event.target.value)} value={workspaceDraft} />
          </div>
          <div className="field-actions">
            <button className="action-button" disabled={pendingAction !== null || workspaceDraft.trim().length === 0} onClick={() => void handleSaveWorkspace()} type="button">
              {pendingAction === "workspace" ? localizedText(locale, "保存中", "Saving") : localizedText(locale, "保存项目工作区", "Save workspace")}
            </button>
          </div>
        </Surface>

        <Surface>
          <p className="section-kicker">{l("导入", "Imports")}</p>
          <h3 className="section-title">{localizedText(locale, "本机可复制的 MCP 服务", "MCP servers available to import")}</h3>
          {availableImports.length === 0 ? (
            <EmptyState title={localizedText(locale, "没有发现额外的本机 MCP 服务", "No additional local MCP servers")} detail={localizedText(locale, "bridge 已经内建了 read/edit/search/execute/python，外部导入源会在这里列出。", "The bridge already includes read/edit/search/execute/python; external import sources appear here.")} />
          ) : (
            <div className="record-list">
              {availableImports.map((server) => (
                <article className="record-card" key={server.id}>
                  <div className="record-head">
                    <div>
                      <h4 className="record-title">{server.displayName}</h4>
                      <p className="meta-copy">{server.id}</p>
                    </div>
                    <StatusBadge value={server.enabled ? "enabled" : "copied-disabled"} />
                  </div>
                  <p className="meta-copy">{serverDescription(server, locale, localizedText(locale, "从本机 MCP 配置复制的服务定义。", "Server definition copied from local MCP configuration."))}</p>
                  <div className="pill-row">
                    <span className="inline-chip">{l("来源", "Origin")} {server.origin}</span>
                    <span className="inline-chip">{l("前缀", "Prefix")} {server.toolPrefix}</span>
                  </div>
                  {server.sourcePath ? <pre className="meta-copy mono">{server.sourcePath}</pre> : null}
                </article>
              ))}
            </div>
          )}
        </Surface>

        <Surface>
          <p className="section-kicker">{l("服务", "Servers")}</p>
          <h3 className="section-title">{localizedText(locale, "Bridge 服务目录", "Bridge server catalog")}</h3>
          <div className="record-list">
            {servers.map((server) => {
              const syncState = syncedById.get(server.id) as MCPSyncedServer | undefined;
              const actionKey = `toggle:${server.id}`;
              const syncKey = `sync:${server.id}`;
              return (
                <article className="record-card" key={server.id}>
                  <div className="record-head">
                    <div>
                      <h4 className="record-title">{server.displayName}</h4>
                      <p className="meta-copy">{server.id}</p>
                    </div>
                    <StatusBadge value={syncState?.status ?? (server.enabled ? "pending-sync" : "disabled")} />
                  </div>
                  <p className="meta-copy">{serverDescription(server, locale, localizedText(locale, "该服务未提供额外说明。", "This server has no additional description."))}</p>
                  <div className="pill-row">
                    <span className="inline-chip">{l("来源", "Origin")} {server.origin}</span>
                    <span className="inline-chip">{l("前缀", "Prefix")} {server.toolPrefix}</span>
                    <span className="inline-chip">{l("保活", "Keep alive")} {String(server.keepAlive)}</span>
                    <span className="inline-chip">{l("工具", "Tools")} {syncState?.toolCount ?? 0}</span>
                    <span className="inline-chip">{l("同步于", "Synced")} {formatTimestamp(syncState?.lastSyncedAt ?? null, locale)}</span>
                  </div>
                  <pre className="meta-copy mono">{[server.command, ...server.args].join(" ")}</pre>
                  {server.sourcePath ? <p className="meta-copy">{l("来源", "Source")} {server.sourcePath}</p> : null}
                  {syncState?.error ? <p className="error-copy">{syncState.error}</p> : null}
                  <div className="field-actions">
                    <button className="ghost-button" disabled={pendingAction !== null} onClick={() => void handleSyncServer(server.id)} type="button">
                      {pendingAction === syncKey ? localizedText(locale, "同步中", "Syncing") : localizedText(locale, "同步服务", "Sync server")}
                    </button>
                    <button className="action-button" disabled={pendingAction !== null} onClick={() => void handleToggleServer(server)} type="button">
                      {pendingAction === actionKey ? localizedText(locale, "处理中", "Working") : server.enabled ? localizedText(locale, "禁用服务", "Disable server") : localizedText(locale, "启用服务", "Enable server")}
                    </button>
                  </div>
                </article>
              );
            })}
          </div>
        </Surface>

        <Surface>
          <p className="section-kicker">{l("工具", "Tools")}</p>
          <h3 className="section-title">{localizedText(locale, "当前已桥接工具", "Bridged tools")}</h3>
          {tools.length === 0 ? (
            <EmptyState title={localizedText(locale, "还没有桥接工具", "No bridged tools")} detail={localizedText(locale, "请先同步至少一个启用中的 MCP 服务。", "Sync at least one enabled MCP server first.")} />
          ) : (
            <div className="record-list">
              {tools.map((tool) => (
                <article className="record-card" key={tool.exposedName}>
                  <div className="record-head">
                    <div>
                      <h4 className="record-title">{tool.exposedName}</h4>
                      <p className="meta-copy">{tool.serverDisplayName} / {tool.remoteToolName}</p>
                    </div>
                  </div>
                  <p className="meta-copy">{serverDescription({ id: tool.serverId, description: tool.description }, locale, localizedText(locale, "该工具未提供额外描述。", "This tool has no additional description."))}</p>
                </article>
              ))}
            </div>
          )}
        </Surface>
      </div>
    </div>
  );
}
