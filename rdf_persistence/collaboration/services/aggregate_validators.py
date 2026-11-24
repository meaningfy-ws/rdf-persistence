"""Aggregate validators: a consumer's rules on the write of a root (aggregate-validators PD-1 to PD-3, PD-7).

A rule is registered for a class of the consumer's schema and runs on every guarded add and replace of a
root of that class or of a class derived from it. It refuses by raising ``InvalidBody``; it may be async and
may ask the reader for the classes of the aggregates the root names. ``AggregateValidators`` checks the keys
once, at start-up, and answers which rules apply to a root.

Delete rules (aggregate-guards D-5 to D-8) are keyed the same way and run, as ``(old, principal, reader)``,
on every removal of a root through a transaction; they refuse by raising ``Conflict``.
"""

import inspect
from collections.abc import Awaitable, Callable, Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any, Protocol

from linkml_runtime.utils.schemaview import SchemaView
from pydantic import BaseModel, ValidationError
from rdflib import RDF, Graph, URIRef

from rdf_persistence.core.domain.exceptions import (
    Conflict,
    DatabaseGone,
    InvalidBody,
    NotFound,
    StoreUnavailable,
)
from rdf_persistence.core.domain.generated.rp_core import Principal
from rdf_persistence.core.domain.sparql import Triple
from rdf_persistence.persistence.services.session import GuardContext, Session
from rdf_persistence.schema.services.schema_structure import (
    own_classes,
    own_schemas,
    root_classes,
)


class AggregateReader(Protocol):
    """What a rule may ask about the aggregates a root names: their classes, and the aggregate itself."""

    async def classes_of(self, iri: str) -> frozenset[str]:
        """The class names of the aggregate at ``iri``; empty when there is none, or the writer may not read it."""
        ...

    async def aggregate(self, iri: str) -> BaseModel | None:
        """The aggregate at ``iri`` as its model, a copy the rule may change; None when there is none, the
        writer may not read it, or this transaction removed it earlier.

        The write then depends on the version read: if the aggregate changes before the commit, the
        commit fails with a ``Conflict`` naming it. A removal collected after the read is not seen.
        """
        ...


# (model class name, root IRI, the root's graph, the graph IRI of its tracking or None) -> its model;
# raises ValueError when the graph does not decode
Decode = Callable[[str, str, Graph, URIRef | None], BaseModel]


# old (None on create), new, who, reader; returns None, or an awaitable of None
AggregateValidator = Callable[
    [BaseModel | None, BaseModel, Principal, AggregateReader], Awaitable[None] | None
]

# The model class name to decode a root as, and the rules that apply to it, most general class first.
Selection = tuple[str, tuple[AggregateValidator, ...]]


class AggregateValidators:
    """The rules of a service, keyed by class, checked against the schema (PD-2) and selected per root (PD-3).

    Raises:
        ValueError: A key is not a class, is a mixin, is a toolkit class, or no root derives from it;
            the message names the key and the reason.
        TypeError: A rule is not callable; the message names the key.
    """

    def __init__(
        self,
        view: SchemaView,
        mapping: Mapping[str, Sequence[AggregateValidator]],
        folder: Path,
    ) -> None:
        roots = _checked_roots(view, mapping, folder)
        chains = {_iri(view, name): _chain(view, name) for name in roots}
        self._names = {_iri(view, name): name for name in roots}
        self._class_names = {_iri(view, name): name for name in view.all_classes()}
        self._lines = {
            iri: frozenset(_iri(view, kin) for kin in chain) for iri, chain in chains.items()
        }
        gathered = {iri: _gather(chain, mapping) for iri, chain in chains.items()}
        self._rules = {iri: found for iri, found in gathered.items() if found}

    @property
    def has_rules(self) -> bool:
        """Whether any rule is registered; with none, a guarded write costs nothing (G-4)."""
        return bool(self._rules)

    def select(self, root_iri: str, type_iris: Iterable[str]) -> Selection | None:
        """The rules for the root at ``root_iri`` typed ``type_iris``; None when no rule applies.

        Takes every type of the root that is a root class. They must lie on one ``is_a`` chain; the most
        specific one is the model class and its chain gives the rules.

        Raises:
            InvalidBody: The types are on two lines and a rule applies to one of them, so a client cannot
                pick a type that escapes a rule.
        """
        return _select(root_iri, type_iris, self._names, self._lines, self._rules)

    def reader(self, session: Session, context: GuardContext, decode: Decode) -> AggregateReader:
        """The reader for one write: it answers for ``session``'s caller and sees what ``context`` collected.

        ``decode`` turns a root's graph into its model.
        """
        return _Reader(session, context, self._class_names, decode, self.model_class)

    def model_class(self, type_iris: Iterable[str]) -> str | None:
        """The class name to decode a root typed ``type_iris`` as; None when its root types name none.

        None also when they lie on two lines: no single class decodes such a root.
        """
        return _model_class(type_iris, self._names, self._lines)


