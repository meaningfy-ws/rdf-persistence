"""The IRI policy and ``Iris``, which derive the IRIs and resource names the policy shapes (PD-4, PD-6, PD-6a).

The policy, its templates and ids, ``Iris``, ``DEFAULT_IRIS`` and the wrappers over it are here; what no
policy changes (the layout of graph IRIs, skolem IRIs, database names) is in ``domain.layout``, which
this module uses. The policy is a technical model, so none of this can be in the domain layer.
"""

import re
import secrets
from collections.abc import Callable
from functools import cached_property
from typing import Any
from urllib.parse import quote
from uuid import uuid4

from rdflib import URIRef

from rdf_persistence.domain.exceptions import InvalidIri, NotFound
from rdf_persistence.domain.layout import (
    _SEGMENT,
    APPLICATION_ID,
    LAYOUT_WORDS,
    LOADED_GRAPH_TYPE,
    _segment,
    is_canonical_uuid,
    tenant_name_prefix,
    toolkit_principal_iri,
)
from rdf_persistence.services.generated.service.rp_service import (
    IdKind,
    IdSpec,
    IriPolicy,
    ServiceSettings,
)
from rdf_persistence.services.generated.templates.rp_templates import (
    IriParts,
    IriTemplateVariables,
)

# The template placeholders and regex group names the matching code tests for.
_OPEN_BRACE = "{"
_TYPE_PLACEHOLDER = "{type}"
_TENANT_ID_PLACEHOLDER = "{tenant_id}"
_DEPLOYMENT_PLACEHOLDER = "{deployment}"
_TENANT_GROUP = "tenant"
_TENANT_ID_GROUP = "tenant_id"


def _default_iris(base: str, tenant_segment: str) -> "Iris":
    """The default policy under ``base`` and ``tenant_segment``, for the module functions below."""
    return Iris(DEFAULT_IRIS.settings.replaced(base=base, tenant_segment=_segment(tenant_segment)))


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
    if _DEPLOYMENT_PLACEHOLDER in template and not settings.deployment:
        raise InvalidIri(f"{name} uses {{deployment}} but the settings set no deployment")


# --- the IRI policy (PD-3 to PD-6, PD-10, PD-11) ------------------------------------------------

DEFAULT_ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyz"
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
    return spec.replaced(alphabet=spec.alphabet or DEFAULT_ALPHABET)


def iri_template_variables(settings: ServiceSettings) -> IriTemplateVariables:
    """The settings' values the IRI templates write in: the base, the deployment (``""`` if none) and the tenant segment."""
    return IriTemplateVariables(
        base=settings.base,
        deployment=settings.deployment or "",
        tenant_segment=settings.tenant_segment,
    )


def effective_policy(policy: IriPolicy | None, settings: ServiceSettings) -> IriPolicy:
    """``policy`` with every unset part filled in, so two spellings of one policy are equal (PD-14b).

    Unset or empty templates take the default; the settings' ``{base}``, ``{deployment}`` and
    ``{tenant_segment}`` are written into them, so changing a setting a template uses changes the
    result; the id specs and the alphabet are filled.
    """
    policy = policy or _DEFAULT_POLICY
    fixed = iri_template_variables(settings)
    update: dict[str, object] = {}
    for name in _TEMPLATE_SLOTS:
        template = str(getattr(policy, name) or getattr(_DEFAULT_POLICY, name))
        for variable, value in fixed.model_dump().items():
            template = template.replace(f"{{{variable}}}", value)
        update[name] = template
    update.update({name: _canonical_spec(getattr(policy, name)) for name in _ID_SPECS})
    return policy.replaced(**update)


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


