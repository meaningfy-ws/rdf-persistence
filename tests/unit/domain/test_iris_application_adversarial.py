"""``Iris`` for the application under hostile input and unusual policies (app-level-data task 2.1, PD-2, PD-3).

Every test names the production change that would make it fail. The Hypothesis tests state invariants
over many policies (default, flat, ``{tenant_id}``-only templates, short ids, ``{deployment}`` and
``{tenant_segment}``, other application templates); the ids come from a seeded source, so a run is
repeatable (the probe tenant of ``Iris.__init__`` draws with ``secrets`` and never decides a test).
"""

import contextlib
import random
from collections.abc import Callable
from uuid import UUID

import pytest
from hypothesis import HealthCheck, assume, given, settings
from hypothesis import strategies as st
from pydantic import ValidationError
from rdflib import URIRef

from rdf_persistence.domain import iris as iris_module
from rdf_persistence.domain.exceptions import InvalidIri, NotFound
from rdf_persistence.domain.generated.service.rp_service import (
    IdKind,
    IdSpec,
    IriPolicy,
    ServiceSettings,
)
from rdf_persistence.domain.iris import (
    APPLICATION_ID,
    DEFAULT_ALPHABET,
    Iris,
    effective_policy,
    graph_iri,
    policy_differences,
)

BASE = "https://ex.org/"
DEPLOYMENT = "dep1"
UUID_TEXT = "0b9d3c52-6f0e-4a5b-8f21-3c7d9e1a4b60"
ROOTS = frozenset({"template", "book"})
OWNED = frozenset({"chapter"})
FLAT_TENANT = "{base}{tenant_id}"
FLAT_AGGREGATE = "{base}{tenant_id}/{type}/{id}"
FLAT = IriPolicy(tenant_template=FLAT_TENANT, aggregate_template=FLAT_AGGREGATE)
INVARIANTS = settings(
    max_examples=60,
    deadline=None,
    derandomize=True,
    suppress_health_check=list(HealthCheck),
)


def _settings(policy: IriPolicy | None = None, base: str = BASE) -> ServiceSettings:
    return ServiceSettings(
        base=base,
        prefix="lib",
        tenant_segment="tenants",
        creator_role="owner",
        roles_claim="roles",
        deployment=DEPLOYMENT,
        iri_policy=policy,
    )


def _seeded(seed: int) -> Callable[[IdSpec], str]:
    """An id source that draws like ``draw_id`` but from a seeded generator."""
    rng = random.Random(seed)

    def draw(spec: IdSpec) -> str:
        if spec.kind == IdKind.UUID4:
            return str(UUID(int=rng.getrandbits(128), version=4))
        alphabet = spec.alphabet or DEFAULT_ALPHABET
        return "".join(rng.choice(alphabet) for _ in range(spec.length or 0))

    return draw


def _iris(
    policy: IriPolicy | None = None,
    id_source: Callable[[IdSpec], str] | None = None,
    base: str = BASE,
) -> Iris:
    extra = {} if id_source is None else {"id_source": id_source}
    return Iris(_settings(policy, base), ROOTS, OWNED, **extra)  # type: ignore[arg-type]


def _built(policy: IriPolicy, seed: int = 0) -> Iris | None:
    """The ``Iris`` of ``policy``, or None when it is refused; any exception but ``InvalidIri`` fails the test."""
    try:
        return _iris(policy, _seeded(seed))
    except InvalidIri:
        return None


def _scripted(*ids: str) -> Callable[[IdSpec], str]:
    drawn = iter(ids)
    return lambda spec: next(drawn)


def _owned(iris: Iris, owner: str) -> dict[str, str]:
    """Every IRI the toolkit mints for ``owner`` (a tenant or the application), by what it is."""
    root = iris.mint_aggregate(owner, "template", "templates")
    return {
        "owner": str(owner),
        "access": str(iris.access(owner)),
        "meta": str(iris.meta(owner)),
        "registry": str(iris.registry(owner)),
        "aggregate": str(root),
        "aggregate graph": str(graph_iri(str(root))),
        "part": str(iris.mint_part(owner, str(root), "chapter")),
        "loaded graph": str(iris.mint_loaded_graph(owner, str(root))),
    }


