"""The theme layout table (thematic-structure PD-1, TC-01), read by the tests of several themes.

``LAYOUT`` is the module map of PD-1 as data: every hand-written module with its theme, its layer,
its old path and its new path. A stage turns its themes on (``TURNED_ON``); a row that is on must
stand at its new path and no longer at its old one, and a row that is off must not have moved.
``Move`` is a frozen dataclass of this module: a row of a test table is not model data of the toolkit,
so no LinkML class fits it. The tests of the table are in ``tests/unit/package/test_theme_layout.py``.
"""

import ast
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = "rdf_persistence"
LAYERS = ("domain", "services", "adapters", "entrypoints")
# A stage adds its themes here (PD-1: the stage turns its rows on, and TC-01 then holds them).
TURNED_ON: frozenset[str] = frozenset(
    {
        "core",
        "iris",
        "schema",
        "files",
        "provenance",
        "persistence",
        "migrations",
        "access",
        "tenancy",
        "events",
        "collaboration",
        "messaging",
        "api",
    }
)


@dataclass(frozen=True)
class Move:
    """One row of PD-1: a hand-written module, its theme and layer; ``created`` has no old path."""

    theme: str
    layer: str
    module: str
    created: bool = False

    @property
    def on(self) -> bool:
        return self.theme in TURNED_ON

    @property
    def old(self) -> str | None:
        return None if self.created else f"{PACKAGE}.{self.layer}.{self.module}"

    @property
    def new(self) -> str:
        return f"{PACKAGE}.{self.theme}.{self.layer}.{self.module}"

    @property
    def standing(self) -> str | None:
        """The module path the row expects the module at: the new one when on or created, else the old one.

        A created module has no old path, so it stands at its new one from the task that creates it, even
        while the rest of its theme has not moved yet.
        """
        return self.new if self.on or self.created else self.old


def _rows(theme: str, layer: str, *modules: str, created: tuple[str, ...] = ()) -> tuple[Move, ...]:
    rows = tuple(Move(theme, layer, module) for module in modules)
    return rows + tuple(Move(theme, layer, module, created=True) for module in created)


# PD-1, row by row. `sparql_parsing` and `shacl` are not in PD-1 yet. `sparql_parsing` sits in `core`
# beside `domain/sparql`, which imports it. `shacl` goes to `api/services`: PD-2's rule is the lowest
# theme that uses a module, and its only library user is `api/documents` (the generator's testkit is
# outside the themes; lead's decision D-8).
LAYOUT: tuple[Move, ...] = (
    *_rows(
        "core", "domain", "base", "exceptions", "media", "sparql", "sparql_parsing", "generated"
    ),
    *_rows("core", "services", "artifacts", "yaml_files", "telemetry"),
    *_rows("core", "adapters", "_http"),
    *_rows("iris", "domain", "layout"),
    *_rows("iris", "services", "iris"),
    *_rows("schema", "services", "schema", "schema_structure", "vocabulary"),
    *_rows("files", "domain", "blob_keys"),
    *_rows("files", "services", "files"),
    *_rows("files", "adapters", "s3"),
    # domain-model-per-theme PD-9: a theme that owns domain concepts generates them into its own
    # `domain/generated/` (the package is created by `make generate`, beside a hand-written `__init__`).
    *_rows("provenance", "domain", created=("generated",)),
    *_rows("provenance", "services", "provenance", "visible_part"),
    *_rows(
        "persistence",
        "services",
        "store",
        "session",
        "unique_keys",
        "referrers",
        "listing",
        "loading",
        "jsonld",
        "mapper",
        "decoding",
    ),
    *_rows("persistence", "adapters", "fuseki", created=("sparql_protocol",)),
    *_rows("migrations", "services", "migrations"),
    *_rows("access", "domain", created=("generated",)),
    *_rows("access", "services", "access", "identity", "tokens"),
    *_rows("access", "adapters", "jwks", "zitadel"),
    *_rows(
        "tenancy",
        "services",
        "tenancy",
        "sweep",
        "tenant_sweep",
        "tenant_dump",
        "migration_runner",
        "grant_report",
        "iri_policy_guard",
        "tenant_move",
    ),
    *_rows("events", "services", "events", "event_hub", "event_stream", "relay"),
    *_rows("events", "adapters", "redis_events"),
    *_rows("collaboration", "domain", created=("generated",)),
    *_rows(
        "collaboration",
        "services",
        "discussion",
        "reference_collections",
        "referrer_naming",
        "referenced_removals",
        "workflows",
        "transitions",
        "assignments",
        "aggregate_activities",
        "write_guards",
        "aggregate_validators",
        "collaboration",
    ),
    *_rows("messaging", "services", "messagebus"),
    *_rows("api", "services", "aggregates", "documents", "file_removal", "components", "shacl"),
    *_rows(
        "api",
        "entrypoints",
        "auth",
        "environment",
        "kit",
        "negotiation",
        "openapi",
        "problems",
        "responses",
        "router",
        "service",
        "sse",
    ),
)


