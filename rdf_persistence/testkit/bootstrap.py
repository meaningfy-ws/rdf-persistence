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
            the wait goes on until ``timeout``. Must be positive. The call runs in a daemon
            thread that cannot be stopped: a hung call is joined again on each later poll (no
            second call starts while it runs) and is left behind if it never ends. So probes
            should be read-only; a late call may still finish.
        retry_on: Errors that mean "not ready yet"; any other error propagates.
        sleep: Injected so tests need no real sleeping.
        monotonic: Injected clock.

    Raises:
        TimeoutError: If the probe did not succeed in time.
        ValueError: If ``probe_timeout`` is not positive.
    """
    _require_positive(probe_timeout)
    bounded = _BoundedCall(probe, probe_timeout)
    deadline = monotonic() + timeout
    while monotonic() < deadline:
        try:
            result = bounded()
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
        ValueError: If ``probe_timeout`` is not positive.
    """
    _require_positive(probe_timeout)
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


def _require_positive(probe_timeout: float | None) -> None:
    if probe_timeout is not None and probe_timeout <= 0:
        raise ValueError(f"probe_timeout must be positive, got {probe_timeout:g}")


class _BoundedCall[T]:
    """Call the probe in a daemon thread; a call still running at the next poll is joined again."""

    def __init__(self, probe: Callable[[], T], probe_timeout: float | None) -> None:
        self._probe = probe
        self._probe_timeout = probe_timeout
        self._worker: threading.Thread | None = None
        self._outcome: list[tuple[T | None, BaseException | None]] = []

    def __call__(self) -> T | None:
        """Return the probe's value, or None if the call is still running after the bound."""
        if self._probe_timeout is None:
            return self._probe()
        if self._worker is None:
            self._outcome = []
            self._worker = threading.Thread(target=self._run, daemon=True)
            self._worker.start()
        self._worker.join(self._probe_timeout)
        if self._worker.is_alive():
            return None
        self._worker = None
        result, error = self._outcome[0]
        if error is not None:
            raise error
        return result

    def _run(self) -> None:
        try:
            self._outcome.append((self._probe(), None))
        except BaseException as error:  # handed to the caller's thread in __call__
            self._outcome.append((None, error))


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
