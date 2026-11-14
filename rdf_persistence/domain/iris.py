"""IRIs and resource names of the toolkit (PD-4, PD-6, PD-6a): the only place they are derived."""

import re
import secrets
from collections.abc import Callable
from functools import cached_property
from typing import Any
from urllib.parse import quote
from uuid import UUID, uuid4

from rdflib import URIRef

from rdf_persistence.domain.exceptions import InvalidIri, NotFound
from rdf_persistence.domain.generated.service.rp_service import (
    IdKind,
    IdSpec,
    IriPolicy,
    ServiceSettings,
)

# The patterns of the schema's ``url_segment`` and ``ServiceSettings.prefix`` slots; a test pins them.
_SEGMENT = re.compile(r"[a-z][a-z0-9-]*")
_PREFIX = re.compile(r"[a-z][a-z0-9]{0,19}")
SYSTEM_SUFFIX = "-system"
TENANT_INFIX = "-t-"
# The application is the one place for data that belongs to no tenant: an id no tenant may take.
APPLICATION_ID = "app"
APPLICATION_SUFFIX = "-app"
TOOLKIT_SEGMENT = "toolkit"
# The graph, under the base, that records the effective IRI policy of the deployment (PD-9, PD-14b).
POLICY_SEGMENT = f"{TOOLKIT_SEGMENT}/iri-policy"
GENID = "/.well-known/genid/"


def _segment(value: str) -> str:
    if not _SEGMENT.fullmatch(value):
        raise InvalidIri(f"not a path segment: {value!r}")
    return value


def _prefix(value: str) -> str:
    if not _PREFIX.fullmatch(value):
        raise InvalidIri(
            f"prefix must be a lower case letter then up to 19 lower case letters or digits: {value!r}"
        )
    return value


def graph_iri(root_iri: str) -> URIRef:
    """The named graph of an aggregate (PD-4); never the root's own IRI."""
    return URIRef(f"{root_iri}/graph")


def root_of_graph(graph: str) -> URIRef:
    """The root an aggregate's named graph belongs to; the inverse of ``graph_iri``."""
    root = str(graph).removesuffix("/graph")
    if root == str(graph) or not root:
        raise InvalidIri(f"not the graph of an aggregate: {graph!r}")
    return URIRef(root)


def _default_iris(base: str, tenant_segment: str) -> "Iris":
    """The default policy under ``base`` and ``tenant_segment``, for the module functions below."""
    return Iris(
        DEFAULT_IRIS.settings.model_copy(
            update={"base": base, "tenant_segment": _segment(tenant_segment)}
        )
    )


def mint_tenant_iri(base: str, tenant_segment: str) -> URIRef:
    """A fresh tenant IRI ``{base}{tenant_segment}/{uuid4}``."""
    return _default_iris(base, tenant_segment).mint_tenant()


def tenant_iri(base: str, tenant_segment: str, tenant_id: str) -> URIRef:
    """The IRI of the tenant whose id in a path is ``tenant_id``: ``{base}{tenant_segment}/{id}``.

    Raises:
        NotFound: ``tenant_id`` is not a canonical UUID, so no tenant has it.
        InvalidIri: ``tenant_segment`` is not a path segment.
    """
    return _default_iris(base, tenant_segment).tenant(tenant_id)


def aggregate_iri(tenant: str, rp_path: str, aggregate_id: str) -> URIRef:
    """The IRI of the aggregate whose id in a path is ``aggregate_id``: ``{tenant}/{rp_path}/{id}``.

    Raises:
        NotFound: ``aggregate_id`` is not a canonical UUID, so no aggregate has it.
        InvalidIri: ``rp_path`` is not a path segment.
    """
    return DEFAULT_IRIS.aggregate(tenant, cls_type="", rp_path=rp_path, object_id=aggregate_id)


def mint_aggregate_iri(tenant_iri: str, rp_path: str) -> URIRef:
    """A fresh aggregate IRI ``{tenant_iri}/{rp_path}/{uuid4}``."""
    return DEFAULT_IRIS.mint_aggregate(tenant_iri, cls_type="", rp_path=rp_path)


