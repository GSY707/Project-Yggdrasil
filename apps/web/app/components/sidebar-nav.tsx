"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV_ITEMS = [
  { href: "/", kicker: "overview", label: "总览", description: "任务、模块、PR、评测与运行脉冲。" },
  { href: "/tasks", kicker: "tasks", label: "任务", description: "查看执行状态、运行记录、快照与路由决策。" },
  { href: "/nodes", kicker: "memory", label: "节点", description: "浏览节点内容、版本历史、来源标注与关系边。" },
  { href: "/collaboration", kicker: "branches", label: "协作", description: "查看分支、PR 审核与合并流。" },
  { href: "/evaluations", kicker: "regression", label: "评测", description: "运行 M4-M6 回归 suite 并查看结果。" },
  { href: "/observability", kicker: "signals", label: "观测", description: "汇总 HTTP、worker、evaluation 与 LLM 的 span、日志和指标。" },
];

export function SidebarNav() {
  const pathname = usePathname();

  return (
    <nav className="sidebar-nav" aria-label="Workbench Navigation">
      {NAV_ITEMS.map((item) => {
        const isActive = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
        return (
          <Link key={item.href} className={`nav-link${isActive ? " active" : ""}`} href={item.href}>
            <span className="nav-kicker">{item.kicker}</span>
            <span className="nav-label">{item.label}</span>
            <span className="nav-description">{item.description}</span>
          </Link>
        );
      })}
    </nav>
  );
}