@dataclass(frozen=True)
class MovedModule:
    """One generated domain module that left ``core`` for its theme (domain-model-per-theme PD-9).

    The old path is the module of ``core/domain/generated``; the new one is the same module name in
    ``<theme>/domain/generated``. A row has no on switch: it stands at ``new`` from the start.
    """

    theme: str
    module: str

    @property
    def old(self) -> str:
        return f"{PACKAGE}.core.domain.generated.{self.module}"

    @property
    def new(self) -> str:
        return f"{PACKAGE}.{self.theme}.domain.generated.{self.module}"


# DEC-1: the seven modules that leave `core`; `rp_core` and `rp_annotations` stay, `rp.py` is no longer
# written (D-1: the root has no classes of its own, so it writes no module).
MOVED_MODULES: tuple[MovedModule, ...] = (
    MovedModule("access", "rp_access"),
    MovedModule("access", "rp_tenancy"),
    MovedModule("provenance", "rp_provenance"),
    MovedModule("files", "rp_files"),
    MovedModule("collaboration", "rp_collections"),
    MovedModule("collaboration", "rp_discussion"),
    MovedModule("collaboration", "rp_workflow"),
)
# What stays generated in `core`: the two shared modules; the combined RDF artefacts are not Python.
CORE_GENERATED_MODULES = frozenset({"rp_core", "rp_annotations"})
GENERATED_REMOVED = f"{PACKAGE}.core.domain.generated.rp"


# The generated technical packages (PD-1's six groups; the testkit group stays: outside the themes) and
# the module of each that a stage empties class by class.
GROUP_MODULES = {
    "service": f"{PACKAGE}.services.generated.service.rp_service",
    "wire": f"{PACKAGE}.adapters.generated.rp_wire",
    "settings": f"{PACKAGE}.services.generated.settings.rp_settings",
    "templates": f"{PACKAGE}.services.generated.templates.rp_templates",
    "telemetry": f"{PACKAGE}.services.generated.telemetry.rp_telemetry",
}


@dataclass(frozen=True)
class Placed:
    """Classes of one generated group that PD-2 puts in one ``<theme>/<layer>`` generated module.

    A group is split over many themes, so the unit is the class, not the package: the new module is
    ``<theme>.<layer>.generated.rp_<theme>_<layer>`` (PD-2). A row is on with its theme, like a ``Move``.
    """

    theme: str
    layer: str
    group: str
    classes: tuple[str, ...]
    # The module below ``<theme>.<layer>.generated``, when it is not ``rp_<theme>_<layer>``: classes a
    # served module must not carry (the TypeScript and OpenAPI of the toy are byte-identical, TC-07) are
    # a schema of their own, in a group package beside it (PD-4 allows a group segment after ``generated``).
    tail: str = ""

    @property
    def on(self) -> bool:
        return self.theme in TURNED_ON

    @property
    def old(self) -> str:
        return GROUP_MODULES[self.group]

    @property
    def new(self) -> str:
        tail = self.tail or f"rp_{self.theme}_{self.layer}"
        return f"{PACKAGE}.{self.theme}.{self.layer}.generated.{tail}"

    @property
    def standing(self) -> str:
        return self.new if self.on else self.old


