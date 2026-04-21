from cn_review_pipeline.processor.clean import clean_review_text
from cn_review_pipeline.processor.tokenize import detect_language, tokenize


def test_clean_strips_html_and_urls():
    text = "<p>手机<br>非常好 https://example.com   很满意！！！！！</p>"
    cleaned = clean_review_text(text)
    assert "<p>" not in cleaned
    assert "https://" not in cleaned
    assert "  " not in cleaned  # whitespace collapsed
    assert "！！！！！" not in cleaned  # repeated punct collapsed


def test_tokenize_removes_stopwords():
    tokens = tokenize("这个 手机 的 屏幕 非常 好")
    assert "手机" in tokens
    assert "屏幕" in tokens
    # '的' is in the shipped stopword list.
    assert "的" not in tokens


def test_detect_language_chinese():
    assert detect_language("这是一个中文句子") in {"zh-cn", "zh-tw", "ko", "ja"}


def test_detect_language_empty():
    assert detect_language("") == "unknown"
