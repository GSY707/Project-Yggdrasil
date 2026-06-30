from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

from yggdrasil_sdk.contracts import (
    TaskTakeoverAmbiguity,
    TaskTakeoverConstraint,
    TaskTakeoverDeliverySection,
    TaskTakeoverMetrics,
    TaskTakeoverPlanStep,
    TaskTakeoverProtocol,
    TaskTakeoverVerificationItem,
)
from yggdrasil_sdk.hooks import HookNames
from yggdrasil_sdk.module import BaseModulePlugin, HookRegistration
from yggdrasil_sdk.support import new_id, normalize_excerpt


_SECTION_MARKERS: dict[str, tuple[str, ...]] = {
    "result": (
        "result", "results", "结论", "结果", "final result", "outcome",
        "summary", "总结", "answer", "answer summary", "conclusion",
    ),
    "evidence": (
        "evidence", "verification", "验证", "证据", "tests", "test",
        "proof", "validation", "supporting evidence", "验证结果",
        "test results", "测试结果",
    ),
    "pending": (
        "pending", "待确认", "open questions", "follow-up", "follow up",
        "待处理", "open items", "risks", "风险", "assumptions", "假设",
    ),
    "incomplete": (
        "incomplete", "未完成", "remaining", "remaining work",
        "limitations", "residual risks", "todo", "待办",
        "known issues", "已知问题", "gaps", "缺口",
    ),
}

_SECTION_WEIGHTS: dict[str, float] = {
    "result": 0.55,
    "evidence": 0.45,
}

_WEB_GROUNDED_REQUIREMENT_MARKERS = (
    "web search",
    "web-grounded",
    "web grounded",
    "source url",
    "source urls",
    "citation",
    "citations",
    "网络检索",
    "网络搜索",
    "来源",
    "网址",
    "链接",
)

_WEB_GROUNDED_FAILURE_MARKERS = (
    "无法进行实时网络搜索",
    "无法执行网络搜索",
    "unable to perform real-time web search",
    "cannot perform real-time web search",
    "based on training knowledge",
    "基于训练知识",
    "未能验证最新来源",
)

_WEB_CITATION_PATTERN = re.compile(r"https?://[^\s)\]>\"']+", re.IGNORECASE)



def _text(value: Any) -> str:
    return str(value or "").strip()


def _objective_from(payload: dict[str, object]) -> str:
    request = payload.get("request") if isinstance(payload.get("request"), dict) else {}
    root_mount = payload.get("rootMount") if isinstance(payload.get("rootMount"), dict) else {}
    task = payload.get("task") if isinstance(payload.get("task"), dict) else {}
    return (
        _text(request.get("taskObjective"))
        or _text(request.get("currentObjective"))
        or _text(task.get("currentObjective"))
        or _text(root_mount.get("taskObjective"))
        or _text(task.get("goal"))
        or "Continue the current task with controlled autonomy."
    )


def _task_type(payload: dict[str, object]) -> str:
    return _text(payload.get("taskType") or "generic").lower() or "generic"


def _run_type(payload: dict[str, object]) -> str:
    return _text(payload.get("runType") or "main").lower() or "main"


def _build_constraint(category: str, label: str, value: str, *, source: str | None = None, required: bool = True) -> dict[str, object]:
    return TaskTakeoverConstraint(
        id=new_id("takeover-constraint", category, label, value, stable=True),
        category=category,
        label=label,
        value=value,
        required=required,
        source=source,
    ).model_dump(by_alias=True, mode="json")


