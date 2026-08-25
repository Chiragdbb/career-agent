"""Tenant isolation: user A must not access user B's owned resources."""

from __future__ import annotations

import pytest


@pytest.mark.parametrize(
    ("path_template", "id_key"),
    [
        ("/api/v1/jobs/{id}", "job"),
        ("/api/v1/applications/{id}", "application"),
        ("/api/v1/resumes/{id}", "resume"),
        ("/api/v1/contacts/{id}", "contact"),
        ("/api/v1/outreach/{id}", "outreach"),
    ],
)
def test_user_a_cannot_access_user_b_resources(
    auth_client, user_b_resources, path_template: str, id_key: str
) -> None:
    resource_id = user_b_resources[id_key]
    response = auth_client.get(
        path_template.format(id=resource_id),
        headers={"Authorization": "Bearer token-user-a"},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_user_b_can_access_own_resources(auth_client, user_b_resources) -> None:
    for path_template, id_key in [
        ("/api/v1/jobs/{id}", "job"),
        ("/api/v1/applications/{id}", "application"),
        ("/api/v1/resumes/{id}", "resume"),
        ("/api/v1/contacts/{id}", "contact"),
        ("/api/v1/outreach/{id}", "outreach"),
    ]:
        response = auth_client.get(
            path_template.format(id=user_b_resources[id_key]),
            headers={"Authorization": "Bearer token-user-b"},
        )
        assert response.status_code == 200, (id_key, response.json())
        assert response.json()["id"] == str(user_b_resources[id_key])


def test_lists_are_tenant_scoped(auth_client, user_b_resources) -> None:
    b_ids = {
        str(user_b_resources["job"]),
        str(user_b_resources["application"]),
        str(user_b_resources["resume"]),
        str(user_b_resources["contact"]),
        str(user_b_resources["outreach"]),
    }
    for path in (
        "/api/v1/jobs",
        "/api/v1/applications",
        "/api/v1/resumes",
        "/api/v1/contacts",
        "/api/v1/outreach",
    ):
        response = auth_client.get(
            path,
            headers={"Authorization": "Bearer token-user-a"},
        )
        assert response.status_code == 200
        ids = {item["id"] for item in response.json()}
        assert ids.isdisjoint(b_ids)
