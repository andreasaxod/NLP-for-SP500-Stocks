"""
app.py – Streamlit MVP for Stock Sentiment Analyzer
Run: streamlit run app.py
"""

import streamlit as st
import pandas as pd
from engine import run_analysis, get_price_history

# ── Page config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Stock Sentiment Analyzer",
    page_icon="📈",
    layout="wide",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────

st.markdown("""
<style>
    .signal-box {
        padding: 1.5rem 2rem;
        border-radius: 12px;
        text-align: center;
        margin: 1rem 0;
    }
    .signal-bullish {
        background: linear-gradient(135deg, #064e3b, #065f46);
        border: 2px solid #10b981;
    }
    .signal-bearish {
        background: linear-gradient(135deg, #7f1d1d, #991b1b);
        border: 2px solid #ef4444;
    }
    .signal-neutral {
        background: linear-gradient(135deg, #78350f, #92400e);
        border: 2px solid #f59e0b;
    }
    .signal-label {
        font-size: 2.5rem;
        font-weight: 800;
        color: white;
    }
    .confidence-label {
        font-size: 1.1rem;
        color: rgba(255,255,255,0.8);
        margin-top: 0.25rem;
    }
    .metric-card {
        background: #1e1e2e;
        border: 1px solid #333;
        border-radius: 10px;
        padding: 1rem 1.25rem;
        text-align: center;
    }
    .metric-value {
        font-size: 1.6rem;
        font-weight: 700;
        color: white;
    }
    .metric-label {
        font-size: 0.8rem;
        color: #999;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    .source-tag {
        display: inline-block;
        background: #2a2a3e;
        border: 1px solid #444;
        border-radius: 6px;
        padding: 0.2rem 0.6rem;
        margin: 0.15rem;
        font-size: 0.8rem;
        color: #ccc;
    }
</style>
""", unsafe_allow_html=True)

# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## 📈 Stock Sentiment Analyzer")
    st.markdown("NLP-powered bullish/bearish signals from multi-source financial news.")
    st.markdown("---")

    ticker = st.text_input(
        "Stock Ticker",
        value="NVDA",
        max_chars=10,
        placeholder="e.g. AAPL, TSLA, NVDA",
    ).upper().strip()

    chart_period = st.selectbox(
        "Price Chart Period",
        options=["1mo", "3mo", "6mo", "1y"],
        index=0,
    )

    analyze_btn = st.button("🔍 Analyze Sentiment", use_container_width=True, type="primary")

    st.markdown("---")
    st.markdown("#### Data Sources")
    st.markdown(
        "**Free (no key):** Yahoo Finance, GDELT, FinViz, MarketWatch, Google News\n\n"
        "**Optional:** NewsAPI"
    )
    st.markdown("---")
    st.markdown(
        "**NLP Engine:** Groq (Llama 3.3)\n\n"
        "Built for IE University NLP Group Project"
    )

# ── Main ──────────────────────────────────────────────────────────────────────

if not analyze_btn and "result" not in st.session_state:
    # Landing
    st.markdown("# 📊 Stock Sentiment Analyzer")
    st.markdown(
        "Enter a stock ticker in the sidebar and click **Analyze Sentiment** to get "
        "an AI-powered bullish/bearish signal based on real-time news from multiple sources."
    )

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("### 📡 Multi-Source")
        st.markdown("Aggregates news from 6 sources including web scraping and APIs.")
    with col2:
        st.markdown("### 🧠 NLP Analysis")
        st.markdown("Llama 3.3 via Groq analyzes sentiment across all collected articles.")
    with col3:
        st.markdown("### 📈 Actionable Signal")
        st.markdown("Clear BULLISH / BEARISH / NEUTRAL output with confidence score.")

