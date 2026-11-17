"""The helpers of the toolkit's logging style: one `LogContext` per log call (otel-observability PD-3).

A log call passes `extra=log_extra(LogContext(step=...))`; the context is generated from the LinkML
schema, so a record names its data as the spans of the same step do.
"""

from rdf_persistence.services.generated.telemetry.rp_telemetry import LogContext


def log_extra(context: LogContext) -> dict[str, object]:
    """The `extra=` of a log call: the slots that are set, under their attribute names.

    `by_alias` is explicit, so it does not rest on the base class's `serialize_by_alias`.
    """
    return context.model_dump(by_alias=True, exclude_none=True)


def error_type(error: BaseException) -> str:
    """The one spelling of `error.type` for an exception, in records and spans alike."""
    return f"{type(error).__module__}.{type(error).__qualname__}"
