from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
from typing import Callable, Protocol

from ..contracts import EventEnvelope, ExternalRef
from ..support import ensure_state_subdir, read_json, relative_workspace_path, utc_now, write_json
from .database import PersistenceRuntime, get_persistence_runtime
from .repositories import OutboxRepository
from .settings import PersistenceSettings


EventHandler = Callable[[EventEnvelope], bool]


class EventBusClient(Protocol):
    def ping(self) -> dict[str, object]:
        ...

    def ensure_stream(self) -> dict[str, object]:
        ...

    def publish(self, envelope: EventEnvelope) -> dict[str, object]:
        ...

    def consume(
        self,
        *,
        event_type: str,
        consumer_group: str,
        batch: int,
        timeout_seconds: int,
        handler: EventHandler,
    ) -> dict[str, object]:
        ...


def event_payload_ref(envelope: EventEnvelope, workspace_root: Path | None = None) -> ExternalRef:
    payload_dir = ensure_state_subdir("outbox-payloads", workspace_root)
    payload_path = payload_dir / f"{envelope.event_id}.json"
    write_json(payload_path, envelope.model_dump(by_alias=True, mode="json"))
    return ExternalRef(type="file", locator=relative_workspace_path(payload_path, workspace_root))


def load_event_envelope(payload_ref: ExternalRef, workspace_root: Path | None = None) -> EventEnvelope | None:
    if payload_ref.type != "file":
        return None
    workspace = Path(workspace_root).resolve() if workspace_root is not None else None
    if workspace is None:
        payload_path = Path(payload_ref.locator)
    else:
        payload_path = workspace / payload_ref.locator
    if not payload_path.exists():
        return None
    payload = read_json(payload_path, {})
    if not isinstance(payload, dict):
        return None
    try:
        return EventEnvelope.model_validate(payload)
    except Exception:
        return None


def outbox_record_to_envelope(record, workspace_root: Path | None = None) -> EventEnvelope:
    existing = load_event_envelope(record.payload_ref, workspace_root)
    if existing is not None:
        return existing
    return EventEnvelope(
        eventType=record.event_type,
        eventVersion=record.event_version,
        eventId=record.id,
        occurredAt=record.created_at,
        source="outbox",
        projectId=record.project_id or "project_default",
        spaceId=None,
        branchId="branch_main",
        correlationId=record.id,
        schemaRef=f"yggdrasil://events/{record.event_type}/v{record.event_version}",
        payload={"payloadRef": record.payload_ref.model_dump(by_alias=True, mode="json")},
    )


