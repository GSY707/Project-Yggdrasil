"use client";

import { useEffect, useMemo, useState } from "react";

import type { MCPBridgeState, MCPServerDefinition, MCPSyncedServer } from "@yggdrasil/frontend-sdk";

import { postApiJson, useApiResource } from "../lib/use-api-resource";
import { EmptyState, ErrorState, LoadingState, PageHeader, Surface, StatusBadge, formatTimestamp } from "./workbench-primitives";

export function MCPBridgePage() {
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
    return <LoadingState title="正在读取 MCP bridge 状态" />;
  }

  if (bridge.error) {
    return <ErrorState detail={bridge.error} />;
  }

  if (!bridge.data) {
    return <EmptyState title="MCP bridge 不可用" detail="未能读取到 MCP bridge 状态。" />;
  }

  const tools = bridge.data.tools ?? [];
  const servers = bridge.data.servers ?? [];

  return (
    <div>
      <PageHeader
        eyebrow="MCP Bridge"
        title="MCP bridge 与项目工作区管理"
        summary={<>这里统一管理 bridge 使用的项目工作区、内建 MCP server、从本机用户配置复制进来的 MCP server，以及当前已桥接到运行时的工具。</>}
        actions={
          <div className="field-actions">
            <button className="ghost-button" disabled={pendingAction !== null} onClick={() => bridge.reload()} type="button">刷新状态</button>
            <button className="ghost-button" disabled={pendingAction !== null} onClick={() => void handleRefreshImports()} type="button">刷新本机导入源</button>
            <button className="action-button" disabled={pendingAction !== null} onClick={() => void handleSyncAll()} type="button">同步全部服务</button>
          </div>
        }
      />

      {actionError ? <ErrorState title="MCP 操作失败" detail={actionError} /> : null}

      <div className="content-grid tight">
        <Surface>
          <p className="section-kicker">Workspace</p>
          <h3 className="section-title">项目工作区</h3>
          <p className="meta-copy">read、edit、search、execute、python 这些内建 MCP server 都会以这里配置的目录作为工作区根目录。</p>
          <div className="form-field">
            <label className="meta-label" htmlFor="mcp-workspace-option">快捷选项</label>
            <select
              className="field-input"
              id="mcp-workspace-option"
              onChange={(event) => setWorkspaceDraft(event.target.value)}
              value={workspaceDraft}
            >
              {bridge.data.workspaceOptions.map((option) => (
                <option key={`${option.source}-${option.value}`} value={option.value}>{option.label}</option>
              ))}
            </select>
          </div>
          <div className="form-field">
            <label className="meta-label" htmlFor="mcp-workspace-path">Workspace Path</label>
            <input className="field-input" id="mcp-workspace-path" onChange={(event) => setWorkspaceDraft(event.target.value)} value={workspaceDraft} />
          </div>
          <div className="field-actions">
            <button className="action-button" disabled={pendingAction !== null || workspaceDraft.trim().length === 0} onClick={() => void handleSaveWorkspace()} type="button">
              {pendingAction === "workspace" ? "保存中" : "保存项目工作区"}
            </button>
          </div>
        </Surface>

        <Surface>
          <p className="section-kicker">Imports</p>
          <h3 className="section-title">本机可复制的 MCP 服务</h3>
          {bridge.data.availableImports.length === 0 ? (
            <EmptyState title="没有发现额外的本机 MCP 服务" detail="bridge 已经内建了 read/edit/search/execute/python，外部导入源会在这里列出。" />
          ) : (
            <div className="record-list">
              {bridge.data.availableImports.map((server) => (
                <article className="record-card" key={server.id}>
                  <div className="record-head">
                    <div>
                      <h4 className="record-title">{server.displayName}</h4>
                      <p className="meta-copy">{server.id}</p>
                    </div>
                    <StatusBadge value={server.enabled ? "enabled" : "copied-disabled"} />
                  </div>
                  <p className="meta-copy">{server.description ?? "从本机 MCP 配置复制的服务定义。"}</p>
                  <div className="pill-row">
                    <span className="inline-chip">origin {server.origin}</span>
                    <span className="inline-chip">prefix {server.toolPrefix}</span>
                  </div>
                  {server.sourcePath ? <pre className="meta-copy mono">{server.sourcePath}</pre> : null}
                </article>
              ))}
            </div>
          )}
        </Surface>

        <Surface>
          <p className="section-kicker">Servers</p>
          <h3 className="section-title">Bridge 服务目录</h3>
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
                  <p className="meta-copy">{server.description ?? "该服务未提供额外说明。"}</p>
                  <div className="pill-row">
                    <span className="inline-chip">origin {server.origin}</span>
                    <span className="inline-chip">prefix {server.toolPrefix}</span>
                    <span className="inline-chip">keepAlive {String(server.keepAlive)}</span>
                    <span className="inline-chip">tools {syncState?.toolCount ?? 0}</span>
                    <span className="inline-chip">synced {formatTimestamp(syncState?.lastSyncedAt ?? null)}</span>
                  </div>
                  <pre className="meta-copy mono">{[server.command, ...server.args].join(" ")}</pre>
                  {server.sourcePath ? <p className="meta-copy">source {server.sourcePath}</p> : null}
                  {syncState?.error ? <p className="error-copy">{syncState.error}</p> : null}
                  <div className="field-actions">
                    <button className="ghost-button" disabled={pendingAction !== null} onClick={() => void handleSyncServer(server.id)} type="button">
                      {pendingAction === syncKey ? "同步中" : "同步服务"}
                    </button>
                    <button className="action-button" disabled={pendingAction !== null} onClick={() => void handleToggleServer(server)} type="button">
                      {pendingAction === actionKey ? "处理中" : server.enabled ? "禁用服务" : "启用服务"}
                    </button>
                  </div>
                </article>
              );
            })}
          </div>
        </Surface>

        <Surface>
          <p className="section-kicker">Tools</p>
          <h3 className="section-title">当前已桥接工具</h3>
          {tools.length === 0 ? (
            <EmptyState title="还没有桥接工具" detail="请先同步至少一个启用中的 MCP 服务。" />
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
                  <p className="meta-copy">{tool.description ?? "该工具未提供额外描述。"}</p>
                </article>
              ))}
            </div>
          )}
        </Surface>
      </div>
    </div>
  );
}