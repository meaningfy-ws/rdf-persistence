"""Every error of the toolkit is a PersistenceError; the ones caused by a caller's input are also ValueErrors."""

import inspect

import pytest

from rdf_persistence.domain import exceptions
from rdf_persistence.domain.exceptions import PersistenceError

ERRORS = [
    cls
    for _, cls in inspect.getmembers(exceptions, inspect.isclass)
    if cls.__module__ == exceptions.__name__
]
INPUT_ERRORS = [
    exceptions.InvalidRoleDefinition,
    exceptions.InvalidWorkflow,
    exceptions.UnknownRole,
    exceptions.InvalidGrant,
    exceptions.InvalidIri,
    exceptions.SparqlError,
]


@pytest.mark.parametrize("error", ERRORS, ids=lambda cls: cls.__name__)
def test_every_error_of_the_module_derives_persistence_error(error):
    assert issubclass(error, PersistenceError), f"{error.__name__} escapes the base"


@pytest.mark.parametrize("error", INPUT_ERRORS, ids=lambda cls: cls.__name__)
def test_an_error_caused_by_the_callers_input_is_also_a_value_error(error):
    assert issubclass(error, ValueError), f"{error.__name__} is not a ValueError"


def test_a_conflict_names_the_roots_that_conflict_and_defaults_to_none():
    assert exceptions.Conflict("lost").iris == ()
    assert str(exceptions.Conflict("lost")) == "lost"
    named = exceptions.Conflict("lost", iris=("urn:a", "urn:b"))
    assert named.iris == ("urn:a", "urn:b")
    assert str(named) == "lost"
