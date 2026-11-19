import uuid
import pytest
from httpx import AsyncClient, ASGITransport

from backend.app.main import app
from backend.app.nlp.keywords import (
    RAKEKeywordExtractor,
    TextRankKeywordExtractor,
    TFIDFKeywordExtractor,
    HybridKeywordExtractor,
)
from backend.app.nlp.topics import LDATopicModeler, KMeansChunkClusterer


SAMPLE_TEXT = (
    "Machine learning algorithms build mathematical models based on training data. "
    "Supervised learning algorithms use labeled datasets to train predictive neural networks. "
    "In unsupervised learning, clustering algorithms discover hidden patterns and groupings without labels. "
    "Reinforcement learning trains software agents to take actions in an environment to maximize cumulative reward. "
    "Deep neural networks, convolutional networks, and transformer attention mechanisms drive modern artificial intelligence."
)


def test_rake_keyword_extractor():
    extractor = RAKEKeywordExtractor()
    keywords = extractor.extract_keywords(SAMPLE_TEXT, top_n=5)

    assert len(keywords) > 0
    terms = [k[0] for k in keywords]
    assert any("learning" in t or "networks" in t or "algorithms" in t for t in terms)
    for term, score in keywords:
        assert score > 0.0


def test_textrank_keyword_extractor():
    extractor = TextRankKeywordExtractor(window_size=3, damping=0.85)
    keywords = extractor.extract_keywords(SAMPLE_TEXT, top_n=5)

    assert len(keywords) > 0
    words = [k[0] for k in keywords]
    assert any("learning" in w or "algorithms" in w or "neural" in w for w in words)


def test_hybrid_keyword_extractor():
    extractor = HybridKeywordExtractor()
    keywords = extractor.extract(SAMPLE_TEXT, top_n=8)

    assert len(keywords) > 0
    assert "term" in keywords[0]
    assert "score" in keywords[0]
    assert "method" in keywords[0]
    assert keywords[0]["score"] <= 1.0


def test_lda_topic_modeler():
    modeler = LDATopicModeler(n_topics=2, n_words=4)
    chunks = [
        "Supervised learning algorithms predict labels on test datasets.",
        "Unsupervised clustering models group data points according to similarity.",
        "Reinforcement learning optimizes reward signals in Markov decision processes.",
    ]
    topics = modeler.fit_transform(chunks)

    assert len(topics) >= 1
    assert "topic_id" in topics[0]
    assert len(topics[0]["words"]) > 0


def test_kmeans_chunk_clusterer():
    clusterer = KMeansChunkClusterer(n_clusters=2)
    chunks = [
        "Deep learning and backpropagation algorithms update neural weights.",
        "Convolutional neural networks process image tensors and visual features.",
        "Recurrent networks and transformers process natural language and sequential tokens.",
    ]
    clusters = clusterer.cluster_chunks(chunks)

    assert len(clusters) >= 1
    assert "cluster_id" in clusters[0]
    assert "label" in clusters[0]
    assert "chunk_count" in clusters[0]


@pytest.mark.asyncio
async def test_keywords_and_topics_api_endpoints():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Register User A
        uid = uuid.uuid4().hex[:8]
        reg_res = await client.post("/api/v1/auth/register", json={
            "email": f"topics_user_{uid}@univ.edu",
            "password": "SecurePassword123!",
            "full_name": "Topics User",
        })
        token = reg_res.json()["access_token"]
        auth_headers = {"Authorization": f"Bearer {token}"}

        # Upload document
        upload_res = await client.post(
            "/api/v1/documents/upload",
            headers=auth_headers,
            files={"file": ("ml_overview.txt", SAMPLE_TEXT.encode("utf-8"), "text/plain")},
        )
        assert upload_res.status_code == 201
        doc_id = upload_res.json()["id"]

        # 1. Keywords endpoint
        kw_res = await client.get(f"/api/v1/documents/{doc_id}/nlp/keywords?top_n=10", headers=auth_headers)
        assert kw_res.status_code == 200
        kw_data = kw_res.json()
        assert "keywords" in kw_data
        assert len(kw_data["keywords"]) > 0

        # 2. Topics endpoint
        top_res = await client.get(f"/api/v1/documents/{doc_id}/nlp/topics?n_topics=2", headers=auth_headers)
        assert top_res.status_code == 200
        top_data = top_res.json()
        assert "lda_topics" in top_data
        assert "clusters" in top_data
        assert len(top_data["lda_topics"]) > 0

        # 3. Search term endpoint
        search_res = await client.get(f"/api/v1/documents/{doc_id}/search-term?term=learning", headers=auth_headers)
        assert search_res.status_code == 200
        search_data = search_res.json()
        assert search_data["term"] == "learning"
        assert len(search_data["passages"]) > 0

        # 4. Security Isolation check for another user
        uid_other = uuid.uuid4().hex[:8]
        reg_other = await client.post("/api/v1/auth/register", json={
            "email": f"other_user_{uid_other}@univ.edu",
            "password": "SecurePassword123!",
            "full_name": "Other User",
        })
        other_headers = {"Authorization": f"Bearer {reg_other.json()['access_token']}"}

        get_other_kw = await client.get(f"/api/v1/documents/{doc_id}/nlp/keywords", headers=other_headers)
        assert get_other_kw.status_code == 404

        get_other_top = await client.get(f"/api/v1/documents/{doc_id}/nlp/topics", headers=other_headers)
        assert get_other_top.status_code == 404
