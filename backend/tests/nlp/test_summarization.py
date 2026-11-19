import uuid
import pytest
from httpx import AsyncClient, ASGITransport

from backend.app.main import app
from backend.app.nlp.extractive import (
    FrequencySummarizer,
    TFIDFSummarizer,
    TextRankSummarizer,
    extract_definitions,
    extract_key_points,
)
from backend.app.nlp.abstractive import AbstractiveSummarizer
from backend.app.nlp.evaluation import compute_rouge_scores, compare_extractive_abstractive


SAMPLE_NLP_TEXT = (
    "Natural Language Processing is defined as a branch of computer science and artificial intelligence. "
    "It focuses on the interactions between computational algorithms and human languages. "
    "Modern systems rely on deep neural networks such as Transformers to process textual data. "
    "The Transformer architecture was introduced in 2017 by Vaswani and colleagues. "
    "It replaces recurrent layers with multi-head self-attention mechanisms. "
    "Self-attention refers to an attention mechanism relating different positions of a single sequence. "
    "Extractive summarization selects salient sentences directly from the source document without modification. "
    "In contrast, abstractive summarization generates novel phrasing and paraphrases using generative models. "
    "Evaluation of summarization systems commonly employs ROUGE metrics to measure n-gram overlap. "
    "ROUGE-1 measures unigram overlap, whereas ROUGE-2 measures bigram overlap between candidate and reference texts."
)


def test_frequency_summarizer():
    summarizer = FrequencySummarizer()
    summary, sentences = summarizer.summarize(SAMPLE_NLP_TEXT, num_sentences=3)

    assert len(sentences) == 3
    assert len(summary) > 50
    assert any("ROUGE" in s or "summarization" in s or "attention" in s for s in sentences)


def test_tfidf_summarizer():
    summarizer = TFIDFSummarizer()
    summary, sentences = summarizer.summarize(SAMPLE_NLP_TEXT, num_sentences=4)

    assert len(sentences) == 4
    assert len(summary) > 50


def test_textrank_summarizer_from_scratch():
    summarizer = TextRankSummarizer(damping=0.85, max_iter=100)
    summary, sentences = summarizer.summarize(SAMPLE_NLP_TEXT, num_sentences=3)

    assert len(sentences) == 3
    assert len(summary) > 50
    # TextRank should extract salient sentences
    assert any("ROUGE" in s or "summarization" in s or "attention" in s or "mechanisms" in s for s in sentences)


def test_definitions_and_key_points_extraction():
    definitions = extract_definitions(SAMPLE_NLP_TEXT)
    assert len(definitions) >= 1
    terms = [d["term"].lower() for d in definitions]
    assert any("natural language processing" in t or "self-attention" in t for t in terms)

    sentences = [s.strip() for s in SAMPLE_NLP_TEXT.split(".") if s.strip()]
    points = extract_key_points(sentences)
    assert len(points) >= 3


def test_rouge_evaluation():
    ref = "The transformer architecture utilizes multi-head self-attention mechanisms."
    hyp = "The transformer architecture utilizes self-attention mechanisms."

    rouge = compute_rouge_scores(hyp, ref)
    assert "rouge1" in rouge
    assert "rouge2" in rouge
    assert "rougeL" in rouge
    assert rouge["rouge1"]["fmeasure"] > 0.8
    assert rouge["rouge2"]["fmeasure"] > 0.6

    # Identical text should have F1 == 1.0
    exact = compute_rouge_scores(ref, ref)
    assert exact["rouge1"]["fmeasure"] == 1.0
    assert exact["rougeL"]["fmeasure"] == 1.0


def test_abstractive_summarizer():
    summarizer = AbstractiveSummarizer()
    summary, points, defs, model = summarizer.summarize(
        SAMPLE_NLP_TEXT, length="short", mode="standard"
    )

    assert len(summary) > 20
    assert len(points) > 0
    assert model is not None

    # Test exam mode
    exam_summ, _, _, _ = summarizer.summarize(
        SAMPLE_NLP_TEXT, length="medium", mode="exam"
    )
    assert "Exam Preparation Key Takeaways" in exam_summ


