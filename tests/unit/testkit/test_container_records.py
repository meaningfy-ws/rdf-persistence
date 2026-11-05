"""The endpoint records of the test containers are generated, and their secrets stay out of repr."""

import pytest

from rdf_persistence.generation.generated.rp_generation import (
    ExecResult,
    FusekiServer,
    GarageServer,
    ZitadelServer,
)

SECRET = "s3cr3t-value"


@pytest.mark.parametrize(
    "record",
    [
        FusekiServer(url="http://h", user="u", password=SECRET),
        GarageServer(endpoint="http://h", key_id="k", secret=SECRET, region="r"),
        ZitadelServer(url="http://h", admin_pat=SECRET),
    ],
    ids=lambda r: type(r).__name__,
)
def test_a_secret_field_does_not_appear_in_repr_or_str(record: object) -> None:
    assert SECRET not in repr(record), "a secret leaked into repr"
    assert SECRET not in str(record), "a secret leaked into str"


def test_the_public_fields_of_a_record_do_appear_in_repr() -> None:
    assert "http://h" in repr(ZitadelServer(url="http://h", admin_pat=SECRET))


def test_a_command_result_keeps_its_output_and_exit_code() -> None:
    result = ExecResult(stdout="o", stderr="e", exit_code=3)
    assert (result.stdout, result.stderr, result.exit_code) == ("o", "e", 3)
