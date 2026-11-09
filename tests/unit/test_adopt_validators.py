"""The guide's validator example runs as shown (``howto/adopt.adoc`` ``[#validators]``, PD-7, R2-5).

The test reads the guide's own listing, so the guide and the test cannot drift.
"""

import re
from pathlib import Path
from typing import Any

import pytest

from rdf_persistence import Grant, GrantSet, InvalidBody, Principal

GUIDE = Path(__file__).parents[2] / "docs" / "modules" / "ROOT" / "pages" / "howto" / "adopt.adoc"
LISTING = re.compile(r"\[source,python\]\n----\n(.*?)\n----", re.DOTALL)
TENANT = "https://example.org/projects/p1"
WHO = Principal(id="https://example.org/people/ada")


def _example() -> str:
    section = GUIDE.read_text(encoding="utf-8").split("[#validators]", 1)[1].split("\n== ", 1)[0]
    (listing,) = LISTING.findall(section)
    return listing


def _keep_an_owner() -> Any:
    rule, _ = _example().split("\n\ninstall_service(", 1)
    namespace: dict[str, Any] = {}
    exec(compile(rule, str(GUIDE), "exec"), namespace)
    return namespace["keep_an_owner"]


def _owners(*names: str) -> GrantSet:
    return GrantSet(
        grants=[
            Grant(assignee=f"https://example.org/people/{n}", target=TENANT, role="owner")
            for n in names
        ]
    )


def test_the_guides_rule_passes_a_grant_set_that_keeps_an_owner() -> None:
    assert _keep_an_owner()(_owners("ada", "bob"), _owners("ada"), WHO) is None, "an owner is kept"


def test_the_guides_rule_refuses_a_grant_set_without_an_owner() -> None:
    with pytest.raises(InvalidBody, match="at least one owner"):
        _keep_an_owner()(_owners("ada"), GrantSet(), WHO)


def test_the_guides_install_call_passes_the_validators_by_keyword() -> None:
    call = _example().split("\n\ninstall_service(", 1)[1]
    assert "grant_validators=[keep_an_owner]" in call, "the validators are a keyword argument"
    assert call.lstrip().startswith("app,\n"), "app is the only positional argument"
