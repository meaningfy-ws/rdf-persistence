"""The ``TokenVerifier`` contract (spec rp-identity): a valid token gives a caller, every other gives ``InvalidToken``."""

import base64
import hmac
import json

import jwt
import pytest
from cryptography.hazmat.primitives import serialization

from rdf_persistence.adapters.jwks import JwksTokenVerifier
from rdf_persistence.domain.exceptions import InvalidToken
from rdf_persistence.services.tokens import TokenVerifier
from rdf_persistence.testkit.tokens import ISSUER, TokenSigner

NOW = 1_700_000_000.0


@pytest.fixture
def signer() -> TokenSigner:
    return TokenSigner(clock=lambda: NOW)


@pytest.fixture
def verifier(signer: TokenSigner) -> TokenVerifier:
    return JwksTokenVerifier(
        ISSUER, signer.audience, signer.roles_claim, transport=signer.transport, clock=lambda: NOW
    )


def public_pem(signer: TokenSigner) -> bytes:
    return signer.public_key.public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )


async def test_a_valid_token_gives_the_caller_with_the_principal_from_sub(
    signer: TokenSigner, verifier: TokenVerifier
) -> None:
    caller = await verifier.verify(signer.issue(sub="u1"))
    assert caller.principal == f"{ISSUER}/users/u1", (
        "the principal IRI is the issuer's users path plus sub"
    )


async def test_the_subject_is_percent_encoded_in_the_principal(
    signer: TokenSigner, verifier: TokenVerifier
) -> None:
    caller = await verifier.verify(signer.issue(sub="a b/c"))
    assert caller.principal == f"{ISSUER}/users/a%20b%2Fc", "a subject cannot break out of the path"


@pytest.mark.parametrize(
    ("roles", "expected"),
    [(["admin", "auditor"], ["admin", "auditor"]), ([], [])],
    ids=["object-keyed-by-role", "empty-object"],
)
async def test_global_roles_come_from_an_object_claim(
    signer: TokenSigner, verifier: TokenVerifier, roles: list[str], expected: list[str]
) -> None:
    caller = await verifier.verify(signer.issue(roles=roles))
    assert caller.global_roles == expected, "the role names are the keys of the claim"


async def test_global_roles_come_from_a_list_claim(
    signer: TokenSigner, verifier: TokenVerifier
) -> None:
    token = signer.issue(extra={signer.roles_claim: ["admin", "auditor"]})
    assert (await verifier.verify(token)).global_roles == ["admin", "auditor"], (
        "a list claim is read as is"
    )


async def test_an_absent_roles_claim_gives_no_roles(
    signer: TokenSigner, verifier: TokenVerifier
) -> None:
    token = signer.issue(roles=None)
    assert (await verifier.verify(token)).global_roles == [], "no claim, no global roles"


async def test_a_roles_claim_of_another_shape_gives_no_roles(
    signer: TokenSigner, verifier: TokenVerifier
) -> None:
    token = signer.issue(extra={signer.roles_claim: "admin"})
    assert (await verifier.verify(token)).global_roles == [], (
        "a string is not a role set, so nothing is granted"
    )


async def test_the_roles_claim_is_configurable(signer: TokenSigner) -> None:
    verifier = JwksTokenVerifier(
        ISSUER, signer.audience, "groups", transport=signer.transport, clock=lambda: NOW
    )
    token = signer.issue(extra={"groups": ["staff"]})
    assert (await verifier.verify(token)).global_roles == ["staff"], "the configured claim is read"


async def test_an_audience_list_containing_ours_is_accepted(
    signer: TokenSigner, verifier: TokenVerifier
) -> None:
    token = signer.issue(extra={"aud": ["other", signer.audience]})
    assert (await verifier.verify(token)).principal, "one matching audience is enough"


INVALID_TOKENS = [
    "expired",
    "not-yet-valid",
    "no-exp",
    "no-sub",
    "exp-not-a-number",
    "empty-sub",
    "wrong-issuer",
    "wrong-audience",
    "bad-signature",
    "alg-none",
    "hs256-with-the-public-key",
    "garbage",
    "empty",
    "missing-kid",
    "unknown-kid",
]


def b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def forge_hs256(signer: TokenSigner) -> str:
    """An HS256 token whose secret is the signer's public key, the classic algorithm-confusion attack.

    Built by hand because PyJWT itself refuses to HMAC with a PEM public key.
    """
    header = b64(json.dumps({"alg": "HS256", "typ": "JWT", "kid": signer.kid}).encode())
    claims = b64(
        json.dumps({"iss": ISSUER, "aud": signer.audience, "sub": "u", "exp": NOW + 60}).encode()
    )
    mac = hmac.new(public_pem(signer), f"{header}.{claims}".encode(), "sha256").digest()
    return f"{header}.{claims}.{b64(mac)}"


def make_invalid(name: str, signer: TokenSigner) -> str:
    other = TokenSigner(kid=signer.kid, clock=lambda: NOW)
    builders = {
        "expired": lambda: signer.issue(expires_in=-1),
        "not-yet-valid": lambda: signer.issue(not_before_in=60),
        "no-exp": lambda: signer.issue(expires_in=None),
        "no-sub": lambda: signer.issue(sub=None),
        "exp-not-a-number": lambda: signer.issue(extra={"exp": "soon"}),
        "empty-sub": lambda: signer.issue(sub=""),
        "wrong-issuer": lambda: signer.issue(issuer="https://evil.example"),
        "wrong-audience": lambda: signer.issue(audience="someone-else"),
        "bad-signature": lambda: other.issue(),
        "alg-none": lambda: jwt.encode(
            {"iss": ISSUER, "aud": signer.audience, "sub": "u", "exp": NOW + 60},
            None,
            algorithm="none",
        ),
        "hs256-with-the-public-key": lambda: forge_hs256(signer),
        "garbage": lambda: "not.a.token",
        "empty": lambda: "",
        "missing-kid": lambda: signer.issue(with_kid=False),
        "unknown-kid": lambda: signer.issue(kid="forged"),
    }
    return builders[name]()


@pytest.mark.parametrize("name", INVALID_TOKENS)
async def test_an_invalid_token_is_refused(
    name: str, signer: TokenSigner, verifier: TokenVerifier
) -> None:
    with pytest.raises(InvalidToken):
        await verifier.verify(make_invalid(name, signer))


async def test_an_expired_token(signer: TokenSigner, verifier: TokenVerifier) -> None:
    """Spec scenario "an expired token": the request is refused as unauthenticated."""
    with pytest.raises(InvalidToken, match="expired"):
        await verifier.verify(signer.issue(expires_in=-1))


async def test_hs256_is_refused_for_its_algorithm(
    signer: TokenSigner, verifier: TokenVerifier
) -> None:
    with pytest.raises(InvalidToken, match="algorithm"):
        await verifier.verify(forge_hs256(signer))
