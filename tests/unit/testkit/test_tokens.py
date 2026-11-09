"""``TokenSigner``: the tokens, JWKS and discovery document a test serves to a verifier."""

import httpx
import jwt
from cryptography.hazmat.primitives.asymmetric import rsa

from rdf_persistence.testkit.tokens import ISSUER, TokenSigner


async def get(signer: TokenSigner, url: str) -> httpx.Response:
    async with httpx.AsyncClient(transport=signer.transport) as client:
        return await client.get(url)


async def test_the_jwks_verifies_a_token_the_signer_issued() -> None:
    signer = TokenSigner()
    jwks = (await get(signer, f"{ISSUER}/keys")).json()
    key = jwt.PyJWKSet.from_dict(jwks)[signer.kid].key
    claims = jwt.decode(signer.issue(sub="u1"), key, algorithms=["RS256"], audience=signer.audience)
    assert claims["sub"] == "u1", "the token carries the subject asked for"
    assert claims["iss"] == ISSUER, "the token carries the issuer"


async def test_discovery_points_at_the_jwks() -> None:
    signer = TokenSigner()
    document = (await get(signer, f"{ISSUER}/.well-known/openid-configuration")).json()
    assert document["jwks_uri"] == f"{ISSUER}/keys", "discovery names the JWKS endpoint"
    assert document["issuer"] == ISSUER, "discovery names the issuer"


async def test_rotate_serves_old_and_new_keys_and_signs_with_the_new_one() -> None:
    signer = TokenSigner(kid="k1")
    signer.rotate("k2")
    jwks = (await get(signer, f"{ISSUER}/keys")).json()
    assert {k["kid"] for k in jwks["keys"]} == {"k1", "k2"}, "both keys are served"
    assert jwt.get_unverified_header(signer.issue())["kid"] == "k2", "new tokens use the new key"


async def test_unreachable_makes_every_request_fail_and_counts_none_as_served() -> None:
    signer = TokenSigner()
    signer.unreachable = True
    response = await get(signer, f"{ISSUER}/keys")
    assert response.status_code == 503, "the provider answers with a server error"
    assert signer.jwks_requests == 0, "a failed request is not a served JWKS"


async def test_jwks_requests_counts_the_fetches() -> None:
    signer = TokenSigner()
    await get(signer, f"{ISSUER}/keys")
    await get(signer, f"{ISSUER}/keys")
    assert signer.jwks_requests == 2, "each JWKS fetch is counted"


def test_the_roles_claim_is_an_object_keyed_by_role_name() -> None:
    signer = TokenSigner()
    claims = jwt.decode(signer.issue(roles=["admin"]), options={"verify_signature": False})
    assert list(claims[signer.roles_claim]) == ["admin"], (
        "Zitadel's shape: role name to organisations"
    )


async def verifies(token: str, signer: TokenSigner) -> bool:
    """Whether ``signer``'s JWKS verifies ``token``."""
    jwks = jwt.PyJWKSet.from_dict((await get(signer, f"{ISSUER}/keys")).json())
    try:
        jwt.decode(token, jwks[signer.kid].key, algorithms=["RS256"], audience=signer.audience)
    except jwt.InvalidSignatureError:
        return False
    return True


async def test_two_signers_from_one_key_verify_each_others_tokens() -> None:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    first, second = TokenSigner(key=key), TokenSigner(key=key)
    assert await verifies(first.issue(), second), "the second's JWKS verifies the first's token"
    assert await verifies(second.issue(), first), "the first's JWKS verifies the second's token"


async def test_two_signers_without_a_key_do_not_share_one() -> None:
    first, second = TokenSigner(), TokenSigner()
    assert not await verifies(first.issue(), second), "each signer generates its own key"


async def test_rotate_after_a_given_key_generates_a_new_key_and_keeps_the_given_one() -> None:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    signer = TokenSigner(kid="k1", key=key)
    signer.rotate("k2")
    jwks = jwt.PyJWKSet.from_dict((await get(signer, f"{ISSUER}/keys")).json())
    given = key.public_key().public_numbers()
    assert jwks["k1"].key.public_numbers() == given, "the given key stays in the JWKS"
    assert jwks["k2"].key.public_numbers() != given, "rotation generates a new key"
