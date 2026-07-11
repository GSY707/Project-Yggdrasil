"use client";

import type { PropsWithChildren } from "react";
import { usePathname } from "next/navigation";
import Link from "next/link";

import { LanguageSwitcher } from "./language-switcher";
import { SidebarNav } from "./sidebar-nav";
import { useTranslation } from "./locale-provider";
import { localizedText } from "../i18n";

const diagnosticsNavigation = [
  { href: "/", icon: "rocket_launch", zh: "开始", en: "Start" },
  { href: "/tasks", icon: "assignment_turned_in", zh: "任务", en: "Tasks" },
  { href: "/applications", icon: "apps", zh: "应用", en: "Applications" },
  { href: "/assets", icon: "folder_open", zh: "材料", en: "Materials" },
  { href: "/data-governance", icon: "shield_person", zh: "数据与隐私", en: "Data & Privacy" },
  { href: "/settings", icon: "settings", zh: "设置", en: "Settings" },
];

function DiagnosticsShell({ children }: PropsWithChildren) {
  const pathname = usePathname();
  const { locale } = useTranslation();

  return (
    <div className="diagnostics-shell">
      <aside className="diagnostics-side">
        <div className="diagnostics-brand">
          <div className="diagnostics-brand-mark"><span className="material-symbols-outlined">park</span></div>
          <div>
            <h1>Yggdrasil</h1>
            <p>{localizedText(locale, "本地智能体系统", "AI Agent OS")}</p>
          </div>
        </div>
        <Link className="diagnostics-cta" href="/tasks">
          <span className="material-symbols-outlined">add</span>
          {localizedText(locale, "新建智能体", "New Agent")}
        </Link>
        <nav className="diagnostics-nav" aria-label={localizedText(locale, "产品导航", "Product navigation")}>
          {diagnosticsNavigation.map((item) => {
            // The Stitch Help & Diagnostics source keeps Settings selected as the
            // contextual intent even though the help surface is rendered here.
            const active = pathname === "/release"
              ? item.href === "/settings"
              : item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
            return (
              <Link className={`diagnostics-nav-link${active ? " active" : ""}`} href={item.href} key={item.href}>
                <span className="material-symbols-outlined">{item.icon}</span>
                <span>{localizedText(locale, item.zh, item.en)}</span>
              </Link>
            );
          })}
        </nav>
        <div className="diagnostics-footer">
          <Link className="diagnostics-nav-link" href="/release">
            <span className="material-symbols-outlined">menu_book</span>
            <span>{localizedText(locale, "文档", "Docs")}</span>
          </Link>
          <Link className="diagnostics-nav-link" href="/release">
            <span className="material-symbols-outlined">support_agent</span>
            <span>{localizedText(locale, "支持", "Support")}</span>
          </Link>
          <LanguageSwitcher />
        </div>
      </aside>
      <div className="diagnostics-main">
        <header className="diagnostics-topbar">
          <div className="diagnostics-search-wrap">
            <span className="material-symbols-outlined">search</span>
            <input aria-label={localizedText(locale, "搜索命令和智能体", "Search commands and agents")} placeholder={localizedText(locale, "搜索命令和智能体…", "Search commands, agents...")} />
            <span className="diagnostics-shortcut">⌘ K</span>
          </div>
          <div className="diagnostics-top-actions">
            <button aria-label={localizedText(locale, "通知", "Notifications")} type="button"><span className="material-symbols-outlined">notifications</span><i /></button>
            <button aria-label={localizedText(locale, "历史", "History")} type="button"><span className="material-symbols-outlined">history</span></button>
            <div className="diagnostics-avatar" aria-label={localizedText(locale, "系统管理员", "System Admin")}>SA</div>
          </div>
        </header>
        <main className="diagnostics-content">{children}</main>
      </div>
    </div>
  );
}

export function AppShell({ children }: PropsWithChildren) {
  const pathname = usePathname();
  const { t } = useTranslation();

  if (pathname === "/release") {
    return <DiagnosticsShell>{children}</DiagnosticsShell>;
  }

  return (
    <div className="app-shell">
      <aside className="shell-side">
        <div className="sidebar-brand">
          <p className="sidebar-kicker">{t("layout.brandKicker")}</p>
          <h1>Project<br />Yggdrasil</h1>
          <p className="sidebar-copy">{t("layout.brandCopy")}</p>
        </div>
        <SidebarNav />
        <div style={{ marginTop: "auto", padding: "0 8px" }}>
          <LanguageSwitcher />
        </div>
      </aside>
      <div className="shell-main">
        <header className="shell-topbar">
          <div>
            <p className="topbar-kicker">{t("layout.topbarKicker")}</p>
            <p className="topbar-copy">{t("layout.topbarCopy")}</p>
          </div>
          <div className="topbar-chip-group">
            <span className="topbar-chip">{t("layout.chip.materials")}</span>
            <span className="topbar-chip">{t("layout.chip.applications")}</span>
            <span className="topbar-chip">{t("layout.chip.approval")}</span>
            <span className="topbar-chip">{t("layout.chip.localData")}</span>
          </div>
        </header>
        <div className="page-stack">{children}</div>
      </div>
    </div>
  );
}
