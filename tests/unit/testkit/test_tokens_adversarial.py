"""Adversarial checks on a ``TokenSigner`` that starts from a shared key (test-lanes RISK-3)."""

import httpx
import jwt
from cryptography.hazmat.primitives.asymmetric import rsa

from rdf_persistence.testkit.tokens import ISSUER, TokenSigner, new_key


async def jwks_of(signer: TokenSigner) -> jwt.PyJWKSet:
    async with httpx.AsyncClient(transport=signer.transport) as client:
        return jwt.PyJWKSet.from_dict((await client.get(f"{ISSUER}/keys")).json())


def numbers(key: rsa.RSAPrivateKey) -> rsa.RSAPublicNumbers:
    return key.public_key().public_numbers()


async def test_rotating_one_signer_leaves_a_signer_on_the_same_key_untouched() -> None:
    key = new_key()
    rotated, bystander = TokenSigner(kid="k1", key=key), TokenSigner(kid="k1", key=key)
    rotated.rotate("k2")
    jwks = await jwks_of(bystander)
    assert [jwk.key_id for jwk in jwks.keys] == ["k1"], "the bystander still serves only its key"
    assert jwt.get_unverified_header(bystander.issue())["kid"] == "k1", "and still signs with it"
    assert bystander.kid == "k1", "its current kid did not move"


async def test_rotation_never_replaces_the_given_key_object() -> None:
    key = new_key()
    before = numbers(key)
    signer = TokenSigner(kid="k1", key=key)
    signer.rotate("k2")
    signer.rotate("k3")
    assert numbers(key) == before, "the shared key object is unchanged"
    assert signer.public_key.public_numbers() != before, "the signer now signs with a new key"


async def test_rotating_back_to_the_first_kid_replaces_the_given_key_in_this_signer_only() -> None:
    key = new_key()
    signer, other = TokenSigner(kid="k1", key=key), TokenSigner(kid="k1", key=key)
    signer.rotate("k1")
    assert (await jwks_of(signer))["k1"].key.public_numbers() != numbers(key), (
        "the rotated kid now holds a fresh key"
    )
    assert (await jwks_of(other))["k1"].key.public_numbers() == numbers(key), (
        "the other signer keeps the shared key under the same kid"
    )


async def test_a_custom_kid_names_the_given_key_in_the_jwks_and_the_token_header() -> None:
    key = new_key()
    signer = TokenSigner(kid="mine", key=key)
    jwks = await jwks_of(signer)
    assert jwks["mine"].key.public_numbers() == numbers(key), "the JWKS serves the given key"
    assert jwt.get_unverified_header(signer.issue())["kid"] == "mine", "the header names the kid"


async def test_a_token_from_a_keyless_signer_with_the_same_kid_fails_verification() -> None:
    key = new_key()
    shared, stranger = TokenSigner(key=key), TokenSigner()
    assert shared.kid == stranger.kid, "the kids collide, so only the key tells them apart"
    verifying_key = (await jwks_of(shared))[shared.kid].key
    try:
        jwt.decode(stranger.issue(), verifying_key, algorithms=["RS256"], audience=shared.audience)
    except jwt.InvalidSignatureError:
        return
    raise AssertionError("a token signed with another key must not verify")


async def test_signer_state_is_per_signer_even_when_the_key_is_shared() -> None:
    key = new_key()
    first, second = TokenSigner(key=key), TokenSigner(key=key)
    first.unreachable = True
    await jwks_of(second)
    assert second.jwks_requests == 1, "the second signer counts its own fetch"
    assert first.jwks_requests == 0, "the first signer counted nothing"
    assert second.unreachable is False, "unreachable is not shared"
