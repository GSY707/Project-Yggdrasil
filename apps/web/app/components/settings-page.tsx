"use client";

import Link from "next/link";

import type { ApplicationCatalogItem, ServiceHealthSnapshot } from "@yggdrasil/frontend-sdk";

import { useApiResource } from "../lib/use-api-resource";
import { ErrorState, LoadingState, PageHeader, StatCard, StatusBadge, Surface } from "./workbench-primitives";

type ApplicationsResponse = { activeAppId: string; applications: ApplicationCatalogItem[] };

const DEFAULT_APP_IDS = [
  "yggdrasil.app.deep-research",
  "yggdrasil.app.graduate-researcher",
  "yggdrasil.app.coding-greenfield",
  "yggdrasil.app.knowledge-studio",
];

const USER_APP_SUMMARIES: Record<string, string> = {
  "yggdrasil.app.deep-research": "研究开放问题，输出证据、结论和不确定性边界。",
  "yggdrasil.app.graduate-researcher": "整理学习资料、论文方向和研究写作任务。",
  "yggdrasil.app.coding-greenfield": "从产品想法或原型启动可运行的软件项目。",
  "yggdrasil.app.knowledge-studio": "把资料、访谈、笔记和创作设定沉淀为知识资产。",
};

function aiServiceCopy(status: ServiceHealthSnapshot["providerStatus"]): string {
  if (!status) {
    return "连接状态暂不可用。";
  }
  if (status.status === "ready") {
    return "AI 服务已连接，可以启动任务。";
  }
  if (status.status === "warning") {
    return "AI 服务连接需要确认，建议先创建草稿。";
  }
  return "请先连接 AI 服务，再启动任务。";
}

export function SettingsPage() {
  const health = useApiResource<ServiceHealthSnapshot>("/health");
  const applications = useApiResource<ApplicationsResponse>("/applications");

  if (health.isLoading || applications.isLoading) {
    return <LoadingState title="正在读取设置" />;
  }

  const providerStatus = health.data?.providerStatus;
  const aiServiceValue = providerStatus?.status === "ready" ? "已连接" : providerStatus?.status === "warning" ? "需确认" : "未连接";
  const apps = applications.data?.applications ?? [];
  const activeApp = apps.find((item) => item.application.appId === applications.data?.activeAppId);
  const defaultApps = DEFAULT_APP_IDS.map((appId) => apps.find((item) => item.application.appId === appId)).filter(Boolean) as ApplicationCatalogItem[];

  return (
    <div>
      <PageHeader
        eyebrow="设置"
        title="本地产品设置"
        summary={<>普通设置只保留启动任务必须理解的事项：AI 服务、预算、本地数据、应用默认值和隐私边界。</>}
        actions={
          <>
            <Link className="action-button" href="/tasks">新建任务</Link>
            <Link className="ghost-button" href="/release">帮助与诊断</Link>
          </>
        }
      />

      {health.error ? <ErrorState title="本地服务状态不可用" detail={health.error} /> : null}
      {applications.error ? <ErrorState title="应用设置不可用" detail={applications.error} /> : null}

      <section className="stat-grid">
        <StatCard label="AI Service" value={aiServiceValue} copy={aiServiceCopy(providerStatus)} />
        <StatCard label="Spending" value="可控" copy="任务启动前先看预算和预估，再确认执行。" />
        <StatCard label="Storage" value="本机" copy="任务材料、结果、日志和备份默认保存在本地。" />
        <StatCard label="App Defaults" value={apps.length} copy={activeApp ? "可在应用详情里调整默认应用和输出偏好。" : "可在应用详情里调整默认值。"} />
      </section>

      <div className="settings-center-grid">
        <Surface>
          <div className="record-head">
            <div>
              <p className="section-kicker">AI Service</p>
              <h3 className="section-title">连接 AI 服务</h3>
              <p className="section-copy">没有连接时仍可创建草稿；启动执行前需要完成连接检查。</p>
            </div>
            <StatusBadge value={providerStatus?.status ?? "unavailable"} />
          </div>
          <div className="field-actions">
            <Link className="action-button" href="/release">查看连接状态</Link>
            <Link className="ghost-button" href="/tasks">先创建草稿</Link>
          </div>
        </Surface>

        <Surface>
          <p className="section-kicker">Spending</p>
          <h3 className="section-title">预算与时间</h3>
          <p className="section-copy">任务模板会带入默认预算。高成本任务应先创建草稿，确认目标、材料和输出标准后再启动。</p>
          <div className="pill-row">
            <span className="inline-chip">草稿优先</span>
            <span className="inline-chip">启动前确认</span>
            <span className="inline-chip">可按应用调整</span>
          </div>
        </Surface>

        <Surface>
          <p className="section-kicker">Storage</p>
          <h3 className="section-title">本地数据位置</h3>
          <p className="section-copy">本地运行状态、任务产物、备份和诊断记录默认保存在本机。删除本地数据属于危险操作，需要先预览影响。</p>
          <div className="field-actions">
            <Link className="action-button" href="/data-governance">备份与删除</Link>
            <Link className="ghost-button" href="/release">查看产品边界</Link>
          </div>
        </Surface>

        <Surface>
          <p className="section-kicker">App Defaults</p>
          <h3 className="section-title">应用默认值</h3>
          <p className="section-copy">默认应用、输出风格和材料位置按应用保存。普通入口只显示会影响任务启动的设置。</p>
          <div className="record-list">
            {(defaultApps.length > 0 ? defaultApps : apps.slice(0, 4)).map((item) => (
              <article className="compact-record" key={item.application.appId}>
                <div className="record-head">
                  <div>
                    <h4 className="record-title">{item.application.displayName}</h4>
                    <p className="meta-copy">{USER_APP_SUMMARIES[item.application.appId] ?? item.application.description ?? "应用详情里可以调整默认值。"}</p>
                  </div>
                  <Link className="ghost-button" href={`/applications/${encodeURIComponent(item.application.appId)}`}>设置</Link>
                </div>
              </article>
            ))}
          </div>
        </Surface>

        <Surface>
          <p className="section-kicker">Data & Privacy</p>
          <h3 className="section-title">数据与外发风险</h3>
          <p className="section-copy">启用真实 AI 服务时，任务目标、材料摘要和必要上下文会发送给所选服务。本地产品不会自动上传到官方远端服务。</p>
          <div className="pill-row">
            <span className="inline-chip">本地优先</span>
            <span className="inline-chip">外发需连接 AI 服务</span>
            <span className="inline-chip">危险操作需确认</span>
          </div>
        </Surface>

        <Surface>
          <p className="section-kicker">Advanced</p>
          <h3 className="section-title">维护者入口</h3>
          <p className="section-copy">运行分析、提示词、评测、观测和桥接工具仍保留，但不再占用普通用户主路径。</p>
          <div className="field-actions">
            <Link className="ghost-button" href="/prompting">Prompt</Link>
            <Link className="ghost-button" href="/mcp">MCP</Link>
            <Link className="ghost-button" href="/observability">观测</Link>
            <Link className="ghost-button" href="/evaluations">评测</Link>
          </div>
        </Surface>
      </div>
    </div>
  );
}
