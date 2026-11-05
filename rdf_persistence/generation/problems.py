"""Check problems: how a rule's finding is built, and the one place it becomes a line of text."""

from rdf_persistence.generation.generated.rp_generation import (
    BoundaryRule,
    CheckProblem,
    HardRule,
)


def rule_problem(rule: HardRule | BoundaryRule, element: str, message: str) -> CheckProblem:
    """A finding of the hard or boundary check: the rule it breaks, the element and what is wrong."""
    return CheckProblem(rule=rule.value, element=element, message=message)


def format_problem(problem: CheckProblem) -> str:
    """``<schema>: <step>: [<rule>] <element>: <message>``, each part only when the problem has it."""
    parts = (
        f"{problem.schema_file}: " if problem.schema_file else "",
        f"{problem.step}: " if problem.step else "",
        f"[{problem.rule}] " if problem.rule else "",
        f"{problem.element}: " if problem.element else "",
        problem.message,
    )
    return "".join(parts)
