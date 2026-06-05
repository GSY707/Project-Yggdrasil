"use client";

import Image from "next/image";
import Link from "next/link";

import { PageHeader, StatCard, StatusBadge, Surface } from "./workbench-primitives";

const releaseModes = [
  {
    mode: "开发者工作区",
    status: "available",
    install: "uv sync + corepack pnpm install",
    launch: "多终端启动，或只启动需要调试的服务",
    update: "git pull 后重新执行 uv sync / pnpm install / alembic upgrade head",
    data: "默认 .yggdrasil，本地数据库可用 SQLite 或 compose PostgreSQL",
    backup: "corepack pnpm ops:backup / corepack pnpm ops:restore",
    boundary: "面向贡献者和调试；需要读开发文档，稳定性以 CI 与本地定向测试为准。",
  },
  {
    mode: "本地产品模式",
    status: "available",
    install: "uv sync + corepack pnpm install + 至少一个 provider key",
    launch: "corepack pnpm yggdrasil:up",
    update: "停止本地服务，拉取更新后重新安装依赖并执行 yggdrasil:up",
    data: ".yggdrasil、.yggdrasil/product-logs、.yggdrasil-backups",
    backup: "正式支持本地运行时备份与恢复",
    boundary: "当前推荐给试用用户；不提供 uptime 承诺，问题按自托管本地环境处理。",
  },
  {
    mode: "完整 Docker Compose 产品栈",
    status: "preview",
    install: "infra/product.env.template + corepack pnpm product:up",
    launch: "corepack pnpm product:up，然后访问 http://localhost:3000",
    update: "停止产品栈，更新镜像 tag 或源码后重新 product:up；迁移由 migrate job 执行",
    data: "postgres-data、yggdrasil-state、yggdrasil-backups、minio-data 四类 volume 分离",
    backup: "corepack pnpm product:backup / corepack pnpm product:restore",
    boundary: "已提供预览 compose、镜像构建和 smoke；正式发布前仍需冷启动、备份恢复和升级回滚验收。",
  },
  {
    mode: "桌面封装",
    status: "preview",
    install: "packaging/desktop/windows/*.cmd",
    launch: "双击 Yggdrasil Desktop.cmd，或运行 Yggdrasil.Desktop.ps1 start",
    update: "自动更新和安装/卸载器尚未发布",
    data: "复用产品 compose volume；不引入远端同步",
    backup: "Yggdrasil.Desktop.ps1 backup / restore",
    boundary: "这是 Windows 薄启动器预览，不是正式安装包或托盘应用。",
  },
  {
    mode: "托管 / SaaS",
    status: "planned",
    install: "尚未发布；已加入产品计划",
    launch: "未来需要官方托管入口、账号体系和工作区选择",
    update: "由官方托管环境负责，版本、维护窗口和回滚策略待定义",
    data: "计划支持官方远端工作区；租户、加密、地域和保留策略待冻结",
    backup: "计划支持官方远端备份、恢复和删除请求闭环",
    boundary: "已加入计划，但当前仍不能作为可用托管服务或 uptime 承诺。",
  },
  {
    mode: "官方远端数据服务",
    status: "planned",
    install: "随托管 / SaaS 或显式远端同步配置发布",
    launch: "尚未发布账号、远端工作区、备份库或删除请求入口",
    update: "远端存储协议、备份调度和删除审计策略待定义",
    data: "计划覆盖远端数据托管、远端备份、远端删除；当前本地模式不会自动上传",
    backup: "计划支持远端快照、恢复演练、删除证明和保留期策略",
    boundary: "当前只进入需求计划；未上线前仍以本地备份/恢复为唯一正式路径。",
  },
];

const demoSteps = [
  {
    title: "导入素材",
    detail: "在资产页选择文本文件或粘贴资料，确认切段预览、摘要节点和附加任务入口。",
    href: "/assets",
  },
  {
    title: "选择高价值应用",
    detail: "第一次演示优先选 Deep Research、Graduate Researcher、Coding Greenfield 或 Knowledge Studio。",
    href: "/applications",
  },
  {
    title: "用模板创建任务",
    detail: "任务页展示示例任务和预期产物；可先创建草稿，也可创建后立即启动。",
    href: "/tasks",
  },
  {
    title: "观察结果",
    detail: "进入任务详情页查看运行状态、模型调用、Prompt 产物、可恢复快照和 LLM 工作分析。",
    href: "/tasks",
  },
];

