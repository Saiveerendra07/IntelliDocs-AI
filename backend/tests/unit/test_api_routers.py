import pytest
from httpx import AsyncClient, ASGITransport
from backend.app.main import app


def test_openapi_schema_generation():
    schema = app.openapi()
    assert schema["info"]["title"] == "IntelliDocs AI"
    assert "/api/v1/auth/register" in schema["paths"]
    assert "/api/v1/auth/login" in schema["paths"]
    assert "/api/v1/documents" in schema["paths"]
    assert "/api/v1/nlp/preprocess" in schema["paths"]
    assert "/api/v1/documents/{id}/nlp/preprocessing" in schema["paths"]
    assert "/api/v1/documents/{id}/summaries/generate" in schema["paths"]
    assert "/api/v1/chat/conversations" in schema["paths"]
    assert "/api/v1/questions/generate" in schema["paths"]
    assert "/api/v1/quizzes" in schema["paths"]
    assert "/api/v1/flashcards" in schema["paths"]
    assert "/api/v1/analytics/overview" in schema["paths"]
    assert "/api/v1/system/models" in schema["paths"]


@pytest.mark.asyncio
async def test_full_api_routers_flow():
    import uuid
    uid = uuid.uuid4().hex[:8]
    test_email = f"sarah_{uid}@university.edu"
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Register a new user
        reg_res = await client.post("/api/v1/auth/register", json={
            "email": test_email,
            "password": "StrongPassword123!",
            "full_name": "Sarah Connor",
        })
        assert reg_res.status_code == 201
        reg_data = reg_res.json()
        token = reg_data["access_token"]
        auth_headers = {"Authorization": f"Bearer {token}"}

        # 2. Duplicate registration should return 400
        dup_res = await client.post("/api/v1/auth/register", json={
            "email": test_email,
            "password": "StrongPassword123!",
            "full_name": "Sarah Connor",
        })
        assert dup_res.status_code == 400

        # 3. Test Login
        login_res = await client.post("/api/v1/auth/login", json={
            "email": test_email,
            "password": "StrongPassword123!",
        })
        assert login_res.status_code == 200
        assert "access_token" in login_res.json()

        # 4. Protected profile route (401 without auth)
        unauth_res = await client.get("/api/v1/users/me")
        assert unauth_res.status_code == 401

        # Profile with auth
        profile_res = await client.get("/api/v1/users/me", headers=auth_headers)
        assert profile_res.status_code == 200
        assert profile_res.json()["email"] == test_email

        # 5. Adhoc Preprocess NLP
        nlp_res = await client.post("/api/v1/nlp/preprocess", json={
            "text": "Intelligent Document Analysis and NLP-Based Exam Preparation Platform."
        })
        assert nlp_res.status_code == 200
        nlp_data = nlp_res.json()
        assert "tokens" in nlp_data
        assert nlp_data["stats"]["total_tokens"] > 0

        # 6. Upload a test document
        upload_res = await client.post(
            "/api/v1/documents/upload",
            headers=auth_headers,
            files={"file": ("lecture_sample.txt", b"Operating Systems: Virtual memory, paging, and deadlocks.", "text/plain")},
        )
        assert upload_res.status_code == 201
        doc_data = upload_res.json()
        doc_id = doc_data["id"]

        # 7. List documents
        docs_list_res = await client.get("/api/v1/documents", headers=auth_headers)
        assert docs_list_res.status_code == 200
        assert docs_list_res.json()["total"] >= 1

        # 8. Document NLP Analysis
        doc_nlp_res = await client.get(f"/api/v1/documents/{doc_id}/nlp/preprocessing", headers=auth_headers)
        assert doc_nlp_res.status_code == 200

        doc_pos_res = await client.get(f"/api/v1/documents/{doc_id}/nlp/pos", headers=auth_headers)
        assert doc_pos_res.status_code == 200

        # 9. Generate Summaries
        summ_res = await client.post(f"/api/v1/documents/{doc_id}/summaries/generate", headers=auth_headers, json={
            "method": "textrank",
            "length": "medium",
            "mode": "standard",
        })
        assert summ_res.status_code == 200
        assert "content" in summ_res.json()

        # Compare summaries
        comp_res = await client.get(f"/api/v1/documents/{doc_id}/summaries/compare", headers=auth_headers)
        assert comp_res.status_code == 200
        assert "rouge" in comp_res.json()

        # 10. Generate Questions & Quiz
        qgen_res = await client.post("/api/v1/questions/generate", headers=auth_headers, json={
            "document_id": doc_id,
            "type": "mcq",
            "difficulty": "medium",
            "count": 3,
        })
        assert qgen_res.status_code == 200
        questions = qgen_res.json()
        assert len(questions) == 3

        # Create Quiz
        quiz_res = await client.post("/api/v1/quizzes", headers=auth_headers, json={
            "document_id": doc_id,
            "title": "OS Midterm Prep Quiz",
            "question_ids": [q["id"] for q in questions],
            "time_limit_seconds": 300,
        })
        assert quiz_res.status_code == 201
        quiz_id = quiz_res.json()["id"]

        # Start attempt
        att_start_res = await client.post(f"/api/v1/quizzes/{quiz_id}/attempts", headers=auth_headers)
        assert att_start_res.status_code == 200
        attempt_id = att_start_res.json()["id"]

        # Submit attempt
        submit_res = await client.post(f"/api/v1/attempts/{attempt_id}/submit", headers=auth_headers, json={
            "responses": [
                {"quiz_question_id": questions[0]["id"], "selected_answer": questions[0]["correct_answer"]},
                {"quiz_question_id": questions[1]["id"], "selected_answer": "Wrong option"},
            ],
            "time_taken_seconds": 45,
        })
        assert submit_res.status_code == 200
        assert submit_res.json()["score"] == 1

        # 11. Flashcards
        fc_res = await client.post("/api/v1/flashcards/generate", headers=auth_headers, json={
            "document_id": doc_id,
        })
        assert fc_res.status_code == 200
        assert len(fc_res.json()) >= 1

        # 12. Analytics
        ana_res = await client.get("/api/v1/analytics/overview", headers=auth_headers)
        assert ana_res.status_code == 200
        assert ana_res.json()["quizzes_completed"] >= 1

        # 13. System Models
        models_res = await client.get("/api/v1/system/models")
        assert models_res.status_code == 200
        assert "available_models" in models_res.json()
