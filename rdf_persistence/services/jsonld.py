"""The one JSON-LD path (PD-6): a document to triples, triples to the dataset PyLD frames.

Bodies (``Documents``) and loaded files (``loading``) are read by ``triples_of`` and nothing else, so
they refuse the same things: a context that is not inline (PyLD fetches nothing), a second graph, a
relative IRI with no base, an IRI that is not valid, a document that is no object or array. Each caller maps the private errors below to its own refusal.
"""

# ruff: noqa: N818  (the refusals are named for what they refuse, as in domain/exceptions.py: PD-6)

import re
from typing import Any

from pyld import jsonld
from rdflib import RDF, XSD, BNode, Dataset, Graph, Literal, URIRef
from rdflib.term import Node

from rdf_persistence.domain.sparql import FORBIDDEN_IRI_CHARS

N_QUADS = "application/n-quads"  # the format PyLD writes and rdflib registers under this media type
# A reserved TLD: nothing resolves it. PyLD drops a triple whose IRI stays relative, so every
# document is read against this base and an IRI that starts with it was relative (``RelativeIriRefused``).
NO_BASE = "https://no-base.invalid/"
# what each caller tells its client
ABSOLUTE_IRIS = "a JSON-LD document must use absolute IRIs"
INVALID_IRI = "a JSON-LD document holds an IRI that is not valid"
OBJECT_OR_ARRAY = "a JSON-LD document is an object or an array"
_SCHEME = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*:")
_CONTEXT, _VALUE, _JSON, _COLON = "@context", "@value", "@json", ":"


class NamedGraphRefused(ValueError):
    """The document puts a statement in a graph of its own; one graph is all a caller takes."""


class RemoteContextRefused(ValueError):
    """The document needs a context, remote or relative, that is not in it."""


class RelativeIriRefused(ValueError):
    """The document has an IRI that is relative and no ``@base`` to resolve it."""


class InvalidIriRefused(ValueError):
    """The document has an IRI with a character no IRI may hold (a space, a control character)."""


class NotADocumentRefused(ValueError):
    """The document is not a JSON object or array: a number, a boolean, a string or null."""


def _refuse_remote(url: str, _options: Any) -> Any:
    raise RemoteContextRefused(url)


# pyld fetches nothing: every context it needs is in the document or the frame.
LOADER = {"documentLoader": _refuse_remote}


def triples_of(document: dict | list) -> Graph:
    """The triples of the JSON-LD ``document``, which must describe the default graph alone.

    Raises:
        NotADocumentRefused: The document is not a JSON object or array.
        RemoteContextRefused: A context is not inline.
        NamedGraphRefused: A statement is in a named graph.
        RelativeIriRefused: An IRI is relative and the document has no ``@base`` for it.
        InvalidIriRefused: An IRI holds a character no IRI may hold.
        Exception: PyLD or the N-Quads parser could not read the document; their own types.
    """
    if not isinstance(document, dict | list):
        raise NotADocumentRefused(type(document).__name__)
    options = {"base": NO_BASE, **LOADER}
    try:
        _refuse_unreadable_iris(jsonld.expand(document, options))
        _refuse_dropped_properties(document)
        nquads = jsonld.to_rdf(document, {"format": N_QUADS, **options})
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


def _refuse_unreadable_iris(expanded: list) -> None:
    """Raise for the first IRI of the ``expanded`` document that PyLD would drop from the triples.

    PyLD's ``to_rdf`` leaves out a statement whose IRI is relative or not valid, without a word, so
    the IRIs are read where they stand in the expansion: every ``@id`` and ``@type`` value and every
    property (a key that is not a keyword); the values of ``@value`` are data. A blank node is no IRI.
    """
    pending: list[Any] = [expanded]
    while pending:
        value = pending.pop()
        if isinstance(value, list):
            pending.extend(value)
        elif isinstance(value, dict):
            for key, member in value.items():
                if not key.startswith("@"):
                    _check_iri(key)
                elif key in {"@id", "@type"}:
                    for iri in member if isinstance(member, list) else [member]:
                        _check_iri(iri)
                if key != _VALUE:
                    pending.append(member)


def _refuse_dropped_properties(document: Any) -> None:
    """Raise for a property of ``document`` written as an IRI with a character no IRI may hold.

    PyLD's expansion takes such a key for a term it does not know and drops it with its value, so the
    expansion shows nothing of it: the key is read in the document itself, outside the contexts.
    """
    pending: list[Any] = [document]
    while pending:
        value = pending.pop()
        if isinstance(value, list):
            pending.extend(value)
        elif isinstance(value, dict):
            for key, member in value.items():
                if key == _CONTEXT:
                    continue
                if _COLON in key and FORBIDDEN_IRI_CHARS.search(key):
                    raise InvalidIriRefused(key[:100])
                pending.append(member)


def _check_iri(iri: Any) -> None:
    if not isinstance(iri, str) or iri.startswith("_:") or iri == _JSON:
        return
    if iri.startswith(NO_BASE) or not _SCHEME.match(iri):
        raise RelativeIriRefused(iri)
    if FORBIDDEN_IRI_CHARS.search(iri):
        raise InvalidIriRefused(iri[:100])


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
