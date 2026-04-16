import { getWorkspaceDashboard } from "../lib/workspace-dashboard";

function renderStateTone(lifecycleState: string): string {
  if (lifecycleState === "active") {
    return "good";
  }
  if (lifecycleState === "disabled") {
    return "muted";
  }
  return "warn";
}

export default async function HomePage() {
  const dashboard = await getWorkspaceDashboard();

  return (
    <main className="page-shell">
      <section className="hero">
        <div className="hero-copy">
          <p className="eyebrow">Project Yggdrasil</p>
          <h1>Runtime Workbench</h1>
          <p className="lede">
            当前首页直接读取仓库里的模块 manifest、规格文档和 todo 执行面板，展示的是可联调的
            当前状态，而不是骨架说明页。
          </p>
        </div>

        <aside className="hero-panel">
          <p className="panel-kicker">Current Track</p>
          <h2>M1 Execution</h2>
          <ul className="compact-list">
            {dashboard.todo.phaseNotes.map((note) => (
              <li key={note}>{note}</li>
            ))}
          </ul>
        </aside>
      </section>

      <section className="metrics-grid">
        <article className="metric-card">
          <p className="metric-label">Module Surface</p>
          <p className="metric-value">{dashboard.modules.length}</p>
          <p className="metric-note">Enabled by default profile and rendered from live manifest data.</p>
        </article>
        <article className="metric-card">
          <p className="metric-label">Spec Surface</p>
          <p className="metric-value">{dashboard.specs.length}</p>
          <p className="metric-note">Markdown documents discovered from product, protocol, ADR, and data-spec directories.</p>
        </article>
        <article className="metric-card accent-card">
          <p className="metric-label">Code Inventory</p>
          <p className="metric-stack">
            <span>{dashboard.todo.formalCount} formal</span>
            <span>{dashboard.todo.temporaryCount} temporary</span>
            <span>{dashboard.todo.stubCount} 占位</span>
          </p>
          <p className="metric-note">Counts are parsed from the execution todo so the dashboard follows the same source of truth.</p>
        </article>
      </section>

      <section className="dashboard-grid">
        <div className="panel">
          <div className="section-head">
            <h2>Immediate Priorities</h2>
            <p>The next actions are pulled from the execution todo document.</p>
          </div>
          <ol className="priority-list">
            {dashboard.todo.priorities.slice(0, 5).map((priority) => (
              <li key={priority}>{priority}</li>
            ))}
          </ol>
        </div>

        <div className="panel">
          <div className="section-head">
            <h2>Spec Index</h2>
            <p>Document metadata is discovered by scanning the docs tree and reading the header blocks.</p>
          </div>
          <div className="doc-list">
            {dashboard.specs.slice(0, 8).map((spec) => (
              <article className="doc-row" key={spec.path}>
                <div>
                  <h3>{spec.title}</h3>
                  <p>{spec.path}</p>
                </div>
                <div className="doc-meta">
                  <span>{spec.category}</span>
                  <span>{spec.status}</span>
                  <span>{spec.version}</span>
                </div>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="grid-section">
        <div className="section-head">
          <h2>Module Registry</h2>
          <p>These cards combine manifest metadata with the local module catalog snapshot.</p>
        </div>
        <div className="module-grid">
          {dashboard.modules.map((module) => (
            <article className="module-card" key={module.id}>
              <div className="module-card-head">
                <div>
                  <p className="module-category">{module.category}</p>
                  <h3>{module.displayName}</h3>
                </div>
                <span className={`state-pill ${renderStateTone(module.lifecycleState)}`}>
                  {module.lifecycleState}
                </span>
              </div>
              <p className="module-description">{module.description}</p>
              <div className="meta-pairs">
                <span>version {module.version}</span>
                <span>{module.runtimeMode}</span>
                <span>{module.desiredState}</span>
              </div>
              <div className="chip-row">
                {module.hooks.map((hook) => (
                  <span className="chip" key={hook}>
                    {hook}
                  </span>
                ))}
              </div>
              <p className="module-footnote">
                publishes {module.publishes.length} events, subscribes {module.subscribes.length}, requests {module.permissions.length} permissions.
              </p>
            </article>
          ))}
        </div>
      </section>

      <section className="grid-section">
        <div className="section-head">
          <h2>Service Surface</h2>
          <p>Service cards describe the current executable inspection endpoints and responsibilities.</p>
        </div>
        <div className="card-grid">
          {dashboard.services.map((service) => (
            <article className="card service-card" key={service.title}>
              <p className="service-endpoint">{service.endpoint}</p>
              <h3>{service.title}</h3>
              <p>{service.description}</p>
              <p className="service-role">{service.responsibility}</p>
            </article>
          ))}
        </div>
      </section>
    </main>
  );
}