from ._common import *  # noqa: F403,F401
from .bootstrap import *  # noqa: F403,F401


def _line_count(path: Path) -> int:
    return len(path.read_text(encoding="utf-8").splitlines())


def _split_group_status(
    root: Path,
    *,
    group_id: str,
    base_path: str,
    expected_files: list[str],
    max_lines: int,
) -> dict[str, Any]:
    group_root = root / base_path
    if not group_root.is_dir():
        raise RuntimeError(f"{group_id} split directory is missing: {base_path}")

    missing = [name for name in expected_files if not (group_root / name).exists()]
    if missing:
        raise RuntimeError(f"{group_id} split directory is missing expected files: {', '.join(missing)}")

    line_counts = {path.name: _line_count(path) for path in sorted(group_root.glob("*.py"))}
    oversized = {name: count for name, count in line_counts.items() if count > max_lines}
    if oversized:
        detail = ", ".join(f"{name}={count}" for name, count in sorted(oversized.items()))
        raise RuntimeError(f"{group_id} split files exceed {max_lines} lines: {detail}")

    return {
        "groupId": group_id,
        "path": base_path,
        "fileCount": len(line_counts),
        "maxLineCount": max(line_counts.values()) if line_counts else 0,
        "lineCounts": line_counts,
    }


def _run_g2_complex_file_split_regression_case(case: dict[str, Any] | None = None) -> dict[str, Any]:
    case_payload = dict(case or {})
    workspace_root = Path(os.environ.get("YGGDRASIL_GIT_REPO_PATH") or resolve_workspace_root()).resolve()
    max_lines = int(case_payload.get("maxLinesPerSplitFile") or 600)
    legacy_paths = [
        "packages/python-sdk/src/yggdrasil_sdk/persistence/repositories.py",
        "services/core-api/src/yggdrasil_core_api/services.py",
    ]
    resurrected = [path for path in legacy_paths if (workspace_root / path).exists()]
    if resurrected:
        raise RuntimeError(f"legacy monolith file(s) were resurrected: {', '.join(resurrected)}")

    groups = [
        _split_group_status(
            workspace_root,
            group_id="persistence.repositories",
            base_path="packages/python-sdk/src/yggdrasil_sdk/persistence/repositories",
            expected_files=[
                "__init__.py",
                "task.py",
                "memory.py",
                "evaluation.py",
                "asset.py",
                "prompting.py",
                "collaboration.py",
                "platform.py",
                "platform_core.py",
            ],
            max_lines=max_lines,
        ),
        _split_group_status(
            workspace_root,
            group_id="core-api.services",
            base_path="services/core-api/src/yggdrasil_core_api/services",
            expected_files=[
                "__init__.py",
                "_base.py",
                "task_service.py",
                "memory_service.py",
                "evaluation_service.py",
                "asset_service.py",
                "prompting_service.py",
                "collaboration_service.py",
                "runtime_service.py",
            ],
            max_lines=max_lines,
        ),
    ]

    route_dir = workspace_root / "services/core-api/src/yggdrasil_core_api/api/routes"
    direct_repository_imports = []
    for route_file in sorted(route_dir.glob("*.py")):
        text = route_file.read_text(encoding="utf-8")
        if "persistence.repositories" in text:
            direct_repository_imports.append(route_file.name)
    if direct_repository_imports:
        raise RuntimeError(
            "route layer imports repositories directly after service split: "
            + ", ".join(direct_repository_imports)
        )

    docs_to_check = {
        "docs/ANTI_TECH_DEBT.md": ["TD-01 · repositories.py 拆分", "当前状态：已进入固定回归", "TD-02 · services.py 拆分"],
        "todo.md": ["复杂文件拆分", "固定回归"],
    }
    missing_doc_terms: dict[str, list[str]] = {}
    for relative_path, terms in docs_to_check.items():
        text = (workspace_root / relative_path).read_text(encoding="utf-8")
        missing_terms = [term for term in terms if term not in text]
        if missing_terms:
            missing_doc_terms[relative_path] = missing_terms
    if missing_doc_terms:
        raise RuntimeError(f"complex split regression documentation is incomplete: {missing_doc_terms}")

    max_line_count = max(group["maxLineCount"] for group in groups)
    return {
        "workspaceRoot": str(workspace_root),
        "legacyMonolithsAbsent": True,
        "routeLayerUsesServices": True,
        "groups": groups,
        "maxLineCount": max_line_count,
        "liveScenario": {
            "complexFileSplitRegression": "passed",
            "groupCount": len(groups),
            "maxLineCount": max_line_count,
        },
    }


__all__ = [name for name in globals() if not name.startswith("__")]
