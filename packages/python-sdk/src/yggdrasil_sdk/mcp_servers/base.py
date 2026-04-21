from __future__ import annotations

from dataclasses import dataclass
import json
import sys
from typing import Any, Callable


ToolHandler = Callable[[dict[str, Any]], dict[str, Any]]


def structured_tool_result(payload: Any, *, text: str | None = None, is_error: bool = False) -> dict[str, Any]:
    summary = text or json.dumps(payload, ensure_ascii=False, indent=2)
    return {
        "content": [{"type": "text", "text": summary}],
        "structuredContent": payload if isinstance(payload, dict) else {"value": payload},
        "isError": is_error,
    }


@dataclass(slots=True)
class _RegisteredTool:
    name: str
    description: str
    input_schema: dict[str, Any]
    handler: ToolHandler


class SimpleMCPServer:
    def __init__(self, name: str, version: str) -> None:
        self.name = name
        self.version = version
        self._tools: dict[str, _RegisteredTool] = {}

    def register_tool(
        self,
        *,
        name: str,
        description: str,
        input_schema: dict[str, Any],
        handler: ToolHandler,
    ) -> None:
        self._tools[name] = _RegisteredTool(
            name=name,
            description=description,
            input_schema=input_schema,
            handler=handler,
        )

    def _write_message(self, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        header = f"Content-Length: {len(body)}\r\n\r\n".encode("ascii")
        sys.stdout.buffer.write(header)
        sys.stdout.buffer.write(body)
        sys.stdout.buffer.flush()

    def _read_message(self) -> dict[str, Any] | None:
        headers: dict[str, str] = {}
        while True:
            line = sys.stdin.buffer.readline()
            if not line:
                return None
            if line in {b"\r\n", b"\n"}:
                break
            decoded = line.decode("utf-8", errors="replace")
            name, _, value = decoded.partition(":")
            if _:
                headers[name.lower().strip()] = value.strip()
        content_length = int(headers.get("content-length", "0") or "0")
        if content_length <= 0:
            return None
        payload = sys.stdin.buffer.read(content_length)
        if not payload:
            return None
        return json.loads(payload.decode("utf-8"))

    def _response(self, request_id: Any, result: dict[str, Any]) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": request_id, "result": result}

    def _error(self, request_id: Any, code: int, message: str) -> dict[str, Any]:
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": code, "message": message},
        }

    def _handle_request(self, message: dict[str, Any]) -> dict[str, Any] | None:
        request_id = message.get("id")
        method = str(message.get("method") or "")
        params = message.get("params") if isinstance(message.get("params"), dict) else {}
        if method == "initialize":
            return self._response(
                request_id,
                {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": {"name": self.name, "version": self.version},
                },
            )
        if method == "notifications/initialized":
            return None
        if method == "tools/list":
            return self._response(
                request_id,
                {
                    "tools": [
                        {
                            "name": tool.name,
                            "description": tool.description,
                            "inputSchema": tool.input_schema,
                        }
                        for tool in self._tools.values()
                    ]
                },
            )
        if method == "tools/call":
            tool_name = str(params.get("name") or "")
            arguments = params.get("arguments") if isinstance(params.get("arguments"), dict) else {}
            tool = self._tools.get(tool_name)
            if tool is None:
                return self._error(request_id, -32601, f"Unknown tool: {tool_name}")
            try:
                result = tool.handler(arguments)
            except Exception as exc:
                return self._response(request_id, structured_tool_result({"error": str(exc)}, text=str(exc), is_error=True))
            return self._response(request_id, result)
        return self._error(request_id, -32601, f"Unsupported method: {method}")

    def serve_stdio(self) -> None:
        while True:
            message = self._read_message()
            if message is None:
                return
            response = self._handle_request(message)
            if response is not None:
                self._write_message(response)