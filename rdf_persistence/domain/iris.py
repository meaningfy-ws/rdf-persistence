"""IRIs and resource names of the toolkit (PD-4, PD-6, PD-6a): the only place they are derived."""

import re
import secrets
from collections.abc import Callable
from functools import cached_property
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
ACCESS_SEGMENT = "access"
TOOLKIT_SEGMENT = "toolkit"
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


def mint_tenant_iri(base: str, tenant_segment: str) -> URIRef:
    """A fresh tenant IRI ``{base}{tenant_segment}/{uuid4}``."""
    return URIRef(f"{base}{_segment(tenant_segment)}/{uuid4()}")


def tenant_iri(base: str, tenant_segment: str, tenant_id: str) -> URIRef:
    """The IRI of the tenant whose id in a path is ``tenant_id``: ``{base}{tenant_segment}/{id}``.

    Raises:
        NotFound: ``tenant_id`` is not a canonical UUID, so no tenant has it.
        InvalidIri: ``tenant_segment`` is not a path segment.
    """
    if not is_canonical_uuid(tenant_id):
        raise NotFound(f"no tenant {tenant_id!r}")
    return URIRef(f"{base}{_segment(tenant_segment)}/{tenant_id}")


def aggregate_iri(tenant: str, rp_path: str, aggregate_id: str) -> URIRef:
    """The IRI of the aggregate whose id in a path is ``aggregate_id``: ``{tenant}/{rp_path}/{id}``.

    Raises:
        NotFound: ``aggregate_id`` is not a canonical UUID, so no aggregate has it.
        InvalidIri: ``rp_path`` is not a path segment.
    """
    if not is_canonical_uuid(aggregate_id):
        raise NotFound(f"no aggregate {aggregate_id!r}")
    return DEFAULT_IRIS.aggregate(tenant, "", rp_path, aggregate_id)


def mint_aggregate_iri(tenant_iri: str, rp_path: str) -> URIRef:
    """A fresh aggregate IRI ``{tenant_iri}/{rp_path}/{uuid4}``."""
    return DEFAULT_IRIS.mint_aggregate(tenant_iri, "", rp_path)


def skolem_iri(graph: str) -> URIRef:
    """A fresh skolem IRI under ``graph`` for a blank node (PD-8a)."""
    return URIRef(f"{graph}{GENID}{uuid4()}")


def toolkit_principal_iri(base: str) -> URIRef:
    """The principal the toolkit acts as when it works on its own behalf: ``{base}toolkit``."""
    return URIRef(f"{base}{TOOLKIT_SEGMENT}")


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
    return DEFAULT_IRIS.mint_part("", root_iri, "")


def loaded_graph_iri(aggregate_iri: str) -> URIRef:
    """A fresh IRI for a graph loaded into an aggregate."""
    return DEFAULT_IRIS.mint_loaded_graph("", aggregate_iri)


def meta_graph_iri(tenant_iri: str) -> URIRef:
    """The graph that holds the tenant's root object."""
    return DEFAULT_IRIS.meta(tenant_iri)


def registry_graph_iri(tenant_iri: str) -> URIRef:
    """The graph that holds the tenant's registry entries."""
    return DEFAULT_IRIS.registry(tenant_iri)


def access_iri(tenant_iri: str) -> URIRef:
    """The IRI of the tenant's access record; its graph is ``graph_iri`` of it."""
    return DEFAULT_IRIS.access(tenant_iri)


def tenant_iri_of_access(access_record_iri: str) -> URIRef:
    """The tenant an access record belongs to; the inverse of ``access_iri``."""
    return DEFAULT_IRIS.tenant_of_access(access_record_iri)


def system_database_name(prefix: str) -> str:
    """The system database ``{prefix}-system``."""
    return f"{_prefix(prefix)}{SYSTEM_SUFFIX}"


def tenant_name_prefix(prefix: str) -> str:
    """What every tenant database and bucket name starts with; the sweep matches on it."""
    return f"{_prefix(prefix)}{TENANT_INFIX}"


def _resource_name(prefix: str, tenant_id: str) -> str:
    return f"{tenant_name_prefix(prefix)}{tenant_id.replace('-', '')}"


def tenant_resource_name(prefix: str, tenant_iri: str) -> str:
    """The tenant's database and bucket name ``{prefix}-t-{uuid hex}``."""
    try:
        last = tenant_iri.rsplit("/", 1)[1]
        tenant_id = UUID(last)
    except (IndexError, ValueError) as error:
        raise InvalidIri(f"tenant IRI must end in a UUID: {tenant_iri!r}") from error
    if str(tenant_id) != last:
        raise InvalidIri(f"tenant IRI must end in a canonical UUID: {tenant_iri!r}")
    return _resource_name(prefix, tenant_id.hex)


