from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class PreprocessRequest(BaseModel):
    text: str


class PreprocessResponse(BaseModel):
    sample_original: str
    sample_cleaned: str
    stats: Dict[str, int]
    tokens: List[str]
    filtered_tokens: List[str]
    porter_stems: List[str]
    snowball_stems: List[str]
    lemmatized_sample: List[str]


class POSToken(BaseModel):
    text: str
    pos: str
    tag: str
    lemma: str


class POSResponse(BaseModel):
    tokens: List[POSToken]


class EntityItem(BaseModel):
    text: str
    label: str
    start_char: int
    end_char: int


class NERResponse(BaseModel):
    entities: List[EntityItem]
    entity_counts: Dict[str, int]


class NgramItem(BaseModel):
    phrase: str
    count: int


class NgramsResponse(BaseModel):
    ngrams: List[NgramItem]


class FrequencyItem(BaseModel):
    word: str
    count: int


class FrequencyResponse(BaseModel):
    frequencies: List[FrequencyItem]


class KeywordItem(BaseModel):
    term: str
    score: float
    method: str = "merged"


class KeywordsResponse(BaseModel):
    keywords: List[KeywordItem]


class LDATopic(BaseModel):
    topic_id: int
    words: List[str]


class ChunkCluster(BaseModel):
    cluster_id: int
    label: str
    chunk_count: int


class TopicsResponse(BaseModel):
    lda_topics: List[LDATopic]
    clusters: List[ChunkCluster]


class SearchTermPassage(BaseModel):
    chunk_id: str
    page_start: int
    page_end: int
    score: float
    text: str


class SearchTermResponse(BaseModel):
    term: str
    passages: List[SearchTermPassage]


class ReadabilityResponse(BaseModel):
    flesch_reading_ease: float
    flesch_reading_ease_label: str
    flesch_kincaid_grade: float
    gunning_fog: float
    coleman_liau: float
    automated_readability_index: float
    type_token_ratio: float
    average_sentence_length: float
