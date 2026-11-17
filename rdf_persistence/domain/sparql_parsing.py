"""The only place that calls rdflib's SPARQL parser, always under one lock.

rdflib's SPARQL grammar is a set of module-level pyparsing objects. pyparsing finds the arity of each
parse action on its first call, in a counter it shares between threads; two threads in that first call
overshoot it, and the action fails with ``TypeError: ... missing 1 required positional argument`` for the
rest of the process (pyparsing 3.3, ``_trim_arity``).

So every parse of SPARQL text goes through ``parse_query``, ``parse_update``, ``prepare_query`` or
``prepare_update``, which hold ``SPARQL_PARSER_LOCK`` for the parse and release it before the caller
evaluates the result. The import-linter contract ``sparql-parser-only-through-the-wrappers`` forbids every
other module of the package to import ``rdflib.plugins.sparql`` or ``pyshacl``; ``Graph.query`` and
``Graph.update`` with a string parse too, so evaluate a prepared query or update instead. The SHACL
wrappers are in ``services.shacl``, which takes the same lock.
"""

import threading
from collections.abc import Mapping

from pyparsing import ParseResults
from rdflib.namespace import Namespace
from rdflib.plugins.sparql import prepareQuery, prepareUpdate
from rdflib.plugins.sparql.parser import parseQuery, parseUpdate
from rdflib.plugins.sparql.parserutils import CompValue
from rdflib.plugins.sparql.sparql import Query, Update

SPARQL_PARSER_LOCK = threading.RLock()

__all__ = [
    "SPARQL_PARSER_LOCK",
    "CompValue",
    "parse_query",
    "parse_update",
    "prepare_query",
    "prepare_update",
]


def parse_query(text: str) -> ParseResults:
    """The parse tree of a SPARQL query, parsed under the lock."""
    with SPARQL_PARSER_LOCK:
        return parseQuery(text)


def parse_update(text: str) -> CompValue:
    """The parse tree of a SPARQL update request, parsed under the lock."""
    with SPARQL_PARSER_LOCK:
        return parseUpdate(text)


def prepare_query(text: str, init_ns: Mapping[str, Namespace | str] | None = None) -> Query:
    """A query ready to evaluate, parsed under the lock; ``init_ns`` binds prefixes the text leaves out."""
    with SPARQL_PARSER_LOCK:
        return prepareQuery(text, initNs=dict(init_ns) if init_ns else None)


def prepare_update(text: str, init_ns: Mapping[str, Namespace | str] | None = None) -> Update:
    """An update ready to evaluate, parsed under the lock; ``init_ns`` binds prefixes the text leaves out."""
    with SPARQL_PARSER_LOCK:
        return prepareUpdate(text, initNs=dict(init_ns) if init_ns else None)
