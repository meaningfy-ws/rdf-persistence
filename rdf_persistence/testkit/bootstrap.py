"""Plain helpers behind the container fixtures: wait, parse, and scope environment variables.

Nothing here needs Docker or ``testcontainers``, so the unit lane can test it.
"""

import os
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager

DEFAULT_TIMEOUT_SECONDS = 180
POLL_SECONDS = 1
SECRET_LABEL = "secret"


def wait_until[T](
    probe: Callable[[], T],
    what: str,
    *,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    retry_on: tuple[type[Exception], ...] = (OSError,),
    sleep: Callable[[float], None] = time.sleep,
    monotonic: Callable[[], float] = time.monotonic,
) -> T:
    """Call ``probe`` until it returns something truthy, and return that value.

    Args:
        probe: Returns a falsy value (or raises one of ``retry_on``) while not ready.
        what: Names the thing waited for, in the timeout message.
        timeout: Seconds to wait.
        retry_on: Errors that mean "not ready yet"; any other error propagates.
        sleep: Injected so tests need no real sleeping.
        monotonic: Injected clock.

    Raises:
        TimeoutError: If the probe did not succeed in time.
    """
    deadline = monotonic() + timeout
    while monotonic() < deadline:
        try:
            result = probe()
        except retry_on:
            result = None
        if result:
            return result
        sleep(POLL_SECONDS)
    raise TimeoutError(f"{what} did not answer within {timeout:g}s")


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
