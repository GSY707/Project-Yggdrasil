from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..support import ensure_state_subdir, new_id, utc_now
from .base import SimpleMCPServer, structured_tool_result


def _reports_file_path() -> Path:
    return ensure_state_subdir("project-issue-reports") / "reports.jsonl"


def _append_report(payload: dict[str, Any]) -> None:
    path = _reports_file_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _report_project_issue(arguments: dict[str, Any]) -> dict[str, Any]:
    title = str(arguments.get("title") or "").strip()
    if not title:
        raise ValueError("title is required")

    report = {
        "reportId": new_id("issue"),
        "reportedAt": utc_now().isoformat(),
        "severity": str(arguments.get("severity") or "warning").strip().lower(),
        "category": str(arguments.get("category") or "runtime").strip(),
        "component": str(arguments.get("component") or "agent-runtime").strip(),
        "title": title,
        "description": str(arguments.get("description") or "").strip(),
        "suspectedCause": str(arguments.get("suspectedCause") or "").strip(),
        "expectedBehavior": str(arguments.get("expectedBehavior") or "").strip(),
        "actualBehavior": str(arguments.get("actualBehavior") or "").strip(),
        "artifacts": arguments.get("artifacts") if isinstance(arguments.get("artifacts"), list) else [],
        "metadata": arguments.get("metadata") if isinstance(arguments.get("metadata"), dict) else {},
    }

    _append_report(report)
    return structured_tool_result(
        {
            "status": "ok",
            "saved": True,
            "report": report,
            "storagePath": str(_reports_file_path()),
        },
        text=f"Project issue report saved: {report['reportId']}",
    )


def main() -> None:
    server = SimpleMCPServer("workspace-report-mcp", "0.1.0")
    server.register_tool(
        name="report_project_issue",
        description="Report project/runtime/tooling issues for follow-up diagnosis.",
        input_schema={
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "severity": {"type": "string", "enum": ["info", "warning", "error", "critical"]},
                "category": {"type": "string"},
                "component": {"type": "string"},
                "description": {"type": "string"},
                "suspectedCause": {"type": "string"},
                "expectedBehavior": {"type": "string"},
                "actualBehavior": {"type": "string"},
                "artifacts": {"type": "array", "items": {"type": "string"}},
                "metadata": {"type": "object", "additionalProperties": True},
            },
            "required": ["title"],
            "additionalProperties": False,
        },
        handler=_report_project_issue,
    )
    server.serve_stdio()


if __name__ == "__main__":
    main()
