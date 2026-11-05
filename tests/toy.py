"""The toy library's mapper and small builders of its objects, shared by the mapper tests."""

from functools import cache
from pathlib import Path

from rdf_persistence.domain.generated import rp_access, rp_core
from rdf_persistence.domain.generated.rp_access import Grant, Prohibition
from rdf_persistence.domain.generated.rp_tenancy import TenantState
from rdf_persistence.services.mapper import Mapper, generated_models, new_part
from rdf_persistence.services.schema import load_schema
from tests.fixtures.library.generated import (
    books,
    library,
    library_access,
    library_tenant,
    scans,
)
from tests.fixtures.library.generated.books import Book, Chapter, Genre, Note
from tests.fixtures.library.generated.library_access import LibraryAccess

TOY_SCHEMA = Path(__file__).parent / "fixtures" / "library" / "library.yaml"
TENANT = "https://example.org/libraries/6f1c0c1e"
ADA = "https://example.org/people/ada"
DATABASE = "acme-t-" + "0" * 32
MODULES = (books, library, library_access, library_tenant, scans, rp_access, rp_core)


@cache
def toy_mapper() -> Mapper:
    return Mapper(load_schema(TOY_SCHEMA), generated_models(*MODULES))


def book_iri(n: object) -> str:
    return f"{TENANT}/books/{n}"


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