def _stable_exploration_variant(entropy_source: str) -> tuple[str, str, list[str]]:
    variants: list[tuple[str, str, list[str]]] = [
        (
            "探索样本池（文献优先）",
            "先做小样本外部探索：快速扫描近期来源与经典基线，提取候选研究问题与术语边界，禁止直接进入正式规划。",
            ["candidate questions", "term boundary", "source shortlist"],
        ),
        (
            "探索冲突面（争议优先）",
            "先做矛盾探索：主动寻找相互冲突的观点或实验结论，记录冲突点与待裁决证据，再进入正式规划。",
            ["conflict map", "open disputes", "evidence gaps"],
        ),
        (
            "探索验证面（实验优先）",
            "先做可验证性探索：确定可快速复现的微实验与度量口径，形成验证入口后再进入正式规划。",
            ["micro experiment candidates", "metrics frame", "repro constraints"],
        ),
    ]
    digest = hashlib.sha256(entropy_source.encode("utf-8")).hexdigest()
    idx = int(digest[:8], 16) % len(variants)
    return variants[idx]


def _plan_blueprint(task_type: str, *, entropy_source: str = "") -> list[tuple[str, str, str, list[str]]]:
    if task_type == "coding":
        return [
            ("objective", "固定目标", "明确验收目标、当前焦点和不可越过的边界。", ["normalized objective", "acceptance target"]),
            ("plan", "定位实现面", "识别受影响的代码面、依赖面和验证入口。", ["affected files", "validation target"]),
            ("execute", "实施改动", "完成代码、配置或文档的正式变更，不留临时分支逻辑。", ["code change", "config change"]),
            ("verify", "验证行为", "运行聚焦验证，确认行为、类型或回归没有被破坏。", ["tests", "typecheck", "runtime proof"]),
            ("deliver", "交付结果", "按任务需要输出结果、证据和必要风险，不填空洞模板。", ["result", "evidence"]),
        ]
    if task_type == "research":
        explore_title, explore_instructions, explore_evidence = _stable_exploration_variant(entropy_source or "research")
        return [
            ("objective", explore_title, explore_instructions, explore_evidence),
            ("objective", "固定研究问题", "明确问题边界、交付口径和已知未知项。", ["question scope", "decision target"]),
            ("constraints", "抽取约束", "固定来源、时间窗、证据标准和风险边界。", ["source policy", "time window"]),
            ("plan", "收集与归纳", "组织检索、筛选、比较与综合步骤。", ["source list", "comparison frame"]),
            ("verify", "校验证据", "区分已证实结论与仍需验证的假设。", ["verified claim", "open assumption"]),
            ("deliver", "交付结论", "输出结论、证据和必要风险，不填空洞模板。", ["result", "evidence"]),
        ]
    return [
        ("objective", "固定目标", "明确当前任务目标和交付边界。", ["normalized objective"]),
        ("constraints", "抽取约束", "抽取预算、环境、工具和交付约束。", ["constraints"]),
        ("plan", "形成计划", "生成可执行且可验证的步骤。", ["plan steps"]),
        ("verify", "验证输出", "确认输出具备证据和边界说明。", ["verification proof"]),
        ("deliver", "交付结果", "输出任务需要的结果、验证和必要风险。", ["result", "evidence"]),
    ]


def _compute_plan_quality(plan_steps: list[dict[str, object]], constraints: list[dict[str, object]], ambiguities: list[dict[str, object]]) -> float:
    phase_count = len({str(step.get("phase") or "") for step in plan_steps if step.get("phase")})
    base = 52.0 + min(phase_count * 8.0, 30.0) + min(len(constraints) * 3.5, 28.0)
    penalty = min(len([item for item in ambiguities if item.get("required")]) * 8.0, 24.0)
    return round(max(0.0, min(100.0, base - penalty)), 2)


def _match_section(label: str) -> str | None:
    """Match a markdown heading to a delivery section name."""
    normalized = label.strip().strip("#").strip().strip(":：").lower()
    # 精确匹配
    for section, markers in _SECTION_MARKERS.items():
        if normalized in markers:
            return section
    # 前缀匹配 — 处理 "结果与说明" 类标题
    for section, markers in _SECTION_MARKERS.items():
        if any(normalized.startswith(marker) for marker in markers):
            return section
    return None


