import type { Metadata } from "next";
import type { ReactNode } from "react";

import { SidebarNav } from "./components/sidebar-nav";

import "./globals.css";

export const metadata: Metadata = {
  title: "Project Yggdrasil",
  description: "从材料到任务产物的本地 AI 工作台。",
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body>
        <div className="app-shell">
          <aside className="shell-side">
            <div className="sidebar-brand">
              <p className="sidebar-kicker">Local Agent System</p>
              <h1>Project<br />Yggdrasil</h1>
              <p className="sidebar-copy">
                在本机整理材料、选择应用、确认任务，并保留数据边界。
              </p>
            </div>
            <SidebarNav />
          </aside>
          <div className="shell-main">
            <header className="shell-topbar">
              <div>
                <p className="topbar-kicker">本地工作台</p>
                <p className="topbar-copy">先确认材料、AI 服务和预算，再启动任务。</p>
              </div>
              <div className="topbar-chip-group">
                <span className="topbar-chip">材料</span>
                <span className="topbar-chip">应用</span>
                <span className="topbar-chip">审批</span>
                <span className="topbar-chip">本地数据</span>
              </div>
            </header>
            <div className="page-stack">{children}</div>
          </div>
        </div>
      </body>
    </html>
  );
}
