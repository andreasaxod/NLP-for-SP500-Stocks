"""
engine.py – Backend: data collection, filtering, NLP sentiment analysis.
"""

import os
import json
import time
import datetime as dt
from dataclasses import dataclass, field
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
import warnings
warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

from dotenv import load_dotenv
import yfinance as yf
from groq import Groq

try:
    from newsapi import NewsApiClient
except ImportError:
    NewsApiClient = None

load_dotenv()

# ── Config ────────────────────────────────────────────────────────────────────

GROQ_MODEL = "llama-3.3-70b-versatile"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

SENTIMENT_PROMPT = """You are a senior financial sentiment analyst.
Analyze the following texts about the stock ticker "{ticker}" ({company}).

Return ONLY a JSON object (no markdown, no explanation) with this exact schema:

{{
  "overall_signal": "BULLISH" | "BEARISH" | "NEUTRAL",
  "confidence": <float 0-1>,
  "summary": "<3-4 sentence justification>",
  "key_factors": ["<factor1>", "<factor2>", "<factor3>"],
  "source_breakdown": {{
    "positive_count": <int>,
    "negative_count": <int>,
    "neutral_count": <int>
  }}
}}

TEXTS:
{texts}
"""


# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class TextItem:
    source: str
    title: str
    text: str
    date: str = ""
    url: str = ""


@dataclass
class SentimentResult:
    ticker: str
    signal: str = "NEUTRAL"
    confidence: float = 0.0
    summary: str = ""
    key_factors: list = field(default_factory=list)
    source_breakdown: dict = field(default_factory=dict)
    sources_used: int = 0
    price: float = 0.0
    change_pct: float = 0.0
    company_name: str = ""
    items: list = field(default_factory=list)
    source_counts: dict = field(default_factory=dict)
    # Timing metrics
    total_time: float = 0.0
    collection_time: float = 0.0
    groq_time: float = 0.0
    raw_count: int = 0
    dedup_count: int = 0
    filtered_count: int = 0


# ── Data collectors ───────────────────────────────────────────────────────────

def collect_yfinance(ticker: str) -> list[TextItem]:
    items = []
    try:
        stock = yf.Ticker(ticker)
        news = stock.news or []
        for n in news[:10]:
            title = n.get("title", "")
            publisher = n.get("publisher", "Yahoo Finance")
            ts = n.get("providerPublishTime", 0)
            items.append(TextItem(
                source=f"Yahoo Finance ({publisher})",
                title=title,
                text=title,
                date=dt.datetime.fromtimestamp(ts).strftime("%Y-%m-%d") if ts else "",
                url=n.get("link", ""),
            ))
    except Exception:
        pass
    return items


def _gdelt_request(url: str, max_retries: int = 2) -> dict | None:
    for attempt in range(max_retries):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=20)
            if resp.status_code == 429:
                time.sleep(2 ** attempt + 1)
                continue
            resp.raise_for_status()
            text = resp.text.strip()
            if not text or text.startswith("<!"):
                return None
            return resp.json()
        except Exception:
            if attempt < max_retries - 1:
                time.sleep(2)
                continue
    return None


def collect_gdelt_tone(ticker: str, company_name: str) -> list[TextItem]:
    items = []
    query = f"{company_name} {ticker}"
    url = (
        "https://api.gdeltproject.org/api/v2/doc/doc"
        f"?query={quote_plus(query)}"
        "&mode=TimelineTone&timespan=3d&format=json"
    )
    try:
        data = _gdelt_request(url)
        if not data:
            return items
        timeline = data.get("timeline", [])
        if timeline and timeline[0].get("data"):
            tones = [pt.get("value", 0) for pt in timeline[0]["data"]]
            avg_tone = sum(tones) / len(tones) if tones else 0
            label = "positive" if avg_tone > 0 else "negative"
            items.append(TextItem(
                source="GDELT Tone Index",
                title=f"3-day avg media tone: {avg_tone:.2f} ({label})",
                text=(
                    f"GDELT global media tone for {company_name} over the past 3 days "
                    f"averages {avg_tone:.2f}. Positive = positive coverage, negative = negative. "
                    f"Current trend is {label}."
                ),
                date=dt.datetime.now().strftime("%Y-%m-%d"),
            ))
    except Exception:
        pass
    return items


