"""The notes application: store a note and read it back, over the toolkit's in-memory fakes."""

import asyncio
from pathlib import Path

import generated
from generated import notes
from generated.notes import Note

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
from rdf_persistence.testkit.tokens import ISSUER

HERE = Path(__file__).parent
ADA = "https://example.org/people/ada"


# tag::kit[]
def build_kit() -> ServiceKit:
    """The toolkit's service kit, over a store, a file store and an identity provider that live in memory."""
    settings = ServiceSettings(
        base="https://example.org/notes/",
        prefix="notes",
        tenant_segment="notebooks",
        creator_role="owner",
        roles_claim="roles",
    )
    signer = TokenSigner(roles_claim=settings.roles_claim)
    return ServiceKit(
        schema=HERE / "models" / "notes.yaml",
        generated=generated,
        store=FakeStore(),
        files=FakeFileStore(),
        identity=FakeIdentity(),
        verifier=JwksTokenVerifier(
            ISSUER, signer.audience, signer.roles_claim, transport=signer.transport
        ),
        rules=AccessRules([]),
        settings=settings,
        migrations=HERE / "migrations",
    )


# end::kit[]


# tag::store[]
async def main() -> tuple[Note, Note]:
    kit = build_kit()
    await kit.tenancy.ensure_system_database()
    notebook = await kit.tenancy.create(
        "Ada's notes", {"description": "Things to do."}, Principal(id=ADA)
    )

    mapper = Mapper(kit.view, generated_models(notes))
    iri = str(kit.iris.mint_aggregate(notebook.id, "note", "notes"))
    note = Note(id=iri, label="Buy milk", description="Before six.", text="Two litres.")

    async with kit.session(notebook.id, ADA) as session:
        work = UnitOfWork(session, mapper)
        work.add(note)
        await work.commit()

    async with kit.session(notebook.id, ADA) as session:
        read_back = await UnitOfWork(session, mapper).get(Note, iri)
    return note, read_back


# end::store[]


if __name__ == "__main__":
    print(asyncio.run(main())[1])
