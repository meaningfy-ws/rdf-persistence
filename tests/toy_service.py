"""The toy library served over the API with fakes, for the router's tests (task 5.2)."""

import uuid
from pathlib import Path

import httpx
from fastapi import FastAPI

from rdf_persistence import (
    AccessRules,
    JwksTokenVerifier,
    ServiceSettings,
    Store,
    load_role_definitions,
)
from rdf_persistence.entrypoints.service import install_service
from rdf_persistence.services.files import FileStore
from rdf_persistence.testkit import FakeFileStore, FakeIdentity, FakeStore, TokenSigner
from rdf_persistence.testkit.tokens import ISSUER
from tests.fixtures.library import generated
from tests.toy import ROLES, SETTINGS, TOY_SCHEMA

BASE_URL = "http://test"
LIBRARIAN, READER, OUTSIDER = "librarian", "reader", "outsider"


def principal_of(sub: str) -> str:
    """The principal IRI a token with ``sub`` identifies."""
    return f"{ISSUER}/users/{sub}"


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
    ) -> None:
        self.signer = TokenSigner()
        self.store = store or FakeStore()
        self.files = files or FakeFileStore()
        self.settings: ServiceSettings = SETTINGS.model_copy(
            update={"roles_claim": self.signer.roles_claim, "prefix": prefix or SETTINGS.prefix}
        )
        verifier = JwksTokenVerifier(
            ISSUER, self.signer.audience, self.signer.roles_claim, transport=self.signer.transport
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
