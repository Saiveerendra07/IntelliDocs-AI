from typing import Any, Dict, List, Optional
import numpy as np
from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer
from sklearn.decomposition import LatentDirichletAllocation
from sklearn.cluster import KMeans

from backend.app.documents.chunking import split_into_sentences


class LDATopicModeler:
    """
    Latent Dirichlet Allocation (LDA) topic modeler:
    Discovers latent thematic topics across document chunks/sentences.
    """
    def __init__(self, n_topics: int = 3, n_words: int = 5):
        self.n_topics = n_topics
        self.n_words = n_words

    def fit_transform(self, documents: List[str]) -> List[Dict[str, Any]]:
        # Filter documents
        valid_docs = [d.strip() for d in documents if len(d.strip()) > 15]
        if not valid_docs:
            return []

        # If too few documents, break into sentences
        if len(valid_docs) < self.n_topics:
            expanded = []
            for d in valid_docs:
                expanded.extend(split_into_sentences(d))
            valid_docs = [s for s in expanded if len(s.split()) >= 3]

        if not valid_docs:
            return []

        k = min(self.n_topics, max(1, len(valid_docs) // 2))

        try:
            vectorizer = CountVectorizer(stop_words="english", max_features=100)
            doc_term_matrix = vectorizer.fit_transform(valid_docs)
            feature_names = vectorizer.get_feature_names_out()

            if len(feature_names) == 0:
                return []

            lda = LatentDirichletAllocation(
                n_components=k,
                random_state=42,
                max_iter=20,
                learning_method="batch",
            )
            lda.fit(doc_term_matrix)

            topics = []
            for topic_idx, topic in enumerate(lda.components_):
                top_features_ind = topic.argsort()[: -self.n_words - 1 : -1]
                top_words = [feature_names[i] for i in top_features_ind]
                topics.append({
                    "topic_id": topic_idx + 1,
                    "words": top_words,
                })
            return topics

        except Exception:
            # Fallback for very small documents
            words = []
            for d in valid_docs:
                words.extend([w.lower() for w in d.split() if len(w) > 3])
            unique = list(set(words))
            return [{
                "topic_id": 1,
                "words": unique[:self.n_words] or ["document", "content"],
            }]


class KMeansChunkClusterer:
    """
    Clusters document chunks into thematic clusters using TF-IDF and K-Means.
    Generates human-readable labels for each cluster from top centroid terms.
    """
    def __init__(self, n_clusters: int = 3):
        self.n_clusters = n_clusters

    def cluster_chunks(self, chunks: List[str]) -> List[Dict[str, Any]]:
        valid_chunks = [c.strip() for c in chunks if len(c.strip()) > 15]
        if not valid_chunks:
            return []

        k = min(self.n_clusters, len(valid_chunks))
        if k <= 1:
            return [{
                "cluster_id": 0,
                "label": "Document Core Overview",
                "chunk_count": len(valid_chunks),
            }]

        try:
            vectorizer = TfidfVectorizer(stop_words="english", max_features=150)
            tfidf_matrix = vectorizer.fit_transform(valid_chunks)
            feature_names = vectorizer.get_feature_names_out()

            kmeans = KMeans(n_clusters=k, random_state=42, n_init="auto")
            labels = kmeans.fit_predict(tfidf_matrix)

            # Generate labels for each cluster from centroid's top TF-IDF words
            order_centroids = kmeans.cluster_centers_.argsort()[:, ::-1]
            clusters = []

            for i in range(k):
                count = int(np.sum(labels == i))
                top_word_indices = order_centroids[i, :3]
                cluster_keywords = [feature_names[ind] for ind in top_word_indices if ind < len(feature_names)]
                label_str = " & ".join(w.title() for w in cluster_keywords) if cluster_keywords else f"Topic Cluster {i + 1}"

                clusters.append({
                    "cluster_id": i,
                    "label": label_str,
                    "chunk_count": count,
                })

            return clusters

        except Exception:
            return [{
                "cluster_id": 0,
                "label": "General Overview",
                "chunk_count": len(valid_chunks),
            }]
