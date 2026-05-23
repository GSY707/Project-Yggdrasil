# P2 任务17实现规范：安全停止与可恢复断点（2026-05-17）

来源：从总规范文档按任务拆分，保持原始代码片段与断言建议。

---

# 任务 17 (C7): 安全停止与可恢复断点

### 17.1 目标与背景

保存 pending tool calls 与 savepoint，恢复时原位续跑。关键承诺：
- 在 SafeShutdownInterrupt 发生时，snapshot 中保存 checksum 校验和
- checksum = sha256(json.dumps(pending_action, sort_keys=True))
- 恢复时校验 checksum 防止数据污染
- 支持 pending action 原位恢复，不丢失执行语义

### 17.2 新增数据类/模型定义

**文件**: `packages/python-sdk/src/yggdrasil_sdk/contracts.py`

在 `RuntimeMetricsArtifact` 之后添加：

```python
class PendingActionSnapshot(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    id: str
    action_type: Literal["tool-call", "memory-write", "external-action"] = Field(alias="actionType")
    action_payload: dict[str, Any] = Field(alias="actionPayload")
    
    # Checksum for integrity verification
    checksum: str  # sha256 hex digest
    checksum_algorithm: str = Field(default="sha256", alias="checksumAlgorithm")
    
    # Recovery metadata
    checksum_verified_at: str | None = Field(default=None, alias="checksumVerifiedAt")
    checksum_failed: bool = Field(default=False, alias="checksumFailed")
    failure_reason: str | None = Field(default=None, alias="failureReason")


class SafeStopSnapshot(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    id: str
    task_id: str = Field(alias="taskId")
    agent_run_id: str = Field(alias="agentRunId")
    invocation_id: str = Field(alias="invocationId")
    round_index: int = Field(alias="roundIndex")
    
    # Pending state
    pending_tool_calls: list[dict[str, Any]] = Field(alias="pendingToolCalls")
    pending_tool_call_count: int = Field(alias="pendingToolCallCount")
    
    # Conversation history
    conversation_messages: list[dict[str, Any]] = Field(alias="conversationMessages")
    assistant_message: dict[str, Any] | None = Field(default=None, alias="assistantMessage")
    
    # Action snapshots with checksums
    pending_action_snapshots: list[PendingActionSnapshot] = Field(
        alias="pendingActionSnapshots"
    )
    
    # Runtime state
    usage_totals: dict[str, int] = Field(alias="usageTotals")
    accumulated_cost: float = Field(alias="accumulatedCost")
    round_summaries: list[dict[str, Any]] = Field(alias="roundSummaries")
    round_modes: list[str] = Field(alias="roundModes")
    
    # Recovery info
    safe_stop_reason: str = Field(alias="safeStopReason")  # e.g., "pause-requested", "shutdown-signal"
    can_resume: bool = Field(alias="canResume", default=True)
    resume_token: str = Field(alias="resumeToken")
    
    # Timestamps
    created_at: str = Field(default_factory=utc_now)
    last_verified_at: str | None = Field(default=None, alias="lastVerifiedAt")
```

### 17.3 函数签名变更说明

#### 17.3.1 新增校验和计算函数

**文件**: `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/snapshot.py`

在文件顶部添加：

```python
from hashlib import sha256
import json


def _compute_action_checksum(action_payload: dict[str, Any]) -> str:
    """
    Compute SHA256 checksum of action payload.
    
    Args:
        action_payload: Action data to checksum
    
    Returns:
        Hex digest of SHA256 hash
    """
    payload_json = json.dumps(action_payload, sort_keys=True, separators=(",", ":"))
    return sha256(payload_json.encode("utf-8")).hexdigest()


def _verify_action_checksum(
    action: PendingActionSnapshot,
    expected_checksum: str | None = None,
) -> tuple[bool, str | None]:
    """
    Verify action checksum.
    
    Args:
        action: Action to verify
        expected_checksum: Optional expected checksum. If None, use action.checksum
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    if expected_checksum is None:
        expected_checksum = action.checksum
    
    computed_checksum = _compute_action_checksum(action.action_payload)
    
    if computed_checksum == expected_checksum:
        return True, None
    
    return False, (
        f"Checksum mismatch: expected {expected_checksum}, got {computed_checksum}"
    )
```

#### 17.3.2 新增 SafeStop 快照构建函数

**文件**: `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/snapshot.py`