def _accepted_by(iris: Iris, owner: str, iri: str) -> list[str]:
    """The matchers of ``Iris`` that take ``iri`` as one of ``owner``'s."""
    found = []
    if iris.is_aggregate(owner, iri):
        found.append("is_aggregate")
    if iris.is_loaded_graph(owner, iri):
        found.append("is_loaded_graph")
    if iris.is_aggregate_graph(owner, iri):
        found.append("is_aggregate_graph")
    return found


# -- the policies the properties range over -------------------------------------------------------


@st.composite
def id_specs(draw: st.DrawFn) -> IdSpec | None:
    if draw(st.booleans()):
        return None
    if draw(st.booleans()):
        return IdSpec(kind=IdKind.UUID4)
    alphabet = draw(st.sampled_from(["ap", "apx", DEFAULT_ALPHABET]))
    return IdSpec(kind=IdKind.RANDOM, length=draw(st.integers(4, 8)), alphabet=alphabet)


@st.composite
def policies(draw: st.DrawFn) -> IriPolicy:
    def one(*choices: str | None) -> str | None:
        return draw(st.sampled_from(choices))

    return IriPolicy(
        tenant_template=one(
            None,
            FLAT_TENANT,
            "{base}{deployment}/{tenant_id}",
            "{base}{tenant_segment}/{tenant_id}",
        ),
        application_template=one(
            None,
            "{base}app",
            "{base}application",
            "{base}{tenant_segment}",
            "{base}tenants/app",
            "{base}{deployment}/app",
        ),
        access_template=one(None, "{base}{tenant_id}/access", "{base}access/{tenant_id}"),
        meta_template=one(None, "{base}{tenant_id}/meta", "{base}meta/{tenant_id}"),
        registry_template=one(None, "{base}{tenant_id}/registry", "{base}registry/{tenant_id}"),
        aggregate_template=one(None, FLAT_AGGREGATE, "{base}{tenant_id}/{id}", "{tenant}/{id}"),
        part_template=one(None, "{base}{tenant_id}/parts/{id}", FLAT_AGGREGATE),
        loaded_graph_template=one(None, FLAT_AGGREGATE, "{base}{tenant_id}/content/{id}"),
        tenant_id=draw(id_specs()),
        object_id=draw(id_specs()),
    )


ACCEPTED = st.tuples(policies(), st.integers(0, 2**32))


# -- 1. nothing changed for tenants; tenants and the application never match each other ----------


TENANT_SHAPED_AGGREGATE = (
    "{tenant}/{id}"  # an aggregate IRI with no type or path: the shape of a tenant's
)


def _tenant_iris_are_not_the_applications(policy: IriPolicy, seed: int) -> None:
    iris = _built(policy, seed)
    assume(iris is not None)
    assert iris is not None
    tenant = str(iris.mint_tenant())
    for name, iri in _owned(iris, tenant).items():
        assert _accepted_by(iris, str(iris.application), iri) == [], (
            f"{name} {iri} of a tenant is taken as the application's under {policy}"
        )


def _application_iris_are_not_a_tenants(policy: IriPolicy, seed: int) -> None:
    iris = _built(policy, seed)
    assume(iris is not None)
    assert iris is not None
    tenant = str(iris.mint_tenant())
    for name, iri in _owned(iris, str(iris.application)).items():
        assert _accepted_by(iris, tenant, iri) == [], (
            f"{name} {iri} of the application is taken as a tenant's under {policy}"
        )


@INVARIANTS
@given(ACCEPTED)
def test_a_tenants_iris_are_never_accepted_for_the_application(case: tuple[IriPolicy, int]) -> None:
    """Fails if ``application=True`` patterns or ``_id_of`` let a tenant's IRI answer for ``A``, or if
    ``Iris`` accepts a policy under which one can (D-4: such policies are refused at construction)."""
    _tenant_iris_are_not_the_applications(*case)