# old, who, reader; returns None, or an awaitable of None
DeleteValidator = Callable[[BaseModel, Principal, AggregateReader], Awaitable[None] | None]

# The model class name to decode a root as, and the delete rules that apply to it, most general first.
DeleteSelection = tuple[str, tuple[DeleteValidator, ...]]


class DeleteValidators:
    """The delete rules of a service, keyed by class, checked against the schema and selected per root
    (aggregate-guards D-6). They share the key checks and the chains with ``AggregateValidators``.

    Raises:
        ValueError: A key is not a class, is a mixin, is a toolkit class, or no root derives from it;
            the message names the key and the reason.
        TypeError: A rule is not callable; the message names the key.
    """

    def __init__(
        self,
        view: SchemaView,
        mapping: Mapping[str, Sequence[DeleteValidator]],
        folder: Path,
    ) -> None:
        roots = _checked_roots(view, mapping, folder, "delete validator")
        chains = {_iri(view, name): _chain(view, name) for name in roots}
        self._names = {_iri(view, name): name for name in roots}
        self._class_names = {_iri(view, name): name for name in view.all_classes()}
        self._lines = {
            iri: frozenset(_iri(view, kin) for kin in chain) for iri, chain in chains.items()
        }
        gathered = {iri: _gather(chain, mapping) for iri, chain in chains.items()}
        self._rules = {iri: found for iri, found in gathered.items() if found}

    @property
    def has_rules(self) -> bool:
        """Whether any rule is registered; with none, a removal costs nothing (G-4)."""
        return bool(self._rules)

    def select(self, root_iri: str, type_iris: Iterable[str]) -> DeleteSelection | None:
        """The delete rules for the root at ``root_iri`` typed ``type_iris``; None when none applies.

        Raises:
            InvalidBody: The types are on two lines and a rule applies to one of them, so a client cannot
                pick a type that escapes a rule.
        """
        return _select(root_iri, type_iris, self._names, self._lines, self._rules)

    def reader(self, session: Session, context: GuardContext, decode: Decode) -> AggregateReader:
        """The reader for one removal: it answers for ``session``'s caller and sees what ``context`` holds."""
        return _Reader(session, context, self._class_names, decode, self.model_class)

    def model_class(self, type_iris: Iterable[str]) -> str | None:
        """The class name to decode a root typed ``type_iris`` as; None when its root types name none."""
        return _model_class(type_iris, self._names, self._lines)


def _named_types(type_iris: Iterable[str], names: Mapping[str, str]) -> list[str]:
    return sorted({iri for iri in type_iris if iri in names})


def _most_specific(types: list[str], lines: Mapping[str, frozenset[str]]) -> str | None:
    """The type every other one is an ancestor of; None when there is none, or no type at all."""
    return next((iri for iri in types if all(other in lines[iri] for other in types)), None)


def _model_class(
    type_iris: Iterable[str], names: Mapping[str, str], lines: Mapping[str, frozenset[str]]
) -> str | None:
    most_specific = _most_specific(_named_types(type_iris, names), lines)
    return None if most_specific is None else names[most_specific]


def _select[Rule](
    root_iri: str,
    type_iris: Iterable[str],
    names: Mapping[str, str],
    lines: Mapping[str, frozenset[str]],
    rules: Mapping[str, tuple[Rule, ...]],
) -> tuple[str, tuple[Rule, ...]] | None:
    """The model class and rules of the root ``root_iri``; None when no rule applies (PD-3)."""
    types = _named_types(type_iris, names)
    most_specific = _most_specific(types, lines)
    if most_specific is None:
        if any(iri in rules for iri in types):
            raise InvalidBody(
                f"{root_iri} has root types on two lines: {', '.join(sorted(names[i] for i in types))}"
            )
        return None
    found = rules.get(most_specific)
    return None if found is None else (names[most_specific], found)


