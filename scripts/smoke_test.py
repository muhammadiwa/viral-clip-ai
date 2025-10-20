"""Minimal end-to-end smoke test for the Viral Clip AI API."""

from __future__ import annotations

import asyncio
import os
from uuid import uuid4

from fastapi.testclient import TestClient

from apps.api.app.main import create_app
from apps.api.app.db import get_sessionmaker, init_db
from apps.api.app.domain.organizations import OrganizationCreate
from apps.api.app.domain.projects import ProjectCreate
from apps.api.app.domain.users import UserCreate
from apps.api.app.repositories.organizations import SqlAlchemyOrganizationsRepository
from apps.api.app.repositories.users import SqlAlchemyUsersRepository


async def _bootstrap_data() -> tuple[str, str]:
    """Ensure the database has a user + organization for smoke testing."""

    await init_db()
    session_factory = get_sessionmaker()
    async with session_factory() as session:
        user_repo = SqlAlchemyUsersRepository(session)
        try:
            user = await user_repo.create(
                UserCreate(email="smoke@example.com", password="smoke-secret", full_name="Smoke Tester")
            )
        except ValueError:
            # User already exists; reuse the existing account for this smoke test.
            user = await user_repo.get_by_email("smoke@example.com")
            if user is None:
                raise

    async with session_factory() as session:
        org_repo = SqlAlchemyOrganizationsRepository(session)
        try:
            organization, _membership = await org_repo.create(
                OrganizationCreate(name="Smoke Test Org", slug="smoke-test-org"),
                owner_user_id=user.id,
            )
        except ValueError:
            existing = await org_repo.list()
            organization = next((org for org in existing if org.slug == "smoke-test-org"), None)
            if organization is None:
                raise

    return str(user.id), str(organization.id)


async def _run_async_smoke() -> None:
    user_id, org_id = await _bootstrap_data()

    app = create_app()
    client = TestClient(app)

    token_response = client.post(
        "/v1/auth/token",
        json={"email": "smoke@example.com", "password": "smoke-secret"},
    )
    token_response.raise_for_status()
    token_payload = token_response.json()
    access_token = token_payload["access_token"]

    headers = {
        "Authorization": f"Bearer {access_token}",
        "X-Org-ID": org_id,
        "Idempotency-Key": str(uuid4()),
    }
    project_payload = ProjectCreate(name="Smoke Project").model_dump()
    create_project_response = client.post(
        "/v1/projects",
        json=project_payload,
        headers=headers,
    )
    create_project_response.raise_for_status()

    list_response = client.get(
        "/v1/projects",
        headers={"Authorization": f"Bearer {access_token}", "X-Org-ID": org_id},
    )
    list_response.raise_for_status()
    projects = list_response.json()["data"]
    assert any(project["name"] == "Smoke Project" for project in projects)

    print("Smoke test passed: created user", user_id, "project count", len(projects))


def main() -> None:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise SystemExit("DATABASE_URL must be set for the smoke test")
    asyncio.run(_run_async_smoke())


if __name__ == "__main__":
    main()