class NatsJetStreamBus:
    def __init__(self, settings: PersistenceSettings | None = None) -> None:
        self.settings = settings or PersistenceSettings.load()

    def subject_for(self, event_type: str) -> str:
        prefix = self.settings.nats_subject_prefix.rstrip(".")
        return f"{prefix}.{event_type}"

    def _run(self, operation):
        return asyncio.run(operation)

    async def _connect(self):
        from nats import connect

        client = await connect(
            servers=[self.settings.nats_url],
            connect_timeout=1,
            max_reconnect_attempts=0,
        )
        return client, client.jetstream()

    async def _ensure_stream_async(self, jetstream) -> dict[str, object]:
        subject_pattern = f"{self.settings.nats_subject_prefix.rstrip('.')}.>"
        try:
            info = await jetstream.stream_info(self.settings.nats_stream)
            return {
                "status": "ok",
                "stream": info.config.name,
                "subjects": list(info.config.subjects or []),
            }
        except Exception:
            info = await jetstream.add_stream(
                name=self.settings.nats_stream,
                subjects=[subject_pattern],
            )
            return {
                "status": "created",
                "stream": info.config.name,
                "subjects": list(info.config.subjects or []),
            }

    def ping(self) -> dict[str, object]:
        async def _ping() -> dict[str, object]:
            client, _ = await self._connect()
            try:
                return {"status": "ok", "natsUrl": self.settings.nats_url}
            finally:
                await client.drain()

        try:
            return self._run(_ping())
        except Exception as exc:
            return {"status": "error", "natsUrl": self.settings.nats_url, "detail": str(exc)}

    def ensure_stream(self) -> dict[str, object]:
        async def _ensure() -> dict[str, object]:
            client, jetstream = await self._connect()
            try:
                result = await self._ensure_stream_async(jetstream)
                result["natsUrl"] = self.settings.nats_url
                return result
            finally:
                await client.drain()

        try:
            return self._run(_ensure())
        except Exception as exc:
            return {"status": "error", "stream": self.settings.nats_stream, "detail": str(exc)}

    def publish(self, envelope: EventEnvelope) -> dict[str, object]:
        async def _publish() -> dict[str, object]:
            client, jetstream = await self._connect()
            try:
                await self._ensure_stream_async(jetstream)
                subject = self.subject_for(envelope.event_type)
                payload = json.dumps(envelope.model_dump(by_alias=True, mode="json"), ensure_ascii=False).encode("utf-8")
                acknowledgement = await jetstream.publish(subject, payload)
                return {
                    "status": "published",
                    "subject": subject,
                    "stream": acknowledgement.stream,
                    "sequence": acknowledgement.seq,
                    "eventId": envelope.event_id,
                }
            finally:
                await client.drain()

        return self._run(_publish())

    def consume(
        self,
        *,
        event_type: str,
        consumer_group: str,
        batch: int,
        timeout_seconds: int,
        handler: EventHandler,
    ) -> dict[str, object]:
        async def _consume() -> dict[str, object]:
            client, jetstream = await self._connect()
            fetched = 0
            acked = 0
            nacked = 0
            errors: list[str] = []
            try:
                await self._ensure_stream_async(jetstream)
                subject = self.subject_for(event_type)
                durable = re.sub(r"[^A-Za-z0-9_\-]", "_", consumer_group)
                subscription = await jetstream.pull_subscribe(
                    subject,
                    durable=durable,
                    stream=self.settings.nats_stream,
                )
                try:
                    messages = await subscription.fetch(batch=batch, timeout=timeout_seconds)
                except TimeoutError:
                    messages = []
                except Exception as exc:
                    if "timeout" in str(exc).lower():
                        messages = []
                    else:
                        raise

                for message in messages:
                    fetched += 1
                    envelope = EventEnvelope.model_validate(json.loads(message.data.decode("utf-8")))
                    try:
                        if handler(envelope):
                            await message.ack()
                            acked += 1
                        else:
                            await message.nak()
                            nacked += 1
                    except Exception as exc:
                        await message.nak()
                        nacked += 1
                        errors.append(str(exc))

                return {
                    "status": "ok",
                    "subject": subject,
                    "fetched": fetched,
                    "acked": acked,
                    "nacked": nacked,
                    "errors": errors,
                }
            finally:
                await client.drain()

        return self._run(_consume())


class OutboxPublisher:
    def __init__(
        self,
        *,
        workspace_root: Path | None = None,
        runtime: PersistenceRuntime | None = None,
        event_bus: EventBusClient | None = None,
    ) -> None:
        self.workspace_root = workspace_root
        self.runtime = runtime or get_persistence_runtime()
        self.event_bus = event_bus or NatsJetStreamBus(self.runtime.settings)

    def publish_pending(self, *, limit: int = 100, retry_delay_seconds: int = 15) -> dict[str, object]:
        stream_status = self.event_bus.ensure_stream()
        if stream_status.get("status") == "error":
            return {
                "status": "error",
                "stream": stream_status,
                "published": 0,
                "failed": 0,
                "events": [],
            }

        with self.runtime.session_scope() as session:
            claimed_events = OutboxRepository(session).claim_events(limit=limit)

        outcomes: list[dict[str, object]] = []
        published = 0
        failed = 0
        for record in claimed_events:
            envelope = outbox_record_to_envelope(record, self.workspace_root)
            try:
                publish_result = self.event_bus.publish(envelope)
                with self.runtime.session_scope() as session:
                    OutboxRepository(session).mark_published(record.id, published_at=utc_now())
                outcomes.append({"eventId": record.id, "status": "published", "publishResult": publish_result})
                published += 1
            except Exception as exc:
                failed += 1
                with self.runtime.session_scope() as session:
                    repository = OutboxRepository(session)
                    if record.attempts >= 5:
                        repository.mark_dead_letter(record.id, last_error=str(exc))
                    else:
                        repository.mark_pending(
                            record.id,
                            last_error=str(exc),
                            available_at=utc_now(),
                        )
                outcomes.append({"eventId": record.id, "status": "failed", "detail": str(exc)})

        return {
            "status": "ok",
            "stream": stream_status,
            "published": published,
            "failed": failed,
            "events": outcomes,
        }