def skolem_iri(graph: str) -> URIRef:
    """A fresh skolem IRI under ``graph`` for a blank node (PD-8a)."""
    return URIRef(f"{graph}{GENID}{uuid4()}")


def is_skolem_of(graph: str, term: object) -> bool:
    """Whether ``term`` is a skolem IRI minted under ``graph`` (the inverse of ``skolem_iri``)."""
    return isinstance(term, URIRef) and term.startswith(f"{graph}{GENID}")


def toolkit_principal_iri(base: str) -> URIRef:
    """The principal the toolkit acts as when it works on its own behalf: ``{base}toolkit``."""
    return URIRef(f"{base}{TOOLKIT_SEGMENT}")


def policy_record_iri(base: str) -> URIRef:
    """The graph, and the subject in it, that record the effective IRI policy: ``{base}toolkit/iri-policy``."""
    return URIRef(f"{base}{POLICY_SEGMENT}")


def is_inside_tenant(tenant_iri: str, iri: str) -> bool:
    """True when ``iri`` lies below the tenant's path (the tenant IRI itself does not)."""
    return iri.startswith(f"{tenant_iri}/")


def is_canonical_uuid(text: str) -> bool:
    """True for a UUID in its lower case hyphenated form: the only id the toolkit mints."""
    try:
        return str(UUID(text)) == text
    except ValueError:
        return False


def is_aggregate_iri(tenant_iri: str, iri: str) -> bool:
    """True for what the toolkit mints as an aggregate: the tenant root, its access record, or
    ``{tenant_iri}/{rp_path}/{canonical uuid}``. Anything else could alias another graph."""
    return DEFAULT_IRIS.is_aggregate(tenant_iri, iri)


def is_aggregate_graph_iri(tenant_iri: str, iri: str) -> bool:
    """True when ``iri`` is the ``graph_iri`` of an aggregate of the tenant (never of the tenant root)."""
    return DEFAULT_IRIS.is_aggregate_graph(tenant_iri, iri)


def is_loaded_graph_of(root_iri: str, graph: str) -> bool:
    """True when ``graph`` is exactly ``{root_iri}/content/{canonical uuid}`` (see ``loaded_graph_iri``)."""
    return DEFAULT_IRIS.is_loaded_graph(None, graph, root_iri)


def mint_part_iri(root_iri: str) -> URIRef:
    """A fresh IRI ``{root_iri}/parts/{uuid4}`` for an owned part that has none."""
    return DEFAULT_IRIS.mint_part(tenant="", root=root_iri, cls_type="")


def loaded_graph_iri(aggregate_iri: str) -> URIRef:
    """A fresh IRI for a graph loaded into an aggregate."""
    return DEFAULT_IRIS.mint_loaded_graph(tenant="", root=aggregate_iri)


def system_database_name(prefix: str) -> str:
    """The system database ``{prefix}-system``."""
    return f"{_prefix(prefix)}{SYSTEM_SUFFIX}"


def application_database_name(prefix: str) -> str:
    """The application database ``{prefix}-app``; it never starts with a tenant's ``{prefix}-t-``."""
    return f"{_prefix(prefix)}{APPLICATION_SUFFIX}"


def tenant_name_prefix(prefix: str) -> str:
    """What every tenant database and bucket name starts with; the sweep matches on it."""
    return f"{_prefix(prefix)}{TENANT_INFIX}"


def _resource_name(prefix: str, tenant_id: str) -> str:
    return f"{tenant_name_prefix(prefix)}{tenant_id.replace('-', '')}"


def tenant_resource_name(prefix: str, tenant_iri: str) -> str:
    """The tenant's database and bucket name ``{prefix}-t-{uuid hex}``."""
    last = tenant_iri.rsplit("/", 1)[-1]
    if not is_canonical_uuid(last):
        raise InvalidIri(f"tenant IRI must end in a canonical UUID: {tenant_iri!r}")
    return _resource_name(prefix, last)