const storageItems = [
  {
    title: "密钥",
    detail: "真实 provider key 只应放在 .env 或用户级环境变量；工作台不展示 key 明文，也不应把 key 写入仓库。",
  },
  {
    title: "数据库",
    detail: "默认开发配置使用 YGGDRASIL_DATABASE_URL=sqlite+pysqlite:///./.yggdrasil/local-dev.db；也可切换到 compose PostgreSQL。",
  },
  {
    title: "状态根",
    detail: "YGGDRASIL_STATE_ROOT 默认是 .yggdrasil；运行时状态、LLM 工件、观测 JSONL 与分析结果都在其下分区保存。",
  },
  {
    title: "产品日志",
    detail: "一键启动器会把 core-api、agent-runtime、module-host、worker 和 web 日志写入 .yggdrasil/product-logs。",
  },
  {
    title: "备份快照",
    detail: "corepack pnpm ops:backup 会创建 .yggdrasil-backups/<timestamp>，包含数据库快照、状态根和 metadata.json。",
  },
  {
    title: "观测与 trace",
    detail: "本地 JSONL 默认保存在 .yggdrasil/state/observability；若 Langfuse 或 OTel 指向远端，观测数据会离开本机。",
  },
];

const outboundItems = [
  "启用真实 LLM provider 时，任务目标、导入素材摘要、检索上下文、Prompt 和模型响应会发送给对应 provider。",
  "Langfuse 或 OpenTelemetry endpoint 指向远端时，trace、generation metadata、错误摘要和部分运行属性会写入远端观测系统。",
  "uv、pnpm、Docker、Git 等安装和更新命令会访问各自的软件源或代码托管服务。",
  "托管 / SaaS 和官方远端数据服务已加入计划；当前本地产品模式仍不会自动把数据上传到 Project Yggdrasil 官方服务。",
];

const actionItems = [
  {
    title: "导出 / 备份",
    status: "available",
    command: "corepack pnpm ops:backup",
    detail: "当前正式支持的用户级导出动作。恢复最近快照使用 corepack pnpm ops:restore。",
  },
  {
    title: "恢复",
    status: "available",
    command: "uv run python -m yggdrasil_sdk.ops_cli backup restore --snapshot ./.yggdrasil-backups/<timestamp>",
    detail: "用于恢复指定快照；PostgreSQL 模式依赖本机 pg_dump / psql。",
  },
  {
    title: "删除本地状态",
    status: "preview",
    command: "打开 /data-governance，先按 task / asset / node 生成删除影响预览。",
    detail: "当前 Web 只暴露 dry-run；task 硬删除需要后端 confirmScopeId，asset/node 仍是策略冻结前的预览。",
  },
  {
    title: "密钥轮换",
    status: "available",
    command: "更新 .env 或用户级环境变量，然后重启本地产品。",
    detail: "仓库不会托管真实 key；如 key 误入仓库，应立即撤销 provider 侧凭据。",
  },
];

const screenshots = [
  {
    src: "/demo/yggdrasil-p2-assets.png",
    title: "素材导入入口",
    detail: "浏览器文本文件导入、切段预览、摘要节点和附加任务入口。",
  },
  {
    src: "/demo/yggdrasil-p2-tasks.png",
    title: "任务模板入口",
    detail: "应用模板、示例任务、预期产物和已附加素材进入同一创建面板。",
  },
];

function MatrixCard({ item }: { item: (typeof releaseModes)[number] }) {
  return (
    <article className="record-card">
      <div className="record-head">
        <div>
          <h3 className="record-title">{item.mode}</h3>
          <p className="meta-copy">{item.boundary}</p>
        </div>
        <StatusBadge value={item.status} />
      </div>
      <div className="kv-grid">
        <div className="kv-item">
          <p className="meta-label">安装</p>
          <p className="meta-copy mono">{item.install}</p>
        </div>
        <div className="kv-item">
          <p className="meta-label">启动</p>
          <p className="meta-copy mono">{item.launch}</p>
        </div>
        <div className="kv-item">
          <p className="meta-label">更新</p>
          <p className="meta-copy">{item.update}</p>
        </div>
        <div className="kv-item">
          <p className="meta-label">数据位置</p>
          <p className="meta-copy">{item.data}</p>
        </div>
        <div className="kv-item">
          <p className="meta-label">备份 / 恢复</p>
          <p className="meta-copy">{item.backup}</p>
        </div>
      </div>
    </article>
  );
}