```python
def build_safe_stop_snapshot(
    task_id: str,
    *,
    agent_run_id: str,
    invocation_id: str,
    round_index: int,
    pending_tool_calls: list[dict[str, Any]],
    conversation_messages: list[dict[str, Any]],
    assistant_message: dict[str, Any] | None,
    usage_totals: dict[str, int],
    accumulated_cost: float,
    round_summaries: list[dict[str, Any]],
    round_modes: list[str],
    safe_stop_reason: str = "pause-requested",
) -> SafeStopSnapshot:
    """
    Build a safe-stop snapshot with checksums for all pending actions.
    
    Args:
        task_id: Task ID
        agent_run_id: Agent run ID
        invocation_id: LLM invocation ID
        round_index: Current tool round index
        pending_tool_calls: Pending tool calls to preserve
        conversation_messages: Full conversation history
        assistant_message: Last assistant message
        usage_totals: Token usage totals
        accumulated_cost: Cost used so far
        round_summaries: Round execution summaries
        round_modes: Round mode per round
        safe_stop_reason: Reason for safe stop
    
    Returns:
        SafeStopSnapshot with checksums computed for each pending action
    """
    resume_token = new_id("resume-token", task_id, agent_run_id, invocation_id, stable=False)
    
    # Build pending action snapshots with checksums
    pending_actions = []
    for idx, tool_call in enumerate(pending_tool_calls):
        checksum = _compute_action_checksum(tool_call)
        action = PendingActionSnapshot(
            id=new_id("pending-action", task_id, idx, stable=False),
            action_type="tool-call",
            action_payload=tool_call,
            checksum=checksum,
            checksum_algorithm="sha256",
        )
        pending_actions.append(action)
    
    return SafeStopSnapshot(
        id=new_id("safe-stop-snapshot", task_id, agent_run_id, invocation_id, stable=False),
        task_id=task_id,
        agent_run_id=agent_run_id,
        invocation_id=invocation_id,
        round_index=round_index,
        pending_tool_calls=pending_tool_calls,
        pending_tool_call_count=len(pending_tool_calls),
        conversation_messages=conversation_messages,
        assistant_message=assistant_message,
        pending_action_snapshots=pending_actions,
        usage_totals=usage_totals,
        accumulated_cost=accumulated_cost,
        round_summaries=round_summaries,
        round_modes=round_modes,
        safe_stop_reason=safe_stop_reason,
        can_resume=True,
        resume_token=resume_token,
    )
```

#### 17.3.3 新增恢复验证函数

**文件**: `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/snapshot.py`

```python
def verify_safe_stop_snapshot(
    snapshot: SafeStopSnapshot,
    strict: bool = True,
) -> dict[str, Any]:
    """
    Verify all checksums in a safe-stop snapshot.
    
    Args:
        snapshot: Snapshot to verify
        strict: If True, fail on any checksum mismatch. If False, log but allow.
    
    Returns:
        Verification result dict:
        {
            "valid": bool,
            "checked_count": int,
            "failed_count": int,
            "errors": [str],
            "verified_at": str,
        }
    """
    errors = []
    checked_count = 0
    failed_count = 0
    
    for action in snapshot.pending_action_snapshots:
        checked_count += 1
        is_valid, error_msg = _verify_action_checksum(action)
        
        if not is_valid:
            failed_count += 1
            errors.append(error_msg or "Unknown verification error")
            if strict:
                action.checksum_failed = True
                action.failure_reason = error_msg
    
    is_valid = failed_count == 0
    
    result = {
        "valid": is_valid,
        "checked_count": checked_count,
        "failed_count": failed_count,
        "errors": errors,
        "verified_at": utc_now(),
    }
    
    if not is_valid and strict:
        raise ValueError(f"Safe-stop snapshot verification failed: {'; '.join(errors)}")
    
    return result
```

#### 17.3.4 修改 SafeShutdownInterrupt 处理流程

**修改位置**: `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop.py` (在处理 SafeShutdownInterrupt 的位置)

