"""The manual's validator example runs as shown (``user-manual/access.adoc`` ``[#validators]``, PD-7,
R2-5).

The test reads the guide's own listing, so the guide and the test cannot drift.
"""

import re
from pathlib import Path
from typing import Any

import pytest

from rdf_persistence import Grant, GrantSet, InvalidBody, Principal

GUIDE = (
    Path(__file__).parents[3]
    / "docs"
    / "modules"
    / "ROOT"
    / "pages"
    / "user-manual"
    / "access.adoc"
)
LISTING = re.compile(r"\[source,python\]\n----\n(.*?)\n----", re.DOTALL)
TENANT = "https://example.org/libraries/6f1c0c1e"
WHO = Principal(id="https://example.org/people/ada")


def _example() -> str:
    # the section is the `==` heading after the anchor, up to the next `==` heading
    section = GUIDE.read_text(encoding="utf-8").split("[#validators]", 1)[1].split("\n== ", 2)[1]
    (listing,) = LISTING.findall(section)
    return listing


def _keep_a_librarian() -> Any:
    rule, _ = _example().split("\n\ninstall_service(", 1)
    namespace: dict[str, Any] = {}
    exec(compile(rule, str(GUIDE), "exec"), namespace)
    return namespace["keep_a_librarian"]


def _librarians(*names: str) -> GrantSet:
    return GrantSet(
        grants=[
            Grant(assignee=f"https://example.org/people/{n}", target=TENANT, role="librarian")
            for n in names
        ]
    )


def test_the_guides_rule_passes_a_grant_set_that_keeps_a_librarian() -> None:
    kept = _keep_a_librarian()(_librarians("ada", "bob"), _librarians("ada"), WHO)
    assert kept is None, "a librarian is kept"


def test_the_guides_rule_refuses_a_grant_set_without_a_librarian() -> None:
    with pytest.raises(InvalidBody, match="at least one librarian"):
        _keep_a_librarian()(_librarians("ada"), GrantSet(), WHO)


def test_the_guides_install_call_passes_the_validators_by_keyword() -> None:
    call = _example().split("\n\ninstall_service(", 1)[1]
    assert "grant_validators=[keep_a_librarian]" in call, "the validators are a keyword argument"
    assert call.lstrip().startswith("app,\n"), "app is the only positional argument"
