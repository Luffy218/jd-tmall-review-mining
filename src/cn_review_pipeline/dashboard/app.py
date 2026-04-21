"""Streamlit dashboard for analyzed reviews.

Launch with::

    crp dashboard  # or: streamlit run src/cn_review_pipeline/dashboard/app.py

Panels:
  * Sentiment distribution (pie + bar)
  * Word cloud
  * Trends over time (rolling sentiment)
  * Rating vs sentiment scatter
  * Complaints and strengths tables
"""

from __future__ import annotations

from collections import Counter
from io import BytesIO
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st
from wordcloud import WordCloud

from cn_review_pipeline.analyzer.insights import complaints_and_strengths
from cn_review_pipeline.logging_setup import configure_logging
from cn_review_pipeline.models import AnalyzedReview
from cn_review_pipeline.storage import get_store

# Fonts that typically ship with Linux / macOS images and support CJK glyphs.
_CJK_FONT_CANDIDATES = (
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "/System/Library/Fonts/PingFang.ttc",
)


def _default_cjk_font() -> str | None:
    for candidate in _CJK_FONT_CANDIDATES:
        if Path(candidate).exists():
            return candidate
    return None

configure_logging()

st.set_page_config(page_title="CN Review Pipeline", layout="wide")
st.title("Chinese E-commerce Review Analytics")

# --------------------------------------------------------------------------- data

store = get_store()
store.init_schema()


@st.cache_data(ttl=60, show_spinner=False)
def load_reviews(platform: str | None, product_id: str | None) -> pd.DataFrame:
    rows = store.list_analyzed(
        platform=platform or None, product_id=product_id or None
    )
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame([r.model_dump() for r in rows])


with st.sidebar:
    st.header("Filters")
    platform = st.selectbox("Platform", options=["", "jd", "tmall"], index=0)
    product_id = st.text_input("Product ID", value="")
    if st.button("Reload"):
        load_reviews.clear()

df = load_reviews(platform or None, product_id or None)

if df.empty:
    st.info(
        "No analyzed reviews found. Run `crp scrape jd <product_id>` first, or "
        "load fixtures with `python scripts/load_fixtures.py`."
    )
    st.stop()

st.metric("Total reviews", len(df))
col_p, col_n = st.columns(2)
col_p.metric("Positive", int((df["sentiment_label"] == "positive").sum()))
col_n.metric("Negative", int((df["sentiment_label"] == "negative").sum()))

# --------------------------------------------------------------------------- charts

st.subheader("Sentiment distribution")
sentiment_counts = df["sentiment_label"].value_counts().reset_index()
sentiment_counts.columns = ["label", "count"]
fig = px.bar(sentiment_counts, x="label", y="count", color="label")
st.plotly_chart(fig, use_container_width=True)

st.subheader("Rating vs sentiment")
rating_df = df.dropna(subset=["rating"])
if rating_df.empty:
    st.caption("No ratings available for this selection.")
else:
    fig = px.scatter(
        rating_df,
        x="rating",
        y="sentiment_score",
        color="sentiment_label",
        hover_data=["clean_text"],
    )
    st.plotly_chart(fig, use_container_width=True)

st.subheader("Sentiment over time")
time_df = df.dropna(subset=["created_at"]).copy()
if time_df.empty:
    st.caption("No timestamped reviews for this selection.")
else:
    time_df["created_at"] = pd.to_datetime(time_df["created_at"])
    time_df = time_df.sort_values("created_at")
    time_df["rolling_sentiment"] = time_df["sentiment_score"].rolling(
        window=max(5, len(time_df) // 20), min_periods=1
    ).mean()
    fig = px.line(time_df, x="created_at", y="rolling_sentiment")
    st.plotly_chart(fig, use_container_width=True)

st.subheader("Word cloud (all reviews)")
all_tokens: list[str] = []
for tokens in df["tokens"]:
    all_tokens.extend(tokens)
freq = Counter(all_tokens)
if freq:
    wc = WordCloud(
        width=1200,
        height=500,
        background_color="white",
        font_path=_default_cjk_font(),
    ).generate_from_frequencies(freq)
    buf = BytesIO()
    wc.to_image().save(buf, format="PNG")
    st.image(buf.getvalue(), use_column_width=True)
else:
    st.caption("No tokens available.")

# --------------------------------------------------------------------------- insights

st.subheader("Complaints vs strengths")
analyzed_objs = [AnalyzedReview.model_validate(row) for row in df.to_dict("records")]
ins = complaints_and_strengths(analyzed_objs)
left, right = st.columns(2)
left.markdown("**Strengths**")
left.dataframe(pd.DataFrame(ins["strengths"], columns=["term", "signal"]))
right.markdown("**Complaints**")
right.dataframe(pd.DataFrame(ins["complaints"], columns=["term", "signal"]))
