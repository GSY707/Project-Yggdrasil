from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _normalize_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if not isinstance(item, dict):
                continue
            for key in ("text", "input_text", "output_text", "content"):
                value = item.get(key)
                if isinstance(value, str) and value.strip():
                    parts.append(value)
                    break
        return "\n".join(parts)
    return ""


def _serialize_messages(messages: Any) -> list[dict[str, str]]:
    if not isinstance(messages, list):
        return []
    result: list[dict[str, str]] = []
    for item in messages:
        if not isinstance(item, dict):
            continue
        result.append(
            {
                "role": str(item.get("role") or "unknown"),
                "content": _normalize_content(item.get("content")),
            }
        )
    return result


def _upsert_record(record_path: Path, task_id: str, entry: dict[str, Any]) -> dict[str, Any]:
    now = entry.get("endedAt") or ""
    payload = _load_json(record_path) or {
        "taskId": task_id,
        "createdAt": now,
        "updatedAt": now,
        "invocations": [],
    }
    invocations = [
        item
        for item in (payload.get("invocations") or [])
        if isinstance(item, dict) and str(item.get("invocationId") or "") != str(entry.get("invocationId") or "")
    ]
    invocations.append(dict(entry))
    invocations.sort(
        key=lambda item: (
            int(item.get("windowIndex") or 0),
            str(item.get("endedAt") or ""),
            str(item.get("invocationId") or ""),
        )
    )
    payload["taskId"] = task_id
    payload["updatedAt"] = now
    payload["invocationCount"] = len(invocations)
    payload["invocations"] = invocations
    if invocations:
        latest = invocations[-1]
        payload["latestInvocationId"] = latest.get("invocationId")
        payload["latestWindowIndex"] = latest.get("windowIndex")
        payload["latestStatus"] = latest.get("status")
    record_path.parent.mkdir(parents=True, exist_ok=True)
    record_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def rebuild(workspace_root: Path) -> None:
    state_requests = workspace_root / ".yggdrasil" / "state" / "llm" / "requests"
    state_responses = workspace_root / ".yggdrasil" / "state" / "llm" / "responses"
    state_out_dir = workspace_root / ".yggdrasil" / "state" / "llm" / "task-conversations"
    tmp_out_dir = workspace_root / "tmp" / "task-conversations" / "data"

    request_files = sorted(state_requests.glob("*.json")) if state_requests.exists() else []
    task_index: dict[str, dict[str, Any]] = {}

    for request_path in request_files:
        request_payload = _load_json(request_path)
        if request_payload is None:
            continue
        invocation_id = str(request_payload.get("invocationId") or request_path.stem).strip()
        task_id = str(request_payload.get("taskId") or "").strip()
        if not task_id:
            continue
        response_path = state_responses / f"{invocation_id}.json"
        response_payload = _load_json(response_path) if response_path.exists() else {}

        runtime_metrics = response_payload.get("runtimeMetrics") if isinstance(response_payload.get("runtimeMetrics"), dict) else {}
        context_observations = response_payload.get("contextLengthObservations") if isinstance(response_payload.get("contextLengthObservations"), list) else []

        base_messages = _serialize_messages(request_payload.get("messages") or request_payload.get("body", {}).get("messages"))
        conversation_messages = _serialize_messages(request_payload.get("conversationMessages"))
        if not conversation_messages:
            conversation_messages = [*base_messages]
            conversation_messages.append(
                {
                    "role": "assistant",
                    "content": str(response_payload.get("assistantText") or ""),
                }
            )

        entry = {
            "invocationId": invocation_id,
            "taskId": task_id,
            "agentRunId": request_payload.get("agentRunId") or response_payload.get("agentRunId"),
            "promptCompileArtifactId": response_payload.get("promptCompileArtifactId") or request_payload.get("promptCompileArtifactId"),
            "status": "error" if response_payload.get("error") else "ok",
            "requestedModel": request_payload.get("requestedModel"),
            "requestedProvider": request_payload.get("requestedProvider"),
            "resolvedModel": response_payload.get("model"),
            "resolvedProvider": response_payload.get("provider"),
            "windowIndex": runtime_metrics.get("windowIndex"),
            "restartCount": runtime_metrics.get("restartCount"),
            "cumulativeWindowSpanTokens": runtime_metrics.get("cumulativeWindowSpanTokens"),
            "contextLengthObservations": context_observations,
            "messages": base_messages,
            "conversationMessages": conversation_messages,
            "assistantText": str(response_payload.get("assistantText") or ""),
            "error": response_payload.get("error"),
            "endedAt": str(response_payload.get("endedAt") or request_payload.get("createdAt") or ""),
        }

        state_record = _upsert_record(state_out_dir / f"task_{task_id}.json", task_id, entry)
        tmp_record = _upsert_record(tmp_out_dir / f"task_{task_id}.json", task_id, entry)
        task_index[task_id] = {
            "taskId": task_id,
            "recordPath": f"task_{task_id}.json",
            "invocationCount": int(tmp_record.get("invocationCount") or 0),
            "latestInvocationId": tmp_record.get("latestInvocationId"),
            "latestWindowIndex": tmp_record.get("latestWindowIndex"),
            "latestStatus": tmp_record.get("latestStatus"),
            "updatedAt": tmp_record.get("updatedAt"),
        }

    tasks = sorted(task_index.values(), key=lambda item: str(item.get("updatedAt") or ""), reverse=True)
    index_payload = {
        "updatedAt": tasks[0].get("updatedAt") if tasks else "",
        "tasks": tasks,
    }
    state_out_dir.mkdir(parents=True, exist_ok=True)
    tmp_out_dir.mkdir(parents=True, exist_ok=True)
    (state_out_dir / "index.json").write_text(json.dumps(index_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (tmp_out_dir / "index.json").write_text(json.dumps(index_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({"tasks": len(tasks), "stateOut": str(state_out_dir), "tmpOut": str(tmp_out_dir)}, ensure_ascii=False))


def main() -> int:
    parser = argparse.ArgumentParser(description="Rebuild task-level merged conversation artifacts from llm request/response state files.")
    parser.add_argument("--workspace", type=Path, default=Path.cwd(), help="Workspace root path")
    args = parser.parse_args()
    rebuild(args.workspace.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
