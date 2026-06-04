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
                <p className="topbar-kicker">控制台</p>
                <p className="topbar-copy">Web 现在直接消费 core-api，而不是从仓库本地文件拼装页面。</p>
              </div>
              <div className="topbar-chip-group">
                <span className="topbar-chip">任务</span>
                <span className="topbar-chip">记忆</span>
                <span className="topbar-chip">协作</span>
                <span className="topbar-chip">评测</span>
                <span className="topbar-chip">观测</span>
                <span className="topbar-chip">LLM</span>
                <span className="topbar-chip">发布</span>
              </div>
            </header>
            <div className="page-stack">{children}</div>
          </div>
        </div>
      </body>
    </html>
  );
}
