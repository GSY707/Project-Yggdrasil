from __future__ import annotations

import re
from pathlib import Path

from .contracts import SpecDocumentSummary
from .support import new_id, relative_workspace_path, resolve_workspace_root


TITLE_PATTERN = re.compile(r"^#\s+(.+)$", re.MULTILINE)
STATUS_PATTERN = re.compile(r"^- (?:文档状态|状态)：(.+)$", re.MULTILINE)
VERSION_PATTERN = re.compile(r"^- 版本：(.+)$", re.MULTILINE)
UPDATED_PATTERN = re.compile(r"^- (?:日期|更新时间)：(.+)$", re.MULTILINE)


def default_docs_root(workspace_root: Path | None = None) -> Path:
    return resolve_workspace_root(workspace_root) / "docs"


def _infer_category(path: str) -> str:
    if path.startswith("docs/specs/"):
        return "Data Spec"
    if path.startswith("docs/protocols/"):
        return "Protocol"
    if path.startswith("docs/adr/"):
        return "ADR"
    return "Product"


def list_spec_documents(workspace_root: Path | None = None) -> list[SpecDocumentSummary]:
    root = resolve_workspace_root(workspace_root)
    docs_root = default_docs_root(root)
    documents: list[SpecDocumentSummary] = []

    for document_path in sorted(docs_root.rglob("*.md")):
        relative_path = relative_workspace_path(document_path, root)
        text = document_path.read_text(encoding="utf-8")
        title = TITLE_PATTERN.search(text)
        status = STATUS_PATTERN.search(text)
        version = VERSION_PATTERN.search(text)
        updated = UPDATED_PATTERN.search(text)
        documents.append(
            SpecDocumentSummary(
                id=new_id("doc", relative_path, stable=True),
                name=title.group(1).strip() if title else document_path.stem,
                category=_infer_category(relative_path),
                path=relative_path,
                status=status.group(1).strip() if status else None,
                version=version.group(1).strip() if version else None,
                updatedAt=updated.group(1).strip() if updated else None,
            )
        )

    return documents