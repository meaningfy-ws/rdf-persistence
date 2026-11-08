"""The predicates and enum meanings the session and tenancy write, read from the metamodel (PD-7, PD-8c).

Nothing here restates the schema: each predicate is the URI of a metamodel slot and each enum
meaning is the ``meaning`` of a permissible value, read once through ``SchemaView`` and cached. The
meanings are keyed by the generated enums, so no caller handles the values as free strings.
"""

from collections.abc import Mapping
from enum import Enum
from functools import cache

from linkml_runtime.utils.schemaview import SchemaView
from rdflib import URIRef

from rdf_persistence.domain.generated.rp_core import RegistryKind
from rdf_persistence.domain.generated.rp_tenancy import TenantState
from rdf_persistence.services.schema import PACKAGE_DIR, load_schema
from rdf_persistence.services.schema_structure import is_bookkeeping

METAMODEL = PACKAGE_DIR / "model" / "rp.yaml"
SERVICE_MODEL = PACKAGE_DIR / "model" / "service" / "rp_service.yaml"


@cache
def metamodel() -> SchemaView:
    """The metamodel, opened once."""
    return load_schema(METAMODEL)


def predicate(slot: str, view: SchemaView | None = None) -> URIRef:
    """The predicate of the slot ``slot`` of the metamodel (or of ``view``): its ``slot_uri``, expanded."""
    view = view or metamodel()
    return URIRef(view.get_uri(view.get_slot(slot), expand=True))


def meanings[E: Enum](members: type[E]) -> Mapping[E, URIRef]:
    """The meaning IRI of each member of a generated enum, as the metamodel declares it."""
    view = metamodel()
    values = view.get_enum(members.__name__).permissible_values
    return {
        member: URIRef(view.expand_curie(values[str(member.value)].meaning)) for member in members
    }


VERSION = predicate("version")
CREATED = predicate("created")
MODIFIED = predicate("modified")
CREATOR = predicate("creator")
CONTRIBUTOR = predicate("contributor")
# The statements the session makes about a graph IRI; closed shapes ignore them (PD-7).
BOOKKEEPING_PREDICATES = frozenset(
    predicate(slot.name) for slot in metamodel().all_slots().values() if is_bookkeeping(slot)
)

REGISTRY_GRAPH = predicate("graph")
REGISTRY_KIND = predicate("kind")
REGISTRY_OWNED_BY = predicate("owned_by")
# A listing states the graph it found each subject in (PD-7); the toolkit drops it before answering.
LISTED_IN = predicate("listed_in")
REGISTRY_KIND_IRIS = meanings(RegistryKind)

STATE = predicate("state")
TENANT_STATE_IRIS = meanings(TenantState)

GRANTS = predicate("grants")
PROHIBITIONS = predicate("prohibitions")
ASSIGNEE = predicate("assignee")

# A listing's query returns the size of the whole listing as this statement about the listed class.
TOTAL = predicate("total", load_schema(SERVICE_MODEL))

# The one statement of the policy record: the graph names itself, the object is the policy's JSON (PD-13).
IRI_POLICY = predicate("iri_policy", load_schema(SERVICE_MODEL))
