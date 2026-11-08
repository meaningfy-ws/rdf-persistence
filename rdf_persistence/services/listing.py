"""Listings (PD-15): what a page of aggregates asks for, and the one query that reads it.

A listing is the aggregates of one type in a tenant, filtered by equality on the type's slots, ordered
by IRI or by one slot, and cut into a page. The query string becomes a ``ListRequest``; against the
type's slots it becomes a ``ListPlan`` of typed terms (a filter value is typed by the range of its
slot, never pasted into the query as text); the plan becomes one ``CONSTRUCT`` that returns the
triples of the page's aggregates and the size of the whole listing.
"""

import re
from collections import defaultdict
from collections.abc import Iterable, Mapping

from linkml_runtime.linkml_model.meta import ClassDefinition, SlotDefinition
from linkml_runtime.utils.formatutils import underscore
from linkml_runtime.utils.schemaview import SchemaView
from pydantic import ValidationError
from rdflib import Graph, Literal, URIRef

from rdf_persistence.domain.exceptions import BadQuery
from rdf_persistence.domain.generated.rp_core import RegistryKind
from rdf_persistence.domain.generated.service.rp_service import (
    Condition,
    Filter,
    ListPlan,
    ListRequest,
)
from rdf_persistence.domain.iris import root_of_graph
from rdf_persistence.domain.sparql import (
    FORBIDDEN_IRI_CHARS,
    count,
    fill,
    match_patterns,
    order_by,
    term,
    term_list,
)
from rdf_persistence.services import vocabulary as v
from rdf_persistence.services.schema_structure import (
    holds_iri,
    holds_owned_part,
    is_bookkeeping,
    is_internal,
    rdf_term,
)

LIMIT, OFFSET, SORT = "limit", "offset", "sort"
RESERVED = frozenset({LIMIT, OFFSET, SORT})
DESCENDING = "-"
_DIGITS = re.compile(r"[0-9]+")
_SCHEME = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*:\S+")

# The aggregates of the class whose graphs are registered, that hold every filter's statement and are
# not hidden from the caller. Used by the count and by the page, which differ in what they select.
_MATCHING = """
  GRAPH $registry { ?graph $p_kind $aggregate ; $p_owned_by ?root }
  GRAPH ?graph { ?root a $class . $patterns }
  FILTER (?graph NOT IN ($hidden))
"""
_COUNT = "SELECT (COUNT(DISTINCT ?root) AS ?total) WHERE { " + _MATCHING + " }"
_PAGE_BY_IRI = (
    "SELECT ?root ?graph WHERE { " + _MATCHING + " } ORDER BY $order LIMIT $limit OFFSET $offset"
)
# A slot may hold several values: an aggregate sorts by the smallest of them.
_PAGE_BY_SLOT = (
    "SELECT ?root ?graph (MIN(?value) AS ?key) WHERE { "
    + _MATCHING
    + " OPTIONAL { GRAPH ?graph { ?root $p_sort ?value } } }"
    + " GROUP BY ?root ?graph ORDER BY $order LIMIT $limit OFFSET $offset"
)
_LISTING = """
CONSTRUCT { ?s ?p ?o . ?s $p_listed_in ?graph . $class $p_total ?total } WHERE {
  { %s }
  UNION
  { { %s } GRAPH ?graph { ?s ?p ?o } }
}
"""


def _number(name: str, values: list[str]) -> int | None:
    """The one non-negative whole number a parameter holds, or None when it is not sent."""
    if not values:
        return None
    if len(values) > 1 or not _DIGITS.fullmatch(values[0]):
        raise BadQuery(f"{name} must be given once, as a whole number")
    return int(values[0])


def _sent(params: Iterable[tuple[str, str]]) -> defaultdict[str, list[str]]:
    sent: defaultdict[str, list[str]] = defaultdict(list)
    for name, value in params:
        sent[name].append(value)
    return sent


def _paging(sent: Mapping[str, list[str]]) -> dict[str, int]:
    """The ``limit`` and ``offset`` that were sent, as whole numbers."""
    numbers = {name: _number(name, sent.get(name, [])) for name in (LIMIT, OFFSET)}
    return {name: number for name, number in numbers.items() if number is not None}


