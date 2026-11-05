"""RpModel, the strict base of every metamodel class and of every consumer's generated class."""

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
