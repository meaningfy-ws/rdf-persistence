"""The wait, parse and environment helpers behind the container fixtures (PD-16)."""

import asyncio
import os
import threading

import pytest

from rdf_persistence.testkit.bootstrap import (
    environment,
    redact_secrets,
    value_after,
    wait_until,
    wait_until_async,
)


class FakeClock:
    """A clock whose sleep advances time, so waits take no real time."""

    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


class AsyncFakeClock(FakeClock):
    async def asleep(self, seconds: float) -> None:
        self.sleep(seconds)


async def _wait_async(probe, clock: AsyncFakeClock, **kwargs):
    return await wait_until_async(
        probe,
        "the file listing",
        timeout=10,
        sleep=clock.asleep,
        monotonic=clock.monotonic,
        **kwargs,
    )


async def test_async_wait_returns_the_value_of_the_third_call_without_real_sleeping() -> None:
    clock = AsyncFakeClock()
    answers = iter([None, None, ["a.csv"]])

    async def probe():
        return next(answers)

    assert await _wait_async(probe, clock) == ["a.csv"]
    assert len(clock.sleeps) == 2


async def test_async_wait_times_out_naming_what_it_waited_for() -> None:
    async def probe():
        return None

    with pytest.raises(TimeoutError, match="the file listing did not answer within 10s"):
        await _wait_async(probe, AsyncFakeClock())


async def test_async_wait_retries_the_listed_errors_and_propagates_others() -> None:
    calls = []

    async def flaky():
        calls.append(1)
        if len(calls) < 3:
            raise ConnectionError("not yet")
        return True

    assert await _wait_async(flaky, AsyncFakeClock(), retry_on=(OSError,)) is True

    bug_calls = []

    async def bug():
        bug_calls.append(1)
        raise ValueError("bug")

    clock = AsyncFakeClock()
    with pytest.raises(ValueError):
        await _wait_async(bug, clock, retry_on=(OSError,))
    assert bug_calls == [1]
    assert clock.sleeps == []


def _wait(probe, clock: FakeClock, **kwargs):
    return wait_until(
        probe, "thing", timeout=10, sleep=clock.sleep, monotonic=clock.monotonic, **kwargs
    )


def test_wait_retries_a_probe_that_fails_twice_then_returns_its_value() -> None:
    clock = FakeClock()
    answers = iter([False, "", "node-1"])
    assert _wait(lambda: next(answers), clock) == "node-1"
    assert len(clock.sleeps) == 2


def test_wait_retries_the_listed_errors_only() -> None:
    clock = FakeClock()
    calls = []

    def probe() -> bool:
        calls.append(1)
        if len(calls) < 3:
            raise ConnectionError("not yet")
        return True

    assert _wait(probe, clock, retry_on=(OSError,)) is True
    with pytest.raises(ValueError):
        _wait(lambda: (_ for _ in ()).throw(ValueError("bug")), clock, retry_on=(OSError,))


def test_wait_times_out_naming_what_it_waited_for() -> None:
    clock = FakeClock()
    with pytest.raises(TimeoutError, match="thing did not answer within 10s"):
        _wait(lambda: False, clock)


# --- probe_timeout: one hung call counts as "not ready yet" (PD-5) ----------------------------

PROBE_TIMEOUT = 0.01  # the only real wait: how long one poll joins the worker thread


def _bounded_wait(probe, clock: FakeClock, **kwargs):
    return wait_until(
        probe,
        "the bucket",
        timeout=3,
        sleep=clock.sleep,
        monotonic=clock.monotonic,
        **kwargs,
    )


async def _bounded_wait_async(probe, clock: AsyncFakeClock, **kwargs):
    return await wait_until_async(
        probe,
        "the bucket",
        timeout=3,
        sleep=clock.asleep,
        monotonic=clock.monotonic,
        **kwargs,
    )


def test_wait_times_out_naming_what_and_starts_one_call_when_a_probe_never_returns() -> None:
    release = threading.Event()  # never set during the wait; set after, to free the thread
    calls = []

    def probe():
        calls.append(1)
        release.wait()

    try:
        with pytest.raises(TimeoutError, match="the bucket did not answer within 3s"):
            _bounded_wait(probe, FakeClock(), probe_timeout=PROBE_TIMEOUT)
    finally:
        release.set()
    assert calls == [1], "a hung call must not be followed by a new thread on every poll"