def principal_iri(issuer: str, subject: str) -> URIRef:
    """The IRI of the person or service account a token's ``sub`` names: ``{issuer}/users/{sub}``.

    The issuer names the provider, so the IRI is unique across providers; percent-encoding keeps a
    ``sub`` from leaving its path segment.
    """
    return DEFAULT_IRIS.principal(issuer, subject)


def _templates(policy: IriPolicy) -> dict[str, str]:
    """The templates a policy sets, by slot name."""
    return {name: value for name, value in policy if name.endswith("_template") and value}


def check_iri_policy(settings: ServiceSettings) -> None:
    """Refuse what the generated models cannot state.

    The template variables, the closing id variable and the literal characters are patterns of the
    schema; what remains is that ``{deployment}`` needs a ``deployment`` slug (PD-1) and that a
    ``random`` id has a length. Absent policy and absent id specs are the defaults and always valid.
    ``Iris`` also refuses templates whose graphs collide (PD-14d).

    Raises:
        InvalidIri: a template uses ``{deployment}`` and no slug is set, or a random id has no length.
    """
    policy = settings.iri_policy
    if policy is None:
        return
    for name, template in _templates(policy).items():
        _check_template(name, template, settings)
    for name in ("tenant_id", "object_id"):
        spec = getattr(policy, name)
        if spec is not None and spec.kind == IdKind.RANDOM and spec.length is None:
            raise InvalidIri(f"{name}: length is required for random ids")


def _check_template(name: str, template: str, settings: ServiceSettings) -> None:
    """Refuse one template of ``check_iri_policy``: ``{deployment}`` without a slug."""
    if "{deployment}" in template and not settings.deployment:
        raise InvalidIri(f"{name} uses {{deployment}} but the settings set no deployment")


# --- the IRI policy (PD-3 to PD-6, PD-10, PD-11) ------------------------------------------------

DEFAULT_ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyz"
LOADED_GRAPH_TYPE = "content"
# The words the IRI layout owns; they are never an id (PD-5) and no class may take one as its type (PD-8).
LAYOUT_WORDS = (LOADED_GRAPH_TYPE, "graph", "parts", "access", "meta", "registry")
_UUID_PATTERN = "[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
_VARIABLE = re.compile(r"(\{[a-z_]+\})")
_WORD = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
_ANY = ".+"
_NOTHING = "(?!)"
_MAX_RESERVED_REDRAWS = 100
_UUID4 = IdSpec(kind=IdKind.UUID4)
_TEMPLATE_SLOTS = tuple(name for name in IriPolicy.model_fields if name.endswith("_template"))
_DEFAULT_POLICY = IriPolicy()
_ID_SPECS = ("tenant_id", "object_id")


def _canonical_spec(spec: IdSpec | None) -> IdSpec:
    if spec is None or spec.kind == IdKind.UUID4:
        return _UUID4
    return spec.model_copy(update={"alphabet": spec.alphabet or DEFAULT_ALPHABET})


def effective_policy(policy: IriPolicy | None, settings: ServiceSettings) -> IriPolicy:
    """``policy`` with every unset part filled in, so two spellings of one policy are equal (PD-14b).

    Unset or empty templates take the default; the settings' ``{base}``, ``{deployment}`` and
    ``{tenant_segment}`` are written into them, so changing a setting a template uses changes the
    result; the id specs and the alphabet are filled.
    """
    policy = policy or _DEFAULT_POLICY
    fixed = {
        "base": settings.base,
        "deployment": settings.deployment or "",
        "tenant_segment": settings.tenant_segment,
    }
    update: dict[str, object] = {}
    for name in _TEMPLATE_SLOTS:
        template = str(getattr(policy, name) or getattr(_DEFAULT_POLICY, name))
        for variable, value in fixed.items():
            template = template.replace(f"{{{variable}}}", value)
        update[name] = template
    update.update({name: _canonical_spec(getattr(policy, name)) for name in _ID_SPECS})
    return policy.model_copy(update=update)


def policy_differences(stored: IriPolicy, configured: IriPolicy) -> list[str]:
    """The dotted names of the fields on which two policies differ (give effective ones)."""
    return _differences(stored.model_dump(), configured.model_dump(), "")


