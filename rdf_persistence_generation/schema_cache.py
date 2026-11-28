"""A cache of the schemas LinkML parses, active while the generator runs (D-15).

LinkML parses every schema file again each time a ``SchemaView`` is built, and the generator
builds many views over the same import closure. For a closure that holds the technical modules
that is most of a run. Here a parsed schema is kept by the file it came from and its stat (size and
modification time), pickled, and each caller gets its own copy unpickled from it, so no view sees
another's changes. A pickle round trip costs a tenth of a parse; ``copy.deepcopy`` cost more than one.
"""

import io
import os
import pickle
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from copy import deepcopy
from typing import Any

from hbreader import Pathilizer  # type: ignore[import-untyped]  # LinkML's dependency, untyped
from linkml_runtime.linkml_model.meta import SchemaDefinition
from linkml_runtime.utils import schemaview

URL_MARK = "://"  # a source with it is fetched, not read from disk, and is never cached
Loader = Callable[..., SchemaDefinition]
Stat = tuple[int, int]  # size, modification time in nanoseconds


def _identity(text: str) -> str:
    return text


def _pathilized(text: str) -> Pathilizer:
    path = Pathilizer(text)
    path._strifier = _identity  # what hbreader sets when no relative offset is in force
    return path


class _SchemaPickler(pickle.Pickler):
    """A pickler that also takes ``hbreader.Pathilizer``, the ``source_file`` of a schema read with a
    base folder: a ``str`` that carries a lambda, which no pickle can hold."""

    def reducer_override(self, obj: object) -> Any:
        if type(obj) is Pathilizer and isinstance(obj, str):
            return _pathilized, (obj[:],)
        return NotImplemented


class SchemaLoadCache:
    """Pickled schemas by (path as given, base folder, absolute path), each with the stat it was read at.

    An index of files, not a model: the values are LinkML's own objects, pickled.
    """

    def __init__(self) -> None:
        self.entries: dict[tuple[str, str | None, str], tuple[Stat, bytes | SchemaDefinition]] = {}

    def clear(self) -> None:
        self.entries.clear()

    def loader(self, load: Loader) -> Loader:
        """``load`` with its results kept; a file or URL the stat cannot tell apart is parsed every time."""

        def cached(path: str, **kwargs: str | None) -> SchemaDefinition:
            key = self._key(path, kwargs)
            stat = self._stat(key[2]) if key else None
            if key is None or stat is None:
                return load(path, **kwargs)
            hit = self.entries.get(key)
            if hit is not None and hit[0] == stat:
                return self._copy(hit[1])
            schema = load(path, **kwargs)
            self.entries[key] = (stat, self._freeze(schema))
            return schema

        return cached

    @staticmethod
    def _freeze(schema: SchemaDefinition) -> bytes | SchemaDefinition:
        """The schema as pickled bytes; one LinkML cannot pickle in spite of ``_SchemaPickler`` as a copy."""
        buffer = io.BytesIO()
        try:
            _SchemaPickler(buffer, protocol=pickle.HIGHEST_PROTOCOL).dump(schema)
        except (AttributeError, TypeError, pickle.PicklingError):
            return deepcopy(schema)
        return buffer.getvalue()

    @staticmethod
    def _copy(frozen: bytes | SchemaDefinition) -> SchemaDefinition:
        if isinstance(frozen, bytes):
            return pickle.loads(frozen)  # bytes this process pickled itself
        return deepcopy(frozen)

    @staticmethod
    def _key(path: str, kwargs: dict[str, str | None]) -> tuple[str, str | None, str] | None:
        base_dir = kwargs.get("base_dir")
        if set(kwargs) - {"base_dir"} or URL_MARK in f"{path}{base_dir or ''}":
            return None
        return str(path), base_dir, os.path.abspath(os.path.join(base_dir or "", str(path)))

    @staticmethod
    def _stat(path: str) -> Stat | None:
        try:
            status = os.stat(path)
        except OSError:
            return None
        return status.st_size, status.st_mtime_ns


PROCESS_CACHE = SchemaLoadCache()
_depth = 0  # the blocks open now; the outermost one ends a run


@contextmanager
def cached_schema_loads(
    cache: SchemaLoadCache = PROCESS_CACHE, *, load: Loader | None = None
) -> Iterator[None]:
    """Serve LinkML's schema loads from ``cache`` inside the block; put the stock loader back after.

    ``load`` is the parse behind the cache (LinkML's own by default); tests give a counting one.
    The default cache lives for one run: it is cleared when the outermost block exits, so a stale
    parse (an edit the stat cannot tell, a same-size one in the same clock tick) never reaches a later run.
    """
    global _depth
    stock = schemaview.load_schema_wrap
    # ponytail: ceiling = LinkML offers no hook for how a SchemaView parses an import, and its
    # stock generators build views of their own, so the one module-level name is replaced for the
    # block; upstream issue to file: SchemaView re-parses every import on each construction.
    schemaview.load_schema_wrap = cache.loader(load or stock)
    _depth += 1
    try:
        yield
    finally:
        _depth -= 1
        schemaview.load_schema_wrap = stock
        if cache is PROCESS_CACHE and _depth == 0:
            cache.clear()
