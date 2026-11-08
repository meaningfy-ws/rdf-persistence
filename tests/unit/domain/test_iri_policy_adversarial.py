"""``Iris`` under hostile input and at the limits of what the schema allows (iri-policy stage 1).

Every test names the production change that would make it fail.
"""

import re
from collections.abc import Callable

import pytest
from pydantic import ValidationError

from rdf_persistence.domain.exceptions import InvalidIri, NotFound
from rdf_persistence.domain.generated.service.rp_service import (
    IdKind,
    IdSpec,
    IriPolicy,
    ServiceSettings,
)
from rdf_persistence.domain.iris import LAYOUT_WORDS, Iris

BASE = "http://mwb.meaningfy.ws/"
FLAT = "{base}{tenant_id}/{type}/{id}"
ROOTS = frozenset({"ontology-file", "book"})
OWNED = frozenset({"term", "chapter"})


def settings(
    policy: IriPolicy | None = None, *, prefix: str = "mwb", deployment: str | None = None
) -> ServiceSettings:
    return ServiceSettings(
        base=BASE,
        prefix=prefix,
        tenant_segment="projects",
        creator_role="owner",
        roles_claim="roles",
        iri_policy=policy,
        deployment=deployment,
    )


def flat_policy(tenant_length: int = 7, object_length: int = 13) -> IriPolicy:
    return IriPolicy(
        tenant_template="{base}project/{tenant_id}",
        aggregate_template=FLAT,
        part_template=FLAT,
        loaded_graph_template=FLAT,
        tenant_id=IdSpec(kind=IdKind.RANDOM, length=tenant_length),
        object_id=IdSpec(kind=IdKind.RANDOM, length=object_length),
    )


def scripted(*ids: str) -> Callable[[IdSpec], str]:
    drawn = iter(ids)
    return lambda spec: next(drawn)


def flat(tenant_length: int = 7, object_length: int = 13) -> Iris:
    return Iris(
        settings(flat_policy(tenant_length, object_length), deployment="k3f9a2x"), ROOTS, OWNED
    )


TENANT_ID = "p4x8k2m"
OBJECT_ID = "a8f3k29dm4x1q"


# -- the limits of the schema: 4 and 32 characters, a 20-character prefix -------------------------


@pytest.mark.parametrize("length", [4, 32])
def test_ids_at_the_ends_of_the_allowed_length_round_trip_through_every_matcher(length):
    iris = flat(tenant_length=length, object_length=length)
    tenant = str(iris.mint_tenant())
    assert len(iris.tenant_id_of(tenant)) == length
    root = str(iris.mint_aggregate(tenant, "book", "books"))
    assert iris.is_aggregate(tenant, root) and iris.is_aggregate_graph(tenant, f"{root}/graph")
    loaded = str(iris.mint_loaded_graph(tenant, root))
    assert iris.is_loaded_graph(tenant, loaded, root=root)
    assert str(iris.mint_part(tenant, root, "chapter")).count("/") == root.count("/")


def test_a_32_character_tenant_id_under_a_20_character_prefix_fits_a_bucket_name():
    longest = "a" * 20
    iris = Iris(settings(flat_policy(32, 32), prefix=longest))
    name = iris.resource_name(str(iris.mint_tenant()))
    assert len(name) <= 63, "S3 bucket names stop at 63 characters"
    assert re.fullmatch(r"[a-z][a-z0-9-]*[a-z0-9]", name)


def test_the_default_uuid_tenant_under_a_20_character_prefix_fits_a_bucket_name():
    iris = Iris(settings(prefix="b" * 20))
    assert len(iris.resource_name(str(iris.mint_tenant()))) == 20 + len("-t-") + 32


# -- hostile ids ----------------------------------------------------------------------------------

HOSTILE = [
    pytest.param("p4x8k2m\n", id="newline"),
    pytest.param("p4x8k2m ", id="space"),
    pytest.param("P4X8K2M", id="upper case"),
    pytest.param("p4x8k2", id="one short"),
    pytest.param("p4x8k2mm", id="one long"),
    pytest.param("p4x8k2/", id="slash"),
    pytest.param("p4x8k2%6d", id="percent-encoded"),
    pytest.param("p4x8k2#", id="fragment"),
    pytest.param("p4x8k2?", id="query"),
    pytest.param("p4x8k١m", id="arabic-indic digit"),
    pytest.param("", id="empty"),
    pytest.param("..", id="dots"),
]