def _differences(stored: dict[str, Any], configured: dict[str, Any], path: str) -> list[str]:
    found: list[str] = []
    for name in stored:
        if isinstance(stored[name], dict) and isinstance(configured[name], dict):
            found += _differences(stored[name], configured[name], f"{path}{name}.")
        elif stored[name] != configured[name]:
            found.append(f"{path}{name}")
    return found


IdSource = Callable[[IdSpec], str]


def draw_id(spec: IdSpec) -> str:
    """A fresh id by ``spec``: a UUIDv4, or ``length`` characters of its alphabet drawn with ``secrets``."""
    if spec.kind == IdKind.UUID4:
        return str(uuid4())
    alphabet = spec.alphabet or DEFAULT_ALPHABET
    return "".join(secrets.choice(alphabet) for _ in range(spec.length or 0))


def _id_pattern(spec: IdSpec) -> str:
    if spec.kind == IdKind.UUID4:
        return _UUID_PATTERN
    return f"[{spec.alphabet or DEFAULT_ALPHABET}]{{{spec.length}}}"


def _alternation(types: frozenset[str]) -> str:
    return "(?:" + "|".join(map(re.escape, sorted(types))) + ")" if types else _NOTHING


def _compile(template: str, fixed: dict[str, str], groups: dict[str, str]) -> re.Pattern[str]:
    """``template`` as a regex: ``fixed`` variables written in, the others named groups (a repeat is a backreference)."""
    parts: list[str] = []
    seen: set[str] = set()
    for piece in filter(None, _VARIABLE.split(template)):
        name = piece[1:-1]
        if not piece.startswith("{"):
            parts.append(re.escape(piece))
        elif name in fixed:
            parts.append(re.escape(fixed[name]))
        elif name in seen:
            parts.append(f"(?P={name})")
        else:
            seen.add(name)
            parts.append(f"(?P<{name}>{groups[name]})")
    return re.compile("".join(parts), re.DOTALL)


