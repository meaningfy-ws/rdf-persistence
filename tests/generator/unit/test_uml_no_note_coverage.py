"""``no-note`` covers neither a role object nor a state nor a transition (task 1.8, how-to).

The model's classes carry a note (``klass`` default), the role object, the states and the
transitions carry none: a ``no-note`` line would then name one of them. The how-to says none does.
"""

from tests.generator.uml_model import run

from .uml_role_rows import READER, _given
from .uml_role_rows import _uml as roles_uml
from .uml_workflow_rows import OVERRIDES, _loan


def test_a_role_object_with_no_note_gets_no_no_note_line() -> None:
    out = run(roles_uml(_given(*READER)))
    assert out.problems == [], out.problem_texts()
    assert out.report_lines("no_note") == [], "a role object needs no note"


def test_a_state_and_a_transition_with_no_note_get_no_no_note_line() -> None:
    out = run(_loan(), **OVERRIDES)
    assert out.problems == [], out.problem_texts()
    assert out.report_lines("no_note") == [], "a state, a transition and the diagram need no note"
