"""The service classes of ``rp_service.yaml`` as gen-pydantic renders them (task 1.13, PD-24)."""

import pytest
from pydantic import ValidationError

from rdf_persistence import (
    GrantSet,
    LabelUpdate,
    Page,
    Problem,
    ServiceSettings,
    TenantCreate,
    TenantState,
    TenantSummary,
    VerifiedCaller,
)
from rdf_persistence.domain.generated.service import rp_service
from tests.unit.domain.builders import ALICE, TENANT, grant, tenant_access

BASE = "https://example.org/"


def settings(**changes: str) -> ServiceSettings:
    fields = {
        "base": BASE,
        "prefix": "lib",
        "tenant_segment": "tenants",
        "creator_role": "owner",
        "roles_claim": "urn:zitadel:iam:org:project:42:roles",
    }
    return ServiceSettings(**{**fields, **changes})


def test_the_roles_claim_has_no_default_because_it_names_the_consumers_project() -> None:
    fields = settings().model_dump(exclude={"roles_claim"})
    with pytest.raises(ValidationError, match="roles_claim"):
        ServiceSettings(**fields)


@pytest.mark.parametrize("prefix", ["l", "lib", "a1b2", "a" * 20])
def test_a_lower_case_prefix_of_at_most_20_characters_is_accepted(prefix: str) -> None:
    assert settings(prefix=prefix).prefix == prefix, "the prefix was not kept"


@pytest.mark.parametrize("prefix", ["", "Lib", "1lib", "a" * 21, "li-b"])
def test_any_other_prefix_is_refused(prefix: str) -> None:
    with pytest.raises(ValidationError, match="Invalid prefix format"):
        settings(prefix=prefix)


@pytest.mark.parametrize(
    "base", ["https://example.org/", "http://x/", "https://example.org/rp/v1/"]
)
def test_a_base_ending_in_a_slash_is_accepted(base: str) -> None:
    assert settings(base=base).base == base, "the base was not kept"


@pytest.mark.parametrize(
    "base",
    ["", "https://example.org", "ftp://example.org/", "https:///", "example.org/", "http://x/\n"],
)
def test_a_base_that_is_not_an_http_iri_ending_in_a_slash_is_refused(base: str) -> None:
    with pytest.raises(ValidationError, match="Invalid base format"):
        settings(base=base)


@pytest.mark.parametrize("segment", ["tenants", "t", "my-tenants", "t1"])
def test_a_lower_case_url_segment_names_the_tenants(segment: str) -> None:
    assert settings(tenant_segment=segment).tenant_segment == segment, "the segment was not kept"


@pytest.mark.parametrize("segment", ["", "Tenants", "1t", "a/b", "a b", "-t", "tenants\n", "t_1"])
def test_any_other_tenant_segment_is_refused(segment: str) -> None:
    with pytest.raises(ValidationError, match="Invalid tenant_segment format"):
        settings(tenant_segment=segment)


def test_the_creator_role_is_not_empty() -> None:
    assert settings(creator_role="owner").creator_role == "owner", "the role was not kept"
    with pytest.raises(ValidationError, match="Invalid creator_role format"):
        settings(creator_role="")


@pytest.mark.parametrize("prefix", ["lib\n"])
def test_a_prefix_with_a_trailing_newline_is_refused(prefix: str) -> None:
    with pytest.raises(ValidationError, match="Invalid prefix format"):
        settings(prefix=prefix)


@pytest.mark.parametrize("missing", ["base", "prefix", "tenant_segment", "creator_role"])
def test_settings_require_what_has_no_default(missing: str) -> None:
    fields = settings().model_dump(exclude={missing})
    with pytest.raises(ValidationError, match=missing):
        ServiceSettings.model_validate(fields)


def test_a_verified_caller_has_a_principal_and_global_roles() -> None:
    caller = VerifiedCaller(principal=ALICE, global_roles=["admin"])
    assert (caller.principal, caller.global_roles) == (ALICE, ["admin"]), "the caller was not kept"


def test_a_verified_caller_needs_a_principal() -> None:
    with pytest.raises(ValidationError, match="principal"):
        VerifiedCaller()


def test_a_tenant_create_body_takes_any_root() -> None:
    body = TenantCreate(label="Acme", root=["anything", {"goes": 1}])
    assert body.root == ["anything", {"goes": 1}], "the root must be kept as given"


