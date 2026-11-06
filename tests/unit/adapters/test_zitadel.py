"""ZitadelIdentity request building, answer reading and error mapping, with no network (httpx.MockTransport)."""

import json
from collections.abc import Callable

import httpx
import pytest

from rdf_persistence.adapters.zitadel import ZitadelIdentity
from rdf_persistence.domain.exceptions import IdentityUnavailable, NotFound

ISSUER = "http://zitadel.test"
ORG, PROJECT = "org-1", "prj-1"
JSON = "application/json"


class Recorder:
    """A MockTransport handler that records each request and answers by method and path."""

    def __init__(
        self, routes: dict[tuple[str, str], httpx.Response | Callable[[], httpx.Response]]
    ):
        self.sent: list[httpx.Request] = []
        self._routes = routes

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.sent.append(request)
        route = self._routes.get((request.method, request.url.path))
        if route is None:
            return httpx.Response(404, text="no route in the test")
        return route() if callable(route) else route

    def body(self, index: int = 0) -> dict:
        return json.loads(self.sent[index].content)

    def calls(self) -> list[str]:
        return [f"{r.method} {r.url.path}" for r in self.sent]


def identity_answering(routes) -> tuple[ZitadelIdentity, Recorder]:
    recorder = Recorder(routes)
    client = ZitadelIdentity(
        ISSUER, "service-token", ORG, PROJECT, transport=httpx.MockTransport(recorder)
    )
    return client, recorder


def answer(text: str = "{}", status: int = 200) -> httpx.Response:
    return httpx.Response(status, text=text, headers={"content-type": JSON})


def human(user_id: str = "u1", email: str = "ann@example.org", state: str = "USER_STATE_ACTIVE"):
    return (
        f'{{"userId":"{user_id}","state":"{state}","username":"{email}",'
        f'"human":{{"email":{{"email":"{email}","isVerified":true}}}}}}'
    )


def machine(user_id: str = "u2", name: str = "bot", state: str = "USER_STATE_ACTIVE"):
    return f'{{"userId":"{user_id}","state":"{state}","username":"{name}","machine":{{"name":"{name}"}}}}'


def users(*found: str) -> httpx.Response:
    return answer(f'{{"result":[{",".join(found)}]}}')


def grant(grant_id: str, user_id: str, *roles: str) -> str:
    keys = ",".join(f'"{r}"' for r in roles)
    return f'{{"id":"{grant_id}","userId":"{user_id}","roleKeys":[{keys}]}}'


def grants(*found: str) -> httpx.Response:
    return answer(f'{{"result":[{",".join(found)}]}}')


USERS, GRANTS = ("POST", "/v2/users"), ("POST", "/management/v1/users/grants/_search")
USER_1 = ("GET", "/v2/users/u1")
USER_1_GRANTS = ("POST", "/management/v1/users/u1/grants")
GRANT_G1 = ("PUT", "/management/v1/users/u1/grants/g1")
GRANT_G1_GONE = ("DELETE", "/management/v1/users/u1/grants/g1")


# --- reading -----------------------------------------------------------------


async def test_find_by_email_asks_for_the_exact_email_in_the_organisation_with_the_service_token():
    client, recorder = identity_answering({USERS: users(human()), GRANTS: grants()})
    await client.find_by_email("ann@example.org")
    request = recorder.sent[0]
    assert request.headers["authorization"] == "Bearer service-token", "the service token"
    assert request.headers["x-zitadel-orgid"] == ORG, "the organisation"
    queries = recorder.body()["queries"]
    assert {"organizationIdQuery": {"organizationId": ORG}} in queries, "scoped to the organisation"
    assert {
        "emailQuery": {"emailAddress": "ann@example.org", "method": "TEXT_QUERY_METHOD_EQUALS"}
    } in queries, "an exact match"


