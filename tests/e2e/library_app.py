"""The toy library's composition root, as a consumer writes it: public names only (PD-13a, PD-20).

``build_library_app`` wires the adapters it is given into ``install_service`` and adds the one route
the toolkit does not have: a scan's file, kept in the tenant's bucket through the kit's file store.
"""

from typing import Any

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
    load_role_definitions,
)
from tests.fixtures.library import generated
from tests.toy import ROLES, SETTINGS, TOY_SCHEMA

SCAN_FILES = "/{segment}/{{t}}/scan-files/{{scan_id}}"
SCANS = "scans"
OCTET_STREAM = "application/octet-stream"


def library_settings(prefix: str, roles_claim: str, **overrides: Any) -> ServiceSettings:
    """The toy library's settings, with the database prefix of one run, the identity provider's roles claim and any ``overrides``."""
    return SETTINGS.model_copy(update={"prefix": prefix, "roles_claim": roles_claim, **overrides})


def build_library_app(
    *,
    store: Store,
    files: FileStore,
    identity: Identity,
    verifier: TokenVerifier,
    settings: ServiceSettings,
) -> FastAPI:
    """The toy library over the given adapters, with its own route for a scan's bytes.

    The route is checked like the toolkit's own, by the kit: the token, then the caller's access to
    the scan itself, so a Prohibition on that scan applies. The bytes go to the tenant's bucket
    through the kit's file store, under the scan's id.
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
    app.state.kit = kit  # for a test to look behind the API
    path = SCAN_FILES.format(segment=settings.tenant_segment)

    async def bucket_after(request: Request, tenant_id: str, scan_id: str, action: Action) -> str:
        """The tenant's bucket, once the caller of the request may take ``action`` on the scan."""
        checked = await kit.require_aggregate(
            request.headers.get("authorization"), tenant_id, SCANS, scan_id, action
        )
        return await kit.bucket_of(checked.caller_access.tenant)

    @app.put(path, status_code=204)
    async def put_file(t: str, scan_id: str, request: Request) -> Response:
        bucket = await bucket_after(request, t, scan_id, Action.MODIFY)
        await kit.files.put(bucket, scan_id, await request.body())
        return Response(status_code=204)

    @app.get(path)
    async def get_file(t: str, scan_id: str, request: Request) -> Response:
        bucket = await bucket_after(request, t, scan_id, Action.READ)
        return Response(await kit.files.get(bucket, scan_id), media_type=OCTET_STREAM)

    return app
