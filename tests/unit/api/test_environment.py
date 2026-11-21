"""`settings_from_env` builds a generated settings model from environment variables (PD-12, DEC-6)."""

import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import BaseModel, Field, SecretStr, ValidationError

import rdf_persistence
from rdf_persistence.api.entrypoints.environment import settings_from_env
from rdf_persistence.api.entrypoints.generated.settings.rp_api_settings import ToolkitSettings
from rdf_persistence.iris.services.generated.rp_iris_services import ServiceSettings

ROOT = Path(__file__).parents[3]


def test_tc40_a_nested_value_is_read_and_every_other_value_keeps_its_default() -> None:
    read = settings_from_env(ToolkitSettings, environ={"RP_HTTP__READ_TIMEOUT_SECONDS": "60"})

    expected = ToolkitSettings().model_dump()
    expected["http"]["read_timeout_seconds"] = 60.0
    assert read.http.read_timeout_seconds == 60.0
    assert read.model_dump() == expected


def test_tc40_an_empty_environment_gives_the_defaults_of_each_group(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RP_HTTP__READ_TIMEOUT_SECONDS", "60")  # the process holds a value ...

    assert (
        settings_from_env(ToolkitSettings, environ={}) == ToolkitSettings()
    )  # ... the mapping wins


def test_tc40_a_prefix_other_than_the_default_is_honoured() -> None:
    read = settings_from_env(
        ToolkitSettings,
        prefix="APP_",
        environ={"APP_HTTP__READ_TIMEOUT_SECONDS": "9", "RP_HTTP__READ_TIMEOUT_SECONDS": "60"},
    )

    assert read.http.read_timeout_seconds == 9.0


def test_tc40_a_list_value_is_read_as_json() -> None:
    read = settings_from_env(ToolkitSettings, environ={"RP_JWKS__ALLOWED_ALGORITHMS": '["RS256"]'})

    assert read.jwks.allowed_algorithms == ["RS256"]


def test_tc40_the_process_environment_is_read_when_no_mapping_is_given(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RP_HTTP__CONNECT_TIMEOUT_SECONDS", "11")

    assert settings_from_env(ToolkitSettings).http.connect_timeout_seconds == 11.0


def test_tc41_a_value_the_model_refuses_is_a_validation_error_naming_the_field() -> None:
    with pytest.raises(ValidationError, match="allowed_algorithms"):
        settings_from_env(ToolkitSettings, environ={"RP_JWKS__ALLOWED_ALGORITHMS": '["HS256"]'})


def test_tc41_a_value_below_its_bound_is_a_validation_error() -> None:
    with pytest.raises(ValidationError, match="read_timeout_seconds"):
        settings_from_env(ToolkitSettings, environ={"RP_HTTP__READ_TIMEOUT_SECONDS": "-1"})


def test_tc42_importing_the_package_reads_no_variable_and_loads_no_settings_library() -> None:
    probe = (
        "import sys, rdf_persistence;"
        "assert 'pydantic_settings' not in sys.modules, 'pydantic_settings loaded';"
        "assert 'rdf_persistence.api.entrypoints' not in sys.modules, 'entrypoints loaded'"
    )
    done = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        env={"PATH": "/usr/bin", "RP_HTTP__READ_TIMEOUT_SECONDS": "abc"},
    )

    assert done.returncode == 0, done.stderr


def test_tc43_without_the_settings_extra_the_error_names_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(sys.modules, "pydantic_settings", None)  # X5

    with pytest.raises(ImportError, match=r"rdf-persistence\[settings\]"):
        settings_from_env(ToolkitSettings, environ={})


def test_tc44_any_generated_settings_model_is_built_from_its_required_fields() -> None:
    read = settings_from_env(
        ServiceSettings,
        environ={
            "RP_BASE": "https://example.org/",
            "RP_PREFIX": "demo",
            "RP_TENANT_SEGMENT": "tenants",
            "RP_CREATOR_ROLE": "owner",
            "RP_ROLES_CLAIM": "roles",
        },
    )

    assert isinstance(read, ServiceSettings)
    assert read.prefix == "demo"
    assert read.max_body_bytes == 1048576


def test_tc44_a_missing_required_field_is_a_validation_error_naming_it() -> None:
    with pytest.raises(ValidationError, match="prefix"):
        settings_from_env(
            ServiceSettings,
            environ={"RP_BASE": "https://example.org/", "RP_TENANT_SEGMENT": "t"},
        )


@pytest.mark.parametrize(
    "name",
    [
        "settings_from_env",
        "ToolkitSettings",
        "HttpSettings",
        "JwksSettings",
        "DirectorySettings",
        "EventSettings",
        "SseSettings",
        "LimitSettings",
    ],
)
def test_the_function_and_the_groups_are_exported_from_the_top_level(name: str) -> None:
    assert name in rdf_persistence.__all__
    assert getattr(rdf_persistence, name) is not None


class _Credentials(BaseModel):
    token: SecretStr = SecretStr("x" * 20)
    port: int = 1


class _ConsumerSettings(BaseModel):
    api_key: SecretStr = Field(default=SecretStr("k" * 20), min_length=20)
    credentials: _Credentials = Field(default_factory=_Credentials)


@pytest.mark.parametrize("variable", ["RP_API_KEY", "RP_CREDENTIALS__PORT"])
def test_a_malformed_value_is_refused_without_echoing_it(variable: str) -> None:
    """D-55 3: neither the reading class nor the final model puts the input in the error."""
    secret = "hunter2-do-not-leak"
    with pytest.raises(ValidationError) as caught:
        settings_from_env(_ConsumerSettings, environ={variable: secret})
    assert secret not in str(caught.value), "the error text echoed the input"
