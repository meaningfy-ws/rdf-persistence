"""The helpers of the toolkit's logging style: one `LogContext` per log call (otel-observability PD-3).

A log call passes `extra=log_extra(LogContext(step=...))`; the context is generated from the LinkML
schema, so a record names its data as the spans of the same step do.
"""

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from importlib.metadata import version
from typing import cast

from opentelemetry import trace
from opentelemetry.context import Context
from opentelemetry.trace import Span, SpanKind
from opentelemetry.util.types import AnyValue, Attributes

from rdf_persistence.services.generated.telemetry.rp_telemetry import LogContext

tracer = trace.get_tracer("rdf_persistence", version("rdf-persistence"))


def log_extra(context: LogContext) -> dict[str, object]:
    """The `extra=` of a log call: the slots that are set, under their attribute names.

    `by_alias` is explicit, so it does not rest on the base class's `serialize_by_alias`.
    """
    return context.model_dump(by_alias=True, exclude_none=True)


def error_type(error: BaseException) -> str:
    """The one spelling of `error.type` for an exception, in records and spans alike."""
    return f"{type(error).__module__}.{type(error).__qualname__}"


@contextmanager
def traced(
    name: str, context: LogContext, *, kind: SpanKind = SpanKind.INTERNAL, root: bool = False
) -> Iterator[Span]:
    """A span named ``name`` around the block, its attributes the set slots of ``context``.

    An exception leaving the block is recorded by the API (an ``exception`` event, status ERROR),
    gets ``error.type`` too, and propagates as the same object. ``root=True`` starts a new trace
    whatever span is current.
    """
    # The set slots are strings, numbers, booleans and lists of strings: valid span attributes.
    attributes = cast(Attributes, log_extra(context))
    with tracer.start_as_current_span(
        name, kind=kind, attributes=attributes, context=Context() if root else None
    ) as span:
        try:
            yield span
        except BaseException as error:
            failed = LogContext(step=context.step, error_type=error_type(error))
            span.set_attributes(cast(Mapping[str, AnyValue], log_extra(failed)))
            raise