async def test_find_by_email_returns_the_account_with_its_roles_in_the_project():
    client, recorder = identity_answering(
        {USERS: users(human()), GRANTS: grants(grant("g1", "u1", "admin", "auditor"))}
    )
    account = await client.find_by_email("ann@example.org")
    assert (account.account_id, account.user_name, account.email) == (
        "u1",
        "ann@example.org",
        "ann@example.org",
    )
    assert account.active is True, "active"
    assert account.global_roles == ["admin", "auditor"]
    grant_queries = recorder.body(1)["queries"]
    assert {"projectIdQuery": {"projectId": PROJECT}} in grant_queries, "this project's grants only"
    assert {"userIdQuery": {"userId": "u1"}} in grant_queries, "this account's grants only"


async def test_find_by_email_with_no_match_is_not_found():
    client, _ = identity_answering({USERS: users()})
    with pytest.raises(NotFound):
        await client.find_by_email("nobody@example.org")


@pytest.mark.parametrize(
    ("state", "active"),
    [
        ("USER_STATE_ACTIVE", True),
        ("USER_STATE_INACTIVE", False),
        ("USER_STATE_LOCKED", False),
        ("USER_STATE_INITIAL", False),
    ],
)
async def test_only_an_active_user_is_an_active_account(state, active):
    client, _ = identity_answering({USERS: users(human(state=state)), GRANTS: grants()})
    assert (await client.find_by_email("ann@example.org")).active is active


async def test_list_accounts_joins_each_account_with_its_roles_and_has_no_email_for_a_service_account():
    client, recorder = identity_answering(
        {USERS: users(human(), machine()), GRANTS: grants(grant("g1", "u2", "admin"))}
    )
    accounts = await client.list_accounts()
    assert [(a.user_name, a.email, a.global_roles) for a in accounts] == [
        ("ann@example.org", "ann@example.org", None),
        ("bot", None, ["admin"]),
    ]
    assert recorder.calls() == ["POST /v2/users", "POST /management/v1/users/grants/_search"]


async def test_list_accounts_reads_every_page():
    page = 100
    pages = iter(
        [
            users(*(human(f"u{n}", f"u{n}@example.org") for n in range(page))),
            users(human("last", "last@example.org")),
        ]
    )
    client, recorder = identity_answering({USERS: lambda: next(pages), GRANTS: grants()})
    accounts = await client.list_accounts()
    assert len(accounts) == page + 1, "both pages"
    assert [recorder.body(i)["query"]["offset"] for i in (0, 1)] == [0, page], "the second page"


# --- changing ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("method", "action"), [("disable", "deactivate"), ("enable", "reactivate")]
)
async def test_disable_and_enable_post_to_the_users_state_endpoints(method, action):
    client, recorder = identity_answering({("POST", f"/v2/users/u 1/{action}"): answer()})
    await getattr(client, method)("u 1")
    assert recorder.sent[0].url.raw_path == f"/v2/users/u%201/{action}".encode(), "id is escaped"


@pytest.mark.parametrize(
    ("method", "action"), [("disable", "deactivate"), ("enable", "reactivate")]
)
async def test_disabling_or_enabling_an_account_already_in_that_state_is_harmless(method, action):
    refusal = answer('{"code":9,"message":"User already inactive"}', status=400)
    client, _ = identity_answering({("POST", f"/v2/users/u1/{action}"): refusal})
    await getattr(client, method)("u1")


@pytest.mark.parametrize("method", ["disable", "enable"])
async def test_disabling_or_enabling_an_unknown_account_is_not_found(method):
    client, _ = identity_answering({})
    with pytest.raises(NotFound):
        await getattr(client, method)("missing")


async def test_the_first_global_role_creates_the_project_grant():
    client, recorder = identity_answering(
        {USER_1: answer(), GRANTS: grants(), USER_1_GRANTS: answer()}
    )
    await client.grant_global_role("u1", "admin")
    assert recorder.calls()[-1] == "POST /management/v1/users/u1/grants"
    assert recorder.body(-1) == {"projectId": PROJECT, "roleKeys": ["admin"]}


async def test_another_global_role_extends_the_existing_grant():
    client, recorder = identity_answering(
        {USER_1: answer(), GRANTS: grants(grant("g1", "u1", "admin")), GRANT_G1: answer()}
    )
    await client.grant_global_role("u1", "auditor")
    assert recorder.body(-1) == {"roleKeys": ["admin", "auditor"]}


