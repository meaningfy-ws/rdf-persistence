"""``Iris`` mints and matches the application's IRIs and never calls the application a tenant (PD-2, PD-3)."""

from collections.abc import Callable, Iterator
from uuid import uuid4

import pytest
from rdflib import URIRef

from rdf_persistence.domain.exceptions import InvalidIri, NotFound
from rdf_persistence.domain.generated.service.rp_service import (
    IdKind,
    IdSpec,
    IriPolicy,
    ServiceSettings,
)
from rdf_persistence.domain.iris import (
    APPLICATION_ID,
    APPLICATION_SUFFIX,
    Iris,
    application_database_name,
    effective_policy,
)

BASE = "https://ex.org/"
APPLICATION = f"{BASE}app"
UUID_TAIL = "[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}"
FLAT_POLICY = IriPolicy(
    tenant_template="{base}{tenant_id}", aggregate_template="{base}{tenant_id}/{type}/{id}"
)
POLICIES = {"default": None, "flat": FLAT_POLICY}
TYPES = {"root_types": frozenset({"template", "book"}), "owned_types": frozenset({"chapter"})}


def _settings(policy: IriPolicy | None = None) -> ServiceSettings:
    return ServiceSettings(
        base=BASE,
        prefix="lib",
        tenant_segment="tenants",
        creator_role="owner",
        roles_claim="roles",
        iri_policy=policy,
    )


def _iris(policy: IriPolicy | None = None, **more: object) -> Iris:
    return Iris(_settings(policy), **TYPES, **more)  # type: ignore[arg-type]


def _scripted(*ids: str) -> Callable[[IdSpec], str]:
    drawn: Iterator[str] = iter(ids)
    return lambda spec: next(drawn)


@pytest.fixture(params=list(POLICIES))
def iris(request: pytest.FixtureRequest) -> Iris:
    return _iris(POLICIES[request.param])


@pytest.fixture(params=list(POLICIES))
def flat_or_default(request: pytest.FixtureRequest) -> IriPolicy | None:
    return POLICIES[request.param]


def test_tc15_default_policy_mints_under_the_application_iri() -> None:
    iris = _iris()
    assert iris.application == URIRef(APPLICATION), "the default application IRI is {base}app"
    minted = str(iris.mint_aggregate(iris.application, "template", "templates"))
    assert minted.startswith(f"{APPLICATION}/templates/"), "the aggregate is under the application"
    assert minted.removeprefix(f"{APPLICATION}/templates/") != "", "and ends in an id"


def test_tc16_flat_policy_mints_the_application_as_a_tenant_id() -> None:
    iris = _iris(FLAT_POLICY)
    minted = str(iris.mint_aggregate(iris.application, "template", "templates"))
    assert minted.startswith(f"{APPLICATION}/template/"), "the flat template writes app as the id"
    assert iris.meta(iris.application) == URIRef(f"{APPLICATION}/meta"), "meta follows the template"
    assert iris.registry(iris.application) == URIRef(f"{APPLICATION}/registry"), "so does registry"


def test_tc17_matching_accepts_the_application_and_refuses_a_tenant(iris: Iris) -> None:
    a, tenant = iris.application, iris.mint_tenant()
    x = iris.mint_aggregate(a, "template", "templates")
    part = iris.mint_part(a, x, "chapter")
    g = iris.mint_loaded_graph(a, x)
    assert str(part).startswith(str(x)), "a part is minted for the application aggregate"
    assert iris.is_aggregate(a, x), "an application aggregate is one of the application"
    assert iris.is_aggregate_graph(a, f"{x}/graph"), "its graph is one of the application"
    assert iris.is_loaded_graph(a, g, x), "its loaded graph is one of the application and root"
    assert iris.is_loaded_graph(None, g), "a loaded graph is recognised with no tenant given"
    assert not iris.is_aggregate(tenant, x), "an application aggregate is not a tenant's"
    assert not iris.is_loaded_graph(tenant, g), "an application loaded graph is not a tenant's"