@INVARIANTS
@given(ACCEPTED)
def test_the_applications_iris_are_never_accepted_for_a_tenant(
    case: tuple[IriPolicy, int],
) -> None:
    """Fails if a tenant matcher takes the ``app`` id for any tenant id."""
    _application_iris_are_not_a_tenants(*case)


def _shaped_like_a_tenant() -> Iris:
    policy = IriPolicy(
        application_template="{base}{tenant_segment}", aggregate_template=TENANT_SHAPED_AGGREGATE
    )
    return _iris(policy, _seeded(3))


def test_an_application_that_is_the_tenants_parent_path_with_a_tenant_shaped_aggregate_is_refused() -> (
    None
):
    """Fails if ``A = {base}tenants`` with the aggregate template ``{tenant}/{id}`` is accepted: an aggregate
    of ``A`` may read as a tenant, and a tenant as an aggregate of ``A`` (D-4)."""
    with pytest.raises(InvalidIri, match="read as a tenant's"):
        _shaped_like_a_tenant()


def test_a_tenant_read_as_an_aggregate_of_the_application_is_refused_on_its_own(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fails if the probe tenant is not asked of ``is_aggregate(A, tenant)`` (D-4 b), the refusal that
    stays when no aggregate of ``A`` reads as a tenant: the probes draw ids that no tenant id can spell."""
    tenant_ids = IdSpec(kind=IdKind.RANDOM, length=8, alphabet="ab")
    policy = IriPolicy(
        application_template="{base}{tenant_segment}",
        aggregate_template=TENANT_SHAPED_AGGREGATE,
        tenant_id=tenant_ids,
        object_id=IdSpec(kind=IdKind.RANDOM, length=8),
    )
    # the probes draw with ``secrets``: pin them, so refusal (a) cannot fire first by chance
    monkeypatch.setattr(
        iris_module, "draw_id", lambda spec: "abababab" if spec.alphabet == "ab" else "zzzzzzzz"
    )
    with pytest.raises(InvalidIri, match="is one of its aggregates"):
        _iris(policy, _seeded(3))


SHAPED = "{tenant}/{id}"
APPLICATION_IS_THE_TENANTS_PATH = "{base}{tenant_segment}"
REFUSED_AS_TENANT_SHAPED = {
    "aggregate": IriPolicy(
        application_template=APPLICATION_IS_THE_TENANTS_PATH, aggregate_template=SHAPED
    ),
    "loaded graph": IriPolicy(
        application_template=APPLICATION_IS_THE_TENANTS_PATH, loaded_graph_template=SHAPED
    ),
    "part": IriPolicy(application_template=APPLICATION_IS_THE_TENANTS_PATH, part_template=SHAPED),
}
ACCEPTED_NEAR_MISSES = {
    "the default policy": None,
    "the flat policy": FLAT,
    "A is the tenants' path, the default aggregate": IriPolicy(
        application_template=APPLICATION_IS_THE_TENANTS_PATH
    ),
}


@pytest.mark.parametrize("name", list(REFUSED_AS_TENANT_SHAPED))
def test_a_policy_whose_application_iris_read_as_a_tenants_is_refused(name: str) -> None:
    """Fails if ``_require_application_apart`` skips this kind of IRI (D-4 a)."""
    with pytest.raises(InvalidIri, match="read as a tenant's"):
        _iris(REFUSED_AS_TENANT_SHAPED[name], _seeded(3))


@pytest.mark.parametrize("name", list(ACCEPTED_NEAR_MISSES))
def test_a_policy_whose_application_iris_do_not_read_as_a_tenants_is_accepted(name: str) -> None:
    """Fails if ``_require_application_apart`` refuses what keeps the application apart."""
    _iris(ACCEPTED_NEAR_MISSES[name], _seeded(3))


@INVARIANTS
@given(ACCEPTED)
def test_a_tenant_still_round_trips_whatever_the_application_template(
    case: tuple[IriPolicy, int],
) -> None:
    """Fails if the application support changed what a tenant mints and matches."""
    policy, seed = case
    iris = _built(policy, seed)
    assume(iris is not None)
    assert iris is not None
    tenant = str(iris.mint_tenant())
    owned = _owned(iris, tenant)
    assert iris.tenant_of_access(owned["access"]) == URIRef(tenant), "access gives the tenant back"
    assert iris.tenant(iris.tenant_id_of(tenant)) == URIRef(tenant), "the id gives the tenant back"
    assert iris.is_aggregate(tenant, owned["aggregate"]), "its aggregate is its own"
    assert iris.is_aggregate_graph(tenant, owned["aggregate graph"]), "so is the aggregate graph"
    assert iris.is_loaded_graph(tenant, owned["loaded graph"]), "so is the loaded graph"


def test_a_tenant_whose_id_starts_like_the_application_is_not_the_application() -> None:
    """Fails if ``_belongs`` compares prefixes where it must compare the whole tenant id."""
    policy = FLAT.model_copy(
        update={
            "tenant_id": IdSpec(kind=IdKind.RANDOM, length=5, alphabet="apl"),
            "object_id": IdSpec(kind=IdKind.RANDOM, length=5, alphabet="apl"),
            "application_template": "{base}other",
        }
    )
    iris = _iris(policy, _scripted("appla", "applp"))
    tenant = str(iris.mint_tenant())
    x = str(iris.mint_aggregate(tenant, "book", "books"))
    assert tenant.endswith("appla"), "the tenant id starts with the word app"
    assert not iris.is_aggregate(str(iris.application), x), (
        "and its aggregate is not the application's"
    )
    assert iris.is_aggregate(tenant, x), "it is the tenant's"


# -- 2. the application never reads as a tenant -----------------------------------------------


@INVARIANTS
@given(ACCEPTED)
def test_the_application_is_never_a_tenant_under_any_accepted_policy(
    case: tuple[IriPolicy, int],
) -> None:
    """Fails if ``tenant_id_of``, ``tenant``, ``resource_name`` or ``tenant_of_access`` widen to ``A``."""
    policy, seed = case
    iris = _built(policy, seed)
    assume(iris is not None)
    assert iris is not None
    a = iris.application
    with pytest.raises(InvalidIri):
        iris.tenant_id_of(a)
    with pytest.raises(InvalidIri):
        iris.resource_name(a)
    with pytest.raises(InvalidIri):
        iris.tenant_of_access(iris.access(a))
    with pytest.raises(NotFound):
        iris.tenant(APPLICATION_ID)


@pytest.mark.parametrize("as_text", [str, URIRef], ids=["str", "URIRef"])
def test_the_application_is_no_tenant_whichever_type_carries_it(as_text: type) -> None:
    """Fails if the refusal compares a ``URIRef`` where it must compare the text."""
    iris = _iris(FLAT)
    a = as_text(str(iris.application))
    with pytest.raises(InvalidIri):
        iris.tenant_id_of(a)
    with pytest.raises(InvalidIri):
        iris.tenant_of_access(as_text(str(iris.access(iris.application))))


def test_a_tenant_id_of_three_characters_is_not_in_the_schema() -> None:
    """Fails if the model lets an id be as short as ``app``, the premise of PD-3's refusal of ``A``."""
    for length in (0, 1, 2, 3):
        with pytest.raises(ValidationError):
            IdSpec(kind=IdKind.RANDOM, length=length)


# -- 3. app is never minted ---------------------------------------------------------------------


@pytest.mark.parametrize(
    "policy",
    [None, FLAT, FLAT.model_copy(update={"application_template": "{base}application"})],
    ids=["default", "flat", "flat-other-template"],
)
def test_no_id_is_minted_as_app_whatever_the_id_source_answers(policy: IriPolicy | None) -> None:
    """Fails if ``APPLICATION_ID`` is dropped from ``_reserved`` or checked only for tenants."""
    iris = _iris(policy, _scripted(*([APPLICATION_ID] * 3), "x" * 8))
    x = str(iris.mint_aggregate(iris.application, "template", "templates"))
    assert not x.endswith(f"/{APPLICATION_ID}"), "the first answer, app, is replaced"
    assert x.endswith("x" * 8), "by the next answer"


def test_a_tenant_is_never_minted_with_the_id_app() -> None:
    """Fails if ``mint_tenant`` takes the id source's ``app``."""
    policy = FLAT.model_copy(update={"tenant_id": IdSpec(kind=IdKind.RANDOM, length=4)})
    iris = _iris(policy, _scripted(APPLICATION_ID, APPLICATION_ID, "k3f9"))
    assert iris.tenant_id_of(iris.mint_tenant()) == "k3f9", "app is drawn twice and refused twice"


@pytest.mark.parametrize("owner", ["application", "tenant"])
def test_an_object_is_never_minted_with_the_id_app(owner: str) -> None:
    """Fails if an aggregate, part or loaded graph may take ``app`` as its id."""
    iris = _iris(
        FLAT,
        _scripted(
            "11111111-1111-4111-8111-111111111111", *([APPLICATION_ID] * 4), *[UUID_TEXT] * 4
        ),
    )
    who = str(iris.application) if owner == "application" else str(iris.mint_tenant())
    root = str(iris.mint_aggregate(who, "book", "books"))
    part = str(iris.mint_part(who, root, "chapter"))
    loaded = str(iris.mint_loaded_graph(who, root))
    for name, iri in (("aggregate", root), ("part", part), ("loaded graph", loaded)):
        assert not iri.endswith(f"/{APPLICATION_ID}"), f"the {name} id is not app"


def test_an_id_source_that_only_says_app_is_refused_for_the_application_too() -> None:
    """Fails if the reserved-id loop gives up with another exception, or never gives up."""
    iris = _iris(FLAT, lambda spec: APPLICATION_ID)
    with pytest.raises(InvalidIri):
        iris.mint_aggregate(iris.application, "template", "templates")
    with pytest.raises(InvalidIri):
        iris.mint_tenant()


@pytest.mark.parametrize(
    "template", ["{base}application", "{base}tenants/app", "{base}x/applications"]
)
def test_the_words_of_the_application_template_are_reserved_ids(template: str) -> None:
    """Fails if the literal words of ``application_template`` are left out of ``_reserved``."""
    policy = FLAT.model_copy(update={"application_template": template})
    words = [word for word in template.removeprefix("{base}").split("/")]
    iris = _iris(policy)
    for word in words:
        with pytest.raises(NotFound):
            iris.aggregate(iris.application, "book", "books", word)


def test_an_object_id_of_a_real_application_template_word_is_replaced() -> None:
    """Fails if a minted object id may spell the application template's own path word."""
    policy = FLAT.model_copy(update={"application_template": "{base}application"})
    iris = _iris(policy, _scripted("application", UUID_TEXT))
    x = str(iris.mint_aggregate(iris.application, "book", "books"))
    assert x.endswith(UUID_TEXT), "application is a reserved word of this policy"


# -- 4. the application's own graphs stay distinct, or the policy is refused -------------------


@INVARIANTS
@given(ACCEPTED)
def test_an_accepted_policy_keeps_the_applications_graphs_apart(
    case: tuple[IriPolicy, int],
) -> None:
    """Fails if the application's probe in ``_require_distinct_graphs`` misses a collision."""
    policy, seed = case
    iris = _built(policy, seed)
    assume(iris is not None)
    assert iris is not None
    a = str(iris.application)
    graphs = {
        "A": a,
        "access": str(iris.access(a)),
        "meta": str(iris.meta(a)),
        "registry": str(iris.registry(a)),
    }
    assert len(set(graphs.values())) == 4, f"A, access, meta and registry are four IRIs: {graphs}"
    for name, iri in graphs.items():
        assert not iris.is_loaded_graph(a, iri), f"{name} is not a loaded graph of A"
        assert not iris.is_aggregate_graph(a, iri), f"{name} is not an aggregate graph of A"
    for name in ("meta", "registry"):
        assert not iris.is_aggregate(a, graphs[name]), f"{name} is not an aggregate of A"


COLLIDING = {
    "meta is A": {"meta_template": "{base}{tenant_id}"},
    "registry is A": {"registry_template": "{base}{tenant_id}"},
    "access is A": {"access_template": "{base}{tenant_id}"},
    "meta is access": {
        "meta_template": "{base}{tenant_id}/x",
        "access_template": "{base}{tenant_id}/x",
    },
    "registry is meta": {
        "meta_template": "{base}{tenant_id}/x",
        "registry_template": "{base}{tenant_id}/x",
    },
    "A is the toolkit": {"application_template": "{base}toolkit"},
    "A is under the toolkit": {"application_template": "{base}toolkit/x/y"},
    "A is the base": {"application_template": "{base}"},
    "A reads as a tenant under a deployment": {
        "application_template": "{base}{deployment}/abcd",
        "tenant_template": "{base}{deployment}/{tenant_id}",
        "tenant_id": IdSpec(kind=IdKind.RANDOM, length=4),
    },
}


@pytest.mark.parametrize("name", list(COLLIDING))
def test_a_policy_with_colliding_application_graphs_is_refused_with_invalid_iri(name: str) -> None:
    """Fails if a collision escapes the constructor, or surfaces as another exception type."""
    policy = IriPolicy(**COLLIDING[name])  # type: ignore[arg-type]
    try:
        _iris(policy)
    except InvalidIri:
        return
    except Exception as error:
        pytest.fail(f"{name}: {type(error).__name__} instead of InvalidIri: {error}")
    pytest.fail(f"{name}: the policy was accepted")


@pytest.mark.parametrize("length", [4, 11])
def test_an_application_iri_that_the_tenant_pattern_matches_is_refused(length: int) -> None:
    """Fails if ``reads as a tenant`` looks at the default id spec and not at the policy's."""
    template = {4: "{base}apps", 11: "{base}application"}[length]
    policy = FLAT.model_copy(
        update={
            "tenant_id": IdSpec(kind=IdKind.RANDOM, length=length),
            "application_template": template,
        }
    )
    with pytest.raises(InvalidIri, match="reads as a tenant"):
        _iris(policy)


def test_an_application_iri_the_short_alphabet_cannot_spell_is_accepted() -> None:
    """Fails if the tenant pattern is built from the default alphabet and not the policy's."""
    policy = FLAT.model_copy(
        update={
            "tenant_id": IdSpec(kind=IdKind.RANDOM, length=4, alphabet="ap"),
            "application_template": "{base}apps",
        }
    )
    assert str(_iris(policy).application) == f"{BASE}apps", "an s is not in the alphabet"


# -- 5. the round trip --------------------------------------------------------------------------


@INVARIANTS
@given(ACCEPTED, st.sampled_from([str, URIRef]))
def test_what_is_minted_for_the_application_is_accepted_for_it(
    case: tuple[IriPolicy, int], as_text: type
) -> None:
    """Fails if a mint of ``A`` is a shape that ``is_aggregate``, ``is_loaded_graph`` or ``is_aggregate_graph`` refuse."""
    policy, seed = case
    iris = _built(policy, seed)
    assume(iris is not None)
    assert iris is not None
    a = as_text(str(iris.application))
    x = as_text(str(iris.mint_aggregate(a, "template", "templates")))
    part = iris.mint_part(a, x, "chapter")
    g = as_text(str(iris.mint_loaded_graph(a, x)))
    assert iris.is_aggregate(a, x), "the aggregate"
    assert iris.is_aggregate_graph(a, as_text(str(graph_iri(str(x))))), "its graph"
    assert iris.is_loaded_graph(a, g, x), "the loaded graph of the aggregate"
    assert iris.is_loaded_graph(a, g), "of the application"
    assert iris.is_loaded_graph(None, g), "with no tenant given"
    assert str(part), "a part has an IRI"
    if "{root}" in str(iris.effective_policy.loaded_graph_template):
        assert not iris.is_loaded_graph(a, g, str(x) + "-other"), "and not of another root"


@pytest.mark.parametrize("cls_type", ["template", "book"])
def test_every_root_type_round_trips_for_the_application(cls_type: str) -> None:
    """Fails if only some root types are matched under ``A``."""
    iris = _iris(FLAT, _seeded(1))
    x = iris.mint_aggregate(iris.application, cls_type, "things")
    assert iris.is_aggregate(iris.application, x), f"{cls_type} is matched"


def test_a_type_that_is_no_root_type_is_refused_for_the_application() -> None:
    """Fails if the allow-list is skipped when the owner is the application."""
    iris = _iris(FLAT)
    with pytest.raises(InvalidIri):
        iris.mint_aggregate(iris.application, "chapter", "chapters")


# -- 6. hostile strings -------------------------------------------------------------------------


def _hostile_variants(a: str) -> list[str]:
    base = BASE
    return [
        a + "/",
        a + "?q=1",
        a + "#frag",
        a.upper(),
        a + "\n",
        a + " ",
        " " + a,
        f"{base}apple",
        f"{base}app-x",
        f"{base}app.",
        f"{base}app%2F",
        f"{base}app.*",
        f"{base}(app|x)",
        f"{base}ap",
        f"{base}appp",
        a.replace("https", "http"),
    ]


@pytest.mark.parametrize("policy", [None, FLAT], ids=["default", "flat"])
@pytest.mark.parametrize("tail", ["templates", "template", "content", "graph"])
def test_an_iri_that_only_starts_like_the_application_is_not_the_applications(
    policy: IriPolicy | None, tail: str
) -> None:
    """Fails if the ``app`` alternative is matched without its separator, or case-insensitively."""
    iris = _iris(policy)
    a = str(iris.application)
    for prefix in _hostile_variants(a):
        iri = f"{prefix}/{tail}/{UUID_TEXT}"
        assert _accepted_by(iris, a, iri) == [], f"{iri} is taken as the application's"
        if tail == "graph":
            iri = f"{prefix}/templates/{UUID_TEXT}/graph"
            assert _accepted_by(iris, a, iri) == [], f"{iri} is taken as the application's"


def test_a_loaded_graph_of_no_tenant_is_not_read_from_a_lookalike_application() -> None:
    """Fails if ``is_loaded_graph(None, ...)`` takes ``app`` followed by more characters as ``app``."""
    iris = _iris(FLAT.model_copy(update={"loaded_graph_template": FLAT_AGGREGATE}))
    for lookalike in ("apple", "app-x", "appp", "APP", "app."):
        iri = f"{BASE}{lookalike}/content/{UUID_TEXT}"
        assert not iris.is_loaded_graph(None, iri), f"{iri} is a loaded graph"


HOSTILE_TENANTS = [
    "",
    ".*",
    "(?P<tenant>.+)",
    "[",
    "\\",
    "app",
    "APP",
    "app/",
    f"{BASE}app/",
    f"{BASE}app?x",
    f"{BASE}app#x",
    f"{BASE}APP",
    f"{BASE}app\n",
    f"{BASE}app.*",
    f"{BASE}app|{BASE}x",
]


@pytest.mark.parametrize("policy", [None, FLAT], ids=["default", "flat"])
@pytest.mark.parametrize("hostile", HOSTILE_TENANTS)
def test_a_hostile_tenant_argument_never_takes_the_applications_iris(
    policy: IriPolicy | None, hostile: str
) -> None:
    """Fails if a tenant argument that is not ``A`` is read as ``A``, or if it raises anything but ``InvalidIri``."""
    iris = _iris(policy, _seeded(7))
    a = str(iris.application)
    x = str(iris.mint_aggregate(a, "template", "templates"))
    g = str(iris.mint_loaded_graph(a, x))
    for iri in (a, x, g, f"{x}/graph", str(iris.access(a))):
        for matcher in (iris.is_aggregate, iris.is_loaded_graph, iris.is_aggregate_graph):
            try:
                accepted = matcher(hostile, iri)
            except InvalidIri:
                continue
            assert not accepted, f"{matcher.__name__}({hostile!r}, {iri!r}) is True"


@pytest.mark.parametrize("policy", [None, FLAT], ids=["default", "flat"])
@pytest.mark.parametrize("hostile", HOSTILE_TENANTS)
def test_a_hostile_tenant_argument_raises_only_the_documented_exceptions(
    policy: IriPolicy | None, hostile: str
) -> None:
    """Fails if a regex or format error leaks out of minting or reading for a hostile owner."""
    iris = _iris(policy, _seeded(9))
    calls: list[Callable[[], object]] = [
        lambda: iris.access(hostile),
        lambda: iris.meta(hostile),
        lambda: iris.registry(hostile),
        lambda: iris.mint_aggregate(hostile, "template", "templates"),
        lambda: iris.mint_loaded_graph(hostile, f"{BASE}x"),
        lambda: iris.tenant_id_of(hostile),
        lambda: iris.tenant_of_access(hostile),
        lambda: iris.resource_name(hostile),
        lambda: iris.tenant(hostile),
    ]
    for call in calls:
        with contextlib.suppress(InvalidIri, NotFound):
            call()


@pytest.mark.parametrize("hostile", HOSTILE_TENANTS)
def test_a_hostile_iri_argument_raises_nothing_for_the_application(hostile: str) -> None:
    """Fails if the matchers raise on any text given as the IRI."""
    iris = _iris(FLAT)
    for matcher in (iris.is_aggregate, iris.is_loaded_graph, iris.is_aggregate_graph):
        matcher(str(iris.application), hostile)


# -- 7. effective policy ------------------------------------------------------------------------


def test_a_policy_without_the_application_template_is_the_default_one() -> None:
    """Fails if the missing slot is not filled with the default before two policies are compared."""
    stored = IriPolicy.model_validate_json("{}")
    spelled = IriPolicy.model_validate_json('{"application_template": "{base}app"}')
    literal = IriPolicy.model_validate_json('{"application_template": "https://ex.org/app"}')
    cfg = _settings()
    assert policy_differences(effective_policy(stored, cfg), effective_policy(spelled, cfg)) == []
    assert policy_differences(effective_policy(None, cfg), effective_policy(literal, cfg)) == [], (
        "the written-out default is the default"
    )


@pytest.mark.parametrize(
    "template",
    ["{base}application", "{base}{tenant_segment}", "{base}{deployment}/app", "{base}tenants/app"],
)
def test_another_application_template_differs_in_that_field_alone(template: str) -> None:
    """Fails if the application template leaks into another field of the effective policy."""
    cfg = _settings()
    other = effective_policy(IriPolicy(application_template=template), cfg)
    assert policy_differences(effective_policy(None, cfg), other) == ["application_template"]


@pytest.mark.parametrize(
    "policy",
    [
        None,
        FLAT,
        IriPolicy(application_template="{base}{deployment}/{tenant_segment}/app"),
        IriPolicy(
            tenant_template="{base}{deployment}/{tenant_id}",
            tenant_id=IdSpec(kind=IdKind.RANDOM, length=5),
        ),
    ],
    ids=["default", "flat", "settings-variables", "random-ids"],
)
def test_the_effective_policy_applied_twice_is_the_effective_policy(
    policy: IriPolicy | None,
) -> None:
    """Fails if filling the settings in is not idempotent."""
    cfg = _settings()
    once = effective_policy(policy, cfg)
    assert effective_policy(once, cfg) == once, "applied twice, the same"


def test_the_effective_policy_applied_twice_keeps_a_base_that_holds_a_variable() -> None:
    """Fails if writing the base in lets a second pass fill a variable the base itself spells."""
    cfg = _settings(base="https://ex.org/{deployment}/")
    once = effective_policy(None, cfg)
    assert effective_policy(once, cfg) == once, "the base is text, never a template"


@INVARIANTS
@given(ACCEPTED)
def test_the_effective_application_template_is_the_iri_that_is_minted(
    case: tuple[IriPolicy, int],
) -> None:
    """Fails if the recorded policy and ``Iris.application`` spell the application differently."""
    policy, seed = case
    iris = _built(policy, seed)
    assume(iris is not None)
    assert iris is not None
    assert iris.effective_policy.application_template == str(iris.application), "one spelling"
