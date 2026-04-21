from cn_review_pipeline.analyzer.insights import complaints_and_strengths
from cn_review_pipeline.analyzer.keywords import (
    lda_topics,
    top_textrank_keywords,
    top_tfidf_keywords,
)
from cn_review_pipeline.analyzer.sentiment import RuleBasedSentimentAnalyzer
from cn_review_pipeline.models import AnalyzedReview


def test_rule_based_positive():
    r = RuleBasedSentimentAnalyzer().analyze("手机非常好，屏幕清晰，推荐购买！", rating=5)
    assert r.label == "positive"
    assert r.score > 0


def test_rule_based_negative():
    r = RuleBasedSentimentAnalyzer().analyze("质量很差，完全是垃圾，后悔购买", rating=1)
    assert r.label == "negative"
    assert r.score < 0


def test_rule_based_neutral():
    r = RuleBasedSentimentAnalyzer().analyze("还行吧，没什么特别的", rating=3)
    assert r.label == "neutral"


def test_tfidf_and_textrank_keywords():
    docs = [
        "手机屏幕非常清晰续航很好",
        "手机屏幕有色差不推荐购买",
        "屏幕亮度很棒但电池续航差",
    ]
    tfidf = top_tfidf_keywords(docs, top_n=5)
    assert tfidf
    assert all(isinstance(score, float) for _, score in tfidf)
    tr = top_textrank_keywords(docs[0], top_n=3)
    assert isinstance(tr, list)


def test_lda_topics_smoke():
    docs = ["手机屏幕 好", "电池 续航 差", "包装 精致 好看"]
    topics = lda_topics(docs, n_topics=2, top_n=3)
    assert len(topics) <= 2
    assert all(isinstance(topic, list) for topic in topics)


def test_insights_splits_by_polarity():
    from datetime import datetime

    base = dict(
        platform="jd",
        product_id="p",
        rating=5,
        text="",
        clean_text="",
        tokens=[],
        language="zh-cn",
        created_at=None,
        fetched_at=datetime.utcnow(),
    )
    reviews = [
        AnalyzedReview(
            review_id="1",
            sentiment_label="positive",
            sentiment_score=0.8,
            keywords=["屏幕", "续航"],
            **base,
        ),
        AnalyzedReview(
            review_id="2",
            sentiment_label="negative",
            sentiment_score=-0.7,
            keywords=["色差", "屏幕"],
            **base,
        ),
    ]
    ins = complaints_and_strengths(reviews)
    assert "strengths" in ins and "complaints" in ins
