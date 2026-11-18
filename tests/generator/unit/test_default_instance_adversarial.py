"""Adversarial tests of the ``default_instance`` generation check (technical-models stage 3, task 3.1, PD-6).

Attacks: the error-matrix row '``default_instance`` on a class with a required slot without default',
by the two ways the range can hold one that the plain case does not show.
"""

from pathlib import Path

import pytest

from rdf_persistence_generation.generated.rp_generation import HardRule

from .test_hard_check import DEFAULT_INSTANCE_SCHEMA, problems_of

SCHEMA = DEFAULT_INSTANCE_SCHEMA.format(name_required="false", name_default="")
RULE = f"[{HardRule.DEFAULT_INSTANCE.value}]"
INHERITED = SCHEMA.replace(
    "  Group:\n    title: Group\n",
    "  Base:\n    title: Base\n    description: A base.\n    slots: [ident]\n"
    "    slot_usage:\n      ident: {required: true}\n"
    "  Group:\n    is_a: Base\n    title: Group\n",
).replace("slots:\n  size:", "slots:\n  ident:\n    title: Ident\n    description: An id.\n  size:")
IDENTIFIED = SCHEMA.replace("      name: {required: false}", "      name: {identifier: true}")


@pytest.mark.parametrize(
    ("text", "slot"),
    [(INHERITED, "ident"), (IDENTIFIED, "name")],
    ids=["required-slot-from-a-parent", "identifier-slot"],
)
def test_a_range_whose_required_slot_cannot_default_is_refused_naming_both(
    tmp_path: Path, text: str, slot: str
) -> None:
    """Error matrix: the range's required slot comes from a parent, or is an identifier: no default instance."""
    root = tmp_path / "groups.yaml"
    root.write_text(text, encoding="utf-8")
    found = [p for p in problems_of(root) if RULE in p and "] group:" in p]
    assert len(found) == 1, f"the slot `group` is the one to name: {found}"
    assert slot in found[0], f"the unbuildable slot is not named in {found[0]}"
