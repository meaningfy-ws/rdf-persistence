"""The toy's test vocabulary: ``book_json()`` hands every caller a body of its own (PD-17)."""

from tests.toy import book_json


def test_book_json_is_new_on_each_call() -> None:
    first, second = book_json(), book_json()

    assert first == second, "each call builds the same book"
    assert first is not second, "each call builds a new dict"
    assert first["chapters"] is not second["chapters"], "the nested list is new too"

    first["chapters"].append({"number": 2})

    assert len(book_json()["chapters"]) == 1, (
        "a change to one call's list does not reach the next call"
    )
