"""Listings (PD-15): what a page of aggregates asks for, and the one query that reads it.

A listing is the aggregates of one type in a tenant, filtered on the type's slots (equality, or
contains for a name ending in ``~``), ordered by IRI or by one slot, and cut into a page. The
query string becomes a ``ListRequest``; against the
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

from rdf_persistence.core.domain.exceptions import BadQuery
from rdf_persistence.core.domain.generated.rp_core import DatabaseKind
from rdf_persistence.core.domain.sparql import (
    FORBIDDEN_IRI_CHARS,
    SparqlTerm,
    contains_patterns,
    count,
    fill_terms,
    join,
    match_patterns,
    no_value_patterns,
    order_by,
    term_list,
)
from rdf_persistence.iris.domain.layout import root_of_graph
from rdf_persistence.persistence.services.generated.rp_persistence_services import (
    Condition,
    Filter,
    ListPlan,
    ListRequest,
)
from rdf_persistence.schema.services import vocabulary as v
from rdf_persistence.schema.services.schema_structure import (
    holds_iri,
    holds_owned_part,
    holds_text,
    is_bookkeeping,
    is_internal,
    rdf_term,
    served_roots,
)

LIMIT, OFFSET, SORT, ABSENT = "limit", "offset", "sort", "absent"
# The largest page a listing gives: the bound the generated request model enforces.
PAGE = next(m.le for m in ListRequest.model_fields["limit"].metadata if hasattr(m, "le"))
# The furthest position a page can start at: the bound the generated request model enforces.
MAX_OFFSET = next(m.le for m in ListRequest.model_fields["offset"].metadata if hasattr(m, "le"))
RESERVED = frozenset({LIMIT, OFFSET, SORT, ABSENT})
# A parameter name ending in it asks for a contains filter on the name without it.
CONTAINS = "~"
DESCENDING = "-"
_DIGITS = re.compile(r"[0-9]+")
_SCHEME = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*:\S+")

# The aggregates of the class whose graphs are registered, that hold every filter's statement and are
# not hidden from the caller. Used by the count and by the page, which differ in what they select.
_MATCHING = """
  GRAPH $registry { ?graph $p_kind $aggregate ; $p_owned_by ?root }
  GRAPH ?graph { ?root a $target . $patterns }
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
CONSTRUCT { ?s ?p ?o . ?s $p_listed_in ?graph . $target $p_total ?total } WHERE {
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
    """The listing a query string asks for: ``limit``, ``offset``, ``sort``, ``absent``, every other parameter a filter.

    A name ending in ``~`` is a contains filter on the name without that last ``~`` (``label~=dune``);
    any other name is an equality filter. The value is taken as sent. The reserved names are compared
    before the ``~`` is stripped, so ``sort~`` is a filter on the slot ``sort``. Each ``absent`` value
    names a slot the aggregates must hold no value for (``absent=published``).

    Raises:
        BadQuery: ``limit`` is not between 1 and ``PAGE``, ``offset`` is not between 0 and
            ``MAX_OFFSET``, a number is not a whole number, or ``limit``, ``offset`` or ``sort``
            is given twice.
    """
    sent = _sent(params)
    if len(sent[SORT]) > 1:
        raise BadQuery("sort must be given once")
    filters = [
        Filter(slot=name.removesuffix(CONTAINS), value=value, contains=name.endswith(CONTAINS))
        for name, values in sent.items()
        if name not in RESERVED
        for value in values
    ] + [Filter(slot=name, value="", absent=True) for name in sent[ABSENT]]
    try:
        return ListRequest(
            **_paging(sent), sort=sent[SORT][0] if sent[SORT] else None, filters=filters or None
        )
    except ValidationError as error:
        raise BadQuery(
            f"limit is between 1 and {PAGE} and offset between 0 and {MAX_OFFSET}"
        ) from error


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


def condition_pairs(conditions: Iterable[Condition]) -> list[tuple[URIRef, URIRef | Literal]]:
    """The ``(predicate, value)`` each condition of a plan asks for: equality conditions only; use ``condition_patterns``."""
    return [(URIRef(c.predicate), _term(c)) for c in conditions]


def condition_patterns(variable: str, conditions: Iterable[Condition]) -> SparqlTerm:
    """The patterns that hold every condition of a plan on ``?variable``: the one renderer of conditions.

    An equality condition is a ``?variable <predicate> <value> .`` triple pattern; a contains condition
    is a ``FILTER EXISTS`` on a value of the predicate holding its text, ignoring case; an absent
    condition is a ``FILTER NOT EXISTS`` on a value of the predicate (``no_value_patterns``). The listing,
    ``Session.matches`` and the commit guard all render through it, so they agree.
    """
    conditions = list(conditions)
    equal = [c for c in conditions if not c.contains and not c.absent]
    containing = [(URIRef(c.predicate), Literal(c.value)) for c in conditions if c.contains]
    absent = [URIRef(c.predicate) for c in conditions if c.absent]
    parts = [
        match_patterns(variable, condition_pairs(equal)),
        contains_patterns(variable, containing),
        no_value_patterns(variable, absent),
    ]
    return join(part for part in parts if part)


class Listings:
    """Turns a ``ListRequest`` into a ``ListPlan`` against the classes of one schema."""

    def __init__(self, view: SchemaView, database: DatabaseKind = DatabaseKind.TENANT) -> None:
        self._view = view
        self._database = database
        self._slots: dict[str, Mapping[str, SlotDefinition]] = {}
        self._roots: dict[str, ClassDefinition] | None = None

    def served_root(self, name: str) -> ClassDefinition:
        """The aggregate root named ``name`` that the listings' database serves (``served_roots``).

        Raises:
            ValueError: ``name`` is not one.
        """
        if self._roots is None:
            self._roots = {root.name: root for root in served_roots(self._view, self._database)}
        if name not in self._roots:
            raise ValueError(f"{name} is not an aggregate root with a path")
        return self._roots[name]

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

    def _filtered(self, cls: ClassDefinition, filter_: Filter) -> Condition:
        """The condition of one filter: its slot resolved, its value typed (equality), kept (contains) or unread (absent).

        Raises:
            BadQuery: The slot is not listable, the filter is both contains and absent, or it fails
                as ``_contains`` or ``typed_value`` say.
        """
        slot = self._slot(cls, filter_.slot)
        if filter_.absent:
            if filter_.contains:
                raise BadQuery(f"a filter on {filter_.slot!r} cannot be both contains and absent")
            return Condition(predicate=str(self._predicate(slot)), value="", absent=True)
        if filter_.contains:
            return self._contains(cls, slot, filter_.value)
        return _condition(self._predicate(slot), typed_value(self._view, slot, filter_.value))

    def _contains(self, cls: ClassDefinition, slot: SlotDefinition, text: str) -> Condition:
        """The condition that a value of ``slot`` contains ``text``, ignoring case.

        Raises:
            BadQuery: The slot is not a string slot, or the text is empty.
        """
        name = underscore(slot.name)
        if not holds_text(self._view, slot):
            raise BadQuery(f"{cls.name} slot {name!r} is not a string; ~= takes a string slot")
        if not text:
            raise BadQuery(f"~= on {name!r} needs at least one character")
        return Condition(predicate=str(self._predicate(slot)), value=text, contains=True)

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

        An equality filter becomes a condition on the value typed by the range of its slot. A contains
        filter keeps its text as sent, to be matched against the text of a string slot.

        Raises:
            BadQuery: A filter or the sort key names a slot the type does not offer, an equality
                filter's value is not a value of its slot, or a contains filter is on a slot that is
                not a string or has no text.
        """
        conditions = [self._filtered(cls, f) for f in request.filters or []]
        sort, descending = self._sort(cls, request.sort)
        assert request.limit is not None, "ListRequest defaults"
        assert request.offset is not None, "ListRequest defaults"
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
    terms = v.listing_terms(
        registry,
        target=URIRef(plan.target),
        patterns=condition_patterns("root", plan.conditions or []),
        hidden=term_list(URIRef(graph) for graph in plan.hidden_graphs or []),
        order=order_by(*keys),
        limit=count(plan.limit),
        offset=count(plan.offset),
        sort=URIRef(plan.sort_by) if plan.sort_by is not None else None,
    )
    return fill_terms(_LISTING % (_COUNT, page), terms)


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