def _parts(found: re.Match[str]) -> IriParts:
    """The named groups of a match, validated at once (the library boundary of ``re``; PD-5)."""
    return IriParts.model_validate(found.groupdict())


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
        return _TYPE_PLACEHOLDER in self._template("part_template")

    @cached_property
    def _tenant_spec(self) -> IdSpec:
        return self._policy.tenant_id or _UUID4

    @cached_property
    def _object_spec(self) -> IdSpec:
        return self._policy.object_id or _UUID4

    @cached_property
    def _fixed(self) -> IriTemplateVariables:
        return iri_template_variables(self.settings)

    @cached_property
    def application(self) -> URIRef:
        """The IRI of the application: what holds data that belongs to no tenant (the ``application_template``)."""
        return URIRef(self._template("application_template").format(**self._fixed.model_dump()))

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
            self._fixed.deployment,
            APPLICATION_ID,
        }
        for template in _templates(self._policy).values():
            literals = (piece for piece in _VARIABLE.split(template) if piece[:1] != _OPEN_BRACE)
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
        return _compile(template, self._fixed.model_dump(), groups)

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
        """Refuse templates under which the access, meta, registry or provenance IRI of a tenant or of the application is another, its owner's, or an aggregate's (PD-14d).

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
            ("provenance", self.provenance),
        ):
            iri = str(make(tenant))
            if iri in taken:
                raise InvalidIri(
                    f"the {name} template mints the same IRI as the {taken[iri]}: {iri!r}"
                )
            taken[iri] = name
            for pattern in (self._aggregate_re, self._loaded_re):
                found = pattern.fullmatch(iri)
                if found is not None and self._belongs(_parts(found), str(tenant)):
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
        return types if _TYPE_PLACEHOLDER in self._template(slot) else frozenset({""})

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
        if _TENANT_ID_PLACEHOLDER in template and _TENANT_ID_GROUP not in values:
            values[_TENANT_ID_GROUP] = self._id_of(values[_TENANT_GROUP])
        return URIRef(template.format(**self._fixed.model_dump(), **values))

    @staticmethod
    def _allow(template: str, cls_type: str, allowed: frozenset[str]) -> None:
        if _TYPE_PLACEHOLDER in template and cls_type not in allowed:
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
        tenant_id = None if found is None else _parts(found).tenant_id
        if tenant_id is None or tenant_id in self._reserved:
            raise InvalidIri(f"not a tenant IRI of this policy: {tenant_iri!r}")
        return tenant_id

    def access(self, tenant: str) -> URIRef:
        """The IRI of the tenant's access record; its graph is ``graph_iri`` of it."""
        return self._fill(self._template("access_template"), tenant=tenant)

    def meta(self, tenant: str) -> URIRef:
        """The graph that holds the tenant's root object."""
        return self._fill(self._template("meta_template"), tenant=tenant)

    def registry(self, tenant: str) -> URIRef:
        """The graph that holds the tenant's registry entries."""
        return self._fill(self._template("registry_template"), tenant=tenant)

    def provenance(self, tenant: str) -> URIRef:
        """The graph that holds the tenant's activity records; it is not registered."""
        return self._fill(self._template("provenance_template"), tenant=tenant)

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
                **self._fixed.model_dump(), issuer=issuer.rstrip("/"), sub=quote(sub, safe="")
            )
        )

    def resource_name(self, tenant: str) -> str:
        """The tenant's database and bucket name ``{prefix}-t-{tenant id without hyphens}`` (PD-6)."""
        return _resource_name(self.settings.prefix, self.tenant_id_of(tenant))

    # -- matching --

    def _reads_reserved(self, parts: IriParts) -> bool:
        """True when a matched ``id`` is a reserved word, or a matched ``tenant_id`` is one other than ``app``."""
        return parts.id in self._reserved or (
            parts.tenant_id in self._reserved and parts.tenant_id != APPLICATION_ID
        )

    def _belongs(self, parts: IriParts, tenant: str | None) -> bool:
        """True when the match reads no reserved word as an id, and its tenant is ``tenant`` (``None``: not checked)."""
        if self._reads_reserved(parts):
            return False
        if tenant is None:
            return True
        if parts.tenant is not None and parts.tenant != tenant:
            return False
        return parts.tenant_id is None or parts.tenant_id == self._id_of(tenant)

    def is_aggregate(self, tenant: str, iri: str) -> bool:
        """True for what the toolkit mints as an aggregate of ``tenant``, or its root or access record.

        The application has no root object and no access record: for it, only an aggregate.
        Anything else could alias another graph.
        """
        tenant, iri = str(tenant), str(iri)  # a URIRef never equals the str of the same text
        if tenant != str(self.application) and iri in (tenant, str(self.access(tenant))):
            return True
        found = self._aggregate_re.fullmatch(iri)
        return found is not None and self._belongs(_parts(found), tenant)

    def is_loaded_graph(self, tenant: str | None, iri: str, root: str | None = None) -> bool:
        """True when ``iri`` is what the toolkit mints as a loaded graph of ``tenant`` (and of ``root``, when given)."""
        tenant = None if tenant is None else str(tenant)
        root = None if root is None else str(root)
        found = self._loaded_re.fullmatch(str(iri))
        if found is None:
            return False
        parts = _parts(found)
        if not self._belongs(parts, tenant):
            return False
        named = parts.root
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
        parts = _parts(found)
        try:
            tenant = (
                URIRef(parts.tenant)
                if parts.tenant is not None
                else self.tenant(str(parts.tenant_id))
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
