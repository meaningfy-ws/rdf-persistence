"""The JWT-profile grant helper of the Zitadel testkit: the assertion it signs and the request it sends."""

import base64
import json

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from rdf_persistence.generation.generated.rp_generation import (
    MachineUser,
    ZitadelProject,
    ZitadelServer,
)
from rdf_persistence.testkit.exceptions import ProvisioningError, TokenRefusedError
from rdf_persistence.testkit.zitadel import (
    ADMIN_ROLE,
    access_token,
    client_assertion,
    create_machine_user,
    provision_project,
    token_scopes,
)

JWT_BEARER_GRANT = "urn:ietf:params:oauth:grant-type:jwt-bearer"
ISSUER = "http://zitadel.test"
NOW = 1_800_000_000.0


@pytest.fixture(scope="module")
def key_pair() -> tuple[str, rsa.RSAPublicKey]:
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = private.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption(),
    ).decode()
    return pem, private.public_key()


@pytest.fixture
def user(key_pair) -> MachineUser:
    return MachineUser(name="bot", user_id="u1", key_id="k1", private_key=key_pair[0])


@pytest.fixture
def project(user) -> ZitadelProject:
    return ZitadelProject(
        server=ZitadelServer(url=ISSUER, admin_pat="pat"),
        organisation_id="o1",
        project_id="p1",
        machine_users=[user],
    )


def test_the_assertion_is_signed_by_the_users_key_for_the_issuer(user, key_pair):
    token = client_assertion(ISSUER, user, now=NOW)
    claims = jwt.decode(
        token,
        key_pair[1],
        algorithms=["RS256"],
        audience=ISSUER,
        options={"verify_exp": False, "verify_iat": False},
    )
    assert (claims["iss"], claims["sub"]) == ("u1", "u1"), "the user is issuer and subject"
    assert jwt.get_unverified_header(token)["kid"] == "k1", "the key id"


def test_the_assertion_lives_for_a_minute_from_the_given_time(user, key_pair):
    claims = jwt.decode(
        client_assertion(ISSUER, user, now=NOW),
        key_pair[1],
        algorithms=["RS256"],
        audience=ISSUER,
        options={"verify_exp": False, "verify_iat": False},
    )
    assert (claims["iat"], claims["exp"]) == (int(NOW), int(NOW) + 60)


def test_the_scopes_ask_for_the_project_audience_and_the_roles(project):
    assert token_scopes("p1").split() == [
        "openid",
        "urn:zitadel:iam:org:project:id:p1:aud",
        "urn:zitadel:iam:org:projects:roles",
    ]


def test_the_token_request_is_a_jwt_profile_grant_with_the_scopes(project, user):
    sent: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return httpx.Response(200, json={"access_token": "the-token"})

    token = access_token(project, user, transport=httpx.MockTransport(handler))
    assert token == "the-token"
    form = dict(httpx.QueryParams(sent[0].content.decode()))
    assert sent[0].url.path == "/oauth/v2/token"
    assert form["grant_type"] == JWT_BEARER_GRANT
    assert form["scope"] == token_scopes("p1"), "the project audience and roles"
    assert "assertion" in form, "the signed assertion"


def test_a_refused_token_request_raises_without_the_users_key(project, user):
    refusal = httpx.MockTransport(lambda request: httpx.Response(400, json={"error": "invalid"}))
    with pytest.raises(TokenRefusedError) as caught:
        access_token(project, user, transport=refusal)
    assert caught.value.status_code == 400
    assert "BEGIN" not in str(caught.value), "the key stayed out of the message"


KEY_DETAILS = base64.b64encode(json.dumps({"keyId": "k9", "key": "PEM", "userId": "u9"}).encode())
USER_ROUTES = {
    "/management/v1/users/machine": {"userId": "u9", "details": {"sequence": "1"}},
    "/management/v1/users/u9/keys": {"keyId": "k9", "keyDetails": KEY_DETAILS.decode()},
    "/management/v1/users/u9/grants": {"userGrantId": "g9"},
}


class Zitadel:
    """A test Zitadel: answers by path, records each request."""

    def __init__(self, routes: dict[str, object]) -> None:
        self.routes = routes
        self.sent: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.sent.append(request)
        answer = self.routes.get(request.url.path)
        if isinstance(answer, httpx.Response):
            return answer
        return httpx.Response(200, json=answer) if answer is not None else httpx.Response(404)

    def body(self, path: str) -> dict:
        return json.loads(next(r for r in self.sent if r.url.path == path).content)


