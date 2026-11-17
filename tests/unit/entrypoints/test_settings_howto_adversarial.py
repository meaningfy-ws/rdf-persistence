"""Adversarial tests of the claims of ``howto/settings.adoc`` (technical-models stage 4).

Attacks: a misspelt group or slot in an ``RP_`` variable, and the non-finite durations of stage 3's F-1.
"""

import pytest
from pydantic import ValidationError

from rdf_persistence.entrypoints.environment import settings_from_env
from rdf_persistence.services.generated.settings.rp_settings import ToolkitSettings


def test_a_misspelt_group_is_ignored_and_the_default_stays() -> None:
    """The how-to says `RP_HTP__READ_TIMEOUT_SECONDS` is ignored without a message."""
    got = settings_from_env(ToolkitSettings, environ={"RP_HTP__READ_TIMEOUT_SECONDS": "60"})
    assert got == ToolkitSettings(), "a misspelt group changed the settings"


def test_a_misspelt_slot_raises_a_validation_error() -> None:
    """The how-to says `RP_HTTP__READ_TIMEOUT_SECOND` raises `Extra inputs are not permitted`."""
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        settings_from_env(ToolkitSettings, environ={"RP_HTTP__READ_TIMEOUT_SECOND": "60"})


def test_a_group_name_in_the_wrong_case_still_reads() -> None:
    """The how-to says the case does not matter."""
    got = settings_from_env(ToolkitSettings, environ={"rp_http__read_timeout_seconds": "61"})
    assert got.http.read_timeout_seconds == 61, "a lower-case variable was not read"


def test_a_single_underscore_after_the_group_is_not_a_group_separator() -> None:
    """Tries `RP_HTTP_READ_TIMEOUT_SECONDS`: no group, so ignored (and so a silent default)."""
    got = settings_from_env(ToolkitSettings, environ={"RP_HTTP_READ_TIMEOUT_SECONDS": "61"})
    assert got == ToolkitSettings(), "a variable with one underscore changed the settings"


@pytest.mark.parametrize(
    "variable",
    [
        "RP_HTTP__READ_TIMEOUT_SECONDS",
        "RP_HTTP__CONNECT_TIMEOUT_SECONDS",
        "RP_JWKS__TTL_SECONDS",
        "RP_JWKS__UNKNOWN_KID_COOLDOWN_SECONDS",
    ],
)
@pytest.mark.parametrize("text", ["inf", "+inf", "Infinity", "1e999", "nan"])
def test_a_non_finite_duration_is_refused(variable: str, text: str) -> None:
    """Stage 3 F-1: a timeout or cache lifetime of infinity or NaN means never; it must be a ValidationError."""
    with pytest.raises(ValidationError):
        settings_from_env(ToolkitSettings, environ={variable: text})


@pytest.mark.parametrize("text", ["inf", "nan"])
def test_a_non_finite_leeway_is_refused(text: str) -> None:
    """The leeway has an upper bound of 300, so infinity is refused by it."""
    with pytest.raises(ValidationError):
        settings_from_env(ToolkitSettings, environ={"RP_JWKS__LEEWAY_SECONDS": text})
