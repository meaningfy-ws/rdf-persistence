"""The running toy library over Fuseki, Garage and Zitadel, for the end-to-end tests."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

import httpx

from rdf_persistence import (
    FusekiStore,
    JwksTokenVerifier,
    S3FileStore,
    ServiceKit,
    ZitadelIdentity,
    zitadel_roles_claim,
)
from rdf_persistence.testkit import access_token
from tests.e2e.library_app import build_library_app, library_settings
from tests.toy_service import drop_buckets, drop_databases, unique_prefix


@dataclass(frozen=True)
class Callers:
    """The bearer headers of the machine users, and the principal IRI of each."""

    tokens: dict[str, str]
    principals: dict[str, str]

    def as_(self, name: str, **headers: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.tokens[name]}", **headers}


@dataclass(frozen=True)
class World:
    """The running library: a client, the callers, and the adapters to look behind the API."""

    http: httpx.AsyncClient
    callers: Callers
    store: FusekiStore
    files: S3FileStore
    identity: ZitadelIdentity
    project: Any
    prefix: str
    kit: ServiceKit


@asynccontextmanager
async def running_world(fuseki, garage, zitadel_project, **settings: Any) -> AsyncIterator[World]:
    """The library served in process; ``settings`` overrides the toy library's (IRI policy, deployment)."""
    prefix = unique_prefix()
    server = zitadel_project.server
    users = {user.name: user for user in zitadel_project.machine_users}
    callers = Callers(
        tokens={name: access_token(zitadel_project, user) for name, user in users.items()},
        principals={name: f"{server.url}/users/{user.user_id}" for name, user in users.items()},
    )
    async with (
        FusekiStore(fuseki.url, fuseki.user, fuseki.password) as store,
        ZitadelIdentity(
            server.url,
            server.admin_pat,
            zitadel_project.organisation_id,
            zitadel_project.project_id,
        ) as identity,
        JwksTokenVerifier(
            server.url,
            zitadel_project.project_id,
            zitadel_roles_claim(zitadel_project.project_id),
            allow_insecure_issuer=True,
        ) as verifier,
    ):
        files = S3FileStore(garage.endpoint, garage.key_id, garage.secret, garage.region)
        app = build_library_app(
            store=store,
            files=files,
            identity=identity,
            verifier=verifier,
            settings=library_settings(
                prefix, zitadel_roles_claim(zitadel_project.project_id), **settings
            ),
        )
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
        async with (
            app.router.lifespan_context(app),
            httpx.AsyncClient(transport=transport, base_url="http://library") as http,
        ):
            yield World(
                http, callers, store, files, identity, zitadel_project, prefix, app.state.kit
            )
        await drop_databases(store, prefix)
        await drop_buckets(files, prefix)
