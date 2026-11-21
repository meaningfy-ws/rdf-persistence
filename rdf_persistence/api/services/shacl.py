"""The only place that calls pyshacl, which parses SPARQL with rdflib on the way.

pyshacl runs SPARQL of its own: the queries of the shapes (``sh:sparql``, ``sh:select``) and the ones it
builds from a shape (``sh:closed``, ``sh:equals``, the focus nodes of a class). Each goes through rdflib's
parser, whose parse actions are not safe to run for the first time in two threads at once
(``domain.sparql_parsing``). Two ways to validate, by who knows the shapes:

* ``validate_locked`` for shapes nobody warmed up (any shapes a test brings): the whole validation holds
  the lock.
* ``warm_up`` once for a fixed set of shapes, under the lock, then ``validate_warm`` as often and as
  concurrently as needed, without it.

Why the second is safe: the race is only on the first call of a parse action. ``warm_up`` validates two
instances of every target class of the shapes, so each shape runs its queries once, and every query is
one of a fixed set of templates filled in from the shapes (the focus nodes, the ignored properties, the
paths), parsed by the same grammar elements for any data. Validating other data later calls no parse
action for the first time. What this does not cover is a shape that targets nothing a class names
(``sh:targetNode``, ``sh:targetSubjectsOf``, a SPARQL target): warm those with ``validate_locked``.
"""

from pyshacl import validate
from rdflib import RDF, SH, Graph, URIRef
from rdflib.namespace import Namespace

from rdf_persistence.core.domain import sparql_parsing

_WARM = Namespace("urn:rdf-persistence:warm-up:")
_INSTANCES = 2  # one focus node and several take different paths through the generated queries

Validation = tuple[bool, Graph, str]

# The digests of the shapes warmed in this process (``warm_up_once``).
_WARMED_SHAPES: set[str] = set()


def _validate(data: Graph, shapes: Graph) -> Validation:
    conforms, report, text = validate(data, shacl_graph=shapes, inference="none")
    assert isinstance(report, Graph)
    return bool(conforms), report, str(text)


def validate_locked(data: Graph, shapes: Graph) -> Validation:
    """Validate ``data`` against ``shapes``, holding the parser lock for the whole validation.

    Returns ``(conforms, report graph, report text)``. ``shapes`` is added to, so pass a copy.
    """
    with sparql_parsing.SPARQL_PARSER_LOCK:
        return _validate(data, shapes)


def warm_up(shapes: Graph) -> None:
    """Parse every query that validating against ``shapes`` runs, once, under the lock."""
    data = Graph()
    for target in set(shapes.objects(None, SH.targetClass)):
        if isinstance(target, URIRef):
            for number in range(_INSTANCES):
                data.add((_WARM[f"{len(data)}-{number}"], RDF.type, target))
    scratch = Graph()
    scratch += shapes  # pyshacl adds to the shapes graph it is given
    validate_locked(data, scratch)


def warm_up_once(shapes: Graph, digest: str) -> None:
    """Warm ``shapes`` up unless this process has warmed shapes of the same digest: the warm-up's effect
    is process-wide. Read without the lock (a set lookup); decided again under it.

    The digest must be that of the bytes the shapes were parsed from (the caller's contract): a wrong
    digest that was already warmed skips the warm-up ``validate_warm`` relies on.
    """
    if digest in _WARMED_SHAPES:
        return
    with sparql_parsing.SPARQL_PARSER_LOCK:
        if digest not in _WARMED_SHAPES:
            warm_up(shapes)
            _WARMED_SHAPES.add(digest)


def validate_warm(data: Graph, shapes: Graph) -> Validation:
    """Validate ``data`` against ``shapes`` that ``warm_up`` has seen, without the parser lock.

    Returns ``(conforms, report graph, report text)``. ``shapes`` is added to, so pass a copy.
    """
    return _validate(data, shapes)