_EVIDENCE_INFER_MARKERS = {"验证", "测试", "test", "pass", "通过", "assert", "确认"}
_PENDING_INFER_MARKERS = {"待确认", "open", "follow", "risk", "风险", "assume", "假设"}
_INCOMPLETE_INFER_MARKERS = {"todo", "未完成", "remaining", "待办", "known issue", "已知问题", "gap", "缺口"}


def _infer_missing_sections(buckets: dict[str, list[str]]) -> None:
    """从 result 桶中推断缺失的 evidence/incomplete/pending 内容。"""
    for target_section, markers in (
        ("evidence", _EVIDENCE_INFER_MARKERS),
        ("pending", _PENDING_INFER_MARKERS),
        ("incomplete", _INCOMPLETE_INFER_MARKERS),
    ):
        if buckets[target_section]:
            continue
        promoted: list[str] = []
        remaining: list[str] = []
        for line in buckets["result"]:
            lower = line.lower()
            if any(m in lower for m in markers):
                promoted.append(line)
            else:
                remaining.append(line)
        if promoted:
            buckets[target_section] = promoted
            buckets["result"] = remaining


def _parse_delivery_sections(model_output: str) -> list[dict[str, object]]:
    text = model_output.strip()
    if not text:
        return [
            TaskTakeoverDeliverySection(id=new_id("takeover-section", section, stable=True), section=section, content="", status="missing").model_dump(by_alias=True, mode="json")
            for section in ("result", "evidence", "pending", "incomplete")
        ]

    lines = text.splitlines()
    buckets: dict[str, list[str]] = {section: [] for section in ("result", "evidence", "pending", "incomplete")}
    current_section: str | None = None

    for line in lines:
        section = _match_section(line)
        if section is not None:
            current_section = section
            continue
        if current_section is None:
            buckets["result"].append(line)
            continue
        buckets[current_section].append(line)

    payload: list[dict[str, object]] = []
    # 尝试从 result 桶推断缺失的 sections
    _infer_missing_sections(buckets)
    for section in ("result", "evidence", "pending", "incomplete"):
        content = "\n".join(item for item in buckets[section] if item.strip()).strip()
        payload.append(
            TaskTakeoverDeliverySection(
                id=new_id("takeover-section", section, stable=True),
                section=section,
                content=content,
                status="present" if content else "missing",
            ).model_dump(by_alias=True, mode="json")
        )
    return payload


def _verification_items(delivery_sections: list[dict[str, object]]) -> list[dict[str, object]]:
    sections_by_name = {str(item.get("section")): item for item in delivery_sections}
    required = {
        "result": ("建议给出明确结果总结。", "advisory"),
        "evidence": ("建议给出支撑结果的证据或验证。", "advisory"),
    }
    items: list[dict[str, object]] = []
    for section, (detail, gate_mode) in required.items():
        item = sections_by_name.get(section) or {}
        status = "passed" if item.get("status") == "present" else "failed"
        items.append(
            TaskTakeoverVerificationItem(
                id=new_id("takeover-verify", section, stable=True),
                label=f"delivery.{section}",
                status=status,
                detail=detail,
                gateMode=gate_mode,
            ).model_dump(by_alias=True, mode="json")
        )
    return items


def _verification_pass_rate(items: list[dict[str, object]]) -> float:
    if not items:
        return 0.0
    passed = len([item for item in items if item.get("status") == "passed"])
    return round(passed / len(items), 4)


def _delivery_completeness(delivery_sections: list[dict[str, object]]) -> float:
    """加权计算 delivery 完整度分数。"""
    if not delivery_sections:
        return 0.0
    total_weight = 0.0
    for item in delivery_sections:
        section = str(item.get("section") or "")
        if item.get("status") == "present" and section in _SECTION_WEIGHTS:
            total_weight += _SECTION_WEIGHTS[section]
    return round(total_weight * 100.0, 2)


def _rework_metrics(plan_steps: list[dict[str, object]], verification_items: list[dict[str, object]]) -> tuple[int, float]:
    if not plan_steps:
        return 0, 0.0
    warnings = len(
        [
            item
            for item in verification_items
            if item.get("gateMode") == "hard" and item.get("status") in {"warning", "failed"}
        ]
    )
    return warnings, round(warnings / len(plan_steps), 4)