class _Reader:
    """The reader of one guarded write (PD-5): built from the session, the context, the view's class IRI to
    name map, the function that decodes a root and the one that names its model class."""

    def __init__(
        self,
        session: Session,
        context: GuardContext,
        names: Mapping[str, str],
        decode: Decode,
        model_class: Callable[[Iterable[str]], str | None],
    ) -> None:
        self._session = session
        self._context = context
        self._names = names
        self._decode = decode
        self._model_class = model_class

    async def classes_of(self, iri: str) -> frozenset[str]:
        if not self._visible(iri) or iri in self._context.removed:
            return frozenset()  # also what a removal collected earlier answers: the two reads agree
        return frozenset(self._names[t] for t in await self._types(iri) if t in self._names)

    async def aggregate(self, iri: str) -> BaseModel | None:
        """The aggregate at ``iri`` as its model, a copy that is the rule's own; None when there is none.

        None also when the writer may not read it, when this transaction removed it earlier, and when
        its root types name no single class. The stored aggregate is read once per transaction and
        the commit fails, naming it, if it changed meanwhile (the version the reader saw is relied on).
        A removal that the transaction collects after the read is not seen: the rule judged the aggregate
        as it was (the commit then holds both changes).

        Raises:
            RuntimeError: The aggregate, stored or collected, does not decode.
            Conflict: The aggregate is relied on already, in this transaction, at another version.
        """
        cache = self._context.read_cache
        if not self._visible(iri) or iri in self._context.removed:
            return None
        model = cache.get(iri)
        if model is None:
            model = await self._read(iri)
            if model is None:
                return None
            cache[iri] = model
        return model.model_copy(deep=True)

    def _visible(self, iri: str) -> bool:
        """Whether ``iri`` is an aggregate IRI of the tenant the writer may read (no query)."""
        if self._session.not_aggregates([iri]):
            return False
        may_read = self._session.may_read
        return may_read is None or may_read(iri)  # a refusal is the answer for an absent aggregate

    async def _read(self, iri: str) -> BaseModel | None:
        """The model of ``iri`` as collected earlier in this transaction (no tracking), else as stored
        (tracked, and relied on at the version read)."""
        collected = self._context.collected.get(iri)
        if collected is not None:
            graph = Graph()
            for triple in collected:
                graph.add(triple)
            return self._decoded(iri, graph, None, "collected")
        try:
            graph, tracked_in, version = await self._session.get_graph(iri)
        except NotFound:
            return None
        model = self._decoded(iri, graph, tracked_in, "stored")
        if model is not None:
            self._context.rely_on(iri, version)
        return model

    def _decoded(
        self, iri: str, graph: Graph, tracked_in: URIRef | None, where: str
    ) -> BaseModel | None:
        """The root as its model; None when its root types name no single class. A body that does not
        decode is a bug (D-3): ``RuntimeError``."""
        name = self._model_class(str(t) for t in graph.objects(URIRef(iri), RDF.type))
        if name is None:
            return None
        try:
            return self._decode(name, iri, graph, tracked_in)
        except ValueError as error:
            raise RuntimeError(f"the {where} {iri} does not decode: {error}") from error

    async def _types(self, iri: str) -> list[str]:
        """The type IRIs of ``iri``: as collected earlier in this transaction, else as stored."""
        collected = self._context.collected.get(iri)
        if collected is not None:
            return root_types(iri, collected)
        return [t for head in await self._session.heads([iri]) for t in head.head_types or []]


def root_types(iri: str, triples: Iterable[Triple]) -> list[str]:
    """The ``rdf:type`` IRIs the triples give the subject ``iri``."""
    root = URIRef(iri)
    return [str(o) for s, p, o in triples if s == root and p == RDF.type]


