"""The toy library's mapper and small builders of its objects, shared by the mapper tests."""

from functools import cache
from pathlib import Path
from typing import Any
from uuid import UUID

from rdf_persistence import (
    Action,
    CallerAccess,
    Grant,
    InvalidBody,
    Mapper,
    Prohibition,
    ServiceSettings,
    TenantState,
    VerifiedCaller,
    generated_models,
    new_part,
)
from rdf_persistence.domain.generated import rp_access, rp_core
from rdf_persistence.domain.iris import graph_iri
from rdf_persistence.services.schema import load_schema
from tests.fixtures.library.generated import (
    books,
    library,
    library_access,
    library_tenant,
    scans,
)
from tests.fixtures.library.generated.books import Book, Chapter, Genre, Note, Shelf
from tests.fixtures.library.generated.library import Library
from tests.fixtures.library.generated.library_access import LibraryAccess

SCANS = "scans"  # the rp_path of the scan roots
TOY_SCHEMA = Path(__file__).parent / "fixtures" / "library" / "library.yaml"
TENANT = "https://example.org/libraries/6f1c0c1e"
ADA = "https://example.org/people/ada"
BOB = "https://example.org/people/bob"
ROLES = Path(__file__).parent / "fixtures" / "library" / "library_roles.yaml"
DATABASE = "acme-t-" + "0" * 32
MODULES = (books, library, library_access, library_tenant, scans, rp_access, rp_core)


@cache
def toy_mapper() -> Mapper:
    return Mapper(load_schema(TOY_SCHEMA), generated_models(*MODULES))


def book_iri(n: object) -> str:
    return f"{TENANT}/books/{UUID(int=int(n))}"  # a minted aggregate IRI ends in a UUID


def shelf_iri(n: object) -> str:
    return f"{TENANT}/shelves/{UUID(int=int(n))}"  # a minted aggregate IRI ends in a UUID


def graph_of(iri: str) -> str:
    return str(graph_iri(iri))


def caller(*global_roles: str, principal: str = ADA) -> VerifiedCaller:
    """The verified caller, with the given global roles from the token."""
    return VerifiedCaller(principal=principal, global_roles=list(global_roles) or None)


def role(name: str, target: str = TENANT, who: str = ADA) -> Grant:
    return Grant(assignee=who, target=target, role=name)


def direct(action: Action, target: str = TENANT, who: str = ADA) -> Grant:
    return Grant(assignee=who, target=target, action=action)


def ban(action: Action, target: str = TENANT, who: str = ADA) -> Prohibition:
    return Prohibition(assignee=who, target=target, action=action)


def held(
    *grants: Grant, bans: list[Prohibition] | None = None, state: TenantState = TenantState.ACTIVE
) -> CallerAccess:
    """What the check knows of one caller in the toy tenant."""
    return CallerAccess(tenant=TENANT, state=state, grants=list(grants) or None, prohibitions=bans)


def dune(iri: str, *, chapters: int = 2) -> Book:
    """A book with ``chapters`` chapters of one note each; every part gets a minted IRI."""
    parts = [
        new_part(
            Chapter,
            iri,
            number=n,
            notes=[new_part(Note, iri, label=f"note {n}", text="a note", shade="ivory")],
        )
        for n in range(1, chapters + 1)
    ]
    return Book(
        id=iri,
        label="Dune",
        description="A planet.",
        genre=Genre.FICTION,
        authors=["Herbert"],
        chapters=parts or None,
    )


def shelf(iri: str) -> Shelf:
    """A shelf with the given IRI."""
    return Shelf(id=iri, label="Shelf", description="A shelf.")


def access(
    grants: list[Grant] | None = None, prohibitions: list[Prohibition] | None = None
) -> LibraryAccess:
    """The tenant's access record, active, with the given rules."""
    return LibraryAccess(
        id=f"{TENANT}/access",
        label="Access",
        description="Who may do what.",
        state=TenantState.ACTIVE,
        database_name=DATABASE,
        grants=grants,
        prohibitions=prohibitions,
    )


SETTINGS = ServiceSettings(
    base="https://example.org/library/",
    prefix="lib",
    tenant_segment="libraries",
    creator_role="librarian",
    roles_claim="urn:zitadel:iam:org:project:42:roles",
)


def library(city: str = "Ghent", iri: str = TENANT) -> Library:
    """A tenant root."""
    return Library(id=iri, label="City library", description="Books for all.", city=city)


def library_slots(city: str = "Ghent") -> dict[str, Any]:
    """The slots of a tenant root, as ``Tenancy.create`` takes them: it mints the ``id`` and gives the tenant's label."""
    return library(city).model_dump(exclude={"id", "label"}, exclude_none=True)


def keep_a_librarian(old: Any, new: Any, who: Any) -> None:
    """A consumer's grant validator: a library keeps at least one librarian."""
    if not any(g.role == "librarian" for g in new.grants or []):
        raise InvalidBody("a library keeps at least one librarian")