def principal_iri(issuer: str, subject: str) -> URIRef:
    """The IRI of the person or service account a token's ``sub`` names: ``{issuer}/users/{sub}``.

    The issuer names the provider, so the IRI is unique across providers; percent-encoding keeps a
    ``sub`` from leaving its path segment.
    """
    return DEFAULT_IRIS.principal(issuer, subject)


def check_iri_policy(settings: ServiceSettings) -> None:
    """Refuse the two rules of the IRI policy that span fields, which the generated models cannot state.

    The template variables, the closing id variable and the literal characters are patterns of the
    schema; what remains is that ``{deployment}`` needs a ``deployment`` slug (PD-1) and that a
    ``random`` id has a length. Absent policy and absent id specs are the defaults and always valid.

    Raises:
        InvalidIri: a template uses ``{deployment}`` and no slug is set, or a random id has no length.
    """
    policy = settings.iri_policy
    if policy is None:
        return
    templates = {name: value for name, value in policy if name.endswith("_template") and value}
    for name, template in templates.items():
        if "{deployment}" in template and not settings.deployment:
            raise InvalidIri(f"{name} uses {{deployment}} but the settings set no deployment")
    for name in ("tenant_id", "object_id"):
        spec = getattr(policy, name)
        if spec is not None and spec.kind == IdKind.RANDOM and spec.length is None:
            raise InvalidIri(f"{name}: length is required for random ids")


# --- the IRI policy (PD-3 to PD-6, PD-10, PD-11) ------------------------------------------------

