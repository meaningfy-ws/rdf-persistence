"""The one JSON-LD path (PD-6): a document to triples, triples to the dataset PyLD frames.

Bodies (``Documents``) and loaded files (``loading``) are read by ``triples_of`` and nothing else, so
they refuse the same things: a context that is not inline (PyLD fetches nothing), a second graph, a
relative IRI with no base. Each caller maps the private errors below to its own refusal.
"""

# ruff: noqa: N818  (the refusals are named for what they refuse, as in domain/exceptions.py: PD-6)

from typing import Any

from pyld import jsonld
from rdflib import RDF, XSD, BNode, Dataset, Graph, Literal, URIRef
from rdflib.term import Node

N_QUADS = "application/n-quads"  # the format PyLD writes and rdflib registers under this media type
# A reserved TLD: nothing resolves it. PyLD drops a triple whose IRI stays relative, so every
# document is read against this base and an IRI that starts with it was relative (``RelativeIriRefused``).
NO_BASE = "https://no-base.invalid/"
ABSOLUTE_IRIS = "a JSON-LD document must use absolute IRIs"  # what each caller tells its client


class NamedGraphRefused(ValueError):
    """The document puts a statement in a graph of its own; one graph is all a caller takes."""


class RemoteContextRefused(ValueError):
    """The document needs a context, remote or relative, that is not in it."""


class RelativeIriRefused(ValueError):
    """The document has an IRI that is relative and no ``@base`` to resolve it."""


def _refuse_remote(url: str, _options: Any) -> Any:
    raise RemoteContextRefused(url)


# pyld fetches nothing: every context it needs is in the document or the frame.
LOADER = {"documentLoader": _refuse_remote}


def triples_of(document: dict | list) -> Graph:
    """The triples of the JSON-LD ``document``, which must describe the default graph alone.

    Raises:
        RemoteContextRefused: A context is not inline.
        NamedGraphRefused: A statement is in a named graph.
        RelativeIriRefused: An IRI is relative and the document has no ``@base`` for it.
        Exception: PyLD or the N-Quads parser could not read the document; their own types.
    """
    try:
        nquads = jsonld.to_rdf(document, {"format": N_QUADS, "base": NO_BASE, **LOADER})
        dataset = Dataset()
        dataset.parse(data=nquads, format=N_QUADS)
    except Exception as error:  # pyld wraps what the loader raised
        refusal = _refusal_in(error)
        if refusal is not None:
            raise refusal from error
        raise
    default = dataset.default_graph
    if any(graph.identifier != default.identifier and len(graph) for graph in dataset.graphs()):
        raise NamedGraphRefused("a statement is in a named graph")
    triples = Graph()
    for triple in default:
        triples.add(triple)
    _refuse_relative(triples)
    return triples


def _refusal_in(error: BaseException) -> RemoteContextRefused | None:
    """The ``RemoteContextRefused`` somewhere in the chain of causes of ``error``, if one is."""
    seen: set[int] = set()
    link: BaseException | None = error
    while link is not None and id(link) not in seen:
        if isinstance(link, RemoteContextRefused):
            return link
        seen.add(id(link))
        link = link.__cause__ or link.__context__
    return None


def _refuse_relative(graph: Graph) -> None:
    for subject, predicate, obj in graph:
        for term in (subject, predicate, obj, getattr(obj, "datatype", None)):
            if isinstance(term, URIRef) and term.startswith(NO_BASE):
                raise RelativeIriRefused(str(term))


def dataset_of(graph: Graph) -> dict:
    """The triples of ``graph`` as the dataset ``jsonld.from_rdf`` takes.

    pyld 3.3.0 reads backslash sequences in N-Quads text wrongly (a literal of a backslash and `r`
    comes back as a backslash and a carriage return), so the text goes through rdflib instead. A
    language-tagged literal carries its ``language`` and the datatype ``rdf:langString``.
    """

    def term(node: Node) -> dict:
        if isinstance(node, URIRef):
            return {"type": "IRI", "value": str(node)}
        if isinstance(node, BNode):
            return {"type": "blank node", "value": f"_:{node}"}
        assert isinstance(node, Literal)
        if node.language:
            return {
                "type": "literal",
                "value": str(node),
                "language": node.language,
                "datatype": str(RDF.langString),
            }
        return {"type": "literal", "value": str(node), "datatype": str(node.datatype or XSD.string)}

    triples = [{"subject": term(s), "predicate": term(p), "object": term(o)} for s, p, o in graph]
    return {"@default": triples}
