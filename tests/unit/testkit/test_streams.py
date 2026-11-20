"""Spec rp-testkit: `open_event_stream` reads an event stream off any ASGI app (PD-1 to PD-5, PD-8).

The apps here are raw ASGI callables and one plain FastAPI app, so the parsing, the return rules, the
errors and the leaving are proven without the toolkit's route.
"""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse

from rdf_persistence.api.entrypoints.service import LIFESPAN_STARTED
from rdf_persistence.testkit import OpenedStream, StreamEvent, open_event_stream

GENERATED_MODULE = "rdf_persistence.testkit.generated.rp_testkit"
URL = "http://test/books/rp-events"
SSE = b"text/event-stream"
SHORT = 0.2


def test_the_result_records_are_public_and_generated() -> None:
    assert StreamEvent(id="x").id == "x", "the field is read under its alias"
    assert StreamEvent().id is None, "an absent field is None"
    assert StreamEvent(data="").data == "", "an empty field is present and empty"
    assert OpenedStream.__module__ == GENERATED_MODULE
    assert StreamEvent.__module__ == GENERATED_MODULE


async def until_disconnect(receive) -> None:
    while (await receive())["type"] != "http.disconnect":
        pass


def head(status: int = 200, content_type: bytes = SSE, *more: tuple[bytes, bytes]) -> dict:
    return {
        "type": "http.response.start",
        "status": status,
        "headers": [(b"Content-Type", content_type), *more],
    }


def body(chunk: bytes, *, more: bool = True) -> dict:
    return {"type": "http.response.body", "body": chunk, "more_body": more}


def serving(*chunks: bytes, ends: bool = False, **head_args: Any):
    """A raw ASGI app: a head, the chunks, then the end of the response or a wait for the disconnect."""

    async def app(scope, receive, send) -> None:
        await send(head(**head_args))
        for chunk in chunks:
            await send(body(chunk))
        if ends:
            await send(body(b"", more=False))
        else:
            await until_disconnect(receive)

    return app


async def opened_from(*chunks: bytes, events: int = 1) -> OpenedStream:
    return await open_event_stream(serving(*chunks), URL, events=events, timeout=3.0)


async def test_a_chunk_boundary_in_an_event_and_in_a_character_is_not_seen() -> None:
    opened = await opened_from(b"id: 1\nda", b"ta: caf\xc3", b"\xa9\n", b"\n")
    assert opened.events == [StreamEvent(id="1", data="café")]


async def test_crlf_and_a_cr_split_from_its_lf_end_lines_like_lf() -> None:
    opened = await opened_from(b"id: a\r\ndata: x\r", b"\n\r", b"\n")
    assert opened.events == [StreamEvent(id="a", data="x")]


async def test_a_lone_cr_ends_a_line() -> None:
    opened = await opened_from(b"id: a\rdata: x\r\r")
    assert opened.events == [StreamEvent(id="a", data="x")]


async def test_data_lines_are_joined_with_a_newline() -> None:
    opened = await opened_from(b"event: E\ndata: one\ndata: two\ndata:\n\n")
    assert opened.events == [StreamEvent(event="E", data="one\ntwo\n")]


async def test_keep_alive_and_ping_comments_are_no_events() -> None:
    opened = await opened_from(b": keep-alive\n\n: ping\n\nid: 7\ndata: x\n\n")
    assert opened.events == [StreamEvent(id="7", data="x")]


async def test_a_reset_has_empty_data_and_no_id() -> None:
    opened = await opened_from(b"event: reset\ndata: \n\n")
    [reset] = opened.events
    assert reset.event == "reset"
    assert reset.data == "", "present and empty"
    assert reset.id is None, "absent"


async def test_the_last_id_and_event_win_and_retry_and_unknown_names_are_ignored() -> None:
    opened = await opened_from(b"id: 1\nid: 2\nevent: A\nevent: B\nretry: 5\nwhat: x\ndata:  y\n\n")
    assert opened.events == [StreamEvent(id="2", event="B", data=" y")]