DEFAULT_ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyz"
LOADED_GRAPH_TYPE = "content"
# The words the IRI layout owns; they are never an id (PD-5) and no class may take one as its type (PD-8).
LAYOUT_WORDS = ("content", "graph", "parts", "access", "meta", "registry")
_UUID_PATTERN = "[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
_VARIABLE = re.compile(r"(\{[a-z_]+\})")
_WORD = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
_ANY = ".+"
_NOTHING = "(?!)"
_MAX_DRAWS = 100
_UUID4 = IdSpec(kind=IdKind.UUID4)
_DEFAULT_POLICY = IriPolicy()

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
    one per service: the patterns are compiled on first use and kept. Frozen: no attribute can be set.

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
        check_iri_policy(settings)
        for name, value in (
            ("settings", settings),
            ("root_types", root_types),
            ("owned_types", owned_types),
            ("id_source", id_source),
        ):
            object.__setattr__(self, name, value)

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError(f"Iris is frozen: cannot set {name!r}")

    # -- what the settings say --

    @cached_property
    def _policy(self) -> IriPolicy:
        return self.settings.iri_policy or IriPolicy()

    def _template(self, name: str) -> str:
        return str(getattr(self._policy, name) or getattr(_DEFAULT_POLICY, name))

    @cached_property
    def nested_parts(self) -> bool:
        """True when a part's IRI is under its root's (the part template starts with ``{root}/``, PD-7)."""
        return self._template("part_template").startswith("{root}/")

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
    def _reserved(self) -> frozenset[str]:
        words = {*LAYOUT_WORDS, *self.root_types, *self.owned_types, self._fixed["deployment"]}
        for name, template in self._policy:
            if name.endswith("_template") and template:
                words.update(
                    w
                    for lit in _VARIABLE.split(template)
                    if lit[:1] != "{"
                    for w in _WORD.findall(lit)
                )
        return frozenset(words - {""})

    def _pattern(self, template: str, types: frozenset[str] | str = frozenset()) -> re.Pattern[str]:
        alternation = types if isinstance(types, str) else _alternation(types)
        groups = {
            "tenant": _ANY,
            "root": _ANY,
            "tenant_id": _id_pattern(self._tenant_spec),
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
        return self._pattern(self._template("aggregate_template"), self.root_types)

    @cached_property
    def _loaded_re(self) -> re.Pattern[str]:
        return self._pattern(self._template("loaded_graph_template"), re.escape(LOADED_GRAPH_TYPE))

    @cached_property
    def _tenant_id_re(self) -> re.Pattern[str]:
        return re.compile(_id_pattern(self._tenant_spec))

    @cached_property
    def _object_id_re(self) -> re.Pattern[str]:
        return re.compile(_id_pattern(self._object_spec))

    # -- minting --

    def _new_id(self, spec: IdSpec) -> str:
        for _ in range(_MAX_DRAWS):
            candidate = self.id_source(spec)
            if candidate not in self._reserved:
                return candidate
        raise InvalidIri(f"no id that is not a reserved word after {_MAX_DRAWS} draws")

    def _fill(self, template: str, **values: str) -> URIRef:
        if "{tenant_id}" in template and "tenant_id" not in values:
            values["tenant_id"] = self.tenant_id_of(values["tenant"])
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
        if not self._tenant_id_re.fullmatch(tenant_id):
            raise NotFound(f"no tenant {tenant_id!r}")
        return self._fill(self._template("tenant_template"), tenant_id=tenant_id)

    def tenant_id_of(self, tenant_iri: str) -> str:
        """The id in a tenant IRI.

        Raises:
            InvalidIri: ``tenant_iri`` is not what the tenant template mints.
        """
        found = self._tenant_re.fullmatch(str(tenant_iri))
        if found is None:
            raise InvalidIri(f"not a tenant IRI of this policy: {tenant_iri!r}")
        return found["tenant_id"]

    def access(self, tenant: str) -> URIRef:
        return self._fill(self._template("access_template"), tenant=tenant)

    def meta(self, tenant: str) -> URIRef:
        return self._fill(self._template("meta_template"), tenant=tenant)

    def registry(self, tenant: str) -> URIRef:
        return self._fill(self._template("registry_template"), tenant=tenant)

    def mint_aggregate(self, tenant: str, cls_type: str, rp_path: str) -> URIRef:
        """A fresh aggregate root IRI; ``cls_type`` is the class's ``{type}``, ``rp_path`` its segment."""
        return self._aggregate(tenant, cls_type, rp_path, self._new_id(self._object_spec))

    def aggregate(self, tenant: str, cls_type: str, rp_path: str, id: str) -> URIRef:
        """The IRI of the aggregate whose id in a path is ``id``.

        Raises:
            NotFound: ``id`` cannot be an object id of the policy.
            InvalidIri: ``rp_path`` is not a path segment, or ``cls_type`` not a root type.
        """
        if not self._object_id_re.fullmatch(id):
            raise NotFound(f"no aggregate {id!r}")
        return self._aggregate(tenant, cls_type, rp_path, id)

    def _aggregate(self, tenant: str, cls_type: str, rp_path: str, id: str) -> URIRef:
        template = self._template("aggregate_template")
        self._allow(template, cls_type, self.root_types)
        return self._fill(template, tenant=tenant, type=cls_type, rp_path=_segment(rp_path), id=id)

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

    def _belongs(self, found: re.Match[str], tenant: str | None) -> bool:
        """True when what the match read for the tenant is ``tenant`` (``None``: not checked)."""
        if tenant is None:
            return True
        groups = found.groupdict()
        if groups.get("tenant", tenant) != tenant:
            return False
        return "tenant_id" not in groups or groups["tenant_id"] == self.tenant_id_of(tenant)

    def is_aggregate(self, tenant: str, iri: str) -> bool:
        """True for what the toolkit mints as an aggregate of ``tenant``, or its root or access record.

        Anything else could alias another graph.
        """
        tenant, iri = str(tenant), str(iri)  # a URIRef never equals the str of the same text
        if iri in (tenant, str(self.access(tenant))):
            return True
        found = self._aggregate_re.fullmatch(iri)
        return found is not None and self._belongs(found, tenant)

    def is_loaded_graph(self, tenant: str | None, iri: str, root: str | None = None) -> bool:
        """True when ``iri`` is what the toolkit mints as a loaded graph of ``tenant`` (and of ``root``, when given)."""
        tenant, root = (None if v is None else str(v) for v in (tenant, root))
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
        return root != iri and root != tenant and self.is_aggregate(tenant, root)

    def tenant_of_access(self, access_record_iri: str) -> URIRef:
        """The tenant an access record belongs to; the inverse of ``access`` (PD-10).

        Raises:
            InvalidIri: ``access_record_iri`` is not what the access template mints.
        """
        found = self._access_re.fullmatch(str(access_record_iri))
        if found is None:
            raise InvalidIri(f"not an access record IRI: {access_record_iri!r}")
        groups = found.groupdict()
        if "tenant" in groups:
            return URIRef(groups["tenant"])
        return self.tenant(groups["tenant_id"])


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