```python
# 原有代码（替换前）：
            except SafeShutdownInterrupt as _shutdown_exc:
                _logger.info(
                    "Safe shutdown requested during tool execution for task %s (invocation %s, round %d, %d pending tool calls). Saving checkpoint.",
                    task_id,
                    _shutdown_exc.invocation_id,
                    _shutdown_exc.round_index,
                    len(_shutdown_exc.pending_tool_calls),
                )
                snap_result = save_pending_tool_calls_snapshot(
                    task_id,
                    agent_run_id=run.id,
                    pending_tool_calls=_shutdown_exc.pending_tool_calls,
                    conversation_messages=_shutdown_exc.conversation_messages,
                    assistant_message=_shutdown_exc.assistant_message,
                    invocation_id=_shutdown_exc.invocation_id,
                    round_index=_shutdown_exc.round_index,
                    usage_totals=_shutdown_exc.usage_totals,
                    accumulated_cost=_shutdown_exc.accumulated_cost,
                    round_summaries=_shutdown_exc.round_summaries,
                    round_modes=_shutdown_exc.round_modes,
                    current_context_state=effective_context,
                    root_mount_preview=root_mount,
                    app_id=task.app_id,
                    project_id=task.project_id,
                    branch_id=task.branch_id,
                    lock_already_held=True,
                    session_override=session,
                    request_state=_build_restart_request_state(
                        request,
                        request.get("runtimeMetrics") if isinstance(request.get("runtimeMetrics"), dict) else {},
                    ),
                )

# 替换为：
            except SafeShutdownInterrupt as _shutdown_exc:
                _logger.info(
                    "Safe shutdown requested during tool execution for task %s (invocation %s, round %d, %d pending tool calls). "
                    "Building and verifying safe-stop snapshot.",
                    task_id,
                    _shutdown_exc.invocation_id,
                    _shutdown_exc.round_index,
                    len(_shutdown_exc.pending_tool_calls),
                )
                
                # Build safe-stop snapshot with checksums
                safe_stop_snapshot = build_safe_stop_snapshot(
                    task_id,
                    agent_run_id=run.id,
                    invocation_id=_shutdown_exc.invocation_id,
                    round_index=_shutdown_exc.round_index,
                    pending_tool_calls=_shutdown_exc.pending_tool_calls,
                    conversation_messages=_shutdown_exc.conversation_messages,
                    assistant_message=_shutdown_exc.assistant_message,
                    usage_totals=_shutdown_exc.usage_totals,
                    accumulated_cost=_shutdown_exc.accumulated_cost,
                    round_summaries=_shutdown_exc.round_summaries,
                    round_modes=_shutdown_exc.round_modes,
                    safe_stop_reason="pause-requested",
                )
                
                # Verify checksums before persisting
                verification_result = verify_safe_stop_snapshot(safe_stop_snapshot, strict=False)
                _logger.info(
                    "Safe-stop snapshot verification: checked=%d, failed=%d, valid=%s",
                    verification_result["checked_count"],
                    verification_result["failed_count"],
                    verification_result["valid"],
                )
                
                # Persist the snapshot
                snap_result = save_pending_tool_calls_snapshot(
                    task_id,
                    agent_run_id=run.id,
                    pending_tool_calls=_shutdown_exc.pending_tool_calls,
                    conversation_messages=_shutdown_exc.conversation_messages,
                    assistant_message=_shutdown_exc.assistant_message,
                    invocation_id=_shutdown_exc.invocation_id,
                    round_index=_shutdown_exc.round_index,
                    usage_totals=_shutdown_exc.usage_totals,
                    accumulated_cost=_shutdown_exc.accumulated_cost,
                    round_summaries=_shutdown_exc.round_summaries,
                    round_modes=_shutdown_exc.round_modes,
                    current_context_state=effective_context,
                    root_mount_preview=root_mount,
                    app_id=task.app_id,
                    project_id=task.project_id,
                    branch_id=task.branch_id,
                    lock_already_held=True,
                    session_override=session,
                    request_state=_build_restart_request_state(
                        request,
                        request.get("runtimeMetrics") if isinstance(request.get("runtimeMetrics"), dict) else {},
                    ),
                )
                
                # Add safe-stop snapshot reference to result
                snap_result["safeStopSnapshot"] = safe_stop_snapshot.model_dump(by_alias=True, mode="json")
                snap_result["checksumVerification"] = verification_result
```

### 17.4 集成点说明

1. **SafeStop 触发**:
   - SafeShutdownInterrupt 异常捕获
   - 调用 build_safe_stop_snapshot 构建包含校验和的快照

2. **校验和计算时机**:
   - 保存前：为每个 pending action 计算 SHA256
   - 恢复前：重新验证校验和，检测数据污染

3. **恢复流程**:
   - 加载快照时调用 verify_safe_stop_snapshot
   - 若验证失败：记录 failure_reason，可选拒绝恢复
   - 若验证通过：恢复 pending_tool_calls，原位续跑