def test_tc18_a_tenant_aggregate_is_not_the_applications(iris: Iris) -> None:
    tenant = iris.mint_tenant()
    book = iris.mint_aggregate(tenant, "book", "books")
    assert iris.is_aggregate(tenant, book), "the book is the tenant's"
    assert not iris.is_aggregate(iris.application, book), "and not the application's"


@pytest.mark.parametrize(
    ("ask", "expected"),
    [
        (lambda i: i.tenant_id_of(i.application), InvalidIri),
        (lambda i: i.tenant(APPLICATION_ID), NotFound),
        (lambda i: i.resource_name(i.application), InvalidIri),
        (lambda i: i.tenant_of_access(i.access(i.application)), InvalidIri),
    ],
    ids=["tenant_id_of", "tenant", "resource_name", "tenant_of_access"],
)
def test_tc19_tc27_the_application_is_never_a_tenant(
    iris: Iris, ask: Callable[[Iris], object], expected: type[Exception]
) -> None:
    with pytest.raises(expected):
        ask(iris)


def test_tc20_no_tenant_is_drawn_as_app() -> None:
    wanted = str(uuid4())
    iris = _iris(id_source=_scripted(APPLICATION_ID, wanted))
    assert str(iris.mint_tenant()).endswith(wanted), "the reserved draw is replaced by the next"


def test_tc21_flat_policy_starts_and_app_is_no_tenant() -> None:
    iris = _iris(FLAT_POLICY)
    with pytest.raises(InvalidIri):
        iris.tenant_id_of(APPLICATION)


def test_tc22_an_application_iri_that_reads_as_a_tenant_is_refused() -> None:
    policy = FLAT_POLICY.model_copy(
        update={
            "tenant_id": IdSpec(kind=IdKind.RANDOM, length=7),
            "application_template": "{base}x7k2m9p",
        }
    )
    with pytest.raises(InvalidIri, match="reads as a tenant"):
        _iris(policy)


def test_tc23_an_application_iri_equal_to_its_meta_is_refused() -> None:
    with pytest.raises(InvalidIri, match="same IRI"):
        _iris(IriPolicy(meta_template="{base}{tenant_id}"))


@pytest.mark.parametrize(
    ("template", "message"),
    [
        ("{base}toolkit", "the toolkit's own IRI"),
        ("{base}toolkit/app", "the toolkit's own IRI"),
        ("app", "outside the base"),
        ("https://other.org/app", "outside the base"),
        ("{base}", "outside the base"),
        ("{base}toolkitapp", None),
        ("{base}application", None),
    ],
)
def test_tc24_the_application_iri_stays_under_the_base_and_off_the_toolkit(
    flat_or_default: IriPolicy | None, template: str, message: str | None
) -> None:
    policy = (flat_or_default or IriPolicy()).model_copy(update={"application_template": template})
    if message is None:
        assert _iris(policy).application, "a sibling of the toolkit's IRI is accepted"
    else:
        with pytest.raises(InvalidIri, match=message):
            _iris(policy)


@pytest.mark.parametrize(
    ("prefix", "expected"), [("lib", "lib-app"), ("Lib", InvalidIri), ("a-b", InvalidIri)]
)
def test_tc25_application_database_name(prefix: str, expected: str | type[Exception]) -> None:
    assert APPLICATION_SUFFIX == "-app", "the suffix is the one the design names"
    if isinstance(expected, str):
        assert application_database_name(prefix) == expected, "the prefix and the suffix"
    else:
        with pytest.raises(expected):
            application_database_name(prefix)


def test_tc26_the_effective_policy_holds_the_application_template() -> None:
    settings = _settings()
    unset = effective_policy(None, settings)
    assert unset == effective_policy(IriPolicy(application_template="{base}app"), settings), (
        "the default and its spelling are one policy"
    )
    assert unset.application_template == APPLICATION, "the base is written in"
