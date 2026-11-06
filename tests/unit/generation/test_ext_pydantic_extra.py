"""A class annotated ``allows_extra: 'true'`` keeps the fields it does not declare; every other class refuses them (PD-24, PD-28a)."""

import importlib
import sys
from collections.abc import Iterator
from types import ModuleType

import pytest
from pydantic import ValidationError

from rdf_persistence.generation.extensions.pydantic_split import render as render_modules

SCHEMA = """
id: https://example.org/ns/answers
name: answers
title: Answers
description: A request we build and an answer a foreign API sends.
prefixes: {v: "https://example.org/ns/v#", linkml: "https://w3id.org/linkml/"}
default_prefix: v
default_range: string
imports: [linkml:types]
classes:
  Request:
    title: Request
    description: What we send.
    slots: [name]
  Answer:
    title: Answer
    description: What the foreign API answers; it says more than we read.
    slots: [name]
    annotations:
      allows_extra: 'true'
slots:
  name: {title: Name, description: The name., range: string}
"""

PACKAGE = "rp_extra_generated"


@pytest.fixture(scope="module")
def models(tmp_path_factory: pytest.TempPathFactory) -> Iterator[ModuleType]:
    root = tmp_path_factory.mktemp("extra")
    (root / "answers.yaml").write_text(SCHEMA, encoding="utf-8")
    folder = root / PACKAGE
    folder.mkdir()
    for module in render_modules(root / "answers.yaml"):
        (folder / module.name).write_text(module.text, encoding="utf-8")
    sys.path.insert(0, str(root))
    yield importlib.import_module(f"{PACKAGE}.answers")
    sys.path.remove(str(root))
    for name in [m for m in sys.modules if m.split(".")[0] == PACKAGE]:
        del sys.modules[name]


def test_an_annotated_class_keeps_an_undeclared_field(models: ModuleType) -> None:
    answer = models.Answer.model_validate_json('{"name": "n", "details": {"x": 1}}')
    assert answer.name == "n"
    assert answer.model_extra == {"details": {"x": 1}}, "the unread field is kept, not lost"


def test_a_class_without_the_annotation_refuses_an_undeclared_field(models: ModuleType) -> None:
    with pytest.raises(ValidationError, match="details"):
        models.Request.model_validate_json('{"name": "n", "details": 1}')
