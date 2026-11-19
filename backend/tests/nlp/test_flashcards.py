import uuid
from datetime import datetime, timezone
import pytest
from httpx import AsyncClient, ASGITransport

from backend.app.main import app
from backend.app.db.session import SessionLocal
from backend.app.db.models.user import User
from backend.app.db.models.document import Document, DocumentChunk
from backend.app.nlp.flashcards import SM2SpacedRepetition, FlashcardGenerator
from backend.app.core.security import get_password_hash, create_access_token


def test_sm2_algorithm_calculations():
    # 1. First review with perfect score (rating=5)
    rep, ef, interval, next_rev = SM2SpacedRepetition.calculate_next_review(rating=5, repetitions=0, easiness_factor=2.5, interval=1)
    assert rep == 1
    assert interval == 1
    assert ef >= 2.5
    assert next_rev > datetime.now(timezone.utc)

    # 2. Second review with good score (rating=4)
    rep2, ef2, interval2, _ = SM2SpacedRepetition.calculate_next_review(rating=4, repetitions=rep, easiness_factor=ef, interval=interval)
    assert rep2 == 2
    assert interval2 == 6

    # 3. Third review with good score (rating=4) -> interval = ceil(6 * ef2)
    rep3, ef3, interval3, _ = SM2SpacedRepetition.calculate_next_review(rating=4, repetitions=rep2, easiness_factor=ef2, interval=interval2)
    assert rep3 == 3
    assert interval3 > 6

    # 4. Failed review (rating=1) -> resets repetitions to 0 and interval to 1
    rep_fail, ef_fail, interval_fail, _ = SM2SpacedRepetition.calculate_next_review(rating=1, repetitions=rep3, easiness_factor=ef3, interval=interval3)
    assert rep_fail == 0
    assert interval_fail == 1

    # 5. Boundary check: EF floor is 1.3
    low_ef = 1.35
    for _ in range(10):
        _, low_ef, _, _ = SM2SpacedRepetition.calculate_next_review(rating=0, repetitions=0, easiness_factor=low_ef, interval=1)
    assert low_ef == 1.3


def test_flashcard_generator_definitions_and_sentences():
    chunks = [
        DocumentChunk(
            id=uuid.uuid4(),
            document_id=uuid.uuid4(),
            chunk_index=0,
            text=(
                "Convolutional Neural Networks are deep neural network architectures specialized for grid structured data. "
                "Kernel filters slide across the input tensor computing local dot products to extract spatial feature maps. "
                "Pooling layers perform spatial downsampling to achieve translation invariance and reduce dimensionality."
            ),
            token_count=45,
            page_start=1,
            page_end=1,
            section_title="Computer Vision with CNNs",
        )
    ]

    generator = FlashcardGenerator()
    cards = generator.generate_flashcards(chunks=chunks, max_cards=5)

    assert len(cards) >= 1
    for c in cards:
        assert "front" in c and c["front"] != ""
        assert "back" in c and c["back"] != ""
        assert "Page 1" in c["back"]
        assert c["source_page"] == 1


@pytest.mark.asyncio
async def test_flashcard_api_endpoints_and_isolation():
    db = SessionLocal()
    uid = uuid.uuid4().hex[:8]

    user_a = User(
        id=uuid.uuid4(),
        email=f"fc_user_a_{uid}@example.com",
        hashed_password=get_password_hash("Secret123!"),
        full_name="Flashcard User A",
    )
    user_b = User(
        id=uuid.uuid4(),
        email=f"fc_user_b_{uid}@example.com",
        hashed_password=get_password_hash("Secret123!"),
        full_name="Flashcard User B",
    )
    db.add(user_a)
    db.add(user_b)
    db.commit()

    doc_id = uuid.uuid4()
    doc_a = Document(
        id=doc_id,
        user_id=user_a.id,
        original_filename="cnn_architectures.pdf",
        stored_path="backend/storage/uploads/cnn_architectures.pdf",
        mime_type="application/pdf",
        file_size=2048,
        status="ready",
        page_count=2,
    )
    db.add(doc_a)

    chunk = DocumentChunk(
        id=uuid.uuid4(),
        document_id=doc_id,
        chunk_index=0,
        text="Max pooling extracts the maximum value within each spatial window to provide translation invariance.",
        token_count=16,
        page_start=2,
        page_end=2,
        section_title="Pooling Operations",
    )
    db.add(chunk)
    db.commit()

    token_a = create_access_token(data={"sub": str(user_a.id), "email": user_a.email})
    token_b = create_access_token(data={"sub": str(user_b.id), "email": user_b.email})

    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. User A generates flashcards
        gen_res = await client.post(
            "/api/v1/flashcards/generate",
            headers=headers_a,
            json={"document_id": str(doc_id)},
        )
        assert gen_res.status_code in (200, 201)
        cards = gen_res.json()
        assert len(cards) >= 1
        card_id = cards[0]["id"]
        assert cards[0]["review_count"] == 0

        # 2. User A reviews card with rating 5 (easy)
        rev_res = await client.post(
            f"/api/v1/flashcards/{card_id}/review",
            headers=headers_a,
            json={"difficulty_mark": "easy", "rating": 5},
        )
        assert rev_res.status_code == 200
        rev_data = rev_res.json()
        assert rev_data["review_count"] == 1
        assert rev_data["difficulty_mark"] == "easy"
        assert rev_data["next_review_at"] is not None

        # 3. Multi-tenant isolation: User B cannot review User A's card (404)
        cross_rev = await client.post(
            f"/api/v1/flashcards/{card_id}/review",
            headers=headers_b,
            json={"difficulty_mark": "medium"},
        )
        assert cross_rev.status_code == 404

        # 4. User A deletes card
        del_res = await client.delete(f"/api/v1/flashcards/{card_id}", headers=headers_a)
        assert del_res.status_code == 204

    try:
        db.delete(doc_a)
        db.delete(user_a)
        db.delete(user_b)
        db.commit()
    except Exception:
        pass
    db.close()