# PD-2's class table, row by row. Not named class by class in PD-2, so read from "the term bundles of
# unique_keys, session, listing" and "the migration guard's terms" by the module that builds them
# (`schema/services/vocabulary.py`) and the one that uses each: `RegistryTerms`, `KeyHeldTerms`,
# `KeyBranchTerms` (unique_keys), `OwnerTerms` (session), `ListingTerms` (listing), `StampGuardTerms`
# (migrations). The Zitadel records are every `Zitadel*` class of `rp_wire`.
_ZITADEL = (
    "ZitadelAssertion",
    "ZitadelCreated",
    "ZitadelDetails",
    "ZitadelEmail",
    "ZitadelEmailQuery",
    "ZitadelGrantPage",
    "ZitadelGrantRequest",
    "ZitadelHuman",
    "ZitadelKeyAnswer",
    "ZitadelKeyFile",
    "ZitadelKeyRequest",
    "ZitadelMachineUserAnswer",
    "ZitadelMachineUserRequest",
    "ZitadelOrganisationAnswer",
    "ZitadelOrganisationQuery",
    "ZitadelProjectQuery",
    "ZitadelProjectRequest",
    "ZitadelQuery",
    "ZitadelRoleRequest",
    "ZitadelSearch",
    "ZitadelTokenAnswer",
    "ZitadelTokenRequest",
    "ZitadelUser",
    "ZitadelUserAnswer",
    "ZitadelUserGrant",
    "ZitadelUserPage",
    "ZitadelUserQuery",
    "ZitadelUserState",
    "ZitadelWindow",
)
PLACED: tuple[Placed, ...] = (
    Placed("core", "services", "settings", ("HttpSettings",)),
    Placed("core", "services", "telemetry", ("LogContext",)),
    Placed("iris", "services", "service", ("IdKind", "IdSpec", "IriPolicy", "ServiceSettings")),
    Placed(
        "iris",
        "services",
        "templates",
        ("IriTemplateVariables", "IriParts"),
        tail="templates.rp_iris_templates",
    ),
    Placed(
        "persistence",
        "services",
        "service",
        ("Filter", "Condition", "ListRequest", "ListPlan", "AggregateHead", "Page"),
    ),
    # Not served: `LimitSettings` would add TypeScript to the served `rp_service.ts` (TC-07), so it is a
    # package of its own beside the served module (PD-4 allows a group segment after `generated`).
    Placed(
        "persistence",
        "services",
        "settings",
        ("LimitSettings",),
        tail="settings.rp_persistence_settings",
    ),
    # Not served either: the row of a reverse-reference read, which the session's port hands over
    # (#227). Born after the move, so its group's old module never held it.
    Placed(
        "persistence",
        "services",
        "service",
        ("ReferrerRow",),
        tail="rows.rp_persistence_rows",
    ),
    # D-8: `schema/vocabulary` builds all six term bundles, so `schema` is their lowest
    # user (PD-2); a bundle placed in `persistence` or `migrations` would make `schema` import a higher
    # theme. Their slots range over `SparqlTerm` of `core`, so no slot reaches a class of a higher theme.
    Placed(
        "schema",
        "services",
        "templates",
        (
            "RegistryTerms",
            "KeyHeldTerms",
            "KeyBranchTerms",
            "OwnerTerms",
            "ListingTerms",
            "StampGuardTerms",
        ),
        tail="templates.rp_schema_templates",
    ),
    Placed("persistence", "adapters", "wire", ("FusekiDatasetList", "FusekiDataset")),
    Placed("migrations", "services", "service", ("Migration", "MigrationStep")),
    Placed(
        "access",
        "services",
        "service",
        ("VerifiedCaller", "CallerAccess", "GrantSet", "AccountSummary"),
    ),
    # Not served, like `LimitSettings`: a package of its own beside the served `access` services.
    Placed(
        "access",
        "services",
        "settings",
        ("JwksSettings", "DirectorySettings"),
        tail="settings.rp_access_settings",
    ),
    Placed(
        "access",
        "adapters",
        "wire",
        ("JwtClaims", "DiscoveryDocument", "BadRequestMeans", *_ZITADEL),
    ),
    Placed("tenancy", "services", "service", ("TenantDump", "TenantSummary")),
    Placed("events", "services", "service", ("EventEnvelope",)),
    # Not served, like `LimitSettings`: a package of its own beside the served `events` services.
    Placed(
        "events",
        "services",
        "settings",
        ("EventSettings",),
        tail="settings.rp_events_settings",
    ),
    Placed("collaboration", "services", "service", ("Referrer", "ReferrerList", "MemberList")),
    Placed(
        "api",
        "entrypoints",
        "service",
        ("Problem", "ProblemKind", "ProblemSlug", "Authorised", "LabelUpdate", "TenantCreate"),
    ),
    # Not served, like `LimitSettings`: the settings are no part of the HTTP API's types (TC-07).
    Placed(
        "api",
        "entrypoints",
        "settings",
        ("SseSettings", "ToolkitSettings"),
        tail="settings.rp_api_settings",
    ),
)


def turned_on_classes(placed: tuple[Placed, ...] = PLACED) -> dict[tuple[str, str], str]:
    """``(old module, class) -> new module`` for the placements that are on."""
    return {(p.old, c): p.new for p in placed if p.on for c in p.classes}