async def test_events_are_returned_as_soon_as_the_asked_number_came() -> None:
    opened = await opened_from(b"id: 1\n\n", b"id: 2\n\n", b"id: 3\n\n", events=2)
    assert [e.id for e in opened.events] == ["1", "2"], "the third was not waited for"


async def test_the_head_alone_is_enough_when_no_event_is_asked() -> None:
    opened = await open_event_stream(serving(), URL, timeout=3.0)
    assert opened.status == 200
    assert opened.events == []


async def test_header_names_are_lower_case_and_a_repeated_name_is_joined() -> None:
    async def app(scope, receive, send) -> None:
        await send(head(206, SSE, (b"Set-Cookie", b"a=1"), (b"set-cookie", b"b=2")))
        await until_disconnect(receive)

    opened = await open_event_stream(app, URL, timeout=3.0)
    assert opened.status == 206
    assert opened.headers["content-type"] == "text/event-stream"
    assert opened.headers["set-cookie"] == "a=1, b=2"


async def test_a_stream_the_server_ends_early_returns_the_events_so_far() -> None:
    app = serving(b"id: 1\n\n", ends=True)
    opened = await open_event_stream(app, URL, events=3, timeout=3.0)
    assert [e.id for e in opened.events] == ["1"], "fewer than asked, no TimeoutError"


async def test_an_app_that_raises_after_the_head_returns_what_came() -> None:
    async def failing_late(scope, receive, send) -> None:
        await send(head())
        await send(body(b"id: 1\n\n"))
        raise KeyError("boom")

    opened = await open_event_stream(failing_late, URL, events=3, timeout=SHORT)
    assert opened.status == 200
    assert [e.id for e in opened.events] == ["1"], "what came, and no exception"


async def test_a_refusal_is_returned_at_once_with_no_events() -> None:
    app = serving(b'{"title": ', b'"no"}', ends=True, status=404, content_type=b"application/json")
    opened = await open_event_stream(app, URL, events=1, timeout=SHORT)
    assert opened.status == 404, "returned, not raised, though one event was asked for"
    assert opened.events == []


async def test_fewer_events_than_asked_within_the_timeout_name_the_url_and_the_count() -> None:
    with pytest.raises(TimeoutError, match=rf"{URL}: 1 of 2 events within {SHORT} s"):
        await open_event_stream(serving(b"id: 1\n\n"), URL, events=2, timeout=SHORT)


async def test_no_head_within_the_timeout_names_the_url_and_leaves_no_app_task() -> None:
    running: list[asyncio.Task] = []

    async def silent(scope, receive, send) -> None:
        running.append(asyncio.current_task())
        await until_disconnect(receive)

    with pytest.raises(TimeoutError, match=rf"{URL}: no response head"):
        await open_event_stream(silent, URL, timeout=SHORT)
    assert running[0].done(), "the app was told to leave"


async def test_an_app_that_raises_before_the_head_has_its_exception_raised() -> None:
    async def failing(scope, receive, send) -> None:
        raise KeyError("boom")

    with pytest.raises(KeyError, match="boom"):
        await open_event_stream(failing, URL, timeout=3.0)


async def test_an_app_that_returns_without_a_head_is_a_runtime_error_naming_the_url() -> None:
    async def mute(scope, receive, send) -> None:
        return None

    with pytest.raises(RuntimeError, match=rf"{URL}: the app sent no response"):
        await open_event_stream(mute, URL, timeout=3.0)


async def test_an_app_that_ignores_the_disconnect_is_done_when_the_call_returns() -> None:
    running: list[asyncio.Task] = []

    async def deaf(scope, receive, send) -> None:
        running.append(asyncio.current_task())
        await send(head())
        await send(body(b"id: 1\n\n"))
        await asyncio.Event().wait()

    opened = await open_event_stream(deaf, URL, events=1, timeout=3.0)
    assert [e.id for e in opened.events] == ["1"]
    assert running[0].done(), "cancelled and awaited, not leaked to the next test"