async def test_granting_a_role_the_account_holds_changes_nothing():
    client, recorder = identity_answering(
        {USER_1: answer(), GRANTS: grants(grant("g1", "u1", "admin"))}
    )
    await client.grant_global_role("u1", "admin")
    assert "PUT" not in {r.method for r in recorder.sent}, "no update"


async def test_granting_a_role_the_project_lacks_is_not_found():
    refusal = answer('{"code":9,"message":"Errors.Project.Role.NotFound"}', status=400)
    client, _ = identity_answering({USER_1: answer(), GRANTS: grants(), USER_1_GRANTS: refusal})
    with pytest.raises(NotFound, match="role"):
        await client.grant_global_role("u1", "nosuch")


async def test_removing_one_of_several_roles_keeps_the_others():
    client, recorder = identity_answering(
        {
            USER_1: answer(),
            GRANTS: grants(grant("g1", "u1", "admin", "auditor")),
            GRANT_G1: answer(),
        }
    )
    await client.remove_global_role("u1", "admin")
    assert recorder.body(-1) == {"roleKeys": ["auditor"]}


async def test_removing_the_last_role_deletes_the_grant():
    client, recorder = identity_answering(
        {USER_1: answer(), GRANTS: grants(grant("g1", "u1", "admin")), GRANT_G1_GONE: answer()}
    )
    await client.remove_global_role("u1", "admin")
    assert recorder.calls()[-1] == "DELETE /management/v1/users/u1/grants/g1"


@pytest.mark.parametrize("held", [(), ("auditor",)], ids=["no grant", "other role only"])
async def test_removing_a_role_the_account_lacks_changes_nothing(held):
    found = (grant("g1", "u1", *held),) if held else ()
    client, recorder = identity_answering({USER_1: answer(), GRANTS: grants(*found)})
    await client.remove_global_role("u1", "admin")
    assert {r.method for r in recorder.sent} == {"GET", "POST"}, "only reads"


@pytest.mark.parametrize("method", ["grant_global_role", "remove_global_role"])
async def test_a_role_change_on_an_unknown_account_is_not_found(method):
    client, _ = identity_answering({})
    with pytest.raises(NotFound):
        await getattr(client, method)("missing", "admin")


# --- failures ----------------------------------------------------------------

CALLS = {
    "find_by_email": ("ann@example.org",),
    "list_accounts": (),
    "disable": ("u1",),
    "enable": ("u1",),
    "grant_global_role": ("u1", "admin"),
    "remove_global_role": ("u1", "admin"),
}


@pytest.mark.parametrize("method", CALLS)
@pytest.mark.parametrize("status", [500, 502, 503, 401, 403])
async def test_a_server_error_or_a_refused_service_token_is_identity_unavailable(method, status):
    transport = httpx.MockTransport(lambda request: answer(status=status))
    client = ZitadelIdentity(ISSUER, "t", ORG, PROJECT, transport=transport)
    with pytest.raises(IdentityUnavailable):
        await getattr(client, method)(*CALLS[method])


@pytest.mark.parametrize("method", CALLS)
async def test_an_unreachable_provider_is_identity_unavailable(method):
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    client = ZitadelIdentity(ISSUER, "t", ORG, PROJECT, transport=httpx.MockTransport(refuse))
    with pytest.raises(IdentityUnavailable):
        await getattr(client, method)(*CALLS[method])


@pytest.mark.parametrize("text", ["not json", '{"result":"no"}', '{"result":[{"userId":1}]}'])
async def test_an_unreadable_answer_is_identity_unavailable(text):
    client, _ = identity_answering({USERS: answer(text)})
    with pytest.raises(IdentityUnavailable):
        await client.find_by_email("ann@example.org")


async def test_the_service_token_is_not_in_the_error():
    client, _ = identity_answering({USERS: answer(status=401)})
    with pytest.raises(IdentityUnavailable) as caught:
        await client.find_by_email("ann@example.org")
    assert "service-token" not in str(caught.value), "the token stayed out of the message"
