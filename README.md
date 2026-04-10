# 📈 Stock Sentiment Analyzer – MVP

NLP-powered bullish/bearish signal from multi-source financial news.  
Built with Streamlit + Groq (Llama 3.3).
Make sure to input your API keys in the env.example 

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![Streamlit](https://img.shields.io/badge/Streamlit-1.32+-red)
![License](https://img.shields.io/badge/License-Academic-green)

## Quick Start (PyCharm)

```bash
# 1. Open this folder as a PyCharm project

# 2. Create virtual environment
python -m venv venv

# 3. Activate it
# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

# 4. Install dependencies
pip install -r requirements.txt

# 5. Set up API key
copy env.example .env
# Edit .env and paste your Groq key

# 6. Run the app
streamlit run app.py
```

The app opens at http://localhost:8501

## API Keys

| Service | Required? | Free Tier | Link |
|---------|-----------|-----------|------|
| **Groq** | ✅ Yes | 30 req/min | https://console.groq.com/keys |
| **NewsAPI** | Optional | 100 req/day | https://newsapi.org/register |

**No key needed for:** Yahoo Finance, GDELT Tone, FinViz, MarketWatch, Google News

## Project Structure

```
stock_sentiment/
├── app.py              ← Streamlit UI (run this)
├── engine.py           ← Backend: collectors, NLP, processing
├── requirements.txt
├── .env.example
└── README.md
```

## Architecture

```
┌──────────────────────────────────────────────────────┐
│                    STREAMLIT UI                       │
│   Ticker Input → Progress Bar → Signal + Charts      │
└──────────────────────┬───────────────────────────────┘
                       │
┌──────────────────────▼───────────────────────────────┐
│                  ENGINE (engine.py)                    │
│                                                       │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────┐ │
│  │   Collect    │→ │  Deduplicate │→ │   Filter    │ │
│  │  6 sources   │  │  + clean     │  │  relevant   │ │
│  └─────────────┘  └──────────────┘  └──────┬──────┘ │
│                                             │        │
│                                    ┌────────▼──────┐ │
│                                    │  Groq API     │ │
│                                    │  Llama 3.3    │ │
│                                    │  Sentiment    │ │
│                                    └────────┬──────┘ │
│                                             │        │
│                                    ┌────────▼──────┐ │
│                                    │ BULLISH /     │ │
│                                    │ BEARISH /     │ │
│                                    │ NEUTRAL       │ │
│                                    └───────────────┘ │
└──────────────────────────────────────────────────────┘

Data Sources:
  • Yahoo Finance (headlines, no key)
  • GDELT Tone Index (media sentiment, no key)
  • FinViz (web scrape)
  • MarketWatch (web scrape)
  • Google News RSS (no key)
  • NewsAPI (optional, free tier)
```

## NLP Techniques Used

1. **Multi-source data aggregation** – 6 heterogeneous sources
2. **Web scraping** – BeautifulSoup on FinViz + MarketWatch
3. **Text deduplication** – near-duplicate headline removal
4. **Relevance filtering** – keyword-based noise removal
5. **LLM sentiment classification** – Llama 3.3 via Groq with structured JSON output
6. **GDELT tone analysis** – quantitative media tone scoring

## IE University – NLP Group Project
