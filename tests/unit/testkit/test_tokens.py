"""``TokenSigner``: the tokens, JWKS and discovery document a test serves to a verifier."""

import jwt

from rdf_persistence.testkit.tokens import ISSUER, TokenSigner


async def test_the_jwks_verifies_a_token_the_signer_issued() -> None:
    signer = TokenSigner()
    jwks = (await signer.client.get(f"{ISSUER}/keys")).json()
    key = jwt.PyJWKSet.from_dict(jwks)[signer.kid].key
    claims = jwt.decode(signer.issue(sub="u1"), key, algorithms=["RS256"], audience=signer.audience)
    assert claims["sub"] == "u1", "the token carries the subject asked for"
    assert claims["iss"] == ISSUER, "the token carries the issuer"


async def test_discovery_points_at_the_jwks() -> None:
    signer = TokenSigner()
    document = (await signer.client.get(f"{ISSUER}/.well-known/openid-configuration")).json()
    assert document["jwks_uri"] == f"{ISSUER}/keys", "discovery names the JWKS endpoint"
    assert document["issuer"] == ISSUER, "discovery names the issuer"


async def test_rotate_serves_old_and_new_keys_and_signs_with_the_new_one() -> None:
    signer = TokenSigner(kid="k1")
    signer.rotate("k2")
    jwks = (await signer.client.get(f"{ISSUER}/keys")).json()
    assert {k["kid"] for k in jwks["keys"]} == {"k1", "k2"}, "both keys are served"
    assert jwt.get_unverified_header(signer.issue())["kid"] == "k2", "new tokens use the new key"


async def test_unreachable_makes_every_request_fail_and_counts_none_as_served() -> None:
    signer = TokenSigner()
    signer.unreachable = True
    response = await signer.client.get(f"{ISSUER}/keys")
    assert response.status_code == 503, "the provider answers with a server error"
    assert signer.jwks_requests == 0, "a failed request is not a served JWKS"


async def test_jwks_requests_counts_the_fetches() -> None:
    signer = TokenSigner()
    await signer.client.get(f"{ISSUER}/keys")
    await signer.client.get(f"{ISSUER}/keys")
    assert signer.jwks_requests == 2, "each JWKS fetch is counted"


def test_the_roles_claim_is_an_object_keyed_by_role_name() -> None:
    signer = TokenSigner()
    claims = jwt.decode(signer.issue(roles=["admin"]), options={"verify_signature": False})
    assert list(claims[signer.roles_claim]) == ["admin"], "Zitadel's shape: role name to organisations"