@pytest.mark.parametrize("hostile", HOSTILE)
def test_a_tenant_id_that_is_not_the_policys_is_not_found(hostile):
    with pytest.raises(NotFound):
        flat().tenant(hostile)


@pytest.mark.parametrize(
    "hostile",
    [
        "A8F3K29DM4X1Q",
        "a8f3k29dm4x1",
        "a8f3k29dm4x1qq",
        "a8f3k29/m4x1q",
        "a8f3k29dm4x1\n",
        "a8f3k29dm4x1%",
        "a8f3k29dm4x1 ",
    ],
)
def test_an_object_id_that_is_not_the_policys_is_not_found(hostile):
    iris = flat()
    with pytest.raises(NotFound):
        iris.aggregate(str(iris.tenant(TENANT_ID)), "book", "books", hostile)


@pytest.mark.parametrize(
    "suffix", ["/", "#frag", "?q=1", "\n", "%20", "/graph/", "//", "/../x", "/graph#x"]
)
def test_an_aggregate_iri_with_anything_after_its_id_is_not_an_aggregate(suffix):
    iris = flat()
    tenant = str(iris.tenant(TENANT_ID))
    root = str(iris.aggregate(tenant, "book", "books", OBJECT_ID))
    assert iris.is_aggregate(tenant, root)
    assert not iris.is_aggregate(tenant, root + suffix)
    assert not iris.is_loaded_graph(tenant, str(iris.mint_loaded_graph(tenant, root)) + suffix)


def test_an_aggregate_graph_is_only_the_roots_slash_graph():
    iris = flat()
    tenant = str(iris.tenant(TENANT_ID))
    root = str(iris.aggregate(tenant, "book", "books", OBJECT_ID))
    assert iris.is_aggregate_graph(tenant, f"{root}/graph")
    for not_a_graph in (
        root,
        f"{root}/graph/graph",
        f"{root}/Graph",
        f"{tenant}/graph",
        "/graph",
        "graph",
    ):
        assert not iris.is_aggregate_graph(tenant, not_a_graph), not_a_graph


def test_another_tenants_objects_are_not_this_tenants():
    iris = flat()
    mine, other = (str(iris.tenant(i)) for i in (TENANT_ID, "q9y7j1n"))
    theirs = str(iris.aggregate(other, "book", "books", OBJECT_ID))
    assert iris.is_aggregate(other, theirs) and not iris.is_aggregate(mine, theirs)
    loaded = str(iris.mint_loaded_graph(other, theirs))
    assert iris.is_loaded_graph(other, loaded) and not iris.is_loaded_graph(mine, loaded)
    assert not iris.is_loaded_graph(mine, loaded, root=theirs)


def test_a_part_type_is_not_an_aggregate_type_and_an_aggregate_type_is_not_a_part_type():
    iris = flat()
    tenant = str(iris.tenant(TENANT_ID))
    with pytest.raises(InvalidIri):
        iris.mint_aggregate(tenant, "chapter", "chapters")
    with pytest.raises(InvalidIri):
        iris.mint_part(tenant, f"{BASE}{TENANT_ID}/book/{OBJECT_ID}", "book")
    assert not iris.is_aggregate(tenant, f"{BASE}{TENANT_ID}/chapter/{OBJECT_ID}")
    assert not iris.is_aggregate(tenant, f"{BASE}{TENANT_ID}/content/{OBJECT_ID}")


def test_a_type_that_is_regex_syntax_matches_only_itself():
    iris = Iris(settings(flat_policy()), frozenset({"a.b", "c+d", "(x)"}), frozenset())
    tenant = str(iris.tenant(TENANT_ID))
    for impostor in ("axb", "ccd", "x"):
        assert not iris.is_aggregate(tenant, f"{BASE}{TENANT_ID}/{impostor}/{OBJECT_ID}")
    assert iris.is_aggregate(tenant, f"{BASE}{TENANT_ID}/a.b/{OBJECT_ID}")


# -- reserved words -------------------------------------------------------------------------------


@pytest.mark.parametrize("word", [*LAYOUT_WORDS, "project", "ontology-file", "term", "k3f9a2x"])
def test_a_drawn_id_that_is_a_reserved_word_is_discarded_for_every_kind_of_id(word):
    iris = Iris(
        settings(flat_policy(), deployment="k3f9a2x"),
        ROOTS,
        OWNED,
        id_source=scripted(word, TENANT_ID, word, OBJECT_ID, word, OBJECT_ID, word, OBJECT_ID),
    )
    tenant = str(iris.mint_tenant())
    assert tenant.endswith(f"/{TENANT_ID}")
    assert iris.mint_aggregate(tenant, "book", "books").endswith(OBJECT_ID)
    assert iris.mint_part(tenant, "x", "term").endswith(OBJECT_ID)
    assert iris.mint_loaded_graph(tenant, "x").endswith(OBJECT_ID)


