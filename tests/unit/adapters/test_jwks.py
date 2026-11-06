"""``JwksTokenVerifier``'s key handling: discovery, the cache, one refresh per unknown kid, an unreachable provider."""

import httpx
import pytest

from rdf_persistence.adapters.jwks import JWKS_TTL_SECONDS, JwksTokenVerifier
from rdf_persistence.domain.exceptions import IdentityUnavailable, InvalidToken
from rdf_persistence.testkit.tokens import ISSUER, TokenSigner

DISCOVERY_PATH = "/.well-known/openid-configuration"
PAST_COOLDOWN = 11.0


class ManualClock:
    """A clock a test moves by hand."""

    def __init__(self) -> None:
        self.now = 1_000_000.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def clock() -> ManualClock:
    return ManualClock()


@pytest.fixture
def signer(clock: ManualClock) -> TokenSigner:
    return TokenSigner(clock=clock)


def verifier_for(signer: TokenSigner, clock: ManualClock, **kwargs: str) -> JwksTokenVerifier:
    return JwksTokenVerifier(
        ISSUER,
        signer.audience,
        signer.roles_claim,
        http_client=signer.client,
        clock=clock,
        **kwargs,
    )


async def test_keys_are_fetched_once_and_cached(signer: TokenSigner, clock: ManualClock) -> None:
    verifier = verifier_for(signer, clock)
    for _ in range(3):
        await verifier.verify(signer.issue())
    assert signer.jwks_requests == 1, "three valid tokens, one fetch"


async def test_an_explicit_jwks_uri_skips_discovery(
    signer: TokenSigner, clock: ManualClock
) -> None:
    seen: list[str] = []

    def spy(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        return signer.handle(request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(spy))
    verifier = JwksTokenVerifier(
        ISSUER,
        signer.audience,
        signer.roles_claim,
        jwks_uri=f"{ISSUER}/keys",
        http_client=client,
        clock=clock,
    )
    await verifier.verify(signer.issue())
    assert DISCOVERY_PATH not in seen, "no discovery request when the JWKS address is given"


async def test_the_cache_expires_after_the_ttl(signer: TokenSigner, clock: ManualClock) -> None:
    verifier = verifier_for(signer, clock)
    await verifier.verify(signer.issue())
    clock.now += JWKS_TTL_SECONDS - 1
    await verifier.verify(signer.issue())
    assert signer.jwks_requests == 1, "still cached just before the TTL"
    clock.now += 2
    await verifier.verify(signer.issue())
    assert signer.jwks_requests == 2, "fetched again once the TTL has passed"


async def test_an_unknown_kid_triggers_one_refresh_then_is_accepted(
    signer: TokenSigner, clock: ManualClock
) -> None:
    verifier = verifier_for(signer, clock)
    await verifier.verify(signer.issue())
    signer.rotate("k2")
    clock.now += PAST_COOLDOWN
    caller = await verifier.verify(signer.issue(sub="u2"))
    assert caller.principal.endswith("/u2"), "the rotated key is picked up"
    assert signer.jwks_requests == 2, "exactly one refresh"


async def test_a_burst_of_unknown_kids_refreshes_once(
    signer: TokenSigner, clock: ManualClock
) -> None:
    verifier = verifier_for(signer, clock)
    await verifier.verify(signer.issue())
    clock.now += PAST_COOLDOWN
    for _ in range(5):
        with pytest.raises(InvalidToken):
            await verifier.verify(signer.issue(kid="forged"))
    assert signer.jwks_requests == 2, (
        "the first unknown kid refreshes; the rest do not hammer the provider"
    )


async def test_discovery_is_not_repeated_on_refresh(
    signer: TokenSigner, clock: ManualClock
) -> None:
    verifier = verifier_for(signer, clock)
    await verifier.verify(signer.issue())
    clock.now += JWKS_TTL_SECONDS + 1
    await verifier.verify(signer.issue())
    assert signer.discovery_requests == 1, "the JWKS address found once is kept"


async def test_unreachable_provider_with_no_cached_keys_is_unavailable(
    signer: TokenSigner, clock: ManualClock
) -> None:
    signer.unreachable = True
    with pytest.raises(IdentityUnavailable):
        await verifier_for(signer, clock).verify(signer.issue())


async def test_unreachable_provider_serves_cached_keys_until_the_ttl(
    signer: TokenSigner, clock: ManualClock
) -> None:
    verifier = verifier_for(signer, clock)
    await verifier.verify(signer.issue())
    signer.unreachable = True
    clock.now += JWKS_TTL_SECONDS - 1
    await verifier.verify(signer.issue())
    clock.now += 2
    with pytest.raises(IdentityUnavailable):
        await verifier.verify(signer.issue())


async def test_a_refresh_for_an_unknown_kid_that_fails_is_unavailable(
    signer: TokenSigner, clock: ManualClock
) -> None:
    verifier = verifier_for(signer, clock)
    await verifier.verify(signer.issue())
    signer.unreachable = True
    clock.now += PAST_COOLDOWN
    with pytest.raises(IdentityUnavailable):
        await verifier.verify(signer.issue(kid="forged"))


async def test_a_transport_error_is_unavailable(clock: ManualClock) -> None:
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down", request=request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(refuse))
    verifier = JwksTokenVerifier(ISSUER, "aud", "roles", http_client=client, clock=clock)
    with pytest.raises(IdentityUnavailable):
        await verifier.verify(TokenSigner(clock=clock).issue())


@pytest.mark.parametrize(
    "body", ["not json", '{"no": "jwks_uri"}'], ids=["not-json", "no-jwks-uri"]
)
async def test_a_broken_discovery_document_is_unavailable(body: str, clock: ManualClock) -> None:
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _r: httpx.Response(200, text=body))
    )
    verifier = JwksTokenVerifier(ISSUER, "aud", "roles", http_client=client, clock=clock)
    with pytest.raises(IdentityUnavailable):
        await verifier.verify(TokenSigner(clock=clock).issue())


async def test_a_jwks_without_a_usable_key_is_unavailable(clock: ManualClock) -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        if request.url.path == DISCOVERY_PATH:
            return httpx.Response(200, json={"jwks_uri": f"{ISSUER}/keys"})
        return httpx.Response(200, json={"keys": "oops"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
    verifier = JwksTokenVerifier(ISSUER, "aud", "roles", http_client=client, clock=clock)
    with pytest.raises(IdentityUnavailable):
        await verifier.verify(TokenSigner(clock=clock).issue())
