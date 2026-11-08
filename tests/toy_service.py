"""The toy library served over the API with fakes, for the router's tests (task 5.2)."""

import uuid
from pathlib import Path

import httpx
from fastapi import FastAPI
from pydantic import BaseModel

from rdf_persistence import (
    AccessRules,
    JwksTokenVerifier,
    ServiceSettings,
    Store,
    TenantCreate,
    load_role_definitions,
)
from rdf_persistence.domain.generated.service.rp_service import IdKind, IdSpec, IriPolicy
from rdf_persistence.domain.iris import DEFAULT_IRIS, Iris, principal_iri
from rdf_persistence.entrypoints.service import install_service
from rdf_persistence.services.files import FileStore
from rdf_persistence.testkit import FakeFileStore, FakeIdentity, FakeStore, TokenSigner
from rdf_persistence.testkit.tokens import ISSUER
from tests.fixtures.library import generated
from tests.fixtures.library.generated.books import Book, Chapter, Genre, Note
from tests.fixtures.library.generated.library import Library
from tests.fixtures.library.generated.scans import Scan
from tests.toy import ROLES, SETTINGS, TOY_SCHEMA

BASE_URL = "http://test"
LIBRARIAN, READER, OUTSIDER = "librarian", "reader", "outsider"


# The consumer's policy: the tenant under ``project/``, every other object flat beside its siblings.
FLAT = "{base}{tenant_id}/{type}/{id}"
CONSUMER_POLICY = IriPolicy(
    tenant_template="{base}project/{tenant_id}",
    aggregate_template=FLAT,
    part_template=FLAT,
    loaded_graph_template=FLAT,
    tenant_id=IdSpec(kind=IdKind.RANDOM, length=7),
    object_id=IdSpec(kind=IdKind.RANDOM, length=13),
)


def principal_of(sub: str) -> str:
    """The principal IRI a token with ``sub`` identifies."""
    return str(principal_iri(ISSUER, sub))


def body_of(model: BaseModel) -> dict:
    """A request body: the slots set on a model built without ids (the service mints them)."""
    return model.model_dump(mode="json", exclude_unset=True)


def dune_book(label: str = "Dune") -> Book:
    """A book with a chapter and a note, without ids."""
    note = Note.model_construct(label="n", description="d", text="t")
    chapter = Chapter.model_construct(number=1, notes=[note])
    return Book.model_construct(
        label=label,
        description="A planet.",
        genre=Genre.FICTION,
        authors=["Herbert"],
        chapters=[chapter],
    )


def scan_of_dune() -> Scan:
    """A scanned copy of Dune, as a client describes it: the service sets the file key."""
    return Scan.model_construct(
        label="Dune, scanned",
        description="A scanned copy.",
        file_name="dune.pdf",
        media_type="application/pdf",
        byte_size=12,
        sha256="0" * 64,
    )


TENANT_BODY = TenantCreate(
    label="Ghent", root=body_of(Library.model_construct(description="Books for all.", city="Ghent"))
).model_dump(exclude_none=True)
DUNE_BODY = body_of(dune_book())
SCAN_BODY = body_of(scan_of_dune())


class ToyService:
    """The toy app, its identity provider and a client; ``store`` and ``files`` default to the fakes."""

    def __init__(
        self,
        store: Store | None = None,
        files: FileStore | None = None,
        *,
        schema: Path = TOY_SCHEMA,
        package=generated,
        prefix: str | None = None,
        max_body_bytes: int | None = None,
        mount: str = "",
        iri_policy: IriPolicy | None = None,
        verifier_iris: Iris = DEFAULT_IRIS,
    ) -> None:
        self.signer = TokenSigner()
        self.store = store or FakeStore()
        self.files = files or FakeFileStore()
        self.mount = mount
        self.settings: ServiceSettings = SETTINGS.model_copy(
            update={
                "roles_claim": self.signer.roles_claim,
                "prefix": prefix or SETTINGS.prefix,
                "max_body_bytes": max_body_bytes or SETTINGS.max_body_bytes,
                "iri_policy": iri_policy,
            }
        )
        verifier = JwksTokenVerifier(
            ISSUER,
            self.signer.audience,
            self.signer.roles_claim,
            transport=self.signer.transport,
            iris=verifier_iris,
        )
        self.app = FastAPI()
        self.kit = install_service(
            self.app,
            schema=schema,
            generated=package,
            store=self.store,
            files=self.files,
            identity=FakeIdentity(),
            verifier=verifier,
            rules=AccessRules(load_role_definitions(ROLES)),
            settings=self.settings,
            prefix=mount,
        )

    def client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            transport=httpx.ASGITransport(app=self.app, raise_app_exceptions=False),
            base_url=BASE_URL,
        )

    def bearer(self, sub: str, *global_roles: str) -> dict[str, str]:
        """The ``Authorization`` header of a caller with ``sub`` and the given global roles."""
        return {"Authorization": f"Bearer {self.signer.issue(sub=sub, roles=list(global_roles))}"}


def unique_prefix() -> str:
    """A database prefix no other test shares (a run against Fuseki keeps its databases)."""
    return f"t{uuid.uuid4().hex[:12]}"


async def drop_databases(store: Store, prefix: str) -> None:
    """Drop every database of the service that has ``prefix``: the system database and the tenants'."""
    for name in await store.list_datasets():
        if name.startswith(f"{prefix}-"):
            await store.drop_dataset(name)


async def drop_buckets(files: FileStore, prefix: str) -> None:
    """Delete every bucket of the tenants of the service that has ``prefix``."""
    for bucket in await files.list_buckets(f"{prefix}-"):
        await files.delete_bucket(bucket)