@pytest.mark.asyncio
async def test_summaries_api_endpoints_and_isolation():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Register User A
        uid_a = uuid.uuid4().hex[:8]
        reg_a = await client.post("/api/v1/auth/register", json={
            "email": f"student_a_{uid_a}@univ.edu",
            "password": "Password123!",
            "full_name": "Student A",
        })
        token_a = reg_a.json()["access_token"]
        headers_a = {"Authorization": f"Bearer {token_a}"}

        # Register User B
        uid_b = uuid.uuid4().hex[:8]
        reg_b = await client.post("/api/v1/auth/register", json={
            "email": f"student_b_{uid_b}@univ.edu",
            "password": "Password123!",
            "full_name": "Student B",
        })
        token_b = reg_b.json()["access_token"]
        headers_b = {"Authorization": f"Bearer {token_b}"}

        # User A uploads a document
        upload_res = await client.post(
            "/api/v1/documents/upload",
            headers=headers_a,
            files={"file": ("nlp_lecture.txt", SAMPLE_NLP_TEXT.encode("utf-8"), "text/plain")},
        )
        assert upload_res.status_code == 201
        doc_id = upload_res.json()["id"]

        # 1. Generate TextRank summary
        tr_res = await client.post(
            f"/api/v1/documents/{doc_id}/summaries/generate",
            headers=headers_a,
            json={"method": "textrank", "length": "short", "mode": "standard"},
        )
        assert tr_res.status_code == 200
        tr_data = tr_res.json()
        assert tr_data["method"] == "textrank"
        assert len(tr_data["content"]) > 30
        summary_id = tr_data["id"]

        # 2. Generate TF-IDF summary in bullet mode
        tfidf_res = await client.post(
            f"/api/v1/documents/{doc_id}/summaries/generate",
            headers=headers_a,
            json={"method": "tfidf", "length": "medium", "mode": "bullet"},
        )
        assert tfidf_res.status_code == 200
        assert "•" in tfidf_res.json()["content"]

        # 3. Generate Frequency summary in exam mode
        exam_res = await client.post(
            f"/api/v1/documents/{doc_id}/summaries/generate",
            headers=headers_a,
            json={"method": "frequency", "length": "detailed", "mode": "exam"},
        )
        assert exam_res.status_code == 200
        assert "Exam Key Points" in exam_res.json()["content"]

        # 4. List summaries for document
        list_res = await client.get(f"/api/v1/documents/{doc_id}/summaries", headers=headers_a)
        assert list_res.status_code == 200
        assert len(list_res.json()) >= 3

        # 5. Compare extractive vs abstractive summaries with ROUGE
        comp_res = await client.get(
            f"/api/v1/documents/{doc_id}/summaries/compare?extractive_method=textrank",
            headers=headers_a,
        )
        assert comp_res.status_code == 200
        comp_data = comp_res.json()
        assert "rouge" in comp_data
        assert "rouge1" in comp_data["rouge"]
        assert "extractive_text" in comp_data
        assert "abstractive_text" in comp_data

        # 6. Retrieve summary by ID
        get_res = await client.get(f"/api/v1/summaries/{summary_id}", headers=headers_a)
        assert get_res.status_code == 200
        assert get_res.json()["id"] == summary_id

        # 7. SECURITY ISOLATION: User B cannot access User A's summaries or comparisons
        b_get_res = await client.get(f"/api/v1/summaries/{summary_id}", headers=headers_b)
        assert b_get_res.status_code == 404

        b_comp_res = await client.get(
            f"/api/v1/documents/{doc_id}/summaries/compare",
            headers=headers_b,
        )
        assert b_comp_res.status_code == 404
