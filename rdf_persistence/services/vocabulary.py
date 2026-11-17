"""The predicates and enum meanings the session and tenancy write, read from the metamodel (PD-7, PD-8c).

Nothing here restates the schema: each predicate is the URI of a metamodel slot and each enum
meaning is the ``meaning`` of a permissible value, read once through ``SchemaView`` and cached. The
meanings are keyed by the generated enums, so no caller handles the values as free strings. The
factories at the end build the term bundles of the query templates (``generated.templates``), so the
vocabulary IRIs a template uses are set in this one module (technical-models PD-5).
"""

from collections.abc import Iterable, Mapping
from enum import Enum
from functools import cache

from linkml_runtime.utils.schemaview import SchemaView
from rdflib import Literal, URIRef

from rdf_persistence.domain.generated.rp_core import RegistryKind, RpAnnotation
from rdf_persistence.domain.generated.rp_tenancy import TenantState
from rdf_persistence.domain.sparql import SparqlTerm, term, term_list
from rdf_persistence.services.generated.templates.rp_templates import (
    KeyBranchTerms,
    KeyHeldTerms,
    ListingTerms,
    OwnerTerms,
    RegistryTerms,
    StampGuardTerms,
)
from rdf_persistence.services.schema import PACKAGE_DIR, SERVICE_SCHEMA, load_schema
from rdf_persistence.services.schema_structure import ACTIVITY as ACTIVITY_NAME
from rdf_persistence.services.schema_structure import annotation_text, flag, is_bookkeeping

METAMODEL = PACKAGE_DIR / "model" / "rp.yaml"
TOOLKIT_MIGRATIONS = PACKAGE_DIR / "model" / "migrations"  # the toolkit's own chain (PD-13)


@cache
def metamodel() -> SchemaView:
    """The metamodel, opened once."""
    return load_schema(METAMODEL)


def predicate(slot: str, view: SchemaView | None = None) -> URIRef:
    """The predicate of the slot ``slot`` of the metamodel (or of ``view``): its ``slot_uri``, expanded."""
    view = view or metamodel()
    return URIRef(view.get_uri(view.get_slot(slot), expand=True))


def class_iri(name: str) -> URIRef:
    """The IRI of the class ``name`` of the metamodel: its ``class_uri``, expanded."""
    view = metamodel()
    return URIRef(view.get_uri(view.get_class(name), expand=True))


def activity_types(name: str, view: SchemaView | None = None) -> list[URIRef]:
    """The class IRIs of the activity class ``name`` of the metamodel (or of ``view``): its own
    first, then each ancestor up to ``prov:Activity``; classes only, no mixins (message-bus PD-7).

    Raises:
        ValueError: ``name`` is no activity class.
    """
    view = view or metamodel()
    types: list[URIRef] = []
    for cls in view.class_ancestors(name, mixins=False):
        types.append(URIRef(view.get_uri(cls, expand=True)))
        if cls == ACTIVITY_NAME:
            return types
    raise ValueError(f"{name} is not an {ACTIVITY_NAME}")


def meanings[E: Enum](members: type[E]) -> Mapping[E, URIRef]:
    """The meaning IRI of each member of a generated enum, as the metamodel declares it."""
    view = metamodel()
    values = view.get_enum(members.__name__).permissible_values
    return {
        member: URIRef(view.expand_curie(values[str(member.value)].meaning)) for member in members
    }


def media_types[E: Enum](members: type[E], view: SchemaView | None = None) -> Mapping[E, str]:
    """The media type of each member of a generated enum, as the metamodel (or ``view``) declares it.

    Raises:
        ValueError: A permissible value has no ``media_type`` annotation; the message names it.
    """
    view = view or metamodel()
    values = view.get_enum(members.__name__).permissible_values
    found: dict[E, str] = {}
    for member in members:
        text = annotation_text(values[str(member.value)], RpAnnotation.MEDIA_TYPE)
        if text is None:
            raise ValueError(f"{members.__name__}.{member.value} has no media_type annotation")
        found[member] = text
    return found


