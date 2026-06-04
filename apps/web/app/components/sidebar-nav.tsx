"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV_ITEMS = [
  { href: "/", kicker: "overview", label: "总览", description: "首次启动检查、任务入口和系统状态。" },
  { href: "/tasks", kicker: "tasks", label: "任务", description: "从应用模板创建任务，并查看运行状态。" },
  { href: "/nodes", kicker: "memory", label: "节点", description: "浏览节点内容、版本历史、来源标注与关系边。" },
  { href: "/collaboration", kicker: "branches", label: "协作", description: "查看分支、PR 审核与合并流。" },
  { href: "/assets", kicker: "assets", label: "资产", description: "导入素材、预览切段并附加到新任务。" },
  { href: "/training", kicker: "training", label: "训练", description: "管理数据集版本、模型制品和验证门。" },
  { href: "/applications", kicker: "apps", label: "应用", description: "选择应用、查看模板并管理重要配置。" },
  { href: "/mcp", kicker: "bridge", label: "MCP", description: "管理 MCP bridge、项目工作区和桥接工具。" },
  { href: "/prompting", kicker: "prompts", label: "Prompt", description: "调试 Prompt 资产、工具清单和编译结果。" },
  { href: "/evaluations", kicker: "regression", label: "评测", description: "运行 M4-M6 回归 suite 并查看结果。" },
  { href: "/observability", kicker: "signals", label: "观测", description: "汇总 HTTP、worker、evaluation 与 LLM 的 span、日志和指标。" },
  { href: "/release", kicker: "release", label: "发布与安全", description: "查看发布模式、演示路径、本地数据和隐私边界。" },
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
