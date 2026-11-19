import uuid
import pytest
from httpx import AsyncClient, ASGITransport

from backend.app.main import app
from backend.app.nlp.preprocessing import NLPPreprocessor, compute_readability_metrics, count_syllables_word


def test_syllable_counter():
    assert count_syllables_word("the") == 1
    assert count_syllables_word("computer") == 3
    assert count_syllables_word("natural") == 3
    assert count_syllables_word("intelligence") >= 4


def test_readability_metrics():
    simple_text = "The cat sat on the mat. The dog saw the cat. They had fun in the sun."
    words = simple_text.lower().replace(".", "").split()
    metrics = compute_readability_metrics(simple_text, words, sentences_count=3)

    assert "flesch_reading_ease" in metrics
    assert metrics["flesch_reading_ease"] >= 70.0  # Simple text should have high ease score
    assert "flesch_kincaid_grade" in metrics
    assert metrics["type_token_ratio"] > 0.0

    complex_text = (
        "The epistemological ramifications of contemporary algorithmic paradigm shifts "
        "necessitate rigorous multidimensional empirical investigation into linguistic phenomenology."
    )
    c_words = complex_text.lower().replace(".", "").split()
    c_metrics = compute_readability_metrics(complex_text, c_words, sentences_count=1)
    assert c_metrics["flesch_reading_ease"] < metrics["flesch_reading_ease"]
    assert c_metrics["flesch_kincaid_grade"] > metrics["flesch_kincaid_grade"]


def test_nlp_preprocessor_full_pipeline():
    preprocessor = NLPPreprocessor()
    sample_text = (
        "Alan Turing was an English mathematician and computer scientist at Cambridge University. "
        "He played a pivotal role in cracking intercepted coded messages during World War II."
    )

    res = preprocessor.process_full(sample_text)

    # Tokens & filtering
    assert len(res["tokens"]) > 10
    assert len(res["filtered_tokens"]) > 0
    assert "Turing" in res["tokens"]
    assert "was" not in res["filtered_tokens"]  # stopword removed

    # Stemming & Lemmatization
    assert len(res["porter_stems"]) == len(res["filtered_tokens"])
    assert len(res["snowball_stems"]) == len(res["filtered_tokens"])
    assert len(res["lemmatized_sample"]) == len(res["filtered_tokens"])

    # POS tagging
    pos_tags = {p["text"]: p["pos"] for p in res["pos_tokens"]}
    assert "scientist" in pos_tags
    assert pos_tags["scientist"] in ["NOUN", "PROPN"]
    assert pos_tags["Turing"] in ["NOUN", "PROPN"]

    # NER
    ent_texts = [e["text"] for e in res["entities"]]
    assert any("Alan Turing" in t or "Turing" in t for t in ent_texts)

    # N-grams
    assert len(res["unigrams"]) > 0
    assert len(res["bigrams"]) > 0

    # Readability
    assert res["readability"]["flesch_reading_ease"] > 0


@pytest.mark.asyncio
async def test_nlp_api_endpoints():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Ad-hoc preprocess endpoint
        res = await client.post("/api/v1/nlp/preprocess", json={
            "text": "Natural Language Processing enables computers to comprehend human documents."
        })
        assert res.status_code == 200
        data = res.json()
        assert "tokens" in data
        assert "filtered_tokens" in data
        assert "porter_stems" in data
        assert "lemmatized_sample" in data

        # 2. Register user & upload a document for document-level NLP endpoints
        uid = uuid.uuid4().hex[:8]
        reg_res = await client.post("/api/v1/auth/register", json={
            "email": f"nlp_tester_{uid}@univ.edu",
            "password": "SecurePassword123!",
            "full_name": "NLP Tester",
        })
        token = reg_res.json()["access_token"]
        auth_headers = {"Authorization": f"Bearer {token}"}

        upload_res = await client.post(
            "/api/v1/documents/upload",
            headers=auth_headers,
            files={"file": ("lecture_turing.txt", (
                b"Alan Turing was a renowned mathematician at Cambridge University in the United Kingdom. "
                b"Natural Language Processing, artificial intelligence, and machine learning transform education."
            ), "text/plain")},
        )
        assert upload_res.status_code == 201
        doc_id = upload_res.json()["id"]

        # 3. Document Preprocessing
        doc_prep = await client.get(f"/api/v1/documents/{doc_id}/nlp/preprocessing", headers=auth_headers)
        assert doc_prep.status_code == 200
        assert "sample_cleaned" in doc_prep.json()

        # 4. Document POS
        doc_pos = await client.get(f"/api/v1/documents/{doc_id}/nlp/pos", headers=auth_headers)
        assert doc_pos.status_code == 200
        pos_data = doc_pos.json()
        assert len(pos_data["tokens"]) > 0
        assert "pos" in pos_data["tokens"][0]

        # 5. Document NER
        doc_ner = await client.get(f"/api/v1/documents/{doc_id}/nlp/entities", headers=auth_headers)
        assert doc_ner.status_code == 200
        ner_data = doc_ner.json()
        assert "entities" in ner_data
        assert "entity_counts" in ner_data

        # 6. Document N-grams
        doc_ngrams = await client.get(f"/api/v1/documents/{doc_id}/nlp/ngrams?n=2", headers=auth_headers)
        assert doc_ngrams.status_code == 200
        assert "ngrams" in doc_ngrams.json()

        # 7. Document Frequency
        doc_freq = await client.get(f"/api/v1/documents/{doc_id}/nlp/frequency?top_n=10", headers=auth_headers)
        assert doc_freq.status_code == 200
        assert "frequencies" in doc_freq.json()

        # 8. Document Readability
        doc_read = await client.get(f"/api/v1/documents/{doc_id}/nlp/readability", headers=auth_headers)
        assert doc_read.status_code == 200
        read_data = doc_read.json()
        assert "flesch_reading_ease" in read_data
        assert "flesch_kincaid_grade" in read_data
        assert "automated_readability_index" in read_data
