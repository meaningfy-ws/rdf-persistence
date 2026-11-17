"""Read a generated settings model from environment variables (PD-12, DEC-6).

The composition root calls ``settings_from_env`` once; the toolkit never reads the environment on
its own, so importing it is free of side effects. ``pydantic_settings`` is the optional extra
``rdf-persistence[settings]`` and is imported only when the function runs.
"""

import os
from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, create_model

NESTED_DELIMITER = "__"
MISSING_EXTRA = "settings_from_env needs pydantic-settings; install the extra: pip install 'rdf-persistence[settings]'"


def settings_from_env[M: BaseModel](
    model: type[M], *, prefix: str = "RP_", environ: Mapping[str, str] | None = None
) -> M:
    """Build ``model`` from the variables ``<prefix><SLOT>`` and ``<prefix><GROUP>__<SLOT>``.

    A value that is not set keeps the model's default, a group's ``default_factory`` included. A list
    is given as JSON. ``environ`` defaults to ``os.environ``, read when this is called. The values are
    validated once, by ``model``; an invalid one raises its ``ValidationError``, and nothing is built.
    """
    try:
        from pydantic_settings import (
            BaseSettings,
            EnvSettingsSource,
            PydanticBaseSettingsSource,
            SettingsConfigDict,
        )
    except ImportError as error:
        raise ImportError(MISSING_EXTRA) from error

    variables = _lower_cased(environ)

    class _GivenEnvironment(EnvSettingsSource):
        def _load_env_vars(self) -> Mapping[str, str | None]:
            return variables

    class _Read(BaseSettings):
        model_config = SettingsConfigDict(env_prefix=prefix, env_nested_delimiter=NESTED_DELIMITER)

        @classmethod
        def settings_customise_sources(
            cls,
            settings_cls: type[BaseSettings],
            init_settings: PydanticBaseSettingsSource,
            env_settings: PydanticBaseSettingsSource,
            dotenv_settings: PydanticBaseSettingsSource,
            file_secret_settings: PydanticBaseSettingsSource,
        ) -> tuple[PydanticBaseSettingsSource, ...]:
            return (_GivenEnvironment(settings_cls),)  # no dotenv file, no secrets directory

    read_class = create_model(
        f"{model.__name__}FromEnvironment", __base__=_Read, **_field_definitions(model)
    )
    return model.model_validate(read_class().model_dump())


def _lower_cased(environ: Mapping[str, str] | None) -> dict[str, str]:
    """The variables, named in lower case as the settings source looks them up."""
    # The one place the toolkit reads the process environment, and only when the consumer asks.
    given = os.environ if environ is None else environ  # noqa: TID251
    return {name.lower(): value for name, value in given.items()}


def _field_definitions(model: type[BaseModel]) -> dict[str, Any]:
    """The fields of ``model`` as ``create_model`` takes them: the field info keeps its default factory."""
    return {name: (info.annotation or Any, info) for name, info in model.model_fields.items()}
