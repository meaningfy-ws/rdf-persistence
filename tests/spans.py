"""Readers of finished spans, for the tests of what never reaches telemetry (otel-observability D-10)."""

from collections.abc import Iterable

from opentelemetry.sdk.trace import ReadableSpan


def assert_no_text_in_spans(spans: Iterable[ReadableSpan], text: str) -> None:
    """Fail if `text` is in an attribute, an event's attribute or the status description of a span."""
    finished = tuple(spans)
    assert finished, "the call was traced"
    for span in finished:
        held = [*span.attributes.values(), span.status.description]
        for event in span.events:
            held += [event.name, *event.attributes.values()]
        assert not any(text in str(value) for value in held), f"span {span.name!r} holds the text"