elif analyze_btn or "result" in st.session_state:
    if analyze_btn:
        # Run analysis
        progress_bar = st.progress(0, text="Starting analysis...")
        status_text = st.empty()
        steps = [0]
        total_steps = 8

        def on_progress(source_name, count):
            steps[0] += 1
            pct = min(steps[0] / total_steps, 0.95)
            progress_bar.progress(pct, text=f"📡 {source_name}... ({count} items)")

        result = run_analysis(ticker, progress_callback=on_progress)
        price_history = get_price_history(ticker, period=chart_period)

        progress_bar.progress(1.0, text="✅ Analysis complete!")
        status_text.empty()

        st.session_state["result"] = result
        st.session_state["price_history"] = price_history
        st.session_state["ticker"] = ticker

    result = st.session_state["result"]
    price_history = st.session_state.get("price_history", [])

    # ── Signal banner ─────────────────────────────────────────────────────

    signal_class = f"signal-{result.signal.lower()}"
    emoji = {"BULLISH": "🐂", "BEARISH": "🐻", "NEUTRAL": "⏸️"}.get(result.signal, "")

    st.markdown(f"""
    <div class="signal-box {signal_class}">
        <div class="signal-label">{emoji} {result.signal}</div>
        <div class="confidence-label">
            {result.company_name} ({result.ticker}) · Confidence: {result.confidence:.0%}
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Metrics row ───────────────────────────────────────────────────────

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Price", f"${result.price:,.2f}", f"{result.change_pct:+.2f}%")
    with c2:
        st.metric("Confidence", f"{result.confidence:.0%}")
    with c3:
        sb = result.source_breakdown
        pos = sb.get("positive_count", 0)
        neg = sb.get("negative_count", 0)
        st.metric("Positive / Negative", f"{pos} / {neg}")
    with c4:
        st.metric("Sources Analyzed", result.sources_used)

    # ── Two columns: chart + summary ──────────────────────────────────────

    left, right = st.columns([3, 2])

    with left:
        st.markdown("### 📈 Price Chart")
        if price_history:
            df = pd.DataFrame(price_history)
            df["date"] = pd.to_datetime(df["date"])
            df = df.set_index("date")
            st.line_chart(df["close"], use_container_width=True)
        else:
            st.info("Price history not available.")

    with right:
        st.markdown("### 🧠 AI Summary")
        st.write(result.summary)

        if result.key_factors:
            st.markdown("#### Key Factors")
            for i, factor in enumerate(result.key_factors, 1):
                st.markdown(f"**{i}.** {factor}")

    # ── Source breakdown ──────────────────────────────────────────────────

    st.markdown("---")
    st.markdown("### 📡 Source Breakdown")

    source_cols = st.columns(len(result.source_counts) if result.source_counts else 1)
    for i, (name, count) in enumerate(result.source_counts.items()):
        with source_cols[i]:
            icon = "✅" if count > 0 else "❌"
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-value">{count} {icon}</div>
                <div class="metric-label">{name}</div>
            </div>
            """, unsafe_allow_html=True)

    # ── Sentiment distribution bar ────────────────────────────────────────

    sb = result.source_breakdown
    if sb:
        st.markdown("### 📊 Sentiment Distribution")
        pos = sb.get("positive_count", 0)
        neg = sb.get("negative_count", 0)
        neu = sb.get("neutral_count", 0)
        total = pos + neg + neu or 1

        col_pos, col_neu, col_neg = st.columns([max(pos, 1), max(neu, 1), max(neg, 1)])
        with col_pos:
            st.markdown(f"🟢 **Positive**: {pos} ({pos/total:.0%})")
            st.progress(pos / total if total else 0)
        with col_neu:
            st.markdown(f"🟡 **Neutral**: {neu} ({neu/total:.0%})")
            st.progress(neu / total if total else 0)
        with col_neg:
            st.markdown(f"🔴 **Negative**: {neg} ({neg/total:.0%})")
            st.progress(neg / total if total else 0)

    # ── Headlines table ───────────────────────────────────────────────────

    st.markdown("---")
    st.markdown("### 📰 Analyzed Headlines")

    if result.items:
        headlines_data = []
        for item in result.items:
            headlines_data.append({
                "Source": item.source,
                "Headline": item.title,
                "Date": item.date,
            })
        df_headlines = pd.DataFrame(headlines_data)
        st.dataframe(
            df_headlines,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Headline": st.column_config.TextColumn(width="large"),
            },
        )
    else:
        st.info("No headlines collected.")

    # ── Results & Validation ─────────────────────────────────────────────

    st.markdown("---")
    st.markdown("### 📊 Results & Validation")

    # Performance metrics row
    perf1, perf2, perf3, perf4 = st.columns(4)
    with perf1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value" style="color:#2dd4bf;">{result.total_time:.1f}s</div>
            <div class="metric-label">Total Processing Time</div>
            <div style="font-size:0.75rem; color:#777;">End-to-end from ticker to signal</div>
        </div>
        """, unsafe_allow_html=True)
    with perf2:
        active = sum(1 for v in result.source_counts.values() if v > 0)
        total_sources = len(result.source_counts)
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value" style="color:#2dd4bf;">{active}/{total_sources}</div>
            <div class="metric-label">Sources Fired</div>
            <div style="font-size:0.75rem; color:#777;">Active data sources this run</div>
        </div>
        """, unsafe_allow_html=True)
    with perf3:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value" style="color:#2dd4bf;">{result.groq_time:.1f}s</div>
            <div class="metric-label">Groq Latency</div>
            <div style="font-size:0.75rem; color:#777;">Llama 3.3 70B inference</div>
        </div>
        """, unsafe_allow_html=True)
    with perf4:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value" style="color:#2dd4bf;">{result.collection_time:.1f}s</div>
            <div class="metric-label">Collection Time</div>
            <div style="font-size:0.75rem; color:#777;">Scraping + API calls</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Pipeline funnel
    pipe_left, pipe_right = st.columns([3, 2])

    with pipe_left:
        st.markdown("#### 🔬 Data Pipeline Funnel")
        funnel_data = {
            "Stage": [
                "① Raw collected",
                "② After deduplication",
                "③ After relevance filter",
                "④ Sent to LLM",
            ],
            "Headlines": [
                result.raw_count,
                result.dedup_count,
                result.filtered_count,
                result.sources_used,
            ],
        }
        df_funnel = pd.DataFrame(funnel_data)
        st.dataframe(df_funnel, use_container_width=True, hide_index=True)

        # Funnel bar chart
        st.bar_chart(
            pd.DataFrame({
                "Headlines": funnel_data["Headlines"],
            }, index=funnel_data["Stage"]),
            use_container_width=True,
        )

    with pipe_right:
        st.markdown("#### 📡 Articles per Source")
        source_df = pd.DataFrame({
            "Source": list(result.source_counts.keys()),
            "Articles": list(result.source_counts.values()),
        })
        source_df = source_df.sort_values("Articles", ascending=True)
        st.bar_chart(
            source_df.set_index("Source"),
            use_container_width=True,
            horizontal=True,
        )

        # Source status
        st.markdown("#### Source Status")
        for name, count in result.source_counts.items():
            icon = "🟢" if count > 0 else "🔴"
            st.markdown(f"{icon} **{name}**: {count} articles")

    # ── Footer ────────────────────────────────────────────────────────────

    st.markdown("---")
    st.markdown(
        "<div style='text-align:center; color:#666; font-size:0.85rem;'>"
        "Stock Sentiment Analyzer · NLP Group Project · IE University · "
        "Powered by Groq (Llama 3.3), GDELT, FinViz, Yahoo Finance, Google News"
        "</div>",
        unsafe_allow_html=True,
    )