def _classes_defined(module: str, root: Path) -> set[str] | None:
    """The classes a module file defines at its top level; None when the file is missing."""
    path = file_of(module, root)
    if not path.is_file():
        return None
    return {
        n.name
        for n in ast.parse(path.read_text(encoding="utf-8")).body
        if isinstance(n, ast.ClassDef)
    }


_GENERATED_BASES = frozenset({"ConfiguredBaseModel", "LinkMLMeta"})


def placed_problems(placed: tuple[Placed, ...], root: Path) -> list[str]:
    """Each placed class must stand in the module its row says; each class of a group needs a row."""
    problems = []
    for p in placed:
        for name in p.classes:
            there = _classes_defined(p.standing, root)
            if p.on and name in (_classes_defined(p.old, root) or set()):
                problems.append(f"{name} is still in {p.old}; it belongs in {p.new}")
            elif there is None or name not in there:
                problems.append(f"{name} is missing from {p.standing} (row {p.old} -> {p.new})")
    for old in sorted({p.old for p in placed}):
        defined = _classes_defined(old, root) or set()
        kept = {c for p in placed if p.old == old and not p.on for c in p.classes}
        moved = {c for p in placed if p.old == old and p.on for c in p.classes}
        problems += [
            f"{name} in {old} has no row in PLACED"
            for name in sorted(defined - kept - moved - _GENERATED_BASES)
        ]
    return problems


def turned_on_pairs(
    rows: tuple[Move, ...] = LAYOUT, moved: tuple[MovedModule, ...] = MOVED_MODULES
) -> tuple[tuple[str, str], ...]:
    """The (old, new) module paths of the rows that are on, and of every moved generated module.

    The guards of the move read these; a ``MovedModule`` has no on switch, so it is always listed.
    """
    pairs = tuple((row.old, row.new) for row in rows if row.on and row.old)
    return pairs + tuple((module.old, module.new) for module in moved)


def moved_module_problems(moved: tuple[MovedModule, ...], root: Path) -> list[str]:
    """What is wrong with the generated modules at ``root`` against the ``MovedModule`` rows."""
    problems = []
    for row in moved:
        if _exists(row.old, root):
            problems.append(f"{row.old} is still in core; it belongs at {row.new}")
        if not _exists(row.new, root):
            problems.append(f"{row.new} is missing (row {row.old} -> {row.new})")
    generated = root / PACKAGE / "core" / "domain" / "generated"
    kept = {p.stem for p in generated.glob("*.py")} - {"__init__"} if generated.is_dir() else set()
    problems += [
        f"{PACKAGE}.core.domain.generated.{name} is not a module core keeps"
        for name in sorted(kept - CORE_GENERATED_MODULES)
        if name not in {row.module for row in moved}
    ]
    return problems


def file_of(module: str, root: Path) -> Path:
    return root / (module.replace(".", "/") + ".py")


def _exists(module: str, root: Path) -> bool:
    folder = root / module.replace(".", "/")
    return file_of(module, root).is_file() or (folder / "__init__.py").is_file()


def _hand_written_modules(root: Path) -> set[str]:
    """The ``.py`` modules directly in a layer folder of the package or of a theme (not generated)."""
    package = root / PACKAGE
    folders = [(layer, package / layer) for layer in LAYERS]
    folders += [
        (f"{theme.name}.{layer}", theme / layer)
        for theme in package.iterdir()
        if theme.is_dir() and (theme / "__init__.py").is_file() and theme.name not in LAYERS
        for layer in LAYERS
    ]
    return {
        f"{PACKAGE}.{prefix}.{path.stem}"
        for prefix, folder in folders
        if folder.is_dir()
        for path in folder.glob("*.py")
        if path.stem != "__init__"
    }


def layout_problems(rows: tuple[Move, ...], root: Path) -> list[str]:
    """What is wrong with the tree at ``root`` against the rows; empty when it matches."""
    problems = []
    for row in rows:
        if row.on and row.old and _exists(row.old, root):
            problems.append(f"{row.old} is still at its old path; it belongs at {row.new}")
        elif row.standing and not _exists(row.standing, root):
            problems.append(f"{row.standing} is missing (row {row.old} -> {row.new})")
    # a ``generated`` row is a package, not a module file: only module files are listed here
    expected = {row.standing for row in rows if row.standing and row.module != "generated"}
    problems += [
        f"{module} has no row in LAYOUT"
        for module in sorted(_hand_written_modules(root) - expected)
    ]
    return problems
