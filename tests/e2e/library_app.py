"""The toy library's composition root, as a consumer writes it: public names only (PD-13a, PD-20).

``build_library_app`` wires the adapters it is given into ``install_service`` and adds the routes
the toolkit does not have: a scan is written by ``POST`` (the record through a session, the bytes
through the kit's file store, as a ``StoredFile`` root requires), and its file is read and replaced.
"""

import hashlib
from contextlib import suppress
from typing import Any

from fastapi import FastAPI, Request, Response

from rdf_persistence import (
    AccessRules,
    Action,
    FileStore,
    Identity,
    Mapper,
    ServiceSettings,
    Store,
    TokenVerifier,
    UnitOfWork,
    generated_models,
    install_service,
    limited_body,
    load_role_definitions,
)
from tests.fixtures.library import generated
from tests.fixtures.library.generated import scans
from tests.fixtures.library.generated.scans import Scan
from tests.toy import ROLES, SCANS, SETTINGS, TOY_SCHEMA

SCAN_UPLOADS = "/{segment}/{{t}}/scan-files"
SCAN_FILES = f"{SCAN_UPLOADS}/{{{{scan_id}}}}"
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
    uploads = SCAN_UPLOADS.format(segment=settings.tenant_segment)
    mapper = Mapper(kit.view, generated_models(scans))

    async def bucket_after(request: Request, tenant_id: str, scan_id: str, action: Action) -> str:
        """The tenant's bucket, once the caller of the request may take ``action`` on the scan."""
        checked = await kit.require_aggregate(
            request.headers.get("authorization"), tenant_id, SCANS, scan_id, action
        )
        return await kit.bucket_of(checked.caller_access.tenant)

    @app.post(uploads, status_code=201)
    async def post_scan(
        t: str, request: Request, label: str, file_name: str, scan_of: str | None = None
    ) -> Response:
        """Write a scan: the bytes of the body to the tenant's bucket and its record through a session."""
        checked = await kit.require(request.headers.get("authorization"), t, Action.MODIFY)
        tenant = checked.caller_access.tenant
        data = await limited_body(request, kit.max_body_bytes)
        iri = str(kit.iris.mint_aggregate(tenant, "scan", SCANS))
        scan = Scan(
            id=iri,
            label=label,
            file_name=file_name,
            media_type=request.headers.get("content-type", OCTET_STREAM),
            byte_size=len(data),
            sha256=hashlib.sha256(data).hexdigest(),
            scan_of=scan_of,
        )
        bucket, scan_id = await kit.bucket_of(tenant), iri.rsplit("/", 1)[-1]
        await kit.files.put(bucket, scan_id, data)
        try:
            async with kit.session(tenant, checked.principal) as session:
                work = UnitOfWork(session, mapper)
                work.add(scan)
                await work.commit()
        except Exception:
            with suppress(Exception):  # a failing cleanup must not hide the error that caused it
                await kit.files.delete(bucket, scan_id)  # the record and its bytes change together
            raise
        return Response(
            status_code=201,
            headers={"Location": f"/{settings.tenant_segment}/{t}/{SCANS}/{scan_id}"},
        )

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
