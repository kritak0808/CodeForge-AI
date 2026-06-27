import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_register_user(client: AsyncClient):
    payload = {
        "username": "testdev",
        "email": "testdev@codeforge.ai",
        "password": "securepassword123",
        "role": "developer"
    }
    response = await client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["success"] is True
    assert data["data"]["username"] == "testdev"
    assert data["data"]["email"] == "testdev@codeforge.ai"
    assert data["data"]["role"] == "developer"
    assert "user_id" in data["data"]

@pytest.mark.asyncio
async def test_login_user(client: AsyncClient):
    # 1. Register user
    reg_payload = {
        "username": "loginuser",
        "email": "loginuser@codeforge.ai",
        "password": "securepassword123",
        "role": "developer"
    }
    await client.post("/api/v1/auth/register", json=reg_payload)

    # 2. Login
    login_payload = {
        "username": "loginuser",
        "password": "securepassword123"
    }
    response = await client.post("/api/v1/auth/login", json=login_payload)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "access_token" in data["data"]
    assert "refresh_token" in data["data"]
    assert data["data"]["token_type"] == "bearer"

@pytest.mark.asyncio
async def test_login_invalid_password(client: AsyncClient):
    reg_payload = {
        "username": "wrongpass",
        "email": "wrongpass@codeforge.ai",
        "password": "correctpassword",
        "role": "developer"
    }
    await client.post("/api/v1/auth/register", json=reg_payload)

    login_payload = {
        "username": "wrongpass",
        "password": "incorrectpassword"
    }
    response = await client.post("/api/v1/auth/login", json=login_payload)
    assert response.status_code == 401
    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "AUTH_FAILED"

@pytest.mark.asyncio
async def test_access_protected_projects_route_without_token(client: AsyncClient):
    response = await client.get("/api/v1/projects/")
    assert response.status_code == 401
    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "AUTH_FAILED"
    assert data["error"]["message"] == "Not authenticated"

@pytest.mark.asyncio
async def test_create_and_list_projects(client: AsyncClient):
    # 1. Register user
    reg_payload = {
        "username": "projectowner",
        "email": "projectowner@codeforge.ai",
        "password": "securepassword123",
        "role": "developer"
    }
    await client.post("/api/v1/auth/register", json=reg_payload)

    # 2. Login
    login_payload = {
        "username": "projectowner",
        "password": "securepassword123"
    }
    auth_resp = await client.post("/api/v1/auth/login", json=login_payload)
    token = auth_resp.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 3. Create Project
    project_payload = {
        "name": "Food Delivery App",
        "description": "Scalable platform",
        "tech_stack": {"backend": "FastAPI", "frontend": "Next.js"},
        "repository_url": "https://github.com/codeforge/food-delivery",
        "budget_usd_limit": 100.00
    }
    create_resp = await client.post("/api/v1/projects/", json=project_payload, headers=headers)
    assert create_resp.status_code == 201
    proj_data = create_resp.json()
    assert proj_data["success"] is True
    assert proj_data["data"]["name"] == "Food Delivery App"
    assert proj_data["data"]["budget_usd_limit"] == "100.00"

    # 4. List Projects
    list_resp = await client.get("/api/v1/projects/", headers=headers)
    assert list_resp.status_code == 200
    list_data = list_resp.json()
    assert list_data["success"] is True
    assert len(list_data["data"]) == 1
    assert list_data["data"][0]["name"] == "Food Delivery App"