async def test_a_call_cancelled_while_it_waits_leaves_its_app_task_done() -> None:
    running: list[asyncio.Task] = []
    sent = asyncio.Event()

    async def app(scope, receive, send) -> None:
        running.append(asyncio.current_task())
        await send(head())
        await send(body(b"id: 1\n\n"))
        sent.set()
        await until_disconnect(receive)

    waiting = asyncio.ensure_future(open_event_stream(app, URL, events=2, timeout=3.0))
    await sent.wait()
    waiting.cancel()
    with pytest.raises(asyncio.CancelledError):
        await waiting
    assert running[0].done()


async def test_the_scope_is_a_get_without_spec_version_and_carries_the_url_and_headers() -> None:
    scopes: list[dict] = []

    async def spy(scope, receive, send) -> None:
        scopes.append(scope)
        await send(head())
        await send(body(b"", more=False))

    await open_event_stream(
        spy, "http://test/a/b?x=1&y=2", headers={"Authorization": "Bearer t"}, timeout=3.0
    )
    [scope] = scopes
    assert scope["type"] == "http"
    assert scope["method"] == "GET"
    assert "spec_version" not in scope["asgi"], "so Starlette listens for the disconnect"
    assert (scope["path"], scope["query_string"]) == ("/a/b", b"x=1&y=2")
    assert (b"authorization", b"Bearer t") in scope["headers"], "names lower-cased"
    assert (b"host", b"test") in scope["headers"], "a default host"


@pytest.mark.parametrize(
    ("arguments", "name"),
    [({"events": -1}, "events"), ({"timeout": 0}, "timeout"), ({"timeout": -1.0}, "timeout")],
)
async def test_a_bad_argument_is_a_value_error_naming_it(arguments: dict, name: str) -> None:
    with pytest.raises(ValueError, match=name):
        await open_event_stream(serving(), URL, **arguments)


class Lifespan:
    """A plain FastAPI app that counts how often its lifespan is entered and left, and serves a stream."""

    def __init__(self, *, state: dict | None = None) -> None:
        self.entered = self.left = 0

        @asynccontextmanager
        async def lifespan(app: FastAPI) -> AsyncIterator[dict | None]:
            self.entered += 1
            try:
                yield state
            finally:
                self.left += 1

        self.app = FastAPI(lifespan=lifespan)

        @self.app.get("/books/rp-events")
        async def events(request: Request) -> StreamingResponse:
            async def stream() -> AsyncIterator[str]:
                yield f"data: {self.entered - self.left}:{getattr(request.state, 'k', '-')}\n\n"

            return StreamingResponse(stream(), media_type="text/event-stream")


async def test_the_lifespan_is_entered_and_left_once_when_the_flag_is_absent() -> None:
    plain = Lifespan()
    opened = await open_event_stream(plain.app, URL, events=1, timeout=3.0)
    assert (plain.entered, plain.left) == (1, 1)
    assert opened.events == [StreamEvent(data="1:-")], "the request ran inside the lifespan"


async def test_the_lifespan_is_not_entered_when_the_flag_says_it_runs() -> None:
    plain = Lifespan()
    setattr(plain.app.state, LIFESPAN_STARTED, True)
    opened = await open_event_stream(plain.app, URL, events=1, timeout=3.0)
    assert (plain.entered, plain.left) == (0, 0)
    assert opened.events == [StreamEvent(data="0:-")]


async def test_the_state_the_lifespan_yields_reaches_the_request() -> None:
    plain = Lifespan(state={"k": "v"})
    opened = await open_event_stream(plain.app, URL, events=1, timeout=3.0)
    assert opened.events == [StreamEvent(data="1:v")]
