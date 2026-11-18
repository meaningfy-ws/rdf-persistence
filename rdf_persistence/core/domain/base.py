"""RpModel, the strict base of every metamodel class and of every consumer's generated class."""

from typing import Self

from pydantic import BaseModel, ConfigDict


class RpModel(BaseModel):
    """A pydantic model that refuses unknown fields and validates every assignment.

    The settings other than ``extra`` and ``validate_assignment`` are those gen-pydantic's own base
    sets, so generated classes keep their usual behaviour: ``validate_by_name`` and
    ``serialize_by_alias`` for aliased slots, ``validate_default`` so a default is checked too, and
    ``use_enum_values`` so enum slots hold plain strings that serialise as they are.
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
        validate_by_name=True,
        serialize_by_alias=True,
        validate_default=True,
        use_enum_values=True,
    )

    def replaced(self, **changes: object) -> Self:
        """A new model of the same class with ``changes`` applied; ``self`` is untouched.

        The fields that were set are carried over and merged with ``changes`` into one mapping, which
        the class validates like any construction: a value of the wrong type or a misspelt name is a
        ``ValidationError``, where ``model_copy(update=...)`` accepts both without a check.
        """
        kept = {name: getattr(self, name) for name in self.model_fields_set}
        return type(self)(**(kept | changes))
