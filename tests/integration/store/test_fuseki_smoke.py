"""Fuseki starts, admits the test user, and answers."""

import uuid

import httpx


def test_fuseki_answers_ping(fuseki) -> None:
    response = httpx.get(f"{fuseki.url}/$/ping", auth=(fuseki.user, fuseki.password))
    assert response.status_code == 200, "an authenticated ping is answered"


def test_fuseki_rejects_anonymous_callers(fuseki) -> None:
    assert httpx.get(f"{fuseki.url}/$/ping").status_code == 401, "an anonymous ping is refused"


def test_fuseki_admin_creates_and_drops_a_dataset(fuseki) -> None:
    name = f"smoke-{uuid.uuid4().hex[:8]}"  # namespaced: the server is the session's (rule 13)
    auth = (fuseki.user, fuseki.password)
    created = httpx.post(
        f"{fuseki.url}/$/datasets", data={"dbName": name, "dbType": "tdb2"}, auth=auth
    )
    try:
        assert created.status_code == 200, "the admin creates a dataset"
    finally:
        dropped = httpx.delete(f"{fuseki.url}/$/datasets/{name}", auth=auth)
    assert dropped.status_code == 200, "the admin drops it"