def test_wait_returns_the_answer_of_a_slow_call_once_it_finishes() -> None:
    release = threading.Event()
    calls = []

    def probe():
        calls.append(1)
        release.wait()
        return ["a.csv"]

    clock = FakeClock()
    first_sleep = clock.sleep

    def sleep_then_release(seconds: float) -> None:
        first_sleep(seconds)
        release.set()  # the slow call finishes while the wait sleeps

    result = wait_until(
        probe,
        "the bucket",
        timeout=3,
        probe_timeout=PROBE_TIMEOUT,
        sleep=sleep_then_release,
        monotonic=clock.monotonic,
    )
    assert result == ["a.csv"]
    assert calls == [1]


@pytest.mark.parametrize("probe_timeout", [0, -1])
def test_wait_refuses_a_probe_timeout_that_is_not_positive(probe_timeout) -> None:
    with pytest.raises(ValueError, match="probe_timeout"):
        _bounded_wait(lambda: True, FakeClock(), probe_timeout=probe_timeout)


@pytest.mark.parametrize("probe_timeout", [0, -1])
async def test_async_wait_refuses_a_probe_timeout_that_is_not_positive(probe_timeout) -> None:
    async def probe():
        return True

    with pytest.raises(ValueError, match="probe_timeout"):
        await _bounded_wait_async(probe, AsyncFakeClock(), probe_timeout=probe_timeout)


def test_wait_propagates_a_non_retry_error_from_the_bounded_call() -> None:
    calls = []

    def probe():
        calls.append(1)
        raise ValueError("bug")

    with pytest.raises(ValueError, match="bug"):
        _bounded_wait(probe, FakeClock(), probe_timeout=1.0, retry_on=(OSError,))
    assert calls == [1]


def test_wait_retries_a_retry_on_error_from_the_bounded_call() -> None:
    calls = []

    def probe():
        calls.append(1)
        if len(calls) < 3:
            raise ConnectionError("not yet")
        return True

    assert _bounded_wait(probe, FakeClock(), probe_timeout=1.0, retry_on=(OSError,)) is True


async def test_async_wait_times_out_naming_what_when_a_probe_call_never_returns() -> None:
    async def probe():
        await asyncio.Event().wait()

    with pytest.raises(TimeoutError, match="the bucket did not answer within 3s"):
        await _bounded_wait_async(probe, AsyncFakeClock(), probe_timeout=PROBE_TIMEOUT)


async def test_async_wait_goes_on_after_a_slow_call_and_returns_the_next_answer() -> None:
    calls = []

    async def probe():
        calls.append(1)
        if len(calls) == 1:
            await asyncio.Event().wait()
        return ["a.csv"]

    assert await _bounded_wait_async(probe, AsyncFakeClock(), probe_timeout=PROBE_TIMEOUT) == [
        "a.csv"
    ]


async def test_async_wait_propagates_a_non_retry_error_from_the_bounded_call() -> None:
    calls = []

    async def probe():
        calls.append(1)
        raise ValueError("bug")

    with pytest.raises(ValueError, match="bug"):
        await _bounded_wait_async(probe, AsyncFakeClock(), probe_timeout=1.0, retry_on=(OSError,))
    assert calls == [1]


async def test_async_wait_treats_a_timeout_raised_by_the_probe_like_any_retry_error() -> None:
    calls = []

    async def probe():
        calls.append(1)
        if len(calls) == 1:
            raise TimeoutError("probe's own")  # not the bound: follows retry_on
        return True

    assert (
        await _bounded_wait_async(
            probe, AsyncFakeClock(), probe_timeout=1.0, retry_on=(TimeoutError,)
        )
        is True
    )

    async def raises_own_timeout():
        raise TimeoutError("probe's own")

    with pytest.raises(TimeoutError, match="probe's own"):
        await _bounded_wait_async(
            raises_own_timeout, AsyncFakeClock(), probe_timeout=1.0, retry_on=(ConnectionError,)
        )


OUTPUT = "==== KEY INFORMATION ====\nKey name: rp\nKey ID: GK123\nSecret key: s3cr3t\n"


def test_value_after_reads_the_labelled_line() -> None:
    assert value_after("key id", OUTPUT) == "GK123"
    assert value_after("secret key", OUTPUT) == "s3cr3t"


def test_value_after_names_the_missing_label_but_not_the_output() -> None:
    with pytest.raises(ValueError) as error:
        value_after("bucket", OUTPUT)
    assert "bucket" in str(error.value)
    assert "s3cr3t" not in str(error.value)


def test_redact_secrets_drops_the_secret_line() -> None:
    redacted = redact_secrets(OUTPUT)
    assert "s3cr3t" not in redacted
    assert "GK123" in redacted