def list_request(params: Iterable[tuple[str, str]]) -> ListRequest:
    """The listing a query string asks for: ``limit``, ``offset``, ``sort``, every other parameter a filter.

    Raises:
        BadQuery: ``limit`` is not between 1 and 200, ``offset`` is negative, a number is not a whole
            number, or ``limit``, ``offset`` or ``sort`` is given twice.
    """
    sent = _sent(params)
    if len(sent[SORT]) > 1:
        raise BadQuery("sort must be given once")
    filters = [
        Filter(slot=name, value=value)
        for name, values in sent.items()
        if name not in RESERVED
        for value in values
    ]
    try:
        return ListRequest(
            **_paging(sent), sort=sent[SORT][0] if sent[SORT] else None, filters=filters or None
        )
    except ValidationError as error:
        raise BadQuery("limit is between 1 and 200 and offset is not negative") from error


def listable_slots(view: SchemaView, cls: ClassDefinition) -> dict[str, SlotDefinition]:
    """The slots of ``cls`` a listing may filter or sort on, by name.

    Not the identifier (the IRI orders by itself), not the bookkeeping and ``internal`` slots, not
    the parts the aggregate owns, and not a slot named like a paging parameter.
    """
    return {
        underscore(slot.name): slot
        for slot in view.class_induced_slots(cls.name)
        if not (
            slot.identifier
            or is_internal(slot)
            or is_bookkeeping(slot)
            or holds_owned_part(view, slot)
            or underscore(slot.name) in RESERVED
        )
    }


def sort_keys(view: SchemaView, cls: ClassDefinition) -> list[str]:
    """The keys a listing of ``cls`` may be ordered by, ascending then descending: the identifier and the listable slots."""
    identifier = view.get_identifier_slot(cls.name)
    names = [
        *([underscore(identifier.name)] if identifier else []),
        *sorted(listable_slots(view, cls)),
    ]
    return [*names, *(f"{DESCENDING}{name}" for name in names)]


def typed_value(view: SchemaView, slot: SlotDefinition, text: str) -> URIRef | Literal:
    """``text`` as a value of the slot, the way the store holds it (``rdf_term``).

    Raises:
        BadQuery: The text is not a value of the slot's range.
    """
    range_ = slot.range or str(view.schema.default_range)
    is_enum = range_ in view.all_enums()
    if (
        not is_enum
        and holds_iri(view, slot)
        and (not _SCHEME.fullmatch(text) or FORBIDDEN_IRI_CHARS.search(text))
    ):
        raise BadQuery(f"{text!r} is not an IRI")
    try:
        term = rdf_term(view, slot, text)
    except ValueError as error:
        raise BadQuery(str(error)) from error
    if isinstance(term, Literal) and term.ill_typed and not is_enum:
        raise BadQuery(f"{text!r} is not a {range_}")
    return term


def _condition(predicate: URIRef, value: URIRef | Literal) -> Condition:
    """The condition that the aggregate has ``predicate`` with ``value``, as the plan keeps it."""
    if isinstance(value, URIRef):
        return Condition(predicate=str(predicate), value=str(value), reference=True)
    datatype = str(value.datatype) if value.datatype else None
    return Condition(predicate=str(predicate), value=str(value), datatype=datatype)


def _term(condition: Condition) -> URIRef | Literal:
    if condition.reference:
        return URIRef(condition.value)
    return Literal(
        condition.value, datatype=URIRef(condition.datatype) if condition.datatype else None
    )


class Listings:
    """Turns a ``ListRequest`` into a ``ListPlan`` against the classes of one schema."""

    def __init__(self, view: SchemaView) -> None:
        self._view = view
        self._slots: dict[str, Mapping[str, SlotDefinition]] = {}

    def _listable(self, cls: ClassDefinition) -> Mapping[str, SlotDefinition]:
        if cls.name not in self._slots:
            self._slots[cls.name] = listable_slots(self._view, cls)
        return self._slots[cls.name]

    def _predicate(self, slot: SlotDefinition) -> URIRef:
        return URIRef(self._view.get_uri(slot, expand=True))

    def _slot(self, cls: ClassDefinition, name: str) -> SlotDefinition:
        slot = self._listable(cls).get(name)
        if slot is None:
            raise BadQuery(f"{cls.name} has no slot {name!r} to filter or sort on")
        return slot

    def _sort(self, cls: ClassDefinition, key: str | None) -> tuple[URIRef | None, bool]:
        if key is None:
            return None, False
        descending = key.startswith(DESCENDING)
        name = key.removeprefix(DESCENDING)
        identifier = self._view.get_identifier_slot(cls.name)
        if identifier is not None and name == underscore(identifier.name):
            return None, descending
        return self._predicate(self._slot(cls, name)), descending

    def plan(
        self, cls: ClassDefinition, request: ListRequest, hidden: Iterable[str] = ()
    ) -> ListPlan:
        """The plan of ``request`` for the aggregates of ``cls``, leaving out the ``hidden`` graphs.

        Raises:
            BadQuery: A filter or the sort key names a slot the type does not offer, or a filter's
                value is not a value of its slot.
        """
        conditions = [
            _condition(self._predicate(slot), typed_value(self._view, slot, f.value))
            for f in request.filters or []
            for slot in [self._slot(cls, f.slot)]
        ]
        sort, descending = self._sort(cls, request.sort)
        assert request.limit is not None and request.offset is not None, "ListRequest defaults"
        return ListPlan(
            target=self._view.get_uri(cls, expand=True),
            conditions=conditions or None,
            sort_by=str(sort) if sort else None,
            descending=descending,
            limit=request.limit,
            offset=request.offset,
            hidden_graphs=[str(graph) for graph in hidden] or None,
        )