def test_a_source_that_only_answers_reserved_words_gives_up_after_100_draws_and_says_so():
    calls: list[str] = []

    def source(spec: IdSpec) -> str:
        calls.append("meta")
        return "meta"

    iris = Iris(settings(), id_source=source)
    with pytest.raises(InvalidIri):
        iris.mint_tenant()
    assert len(calls) == 100


def test_an_alphabet_that_can_only_spell_a_reserved_word_fails_loudly_not_forever():
    one_letter = IdSpec(kind=IdKind.RANDOM, length=4, alphabet="m")
    policy = IriPolicy(tenant_template="{base}mmmm/{tenant_id}", tenant_id=one_letter)
    iris = Iris(settings(policy))
    with pytest.raises(InvalidIri):
        iris.mint_tenant()


def test_the_deployment_slug_is_never_an_id_even_when_the_policy_has_no_template_for_it():
    free = "12345678-1234-4234-8234-123456789abc"
    iris = Iris(settings(deployment="k3f9a2x"), id_source=scripted("k3f9a2x", free))
    assert str(iris.mint_tenant()).endswith(free)


# -- the access template with both tenant variables -----------------------------------------------


def both() -> Iris:
    policy = IriPolicy(
        tenant_template="{base}project/{tenant_id}",
        access_template="{tenant}/access/{tenant_id}",
        tenant_id=IdSpec(kind=IdKind.RANDOM, length=7),
    )
    return Iris(settings(policy))


def test_an_access_template_with_tenant_and_tenant_id_round_trips(until_stage_two):
    iris = both()
    tenant = str(iris.tenant(TENANT_ID))
    assert str(iris.tenant_of_access(str(iris.access(tenant)))) == tenant


def test_an_access_iri_whose_two_tenant_variables_disagree_is_not_an_access_iri(until_stage_two):
    iris = both()
    tenant = str(iris.tenant(TENANT_ID))
    forged = f"{tenant}/access/q9y7j1n"
    with pytest.raises(InvalidIri):
        iris.tenant_of_access(forged)


def test_an_access_iri_of_another_tenant_is_not_this_tenants_record(until_stage_two):
    iris = both()
    mine, other = str(iris.tenant(TENANT_ID)), str(iris.tenant("q9y7j1n"))
    assert iris.is_aggregate(other, str(iris.access(other)))
    assert not iris.is_aggregate(mine, str(iris.access(other)))


# -- principals ------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "sub", ["a#b", "a/b", "a?b", "a b", "../x", "a%2Fb", "é", "a\nb", "", "x" * 2000]
)
def test_a_subject_never_leaves_its_path_segment(sub):
    iri = str(flat().principal("https://id.example.org/realm/", sub))
    prefix = "https://id.example.org/realm/users/"
    assert iri.startswith(prefix) and "/" not in iri[len(prefix) :]
    assert not any(c in iri[len(prefix) :] for c in "#? \n")


def test_a_subject_and_its_percent_encoding_are_two_principals():
    iris = flat()
    assert iris.principal("https://i", "a/b") != iris.principal("https://i", "a%2Fb")


# -- the frozen object and the settings -----------------------------------------------------------


def test_iris_cannot_be_changed_after_it_is_built():
    iris = flat()
    for name in ("settings", "root_types", "id_source", "_policy", "nested_parts"):
        with pytest.raises(AttributeError):
            setattr(iris, name, None)


def test_the_settings_an_iris_was_built_from_cannot_change_what_it_mints():
    built = settings(flat_policy())
    iris = Iris(built, ROOTS, OWNED)
    try:
        built.base = "http://evil.example/"
    except (ValidationError, TypeError, AttributeError):
        return
    assert str(iris.tenant(TENANT_ID)).startswith(BASE)


def test_building_an_iris_checks_the_policy_even_for_a_random_id_without_a_length():
    with pytest.raises((InvalidIri, ValidationError)):
        Iris(settings(IriPolicy(object_id=IdSpec(kind=IdKind.RANDOM))))


