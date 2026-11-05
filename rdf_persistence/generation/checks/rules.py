"""The unsupported-rules check (PD-24): only exactly_one_of, any_of and unique_keys are enforced.

LinkML's ``rules`` (pre- and postconditions), ``all_of`` and ``none_of`` would be silently ignored
by the generated classes and shapes, so a schema declaring them on a class fails instead.
"""

from linkml_runtime.utils.schemaview import SchemaView

UNSUPPORTED = ("rules", "all_of", "none_of")


def rules_problems(view: SchemaView) -> list[str]:
    """One line for each class of the schema's closure that declares an unsupported rule."""
    return [
        f"{cls.name}: `{rule}` is not supported; use exactly_one_of, any_of or unique_keys"
        for cls in view.all_classes().values()
        for rule in UNSUPPORTED
        if getattr(cls, rule)
    ]