def scrape_finviz(ticker: str) -> list[TextItem]:
    items = []
    url = f"https://finviz.com/quote.ashx?t={ticker}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        news_table = soup.find("table", {"id": "news-table"})
        if not news_table:
            return items
        rows = news_table.find_all("tr")
        current_date = ""
        for row in rows[:15]:
            cells = row.find_all("td")
            if len(cells) < 2:
                continue
            date_cell = cells[0].text.strip()
            if len(date_cell) > 8:
                current_date = date_cell.split()[0]
            link = cells[1].find("a")
            if link:
                title = link.text.strip()
                items.append(TextItem(
                    source="FinViz",
                    title=title,
                    text=title,
                    date=current_date,
                    url=link.get("href", ""),
                ))
    except Exception:
        pass
    return items


def scrape_marketwatch(ticker: str) -> list[TextItem]:
    items = []
    mw_headers = {
        **HEADERS,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.google.com/",
    }
    try:
        url = f"https://www.marketwatch.com/investing/stock/{ticker.lower()}"
        resp = requests.get(url, headers=mw_headers, timeout=10)
        if resp.status_code in (401, 403):
            url = f"https://www.marketwatch.com/search?q={ticker}&ts=0&tab=All%20News"
            resp = requests.get(url, headers=mw_headers, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        headlines = soup.select(
            "h3.article__headline a, .article__headline a, h3 a.link, div.article__content a"
        )
        for h in headlines[:10]:
            title = h.text.strip()
            if title and len(title) > 15:
                items.append(TextItem(
                    source="MarketWatch",
                    title=title,
                    text=title,
                    url=h.get("href", ""),
                ))
    except Exception:
        pass
    return items


def scrape_google_news(ticker: str, company_name: str) -> list[TextItem]:
    items = []
    query = quote_plus(f"{ticker} stock {company_name}")
    url = f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.content, "html.parser")
        entries = soup.find_all("item")
        for entry in entries[:10]:
            title_el = entry.find("title")
            pub_date_el = entry.find("pubdate")
            source_el = entry.find("source")
            if title_el and title_el.string:
                items.append(TextItem(
                    source=f"Google News ({source_el.string if source_el and source_el.string else 'Unknown'})",
                    title=title_el.string.strip(),
                    text=title_el.string.strip(),
                    date=pub_date_el.string.strip()[:16] if pub_date_el and pub_date_el.string else "",
                ))
    except Exception:
        pass
    return items


def collect_newsapi(ticker: str, company_name: str) -> list[TextItem]:
    key = os.getenv("NEWSAPI_KEY")
    if not key or not NewsApiClient:
        return []
    items = []
    try:
        api = NewsApiClient(api_key=key)
        query = f'"{company_name}" OR "{ticker} stock"'
        from_date = (dt.datetime.now() - dt.timedelta(days=90)).strftime("%Y-%m-%d")
        resp = api.get_everything(
            q=query, language="en", sort_by="relevancy",
            from_param=from_date, page_size=10,
        )
        for a in resp.get("articles", []):
            title = a.get("title", "")
            desc = a.get("description", "") or ""
            items.append(TextItem(
                source=f"NewsAPI ({a.get('source', {}).get('name', '')})",
                title=title,
                text=f"{title}. {desc}",
                date=a.get("publishedAt", "")[:10],
            ))
    except Exception:
        pass
    return items


# ── Processing ────────────────────────────────────────────────────────────────

def deduplicate(items: list[TextItem]) -> list[TextItem]:
    seen = set()
    unique = []
    for item in items:
        key = item.title.lower().strip()[:80]
        if key and key not in seen:
            seen.add(key)
            unique.append(item)
    return unique


def filter_relevant(items: list[TextItem], ticker: str, company_name: str) -> list[TextItem]:
    keywords = {ticker.lower()}
    skip = {"inc", "inc.", "corp", "corp.", "co", "co.", "the", "company", "ltd", "plc", "group"}
    for word in company_name.split():
        w = word.lower().strip(".,")
        if w not in skip and len(w) > 1:
            keywords.add(w)
    relevant = []
    for item in items:
        text = f"{item.title} {item.text}".lower()
        if any(kw in text for kw in keywords):
            relevant.append(item)
    return relevant


def filter_by_date(items: list[TextItem], max_days: int = 90) -> list[TextItem]:
    """Keep only items from the last max_days (default 3 months)."""
    from dateutil import parser as dateparser
    cutoff = dt.datetime.now() - dt.timedelta(days=max_days)
    filtered = []
    for item in items:
        if not item.date:
            filtered.append(item)  # keep items with no date (e.g. GDELT tone)
            continue
        try:
            parsed = dateparser.parse(item.date, fuzzy=True)
            if parsed and parsed.replace(tzinfo=None) >= cutoff:
                filtered.append(item)
        except Exception:
            filtered.append(item)  # keep if unparseable
    return filtered