def _requires_web_grounded_evidence(payload: dict[str, object]) -> bool:
    request = payload.get("request") if isinstance(payload.get("request"), dict) else {}
    root_mount = payload.get("rootMount") if isinstance(payload.get("rootMount"), dict) else {}
    startup_contract = root_mount.get("startupContract") if isinstance(root_mount.get("startupContract"), dict) else {}
    text = "\n".join(
        [
            _text(request.get("responseRequirements")),
            _text(startup_contract.get("responseRequirements")),
            _text(request.get("currentObjective")),
            _text(request.get("taskObjective")),
        ]
    ).lower()
    return any(marker in text for marker in _WEB_GROUNDED_REQUIREMENT_MARKERS)


def _tool_execution_success_count(tool_executions: list[object]) -> int:
    success_count = 0
    for item in tool_executions:
        if not isinstance(item, dict):
            continue
        status = _text(item.get("status")).lower()
        error = item.get("error")
        result = item.get("result") if isinstance(item.get("result"), dict) else {}
        is_error = bool(result.get("isError"))
        if status in {"failed", "error", "blocked", "timeout"}:
            continue
        if error is not None or is_error:
            continue
        success_count += 1
    return success_count


def _has_web_grounded_failure_disclaimer(delivery_sections: list[dict[str, object]]) -> bool:
    joined = "\n".join(
        _text(item.get("content"))
        for item in delivery_sections
        if isinstance(item, dict)
    ).lower()
    return any(marker in joined for marker in _WEB_GROUNDED_FAILURE_MARKERS)


def _has_web_citation_evidence(delivery_sections: list[dict[str, object]]) -> bool:
    joined = "\n".join(
        _text(item.get("content"))
        for item in delivery_sections
        if isinstance(item, dict)
    )
    return bool(_WEB_CITATION_PATTERN.search(joined))


def _is_continuation_window(payload: dict[str, object]) -> bool:
    request = payload.get("request") if isinstance(payload.get("request"), dict) else {}
    # Some runtimes lift continuation hints to the top-level payload instead of request.
    candidates: list[dict[str, Any]] = [request, payload]
    for item in candidates:
        if not isinstance(item, dict):
            continue
        if item.get("resumeToken") or item.get("parentRunId") or item.get("currentNodeId"):
            return True
        if isinstance(item.get("workContextStack"), dict):
            return True
        try:
            if int(item.get("windowIndex") or 1) > 1:
                return True
        except (TypeError, ValueError):
            continue
    return False


_TERMINAL_WORK_NODE_STATUSES = {"completed", "failed", "skipped", "cancelled", "canceled"}
_SEEDED_PLACEHOLDER_TITLES = {
    "固定研究问题",
    "抽取约束",
    "收集与归纳",
    "校验证据",
    "交付结论",
    "固定目标",
    "定位实现面",
    "实施改动",
    "验证行为",
    "交付结果",
    "抽取约束",
    "形成计划",
    "验证输出",
}


def _work_tree_from_tool_arguments(arguments: dict[str, Any]) -> dict[str, Any]:
    context = arguments.get("executionContext") if isinstance(arguments.get("executionContext"), dict) else {}
    root_mount = context.get("rootMount") if isinstance(context.get("rootMount"), dict) else {}
    protocol = root_mount.get("takeoverProtocol") if isinstance(root_mount.get("takeoverProtocol"), dict) else {}
    work_tree = protocol.get("workTree") if isinstance(protocol.get("workTree"), dict) else {}
    override = arguments.get("workTree") if isinstance(arguments.get("workTree"), dict) else {}
    return override or work_tree


def _node_id(node: dict[str, Any]) -> str:
    return str(node.get("id") or node.get("nodeId") or "").strip()


