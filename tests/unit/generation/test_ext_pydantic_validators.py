"""Golden test and behaviour of the model validators gen-pydantic is extended with (PD-24, PD-25).

``exactly_one_of`` and ``any_of`` become a validator on the class that declares them, ``unique_keys`` one on
every class with a multivalued slot whose range declares the key; ``rules`` is refused.
"""

import importlib
import sys
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType

import pytest
from pydantic import ValidationError

from rdf_persistence.generation.cli import main
from rdf_persistence.generation.extensions.pydantic_split import render_modules

from .conftest import Breaker
from .golden import assert_matches_golden

PREFIXES = """
prefixes: {v: "https://example.org/ns/v#", linkml: "https://w3id.org/linkml/"}
default_prefix: v
default_range: string
imports: [linkml:types]
"""

SCHEMA = (
    """
id: https://example.org/ns/validators
name: validators
title: Validators
description: Classes that declare each rule the validators enforce.
"""
    + PREFIXES
    + """
classes:
  Contact:
    title: Contact
    description: A contact reachable by exactly one of mail and phone.
    slots: [mail, phone]
    exactly_one_of:
      - slot_conditions: {mail: {name: mail, required: true}}
      - slot_conditions: {phone: {name: phone, value_presence: PRESENT}}
  Customer:
    title: Customer
    description: A contact that is also a customer.
    is_a: Contact
    slots: [account]
  Reach:
    title: Reach
    description: A way to reach somebody by at least one of mail and phone.
    slots: [mail, phone]
    any_of:
      - slot_conditions: {mail: {name: mail, value_presence: PRESENT}}
      - slot_conditions: {phone: {name: phone, value_presence: PRESENT}}
  Entry:
    title: Entry
    description: A ledger entry, one per name and tag.
    slots: [name, tag]
    unique_keys:
      entry_key:
        description: One entry per name and tag.
        unique_key_slots: [name, tag]
  Ledger:
    title: Ledger
    description: Entries and the people who care about them.
    slots: [entries, watchers]
  Archive:
    title: Archive
    description: A ledger that is kept.
    is_a: Ledger

slots:
  mail: {title: Mail, description: The mail address., range: string}
  phone: {title: Phone, description: The phone number., range: string}
  account: {title: Account, description: The account number., range: string}
  name: {title: Name, description: The name of the entry., range: string}
  tag: {title: Tag, description: The tag of the entry., range: string}
  entries:
    title: Entries
    description: The entries.
    range: Entry
    multivalued: true
    inlined_as_list: true
  watchers:
    title: Watchers
    description: The names of those who watch.
    range: string
    multivalued: true
"""
)

PACKAGE = "rp_validators_generated"


@pytest.fixture(scope="module")
def generated(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Path]:
    """The validators schema generated once into a folder importable as ``rp_validators_generated``."""
    root = tmp_path_factory.mktemp("validators")
    (root / "validators.yaml").write_text(SCHEMA, encoding="utf-8")
    folder = root / PACKAGE
    folder.mkdir()
    for module in render_modules(root / "validators.yaml"):
        (folder / module.name).write_text(module.text, encoding="utf-8")
    sys.path.insert(0, str(root))
    yield folder
    sys.path.remove(str(root))
    for name in [m for m in sys.modules if m.split(".")[0] == PACKAGE]:
        del sys.modules[name]


@pytest.fixture(scope="module")
def models(generated: Path) -> ModuleType:
    return importlib.import_module(f"{PACKAGE}.validators")


def test_the_generated_validators_match_the_golden_files(generated: Path) -> None:
    assert_matches_golden("pydantic_validators", generated)


@pytest.mark.parametrize(
    ("fields", "accepted"),
    [
        ({"mail": "a@example.org"}, True),
        ({"phone": "123"}, True),
        ({"mail": "a@example.org", "phone": "123"}, False),
        ({}, False),
    ],
    ids=["mail only", "phone only", "both", "neither"],
)
@pytest.mark.parametrize(("name", "declaring"), [("Contact", "Contact"), ("Customer", "Contact")])
def test_exactly_one_of_accepts_one_alternative_and_refuses_the_rest(
    models: ModuleType, name: str, declaring: str, fields: dict[str, str], accepted: bool
) -> None:
    """A subclass inherits the rule, so its message names the class that declares it."""
    cls = getattr(models, name)
    if accepted:
        assert cls(**fields), "one alternative must be accepted"
        return
    with pytest.raises(ValidationError, match=rf"{declaring}.*exactly_one_of.*mail"):
        cls(**fields)


def test_a_subclass_inherits_the_exactly_one_of_rule(models: ModuleType) -> None:
    with pytest.raises(ValidationError, match="exactly_one_of"):
        models.Customer(account="a-1")


@pytest.mark.parametrize(
    ("fields", "accepted"),
    [
        ({"mail": "a@example.org"}, True),
        ({"phone": "123"}, True),
        ({"mail": "a@example.org", "phone": "123"}, True),
        ({}, False),
    ],
    ids=["mail only", "phone only", "both", "neither"],
)
def test_any_of_accepts_one_alternative_or_more_and_refuses_none(
    models: ModuleType, fields: dict[str, str], accepted: bool
) -> None:
    if accepted:
        assert models.Reach(**fields), "at least one alternative must be accepted"
        return
    with pytest.raises(ValidationError, match=r"Reach.*any_of.*mail"):
        models.Reach(**fields)


