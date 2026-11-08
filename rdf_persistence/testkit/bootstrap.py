"""Plain helpers behind the container fixtures, and the public waiting helpers of the testkit:
wait (sync and async), parse, and scope environment variables.

Nothing here needs Docker or ``testcontainers``, so the unit lane can test it.
"""

import asyncio
import os
import threading
import time
from collections.abc import Awaitable, Callable, Iterator
from contextlib import contextmanager

DEFAULT_TIMEOUT_SECONDS = 180
POLL_SECONDS = 1
SECRET_LABEL = "secret"


def wait_until[T](
    probe: Callable[[], T],
    what: str,
    *,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    probe_timeout: float | None = None,
    retry_on: tuple[type[Exception], ...] = (OSError,),
    sleep: Callable[[float], None] = time.sleep,
    monotonic: Callable[[], float] = time.monotonic,
) -> T:
    """Call ``probe`` until it returns something truthy, and return that value.

    Args:
        probe: Returns a falsy value (or raises one of ``retry_on``) while not ready.
        what: Names the thing waited for, in the timeout message.
        timeout: Seconds to wait.
        probe_timeout: Seconds one call of ``probe`` may take (default: no bound). A call that
            has not returned by then counts as "not ready yet", like a ``retry_on`` error, and
            the wait goes on until ``timeout``. The call runs in a daemon thread that cannot be
            stopped, so a hung call is left behind until the process ends.
        retry_on: Errors that mean "not ready yet"; any other error propagates.
        sleep: Injected so tests need no real sleeping.
        monotonic: Injected clock.

    Raises:
        TimeoutError: If the probe did not succeed in time.
    """
    deadline = monotonic() + timeout
    while monotonic() < deadline:
        try:
            result = _call_bounded(probe, probe_timeout)
        except retry_on:
            result = None
        if result:
            return result
        sleep(POLL_SECONDS)
    raise TimeoutError(_timed_out(what, timeout))


async def wait_until_async[T](
    probe: Callable[[], Awaitable[T]],
    what: str,
    *,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    probe_timeout: float | None = None,
    retry_on: tuple[type[Exception], ...] = (OSError,),
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    monotonic: Callable[[], float] = time.monotonic,
) -> T:
    """Await ``probe`` until it returns something truthy, and return that value.

    Same contract as :func:`wait_until`, for a probe that returns an awaitable. With
    ``probe_timeout`` set, a call still running after it is cancelled and counts as "not ready
    yet"; a ``TimeoutError`` the probe raises itself follows ``retry_on`` like any other error.

    Raises:
        TimeoutError: If the probe did not succeed in time.
    """
    deadline = monotonic() + timeout
    while monotonic() < deadline:
        try:
            result = await _await_bounded(probe, probe_timeout)
        except retry_on:
            result = None
        if result:
            return result
        await sleep(POLL_SECONDS)
    raise TimeoutError(_timed_out(what, timeout))


def _call_bounded[T](probe: Callable[[], T], probe_timeout: float | None) -> T | None:
    """Return the probe's value, or None if it is still running after ``probe_timeout``."""
    if probe_timeout is None:
        return probe()
    box: list[tuple[T | None, BaseException | None]] = []

    def run() -> None:
        try:
            box.append((probe(), None))
        except BaseException as error:  # handed to the caller's thread below
            box.append((None, error))

    # A Python thread cannot be stopped: a hung call's thread stays until the process ends.
    worker = threading.Thread(target=run, daemon=True)
    worker.start()
    worker.join(probe_timeout)
    if worker.is_alive():
        return None
    result, error = box[0]
    if error is not None:
        raise error
    return result


async def _await_bounded[T](
    probe: Callable[[], Awaitable[T]], probe_timeout: float | None
) -> T | None:
    """Return the awaited value, or None if the bound fired and cancelled the call."""
    try:
        async with asyncio.timeout(probe_timeout) as bound:
            return await probe()
    except TimeoutError:
        if not bound.expired():  # the probe raised it itself: let retry_on decide
            raise
        return None


def _timed_out(what: str, timeout: float) -> str:
    return f"{what} did not answer within {timeout:g}s"


def value_after(label: str, output: str) -> str:
    """Return the text after ``label:`` on the first line that starts with the label.

    The error names the label and never quotes ``output``, which may hold a secret.
    """
    for line in output.splitlines():
        if line.strip().lower().startswith(label):
            return line.split(":", 1)[1].strip()
    raise ValueError(f"no '{label}' line in the output")


def redact_secrets(text: str) -> str:
    """Drop the lines that carry a secret, so the rest can go into an error message."""
    return "\n".join(
        line for line in text.splitlines() if not line.strip().lower().startswith(SECRET_LABEL)
    )


@contextmanager
def environment(**variables: str) -> Iterator[None]:
    """Set environment variables for the block, then restore each to its previous value."""
    previous = {name: os.environ.get(name) for name in variables}
    os.environ.update(variables)
    try:
        yield
    finally:
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
