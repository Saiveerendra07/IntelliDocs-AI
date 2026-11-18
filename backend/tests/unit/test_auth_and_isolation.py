import pytest
from httpx import AsyncClient, ASGITransport
from backend.app.main import app
from backend.app.core.security import create_access_token


@pytest.mark.asyncio
async def test_auth_registration_and_login_validation():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Invalid short password
        short_pw_res = await client.post("/api/v1/auth/register", json={
            "email": "student_invalid@univ.edu",
            "password": "short",
            "full_name": "Test Student",
        })
        assert short_pw_res.status_code == 422

        # Invalid email format
        bad_email_res = await client.post("/api/v1/auth/register", json={
            "email": "not-an-email",
            "password": "ValidPassword123!",
            "full_name": "Test Student",
        })
        assert bad_email_res.status_code == 422

        # Valid registration
        reg_res = await client.post("/api/v1/auth/register", json={
            "email": "alice@univ.edu",
            "password": "SecurePassword123!",
            "full_name": "Alice Smith",
        })
        assert reg_res.status_code == 201
        data = reg_res.json()
        assert "access_token" in data
        assert data["user"]["email"] == "alice@univ.edu"

        # Login with bad password
        bad_login = await client.post("/api/v1/auth/login", json={
            "email": "alice@univ.edu",
            "password": "WrongPassword123!",
        })
        assert bad_login.status_code == 401
        assert "error" in bad_login.json() or "detail" in bad_login.json()

        # Login with correct password
        good_login = await client.post("/api/v1/auth/login", json={
            "email": "alice@univ.edu",
            "password": "SecurePassword123!",
        })
        assert good_login.status_code == 200
        assert "access_token" in good_login.json()


@pytest.mark.asyncio
async def test_token_tampering_and_profile_access():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Tampered / malformed token should fail with 401
        tampered_headers = {"Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.tampered.token"}
        res = await client.get("/api/v1/users/me", headers=tampered_headers)
        assert res.status_code == 401

        # 2. Register user to test profile update and password change
        reg_res = await client.post("/api/v1/auth/register", json={
            "email": "bob@univ.edu",
            "password": "OriginalPassword123!",
            "full_name": "Bob Jones",
        })
        token = reg_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Update profile
        update_res = await client.patch("/api/v1/users/me", headers=headers, json={
            "full_name": "Robert Jones",
            "theme": "dark",
            "preferences": {"default_provider": "local"},
        })
        assert update_res.status_code == 200
        assert update_res.json()["full_name"] == "Robert Jones"
        assert update_res.json()["theme"] == "dark"

        # Change password
        pwd_res = await client.post("/api/v1/users/me/password", headers=headers, json={
            "current_password": "OriginalPassword123!",
            "new_password": "NewSecurePassword456!",
        })
        assert pwd_res.status_code == 200

        # Login with new password
        login_res = await client.post("/api/v1/auth/login", json={
            "email": "bob@univ.edu",
            "password": "NewSecurePassword456!",
        })
        assert login_res.status_code == 200


@pytest.mark.asyncio
async def test_multi_user_access_control_and_data_isolation():
    """
    CRITICAL SECURITY INVARIANT:
    User A cannot read, query, delete or search User B's documents, chats, quizzes, flashcards or vectors.
    Returns 404 (not 403) for other users' resources to prevent resource enumeration.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Create User A (Student A)
        res_a = await client.post("/api/v1/auth/register", json={
            "email": "user_a@univ.edu",
            "password": "PasswordA123!",
            "full_name": "User Alpha",
        })
        token_a = res_a.json()["access_token"]
        headers_a = {"Authorization": f"Bearer {token_a}"}

        # 2. Create User B (Student B)
        res_b = await client.post("/api/v1/auth/register", json={
            "email": "user_b@univ.edu",
            "password": "PasswordB123!",
            "full_name": "User Beta",
        })
        token_b = res_b.json()["access_token"]
        headers_b = {"Authorization": f"Bearer {token_b}"}

        # 3. User A uploads a private document
        upload_res = await client.post(
            "/api/v1/documents/upload",
            headers=headers_a,
            files={"file": ("alpha_private.pdf", b"%PDF-1.4 Private confidential notes for Alpha.", "application/pdf")},
        )
        assert upload_res.status_code == 201
        doc_a_id = upload_res.json()["id"]

        # 4. User B cannot see User A's document in document listing
        list_b = await client.get("/api/v1/documents", headers=headers_b)
        assert list_b.status_code == 200
        b_doc_ids = [d["id"] for d in list_b.json()["items"]]
        assert doc_a_id not in b_doc_ids

        # 5. User B querying User A's document ID returns 404 (NOT 403)
        get_b = await client.get(f"/api/v1/documents/{doc_a_id}", headers=headers_b)
        assert get_b.status_code == 404
        assert "not found" in get_b.json()["error"]["message"].lower() or "not found" in str(get_b.json()).lower()

        # 6. User B cannot access User A's pages
        pages_b = await client.get(f"/api/v1/documents/{doc_a_id}/pages", headers=headers_b)
        assert pages_b.status_code == 404

        # 7. User B cannot access User A's NLP preprocessing
        nlp_b = await client.get(f"/api/v1/documents/{doc_a_id}/nlp/preprocessing", headers=headers_b)
        assert nlp_b.status_code == 404

        # 8. User B cannot download User A's document
        dl_b = await client.get(f"/api/v1/documents/{doc_a_id}/download", headers=headers_b)
        assert dl_b.status_code == 404

        # 9. User B cannot delete User A's document
        del_b = await client.delete(f"/api/v1/documents/{doc_a_id}", headers=headers_b)
        assert del_b.status_code == 404

        # 10. User A can still access their own document
        get_a = await client.get(f"/api/v1/documents/{doc_a_id}", headers=headers_a)
        assert get_a.status_code == 200
        assert get_a.json()["id"] == doc_a_id
