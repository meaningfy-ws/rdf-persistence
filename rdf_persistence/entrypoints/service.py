"""``install_service``: mounts the generic router on a consumer's FastAPI app (PD-13)."""

from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from pathlib import Path
from types import ModuleType
from typing import Any

from fastapi import FastAPI

from rdf_persistence.domain.exceptions import InvalidIri
from rdf_persistence.domain.generated.service.rp_service import ServiceSettings
from rdf_persistence.domain.iris import IdSource, draw_id
from rdf_persistence.entrypoints.kit import ServiceKit
from rdf_persistence.entrypoints.openapi import install_openapi
from rdf_persistence.entrypoints.problems import install_problem_handlers
from rdf_persistence.entrypoints.router import build_router
from rdf_persistence.services.access import AccessRules, load_role_definitions
from rdf_persistence.services.files import FileStore
from rdf_persistence.services.identity import Identity
from rdf_persistence.services.iri_policy_guard import guard_iri_policy
from rdf_persistence.services.store import Store
from rdf_persistence.services.sweep import sweep
from rdf_persistence.services.tenancy import GrantValidator, RootValidator
from rdf_persistence.services.tokens import TokenVerifier


def install_service(
    app: FastAPI,
    *,
    schema: Path,
    generated: ModuleType,
    store: Store,
    files: FileStore,
    identity: Identity,
    verifier: TokenVerifier,
    rules: AccessRules | Path,
    settings: ServiceSettings,
    prefix: str = "",
    id_source: IdSource = draw_id,
    grant_validators: Sequence[GrantValidator] = (),
    root_validators: Sequence[RootValidator] = (),
    workflows: Sequence[Path] = (),
) -> ServiceKit:
    """Serve the application's schema on ``app``: its routes, its problem responses, its start-up.

    ``schema`` is the root LinkML file and ``generated`` the package the generator wrote for it (the
    context, frames and shapes are read from its folder). ``rules`` is the access rules, or the path
    of the role definitions file to build them from. The routes are those of the schema now, so a
    class added to it is served after a restart. Start-up creates the system database if it is
    missing, records the IRI policy or refuses to start when it differs from the recorded one
    (``IriPolicyChanged``), then runs the sweep, before the app serves. The policy comes first: the
    sweep reads the access records through it.

    ``prefix`` is the path the routes are mounted under; the ``Link`` header names the context at
    ``settings.base`` plus that prefix, never at the ``Host`` the request came with. A request body
    may hold at most ``settings.max_body_bytes``. ``id_source`` draws the raw ids of new tenants and
    objects: for tests that need to force a clash; leave it out in a running service.

    ``grant_validators`` and ``root_validators`` are the consumer's own rules on tenant writes: each
    refuses a write by raising ``InvalidBody`` (422), before anything is written (see ``Tenancy``).

    ``workflows`` are the paths of the workflow files, one per workflow, that the classes of the schema
    name with the ``workflow`` annotation. They are checked here, so a bad file stops the service
    before it serves.

    Returns the kit the routes share, for the consumer's own routes: its ``tenancy``, ``store``,
    ``files`` and ``identity``, and ``require`` and ``require_aggregate``, the token and access check
    of the toolkit's routes.

    Raises:
        InvalidIri: the verifier mints principals by another ``principal_template`` than ``settings``
            say (build it with ``iris=Iris(settings)``).
        InvalidRoleDefinition: ``rules`` is a file that is not a valid list of role definitions;
            the message names the entry.
        InvalidWorkflow: A workflow file is not valid, or a class of the schema names a workflow no
            file defines; the message names the file or the workflow and the element.
        IriPolicyChanged: (at start-up) ``settings.iri_policy`` differs from the recorded policy.
        LookupError: The schema has no tenant root class, or no (or several) access record classes.
        OSError: The generated folder lacks the context, the shapes, a frame or the OpenAPI components.
    """
    if isinstance(rules, Path):
        rules = AccessRules(load_role_definitions(rules))
    kit = ServiceKit(
        schema=schema,
        generated=generated,
        store=store,
        files=files,
        identity=identity,
        verifier=verifier,
        rules=rules,
        settings=settings,
        prefix=prefix,
        id_source=id_source,
        grant_validators=grant_validators,
        root_validators=root_validators,
        workflows=workflows,
    )
    _require_same_principals(kit)
    install_problem_handlers(app, settings.base)
    app.include_router(build_router(kit), prefix=prefix)
    install_openapi(app, kit)
    _run_at_startup(app, kit)
    return kit


def _require_same_principals(kit: ServiceKit) -> None:
    """Refuse a verifier that mints principals by another template than the kit's: grants would never match (PD-14c)."""
    ours = kit.iris.effective_policy.principal_template
    theirs = kit.verifier.iris.effective_policy.principal_template
    if ours != theirs:
        raise InvalidIri(
            f"the verifier mints principals by {theirs!r}, the settings say {ours!r}: "
            "build the verifier with iris=Iris(settings)"
        )


def _run_at_startup(app: FastAPI, kit: ServiceKit) -> None:
    """Make the app's lifespan create the system database, guard the IRI policy and sweep, then run the app's own."""
    inner = app.router.lifespan_context

    @asynccontextmanager
    async def lifespan(scope_app: FastAPI) -> AsyncIterator[Any]:
        await kit.tenancy.ensure_system_database()
        await guard_iri_policy(kit.store, kit.tenancy, kit.settings)
        await sweep(kit.tenancy, kit.store, kit.files, kit.settings)
        async with inner(scope_app) as state:
            yield state

    app.router.lifespan_context = lifespan
