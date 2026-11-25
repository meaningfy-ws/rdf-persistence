"""Release memory at each test module boundary (PD-9).

A worker process runs many modules; the ``lru_cache`` of linkml-runtime's ``SchemaView`` and of
FastAPI's dependency models hold every view and app a test built (inputs/memory.md). Clearing a
cache is always safe: a later call recomputes.
"""

import ctypes
import gc
import logging
import sys
import typing
from collections.abc import Callable, Mapping
from typing import Any

from linkml_runtime.utils.schemaview import SchemaView

from rdf_persistence.core.services.generated.rp_core_services import LogContext
from rdf_persistence.core.services.telemetry import error_type, log_extra

log = logging.getLogger(__name__)

RELEASE_SWITCH = "TEST_RELEASE"
OFF = "off"


CacheCounts = dict[str, int]
"""How many caches were cleared, by library name: an index, keys ``linkml_runtime``, ``fastapi``, ``typing``."""


def _clear_typing() -> int:
    """Clear the caches of ``typing`` (its own ``_cleanups`` list, what CPython's tests use).

    ``typing.Annotated[X, Depends(kit.gate.caller)]`` is cached by value, so one entry keeps the
    last built ``ServiceKit`` alive (found in task 1.3; it is not in PD-9's list).
    """
    cleanups = getattr(typing, "_cleanups", ())
    for cleanup in cleanups:
        cleanup()
    return len(cleanups)


def _clear_each(attributes: Mapping[str, Any]) -> int:
    cleared = 0
    for value in attributes.values():
        clear = getattr(value, "cache_clear", None)
        if callable(clear):
            clear()
            cleared += 1
    return cleared


def _clear_fastapi() -> int:
    """FastAPI is an extra: without it there is nothing to clear."""
    try:
        from fastapi.dependencies import models
    except ImportError:
        return 0
    return _clear_each(vars(models))


def clear_caches() -> CacheCounts:
    """Call ``cache_clear()`` on every cached ``SchemaView`` method and FastAPI dependency function."""
    return {
        "linkml_runtime": _clear_each(vars(SchemaView)),
        "fastapi": _clear_fastapi(),
        "typing": _clear_typing(),
    }


def _trim() -> None:
    """Hand freed heap pages back to the system; glibc only, skipped quietly elsewhere."""
    if not sys.platform.startswith("linux"):
        return
    try:
        ctypes.CDLL("libc.so.6").malloc_trim(0)
    except (OSError, AttributeError):
        return


def release_memory() -> CacheCounts:
    """Clear the caches, collect garbage and trim the heap; return the caches cleared."""
    counts = clear_caches()
    gc.collect()
    _trim()
    return counts


def after_test(
    item: Any,
    nextitem: Any | None,
    *,
    clear: Callable[[], object],
    release: Callable[[], object],
    environ: Mapping[str, str],
) -> None:
    """What to run once a test is torn down: ``clear`` always, ``release`` at a module boundary.

    Nothing runs with ``TEST_RELEASE=off``. A failure is logged, never raised: it must not fail a test.
    """
    if environ.get(RELEASE_SWITCH) == OFF:
        return
    try:
        clear()
        if nextitem is None or nextitem.module is not item.module:
            release()
    except Exception as error:  # noqa: BLE001 -- releasing memory must never fail a test: logged only
        log.warning(
            "releasing memory after a test failed",
            exc_info=True,
            extra=log_extra(LogContext(step="release-test-memory", error_type=error_type(error))),
        )
