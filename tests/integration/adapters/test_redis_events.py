"""The Redis event bus: the conformance suite (TC-22), the trim (TC-23) and the claim (TC-08)."""

import logging
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import timedelta

import pytest
from redis.asyncio import Redis

from rdf_persistence.adapters.redis_events import RedisEventBus
from rdf_persistence.testkit.bootstrap import wait_until_async
from rdf_persistence.testkit.event_bus_conformance import (
    BODY,
    CASES,
    ENVELOPE,
    OTHER_BODY,
    Inbox,
    run_case,
)


class RedisPair:
    """Two deployments on one stream; Redis fails a bus by closing it, and starts it again after."""

    def __init__(self, url: str, **options: timedelta) -> None:
        self.stream = stream = f"rp-events-{uuid.uuid4().hex[:8]}"
        self.a = RedisEventBus(url, deployment="lib", stream=stream, **options)
        self.b = RedisEventBus(url, deployment="cat", stream=stream, **options)

    @asynccontextmanager
    async def failing(self, bus: RedisEventBus) -> AsyncIterator[None]:
        await bus.close()
        yield
        await bus.start(Inbox())


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.__name__)
async def test_the_redis_bus_conforms(redis, case):
    await run_case(case, RedisPair(redis, claim_idle=timedelta(milliseconds=500)))


async def test_an_entry_older_than_the_retention_is_trimmed_on_the_next_publish(redis):
    pair = RedisPair(redis, retention=timedelta(seconds=1))
    inbox = Inbox()
    await pair.a.start(inbox)
    async with Redis.from_url(redis) as client:
        # the trim is approximate (D-17): it drops whole nodes, so one entry per node makes it exact here
        await client.config_set("stream-node-max-entries", 1)
        await pair.a.publish(ENVELOPE, BODY)
        [(first_id, _)] = await client.xrange(pair.stream)
        first_ms = int(first_id.decode().split("-")[0])

        async def retention_has_passed() -> bool:
            seconds, micros = await client.time()
            return seconds * 1000 + micros // 1000 > first_ms + 1000

        await wait_until_async(retention_has_passed, "the retention to pass")
        await pair.a.publish(ENVELOPE, OTHER_BODY)
        ids = [entry_id for entry_id, _ in await client.xrange(pair.stream)]
    await pair.a.close()
    assert first_id not in ids
    assert len(ids) == 1


async def test_a_trim_that_fails_does_not_fail_the_publish(redis, monkeypatch, caplog):  # D-17
    pair = RedisPair(redis)
    await pair.a.start(Inbox())
    client = pair.a._broker.config.broker_config.connection.client

    async def refused(*args, **kwargs):
        raise ConnectionError("the trim was refused")

    monkeypatch.setattr(type(client), "xtrim", refused)
    with caplog.at_level(logging.WARNING, logger="rdf_persistence.adapters.redis_events"):
        await pair.a.publish(ENVELOPE, BODY)  # the entry is sent; only the trim fails
    async with Redis.from_url(redis) as reader:
        assert len(await reader.xrange(pair.stream)) == 1
    await pair.a.close()
    assert [r.levelno for r in caplog.records] == [logging.WARNING]
