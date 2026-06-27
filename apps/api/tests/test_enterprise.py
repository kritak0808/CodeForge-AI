import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_api_keys_workflow(client: AsyncClient):
    # 1. Register and login
    reg_payload = {
        "username": "keyuser",
        "email": "keyuser@codeforge.ai",
        "password": "securepassword123",
        "role": "developer"
    }
    await client.post("/api/v1/auth/register", json=reg_payload)

    login_payload = {
        "username": "keyuser",
        "password": "securepassword123"
    }
    auth_resp = await client.post("/api/v1/auth/login", json=login_payload)
    token = auth_resp.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Create API key
    key_payload = {
        "name": "Production Key",
        "expires_at": None
    }
    create_resp = await client.post("/api/v1/api-keys", json=key_payload, headers=headers)
    assert create_resp.status_code == 201
    key_data = create_resp.json()
    assert key_data["success"] is True
    assert key_data["data"]["name"] == "Production Key"
    assert "plain_key" in key_data["data"]
    assert "api_key_id" in key_data["data"]
    key_id = key_data["data"]["api_key_id"]

    # 3. List API keys
    list_resp = await client.get("/api/v1/api-keys", headers=headers)
    assert list_resp.status_code == 200
    list_data = list_resp.json()
    assert len(list_data["data"]) == 1
    assert list_data["data"][0]["name"] == "Production Key"

    # 4. Revoke API key
    revoke_resp = await client.delete(f"/api/v1/api-keys/{key_id}", headers=headers)
    assert revoke_resp.status_code == 200

    # 5. List again, should be empty
    list_resp = await client.get("/api/v1/api-keys", headers=headers)
    assert len(list_resp.json()["data"]) == 0

@pytest.mark.asyncio
async def test_audit_logs(client: AsyncClient):
    # 1. Register and login admin
    reg_payload = {
        "username": "adminuser",
        "email": "admin@codeforge.ai",
        "password": "securepassword123",
        "role": "admin"
    }
    await client.post("/api/v1/auth/register", json=reg_payload)

    login_payload = {
        "username": "adminuser",
        "password": "securepassword123"
    }
    auth_resp = await client.post("/api/v1/auth/login", json=login_payload)
    token = auth_resp.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Generate an audit event (by creating an api key)
    key_payload = {
        "name": "Audit Key"
    }
    await client.post("/api/v1/api-keys", json=key_payload, headers=headers)

    # 3. List audit events
    audit_resp = await client.get("/api/v1/audit-events", headers=headers)
    assert audit_resp.status_code == 200
    audit_data = audit_resp.json()
    assert len(audit_data["data"]) >= 1
    assert audit_data["data"][0]["action"] == "CREATE_API_KEY"

@pytest.mark.asyncio
async def test_feature_flags(client: AsyncClient):
    # 1. Register & Login Admin
    reg_payload = {
        "username": "flagadmin",
        "email": "flagadmin@codeforge.ai",
        "password": "securepassword123",
        "role": "admin"
    }
    await client.post("/api/v1/auth/register", json=reg_payload)

    login_payload = {
        "username": "flagadmin",
        "password": "securepassword123"
    }
    auth_resp = await client.post("/api/v1/auth/login", json=login_payload)
    token = auth_resp.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Create feature flag
    flag_payload = {
        "name": "beta-access",
        "description": "Beta platform access",
        "is_enabled": True,
        "conditions": {"roles": ["admin"]}
    }
    create_resp = await client.post("/api/v1/feature-flags", json=flag_payload, headers=headers)
    assert create_resp.status_code == 201

    # 3. Check flag active
    check_resp = await client.get("/api/v1/feature-flags/beta-access/active", headers=headers)
    assert check_resp.status_code == 200
    assert check_resp.json()["data"]["is_active"] is True
