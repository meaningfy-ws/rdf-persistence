"""The Redis Streams event bus, on FastStream (aggregate-events PD-8, D-1).

Needs the extra ``rdf-persistence[events]`` and Redis 8.4 or later (redelivery uses
``XREADGROUP ... CLAIM``). Only this module imports ``faststream`` and ``redis``.

A deployment is a consumer group: each deployment reads every entry once, and an entry whose
``receive`` raised stays pending and is delivered again after ``events.claim_idle_seconds``. Publishing needs a
started bus; a closed bus raises on ``publish``. Two processes of one deployment share the consumer
name ``deployment``, so run one consumer per deployment.
"""

import logging
import time
from datetime import timedelta

from faststream import AckPolicy
from faststream.redis import RedisBroker, StreamSub
from faststream.redis.annotations import RedisMessage
from pydantic import ValidationError

from rdf_persistence.domain.generated.rp_provenance import Activity
from rdf_persistence.services.events import Receive
from rdf_persistence.services.generated.service.rp_service import EventEnvelope
from rdf_persistence.services.generated.settings.rp_settings import EventSettings
from rdf_persistence.services.generated.telemetry.rp_telemetry import LogContext
from rdf_persistence.services.telemetry import log_extra

log = logging.getLogger(__name__)

REDIS_SYSTEM = "redis"

ENVELOPE_FIELDS = tuple(EventEnvelope.model_fields)


class RedisEventBus:
    def __init__(
        self,
        url: str,
        *,
        deployment: str,
        events: EventSettings | None = None,
    ) -> None:
        events = events or EventSettings()
        self._url = url
        self._deployment = deployment
        self._stream = events.stream
        self._retention = timedelta(seconds=events.retention_seconds)
        self._claim_idle = timedelta(seconds=events.claim_idle_seconds)
        self._polling_interval_ms = events.polling_interval_ms
        self._broker: RedisBroker | None = None

    def _context(self, step: str) -> LogContext:
        return LogContext(
            step=step,
            messaging_system_name=REDIS_SYSTEM,
            messaging_destination_name=self._stream,
        )

    async def publish(self, envelope: EventEnvelope, body: Activity) -> None:
        if self._broker is None:
            raise RuntimeError("the Redis event bus is not started")
        await self._broker.publish(
            body.model_dump_json(exclude_none=True),
            stream=self._stream,
            headers=envelope.model_dump(),
        )
        # publish has no MINID; trimming through the broker's client is D-1's fallback (RISK-1).
        # best effort (D-17): the entry is sent, so a failed trim must not make the relay send it again
        try:
            client = self._broker.config.broker_config.connection.client
            minid = int(time.time() * 1000) - int(self._retention.total_seconds() * 1000)
            await client.xtrim(self._stream, minid=f"{minid}-0", approximate=True)
        except Exception:  # noqa: BLE001 -- best effort (D-17): a failed trim is logged, never raised
            log.warning(
                "trimming the stream failed; the entry was published",
                extra=log_extra(self._context("event-trim-failed")),
                exc_info=True,
            )

    async def start(self, receive: Receive) -> None:
        broker = RedisBroker(self._url)
        subscription = StreamSub(
            self._stream,
            group=self._deployment,
            consumer=self._deployment,
            polling_interval=self._polling_interval_ms,
            claim_min_idle_time=int(self._claim_idle.total_seconds() * 1000),
        )

        @broker.subscriber(stream=subscription, ack_policy=AckPolicy.NACK_ON_ERROR)
        async def handle(raw: bytes, msg: RedisMessage) -> None:
            try:
                envelope = EventEnvelope.model_validate(
                    {f: msg.headers.get(f) for f in ENVELOPE_FIELDS}
                )
            except ValidationError:
                # shortcut: a message without a valid envelope is dropped (acked); no one could handle it.
                log.warning(
                    "dropped a message with an invalid envelope",
                    extra=log_extra(self._context("event-invalid-envelope")),
                )
                return
            await receive(envelope, raw)

        await broker.start()
        self._broker = broker

    async def close(self) -> None:
        broker, self._broker = self._broker, None
        if broker is not None:
            await broker.stop()