def _parent_node_id(node: dict[str, Any]) -> str:
    return str(node.get("parentNodeId") or node.get("parentId") or "").strip()


def _node_status(node: dict[str, Any]) -> str:
    return str(node.get("status") or "unknown").strip().lower()


def _node_title(node: dict[str, Any]) -> str:
    return str(node.get("title") or node.get("localGoal") or node.get("nodeText") or _node_id(node)).strip()


def _unfinished_work_nodes(work_tree: dict[str, Any]) -> dict[str, Any]:
    nodes = [node for node in work_tree.get("nodes") or [] if isinstance(node, dict)]
    root_node_id = str(work_tree.get("rootNodeId") or "").strip()
    current_node_id = str(work_tree.get("currentNodeId") or "").strip()
    by_id = {_node_id(node): node for node in nodes if _node_id(node)}
    children_by_parent: dict[str, list[str]] = {}
    for node in nodes:
        parent_id = _parent_node_id(node)
        if parent_id:
            children_by_parent.setdefault(parent_id, []).append(_node_id(node))

    unfinished: list[dict[str, Any]] = []
    suggested_batch_prune: list[str] = []
    for node in nodes:
        node_id = _node_id(node)
        status = _node_status(node)
        if not node_id or status in _TERMINAL_WORK_NODE_STATUSES:
            continue
        parent_id = _parent_node_id(node)
        child_ids = [item for item in children_by_parent.get(node_id, []) if item]
        unfinished_child_ids = [
            child_id
            for child_id in child_ids
            if _node_status(by_id.get(child_id, {})) not in _TERMINAL_WORK_NODE_STATUSES
        ]
        title = _node_title(node)
        is_root = node_id == root_node_id
        seeded_placeholder_likely = (
            not is_root
            and parent_id == root_node_id
            and not child_ids
            and title in _SEEDED_PLACEHOLDER_TITLES
        )
        reason: str
        if is_root:
            reason = "root is still not completed; inspect unfinished children before final completion"
        elif unfinished_child_ids:
            reason = "node has unfinished descendants and cannot be pruned until they are resolved"
        elif seeded_placeholder_likely:
            reason = "root-level seeded planning placeholder with no descendants; if covered by completed real work, batch prune/skip it"
            suggested_batch_prune.append(node_id)
        else:
            reason = "non-terminal work node; complete it, enter it, or skip/prune it if obsolete"
        unfinished.append(
            {
                "nodeId": node_id,
                "title": title,
                "status": status,
                "parentNodeId": parent_id or None,
                "isRoot": is_root,
                "isCurrent": node_id == current_node_id,
                "childNodeIds": child_ids,
                "unfinishedChildNodeIds": unfinished_child_ids,
                "seededPlaceholderLikely": seeded_placeholder_likely,
                "suggestedAction": "complete-root-after-children-terminal" if is_root else ("batch-prune-if-covered" if seeded_placeholder_likely else "resolve-node"),
                "reason": reason,
            }
        )

    return {
        "rootNodeId": root_node_id or None,
        "currentNodeId": current_node_id or None,
        "unfinishedCount": len(unfinished),
        "unfinishedNodes": unfinished,
        "suggestedBatchPruneNodeIds": suggested_batch_prune,
        "suggestedBatchPruneDirective": (
            f'<work-node-prune nodeIds="{",".join(suggested_batch_prune)}">seeded planning placeholders covered by completed real work</work-node-prune>'
            if suggested_batch_prune
            else None
        ),
        "completionHint": (
            "After all non-root unfinished nodes are completed/skipped/pruned, the parent/root must emit <work-node-complete status=\"completed\">...</work-node-complete>."
            if unfinished
            else "All work nodes are terminal; root completion may proceed if delivery evidence is accepted."
        ),
    }


def list_unfinished_work_nodes_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    work_tree = _work_tree_from_tool_arguments(arguments)
    result = _unfinished_work_nodes(work_tree)
    return {
        "status": "ok",
        **result,
    }


