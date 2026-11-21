"""Every error of the toolkit is a PersistenceError; the ones caused by a caller's input are also ValueErrors."""

import inspect

import pytest

from rdf_persistence.core.domain import exceptions
from rdf_persistence.core.domain.exceptions import PersistenceError

ERRORS = [
    cls
    for _, cls in inspect.getmembers(exceptions, inspect.isclass)
    if cls.__module__ == exceptions.__name__
]
INPUT_ERRORS = [
    exceptions.InvalidRoleDefinition,
    exceptions.InvalidWorkflow,
    exceptions.InvalidMigration,
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
    assert exceptions.Conflict("lost").iris == (), (
        "a conflict with no roots named carries an empty tuple of IRIs"
    )
    assert str(exceptions.Conflict("lost")) == "lost", (
        "a conflict's text is the message it was raised with"
    )
    named = exceptions.Conflict("lost", iris=("urn:a", "urn:b"))
    assert named.iris == ("urn:a", "urn:b"), "a conflict carries the roots it was given"
    assert str(named) == "lost", "naming roots does not change the conflict's text"


def test_in_use_keeps_the_roots_referrers_and_counts_it_was_given():
    referrers = (("urn:b1", "Book", "written_by"), ("urn:b2", "Book", "written_by"))
    error = exceptions.InUse(
        "in use",
        iris=("urn:a1",),
        referrers=referrers,
        more_count=1,
        hidden_count=2,
    )
    assert error.iris == ("urn:a1",), "the refused roots are kept as a tuple"
    assert error.referrers == referrers, "the (referrer, class, slot) triples are kept as given"
    assert (error.more_count, error.hidden_count) == (1, 2), "both counts are kept"
    assert str(error) == "in use", "the text is the message it was raised with"
    assert isinstance(error, exceptions.Conflict), "a Conflict subclass, as KeyConflict is"


def test_in_use_sorts_the_roots_and_the_referrers_it_was_given_unsorted():
    error = exceptions.InUse(
        "in use",
        iris=("urn:a2", "urn:a1"),
        referrers=(("urn:b2", "Book", "written_by"), ("urn:b1", "Book", "written_by")),
    )
    assert error.iris == ("urn:a1", "urn:a2"), "the refused roots are sorted"
    assert error.referrers == (
        ("urn:b1", "Book", "written_by"),
        ("urn:b2", "Book", "written_by"),
    ), "the referrers are sorted"


def test_in_use_with_nothing_named_defaults_to_empty_and_zero():
    error = exceptions.InUse("in use", iris=["urn:a1"], referrers=[("urn:b", "Book", "s")])
    assert error.referrers == (("urn:b", "Book", "s"),), "referrers become a tuple"
    assert exceptions.InUse("in use").referrers == (), "no referrers by default"
    bare = exceptions.InUse("in use")
    assert (bare.iris, bare.more_count, bare.hidden_count) == ((), 0, 0), "defaults are empty/0"


def test_in_use_is_unfiltered_unless_told_otherwise_and_keeps_what_it_was_told():  # D-10
    assert exceptions.InUse("in use").filtered is False, "no readable callable judged it by default"
    assert exceptions.InUse("in use", filtered=True).filtered is True, "the flag is kept"


def test_a_key_conflict_keeps_the_roots_and_the_keys_it_was_given_as_tuples():
    error = exceptions.KeyConflict("clash", iris=["urn:a"], keys=["isbn", "slug"])
    assert error.iris == ("urn:a",), "the roots whose claim clashed are kept as a tuple"
    assert error.keys == ("isbn", "slug"), "the key names are kept as a tuple"
    assert str(error) == "clash", "the text is the message it was raised with"
    assert isinstance(error, exceptions.Conflict), "a Conflict subclass"


def test_a_key_conflict_with_nothing_named_defaults_to_empty():
    error = exceptions.KeyConflict("clash")
    assert (error.iris, error.keys) == ((), ()), "no roots and no keys by default"


def test_a_failed_migration_keeps_the_schema_the_migration_and_the_cause_apart():
    error = exceptions.MigrationFailed("failed", schema="urn:s", migration="m1", cause="timeout")
    assert (error.schema, error.migration, error.cause) == ("urn:s", "m1", "timeout")
    assert str(error) == "failed", "the text is the message it was raised with"


def test_a_failed_migration_with_nothing_named_holds_empty_strings():
    error = exceptions.MigrationFailed("failed")
    assert (error.schema, error.migration, error.cause) == ("", "", ""), "each defaults to empty"


def test_a_message_limit_error_keeps_the_limit_and_names_the_message_that_went_over():
    error = exceptions.MessageLimitExceeded(5, "Create#7")
    assert (error.limit, error.command) == (5, "Create#7"), "both are kept"
    assert "5" in str(error), "the text names the limit"
    assert str(error).endswith("by Create#7"), "the text ends by naming the message"


def test_a_message_limit_error_without_a_command_names_none():
    error = exceptions.MessageLimitExceeded(5)
    assert (error.limit, error.command) == (5, None), "no command by default"
    assert "5" in str(error), "the text names the limit"
    assert "by" not in str(error), "no message is named"
