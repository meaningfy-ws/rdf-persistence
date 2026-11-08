"""The mapper between generated objects and the graph of an aggregate, and the object-level unit of
work (PD-7a, PD-8a, PD-10, PD-12 D-2).

Domain services work on the generated classes; the router works on whole graphs and frames. The
mapper serves the first: ``to_graph`` writes an aggregate root and its owned parts as triples,
``from_graph`` builds the object back, nesting owned parts whether their nodes are IRIs or skolem
IRIs. It is driven by ``SchemaView`` and writes rdflib terms directly, not through linkml's
``rdflib_dumper``/``rdflib_loader``: those take linkml's own dataclass classes, not the generated
pydantic ones, and they fail on a slot that ranges over a class but holds an IRI string
(``Grant.assignee``). Predicates and types are those of the generated context, which a test checks.

What a value becomes: an owned part, a node; a class-ranged slot that is not owned, or a ``uri``
slot, the IRI; an enum value, its meaning IRI when it has one; anything else, a literal. Internal
slots are written (the toolkit persists them). The tracking slots (``bookkeeping``) are never
written: the session writes them as statements about the graph IRI, and ``from_graph`` reads them
from there.

Shortcut: an owned part is read as the slot's range class, so a subclass comes back as its parent;
upgrade when a schema owns a hierarchy. A ``uri`` value is taken as an absolute IRI; CURIEs are not
expanded.
"""

import importlib
import pkgutil
from collections.abc import Iterable
from types import ModuleType
from typing import Any, cast

from linkml_runtime.linkml_model.meta import SlotDefinition
from linkml_runtime.utils.formatutils import camelcase, underscore
from linkml_runtime.utils.schemaview import SchemaView
from pydantic import BaseModel
from rdflib import RDF, BNode, Graph, Literal, URIRef
from rdflib.term import Node

from rdf_persistence.domain.base import RpModel
from rdf_persistence.domain.iris import DEFAULT_IRIS, Iris
from rdf_persistence.domain.sparql import Triple
from rdf_persistence.services.schema_structure import (
    aggregate_roots,
    holds_iri,
    holds_owned_part,
    is_bookkeeping,
    is_tenant_root,
    kebab_case,
    rdf_term,
)
from rdf_persistence.services.session import Session


class GeneratedModels:
    """The generated classes of some modules, found by the name of the schema class they come from."""

    def __init__(self, modules: Iterable[ModuleType]) -> None:
        self._by_name = {
            name: member
            for module in modules
            for name, member in vars(module).items()
            if isinstance(member, type)
            and issubclass(member, RpModel)
            and member.__module__ == module.__name__
        }

    def classes(self) -> dict[str, type[RpModel]]:
        """Every class, by its name in the generated module."""
        return dict(self._by_name)

    def named(self, schema_name: str) -> type[RpModel]:
        """The generated class of the schema class ``schema_name``; ``LookupError`` if there is none."""
        try:
            return self._by_name[camelcase(schema_name)]
        except KeyError:
            raise LookupError(f"no generated class for {schema_name}") from None


def generated_models(*modules: ModuleType) -> GeneratedModels:
    """The generated classes of ``modules``, for ``Mapper``."""
    return GeneratedModels(modules)


def generated_models_of(package: ModuleType, *modules: ModuleType) -> GeneratedModels:
    """The generated classes of every module of ``package``, and of ``modules``, for ``Mapper``."""
    found = [
        importlib.import_module(f"{package.__name__}.{info.name}")
        for info in pkgutil.iter_modules(package.__path__)
    ]
    return GeneratedModels([*found, *modules])


def new_part[M: BaseModel](
    cls: type[M], root_iri: str, *, iris: Iris = DEFAULT_IRIS, tenant: str = "", **fields: Any
) -> M:
    """A part of the aggregate rooted at ``root_iri``, with an IRI minted by ``iris`` (default
    policy: ``{root}/parts/{uuid4}``); ``tenant`` is the tenant the aggregate is in (PD-3).

    Shortcut: the ``{type}`` is the kebab-case name of ``cls``; the generated class does not carry an
    ``rp_iri_type``. A policy that needs ``{type}`` refuses a class whose type differs (``InvalidIri``).

    A part whose class is ``Described`` has a required ``id``, so it cannot be built without one;
    domain code builds it here, and the IRI is kept across commits because it is the node's IRI in
    the graph. (Minting inside ``add`` is impossible: the object does not exist before it has an id.)
    """
    minted = iris.mint_part(tenant, root_iri, kebab_case(cls.__name__))
    return cls(id=str(minted), **fields)


