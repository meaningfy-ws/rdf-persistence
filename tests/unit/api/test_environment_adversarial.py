"""Adversarial tests of ``settings_from_env`` (technical-models stage 3, task 3.4, PD-12, DEC-6).

Attacks: variables the prefix or the group names do not claim.
"""

from pathlib import Path

import pytest
from pydantic import ValidationError

from rdf_persistence.api.entrypoints.environment import settings_from_env
from rdf_persistence.api.entrypoints.generated.settings.rp_api_settings import ToolkitSettings

NOISE = {
    "PATH": "/usr/bin",
    "HOME": "/root",
    "RP": "1",
    "RPHTTP__MAX_ATTEMPTS": "9",  # the prefix without its underscore
    "XRP_HTTP__MAX_ATTEMPTS": "9",  # the prefix inside a longer name
    "APP_HTTP__MAX_ATTEMPTS": "9",  # another prefix
    "RP_NOSUCH__SLOT": "1",  # a group that does not exist
    "RP_NOSUCH": "1",
    "RP_UNRELATED_FLAG": "true",
}


def test_variables_without_the_prefix_or_naming_no_group_change_nothing() -> None:
    """Invariant: a variable without the prefix, or an ``RP_`` one naming no group, is ignored."""
    assert settings_from_env(ToolkitSettings, environ=NOISE) == ToolkitSettings()


def test_a_dotenv_file_in_the_working_directory_is_not_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Attacks D-34: no dotenv file and no secrets directory is read; the spec says it loads none."""
    (tmp_path / ".env").write_text("RP_HTTP__MAX_ATTEMPTS=9\n")
    (tmp_path / ".env.local").write_text("RP_HTTP__MAX_ATTEMPTS=9\n")
    monkeypatch.chdir(tmp_path)
    assert settings_from_env(ToolkitSettings, environ={}) == ToolkitSettings()


@pytest.mark.parametrize(
    "variable",
    [
        "RP_HTTP__READ_TIMEOUT_SECONDS",
        "RP_JWKS__UNKNOWN_KID_COOLDOWN_SECONDS",
        "RP_EVENTS__RETENTION_SECONDS",
        "RP_SSE__MAX_LIFETIME_SECONDS",
    ],
)
@pytest.mark.parametrize("text", ["inf", "1e309", "31536001"])
def test_a_duration_that_is_infinite_or_over_a_year_is_refused_from_the_environment(
    variable: str, text: str
) -> None:
    """D-55 1: one duration of each group (and the bound) is refused as a ValidationError."""
    with pytest.raises(ValidationError):
        settings_from_env(ToolkitSettings, environ={variable: text})
