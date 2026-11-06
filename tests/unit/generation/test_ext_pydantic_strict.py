"""A slot annotated ``strict: 'true'`` takes exactly its type: no string becomes a number, no bool becomes a number (PD-24, PD-28a)."""

import importlib
import sys
from collections.abc import Iterator
from types import ModuleType

import pytest
from pydantic import ValidationError

from rdf_persistence.generation.extensions.pydantic_split import render as render_modules

SCHEMA = """
id: https://example.org/ns/claims
name: claims
title: Claims
description: Claims whose types are not coerced.
prefixes: {v: "https://example.org/ns/v#", linkml: "https://w3id.org/linkml/"}
default_prefix: v
default_range: string
imports: [linkml:types]
classes:
  Claims:
    title: Claims
    description: Strict and lax slots side by side.
    slots: [expires, loose_expires, subject]
    slot_usage:
      expires: {required: true}
slots:
  expires:
    title: Expires
    description: A number.
    range: float
    annotations:
      strict: 'true'
  loose_expires:
    title: Loose expires
    description: A number, coerced.
    range: float
  subject:
    title: Subject
    description: A string.
    annotations:
      strict: 'true'
"""

PACKAGE = "rp_strict_generated"


@pytest.fixture(scope="module")
def models(tmp_path_factory: pytest.TempPathFactory) -> Iterator[ModuleType]:
    root = tmp_path_factory.mktemp("strict")
    (root / "claims.yaml").write_text(SCHEMA, encoding="utf-8")
    folder = root / PACKAGE
    folder.mkdir()
    for module in render_modules(root / "claims.yaml"):
        (folder / module.name).write_text(module.text, encoding="utf-8")
    sys.path.insert(0, str(root))
    yield importlib.import_module(f"{PACKAGE}.claims")
    sys.path.remove(str(root))
    for name in [m for m in sys.modules if m.split(".")[0] == PACKAGE]:
        del sys.modules[name]


@pytest.mark.parametrize("value", ["123", True, False, None], ids=repr)
def test_a_strict_number_refuses_what_is_not_a_number(models: ModuleType, value: object) -> None:
    with pytest.raises(ValidationError, match="expires"):
        models.Claims(expires=value)


@pytest.mark.parametrize("value", [1, 1.5])
def test_a_strict_number_takes_integers_and_floats(models: ModuleType, value: float) -> None:
    assert models.Claims(expires=value).expires == value


def test_a_slot_without_the_annotation_still_coerces(models: ModuleType) -> None:
    assert models.Claims(expires=1, loose_expires="2").loose_expires == 2.0


def test_a_strict_string_refuses_a_number(models: ModuleType) -> None:
    with pytest.raises(ValidationError, match="subject"):
        models.Claims(expires=1, subject=5)
