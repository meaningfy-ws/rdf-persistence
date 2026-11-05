"""Text from a schema never breaks out of the string it is rendered into (stage 1 review, injection)."""

import importlib
import inspect
import json
import sys
from collections.abc import Iterator
from types import ModuleType

import pytest
from pydantic import ValidationError

from rdf_persistence.generation.extensions.pydantic_split import render as render_modules

PACKAGE = "rp_hostile_generated"
TITLE = "Say \"hi\" \\ {x} 'q'"
TEXT = 'Close """ and \\ and {braces} {{x}} \'q\' and "dq"\nand a new line'
TITLE_YAML, TEXT_YAML = json.dumps(TITLE), json.dumps(TEXT)  # JSON strings are YAML strings
SCHEMA = f"""
id: https://example.org/ns/hostile
name: hostile
title: Hostile
description: Text that would break out of the code around it.
prefixes: {{h: "https://example.org/ns/h#", linkml: "https://w3id.org/linkml/"}}
default_prefix: h
default_range: string
imports: [linkml:types]
classes:
  Hostile:
    title: {TITLE_YAML}
    description: {TEXT_YAML}
    slots: [mail, phone, shade]
    exactly_one_of:
      - slot_conditions: {{mail: {{name: mail, required: true}}}}
      - slot_conditions: {{phone: {{name: phone, value_presence: PRESENT}}}}
  Entry:
    title: Entry
    description: An entry.
    slots: [mail, phone]
    unique_keys:
      entry_key:
        description: {TEXT_YAML}
        unique_key_slots: [mail]
  Ledger:
    title: Ledger
    description: Entries.
    slots: [entries]
slots:
  mail: {{title: {TITLE_YAML}, description: {TEXT_YAML}, range: string}}
  phone: {{title: Phone, description: The phone number., range: string}}
  shade: {{title: Shade, description: A quoted shade., range: string, pattern: '^"q"$'}}
  entries:
    title: Entries
    description: The entries.
    range: Entry
    multivalued: true
    inlined_as_list: true
enums:
  Colour:
    title: Colour
    description: {TEXT_YAML}
    permissible_values:
      'a"b': {{description: {TEXT_YAML}}}
"""


@pytest.fixture(scope="module")
def models(tmp_path_factory: pytest.TempPathFactory) -> Iterator[ModuleType]:
    root = tmp_path_factory.mktemp("hostile")
    (root / "hostile.yaml").write_text(SCHEMA, encoding="utf-8")
    folder = root / PACKAGE
    folder.mkdir()
    for module in render_modules(root / "hostile.yaml"):
        compile(module.text, module.name, "exec")  # a module that is not Python fails here
        (folder / module.name).write_text(module.text, encoding="utf-8")
    sys.path.insert(0, str(root))
    yield importlib.import_module(f"{PACKAGE}.hostile")
    sys.path.remove(str(root))
    for name in [m for m in sys.modules if m.split(".")[0] == PACKAGE]:
        del sys.modules[name]


def test_a_description_with_quotes_is_the_docstring_as_written(models: ModuleType) -> None:
    assert inspect.cleandoc(models.Hostile.__doc__) == TEXT, "the class docstring changed"


def test_a_title_and_a_description_with_quotes_reach_the_field_as_written(
    models: ModuleType,
) -> None:
    field = models.Hostile.model_fields["mail"]
    assert (field.title, field.description) == (TITLE, TEXT), "the field metadata changed"


def test_an_enum_value_with_a_quote_is_the_value_as_written(models: ModuleType) -> None:
    assert [m.value for m in models.Colour] == ['a"b'], "the enum value changed"


@pytest.mark.parametrize(("value", "accepted"), [('"q"', True), ("q", False), ('"q"\n', False)])
def test_a_pattern_with_quotes_is_checked_as_written(
    models: ModuleType, value: str, accepted: bool
) -> None:
    if accepted:
        assert models.Hostile(mail="m", shade=value), "the pattern refused a match"
        return
    with pytest.raises(ValidationError, match="Invalid shade format"):
        models.Hostile(mail="m", shade=value)


def test_a_rule_message_is_built_without_the_schemas_text_in_an_f_string(
    models: ModuleType,
) -> None:
    with pytest.raises(ValidationError, match="exactly_one_of needs exactly one of"):
        models.Hostile()


def test_a_unique_key_message_names_the_key(models: ModuleType) -> None:
    entry = models.Entry(mail="m")
    with pytest.raises(ValidationError, match="Ledger.entries: unique_keys entry_key"):
        models.Ledger(entries=[entry, entry])