def test_a_template_with_deployment_and_no_slug_is_refused_at_build_time():
    policy = IriPolicy(tenant_template="{base}{deployment}/{tenant_id}")
    with pytest.raises(InvalidIri, match="deployment"):
        Iris(settings(policy))


# -- the default policy ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "hostile",
    [
        "12345678-1234-4234-8234-123456789ABC",
        "12345678123442348234123456789abc",
        " 12345678-1234-4234-8234-123456789abc",
    ],
)
def test_a_default_tenant_id_is_a_lower_case_hyphenated_uuid_and_nothing_else(hostile):
    with pytest.raises(NotFound):
        Iris(settings()).tenant(hostile)


def test_a_default_aggregate_iri_with_a_longer_nesting_is_not_an_aggregate():
    iris = Iris(settings())
    tenant = str(iris.tenant("12345678-1234-4234-8234-123456789abc"))
    nested = f"{tenant}/files/12345678-1234-4234-8234-123456789abc"
    assert iris.is_aggregate(tenant, nested)
    for deeper in (
        f"{nested}/parts/12345678-1234-4234-8234-123456789abc",
        f"{nested}/content/12345678-1234-4234-8234-123456789abc",
        f"{tenant}/x/{nested}",
    ):
        assert not iris.is_aggregate(tenant, deeper), deeper


# -- review decisions PD-12a to PD-12c ------------------------------------------------------------


@pytest.mark.parametrize(
    "slot, template",
    [
        ("access_template", "{base}{tenant_id}/acc"),
        ("meta_template", "{base}{tenant_id}/m"),
        ("registry_template", "{base}{tenant_id}/r"),
        ("principal_template", "{base}u/{sub}"),
    ],
)
def test_a_template_stage_two_does_not_wire_yet_is_refused_naming_it(slot, template):
    with pytest.raises(InvalidIri, match=f"{slot}.*stage 2"):
        Iris(
            settings(IriPolicy(tenant_id=IdSpec(kind=IdKind.RANDOM, length=7), **{slot: template}))
        )


@pytest.mark.parametrize("slot", ["access_template", "meta_template", "registry_template"])
def test_the_default_value_of_a_stage_two_template_is_accepted(slot):
    assert Iris(settings(IriPolicy(**{slot: getattr(IriPolicy(), slot)})))


def tiny(length: int) -> Iris:
    policy = flat_policy(tenant_length=length, object_length=length)
    return Iris(settings(policy), ROOTS, OWNED)


WORDS = [pytest.param(4, "meta", id="meta"), pytest.param(5, "graph", id="graph")]


@pytest.mark.parametrize(("length", "word"), WORDS)
def test_a_reserved_word_is_not_a_tenant_id_when_matching(length, word):
    iris = tiny(length)
    with pytest.raises(NotFound):
        iris.tenant(word)
    with pytest.raises(InvalidIri):
        iris.tenant_id_of(f"{BASE}project/{word}")


@pytest.mark.parametrize(("length", "word"), WORDS)
def test_a_reserved_word_is_not_an_object_id_when_matching(length, word):
    iris = tiny(length)
    tid = "p4x8k"[:length]
    tenant = str(iris.tenant(tid))
    with pytest.raises(NotFound):
        iris.aggregate(tenant, "book", "books", word)
    assert not iris.is_aggregate(tenant, f"{BASE}{tid}/book/{word}")
    assert not iris.is_loaded_graph(tenant, f"{BASE}{tid}/content/{word}")


def test_an_aggregate_graph_is_never_the_graph_of_the_access_record():
    iris = Iris(settings())
    tenant = str(iris.tenant("12345678-1234-4234-8234-123456789abc"))
    access = str(iris.access(tenant))
    assert iris.is_aggregate(tenant, access)
    assert not iris.is_aggregate_graph(tenant, f"{access}/graph")


def test_an_aggregate_template_must_name_its_tenant():
    with pytest.raises(ValidationError, match="aggregate_template"):
        IriPolicy(aggregate_template="{base}{type}/{id}")


@pytest.mark.parametrize("slot", ["part_template", "loaded_graph_template"])
def test_a_part_or_loaded_graph_template_must_name_a_tenant_or_a_root(slot):
    with pytest.raises(ValidationError, match=slot):
        IriPolicy(**{slot: "{base}{type}/{id}"})
    for ok in ("{root}/x/{id}", "{base}{tenant}/{id}", "{base}{tenant_id}/{id}"):
        assert getattr(IriPolicy(**{slot: ok}), slot) == ok