def listing_query(registry: URIRef, plan: ListPlan) -> str:
    """The query for ``plan`` over the tenant's registry graph ``registry``."""
    by_slot = plan.sort_by is not None
    descending = bool(plan.descending)
    page = _PAGE_BY_SLOT if by_slot else _PAGE_BY_IRI
    keys = (("key", descending), ("root", False)) if by_slot else (("root", descending),)
    terms = {"p_sort": term(URIRef(plan.sort_by))} if plan.sort_by is not None else {}
    pairs = ((URIRef(c.predicate), _term(c)) for c in plan.conditions or [])
    return fill(
        _LISTING % (_COUNT, page),
        **terms,
        registry=term(registry),
        p_kind=term(v.REGISTRY_KIND),
        p_owned_by=term(v.REGISTRY_OWNED_BY),
        aggregate=term(v.REGISTRY_KIND_IRIS[RegistryKind.AGGREGATE]),
        **{"class": term(URIRef(plan.target))},
        patterns=match_patterns("root", pairs),
        hidden=term_list(URIRef(graph) for graph in plan.hidden_graphs or []),
        p_listed_in=term(v.LISTED_IN),
        p_total=term(v.TOTAL),
        order=order_by(*keys),
        limit=count(plan.limit),
        offset=count(plan.offset),
    )


def total_of(answer: Graph, plan: ListPlan) -> int:
    """The size of the whole listing, which the query states about the listed class."""
    total = answer.value(URIRef(plan.target), v.TOTAL)
    assert total is not None, "the listing query always answers the total"
    assert isinstance(total, Literal), "the total is a literal"
    return int(total.toPython())


def _order_key(graph: Graph, root: URIRef, sort: URIRef) -> tuple:
    """The key an aggregate sorts by: its smallest value of the sort slot; none sorts first."""
    values = [o.toPython() if isinstance(o, Literal) else str(o) for o in graph.objects(root, sort)]
    return (1, min(values)) if values else (0,)


def _by_listed_graph(answer: Graph) -> defaultdict[str, Graph]:
    """The answer's triples by the root of the graph their subject was listed in, without ``listedIn``."""
    parts: defaultdict[str, Graph] = defaultdict(Graph)
    listed_in = {s: g for s, _, g in answer.triples((None, v.LISTED_IN, None))}
    for s, p, o in answer:
        if p != v.LISTED_IN and s in listed_in:
            parts[str(root_of_graph(str(listed_in[s])))].add((s, p, o))
    return parts


def items_of(answer: Graph, plan: ListPlan) -> list[tuple[URIRef, Graph]]:
    """The aggregates of the page with their triples, in the order of the listing.

    The query selects the page but returns triples, which carry no order, so the order is rebuilt:
    by IRI, then by the sort slot's smallest value with the IRI breaking ties. Each item is the
    aggregate's root and its triples, the statements about its graph included. A triple belongs to
    the aggregate whose graph the query found its subject in (``listedIn``, PD-7), whatever the
    subject's IRI looks like.
    """
    roots = {
        str(root_of_graph(s)) for s, p, _ in answer if p == v.VERSION and isinstance(s, URIRef)
    }
    parts = _by_listed_graph(answer)
    sort = URIRef(plan.sort_by) if plan.sort_by else None
    descending = bool(plan.descending)
    ordered = sorted(roots, reverse=descending and sort is None)
    if sort is not None:
        ordered.sort(key=lambda root: _order_key(answer, URIRef(root), sort), reverse=descending)
    return [(URIRef(root), parts[root]) for root in ordered]
