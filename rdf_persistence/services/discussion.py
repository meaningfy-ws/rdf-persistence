"""Discussion: comments on an aggregate, who sees them, and what a delete takes with them (PD-12 to PD-15).

A comment is an aggregate root of its own, written by the toolkit (``rp_writes: toolkit``): it targets
the aggregate it is about, and a reply also names the comment it answers. ``Discussion`` holds one
``Session`` and the caller it acts for; ``Collaboration`` hands ``comment`` and ``thread`` over to it.
``visible`` is the one rule of who sees a comment, which ``Collaboration.referrers`` uses too.
"""

from collections import defaultdict
from collections.abc import Iterable, Sequence
from collections.abc import Set as AbstractSet
from datetime import UTC, datetime

from linkml_runtime.utils.schemaview import SchemaView
from rdflib import RDF, Graph, URIRef

from rdf_persistence.domain.exceptions import InvalidBody, InvalidIri, NotFound, UnknownRole
from rdf_persistence.domain.generated.rp_access import Action
from rdf_persistence.domain.generated.rp_core import RpAnnotation, WritesKind
from rdf_persistence.domain.generated.rp_discussion import Comment, Motivation
from rdf_persistence.domain.generated.service.rp_service import CallerAccess, VerifiedCaller
from rdf_persistence.domain.iris import Iris, graph_iri
from rdf_persistence.services import vocabulary as v
from rdf_persistence.services.access import AccessRules
from rdf_persistence.services.mapper import Mapper
from rdf_persistence.services.schema_structure import annotation, annotation_text, iri_type_of
from rdf_persistence.services.session import Dependents, ReferrerRow, Session

COMMENT = "Comment"
_NEVER = datetime.min.replace(
    tzinfo=UTC
)  # a stored comment always has a time; this sorts one that has none first


def dependents(view: SchemaView) -> Dependents:
    """The ``(class, link)`` pair a remove drops with the aggregate it points at: a comment's target.

    None for a schema that does not import the discussion module.
    """
    return ((v.ANNOTATION, v.HAS_TARGET),) if view.get_class(COMMENT) else ()


def visible(comments: Iterable[Comment], roles: AbstractSet[str]) -> list[Comment]:
    """The comments of one thread that someone holding ``roles`` sees, oldest first, ties by IRI.

    A comment is seen when it has no audience or its audience meets ``roles``, and, for a reply,
    when its parent is seen: a reply under a hidden parent is hidden (PD-14).
    """
    by_iri = {c.id: c for c in comments}
    seen: dict[str, bool] = {}

    def sees(comment: Comment) -> bool:
        if comment.id not in seen:
            seen[comment.id] = False  # a cycle in stored data ends here, hidden
            parent = by_iri.get(comment.replies_to or "")
            audience = comment.comment_audience
            seen[comment.id] = (not audience or bool(roles & set(audience))) and (
                comment.replies_to is None or (parent is not None and sees(parent))
            )
        return seen[comment.id]

    return sorted(
        (c for c in by_iri.values() if sees(c)), key=lambda c: (c.created or _NEVER, c.id)
    )