class TaskTakeoverModule(BaseModulePlugin):
    module_id = "task-takeover"

    def manifest_path(self) -> Path:
        return Path(__file__).resolve().parents[2] / "yggdrasil.module.yaml"

    def register_hooks(self) -> tuple[HookRegistration, ...]:
        return (
            HookRegistration(name=HookNames.MODULE_ENABLE_PREFLIGHT, handler=self.enable_preflight),
            HookRegistration(name=HookNames.MODULE_HEALTH_REPORT, handler=self.report_health),
            HookRegistration(name=HookNames.TASK_TAKEOVER_PARSE_OBJECTIVE, handler=self.parse_objective),
            HookRegistration(name=HookNames.TASK_TAKEOVER_EXTRACT_CONSTRAINTS, handler=self.extract_constraints),
            HookRegistration(name=HookNames.TASK_TAKEOVER_GENERATE_PLAN, handler=self.generate_plan),
            HookRegistration(name=HookNames.TASK_TAKEOVER_VERIFY_DELIVERY, handler=self.verify_delivery),
            HookRegistration(name=HookNames.TASK_TAKEOVER_FORMAT_OUTPUT, handler=self.format_output),
            HookRegistration(name=HookNames.AGENT_TOOLS_REGISTER, handler=self.register_tools_hook),
        )

    def register_tools(self) -> tuple[dict[str, object], ...]:
        return (
            {
                "name": "task_takeover.list_unfinished_work_nodes",
                "displayName": "List unfinished work-tree nodes",
                "description": "List all non-terminal work-tree nodes from the current task state and suggest batch prune candidates for seeded planning placeholders.",
                "permissionRequired": ["runtime.read"],
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "workTree": {
                            "type": "object",
                            "description": "Optional workTree snapshot override. Omit to inspect the current runtime takeoverProtocol workTree.",
                            "additionalProperties": True,
                        }
                    },
                    "additionalProperties": False,
                },
                "implementationRef": "yggdrasil_task_takeover.plugin:list_unfinished_work_nodes_tool",
                "executionMode": "sync",
                "timeoutMs": 5000,
            },
        )

    def register_tools_hook(self, payload: dict[str, object]) -> dict[str, object]:
        return {"tools": list(self.register_tools()), "toolCount": len(self.register_tools())}

    def enable_preflight(self, payload: dict[str, object]) -> dict[str, object]:
        return {"status": "ok", "summary": "Task Takeover preflight passed."}

    def report_health(self, payload: dict[str, object]) -> dict[str, object]:
        return {"status": "healthy", "summary": "Task Takeover is ready to formalize controlled autonomy runs."}

    def parse_objective(self, payload: dict[str, object]) -> dict[str, object]:
        objective = _objective_from(payload)
        ambiguities: list[dict[str, object]] = []
        if len(objective) < 12:
            ambiguities.append(
                TaskTakeoverAmbiguity(
                    id=new_id("takeover-ambiguity", objective or "empty", stable=True),
                    prompt="当前目标过短，可能需要补充验收标准。",
                    reason="objective-too-short",
                    required=False,
                ).model_dump(by_alias=True, mode="json")
            )
        return {
            "objective": objective,
            "objectiveSummary": normalize_excerpt(objective, 160),
            "ambiguities": ambiguities,
        }

    def extract_constraints(self, payload: dict[str, object]) -> dict[str, object]:
        request = payload.get("request") if isinstance(payload.get("request"), dict) else {}
        root_mount = payload.get("rootMount") if isinstance(payload.get("rootMount"), dict) else {}
        budget = root_mount.get("budgetState") if isinstance(root_mount.get("budgetState"), dict) else {}
        startup_contract = root_mount.get("startupContract") if isinstance(root_mount.get("startupContract"), dict) else {}
        root_branches = root_mount.get("rootBranches") if isinstance(root_mount.get("rootBranches"), dict) else {}
        constraints: list[dict[str, object]] = [
            _build_constraint("delivery", "交付证据", "按任务需要说明结果、证据和必要风险。", source="gate-2", required=False),
            _build_constraint("tooling", "可见能力", ", ".join([str(item) for item in root_mount.get("activeCapabilities") or []]) or "none", source="root-mount", required=False),
        ]
        if root_branches:
            constraints.append(
                _build_constraint(
                    "environment",
                    "根挂载",
                    ", ".join(f"{key}={value}" for key, value in root_branches.items() if value),
                    source="root-mount",
                    required=True,
                )
            )
        if budget.get("tokenBudgetTotal") is not None:
            constraints.append(
                _build_constraint(
                    "budget",
                    "Token 预算",
                    f"{int(budget['tokenBudgetTotal'])} total / {int(budget.get('tokenBudgetUsed') or 0)} used",
                    source="budget-state",
                    required=True,
                )
            )
        if budget.get("costBudgetTotal") is not None:
            constraints.append(
                _build_constraint(
                    "budget",
                    "Cost 预算",
                    f"{float(budget['costBudgetTotal']):.4f} total / {float(budget.get('costBudgetUsed') or 0.0):.4f} used",
                    source="budget-state",
                    required=True,
                )
            )
        if request.get("readonlyContextRef") is not None:
            constraints.append(
                _build_constraint("scope", "只读切片", "当前运行只能依赖已挂载只读上下文。", source="request", required=True)
            )
        if startup_contract.get("responseRequirements"):
            constraints.append(
                _build_constraint(
                    "delivery",
                    "启动合同",
                    str(startup_contract["responseRequirements"]),
                    source="startup-contract",
                    required=True,
                )
            )
        if startup_contract.get("restartMessage"):
            constraints.append(
                _build_constraint(
                    "runtime",
                    "重启交接",
                    str(startup_contract["restartMessage"]),
                    source="startup-contract",
                    required=True,
                )
            )
        if request.get("resumeMessage") or root_mount.get("resumeMessage"):
            constraints.append(
                _build_constraint("runtime", "恢复链路", "当前任务带有 resume 语义，必须保持连续性。", source="resume", required=True)
            )
        return {"constraints": constraints}

    def generate_plan(self, payload: dict[str, object]) -> dict[str, object]:
        objective_result = payload.get("objectiveResult") if isinstance(payload.get("objectiveResult"), dict) else {}
        constraints_result = payload.get("constraintsResult") if isinstance(payload.get("constraintsResult"), dict) else {}
        task_type = _task_type(payload)
        entropy_source = "|".join(
            [
                _text(payload.get("taskId")),
                _text(objective_result.get("objective")),
                _text((payload.get("request") or {}).get("currentFocus") if isinstance(payload.get("request"), dict) else ""),
            ]
        )
        plan_steps: list[dict[str, object]] = []
        previous_step_id: str | None = None
        for index, (phase, title, instructions, expected_evidence) in enumerate(
            _plan_blueprint(task_type, entropy_source=entropy_source),
            start=1,
        ):
            step_id = new_id("takeover-step", task_type, phase, index, stable=True)
            plan_steps.append(
                TaskTakeoverPlanStep(
                    id=step_id,
                    title=title,
                    instructions=instructions,
                    phase=phase,
                    expectedEvidence=expected_evidence,
                    dependsOn=[previous_step_id] if previous_step_id else [],
                ).model_dump(by_alias=True, mode="json")
            )
            previous_step_id = step_id
        ambiguities = objective_result.get("ambiguities") if isinstance(objective_result.get("ambiguities"), list) else []
        constraints = constraints_result.get("constraints") if isinstance(constraints_result.get("constraints"), list) else []
        return {
            "plan": plan_steps,
            "metrics": TaskTakeoverMetrics(
                planQualityScore0_100=_compute_plan_quality(plan_steps, constraints, ambiguities),
                reworkCount=0,
                reworkRate=0.0,
                clarificationNeeded=bool([item for item in ambiguities if item.get("required")]),
                deliveryCompletenessScore0_100=0.0,
                verificationPassRate=0.0,
            ).model_dump(by_alias=True, mode="json"),
        }

    def format_output(self, payload: dict[str, object]) -> dict[str, object]:
        model_output = _text(payload.get("modelOutput"))
        delivery_sections = _parse_delivery_sections(model_output)
        return {
            "deliverySections": delivery_sections,
            "structuredSummary": normalize_excerpt(model_output, 180),
        }

    def verify_delivery(self, payload: dict[str, object]) -> dict[str, object]:
        formatted = self.format_output(payload)
        delivery_sections = formatted["deliverySections"]
        verification_items = _verification_items(delivery_sections)
        tool_executions = payload.get("toolExecutions") if isinstance(payload.get("toolExecutions"), list) else []
        if _requires_web_grounded_evidence(payload):
            success_count = _tool_execution_success_count(tool_executions)
            has_disclaimer = _has_web_grounded_failure_disclaimer(delivery_sections)
            has_citation_evidence = _has_web_citation_evidence(delivery_sections)
            continuation_window = _is_continuation_window(payload)
            web_gate_passed = (success_count > 0 or has_citation_evidence or continuation_window) and not has_disclaimer
            verification_items.append(
                TaskTakeoverVerificationItem(
                    id=new_id("takeover-verify", "web-grounded-evidence", stable=True),
                    label="delivery.web-grounded-evidence",
                    status="passed" if web_gate_passed else "failed",
                    detail=(
                        "合同要求 web-grounded/source URL 证据时，必须满足以下之一：至少一次成功工具执行、交付内容包含可验证 URL 引用、或处于 continuation 窗口并继承前序证据；且不得声明无法实时网络检索。"
                    ),
                    gateMode="hard",
                ).model_dump(by_alias=True, mode="json")
            )
        plan_steps = payload.get("plan") if isinstance(payload.get("plan"), list) else []
        rework_count, rework_rate = _rework_metrics(plan_steps, verification_items)
        return {
            "deliverySections": delivery_sections,
            "verificationItems": verification_items,
            "metrics": TaskTakeoverMetrics(
                planQualityScore0_100=float(payload.get("planQualityScore0_100") or 0.0),
                reworkCount=rework_count,
                reworkRate=rework_rate,
                clarificationNeeded=False,
                deliveryCompletenessScore0_100=_delivery_completeness(delivery_sections),
                verificationPassRate=_verification_pass_rate(verification_items),
            ).model_dump(by_alias=True, mode="json"),
        }

    def build_protocol(self, payload: dict[str, object]) -> dict[str, object]:
        objective_result = self.parse_objective(payload)
        constraints_result = self.extract_constraints(payload)
        plan_result = self.generate_plan({**payload, "objectiveResult": objective_result, "constraintsResult": constraints_result})
        protocol = TaskTakeoverProtocol(
            id=new_id("takeover", payload.get("taskId") or "unknown", _run_type(payload), stable=True),
            taskId=_text(payload.get("taskId") or "unknown"),
            taskType=_task_type(payload),
            runType=_run_type(payload),
            currentPhase="plan",
            status="needs-clarification" if any(item.get("required") for item in objective_result.get("ambiguities") or []) else "prepared",
            objective=_text(objective_result.get("objective")),
            objectiveSummary=_text(objective_result.get("objectiveSummary")),
            ambiguities=[TaskTakeoverAmbiguity.model_validate(item) for item in objective_result.get("ambiguities") or []],
            constraints=[TaskTakeoverConstraint.model_validate(item) for item in constraints_result.get("constraints") or []],
            plan=[TaskTakeoverPlanStep.model_validate(item) for item in plan_result.get("plan") or []],
            deliverySections=[],
            verificationItems=[],
            metrics=TaskTakeoverMetrics.model_validate(plan_result.get("metrics") or {}),
            appliedModules=[self.module_id],
            hookTrace=[],
        )
        return protocol.model_dump(by_alias=True, mode="json")


plugin = TaskTakeoverModule()