class Mapper:
    """Maps the generated classes of a schema to and from the triples of an aggregate.

    It keeps no model of its own (PD-24): it reads each class and slot from ``SchemaView`` as it
    goes, remembering only the induced slots of a class and their predicates.
    """

    def __init__(self, view: SchemaView, models: GeneratedModels) -> None:
        self.view = view
        self._models = models
        self._schema_names = {camelcase(name): name for name in view.all_classes()}
        self._slots: dict[str, list[tuple[SlotDefinition, URIRef]]] = {}
        classes = list(view.all_classes().values())
        self._roots = {c.name for c in aggregate_roots(view, classes)} | {
            c.name for c in classes if is_tenant_root(c)
        }

    def is_root(self, cls: type[BaseModel]) -> bool:
        """True for an aggregate root or the tenant root: what a session stores as a graph."""
        return self._schema_names.get(cls.__name__) in self._roots

    # -- writing -----------------------------------------------------------------------------

    def to_triples(self, obj: BaseModel) -> Iterable[Triple]:
        """The triples of ``obj`` and its owned parts: what ``Session`` takes, without tracking."""
        # rdflib types a graph's terms as Node; the mapper writes only URIs, literals and blank nodes
        return cast(Iterable[Triple], self.to_graph(obj))

    def to_graph(self, obj: BaseModel) -> Graph:
        """The triples of ``obj`` and its owned parts, without the tracking statements."""
        graph = Graph()
        self._write(obj, URIRef(getattr(obj, "id")), graph)  # noqa: B009 - a root always has an id
        return graph

    def _write(self, obj: BaseModel, subject: Node, graph: Graph) -> None:
        name = self._schema_names[type(obj).__name__]
        graph.add((subject, RDF.type, URIRef(self.view.get_uri(name, expand=True))))
        for slot, predicate in self._slots_of(name):
            if is_bookkeeping(slot):
                continue
            for value in _listed(getattr(obj, underscore(slot.name))):
                graph.add((subject, predicate, self._term(slot, value, graph)))

    def _term(self, slot: SlotDefinition, value: Any, graph: Graph) -> Node:
        if holds_owned_part(self.view, slot):
            return self._write_part(value, graph)
        if isinstance(value, BaseModel):
            raise ValueError(f"slot {slot.name} holds an object but is not owned: give its IRI")
        return rdf_term(self.view, slot, value)

    def _write_part(self, part: BaseModel, graph: Graph) -> Node:
        identifier = self._identifier(self._schema_names[type(part).__name__])
        node = URIRef(getattr(part, identifier)) if identifier else BNode()
        self._write(part, node, graph)
        return node

    # -- reading -----------------------------------------------------------------------------

    def from_graph[M: BaseModel](
        self, cls: type[M], iri: str, graph: Graph, graph_iri: URIRef
    ) -> M:
        """The object of class ``cls`` rooted at ``iri``, owned parts nested.

        The tracking slots are read from the statements about ``graph_iri`` (PD-7): the graph IRI
        ``Session.get_graph`` returns with the aggregate.

        Raises:
            ValueError: ``graph`` has no statement about ``iri``, or its owned parts form a cycle.
        """
        root = URIRef(iri)
        if (root, None, None) not in graph:
            raise ValueError(f"the graph has no statements about {iri}")
        return self._read(cls, root, graph, graph_iri, frozenset())

    def _read[M: BaseModel](
        self, cls: type[M], node: Node, graph: Graph, tracked_by: URIRef | None, path: frozenset
    ) -> M:
        if node in path:
            raise ValueError(f"the owned parts of the graph form a cycle at {node}")
        path = path | {node}
        name = self._schema_names[cls.__name__]
        data: dict[str, Any] = {}
        if identifier := self._identifier(name):
            if isinstance(node, BNode):
                raise ValueError(f"a {cls.__name__} needs an IRI, found a blank node")
            data[identifier] = str(node)
        for slot, predicate in self._slots_of(name):
            subject = tracked_by if is_bookkeeping(slot) else node
            if subject is None:
                continue
            found = [
                self._value(slot, o, graph, path)
                for o in sorted(graph.objects(subject, predicate), key=str)
            ]
            if found:
                data[underscore(slot.name)] = found if slot.multivalued else found[0]
        return cls.model_validate(data)

    def _value(self, slot: SlotDefinition, term: Node, graph: Graph, path: frozenset) -> Any:
        if holds_owned_part(self.view, slot):
            return self._read(self._model(slot.range), term, graph, None, path)
        if self._is_enum(slot):
            return self._enum_text(slot.range, term)
        if isinstance(term, Literal) and not holds_iri(self.view, slot):
            return term.toPython()
        return str(term)

    # -- the schema --------------------------------------------------------------------------

    def _model(self, schema_name: str) -> type[RpModel]:
        return self._models.named(schema_name)

    def _identifier(self, name: str) -> str | None:
        slot = self.view.get_identifier_slot(name, use_key=False)
        return underscore(slot.name) if slot else None

    def _slots_of(self, name: str) -> list[tuple[SlotDefinition, URIRef]]:
        """The induced slots of a class other than its identifier, each with its predicate."""
        if name not in self._slots:
            self._slots[name] = [
                (slot, URIRef(self.view.get_uri(slot, expand=True)))
                for slot in self.view.class_induced_slots(name)
                if not slot.identifier
            ]
        return self._slots[name]

    def _is_enum(self, slot: SlotDefinition) -> bool:
        return slot.range in self.view.all_enums()

    def _meaning(self, enum: str, text: str) -> URIRef | None:
        meaning = self.view.get_enum(enum).permissible_values[text].meaning
        return URIRef(self.view.expand_curie(meaning)) if meaning else None

    def _enum_text(self, enum: str, term: Node) -> str:
        for text in self.view.get_enum(enum).permissible_values:
            if self._meaning(enum, text) == term:
                return str(text)
        return str(term)


