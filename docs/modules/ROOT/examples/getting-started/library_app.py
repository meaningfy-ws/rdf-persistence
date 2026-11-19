"""The first step of the toy library: store a book and read it back, over the toolkit's in-memory fakes."""

# tag::setup[]
import asyncio
from pathlib import Path

import generated
from generated import library
from generated.library import Book

from rdf_persistence import (
    AccessRules,
    JwksTokenVerifier,
    Mapper,
    Principal,
    ServiceKit,
    ServiceSettings,
    UnitOfWork,
    generated_models,
)
from rdf_persistence.testkit import FakeFileStore, FakeIdentity, FakeStore, TokenSigner

HERE = Path(__file__).parent
ISSUER = "https://idp.test"  # the issuer the testkit's TokenSigner signs for
ADA = "https://example.org/people/ada"  # the principal: whoever acts, named by an IRI
# end::setup[]


# tag::kit[]
def build_kit() -> ServiceKit:
    """The toolkit's service kit, over a store, a file store and an identity provider that live in memory."""
    settings = ServiceSettings(
        base="https://example.org/library/",
        prefix="lib",
        tenant_segment="libraries",
        creator_role="librarian",
        roles_claim="roles",
    )
    signer = TokenSigner(roles_claim=settings.roles_claim)
    return ServiceKit(
        schema=HERE / "models" / "library.yaml",
        generated=generated,
        store=FakeStore(),
        files=FakeFileStore(),
        identity=FakeIdentity(),
        # the kit requires a token verifier and access rules; only the HTTP routes use them
        verifier=JwksTokenVerifier(
            ISSUER, signer.audience, signer.roles_claim, transport=signer.transport
        ),
        rules=AccessRules([]),
        settings=settings,
        migrations=HERE / "migrations",
    )


# end::kit[]


# tag::store[]
async def main() -> tuple[Book, Book]:
    kit = build_kit()
    await kit.tenancy.ensure_system_database()
    ghent = await kit.tenancy.create("Ghent", {"description": "Books for all."}, Principal(id=ADA))

    # the mapper reads the schema (kit.view) and builds the classes the generator wrote
    mapper = Mapper(kit.view, generated_models(library))
    # "book" is the class's word in an IRI, "books" its rp_path
    iri = str(kit.iris.mint_aggregate(ghent.id, "book", "books"))
    dune = Book(id=iri, label="Dune", description="A planet.", authors=["Frank Herbert"])

    async with kit.session(ghent.id, ADA) as session:
        work = UnitOfWork(session, mapper)
        work.add(dune)
        await work.commit()

    async with kit.session(ghent.id, ADA) as session:
        read_back = await UnitOfWork(session, mapper).get(Book, iri)
    return dune, read_back


# end::store[]


# tag::run[]
if __name__ == "__main__":
    print(asyncio.run(main())[1])
# end::run[]
