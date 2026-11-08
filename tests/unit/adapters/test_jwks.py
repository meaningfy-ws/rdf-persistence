"""``JwksTokenVerifier``'s key handling: discovery, the cache, one refresh per unknown kid, an unreachable provider."""

import asyncio

import httpx
import pytest

from rdf_persistence.adapters.jwks import DISCOVERY_PATH, JWKS_TTL_SECONDS, JwksTokenVerifier
from rdf_persistence.domain.exceptions import IdentityUnavailable, InvalidToken
from rdf_persistence.domain.generated.service.rp_service import IriPolicy, ServiceSettings
from rdf_persistence.domain.iris import Iris
from rdf_persistence.testkit.tokens import ISSUER, TokenSigner

PAST_COOLDOWN = 11.0
WITHIN_COOLDOWN = 1.0


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


def verifier_for(signer: TokenSigner, clock: ManualClock, **kwargs: object) -> JwksTokenVerifier:
    return JwksTokenVerifier(
        ISSUER,
        signer.audience,
        signer.roles_claim,
        transport=signer.transport,
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

    verifier = JwksTokenVerifier(
        ISSUER,
        signer.audience,
        signer.roles_claim,
        jwks_uri=f"{ISSUER}/keys",
        transport=httpx.MockTransport(spy),
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

    verifier = JwksTokenVerifier(
        ISSUER, "aud", "roles", transport=httpx.MockTransport(refuse), clock=clock
    )
    with pytest.raises(IdentityUnavailable):
        await verifier.verify(TokenSigner(clock=clock).issue())


@pytest.mark.parametrize(
    "body", ["not json", '{"no": "jwks_uri"}'], ids=["not-json", "no-jwks-uri"]
)
async def test_a_broken_discovery_document_is_unavailable(body: str, clock: ManualClock) -> None:
    transport = httpx.MockTransport(lambda _r: httpx.Response(200, text=body))
    verifier = JwksTokenVerifier(ISSUER, "aud", "roles", transport=transport, clock=clock)
    with pytest.raises(IdentityUnavailable):
        await verifier.verify(TokenSigner(clock=clock).issue())


async def test_a_jwks_without_a_usable_key_is_unavailable(clock: ManualClock) -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        if request.url.path == DISCOVERY_PATH:
            return httpx.Response(200, json={"jwks_uri": f"{ISSUER}/keys"})
        return httpx.Response(200, json={"keys": "oops"})

    transport = httpx.MockTransport(respond)
    verifier = JwksTokenVerifier(ISSUER, "aud", "roles", transport=transport, clock=clock)
    with pytest.raises(IdentityUnavailable):
        await verifier.verify(TokenSigner(clock=clock).issue())


# --- availability (PD-28a): a request never queues on the network for another's sake ----------


class StallingProvider:
    """A provider a test can hold: every request is counted, and waits for ``release`` while ``stalled``."""

    def __init__(self, signer: TokenSigner) -> None:
        self._signer = signer
        self.stalled = False
        self.calls = 0
        self.release = asyncio.Event()
        self.transport = httpx.MockTransport(self._handle)

    async def _handle(self, request: httpx.Request) -> httpx.Response:
        self.calls += 1
        if self.stalled:
            await self.release.wait()
        return self._signer.handle(request)


async def let_tasks_run() -> None:
    for _ in range(20):
        await asyncio.sleep(0)


@pytest.fixture
def provider(signer: TokenSigner) -> StallingProvider:
    return StallingProvider(signer)


def verifier_over(provider: StallingProvider, signer: TokenSigner, clock: ManualClock):
    return JwksTokenVerifier(
        ISSUER, signer.audience, signer.roles_claim, transport=provider.transport, clock=clock
    )


async def test_a_forged_kid_during_a_slow_provider_does_not_delay_a_valid_token(
    signer: TokenSigner, provider: StallingProvider, clock: ManualClock
) -> None:
    verifier = verifier_over(provider, signer, clock)
    good = signer.issue()
    await verifier.verify(good)
    clock.now += PAST_COOLDOWN
    provider.stalled = True
    forged = asyncio.create_task(verifier.verify(signer.issue(kid="forged")))
    await let_tasks_run()
    assert not forged.done(), "the forged-kid request is waiting on the provider"
    caller = await asyncio.wait_for(verifier.verify(good), timeout=1)
    assert caller.principal, "a cached key needs no lock and no network"
    provider.release.set()
    with pytest.raises(InvalidToken):
        await forged


async def test_requests_after_the_expiry_during_an_outage_make_one_provider_call(
    signer: TokenSigner, provider: StallingProvider, clock: ManualClock
) -> None:
    verifier = verifier_over(provider, signer, clock)
    good = signer.issue()
    await verifier.verify(good)
    clock.now += JWKS_TTL_SECONDS + 1
    signer.unreachable = True
    provider.stalled = True
    provider.calls = 0
    requests = [asyncio.create_task(verifier.verify(good)) for _ in range(5)]
    await let_tasks_run()
    provider.release.set()
    results = await asyncio.gather(*requests, return_exceptions=True)
    assert all(isinstance(result, IdentityUnavailable) for result in results)
    assert provider.calls == 1, "one refresh is made; the rest share its outcome"


async def test_stale_keys_inside_the_cooldown_are_unavailable_without_a_call(
    signer: TokenSigner, provider: StallingProvider, clock: ManualClock
) -> None:
    verifier = verifier_over(provider, signer, clock)
    good = signer.issue()
    await verifier.verify(good)
    clock.now += JWKS_TTL_SECONDS + 1
    signer.unreachable = True
    provider.calls = 0
    for _ in range(3):
        with pytest.raises(IdentityUnavailable):
            await verifier.verify(good)
        clock.now += WITHIN_COOLDOWN
    assert provider.calls == 1, "the cooldown holds for stale keys too"
    clock.now += PAST_COOLDOWN
    with pytest.raises(IdentityUnavailable):
        await verifier.verify(good)
    assert provider.calls == 2, "and ends"


async def test_an_unknown_kid_during_an_outage_is_refused_not_unavailable(
    signer: TokenSigner, provider: StallingProvider, clock: ManualClock
) -> None:
    verifier = verifier_over(provider, signer, clock)
    await verifier.verify(signer.issue())
    clock.now += PAST_COOLDOWN
    signer.unreachable = True
    provider.calls = 0
    with pytest.raises(IdentityUnavailable):
        await verifier.verify(signer.issue(kid="forged"))
    for _ in range(3):
        with pytest.raises(InvalidToken):
            await verifier.verify(signer.issue(kid="forged"))
    assert provider.calls == 1, "inside the cooldown the answer is immediate: 401, not 503"


# --- the issuer (PD-28a) -------------------------------------------------------------------


async def test_a_discovery_document_naming_another_issuer_is_unavailable(
    signer: TokenSigner, clock: ManualClock
) -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        if request.url.path == DISCOVERY_PATH:
            return httpx.Response(
                200, json={"issuer": "https://evil.test", "jwks_uri": f"{ISSUER}/keys"}
            )
        return signer.handle(request)

    verifier = JwksTokenVerifier(
        ISSUER,
        signer.audience,
        signer.roles_claim,
        transport=httpx.MockTransport(respond),
        clock=clock,
    )
    with pytest.raises(IdentityUnavailable, match="issuer"):
        await verifier.verify(signer.issue())


def test_an_issuer_that_is_not_https_is_refused() -> None:
    with pytest.raises(ValueError, match="https"):
        JwksTokenVerifier("http://idp.test", "aud", "roles")


def test_an_insecure_issuer_is_allowed_when_the_caller_opts_out() -> None:
    assert JwksTokenVerifier("http://idp.test", "aud", "roles", allow_insecure_issuer=True)


@pytest.mark.parametrize("field", ["issuer", "audience", "roles_claim"])
def test_an_empty_issuer_audience_or_roles_claim_is_refused(field: str) -> None:
    arguments = {"issuer": "https://idp.test", "audience": "aud", "roles_claim": "roles"}
    arguments[field] = ""
    with pytest.raises(ValueError, match=field):
        JwksTokenVerifier(**arguments)


# --- the principal IRI follows the IRI policy (PD-2, PD-3a) --------------------------------------

PRINCIPAL_BASE = "http://mwb.meaningfy.ws/"


async def test_the_default_principal_is_the_issuer_and_the_subject(
    signer: TokenSigner, clock: ManualClock
) -> None:
    caller = await verifier_for(signer, clock).verify(signer.issue(sub="user-1"))
    assert caller.principal == f"{ISSUER}/users/user-1", "the default principal IRI changed"


@pytest.mark.parametrize(
    ("sub", "segment"), [("a/b", "a%2Fb"), ("100%", "100%25"), ("a b", "a%20b")]
)
async def test_a_policy_principal_keeps_the_subject_in_one_segment(
    signer: TokenSigner, clock: ManualClock, sub: str, segment: str
) -> None:
    iris = Iris(
        ServiceSettings(
            base=PRINCIPAL_BASE,
            prefix="mwb",
            tenant_segment="projects",
            creator_role="owner",
            roles_claim=signer.roles_claim,
            deployment="k3f9a2x",
            iri_policy=IriPolicy(principal_template="{base}{deployment}/user/{sub}"),
        )
    )
    verifier = verifier_for(signer, clock, iris=iris)
    caller = await verifier.verify(signer.issue(sub=sub))
    assert caller.principal == f"{PRINCIPAL_BASE}k3f9a2x/user/{segment}", (
        "the subject left its segment"
    )