# ── NLP Analysis ──────────────────────────────────────────────────────────────

def analyze_sentiment(ticker: str, company: str, items: list[TextItem]) -> SentimentResult:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return SentimentResult(ticker=ticker, summary="GROQ_API_KEY not set in .env")

    texts_block = "\n---\n".join(
        f"[{i.source} | {i.date}] {i.text}" for i in items
    )

    client = Groq(api_key=api_key)
    prompt = SENTIMENT_PROMPT.format(ticker=ticker, company=company, texts=texts_block)

    try:
        resp = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=800,
        )
        raw = resp.choices[0].message.content.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]
        data = json.loads(raw)
        return SentimentResult(
            ticker=ticker,
            signal=data.get("overall_signal", "NEUTRAL"),
            confidence=data.get("confidence", 0),
            summary=data.get("summary", ""),
            key_factors=data.get("key_factors", []),
            source_breakdown=data.get("source_breakdown", {}),
            sources_used=len(items),
        )
    except Exception as e:
        return SentimentResult(ticker=ticker, summary=f"Analysis error: {e}")


# ── Price ─────────────────────────────────────────────────────────────────────

def get_price_info(ticker: str) -> tuple[float, float, str]:
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        price = info.get("currentPrice") or info.get("regularMarketPrice", 0)
        prev = info.get("previousClose") or info.get("regularMarketPreviousClose", 0)
        change = ((price - prev) / prev * 100) if prev else 0
        name = info.get("shortName", ticker)
        return price, change, name
    except Exception:
        return 0.0, 0.0, ticker


def get_price_history(ticker: str, period: str = "1mo") -> list[dict]:
    """Get OHLCV price history for charting."""
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period=period)
        records = []
        for date, row in hist.iterrows():
            records.append({
                "date": date.strftime("%Y-%m-%d"),
                "close": round(row["Close"], 2),
                "volume": int(row["Volume"]),
            })
        return records
    except Exception:
        return []


# ── Orchestrator ──────────────────────────────────────────────────────────────

def run_analysis(ticker: str, progress_callback=None) -> SentimentResult:
    """
    Full pipeline: collect → deduplicate → filter → analyze.
    progress_callback(source_name, count) is called after each source.
    """
    ticker = ticker.upper().strip()
    t_start = time.time()

    # Price
    if progress_callback:
        progress_callback("Price data", 0)
    price, change, company_name = get_price_info(ticker)

    # Collectors
    collectors = [
        ("Yahoo Finance",   lambda: collect_yfinance(ticker)),
        ("GDELT Tone",      lambda: collect_gdelt_tone(ticker, company_name)),
        ("FinViz",          lambda: scrape_finviz(ticker)),
        ("MarketWatch",     lambda: scrape_marketwatch(ticker)),
        ("Google News",     lambda: scrape_google_news(ticker, company_name)),
        ("NewsAPI",         lambda: collect_newsapi(ticker, company_name)),
    ]

    all_items: list[TextItem] = []
    source_counts = {}

    t_collect_start = time.time()
    for name, fn in collectors:
        items = fn()
        all_items.extend(items)
        source_counts[name] = len(items)
        if progress_callback:
            progress_callback(name, len(items))
        time.sleep(0.2)
    t_collect_end = time.time()

    raw_count = len(all_items)

    # Process
    all_items = deduplicate(all_items)
    dedup_count = len(all_items)
    all_items = filter_relevant(all_items, ticker, company_name)
    all_items = filter_by_date(all_items, max_days=90)
    filtered_count = len(all_items)

    if not all_items:
        return SentimentResult(
            ticker=ticker, price=price, change_pct=change,
            company_name=company_name, summary="No relevant data found.",
            source_counts=source_counts,
            total_time=time.time() - t_start,
            collection_time=t_collect_end - t_collect_start,
            raw_count=raw_count, dedup_count=dedup_count, filtered_count=filtered_count,
        )

    # Analyze
    if progress_callback:
        progress_callback("AI Analysis", 0)
    t_groq_start = time.time()
    result = analyze_sentiment(ticker, company_name, all_items)
    t_groq_end = time.time()

    result.price = price
    result.change_pct = change
    result.company_name = company_name
    result.items = all_items
    result.source_counts = source_counts
    result.total_time = time.time() - t_start
    result.collection_time = t_collect_end - t_collect_start
    result.groq_time = t_groq_end - t_groq_start
    result.raw_count = raw_count
    result.dedup_count = dedup_count
    result.filtered_count = filtered_count
    return result