def entry(models: ModuleType, name: str = "n", tag: str | None = None) -> object:
    return models.Entry(name=name, tag=tag)


@pytest.mark.parametrize("name", ["Ledger", "Archive"])
def test_unique_keys_refuse_two_entries_with_equal_keys(models: ModuleType, name: str) -> None:
    ledger = getattr(models, name)
    with pytest.raises(ValidationError, match=r"Ledger.entries.*entry_key.*name.*tag"):
        ledger(entries=[entry(models, tag="t"), entry(models, tag="t")])


def test_two_absent_key_values_are_equal(models: ModuleType) -> None:
    with pytest.raises(ValidationError, match="entry_key"):
        models.Ledger(entries=[entry(models), entry(models)])


def test_an_absent_value_differs_from_a_present_one(models: ModuleType) -> None:
    ledger = models.Ledger(entries=[entry(models), entry(models, tag="t")])
    assert len(ledger.entries) == 2, "an absent tag and a present one are different keys"


def test_the_message_names_the_repeated_key(models: ModuleType) -> None:
    with pytest.raises(ValidationError, match="'dup'"):
        models.Ledger(entries=[entry(models, name="dup"), entry(models, name="dup")])


def test_a_ledger_without_entries_is_accepted(models: ModuleType) -> None:
    assert models.Ledger().entries is None, "an absent list has no duplicates"


def test_the_class_that_only_inherits_the_slot_does_not_repeat_the_validator(
    generated: Path,
) -> None:
    text = (generated / "validators.py").read_text(encoding="utf-8")
    assert text.count("def unique_keys_") == 1, (
        "Archive must inherit Ledger's validator, not repeat it"
    )


def render(tmp_path: Path, schema: str) -> list[str]:
    (tmp_path / "bad.yaml").write_text(schema, encoding="utf-8")
    return [module.name for module in render_modules(tmp_path / "bad.yaml")]


def bad_schema(rule: str) -> str:
    return (
        SCHEMA.split("classes:")[0]
        + f"""
classes:
  Broken:
    title: Broken
    description: A class whose rule uses a form the validators do not support.
    slots: [mail, phone]
{rule}
slots:
  mail: {{title: Mail, description: The mail address., range: string}}
  phone: {{title: Phone, description: The phone number., range: string}}
"""
    )


UNSUPPORTED = [
    (
        "    any_of:\n      - slot_conditions: {mail: {name: mail}}\n"
        "      - slot_conditions: {phone: {name: phone, required: true}}\n",
        r"Broken.*any_of.*mail.*exactly one of required",
    ),
    (
        "    exactly_one_of:\n      - slot_conditions: {mail: {name: mail, pattern: x}}\n"
        "      - slot_conditions: {phone: {name: phone, required: true}}\n",
        r"Broken.*exactly_one_of.*mail.*pattern",
    ),
    (
        "    any_of:\n      - slot_conditions: {mail: {name: mail, required: false}}\n"
        "      - slot_conditions: {phone: {name: phone, required: true}}\n",
        r"Broken.*any_of.*mail.*required",
    ),
    (
        "    exactly_one_of:\n      - is_a: Broken\n      - slot_conditions: {phone: {name: phone, required: true}}\n",
        r"Broken.*exactly_one_of.*is_a",
    ),
    (
        "    any_of:\n      - slot_conditions: {nowhere: {name: nowhere, required: true}}\n"
        "      - slot_conditions: {phone: {name: phone, required: true}}\n",
        r"Broken.*any_of.*nowhere",
    ),
]


@pytest.mark.parametrize(("rule", "message"), UNSUPPORTED)
def test_a_condition_the_validators_cannot_express_is_a_generation_error(
    tmp_path: Path, rule: str, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        render(tmp_path, bad_schema(rule))


RULES = """    rules:
      - preconditions:
          slot_conditions: {text: {required: true}}
        postconditions:
          slot_conditions: {text: {required: true}}
"""


ALL_OF = """    all_of:
      - slot_conditions: {text: {required: true}}
"""
NONE_OF = """    none_of:
      - slot_conditions: {text: {required: true}}
"""


@pytest.mark.parametrize("check", [[], ["--check"]], ids=["generate", "check"])
@pytest.mark.parametrize(
    ("rule", "snippet"), [("rules", RULES), ("all_of", ALL_OF), ("none_of", NONE_OF)]
)
def test_a_schema_using_an_unsupported_rule_makes_rp_generate_exit_1_naming_the_class(
    break_toy: Breaker,
    capsys: pytest.CaptureFixture[str],
    check: list[str],
    rule: str,
    snippet: str,
) -> None:
    root = break_toy(
        "books.yaml", "    class_uri: lib:Note\n", "    class_uri: lib:Note\n" + snippet
    )
    code = main(["--project", str(root.parent / "pyproject.toml"), *check])
    assert code == 1, f"a schema using {rule} must fail"
    error = capsys.readouterr().err
    assert "Note" in error, f"the problem must name the class: {error}"
    assert f"`{rule}`" in error, f"the problem must name the rule: {error}"
    assert not (root.parent / "generated").exists(), "nothing may be written when a check fails"


def test_a_unique_key_over_a_slot_the_items_lack_is_a_generation_error(tmp_path: Path) -> None:
    schema = SCHEMA.replace("unique_key_slots: [name, tag]", "unique_key_slots: [name, nothing]")
    with pytest.raises(ValueError, match=r"Ledger.*entry_key.*nothing"):
        render(tmp_path, schema)
