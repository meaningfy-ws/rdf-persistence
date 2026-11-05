"""RpModel is the strict base of every metamodel class and of every consumer's generated class."""

import pytest
from pydantic import ValidationError

from rdf_persistence import Principal, RpModel, TenantAccess
from rdf_persistence.domain.generated import rp as generated
from tests.unit.domain.builders import ALICE, tenant_access

METAMODEL_CLASSES = sorted(
    (
        value
        for value in vars(generated).values()
        if isinstance(value, type) and issubclass(value, RpModel) and value is not RpModel
    ),
    key=lambda cls: cls.__name__,
)


class Plain(RpModel):
    """A consumer-style model: it declares one field and nothing else."""

    name: str


def test_every_generated_class_inherits_rp_model() -> None:
    assert METAMODEL_CLASSES, "no metamodel class was generated"
    for cls in METAMODEL_CLASSES:
        assert issubclass(cls, RpModel), f"{cls.__name__} does not inherit RpModel"


@pytest.mark.parametrize("cls", METAMODEL_CLASSES, ids=lambda cls: cls.__name__)
def test_metamodel_class_refuses_extra_fields_by_config(cls: type[RpModel]) -> None:
    assert cls.model_config.get("extra") == "forbid", f"{cls.__name__} allows extra fields"
    assert cls.model_config.get("validate_assignment") is True, (
        f"{cls.__name__} skips validation on assignment"
    )


def test_unknown_field_is_refused() -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        Plain(name="x", surprise=1)  # type: ignore[call-arg]


def test_invalid_assignment_is_refused() -> None:
    model = Plain(name="x")
    with pytest.raises(ValidationError):
        model.name = 3  # type: ignore[assignment]


def test_refused_assignment_leaves_the_value_unchanged() -> None:
    model = Plain(name="x")
    with pytest.raises(ValidationError):
        model.name = 3  # type: ignore[assignment]
    assert model.name == "x", "a refused assignment must not change the model"


def test_metamodel_class_refuses_an_unknown_field() -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        Principal(id=ALICE, nickname="al")  # type: ignore[call-arg]


def test_metamodel_class_refuses_an_invalid_assignment() -> None:
    access = tenant_access()
    with pytest.raises(ValidationError):
        access.state = "archived"  # type: ignore[assignment]


def test_missing_required_field_is_refused() -> None:
    with pytest.raises(ValidationError, match="database_name"):
        TenantAccess(id=ALICE, label="Acme", state="active")  # type: ignore[call-arg]