VERSION = predicate("version")
# The version of a schema that a database's data follows, in the schema-stamps graph (PD-2).
DATA_SCHEMA_VERSION = predicate("data_schema_version")
CREATED = predicate("created")
MODIFIED = predicate("modified")
CREATOR = predicate("creator")
CONTRIBUTOR = predicate("contributor")
# The statements the session makes about a graph IRI; closed shapes ignore them (PD-7).
BOOKKEEPING_PREDICATES = frozenset(
    predicate(slot.name) for slot in metamodel().all_slots().values() if is_bookkeeping(slot)
)

# The slots of an activity's record the toolkit sets itself (message-bus PD-2).
TOOLKIT_FILLED = frozenset(
    slot.name
    for slot in metamodel().all_slots().values()
    if flag(slot, RpAnnotation.TOOLKIT_FILLED)
)
# The five the session itself writes; a test pins it as a subset of TOOLKIT_FILLED (which, with the
# three of a transition, has eight).
SESSION_FILLED = (
    "started_at_time",
    "ended_at_time",
    "was_associated_with",
    "generations",
    "invalidations",
)

# The stored shape of an activity: its slots, and its parts' class and slots (message-bus PD-3).
ACTIVITY_STARTED = predicate("started_at_time")
ACTIVITY_ENDED = predicate("ended_at_time")
ASSOCIATED_WITH = predicate("was_associated_with")
HAS_GENERATION = predicate("generations")
HAS_INVALIDATION = predicate("invalidations")
SESSION_FILLED_PREDICATES = frozenset(predicate(name) for name in SESSION_FILLED)
ACTIVITY = class_iri("Activity")
ADD = class_iri("Add")
REPLACE = class_iri("Replace")
REMOVE = class_iri("Remove")
GENERATION = class_iri("Generation")
INVALIDATION = class_iri("Invalidation")
PART_ACTIVITY = predicate("activity")
AT_TIME = predicate("at_time")
ENTITY = predicate("entity")
ENTITY_CLASS = predicate("entity_class")
ENTITY_VERSION = predicate("entity_version")

REGISTRY_GRAPH = predicate("graph")
REGISTRY_KIND = predicate("kind")
REGISTRY_OWNED_BY = predicate("owned_by")
# The time a load put a graph: the one statement of its marker in the registry (live-tenant-sweep PD-2).
LOADED_AT = predicate("loaded_at")
# A transaction's commit marker: its class and the time it started (atomic-commit PD-1).
COMMIT_MARKER = class_iri("CommitMarker")
STARTED_AT = predicate("started_at")
# The relay's plumbing on an activity (aggregate-events PD-1): not slots, so no model and no message
# carries them; reads of an activity exclude them and a restore drops them (PD-14).
PENDING_SINCE = URIRef(f"{STARTED_AT.removesuffix('startedAt')}pendingSince")
RELAYED_AT = URIRef(f"{STARTED_AT.removesuffix('startedAt')}relayedAt")
PUBLICATION_FAILED = URIRef(f"{STARTED_AT.removesuffix('startedAt')}publicationFailed")
RELAY_PLUMBING = (PENDING_SINCE, RELAYED_AT, PUBLICATION_FAILED)
# A graph naming a blob of the tenant's bucket by its key (PD-3 of the live-tenant sweep).
FILE_KEY = predicate("file_key")
# A listing states the graph it found each subject in (PD-7); the toolkit drops it before answering.
LISTED_IN = predicate("listed_in")
REGISTRY_KIND_IRIS = meanings(RegistryKind)

STATE = predicate("state")
TENANT_STATE_IRIS = meanings(TenantState)

# A collection names its members, and has a rule that says which others belong (PD-5, PD-7).
HAD_MEMBER = predicate("had_member")
MEMBERSHIP_RULE = predicate("membership_rule")

# A comment is a Web Annotation: its class, the aggregate it targets and the aggregates it refers to (PD-12).
ANNOTATION = class_iri("Comment")
HAS_TARGET = predicate("has_target")
COMMENT_REFERENCES = predicate("comment_references")

# An aggregate under a workflow holds its current state, the IRI of one of the workflow's states (PD-16).
WORKFLOW_STATUS = predicate("workflow_status")

# A transition is an activity: its class, the aggregate it moved by prov:used, the states and the comment
# it names (message-bus PD-11).
TRANSITION = class_iri("Transition")
USED = predicate("used_resource")
FROM_STATE = predicate("from_state_iri")
TO_STATE = predicate("to_state_iri")
TRANSITION_COMMENT = predicate("transition_comment")

