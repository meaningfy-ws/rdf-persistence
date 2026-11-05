"""Zitadel starts, writes the admin token, and answers an authenticated management call."""

import httpx


def test_zitadel_answers_an_authenticated_management_call(zitadel) -> None:
    response = httpx.get(
        f"{zitadel.url}/management/v1/orgs/me",
        headers={"Authorization": f"Bearer {zitadel.admin_pat}"},
    )
    assert response.status_code == 200
    assert response.json()["org"]["id"]
