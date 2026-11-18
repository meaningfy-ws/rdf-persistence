"""The Redis event bus: the conformance suite (TC-22), the trim (TC-23) and the claim (TC-08)."""

import logging
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pytest
from faststream.redis import RedisBroker
from faststream.redis.opentelemetry import RedisTelemetryMiddleware
from opentelemetry.trace import SpanKind
from redis.asyncio import Redis

from rdf_persistence import ToolkitSettings
from rdf_persistence.core.domain.generated.rp_provenance import Replace
from rdf_persistence.events.adapters.redis_events import RedisEventBus
from rdf_persistence.testkit.bootstrap import wait_until_async
from rdf_persistence.testkit.event_bus_conformance import (
    BODY,
    CASES,
    ENVELOPE,
    OTHER_BODY,
    Inbox,
    run_case,
)
from tests.logs import attributes, records_of

NODE_MAX_ENTRIES = "stream-node-max-entries"


class RedisPair:
    """Two deployments on one stream; Redis fails a bus by closing it, and starts it again after."""

    def __init__(self, url: str, toolkit: ToolkitSettings, **options: float) -> None:
        self.stream = stream = f"rp-events-{uuid.uuid4().hex[:8]}"
        events = toolkit.events.replaced(stream=stream, **options)
        self.a = RedisEventBus(url, deployment="lib", events=events)
        self.b = RedisEventBus(url, deployment="cat", events=events)

    @asynccontextmanager
    async def failing(self, bus: RedisEventBus) -> AsyncIterator[None]:
        await bus.close()
        yield
        await bus.start(Inbox())


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.__name__)
async def test_the_redis_bus_conforms(redis, toolkit, case):
    await run_case(case, RedisPair(redis, toolkit, claim_idle_seconds=0.5))


def test_the_redis_bus_takes_no_per_value_keyword_beside_its_events_group():  # TC-39, DEC-5
    with pytest.raises(TypeError, match="stream"):
        RedisEventBus("redis://localhost", deployment="d", stream="x")  # type: ignore[call-arg]


async def test_an_entry_older_than_the_retention_is_trimmed_on_the_next_publish(redis, toolkit):
    pair = RedisPair(redis, toolkit, retention_seconds=1)
    inbox = Inbox()
    await pair.a.start(inbox)
    async with Redis.from_url(redis) as client:
        # the trim is approximate (D-17): it drops whole nodes, so one entry per node makes it exact here
        # the server is shared by the session: put its setting back whatever the test does (rule 13)
        previous = (await client.config_get(NODE_MAX_ENTRIES))[NODE_MAX_ENTRIES]
        await client.config_set(NODE_MAX_ENTRIES, 1)
        try:
            await pair.a.publish(ENVELOPE, BODY)
            [(first_id, _)] = await client.xrange(pair.stream)
            first_ms = int(first_id.decode().split("-")[0])

            async def retention_has_passed() -> bool:
                seconds, micros = await client.time()
                return seconds * 1000 + micros // 1000 > first_ms + 1000

            await wait_until_async(retention_has_passed, "the retention to pass")
            await pair.a.publish(ENVELOPE, OTHER_BODY)
            ids = [entry_id for entry_id, _ in await client.xrange(pair.stream)]
        finally:
            await client.config_set(NODE_MAX_ENTRIES, previous)
    await pair.a.close()
    assert first_id not in ids, "the old entry was trimmed"
    assert len(ids) == 1, "one entry remains after the trim"


async def test_a_trim_that_fails_does_not_fail_the_publish(
    redis, toolkit, monkeypatch, caplog
):  # D-17
    pair = RedisPair(redis, toolkit)
    await pair.a.start(Inbox())
    client = pair.a._broker.config.broker_config.connection.client

    async def refused(*args, **kwargs):
        raise ConnectionError("the trim was refused")

    monkeypatch.setattr(client, "xtrim", refused)  # this client only, not the class
    with caplog.at_level(logging.WARNING, logger="rdf_persistence.events.adapters.redis_events"):
        await pair.a.publish(ENVELOPE, BODY)  # the entry is sent; only the trim fails
    async with Redis.from_url(redis) as reader:
        assert len(await reader.xrange(pair.stream)) == 1, "the publish still wrote its entry"
    await pair.a.close()
    [record] = records_of(caplog, "event-trim-failed")
    assert record.levelno == logging.WARNING
    assert record.getMessage() == "trimming the stream failed; the entry was published"
    assert record.exc_info is not None, "the cause stays on the record"
    assert attributes(record) == {
        "rp.step": "event-trim-failed",
        "messaging.system.name": "redis",
        "messaging.destination.name": pair.stream,
    }
    assert [r.levelno for r in caplog.records] == [logging.WARNING], (
        "a failed trim is logged once as a warning"
    )


async def test_tc28_the_broker_middleware_links_a_publish_to_its_receive(redis, toolkit, spans):
    stream = f"rp-events-{uuid.uuid4().hex[:8]}"
    bus = RedisEventBus(
        redis,
        deployment="lib",
        events=toolkit.events.replaced(stream=stream),
        middlewares=[RedisTelemetryMiddleware()],
    )
    inbox = Inbox()
    await bus.start(inbox)
    await bus.publish(ENVELOPE, BODY)
    await inbox.has(1)
    await bus.close()
    kinds = {
        span.kind: span for span in spans() if span.kind in (SpanKind.PRODUCER, SpanKind.CONSUMER)
    }
    assert set(kinds) == {SpanKind.PRODUCER, SpanKind.CONSUMER}, "one span of each kind"
    assert kinds[SpanKind.PRODUCER].context.trace_id == kinds[SpanKind.CONSUMER].context.trace_id, (
        "one trace"
    )
    [(envelope, body)] = inbox.got
    assert envelope == ENVELOPE, "the envelope reads back unchanged"
    assert Replace.model_validate_json(body) == BODY, "and the body"


async def test_a_message_without_a_valid_envelope_is_dropped_with_a_warning(
    redis, toolkit, caplog
):  # TC-22
    pair = RedisPair(redis, toolkit)
    inbox = Inbox()
    await pair.a.start(inbox)
    with caplog.at_level(logging.WARNING, logger="rdf_persistence.events.adapters.redis_events"):
        # a text body, as RedisEventBus.publish sends it, with headers that hold no envelope (D-7)
        async with RedisBroker(redis) as sender:
            await sender.publish(
                BODY.model_dump_json(exclude_none=True), stream=pair.stream, headers={}
            )

        async def warned() -> bool:
            return bool(records_of(caplog, "event-invalid-envelope"))

        await wait_until_async(warned, "the invalid envelope to be logged")
    await pair.a.close()
    [record] = records_of(caplog, "event-invalid-envelope")
    assert record.levelno == logging.WARNING
    assert record.getMessage() == "dropped a message with an invalid envelope"
    assert attributes(record) == {
        "rp.step": "event-invalid-envelope",
        "messaging.system.name": "redis",
        "messaging.destination.name": pair.stream,
    }
