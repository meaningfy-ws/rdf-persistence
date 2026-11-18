"""``install_service``: mounts the generic router on a consumer's FastAPI app (PD-13)."""

import asyncio
from collections.abc import AsyncIterator, Mapping, Sequence
from contextlib import asynccontextmanager
from pathlib import Path
from types import ModuleType
from typing import Any

from fastapi import FastAPI

from rdf_persistence.core.domain.exceptions import InvalidIri
from rdf_persistence.entrypoints.kit import ServiceKit
from rdf_persistence.entrypoints.openapi import install_openapi
from rdf_persistence.entrypoints.problems import install_problem_handlers
from rdf_persistence.entrypoints.router import build_router
from rdf_persistence.files.services.files import FileStore
from rdf_persistence.iris.services.generated.rp_iris_services import ServiceSettings
from rdf_persistence.iris.services.iris import IdSource, draw_id
from rdf_persistence.persistence.services.store import Store
from rdf_persistence.services.access import AccessRules, load_role_definitions
from rdf_persistence.services.events import EventBus
from rdf_persistence.services.generated.settings.rp_settings import ToolkitSettings
from rdf_persistence.services.identity import Identity
from rdf_persistence.services.iri_policy_guard import guard_iri_policy
from rdf_persistence.services.messagebus import MessageBus
from rdf_persistence.services.migration_runner import migrate_shared, migrate_tenants
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
    migrations: Path,
    prefix: str = "",
    id_source: IdSource = draw_id,
    grant_validators: Sequence[GrantValidator] = (),
    root_validators: Sequence[RootValidator] = (),
    workflows: Sequence[Path] = (),
    bus: MessageBus | None = None,
    stores: Mapping[str, Store] = {},
    event_bus: EventBus | None = None,
    toolkit: ToolkitSettings | None = None,
) -> ServiceKit:
    """Serve the application's schema on ``app``: its routes, its problem responses, its start-up.

    ``schema`` is the root LinkML file and ``generated`` the package the generator wrote for it (the
    context, frames and shapes are read from its folder). ``rules`` is the access rules, or the path
    of the role definitions file to build them from. The routes are those of the schema now, so a
    class added to it is served after a restart. Start-up creates the system database if it is
    missing, records the IRI policy or refuses to start when it differs from the recorded one
    (``IriPolicyChanged``), creates the application database, migrates the shared databases
    (``MigrationFailed`` stops the start), runs the sweep, then migrates the tenants, before the app
    serves. The policy comes first: the sweep reads the access records through it. The shared
    databases are migrated before the sweep, which decodes the access records in their current shape.
    A tenant whose migration fails is set aside: its requests answer ``503`` (``tenant-behind``) and
    the other tenants are served.

    ``migrations`` is the folder of the application's migration files, one chain for the schema's
    ``version``; the toolkit's own chain ships in the package. Both are checked here, so a bad chain
    stops the service before it serves.

    ``prefix`` is the path the routes are mounted under; the ``Link`` header names the context at
    ``settings.base`` plus that prefix, never at the ``Host`` the request came with. A request body
    may hold at most ``settings.max_body_bytes``. ``id_source`` draws the raw ids of new tenants and
    objects: for tests that need to force a clash; leave it out in a running service.

    ``grant_validators`` and ``root_validators`` are the consumer's own rules on tenant writes: each
    refuses a write by raising ``InvalidBody`` (422), before anything is written (see ``Tenancy``).

    ``workflows`` are the paths of the workflow files, one per workflow, that the classes of the schema
    name with the ``workflow`` annotation. They are checked here, so a bad file stops the service
    before it serves.

    ``bus`` is the message bus the commits of tenant and application databases are published to; it is
    ``kit.bus``, which the consumer may also set later, once the handlers' dependencies exist.

    ``store`` is the ``default`` store, which holds the system database and the tenants the generic
    ``POST`` creates (DEC-1). ``stores`` are further stores by name; a consumer creates a tenant on one
    with ``kit.tenancy.create(..., store=name)``. A name is never ``default``, and one ``Store`` object is
    wired once. Start-up refuses (``StoreNotWired``) an access record that names a store not wired here,
    before any route is served.

    ``event_bus`` carries the commits to the other deployments (aggregate-events). Its consumer starts
    with the app, with ``kit.receive``, and stops with it. Every commit is relayed (to the live
    subscribers too) whether or not there is an event bus.

    ``toolkit`` holds the deployment values of the toolkit's own pieces (a fresh ``ToolkitSettings``,
    every default, unless given): the kit gives ``limits`` to its documents, mapper and restore,
    ``events`` to its hub and relay, and the events route its ``sse``. The ``http``, ``jwks`` and
    ``directory`` groups are for the adapters your composition root builds.

    Returns the kit the routes share, for the consumer's own routes: its ``tenancy``, ``store``,
    ``files`` and ``identity``, and ``require`` and ``require_aggregate``, the token and access check
    of the toolkit's routes.

    Raises:
        ValueError: ``stores`` has the key ``default``, or one ``Store`` object is wired under two names
            (the default included); the message names the key. Or ``event_bus`` is given and ``settings.deployment`` is empty: the deployments
            could not tell their own messages from the others'.
        StoreNotWired: (at start-up) an access record names a store that is not wired.
        InvalidIri: the verifier mints principals by another ``principal_template`` than ``settings``
            say (build it with ``iris=Iris(settings)``).
        InvalidRoleDefinition: ``rules`` is a file that is not a valid list of role definitions;
            the message names the entry.
        InvalidWorkflow: A workflow file is not valid, or a class of the schema names a workflow no
            file defines; the message names the file or the workflow and the element.
        InvalidMigration: A chain of migration files is not valid (a fork, a gap, a file that does not
            load); the message names the files.
        IriPolicyChanged: (at start-up) ``settings.iri_policy`` differs from the recorded policy.
        MigrationFailed: (at start-up) a migration of the system or the application database failed.
        LookupError: The schema has no tenant root class, or no (or several) access record classes.
        OSError: The generated folder lacks the context, the shapes, a frame or the OpenAPI components.
    """
    if event_bus is not None and not settings.deployment:
        raise ValueError(
            "an event bus needs settings.deployment: it names the origin of each message"
        )
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
        migrations=migrations,
        prefix=prefix,
        id_source=id_source,
        grant_validators=grant_validators,
        root_validators=root_validators,
        workflows=workflows,
        stores=stores,
        event_bus=event_bus,
        toolkit=toolkit,
    )
    kit.bus = bus
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
    """Make the app's lifespan create the system database, guard the IRI policy, create the application database, migrate the shared databases, sweep and migrate the tenants (PD-9), then run the app's own."""
    inner = app.router.lifespan_context

    @asynccontextmanager
    async def lifespan(scope_app: FastAPI) -> AsyncIterator[Any]:
        await kit.tenancy.ensure_system_database()
        await guard_iri_policy(kit.store, kit.tenancy, kit.settings)
        await kit.tenancy.ensure_application_database()
        await migrate_shared(kit.tenancy, kit.store, kit.chains)
        await sweep(kit.tenancy, kit.store, kit.files, kit.settings)
        await migrate_tenants(kit.tenancy, kit.store, kit.chains)
        if kit.event_bus is not None:
            await kit.event_bus.start(kit.receive)
        relay = asyncio.create_task(kit.relay.run())
        try:
            async with inner(scope_app) as state:
                yield state
        finally:
            relay.cancel()
            await asyncio.gather(relay, return_exceptions=True)
            if kit.event_bus is not None:
                await kit.event_bus.close()

    app.router.lifespan_context = lifespan