class Iris:
    """Every IRI of a service, minted and checked by the templates of its IRI policy.

    ``root_types`` and ``owned_types`` are the ``{type}`` values of the schema's concrete aggregate roots
    and owned classes (``services.schema_structure.iri_types``); ``id_source`` draws the raw ids. Build
    one per service: the patterns are compiled on first use and kept. Frozen, and it keeps its own copy
    of ``settings``, so nothing the caller does to theirs changes what it mints (PD-12f).

    Raises:
        InvalidIri: the settings fail ``check_iri_policy``.
    """

    settings: ServiceSettings
    root_types: frozenset[str]
    owned_types: frozenset[str]
    id_source: IdSource

    def __init__(
        self,
        settings: ServiceSettings,
        root_types: frozenset[str] = frozenset(),
        owned_types: frozenset[str] = frozenset(),
        id_source: IdSource = draw_id,
    ) -> None:
        own = settings.model_copy(deep=True)
        check_iri_policy(own)
        # not a dataclass: the model guard keeps dataclasses out of the domain (models come from LinkML)
        for name, value in (
            ("settings", own),
            ("root_types", root_types),
            ("owned_types", owned_types),
            ("id_source", id_source),
        ):
            object.__setattr__(self, name, value)
        self._require_application_iri()
        self._require_distinct_graphs()
        self._require_application_apart()

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError(f"Iris is frozen: cannot set {name!r}")

    # -- what the settings say --

    @cached_property
    def effective_policy(self) -> IriPolicy:
        """The policy with every unset part filled in and the settings written into the templates (PD-14b)."""
        return effective_policy(self.settings.iri_policy, self.settings)

    @cached_property
    def _policy(self) -> IriPolicy:
        return self.settings.iri_policy or IriPolicy()

    def _template(self, name: str) -> str:
        return str(getattr(self._policy, name) or getattr(_DEFAULT_POLICY, name))

    @cached_property
    def nested_parts(self) -> bool:
        """True when a part's IRI is under its root's (the part template starts with ``{root}/``, PD-7)."""
        return self._template("part_template").startswith("{root}/")

    def part_needs_type(self) -> bool:
        """True when the part template writes the class's ``{type}``, so a part of no known class has no IRI."""
        return "{type}" in self._template("part_template")

    @cached_property
    def _tenant_spec(self) -> IdSpec:
        return self._policy.tenant_id or _UUID4

    @cached_property
    def _object_spec(self) -> IdSpec:
        return self._policy.object_id or _UUID4

    @cached_property
    def _fixed(self) -> dict[str, str]:
        return {
            "base": self.settings.base,
            "deployment": self.settings.deployment or "",
            "tenant_segment": self.settings.tenant_segment,
        }

    @cached_property
    def application(self) -> URIRef:
        """The IRI of the application: what holds data that belongs to no tenant (the ``application_template``)."""
        return URIRef(self._template("application_template").format(**self._fixed))

    def _id_of(self, tenant: str) -> str:
        """The id ``{tenant_id}`` stands for in the IRIs of ``tenant``: ``app`` for the application."""
        if str(tenant) == str(self.application):
            return APPLICATION_ID
        return self.tenant_id_of(tenant)

    @cached_property
    def _reserved(self) -> frozenset[str]:
        words = {
            *LAYOUT_WORDS,
            *self.root_types,
            *self.owned_types,
            self._fixed["deployment"],
            APPLICATION_ID,
        }
        for template in _templates(self._policy).values():
            literals = (piece for piece in _VARIABLE.split(template) if piece[:1] != "{")
            words.update(word for literal in literals for word in _WORD.findall(literal))
        return frozenset(words - {""})

    def _pattern(
        self, template: str, types: frozenset[str] | str = frozenset(), application: bool = False
    ) -> re.Pattern[str]:
        """``template`` as a regex; with ``application`` the ``{tenant_id}`` may also be ``app`` (only the application's aggregates)."""
        alternation = types if isinstance(types, str) else _alternation(types)
        tenant_id = _id_pattern(self._tenant_spec)
        groups = {
            "tenant": _ANY,
            "root": _ANY,
            "tenant_id": f"(?:{tenant_id}|{APPLICATION_ID})" if application else tenant_id,
            "id": _id_pattern(self._object_spec),
            "rp_path": _SEGMENT.pattern,
            "type": alternation,
        }
        return _compile(template, self._fixed, groups)

    @cached_property
    def _tenant_re(self) -> re.Pattern[str]:
        return self._pattern(self._template("tenant_template"))

    @cached_property
    def _access_re(self) -> re.Pattern[str]:
        return self._pattern(self._template("access_template"))

    @cached_property
    def _aggregate_re(self) -> re.Pattern[str]:
        return self._pattern(
            self._template("aggregate_template"), self.root_types, application=True
        )

    @cached_property
    def _loaded_re(self) -> re.Pattern[str]:
        return self._pattern(
            self._template("loaded_graph_template"), re.escape(LOADED_GRAPH_TYPE), application=True
        )

    @cached_property
    def _tenant_id_re(self) -> re.Pattern[str]:
        return re.compile(_id_pattern(self._tenant_spec))

    @cached_property
    def _object_id_re(self) -> re.Pattern[str]:
        return re.compile(_id_pattern(self._object_spec))

    def _require_application_iri(self) -> None:
        """Refuse an application IRI outside the base, on the toolkit's own IRI, or one that reads as a tenant.

        Raises:
            InvalidIri: the ``application_template`` mints such an IRI.
        """
        iri, base = str(self.application), self.settings.base
        toolkit = str(toolkit_principal_iri(base))
        if not iri.startswith(base) or iri == base:
            raise InvalidIri(f"the application template mints an IRI outside the base: {iri!r}")
        if iri == toolkit or iri.startswith(f"{toolkit}/"):
            raise InvalidIri(f"the application template mints the toolkit's own IRI: {iri!r}")
        if self._tenant_re.fullmatch(iri):
            raise InvalidIri(
                f"the application template mints an IRI that reads as a tenant: {iri!r}"
            )

    def _require_distinct_graphs(self) -> None:
        """Refuse templates under which the access, meta or registry IRI of a tenant or of the application is another, its owner's, or an aggregate's (PD-14d).

        Raises:
            InvalidIri: two of the IRIs coincide, or one reads as an aggregate or a loaded graph.
        """
        tenant = self._probe_tenant()
        if tenant is not None:  # else no id can be drawn: minting a tenant fails on its own, loudly
            self._require_distinct_graphs_of(tenant)
        self._require_distinct_graphs_of(self.application)

    def _require_distinct_graphs_of(self, tenant: URIRef) -> None:
        taken = {str(tenant): "tenant"}
        for name, make in (
            ("access", self.access),
            ("meta", self.meta),
            ("registry", self.registry),
        ):
            iri = str(make(tenant))
            if iri in taken:
                raise InvalidIri(
                    f"the {name} template mints the same IRI as the {taken[iri]}: {iri!r}"
                )
            taken[iri] = name
            for pattern in (self._aggregate_re, self._loaded_re):
                found = pattern.fullmatch(iri)
                if found is not None and self._belongs(found, str(tenant)):
                    raise InvalidIri(
                        f"the {name} template mints an IRI that reads as an aggregate: {iri!r}"
                    )

    def _require_application_apart(self) -> None:
        """Refuse templates under which the application's IRIs read as a tenant's, or a tenant as the application's (D-4).

        Raises:
            InvalidIri: an aggregate, part or loaded graph of the application matches the tenant
                template, or a tenant is taken as an aggregate or loaded graph of the application.
        """
        refusal = "the application's IRIs read as a tenant's under these templates"
        for iri in self._application_probes():
            if self._tenant_re.fullmatch(iri):
                raise InvalidIri(f"{refusal}: {iri!r}")
        tenant, application = self._probe_tenant(), str(self.application)
        if tenant is not None and (
            self.is_aggregate(application, tenant) or self.is_loaded_graph(application, tenant)
        ):
            raise InvalidIri(f"{refusal}: the tenant {str(tenant)!r} is one of its aggregates")

    def _application_probes(self) -> list[str]:
        """One aggregate, part and loaded graph of the application per type the templates write (ids from ``draw_id``, like ``_probe_tenant``)."""
        application, spec = str(self.application), self._object_spec
        aggregates = [
            str(self._aggregate(application, kind, "probe", draw_id(spec)))
            for kind in self._probe_types("aggregate_template", self.root_types)
        ]
        root = aggregates[0] if aggregates else application
        parts = [
            self._fill(
                self._template("part_template"),
                tenant=application,
                root=root,
                type=kind,
                id=draw_id(spec),
            )
            for kind in self._probe_types("part_template", self.owned_types)
        ]
        loaded = self._fill(
            self._template("loaded_graph_template"),
            tenant=application,
            root=root,
            type=LOADED_GRAPH_TYPE,
            id=draw_id(spec),
        )
        return [*aggregates, *map(str, parts), str(loaded)]

    def _probe_types(self, slot: str, types: frozenset[str]) -> frozenset[str]:
        """The ``{type}`` values a template is probed with: its class types, or one empty type when it writes none."""
        return types if "{type}" in self._template(slot) else frozenset({""})

    def _probe_tenant(self) -> URIRef | None:
        for _ in range(_MAX_RESERVED_REDRAWS):
            candidate = draw_id(self._tenant_spec)
            if candidate not in self._reserved:
                return self.tenant(candidate)
        return None

    # -- minting --

    def _new_id(self, spec: IdSpec) -> str:
        for _ in range(_MAX_RESERVED_REDRAWS):
            candidate = self.id_source(spec)
            if candidate not in self._reserved:
                return candidate
        raise InvalidIri(f"no id that is not a reserved word after {_MAX_RESERVED_REDRAWS} draws")

    def _fill(self, template: str, **values: str) -> URIRef:
        if "{tenant_id}" in template and "tenant_id" not in values:
            values["tenant_id"] = self._id_of(values["tenant"])
        return URIRef(template.format(**self._fixed, **values))

    @staticmethod
    def _allow(template: str, cls_type: str, allowed: frozenset[str]) -> None:
        if "{type}" in template and cls_type not in allowed:
            raise InvalidIri(f"type {cls_type!r} is not one of {sorted(allowed)}")

    def mint_tenant(self) -> URIRef:
        """A fresh tenant IRI. A clash with a stored tenant is the caller's to check (PD-5)."""
        return self.tenant(self._new_id(self._tenant_spec))

    def tenant(self, tenant_id: str) -> URIRef:
        """The IRI of the tenant whose id in a path is ``tenant_id``.

        Raises:
            NotFound: ``tenant_id`` cannot be an id of the policy.
        """
        if not self._tenant_id_re.fullmatch(tenant_id) or tenant_id in self._reserved:
            raise NotFound(f"no tenant {tenant_id!r}")
        return self._fill(self._template("tenant_template"), tenant_id=tenant_id)

    def tenant_id_of(self, tenant_iri: str) -> str:
        """The id in a tenant IRI.

        Raises:
            InvalidIri: ``tenant_iri`` is not what the tenant template mints.
        """
        found = self._tenant_re.fullmatch(str(tenant_iri))
        if found is None or found["tenant_id"] in self._reserved:
            raise InvalidIri(f"not a tenant IRI of this policy: {tenant_iri!r}")
        return found["tenant_id"]

    def access(self, tenant: str) -> URIRef:
        """The IRI of the tenant's access record; its graph is ``graph_iri`` of it."""
        return self._fill(self._template("access_template"), tenant=tenant)

    def meta(self, tenant: str) -> URIRef:
        """The graph that holds the tenant's root object."""
        return self._fill(self._template("meta_template"), tenant=tenant)

    def registry(self, tenant: str) -> URIRef:
        """The graph that holds the tenant's registry entries."""
        return self._fill(self._template("registry_template"), tenant=tenant)

    def mint_aggregate(self, tenant: str, cls_type: str, rp_path: str) -> URIRef:
        """A fresh aggregate root IRI; ``cls_type`` is the class's ``{type}``, ``rp_path`` its segment."""
        return self._aggregate(tenant, cls_type, rp_path, self._new_id(self._object_spec))

    def aggregate(self, tenant: str, cls_type: str, rp_path: str, object_id: str) -> URIRef:
        """The IRI of the aggregate whose id in a path is ``object_id``.

        Raises:
            NotFound: ``object_id`` cannot be an object id of the policy.
            InvalidIri: ``rp_path`` is not a path segment, or ``cls_type`` not a root type.
        """
        if not self._object_id_re.fullmatch(object_id) or object_id in self._reserved:
            raise NotFound(f"no aggregate {object_id!r}")
        return self._aggregate(tenant, cls_type, rp_path, object_id)

    def _aggregate(self, tenant: str, cls_type: str, rp_path: str, object_id: str) -> URIRef:
        template = self._template("aggregate_template")
        self._allow(template, cls_type, self.root_types)
        return self._fill(
            template, tenant=tenant, type=cls_type, rp_path=_segment(rp_path), id=object_id
        )

    def mint_part(self, tenant: str, root: str, cls_type: str) -> URIRef:
        """A fresh IRI for an owned part of class type ``cls_type`` that has none."""
        template = self._template("part_template")
        self._allow(template, cls_type, self.owned_types)
        return self._fill(
            template, tenant=tenant, root=root, type=cls_type, id=self._new_id(self._object_spec)
        )

    def mint_loaded_graph(self, tenant: str, root: str) -> URIRef:
        """A fresh IRI for a graph loaded into the aggregate ``root``."""
        return self._fill(
            self._template("loaded_graph_template"),
            tenant=tenant,
            root=root,
            type=LOADED_GRAPH_TYPE,
            id=self._new_id(self._object_spec),
        )

    def principal(self, issuer: str, sub: str) -> URIRef:
        """The IRI of the person or service account a token's ``sub`` names; ``sub`` stays in one segment."""
        return URIRef(
            self._template("principal_template").format(
                **self._fixed, issuer=issuer.rstrip("/"), sub=quote(sub, safe="")
            )
        )

    def resource_name(self, tenant: str) -> str:
        """The tenant's database and bucket name ``{prefix}-t-{tenant id without hyphens}`` (PD-6)."""
        return _resource_name(self.settings.prefix, self.tenant_id_of(tenant))

    # -- matching --

    def _reads_reserved(self, groups: dict[str, str | None]) -> bool:
        """True when a matched ``id`` is a reserved word, or a matched ``tenant_id`` is one other than ``app``."""
        tenant_id = groups.get("tenant_id")
        return groups.get("id") in self._reserved or (
            tenant_id in self._reserved and tenant_id != APPLICATION_ID
        )

    def _belongs(self, found: re.Match[str], tenant: str | None) -> bool:
        """True when the match reads no reserved word as an id, and its tenant is ``tenant`` (``None``: not checked)."""
        groups = found.groupdict()
        if self._reads_reserved(groups):
            return False
        if tenant is None:
            return True
        if groups.get("tenant", tenant) != tenant:
            return False
        return "tenant_id" not in groups or groups["tenant_id"] == self._id_of(tenant)

    def is_aggregate(self, tenant: str, iri: str) -> bool:
        """True for what the toolkit mints as an aggregate of ``tenant``, or its root or access record.

        The application has no root object and no access record: for it, only an aggregate.
        Anything else could alias another graph.
        """
        tenant, iri = str(tenant), str(iri)  # a URIRef never equals the str of the same text
        if tenant != str(self.application) and iri in (tenant, str(self.access(tenant))):
            return True
        found = self._aggregate_re.fullmatch(iri)
        return found is not None and self._belongs(found, tenant)

    def is_loaded_graph(self, tenant: str | None, iri: str, root: str | None = None) -> bool:
        """True when ``iri`` is what the toolkit mints as a loaded graph of ``tenant`` (and of ``root``, when given)."""
        tenant = None if tenant is None else str(tenant)
        root = None if root is None else str(root)
        found = self._loaded_re.fullmatch(str(iri))
        if found is None or not self._belongs(found, tenant):
            return False
        named = found.groupdict().get("root")
        if root is not None and named is not None:
            return named == root
        return tenant is None or named is None or self.is_aggregate(tenant, named)

    def is_aggregate_graph(self, tenant: str, iri: str) -> bool:
        """True when ``iri`` is the ``graph_iri`` of an aggregate of ``tenant`` (never of the tenant root)."""
        tenant, iri = str(tenant), str(iri)
        root = iri.removesuffix("/graph")
        not_a_graph_root = (iri, tenant, str(self.access(tenant)))
        return root not in not_a_graph_root and self.is_aggregate(tenant, root)

    def tenant_of_access(self, access_record_iri: str) -> URIRef:
        """The tenant an access record belongs to; the inverse of ``access`` (PD-10).

        Raises:
            InvalidIri: ``access_record_iri`` is not what the access template mints.
        """
        found = self._access_re.fullmatch(str(access_record_iri))
        if found is None:
            raise InvalidIri(f"not an access record IRI: {access_record_iri!r}")
        groups = found.groupdict()
        try:
            tenant = (
                URIRef(groups["tenant"]) if "tenant" in groups else self.tenant(groups["tenant_id"])
            )
        except NotFound as error:  # a reserved word where the tenant id stands
            raise InvalidIri(f"not an access record IRI: {access_record_iri!r}") from error
        if self.access(tenant) != URIRef(str(access_record_iri)) or not self._tenant_re.fullmatch(
            str(tenant)
        ):
            raise InvalidIri(f"not an access record IRI: {access_record_iri!r}")
        return tenant


# The default policy for the module functions above: their templates ignore the base and the segment.
DEFAULT_IRIS = Iris(
    ServiceSettings(
        base="https://default.invalid/",
        prefix="rp",
        tenant_segment="tenants",
        creator_role="owner",
        roles_claim="roles",
    )
)