async def run_aggregate_validators(
    rules: Iterable[AggregateValidator],
    old: BaseModel | None,
    new: BaseModel,
    principal: Principal,
    reader: AggregateReader,
) -> None:
    """Run ``rules`` in order on copies of ``old`` and ``new``; the first refusal stops the write (PD-7).

    ``InvalidBody`` and pydantic's ``ValidationError`` pass as they are (422), and so do the store errors
    the reader may raise and the ``Conflict`` it raises when an aggregate read changed within the
    transaction (409). Anything else a rule raises is a bug in it: ``RuntimeError`` naming the rule,
    chained to the error. A result other than None, after awaiting, is ``TypeError``.
    """
    for rule in rules:
        name = getattr(rule, "__qualname__", repr(rule))
        try:
            result: object = rule(
                None if old is None else old.model_copy(deep=True),
                new.model_copy(deep=True),
                principal,
                reader,
            )
            if inspect.isawaitable(result):
                result = await result
        except (InvalidBody, ValidationError, StoreUnavailable, DatabaseGone, Conflict):
            raise
        except Exception as error:
            raise RuntimeError(
                f"aggregate validator {name} raised {type(error).__name__}: {error}"
            ) from error
        if result is not None:
            raise TypeError(f"aggregate validator {name} returns None or raises, not {result!r}")


async def run_delete_validators(
    rules: Iterable[DeleteValidator],
    old: BaseModel,
    principal: Principal,
    reader: AggregateReader,
) -> None:
    """Run ``rules`` in order on copies of ``old``; the first refusal stops the removal (D-5).

    A rule refuses by raising ``Refused`` (D-12), which passes as it is; so does a plain ``Conflict``
    (the reader's version clash), and so do the store errors the reader may raise. Anything else a rule raises, ``InvalidBody`` included (a delete has no body to
    call invalid), is a bug in it: ``RuntimeError`` naming the rule, chained to the error. A result
    other than None, after awaiting, is ``TypeError``.
    """
    for rule in rules:
        name = getattr(rule, "__qualname__", repr(rule))
        try:
            result: object = rule(old.model_copy(deep=True), principal, reader)
            if inspect.isawaitable(result):
                result = await result
        except (StoreUnavailable, DatabaseGone, Conflict):
            raise
        except Exception as error:
            raise RuntimeError(
                f"delete validator {name} raised {type(error).__name__}: {error}"
            ) from error
        if result is not None:
            raise TypeError(f"delete validator {name} returns None or raises, not {result!r}")


def _checked_roots(
    view: SchemaView,
    mapping: Mapping[str, Sequence[Any]],
    folder: Path,
    kind: str = "aggregate validator",
) -> set[str]:
    """The names of the roots of ``folder``, after checking every key and rule of ``mapping``."""
    own = {cls.name for cls in own_classes(own_schemas(view, folder))}
    roots = {cls.name for cls in root_classes(view, folder)}
    for key, rules in mapping.items():
        _check_key(view, key, own, roots)
        _check_callable(key, rules, kind)
    return roots


def _iri(view: SchemaView, name: str) -> str:
    return str(view.get_uri(name, expand=True))


def _chain(view: SchemaView, name: str) -> list[str]:
    """The ``is_a`` ancestors of ``name`` and itself, most general first, mixins left out."""
    return list(reversed(view.class_ancestors(name, mixins=False)))


def _gather[Rule](chain: list[str], mapping: Mapping[str, Sequence[Rule]]) -> tuple[Rule, ...]:
    return tuple(rule for ancestor in chain for rule in mapping.get(ancestor, ()))


def _check_callable(key: str, rules: Sequence[object], kind: str) -> None:
    for rule in rules:
        if not callable(rule):
            raise TypeError(f"the {kind} for {key} is not callable: {rule!r}")


def _check_key(view: SchemaView, key: str, own: set[str], roots: set[str]) -> None:
    """Refuse a key that is not an application class a root derives from, naming the key and why."""
    cls = view.get_class(key)
    if cls is None:
        raise ValueError(f"{key}: not a class of the schema")
    if cls.mixin:
        raise ValueError(f"{key}: a mixin")
    if key not in own:
        raise ValueError(f"{key}: a toolkit class")
    if not roots.intersection(view.class_descendants(key, mixins=False)):
        raise ValueError(f"{key}: no root derives from it")
