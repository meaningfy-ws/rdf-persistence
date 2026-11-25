"""``Iris.aggregate_id_of``: the id an aggregate IRI ends in, for the address of a referrer (E12)."""

import pytest

from rdf_persistence.iris.services.iris import DEFAULT_IRIS
from tests.toy import TENANT, book_iri

OTHER_TENANT = "https://example.org/libraries/0a0a0a0a"
MINTED = DEFAULT_IRIS.mint_aggregate(TENANT, cls_type="", rp_path="books")

CASES = [
    pytest.param(MINTED, MINTED.rsplit("/", 1)[1], id="a-policy-minted-aggregate"),
    pytest.param(book_iri(7), book_iri(7).rsplit("/", 1)[1], id="a-toy-aggregate"),
    pytest.param(
        f"{OTHER_TENANT}/books/{book_iri(7).rsplit('/', 1)[1]}",
        book_iri(7).rsplit("/", 1)[1],
        id="another-tenants-aggregate-no-tenant-check",
    ),
    pytest.param(TENANT, None, id="a-tenant-root"),
    pytest.param("https://elsewhere.org/books/42", None, id="a-foreign-iri"),
    pytest.param("not an iri", None, id="not-an-iri"),
]


@pytest.mark.parametrize(("iri", "expected"), CASES)
def test_aggregate_id_of_is_the_minted_id_or_none(iri, expected):  # E12
    assert DEFAULT_IRIS.aggregate_id_of(iri) == expected, f"the id of {iri}"