class Discussion:
    """What a caller may ask of the comments of a tenant."""

    def __init__(
        self,
        session: Session,
        *,
        view: SchemaView,
        rules: AccessRules,
        iris: Iris,
        mapper: Mapper,
        caller: VerifiedCaller,
        access: CallerAccess,
    ) -> None:
        self._session = session
        self._view = view
        self._rules = rules
        self._iris = iris
        self._mapper = mapper
        self._caller = caller
        self._access = access

    async def comment(
        self,
        iri: str,
        text: str,
        *,
        audience: Sequence[str] = (),
        references: Sequence[str] = (),
        reply_to: str | None = None,
    ) -> str:
        """Post a comment on the aggregate ``iri``; returns the comment's IRI.

        ``audience`` names the roles that may see it (none: everyone who may read ``iri``);
        ``references`` are aggregates of the tenant it points to; ``reply_to`` is a comment of the
        thread of ``iri`` that this caller sees. The aggregate itself is not written, so its
        version does not change. The author and the time are the session's.

        Raises:
            LookupError: The schema does not import the module rp_discussion.
            InvalidIri: ``iri`` is the tenant, or a comment; or a reference is not an aggregate of the tenant.
            NotFound: The caller can see nothing of ``iri``, ``iri`` has no graph, or ``reply_to``
                is not in the thread as this caller sees it.
            Forbidden: The caller may see ``iri`` but not annotate it.
            InvalidBody: ``text`` is blank.
            UnknownRole: An audience role is not defined by the roles file.
            Conflict: ``iri`` was removed meanwhile; nothing was stored (``iris`` names it).
            DatabaseGone: The tenant database does not exist.
        """
        self._require_module()
        if iri == self._access.tenant:
            raise InvalidIri("a comment is on an aggregate, not on the tenant")
        self._rules.require(self._caller, self._access, iri, Action.ANNOTATE)
        await self._require_commentable(iri)
        self._require_valid(text, audience, references)
        if reply_to is not None and reply_to not in {c.id for c in await self.thread(iri)}:
            raise NotFound(f"no comment {reply_to} in the thread of {iri}")
        return await self._store(iri, text, audience, references, reply_to)

    async def thread(self, iri: str) -> list[Comment]:
        """The comments on the aggregate ``iri`` that the caller sees, oldest first, ties by IRI.

        A comment is seen when it has no audience or its audience meets the caller's roles on
        ``iri``, and, for a reply, when its parent is seen. The list is flat; a reply names its parent.

        Raises:
            LookupError: The schema does not import the module rp_discussion.
            NotFound: The caller can see nothing of ``iri``.
            Forbidden: The caller may see ``iri`` but not read it.
            DatabaseGone: The tenant database does not exist.
        """
        self._require_module()
        self._rules.require(self._caller, self._access, iri, Action.READ)
        found = await self._session.graphs_with(v.HAS_TARGET, URIRef(iri))
        comments = [
            self._decode(root, graph) for root, graph in found.items() if self._is(graph, root)
        ]
        return visible(comments, self._rules.roles(self._caller, self._access, iri))

    async def unseen(self, rows: Sequence[ReferrerRow]) -> set[str]:
        """Of the referrers in ``rows``, the comments this caller may not see (PD-3 step 4).

        A comment is seen when the caller may read the aggregate it is on and it is in that
        aggregate's thread as the caller sees it.
        """
        if self._view.get_class(COMMENT) is None:
            return set()
        on: defaultdict[str, set[str]] = defaultdict(set)
        for referrer, cls, _, link in rows:
            if (cls, link) == (str(v.ANNOTATION), str(v.COMMENT_REFERENCES)):
                on[(await self._comment(referrer)).has_target].add(referrer)
        hidden: set[str] = set()
        for target, comments in on.items():
            readable = self._rules.may(self._caller, self._access, target, Action.READ)
            hidden |= comments - ({c.id for c in await self.thread(target)} if readable else set())
        return hidden

    def _require_module(self) -> None:
        if self._view.get_class(COMMENT) is None:
            raise LookupError("the schema does not import the module rp_discussion")

    async def _require_commentable(self, iri: str) -> None:
        """The aggregate exists and is not itself something the toolkit writes (a comment)."""
        graph, _, _ = await self._session.get_graph(iri)
        toolkit = {
            self._view.get_uri(c, expand=True)
            for c in self._view.all_classes().values()
            if annotation(c, RpAnnotation.RP_WRITES) == WritesKind.TOOLKIT.value
        }
        if toolkit & {str(t) for t in graph.objects(URIRef(iri), RDF.type)}:
            raise InvalidIri(f"{iri} is written by the toolkit; it takes no comment")

    def _require_valid(self, text: str, audience: Sequence[str], references: Sequence[str]) -> None:
        if not text.strip():
            raise InvalidBody("a comment needs text")
        if undefined := [r for r in audience if not self._rules.defines(r)]:
            raise UnknownRole(f"no role is defined as {undefined}")
        if foreign := self._session.not_aggregates(references):
            raise InvalidIri(f"not aggregates of the tenant: {foreign}")

    async def _store(
        self,
        iri: str,
        text: str,
        audience: Sequence[str],
        references: Sequence[str],
        reply_to: str | None,
    ) -> str:
        comment_class = self._view.get_class(COMMENT)
        minted = str(
            self._iris.mint_aggregate(
                self._access.tenant,
                iri_type_of(comment_class),
                annotation_text(comment_class, RpAnnotation.RP_PATH) or "",
            )
        )
        model = Comment(
            id=minted,
            has_target=iri,
            body_value=text,
            motivated_by=Motivation.COMMENTING if reply_to is None else Motivation.REPLYING,
            comment_audience=list(audience) or None,
            comment_references=list(references) or None,
            replies_to=reply_to,
        )
        async with self._session.transaction() as transaction:
            transaction._require_present(iri)
            await transaction.add_graph(minted, self._mapper.to_triples(model))
        return minted

    async def _comment(self, iri: str) -> Comment:
        graph, _, _ = await self._session.get_graph(iri)
        return self._decode(iri, graph)

    def _decode(self, iri: str, graph: Graph) -> Comment:
        return self._mapper.from_graph(Comment, iri, graph, graph_iri(iri))

    @staticmethod
    def _is(graph: Graph, root: str) -> bool:
        """Whether ``root`` is typed as a web annotation in ``graph`` (a comment or another's)."""
        return (URIRef(root), RDF.type, v.ANNOTATION) in graph
