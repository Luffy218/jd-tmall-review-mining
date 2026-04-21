"""Keyword and topic extraction.

* ``top_tfidf_keywords`` — corpus-level TF-IDF.
* ``top_textrank_keywords`` — per-document TextRank via jieba.analyse.
* ``lda_topics`` — scikit-learn LatentDirichletAllocation topic model.
"""

from __future__ import annotations

from collections.abc import Sequence

from sklearn.decomposition import LatentDirichletAllocation
from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer

from ..processor.tokenize import tokenize


def _tokenized_joiner(text: str) -> list[str]:
    return tokenize(text)


def top_tfidf_keywords(
    documents: Sequence[str], *, top_n: int = 20
) -> list[tuple[str, float]]:
    """Return the top-N TF-IDF keywords across a corpus."""
    if not documents:
        return []
    vectoriser = TfidfVectorizer(
        tokenizer=_tokenized_joiner,
        token_pattern=None,
        lowercase=False,
        max_df=0.95,
        min_df=1,
    )
    matrix = vectoriser.fit_transform(documents)
    scores = matrix.sum(axis=0).A1
    vocab = vectoriser.get_feature_names_out()
    pairs = sorted(zip(vocab, scores, strict=False), key=lambda kv: kv[1], reverse=True)
    return [(term, float(score)) for term, score in pairs[:top_n]]


def top_textrank_keywords(text: str, *, top_n: int = 10) -> list[str]:
    """Per-document TextRank keywords using jieba.analyse."""
    from jieba import analyse  # local import; jieba.analyse is heavier than jieba.cut

    return list(analyse.textrank(text, topK=top_n))


def lda_topics(
    documents: Sequence[str], *, n_topics: int = 5, top_n: int = 8
) -> list[list[str]]:
    """Return ``n_topics`` topic word-lists via LDA."""
    if not documents:
        return []
    vectoriser = CountVectorizer(
        tokenizer=_tokenized_joiner,
        token_pattern=None,
        lowercase=False,
        max_df=0.95,
        min_df=1,
    )
    matrix = vectoriser.fit_transform(documents)
    effective_topics = min(n_topics, matrix.shape[0]) or 1
    lda = LatentDirichletAllocation(n_components=effective_topics, random_state=42)
    lda.fit(matrix)
    vocab = vectoriser.get_feature_names_out()
    topics: list[list[str]] = []
    for component in lda.components_:
        top_idx = component.argsort()[::-1][:top_n]
        topics.append([vocab[i] for i in top_idx])
    return topics