@pytest.fixture
def serving(monkeypatch: pytest.MonkeyPatch):
    """Make the testkit's HTTP clients talk to a ``Zitadel``."""

    def install(zitadel: Zitadel) -> Zitadel:
        client = httpx.Client
        monkeypatch.setattr(
            httpx, "Client", lambda **kw: client(transport=httpx.MockTransport(zitadel), **kw)
        )
        return zitadel

    return install


def test_a_machine_user_is_created_with_a_key_and_its_roles(serving, project):
    zitadel = serving(Zitadel(USER_ROUTES))
    made = create_machine_user(project, "bot-9", roles=[ADMIN_ROLE])
    assert (made.name, made.user_id, made.key_id, made.private_key) == ("bot-9", "u9", "k9", "PEM")
    assert zitadel.body("/management/v1/users/machine") == {
        "userName": "bot-9",
        "name": "bot-9",
        "accessTokenType": "ACCESS_TOKEN_TYPE_JWT",
    }
    assert zitadel.body("/management/v1/users/u9/keys") == {"type": "KEY_TYPE_JSON"}
    assert zitadel.body("/management/v1/users/u9/grants") == {
        "projectId": "p1",
        "roleKeys": [ADMIN_ROLE],
    }
    assert all(r.headers["x-zitadel-orgid"] == "o1" for r in zitadel.sent), "in the organisation"
    assert all(r.headers["authorization"] == "Bearer pat" for r in zitadel.sent)


def test_a_machine_user_without_roles_is_not_granted_any(serving, project):
    zitadel = serving(Zitadel(USER_ROUTES))
    create_machine_user(project, "bot-9")
    assert "/management/v1/users/u9/grants" not in [r.url.path for r in zitadel.sent]


@pytest.mark.parametrize(
    ("path", "answer"),
    [
        ("/management/v1/users/machine", {"no": "userId"}),
        ("/management/v1/users/machine", httpx.Response(200, text="not json")),
        ("/management/v1/users/u9/keys", {"no": "keyDetails"}),
        ("/management/v1/users/u9/keys", {"keyDetails": "!!not base64!!"}),
        ("/management/v1/users/u9/keys", {"keyDetails": base64.b64encode(b'{"no": 1}').decode()}),
    ],
    ids=["no-user-id", "not-json", "no-key-details", "not-base64", "no-key-in-the-file"],
)
def test_a_malformed_answer_is_a_provisioning_error(serving, project, path, answer):
    serving(Zitadel({**USER_ROUTES, path: answer}))
    with pytest.raises(ProvisioningError, match="unreadably"):
        create_machine_user(project, "bot-9")


def test_a_refused_call_is_a_provisioning_error_with_the_status_only(serving, project):
    refusal = httpx.Response(403, text="the pat is secret-pat")
    serving(Zitadel({**USER_ROUTES, "/management/v1/users/machine": refusal}))
    with pytest.raises(ProvisioningError, match="403") as caught:
        create_machine_user(project, "bot-9")
    assert "secret-pat" not in str(caught.value), "the answer's text stays out of the message"


def test_the_project_is_provisioned_with_the_admin_role_and_a_user_per_principal(serving):
    zitadel = serving(
        Zitadel(
            {
                "/management/v1/orgs/me": {"org": {"id": "o1", "name": "acme"}},
                "/management/v1/projects": {"id": "p1"},
                "/management/v1/projects/p1/roles": {},
                **USER_ROUTES,
            }
        )
    )
    server = ZitadelServer(url=ISSUER, admin_pat="pat")
    provisioned = provision_project(server, [ADMIN_ROLE, "reader"])
    assert (provisioned.organisation_id, provisioned.project_id) == ("o1", "p1")
    assert [u.name for u in provisioned.machine_users] == [ADMIN_ROLE, "reader"]
    assert zitadel.body("/management/v1/projects") == {"name": "rp-test"}
    assert zitadel.body("/management/v1/projects/p1/roles") == {
        "roleKey": ADMIN_ROLE,
        "displayName": ADMIN_ROLE,
    }
    grants = [r for r in zitadel.sent if r.url.path == "/management/v1/users/u9/grants"]
    assert len(grants) == 1, "only the admin principal is granted a role"


def test_an_unreadable_organisation_answer_is_a_provisioning_error(serving):
    serving(Zitadel({"/management/v1/orgs/me": {"org": {}}}))
    with pytest.raises(ProvisioningError, match="unreadably"):
        provision_project(ZitadelServer(url=ISSUER, admin_pat="pat"), [])


def test_an_unreadable_token_answer_is_a_provisioning_error(project, user):
    transport = httpx.MockTransport(lambda _r: httpx.Response(200, json={"token": "x"}))
    with pytest.raises(ProvisioningError, match="unreadably"):
        access_token(project, user, transport=transport)