@pytest.mark.parametrize("missing", ["label", "root"])
def test_a_tenant_create_body_needs_a_label_and_a_root(missing: str) -> None:
    fields = {"label": "Acme", "root": {}}
    del fields[missing]
    with pytest.raises(ValidationError, match=missing):
        TenantCreate(**fields)


def test_a_tenant_summary_holds_the_state_of_the_tenant() -> None:
    summary = TenantSummary(id=TENANT, label="Acme", state="deleting")
    assert summary.state == TenantState.DELETING, "the state must be a tenant state"
    with pytest.raises(ValidationError, match="state"):
        TenantSummary(id=TENANT, label="Acme", state="archived")


def test_a_label_update_needs_a_label() -> None:
    assert LabelUpdate(label="New").label == "New", "the label was not kept"
    with pytest.raises(ValidationError, match="label"):
        LabelUpdate()


def test_a_grant_set_accepts_distinct_grants() -> None:
    grants = [grant(), grant(role="viewer"), grant(role=None, action="read")]
    assert len(GrantSet(grants=grants).grants or []) == 3, "distinct grants were refused"


@pytest.mark.parametrize("direct", [False, True], ids=["by role", "by action"])
def test_a_grant_set_refuses_a_duplicate_grant(direct: bool) -> None:
    make = (lambda: grant(role=None, action="read")) if direct else grant
    with pytest.raises(ValidationError, match=r"GrantSet.grants.*grant_key"):
        GrantSet(grants=[make(), make()])


def test_a_grant_set_builds_grants_from_data() -> None:
    body = GrantSet.model_validate(
        {"grants": [{"assignee": ALICE, "target": TENANT, "role": "editor"}]}
    )
    assert body.grants and body.grants[0].role == "editor", "the grant must be built from the data"


def test_a_page_keeps_any_items_and_refuses_negative_positions() -> None:
    page = Page(items=[{"id": 1}, "x"], total=2, limit=50, offset=0)
    assert page.items == [{"id": 1}, "x"], "the items must be kept as given"
    with pytest.raises(ValidationError, match="offset"):
        Page(items=[], total=0, limit=50, offset=-1)


def test_a_problem_is_dumped_under_the_names_of_rfc_9457() -> None:
    problem = Problem(type=f"{BASE}problems/forbidden", title="Forbidden", status=403)
    assert set(problem.model_dump(exclude_none=True)) == {"type", "title", "status"}, (
        "a problem must serialise as type, title, status, detail and instance"
    )


@pytest.mark.parametrize("missing", ["type", "title", "status"])
def test_a_problem_needs_a_type_a_title_and_a_status(missing: str) -> None:
    fields = {"type": f"{BASE}problems/forbidden", "title": "Forbidden", "status": 403}
    del fields[missing]
    with pytest.raises(ValidationError, match=missing):
        Problem(**fields)


def test_the_service_module_declares_only_its_own_classes() -> None:
    declared = {
        n
        for n, v in vars(rp_service).items()
        if isinstance(v, type) and v.__module__ == rp_service.__name__
    }
    assert {"Grant", "Principal", "TenantState"}.isdisjoint(declared), (
        "the metamodel's classes are imported"
    )


# --- the tenant label is the same at every boundary: 1 to 200 characters, one line ---

LABEL_BOUNDARIES = {
    "TenantAccess": lambda label: tenant_access(label=label),
    "TenantCreate": lambda label: TenantCreate(label=label, root={}),
    "LabelUpdate": lambda label: LabelUpdate(label=label),
}
LABEL_BOUNDARY = pytest.mark.parametrize("build", LABEL_BOUNDARIES.values(), ids=LABEL_BOUNDARIES)


@LABEL_BOUNDARY
@pytest.mark.parametrize("label", ["A", "a", "Acme", "Acme Ltd", "x" * 200, "a" + " " * 198 + "b"])
def test_a_tenant_label_of_1_to_200_characters_is_accepted(build, label: str) -> None:
    assert build(label).label == label, "the label was not kept"


@LABEL_BOUNDARY
@pytest.mark.parametrize(
    "label",
    ["", "x" * 201, "Acme\n", "Ac\nme", " .", " ", "  ", " a", "a ", "x" * 199 + " "],
    ids=[
        "empty",
        "long",
        "newline-end",
        "newline-inside",
        "space-dot",
        "one-space",
        "two-spaces",
        "leading-space",
        "trailing-space",
        "trailing-space-at-199",
    ],
)
def test_any_other_tenant_label_is_refused(build, label: str) -> None:
    with pytest.raises(ValidationError, match="Invalid label format"):
        build(label)
