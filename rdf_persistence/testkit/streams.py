"""``open_event_stream``: read a tenant's event stream off an ASGI app, in-process (PD-2 to PD-5, PD-8).

``httpx.ASGITransport`` waits for the response to end, and an event stream ends only when the follower
leaves; this reads the stream straight off the app instead, returns once enough events came and then
disconnects. Start it as a task, wait until the follower is subscribed, then commit::

    stream = asyncio.ensure_future(open_event_stream(app, url, headers=rita, events=1))
    ...  # commit
    opened = await stream  # status, headers (a ``dict[str, str]`` with lower-case names), events
"""

import asyncio
import codecs
from collections.abc import Mapping
from contextlib import AsyncExitStack
from urllib.parse import unquote, urlsplit

from starlette.types import ASGIApp, Message, Scope

from rdf_persistence.api.entrypoints.service import LIFESPAN_STARTED
from rdf_persistence.testkit.generated.rp_testkit import OpenedStream, StreamEvent

SSE_MEDIA_TYPE = "text/event-stream"
LEAVE_WAIT_SECONDS = 1.0
DEFAULT_HOST = "test"
BLOCK_END = "\n\n"
COMMENT = ":"
KEPT_FIELDS = ("id", "event")
DATA_FIELD = "data"
RESPONSE_START = "http.response.start"
RESPONSE_BODY = "http.response.body"


class _Parser:
    """The events of the chunks fed so far: whole blocks only, the rest waits for its end."""

    def __init__(self) -> None:
        self._decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
        self._pending = ""
        self._after_cr = False

    def feed(self, chunk: bytes) -> list[StreamEvent]:
        if not (text := self._decoder.decode(chunk)):
            return []
        if self._after_cr and text.startswith("\n"):  # the LF of a CR LF that a chunk split
            text = text[1:]
        if text:
            self._after_cr = text.endswith("\r")
        self._pending += text.replace("\r\n", "\n").replace("\r", "\n")
        *blocks, self._pending = self._pending.split(BLOCK_END)
        return [event for block in blocks if (event := _event(block)) is not None]


def _event(block: str) -> StreamEvent | None:
    """The event of one block; ``None`` for a block of comments only (a keep-alive, a ``: ping``)."""
    fields: dict[str, str] = {}
    data: list[str] = []
    for line in block.split("\n"):
        if line.startswith(COMMENT):
            continue
        name, _, value = line.partition(":")
        value = value.removeprefix(" ")
        if name == DATA_FIELD:
            data.append(value)
        elif name in KEPT_FIELDS:
            fields[name] = value
    if data:
        fields[DATA_FIELD] = "\n".join(data)
    return StreamEvent(**fields) if fields else None


class _Exchange:
    """One request to an app and the response as it comes: the ASGI ``receive`` and ``send``."""

    def __init__(self, url: str, headers: Mapping[str, str] | None, state: Mapping | None) -> None:
        parts = urlsplit(url)
        given = {name.lower(): value for name, value in (headers or {}).items()}
        merged = {"host": DEFAULT_HOST, **given}
        self.scope: Scope = {
            "type": "http",
            # no spec_version: Starlette then listens for the disconnect
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "GET",
            "scheme": parts.scheme or "http",
            "path": unquote(parts.path) or "/",
            "raw_path": (parts.path or "/").encode(),
            "query_string": parts.query.encode(),
            "root_path": "",
            "headers": [(k.encode("latin-1"), v.encode("latin-1")) for k, v in merged.items()],
            "client": ("testclient", 50000),
            "server": (DEFAULT_HOST, 80),
        }
        if isinstance(state, Mapping):
            self.scope["state"] = dict(state)
        self.status = 0
        self.headers: dict[str, str] = {}
        self.started = asyncio.Event()
        self.leave = asyncio.Event()
        self.chunks: asyncio.Queue[bytes | None] = asyncio.Queue()
        self._asked = False

    async def receive(self) -> Message:
        if not self._asked:
            self._asked = True
            return {"type": "http.request", "body": b"", "more_body": False}
        await self.leave.wait()
        return {"type": "http.disconnect"}

    async def send(self, message: Message) -> None:
        if message["type"] == RESPONSE_START:
            self.status = message["status"]
            for raw_name, raw_value in message.get("headers", []):
                name, value = raw_name.decode("latin-1").lower(), raw_value.decode("latin-1")
                held = self.headers.get(name)
                self.headers[name] = value if held is None else f"{held}, {value}"
            self.started.set()
        elif message["type"] == RESPONSE_BODY:
            self.chunks.put_nowait(message.get("body", b""))
            if not message.get("more_body", False):
                self.chunks.put_nowait(None)

    def is_event_stream(self) -> bool:
        return self.headers.get("content-type", "").startswith(SSE_MEDIA_TYPE)


