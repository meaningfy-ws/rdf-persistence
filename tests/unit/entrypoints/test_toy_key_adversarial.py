"""Adversarial checks on the signing key the ``ToyService``s share (test-lanes RISK-3)."""

import jwt

from rdf_persistence.testkit.tokens import TokenSigner
from tests.toy_service import ToyService, toy_key
from tests.unit.entrypoints.test_service_kit import A_UUID


async def test_a_token_from_a_signer_with_another_key_is_a_401_even_under_the_same_kid() -> None:
    toy = ToyService()
    stranger = TokenSigner()
    assert stranger.kid == toy.signer.kid, "the kids collide, so only the key tells them apart"
    async with toy.app.router.lifespan_context(toy.app), toy.client() as http:
        response = await http.get(
            f"/libraries/{A_UUID}", headers={"Authorization": f"Bearer {stranger.issue()}"}
        )
    assert response.status_code == 401, "sharing toy_key does not make arbitrary signers trusted"


async def test_two_toy_services_share_the_key_but_not_state() -> None:
    first, second = ToyService(), ToyService()
    assert first.signer.public_key.public_numbers() == toy_key().public_key().public_numbers(), (
        "the first service signs with the shared key"
    )
    assert second.signer.public_key.public_numbers() == toy_key().public_key().public_numbers(), (
        "the second service signs with the shared key"
    )
    first.signer.unreachable = True
    first.signer.rotate("rotated")
    assert second.signer.unreachable is False, "unreachable is per service"
    assert second.signer.kid != "rotated", "a rotation in one service does not move the other"
    assert first.store is not second.store, "each service has its own store"
    assert jwt.get_unverified_header(second.signer.issue())["kid"] == second.signer.kid, (
        "the second service still signs under its own kid"
    )
    assert second.signer.public_key.public_numbers() == toy_key().public_key().public_numbers(), (
        "and still with the shared key, which the first's rotation did not touch"
    )
