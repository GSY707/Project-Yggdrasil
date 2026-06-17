"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const PRIMARY_NAV_ITEMS = [
  { href: "/", kicker: "start", label: "开始", description: "添加材料，选择应用，确认第一任务。" },
  { href: "/tasks", kicker: "tasks", label: "任务", description: "查看草稿、运行中任务和结果状态。" },
  { href: "/applications", kicker: "apps", label: "应用", description: "比较四类应用入口和可用模板。" },
  { href: "/settings", kicker: "settings", label: "设置", description: "连接 AI 服务、预算、本地数据和隐私。" },
];

const SUPPORT_NAV_ITEMS = [
  { href: "/assets", kicker: "materials", label: "材料", description: "导入资料并附加到任务。" },
  { href: "/data-governance", kicker: "privacy", label: "数据与备份", description: "预览删除影响，创建本地备份。" },
  { href: "/release", kicker: "help", label: "帮助与诊断", description: "查看产品状态、诊断和维护入口。" },
];

const ADVANCED_NAV_ITEMS = [
  { href: "/nodes", label: "记忆节点" },
  { href: "/collaboration", label: "协作" },
  { href: "/training", label: "训练" },
  { href: "/mcp", label: "MCP" },
  { href: "/prompting", label: "Prompt" },
  { href: "/evaluations", label: "评测" },
  { href: "/observability", label: "观测" },
];

function isActivePath(pathname: string, href: string) {
  return href === "/" ? pathname === "/" : pathname.startsWith(href);
}

export function SidebarNav() {
  const pathname = usePathname();

  return (
    <nav className="sidebar-nav" aria-label="Product Navigation">
      <div className="nav-group">
        {PRIMARY_NAV_ITEMS.map((item) => (
          <Link key={item.href} className={`nav-link${isActivePath(pathname, item.href) ? " active" : ""}`} href={item.href}>
            <span className="nav-kicker">{item.kicker}</span>
            <span className="nav-label">{item.label}</span>
            <span className="nav-description">{item.description}</span>
          </Link>
        ))}
      </div>

      <div className="nav-group support">
        <p className="nav-group-title">支持</p>
        {SUPPORT_NAV_ITEMS.map((item) => (
          <Link key={item.href} className={`nav-link compact${isActivePath(pathname, item.href) ? " active" : ""}`} href={item.href}>
            <span className="nav-kicker">{item.kicker}</span>
            <span className="nav-label">{item.label}</span>
            <span className="nav-description">{item.description}</span>
          </Link>
        ))}
      </div>

      <details className="advanced-nav">
        <summary>维护者入口</summary>
        <div className="advanced-nav-grid">
          {ADVANCED_NAV_ITEMS.map((item) => (
            <Link key={item.href} className={isActivePath(pathname, item.href) ? "active" : ""} href={item.href}>
              {item.label}
            </Link>
          ))}
        </div>
      </details>
    </nav>
  );
}