async def _enter_lifespan(stack: AsyncExitStack, app: ASGIApp) -> Mapping | None:
    """Run the app's lifespan for the call, unless it has none or the caller already runs it (PD-3)."""
    lifespan = getattr(getattr(app, "router", None), "lifespan_context", None)
    if lifespan is None or getattr(getattr(app, "state", None), LIFESPAN_STARTED, False):
        return None
    return await stack.enter_async_context(lifespan(app))


async def _head_or_end(exchange: _Exchange, task: asyncio.Future, url: str) -> None:
    """Wait for the response head; if the app ended without one, say why."""
    head = asyncio.ensure_future(exchange.started.wait())
    try:
        await asyncio.wait({task, head}, return_when=asyncio.FIRST_COMPLETED)
    finally:
        head.cancel()
    if not exchange.started.is_set():
        task.result()  # the app's own exception, if it raised
        raise RuntimeError(f"{url}: the app sent no response")


async def _read(exchange: _Exchange, events: int, found: list[StreamEvent]) -> None:
    """Read until ``events`` events came or the response ended; a refusal is read to its end."""
    parser = _Parser()
    sse = exchange.is_event_stream()
    while not (sse and len(found) >= events):
        chunk = await exchange.chunks.get()
        if chunk is None:
            return
        if sse:
            found.extend(parser.feed(chunk))


async def _leave(exchange: _Exchange, task: asyncio.Future) -> None:
    """Tell the app the client is gone; give it a moment, then cancel it and wait for it."""
    exchange.leave.set()
    await asyncio.wait({task}, timeout=LEAVE_WAIT_SECONDS)
    if not task.done():
        task.cancel()
    await asyncio.gather(task, return_exceptions=True)


async def open_event_stream(
    app: ASGIApp,
    url: str,
    *,
    headers: Mapping[str, str] | None = None,
    events: int = 0,
    timeout: float = 3.0,
) -> OpenedStream:
    """Open ``url`` on ``app``; return its status, headers (``dict[str, str]``, lower-case names) and events.

    Returns as soon as the head came and ``events`` is 0, ``events`` events came, or the response ended
    (then with the events so far, fewer than asked: a refusal, or a stream the server ended). A response
    that is not an event stream is read to its end and has no events. Raises ``TimeoutError`` naming
    ``url`` when ``timeout`` seconds, for the head and the events together, are not enough; ``RuntimeError``
    when the app sent no response; the app's own exception when it raised before the head; ``ValueError``
    for a bad argument. The app's lifespan runs for the call unless it is already running.
    """
    if events < 0:
        raise ValueError(f"events must be 0 or more, got {events}")
    if timeout <= 0:
        raise ValueError(f"timeout must be above 0, got {timeout}")
    async with AsyncExitStack() as stack:
        exchange = _Exchange(url, headers, await _enter_lifespan(stack, app))
        task = asyncio.ensure_future(app(exchange.scope, exchange.receive, exchange.send))
        # a finished app ends the read
        task.add_done_callback(lambda _: exchange.chunks.put_nowait(None))
        found: list[StreamEvent] = []
        deadline = asyncio.timeout(timeout)
        try:
            async with deadline:
                await _head_or_end(exchange, task, url)
                await _read(exchange, events, found)
        except TimeoutError:
            if not deadline.expired():
                raise
            got = f"{len(found)} of {events} events"
            what = got if exchange.started.is_set() else "no response head"
            raise TimeoutError(f"{url}: {what} within {timeout} s") from None
        finally:
            await _leave(exchange, task)
        return OpenedStream(
            status=exchange.status, headers=exchange.headers, events=found[: events or 0]
        )