4. **数据一致性保障**:
   - JSON 序列化时使用 sort_keys=True 保证确定性
   - Checksum 作为数据完整性证明

### 17.5 测试断言建议

```python
def test_safe_stop_snapshot_computes_checksums() -> None:
    """Test that safe-stop snapshot computes checksums for pending actions."""
    pending_tool_calls = [
        {"id": "call-1", "name": "search", "arguments": {"query": "test"}},
        {"id": "call-2", "name": "summarize", "arguments": {"text": "content"}},
    ]
    
    snapshot = build_safe_stop_snapshot(
        "task-123",
        agent_run_id="run-1",
        invocation_id="inv-1",
        round_index=1,
        pending_tool_calls=pending_tool_calls,
        conversation_messages=[],
        assistant_message=None,
        usage_totals={"inputTokens": 100, "outputTokens": 50},
        accumulated_cost=0.01,
        round_summaries=[],
        round_modes=["live"],
    )
    
    # Verify all actions have checksums
    assert len(snapshot.pending_action_snapshots) == 2
    for action in snapshot.pending_action_snapshots:
        assert action.checksum is not None
        assert len(action.checksum) == 64  # SHA256 hex is 64 chars


def test_checksum_verification_passes_for_intact_action() -> None:
    """Test that checksum verification passes for intact action."""
    action_payload = {"id": "call-1", "name": "search", "arguments": {"query": "test"}}
    checksum = _compute_action_checksum(action_payload)
    
    action = PendingActionSnapshot(
        id="action-1",
        action_type="tool-call",
        action_payload=action_payload,
        checksum=checksum,
    )
    
    is_valid, error_msg = _verify_action_checksum(action)
    assert is_valid is True
    assert error_msg is None


def test_checksum_verification_fails_for_corrupted_action() -> None:
    """Test that checksum verification fails for corrupted action."""
    action_payload = {"id": "call-1", "name": "search", "arguments": {"query": "test"}}
    checksum = _compute_action_checksum(action_payload)
    
    # Corrupt the payload after checksum computation
    corrupted_payload = {"id": "call-1", "name": "search", "arguments": {"query": "modified"}}
    
    action = PendingActionSnapshot(
        id="action-1",
        action_type="tool-call",
        action_payload=corrupted_payload,
        checksum=checksum,
    )
    
    is_valid, error_msg = _verify_action_checksum(action)
    assert is_valid is False
    assert "mismatch" in (error_msg or "").lower()


def test_safe_stop_snapshot_verification_strict_mode_raises() -> None:
    """Test that strict verification raises on checksum failure."""
    # Build snapshot with corrupted actions
    pending_tool_calls = [
        {"id": "call-1", "name": "search", "arguments": {"query": "test"}},
    ]
    
    snapshot = build_safe_stop_snapshot(
        "task-123",
        agent_run_id="run-1",
        invocation_id="inv-1",
        round_index=1,
        pending_tool_calls=pending_tool_calls,
        conversation_messages=[],
        assistant_message=None,
        usage_totals={},
        accumulated_cost=0.0,
        round_summaries=[],
        round_modes=[],
    )
    
    # Corrupt the payload
    snapshot.pending_action_snapshots[0].action_payload["arguments"]["query"] = "corrupted"
    
    # Strict verification should raise
    with pytest.raises(ValueError, match="verification failed"):
        verify_safe_stop_snapshot(snapshot, strict=True)


def test_safe_stop_snapshot_recovery_preserves_pending_actions() -> None:
    """Test that pending actions can be recovered from snapshot."""
    original_pending_calls = [
        {"id": "call-1", "name": "search", "arguments": {"query": "test"}},
        {"id": "call-2", "name": "read_file", "arguments": {"path": "/tmp/test.txt"}},
    ]
    
    snapshot = build_safe_stop_snapshot(
        "task-123",
        agent_run_id="run-1",
        invocation_id="inv-1",
        round_index=2,
        pending_tool_calls=original_pending_calls,
        conversation_messages=[],
        assistant_message=None,
        usage_totals={"inputTokens": 500},
        accumulated_cost=0.02,
        round_summaries=[],
        round_modes=["live"],
    )
    
    # Verify snapshot
    verification = verify_safe_stop_snapshot(snapshot, strict=True)
    assert verification["valid"] is True
    
    # Recover and verify
    recovered_calls = snapshot.pending_tool_calls
    assert len(recovered_calls) == 2
    assert recovered_calls[0]["id"] == "call-1"
    assert recovered_calls[1]["name"] == "read_file"
```

---

