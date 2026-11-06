"""The JWT-profile grant helper of the Zitadel testkit: the assertion it signs and the request it sends."""

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
from rdf_persistence.testkit.zitadel import (
    JWT_BEARER_GRANT,
    TokenRefusedError,
    access_token,
    client_assertion,
    token_scopes,
)

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
