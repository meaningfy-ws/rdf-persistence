"""The toy library's composition root, as a consumer writes it: public names only (PD-13a, PD-20).

``build_library_app`` wires the adapters it is given into ``install_service`` and adds the one route
the toolkit does not have: a scan's file, kept in the tenant's bucket through the kit's file store.
"""

from fastapi import FastAPI, Request, Response

from rdf_persistence import (
    AccessRules,
    Action,
    FileStore,
    Identity,
    ServiceSettings,
    Store,
    TokenVerifier,
    install_service,
    load_caller_access,
    load_role_definitions,
)
from tests.fixtures.library import generated
from tests.toy import ROLES, SETTINGS, TOY_SCHEMA

SCAN_FILES = "/{segment}/{{t}}/scan-files/{{name}}"
OCTET_STREAM = "application/octet-stream"


def library_settings(prefix: str, roles_claim: str) -> ServiceSettings:
    """The toy library's settings, with the database prefix of one run and the identity provider's roles claim."""
    return SETTINGS.model_copy(update={"prefix": prefix, "roles_claim": roles_claim})


def build_library_app(
    *,
    store: Store,
    files: FileStore,
    identity: Identity,
    verifier: TokenVerifier,
    settings: ServiceSettings,
) -> FastAPI:
    """The toy library over the given adapters, with its own route for a scan's bytes.

    The route is checked like the toolkit's own: the kit's verifier, the caller's access in the
    tenant, the kit's rules. The bytes go to the tenant's bucket through the kit's file store.
    """
    app = FastAPI()
    kit = install_service(
        app,
        schema=TOY_SCHEMA,
        generated=generated,
        store=store,
        files=files,
        identity=identity,
        verifier=verifier,
        rules=AccessRules(load_role_definitions(ROLES)),
        settings=settings,
    )
    path = SCAN_FILES.format(segment=settings.tenant_segment)

    async def bucket_after(request: Request, tenant_id: str, action: Action) -> str:
        """The tenant's bucket, once the caller of the request may take ``action`` in the tenant."""
        scheme, _, token = request.headers.get("authorization", "").partition(" ")
        caller = await kit.verifier.verify(token if scheme.lower() == "bearer" else "")
        tenant = kit.tenant_iri(tenant_id)
        access = await load_caller_access(kit.store, kit.system_database, tenant, caller.principal)
        kit.rules.require(caller, access, tenant, action)
        return await kit.bucket_of(tenant)

    @app.put(path, status_code=204)
    async def put_file(t: str, name: str, request: Request) -> Response:
        bucket = await bucket_after(request, t, Action.MODIFY)
        await kit.files.put(bucket, name, await request.body())
        return Response(status_code=204)

    @app.get(path)
    async def get_file(t: str, name: str, request: Request) -> Response:
        bucket = await bucket_after(request, t, Action.READ)
        return Response(await kit.files.get(bucket, name), media_type=OCTET_STREAM)

    return app
