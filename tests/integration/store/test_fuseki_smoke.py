"""Fuseki starts, admits the test user, and answers."""

import httpx


def test_fuseki_answers_ping(fuseki) -> None:
    response = httpx.get(f"{fuseki.url}/$/ping", auth=fuseki.auth)
    assert response.status_code == 200


def test_fuseki_rejects_anonymous_callers(fuseki) -> None:
    assert httpx.get(f"{fuseki.url}/$/ping").status_code == 401


def test_fuseki_admin_creates_and_drops_a_dataset(fuseki) -> None:
    created = httpx.post(
        f"{fuseki.url}/$/datasets",
        data={"dbName": "smoke", "dbType": "tdb2"},
        auth=fuseki.auth,
    )
    assert created.status_code == 200
    dropped = httpx.delete(f"{fuseki.url}/$/datasets/smoke", auth=fuseki.auth)
    assert dropped.status_code == 200
