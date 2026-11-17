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
from opentelemetry.trace import Span, SpanKind, Status, StatusCode
from opentelemetry.util.types import AnyValue, Attributes

from rdf_persistence.services.generated.telemetry.rp_telemetry import LogContext

tracer = trace.get_tracer("rdf_persistence", version("rdf-persistence"))

EXCEPTION_EVENT = "exception"  # the event name the semantic conventions give a recorded exception


def _exception_type_name() -> str:
    """The attribute name of the event, read from the generated slot, not a literal (D-10).

    A function, not a constant: the generator imports this module before the slot exists.
    """
    return cast(str, LogContext.model_fields["exception_type"].alias)


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

    An exception leaving the block marks the span failed and propagates as the same object: status
    ERROR with no description, ``error.type``, and one ``exception`` event carrying only
    ``exception.type``. Never its message or traceback, which can quote tenant data (D-10); the API's
    own recording is off. A cancellation is no failure and leaves the span as it is. ``root=True``
    starts a new trace whatever span is current.
    """
    # The set slots are strings, numbers, booleans and lists of strings: valid span attributes.
    attributes = cast(Attributes, log_extra(context))
    with tracer.start_as_current_span(
        name,
        kind=kind,
        attributes=attributes,
        context=Context() if root else None,
        record_exception=False,
        set_status_on_exception=False,
    ) as span:
        try:
            yield span
        except Exception as error:
            spelling = error_type(error)
            failed = LogContext(step=context.step, error_type=spelling)
            span.set_attributes(cast(Mapping[str, AnyValue], log_extra(failed)))
            span.set_status(Status(StatusCode.ERROR))
            span.add_event(EXCEPTION_EVENT, attributes={_exception_type_name(): spelling})
            raise