def test_environment_sets_variables_and_restores_every_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RP_TEST_KEPT", "before")
    monkeypatch.delenv("RP_TEST_NEW", raising=False)
    with pytest.raises(RuntimeError), environment(RP_TEST_KEPT="during", RP_TEST_NEW="x"):
        assert os.environ["RP_TEST_KEPT"] == "during"
        assert os.environ["RP_TEST_NEW"] == "x"
        raise RuntimeError("boom")
    assert os.environ["RP_TEST_KEPT"] == "before", "a changed variable was not restored"
    assert "RP_TEST_NEW" not in os.environ, "a new variable was not removed"


# --- deep tests: edges of wait_until_async ---------------------------------------------------


async def test_async_wait_with_zero_timeout_never_calls_the_probe_and_times_out() -> None:
    calls = []

    async def probe():
        calls.append(1)
        return True

    clock = AsyncFakeClock()
    with pytest.raises(TimeoutError, match="the file listing did not answer within 0s"):
        await wait_until_async(
            probe, "the file listing", timeout=0, sleep=clock.asleep, monotonic=clock.monotonic
        )
    assert calls == []
    assert clock.sleeps == []


@pytest.mark.parametrize("falsy", [0, "", [], False, None])
async def test_async_wait_keeps_polling_on_falsy_results_until_timeout(falsy) -> None:
    calls = []

    async def probe():
        calls.append(1)
        return falsy

    clock = AsyncFakeClock()
    with pytest.raises(TimeoutError):
        await _wait_async(probe, clock)
    assert len(calls) == len(clock.sleeps) == 10  # truthy is the contract, not "not None"


async def test_async_wait_with_empty_retry_on_lets_oserror_propagate() -> None:
    async def probe():
        raise OSError("refused")

    with pytest.raises(OSError, match="refused"):
        await _wait_async(probe, AsyncFakeClock(), retry_on=())


async def test_async_wait_retries_a_subclass_of_a_listed_error() -> None:
    class RefusedError(ConnectionError):
        pass

    calls = []

    async def probe():
        calls.append(1)
        if len(calls) < 2:
            raise RefusedError("not yet")
        return "up"

    assert await _wait_async(probe, AsyncFakeClock(), retry_on=(ConnectionError,)) == "up"


async def test_async_wait_does_not_swallow_cancellation_even_when_retry_on_is_broad() -> None:
    import asyncio

    async def probe():
        raise asyncio.CancelledError

    clock = AsyncFakeClock()
    with pytest.raises(asyncio.CancelledError):
        await _wait_async(probe, clock, retry_on=(Exception,))
    assert clock.sleeps == []


async def test_async_wait_cancelled_during_sleep_propagates() -> None:
    import asyncio

    async def probe():
        return None

    async def cancelled_sleep(_seconds):
        raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        await wait_until_async(
            probe, "x", timeout=10, sleep=cancelled_sleep, monotonic=AsyncFakeClock().monotonic
        )


async def test_async_wait_given_a_sync_probe_raises_type_error() -> None:
    def sync_probe():
        return True

    with pytest.raises(TypeError):
        await _wait_async(sync_probe, AsyncFakeClock())


async def test_async_sync_probe_raising_a_retried_error_is_not_masked() -> None:
    # The sync probe raises before returning, so the retry swallows it and the misuse
    # surfaces only as a timeout instead of a TypeError.
    def sync_probe():
        raise OSError("sync")

    with pytest.raises(TimeoutError):
        await _wait_async(sync_probe, AsyncFakeClock())


@pytest.mark.parametrize("timeout", [2.5, 0.5, 180, 1e-3])
async def test_async_and_sync_timeout_messages_are_identical(timeout) -> None:
    async def aprobe():
        return None

    def probe():
        return None

    aclock, sclock = AsyncFakeClock(), FakeClock()
    with pytest.raises(TimeoutError) as async_error:
        await wait_until_async(
            aprobe, "the store", timeout=timeout, sleep=aclock.asleep, monotonic=aclock.monotonic
        )
    with pytest.raises(TimeoutError) as sync_error:
        wait_until(
            probe, "the store", timeout=timeout, sleep=sclock.sleep, monotonic=sclock.monotonic
        )
    assert str(async_error.value) == str(sync_error.value)


async def test_async_timeout_message_renders_a_fractional_timeout_plainly() -> None:
    async def probe():
        return None

    clock = AsyncFakeClock()
    with pytest.raises(TimeoutError, match=r"^the store did not answer within 2\.5s$"):
        await wait_until_async(
            probe, "the store", timeout=2.5, sleep=clock.asleep, monotonic=clock.monotonic
        )


def test_importing_the_testkit_loads_no_third_party_module() -> None:
    import subprocess
    import sys

    code = (
        "import sys, rdf_persistence.testkit\n"
        "bad = [m for m in ('jwt', 'cryptography', 'testcontainers', 'httpx') "
        "if m in sys.modules]\n"
        "sys.exit(','.join(bad) or 0)"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