# Posting a comment, replying to one and deleting a file are activities too (message-bus PD-18, PD-19).
POST_COMMENT = class_iri("PostComment")
POST_REPLY = class_iri("PostReply")
DELETE_FILE = class_iri("DeleteFile")
REPLIES_TO = predicate("replies_to")

GRANTS = predicate("grants")
PROHIBITIONS = predicate("prohibitions")
ASSIGNEE = predicate("assignee")

# A listing's query returns the size of the whole listing as this statement about the listed class.
TOTAL = predicate("total", load_schema(SERVICE_SCHEMA))

# The one statement of the policy record: the graph names itself, the object is the policy's JSON (PD-13).
IRI_POLICY = predicate("iri_policy", load_schema(SERVICE_SCHEMA))


# The term bundles of the query templates (technical-models PD-5): the fixed vocabulary is set here,
# once; a factory takes the varying fields as keywords. None spreads ``model_dump()``, which would
# turn each ``SparqlTerm`` into a ``str``.
def registry_terms(registry: URIRef) -> RegistryTerms:
    """The registry graph and the two predicates of its entries."""
    return RegistryTerms(
        registry=term(registry), p_kind=term(REGISTRY_KIND), p_owned_by=term(REGISTRY_OWNED_BY)
    )


def key_held_terms(
    registry: URIRef, *, values: SparqlTerm, excluded: Iterable[URIRef]
) -> KeyHeldTerms:
    """The terms of the pattern that holds while another aggregate has the claimed ``values``."""
    return KeyHeldTerms(
        registry=term(registry),
        p_kind=term(REGISTRY_KIND),
        p_owned_by=term(REGISTRY_OWNED_BY),
        aggregate=term(REGISTRY_KIND_IRIS[RegistryKind.AGGREGATE]),
        values=values,
        excluded=term_list(excluded),
    )


def key_branch_terms(
    registry: URIRef, *, values: SparqlTerm, excluded: Iterable[URIRef], index: SparqlTerm
) -> KeyBranchTerms:
    """The terms of one branch of the diagnosis: ``key_held_terms`` and the claim's ``index``."""
    return KeyBranchTerms(
        registry=term(registry),
        p_kind=term(REGISTRY_KIND),
        p_owned_by=term(REGISTRY_OWNED_BY),
        aggregate=term(REGISTRY_KIND_IRIS[RegistryKind.AGGREGATE]),
        values=values,
        excluded=term_list(excluded),
        index=index,
    )


def owner_terms(root: URIRef) -> OwnerTerms:
    """The terms of the operations that drop what ``root`` owns."""
    return OwnerTerms(
        root=term(root),
        p_owned_by=term(REGISTRY_OWNED_BY),
        p_kind=term(REGISTRY_KIND),
        loaded=term(REGISTRY_KIND_IRIS[RegistryKind.LOADED_GRAPH]),
    )


def listing_terms(  # noqa: PLR0913 - one keyword per varying field of the listing
    registry: URIRef,
    *,
    target: URIRef,
    patterns: SparqlTerm,
    hidden: SparqlTerm,
    order: SparqlTerm,
    limit: SparqlTerm,
    offset: SparqlTerm,
    sort: URIRef | None = None,
) -> ListingTerms:
    """The terms of the listing query; ``sort`` is the predicate it is ordered by, none for the IRI."""
    return ListingTerms(
        registry=term(registry),
        p_kind=term(REGISTRY_KIND),
        p_owned_by=term(REGISTRY_OWNED_BY),
        aggregate=term(REGISTRY_KIND_IRIS[RegistryKind.AGGREGATE]),
        target=term(target),
        patterns=patterns,
        hidden=hidden,
        p_listed_in=term(LISTED_IN),
        p_total=term(TOTAL),
        p_sort=term(sort) if sort is not None else None,
        order=order,
        limit=limit,
        offset=offset,
    )


def stamp_guard_terms(stamps: URIRef, *, schema_id: URIRef, from_version: str) -> StampGuardTerms:
    """The terms that make a migration operation match only the stamp of ``from_version``."""
    return StampGuardTerms(
        stamps=term(stamps),
        schema_id=term(schema_id),
        p_stamp=term(DATA_SCHEMA_VERSION),
        from_version=term(Literal(from_version)),
    )