def _listed(value: Any) -> Iterable[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


class UnitOfWork:
    """Object-level access to one session: ``get`` roots, ``add`` new or changed ones, ``commit``.

    A root read twice is the same object, so edits cannot race with themselves. ``commit`` writes
    each changed aggregate with the version it read (``replace_graph``), or as new (``add_graph``);
    ``Conflict`` propagates from the first aggregate that changed meanwhile. Each aggregate is
    committed atomically, the set of them is not: those committed before the conflict stay done.
    The held objects keep the tracking they were read with; ``get`` again from a new unit of work
    for the fresh values.
    """

    def __init__(self, session: Session, mapper: Mapper) -> None:
        self._session = session
        self._mapper = mapper
        self._objects: dict[str, BaseModel] = {}
        self._versions: dict[str, str] = {}  # of the roots that are stored
        self._dirty: set[str] = set()

    async def get[M: BaseModel](self, cls: type[M], iri: str) -> M:
        """The root ``iri`` as an object of ``cls``.

        Raises:
            NotFound: The aggregate has no graph.
            TypeError: The root was already read as another class.
        """
        if iri not in self._objects:
            graph, graph_iri, version = await self._session.get_graph(iri)
            self._objects[iri] = self._mapper.from_graph(cls, iri, graph, graph_iri)
            self._versions[iri] = version
        obj = self._objects[iri]
        if not isinstance(obj, cls):
            raise TypeError(f"{iri} was read as {type(obj).__name__}, not {cls.__name__}")
        return obj

    def add(self, obj: BaseModel) -> None:
        """Take a new root, or a changed one read here, to be written by the next ``commit``.

        Raises:
            ValueError: ``obj`` is not an aggregate root or the tenant root.
        """
        if not self._mapper.is_root(type(obj)):
            raise ValueError(f"{type(obj).__name__} is not an aggregate root")
        iri = str(getattr(obj, "id"))  # noqa: B009
        self._objects[iri] = obj
        self._dirty.add(iri)

    async def commit(self) -> None:
        """Write every added root.

        Raises:
            Conflict: A new root already exists, or a read one changed since it was read.
        """
        for iri in [i for i in self._objects if i in self._dirty]:
            triples = self._mapper.to_triples(self._objects[iri])
            if iri in self._versions:
                self._versions[iri] = await self._session.replace_graph(
                    iri, triples, self._versions[iri]
                )
            else:
                self._versions[iri] = await self._session.add_graph(iri, triples)
            self._dirty.discard(iri)
