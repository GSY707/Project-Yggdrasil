"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { useTranslation } from "./locale-provider";

function isActivePath(pathname: string, href: string) {
  return href === "/" ? pathname === "/" : pathname.startsWith(href);
}

export function SidebarNav() {
  const pathname = usePathname();
  const { t } = useTranslation();
  const primaryNavItems = [
    { href: "/", kicker: t("nav.start.kicker"), label: t("nav.start.label"), description: t("nav.start.description") },
    { href: "/tasks", kicker: t("nav.tasks.kicker"), label: t("nav.tasks.label"), description: t("nav.tasks.description") },
    { href: "/applications", kicker: t("nav.applications.kicker"), label: t("nav.applications.label"), description: t("nav.applications.description") },
    { href: "/settings", kicker: t("nav.settings.kicker"), label: t("nav.settings.label"), description: t("nav.settings.description") },
  ];
  const supportNavItems = [
    { href: "/assets", kicker: t("nav.materials.kicker"), label: t("nav.materials.label"), description: t("nav.materials.description") },
    { href: "/data-governance", kicker: t("nav.privacy.kicker"), label: t("nav.privacy.label"), description: t("nav.privacy.description") },
    { href: "/release", kicker: t("nav.help.kicker"), label: t("nav.help.label"), description: t("nav.help.description") },
  ];
  const advancedNavItems = [
    { href: "/nodes", label: t("nav.nodes") },
    { href: "/collaboration", label: t("nav.collaboration") },
    { href: "/training", label: t("nav.training") },
    { href: "/mcp", label: t("nav.mcp") },
    { href: "/prompting", label: t("nav.prompting") },
    { href: "/evaluations", label: t("nav.evaluations") },
    { href: "/observability", label: t("nav.observability") },
  ];

  return (
    <nav className="sidebar-nav" aria-label={t("nav.aria")}>
      <div className="nav-group">
        {primaryNavItems.map((item) => (
          <Link key={item.href} className={`nav-link${isActivePath(pathname, item.href) ? " active" : ""}`} href={item.href}>
            <span className="nav-kicker">{item.kicker}</span>
            <span className="nav-label">{item.label}</span>
            <span className="nav-description">{item.description}</span>
          </Link>
        ))}
      </div>

      <div className="nav-group support">
        <p className="nav-group-title">{t("nav.support")}</p>
        {supportNavItems.map((item) => (
          <Link key={item.href} className={`nav-link compact${isActivePath(pathname, item.href) ? " active" : ""}`} href={item.href}>
            <span className="nav-kicker">{item.kicker}</span>
            <span className="nav-label">{item.label}</span>
            <span className="nav-description">{item.description}</span>
          </Link>
        ))}
      </div>

      <details className="advanced-nav">
        <summary>{t("nav.advanced")}</summary>
        <div className="advanced-nav-grid">
          {advancedNavItems.map((item) => (
            <Link key={item.href} className={isActivePath(pathname, item.href) ? "active" : ""} href={item.href}>
              {item.label}
            </Link>
          ))}
        </div>
      </details>
    </nav>
  );
}
