"""Adversarial tests of ``TokenSigner.issue`` built on ``JwtClaims.model_construct`` (technical-models stage 4).

Attacks: every combination of the arguments, against the claims the former dict-building code made.
"""

import itertools
import warnings
from collections.abc import Mapping, Sequence

import jwt
import pytest

from rdf_persistence.testkit.tokens import AUDIENCE, ISSUER, ORG_DOMAIN, ORG_ID, TokenSigner

NOW = 1_700_000_000.0
SIGNER = TokenSigner(clock=lambda: NOW)
ROLES_CLAIM = SIGNER.roles_claim


def former_claims(
    *,
    sub: str | None,
    roles: Sequence[str] | None,
    expires_in: float | None,
    not_before_in: float | None,
    issuer: str,
    audience: str | list[str] | None,
    extra: Mapping[str, object] | None,
) -> dict[str, object]:
    """The claims the dict-building code of the stage before wrote."""
    claims: dict[str, object] = {"iss": issuer, "aud": audience or AUDIENCE, "iat": NOW}
    if sub is not None:
        claims["sub"] = sub
    if expires_in is not None:
        claims["exp"] = NOW + expires_in
    if not_before_in is not None:
        claims["nbf"] = NOW + not_before_in
    if roles is not None:
        claims[ROLES_CLAIM] = {role: {ORG_ID: ORG_DOMAIN} for role in roles}
    claims.update(extra or {})
    return claims


def claims_of(token: str) -> dict[str, object]:
    return jwt.decode(
        token,
        options={
            "verify_signature": False,
            "verify_aud": False,
            "verify_exp": False,
            "verify_nbf": False,
            "verify_iat": False,
        },
    )


SUBS = ["user-1", None, "", "ünï"]
EXPIRES = [300.0, None, 0, -5]
NOT_BEFORE = [None, 60.0]
ROLES = [(), None, ("admin", "reader")]
AUDIENCES = [None, "other", ["a", "b"], "", []]
EXTRAS = [None, {"iss": "evil"}, {"aud": ["x"]}, {"exp": 1}, {"sub": None}, {"azp": "c"}]


@pytest.mark.parametrize(
    ("sub", "expires_in", "not_before_in"), list(itertools.product(SUBS, EXPIRES, NOT_BEFORE))
)
def test_claims_equal_the_former_ones_for_every_sub_exp_nbf(sub, expires_in, not_before_in) -> None:
    """Tries the product of subject, lifetime and not-before values, `exp=0` and negatives included."""
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        token = SIGNER.issue(sub=sub, expires_in=expires_in, not_before_in=not_before_in)
    expected = former_claims(
        sub=sub,
        roles=(),
        expires_in=expires_in,
        not_before_in=not_before_in,
        issuer=ISSUER,
        audience=None,
        extra=None,
    )
    assert claims_of(token) == expected, "the claims differ from the former ones"


@pytest.mark.parametrize(
    ("audience", "extra", "roles"), list(itertools.product(AUDIENCES, EXTRAS, ROLES))
)
def test_claims_equal_the_former_ones_for_every_audience_extra_roles(
    audience, extra, roles
) -> None:
    """Tries audience lists and empties, an `extra` overriding iss/aud/exp/sub/iat, and every roles form."""
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        token = SIGNER.issue(audience=audience, extra=extra, roles=roles)
    expected = former_claims(
        sub="user-1",
        roles=roles,
        expires_in=300.0,
        not_before_in=None,
        issuer=ISSUER,
        audience=audience,
        extra=extra,
    )
    assert claims_of(token) == expected, "the claims differ from the former ones"


@pytest.mark.parametrize("issuer", ["", "https://other", "x" * 300])
def test_the_issuer_is_written_as_given(issuer: str) -> None:
    """Tries an empty and an odd issuer, which the former code wrote unchanged."""
    assert claims_of(SIGNER.issue(issuer=issuer))["iss"] == issuer, "the issuer is changed"


def test_an_integer_clock_gives_integer_claims_unchanged() -> None:
    """Tries a clock that returns whole seconds: `iat` and `exp` stay whole numbers, as before."""
    signer = TokenSigner(clock=lambda: 1_700_000_000)
    claims = claims_of(signer.issue(expires_in=60))
    assert claims["iat"] == claims["exp"] - 60 == 1_700_000_000, "the integer claims changed"


@pytest.mark.xfail(strict=True, reason="under the floor, design D-55")
def test_a_non_string_subject_is_still_written_for_a_verifier_to_refuse() -> None:
    """Tries `sub=123`: a test token may carry a subject the wire model refuses (the stated reason for model_construct)."""
    with warnings.catch_warnings():
        warnings.simplefilter("error")  # a serializer warning on a deliberate test token is noise
        claims = claims_of(SIGNER.issue(sub=123))  # type: ignore[arg-type]
    assert claims["sub"] == 123, "the subject was dropped or coerced"


def test_a_token_that_claims_the_azp_or_unknown_claim_through_extra_keeps_it() -> None:
    """Tries an extra claim of a name the wire model declares (`azp`) and one it does not."""
    claims = claims_of(SIGNER.issue(extra={"azp": "client", "whatever": [1, 2]}))
    assert claims["azp"] == "client", "a declared extra claim is lost"
    assert claims["whatever"] == [1, 2], "an unknown extra claim is lost"