export function ReleasePage() {
  return (
    <div>
      <PageHeader
        eyebrow="发布与安全"
        title="本地产品边界"
        summary={
          <>
            这里说明当前真正支持的运行模式、演示路径、本地数据位置、出机边界和恢复动作。外部用户可以先按本地产品模式试用，开发者再进入内部控制面。
          </>
        }
        actions={
          <>
            <Link className="action-button" href="/tasks">
              新建任务
            </Link>
            <Link className="ghost-button" href="/assets">
              导入素材
            </Link>
            <Link className="ghost-button" href="/observability">
              查看观测
            </Link>
            <Link className="ghost-button" href="/data-governance">
              数据治理
            </Link>
          </>
        }
      />

      <section className="stat-grid">
        <StatCard label="推荐模式" value="本地产品" copy="当前外部试用优先使用 corepack pnpm yggdrasil:up。" />
        <StatCard label="数据默认位置" value=".yggdrasil" copy="状态根、运行工件、观测 JSONL 与产品日志都在本机。" />
        <StatCard label="备份命令" value="ops:backup" copy="当前正式导出路径是本地运行时快照。" />
        <StatCard label="托管服务" value="计划中" copy="官方远端托管、备份和删除已进入计划；当前不提供 uptime 承诺。" />
      </section>

      <Surface>
        <p className="section-kicker">发布模式</p>
        <h2 className="section-title">发布模式矩阵</h2>
        <p className="section-copy">只把已经真实存在的入口标成可用；尚未发布的模式明确标为计划中，不能当作当前服务承诺。</p>
        <div className="release-matrix">
          {releaseModes.map((item) => (
            <MatrixCard item={item} key={item.mode} />
          ))}
        </div>
      </Surface>

      <div className="content-grid">
        <Surface>
          <p className="section-kicker">演示</p>
          <h2 className="section-title">公开演示路径</h2>
          <p className="section-copy">演示只走用户会真实点击的 Web 路径，不使用内部评测 suite 代替首次体验。</p>
          <div className="record-list">
            {demoSteps.map((step, index) => (
              <article className="compact-record" key={step.title}>
                <div className="record-head">
                  <div>
                    <p className="meta-label">步骤 {index + 1}</p>
                    <h3 className="record-title">{step.title}</h3>
                    <p className="meta-copy">{step.detail}</p>
                  </div>
                  <Link className="ghost-button" href={step.href}>
                    打开
                  </Link>
                </div>
              </article>
            ))}
          </div>
        </Surface>

        <Surface>
          <p className="section-kicker">截图</p>
          <h2 className="section-title">产品截图</h2>
          <p className="section-copy">这些截图用于 README 和用户文档，证明首次成功路径已经有可展示的产品入口。</p>
          <div className="screenshot-list">
            {screenshots.map((shot) => (
              <article className="screenshot-card" key={shot.src}>
                <Image alt={shot.title} className="screenshot-image" height={360} src={shot.src} width={640} />
                <h3 className="record-title">{shot.title}</h3>
                <p className="meta-copy">{shot.detail}</p>
              </article>
            ))}
          </div>
        </Surface>
      </div>

      <Surface>
        <p className="section-kicker">数据边界</p>
        <h2 className="section-title">本地数据与密钥位置</h2>
        <div className="content-grid tight">
          {storageItems.map((item) => (
            <article className="kv-item" key={item.title}>
              <h3 className="record-title">{item.title}</h3>
              <p className="meta-copy">{item.detail}</p>
            </article>
          ))}
        </div>
      </Surface>

      <div className="content-grid">
        <Surface>
          <p className="section-kicker">出机边界</p>
          <h2 className="section-title">哪些内容会离开本机</h2>
          <ul className="mini-list">
            {outboundItems.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </Surface>

        <Surface>
          <p className="section-kicker">可用动作</p>
          <h2 className="section-title">导出、恢复与删除状态</h2>
          <div className="record-list">
            {actionItems.map((item) => (
              <article className="compact-record" key={item.title}>
                <div className="record-head">
                  <h3 className="record-title">{item.title}</h3>
                  <StatusBadge value={item.status} />
                </div>
                <p className="meta-copy mono">{item.command}</p>
                <p className="meta-copy">{item.detail}</p>
              </article>
            ))}
          </div>
        </Surface>
      </div>
    </div>
  );
}
