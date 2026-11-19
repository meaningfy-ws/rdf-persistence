"""The shared scratch import-linter helper reads a broken contract however its name wraps (D-25, 8.1)."""

import pytest

from tests.unit.import_contracts import broken_in, run_contracts, scratch_config

KEYS = ("domain-pure", "services-of-a-theme-import-no-adapters-or-entrypoints")


def test_a_broken_contract_is_found_by_its_key():
    report = "domain-pure BROKEN\nservices-of-a-theme-import-no-adapters-or-entrypoints KEPT\n"

    assert broken_in(report, KEYS) == ["domain-pure"]


@pytest.mark.parametrize(
    "report",
    [
        "services-of-a-theme-import-no-adapters-or-\nentrypoints BROKEN\n",
        "services-of-a-theme-import-no-adapters-\n  or-entrypoints\n  BROKEN\n",
        "services-of-a-theme-import-no-adapters-or-entrypoints\nBROKEN\n",
    ],
)
def test_a_name_wrapped_over_lines_is_still_found(report):
    assert broken_in(report, KEYS) == [KEYS[1]]


def test_a_contract_that_is_kept_or_not_asked_for_is_not_reported():
    report = "domain-pure KEPT\nsome-other-contract BROKEN\n"

    assert broken_in(report, KEYS) == []


def test_the_scratch_config_names_each_contract_by_its_key():
    config = scratch_config(KEYS)

    assert [config[f"importlinter:contract:{key}"]["name"] for key in KEYS] == list(KEYS)


def test_a_contract_gone_from_the_source_is_named():
    with pytest.raises(AssertionError, match="no-such-contract is gone"):
        scratch_config(("no-such-contract",))


def test_a_planted_import_breaks_the_contract_and_the_control_keeps_it(tmp_path):
    layout = {
        "__init__.py": "",
        "core/__init__.py": "",
        "core/domain/__init__.py": "",
        "core/services/__init__.py": "",
        "core/domain/x.py": "",
    }
    control = run_contracts(tmp_path / "control", layout, ("domain-pure",))
    planted = run_contracts(
        tmp_path / "planted", {**layout, "core/domain/x.py": "import httpx\n"}, ("domain-pure",)
    )

    assert control == (0, []), "the layout alone keeps the contract"
    assert planted[0] != 0, "a domain importing httpx is not kept"
    assert planted[1] == ["domain-pure"], "and the helper names it"
