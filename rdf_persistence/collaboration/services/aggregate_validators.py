"""Aggregate validators: a consumer's rules on the write of a root (aggregate-validators PD-1 to PD-3, PD-7).

A rule is registered for a class of the consumer's schema and runs on every guarded add and replace of a
root of that class or of a class derived from it. It refuses by raising ``InvalidBody``; it may be async and
may ask the reader for the classes of the aggregates the root names. ``AggregateValidators`` checks the keys
once, at start-up, and answers which rules apply to a root.
"""

import inspect
from collections.abc import Awaitable, Callable, Iterable, Mapping, Sequence
from pathlib import Path
from typing import Protocol

from linkml_runtime.utils.schemaview import SchemaView
from pydantic import BaseModel, ValidationError
from rdflib import RDF, URIRef

from rdf_persistence.core.domain.exceptions import DatabaseGone, InvalidBody, StoreUnavailable
from rdf_persistence.core.domain.generated.rp_core import Principal
from rdf_persistence.core.domain.sparql import Triple
from rdf_persistence.persistence.services.session import GuardContext, Session
from rdf_persistence.schema.services.schema_structure import (
    own_classes,
    own_schemas,
    root_classes,
)


class AggregateReader(Protocol):
    """What a rule may ask about the aggregates a root names: their classes, and nothing else (DEC-2)."""

    async def classes_of(self, iri: str) -> frozenset[str]:
        """The class names of the aggregate at ``iri``; empty when there is none, or the writer may not read it."""
        ...


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
        self._lines = {
            iri: frozenset(_iri(view, kin) for kin in chain) for iri, chain in chains.items()
        }
        gathered = {iri: _gather(chain, mapping) for iri, chain in chains.items()}
        self._rules = {iri: found for iri, found in gathered.items() if found}

    def select(self, root_iri: str, type_iris: Iterable[str]) -> Selection | None:
        """The rules for the root at ``root_iri`` typed ``type_iris``; None when no rule applies.

        Takes every type of the root that is a root class. They must lie on one ``is_a`` chain; the most
        specific one is the model class and its chain gives the rules.

        Raises:
            InvalidBody: The types are on two lines and a rule applies to one of them, so a client cannot
                pick a type that escapes a rule.
        """
        types = sorted({iri for iri in type_iris if iri in self._names})
        most_specific = self._most_specific(types)
        if most_specific is None:
            self._refuse_two_lines(root_iri, types)
            return None
        rules = self._rules.get(most_specific)
        return None if rules is None else (self._names[most_specific], rules)

    def reader(self, session: Session, context: GuardContext) -> AggregateReader:
        """The reader for one write: it answers for ``session``'s caller and sees what ``context`` collected."""
        return _Reader(session, context, self._names)

    def model_class(self, type_iris: Iterable[str]) -> str | None:
        """The class name to decode a root typed ``type_iris`` as; None when its root types name none.

        None also when they lie on two lines: no single class decodes such a root.
        """
        types = sorted({iri for iri in type_iris if iri in self._names})
        most_specific = self._most_specific(types)
        return None if most_specific is None else self._names[most_specific]

    def _most_specific(self, types: list[str]) -> str | None:
        """The type every other one is an ancestor of; None when there is none, or no type at all."""
        return next(
            (iri for iri in types if all(other in self._lines[iri] for other in types)), None
        )

    def _refuse_two_lines(self, root_iri: str, types: list[str]) -> None:
        if any(iri in self._rules for iri in types):
            names = ", ".join(sorted(self._names[iri] for iri in types))
            raise InvalidBody(f"{root_iri} has root types on two lines: {names}")


class _Reader:
    """The reader of one guarded write (PD-5): built from the session, the context and the root classes."""

    def __init__(self, session: Session, context: GuardContext, names: Mapping[str, str]) -> None:
        self._session = session
        self._context = context
        self._names = names

    async def classes_of(self, iri: str) -> frozenset[str]:
        if self._session.not_aggregates([iri]):
            return frozenset()  # not an aggregate IRI of the tenant: no query
        may_read = self._session.may_read
        if may_read is not None and not may_read(iri):
            return frozenset()  # the same answer as for an aggregate that is not there
        return frozenset(self._names[t] for t in await self._types(iri) if t in self._names)

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
    the reader may raise. Anything else a rule raises is a bug in it: ``RuntimeError`` naming the rule,
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
        except (InvalidBody, ValidationError, StoreUnavailable, DatabaseGone):
            raise
        except Exception as error:
            raise RuntimeError(
                f"aggregate validator {name} raised {type(error).__name__}: {error}"
            ) from error
        if result is not None:
            raise TypeError(f"aggregate validator {name} returns None or raises, not {result!r}")


def _checked_roots(
    view: SchemaView, mapping: Mapping[str, Sequence[AggregateValidator]], folder: Path
) -> set[str]:
    """The names of the roots of ``folder``, after checking every key and rule of ``mapping``."""
    own = {cls.name for cls in own_classes(own_schemas(view, folder))}
    roots = {cls.name for cls in root_classes(view, folder)}
    for key, rules in mapping.items():
        _check_key(view, key, own, roots)
        _check_callable(key, rules)
    return roots


def _iri(view: SchemaView, name: str) -> str:
    return str(view.get_uri(name, expand=True))


def _chain(view: SchemaView, name: str) -> list[str]:
    """The ``is_a`` ancestors of ``name`` and itself, most general first, mixins left out."""
    return list(reversed(view.class_ancestors(name, mixins=False)))


def _gather(
    chain: list[str], mapping: Mapping[str, Sequence[AggregateValidator]]
) -> tuple[AggregateValidator, ...]:
    return tuple(rule for ancestor in chain for rule in mapping.get(ancestor, ()))


def _check_callable(key: str, rules: Sequence[object]) -> None:
    for rule in rules:
        if not callable(rule):
            raise TypeError(f"the aggregate validator for {key} is not callable: {rule!r}")


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
