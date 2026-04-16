import type { Metadata } from "next";
import type { ReactNode } from "react";

import { SidebarNav } from "./components/sidebar-nav";

import "./globals.css";

export const metadata: Metadata = {
  title: "Project Yggdrasil Workbench",
  description: "任务、记忆、协作、评测与观测一体化工作台。",
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body>
        <div className="app-shell">
          <aside className="shell-side">
            <div className="sidebar-brand">
              <p className="sidebar-kicker">Project Yggdrasil</p>
              <h1>World Engine Workbench</h1>
              <p className="sidebar-copy">
                把任务、记忆、协作、评测、观测与 LLM 网关统一收口到正式控制台。
              </p>
            </div>
            <SidebarNav />
          </aside>
          <div className="shell-main">
            <header className="shell-topbar">
              <div>
                <p className="topbar-kicker">Control Plane</p>
                <p className="topbar-copy">Web 现在直接消费 core-api，而不是从仓库本地文件拼装页面。</p>
              </div>
              <div className="topbar-chip-group">
                <span className="topbar-chip">Tasks</span>
                <span className="topbar-chip">Memory</span>
                <span className="topbar-chip">Collaboration</span>
                <span className="topbar-chip">Evaluation</span>
                <span className="topbar-chip">Observability</span>
                <span className="topbar-chip">LLM</span>
              </div>
            </header>
            <div className="page-stack">{children}</div>
          </div>
        </div>
      </body>
    </html>
  );
}