"""``CheckProblem.replaced``, the pipeline's rewrite of a problem (generator-package D-13)."""

from rdf_persistence_generation.generated.rp_generation import CheckProblem


def test_a_check_problem_replaced_keeps_what_it_does_not_name() -> None:
    """Tries the pipeline's rewrite of a problem: rule, element and message stay; a prior step is overwritten."""
    problem = CheckProblem(rule="r", element="e", message="m", step="old", schema_file="a.yaml")
    changed = problem.replaced(schema_file="sub/b.yaml", step="new")
    assert (changed.rule, changed.element, changed.message) == ("r", "e", "m"), (
        "unnamed fields were lost"
    )
    assert (changed.schema_file, changed.step) == ("sub/b.yaml", "new"), (
        "named fields were not replaced"
    )
    assert problem.step == "old", "the original problem was changed"
