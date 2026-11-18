"""``load_cases`` of the conformance suite: paths and absent lists (generator-package D-13)."""

from pathlib import Path

import pytest
import yaml

from rdf_persistence_generation.testkit.conformance import load_cases


def test_load_cases_resolves_paths_and_leaves_absent_lists_empty(tmp_path: Path) -> None:
    """Tries a row with no valid/invalid, one with an absolute path, and a refused extra key."""
    cases = tmp_path / "cases.yaml"
    cases.write_text(
        yaml.safe_dump(
            [
                {"kind": "pattern", "class_name": "A"},
                {
                    "kind": "pattern",
                    "class_name": "B",
                    "valid": ["/abs/x.json"],
                    "invalid": ["y.json"],
                },
            ]
        )
    )
    first, second = load_cases(cases)
    assert first.valid == [], "an absent list is empty"
    assert first.invalid == [], "an absent list is empty"
    assert second.valid == ["/abs/x.json"], "an absolute path stays absolute"
    assert second.invalid == [str(tmp_path / "y.json")], (
        "a relative path is resolved beside the file"
    )
    cases.write_text(yaml.safe_dump([{"kind": "pattern", "class_name": "A", "bogus": 1}]))
    with pytest.raises(Exception, match="bogus"):
        load_cases(cases)


def test_load_cases_of_an_empty_file_is_empty(tmp_path: Path) -> None:
    """Tries an empty YAML file."""
    empty = tmp_path / "cases.yaml"
    empty.write_text("")
    assert load_cases(empty) == [], "an empty file has no cases"
