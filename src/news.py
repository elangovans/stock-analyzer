import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

import yfinance as yf

NEWS_CACHE_PATH = Path.cwd() / "cache" / "news.json"
NEWS_CACHE_TTL_HOURS = 6  # news is time-sensitive, shorter TTL


@dataclass
class NewsItem:
    ticker: str
    title: str
    publisher: str
    url: str
    published_at: Optional[datetime]
    category: str        # Leadership | M&A | Regulatory | Financial | Legal | Product
    summary: str         # 1-sentence Claude summary
    stars: int           # 1–5
    classification: str  # noise | routine | notable | high-stake


def _api_key() -> Optional[str]:
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    return key if key else None


def is_enabled() -> bool:
    return _api_key() is not None


def _read_news_cache() -> dict:
    if not NEWS_CACHE_PATH.exists():
        return {}
    try:
        data = json.loads(NEWS_CACHE_PATH.read_text())
        cached_at = datetime.fromisoformat(data.get("cached_at", "2000-01-01"))
        if datetime.now() - cached_at > timedelta(hours=NEWS_CACHE_TTL_HOURS):
            return {}
        return data.get("items", {})
    except Exception:
        return {}


def _write_news_cache(items: dict) -> None:
    NEWS_CACHE_PATH.parent.mkdir(exist_ok=True)
    NEWS_CACHE_PATH.write_text(json.dumps({
        "cached_at": datetime.now().isoformat(),
        "items": items,
    }, indent=2))


def _fetch_raw_headlines(tickers: List[str]) -> dict[str, list]:
    """Return {ticker: [{"title": ..., "publisher": ..., "link": ..., "providerPublishTime": ...}]}."""
    results: dict[str, list] = {}
    for t in tickers:
        print(f"      {t}...", end=" ", flush=True)
        try:
            news = yf.Ticker(t).news or []
            items = [
                {
                    "title": n.get("content", {}).get("title") or n.get("title", ""),
                    "publisher": (
                        n.get("content", {}).get("provider", {}).get("displayName")
                        or n.get("publisher", "")
                    ),
                    "link": (
                        n.get("content", {}).get("canonicalUrl", {}).get("url")
                        or n.get("link", "")
                    ),
                    "publishedAt": (
                        n.get("content", {}).get("pubDate")
                        or n.get("providerPublishTime", "")
                    ),
                }
                for n in news[:8]
                if (n.get("content", {}).get("title") or n.get("title", ""))
            ]
            results[t] = items
            print(f"{len(items)} article(s)")
        except Exception:
            results[t] = []
            print("no news")
    return results


BATCH_SIZE = 20  # articles per Claude call — keeps response well under token limit

CLASSIFY_PROMPT = """You are a financial news analyst. Classify each article for a retail investor tracking their stock portfolio.

For each article return a JSON object with:
- "id": the article id (integer, unchanged)
- "classification": one of "noise" | "routine" | "notable" | "high-stake"
- "category": one of "Leadership" | "M&A" | "Regulatory" | "Financial" | "Legal" | "Product" | "Other"
- "stars": integer 1-5 (1=noise, 2=routine, 3=notable, 4=high-stake, 5=market-moving critical)
- "summary": one sentence max 20 words explaining why it matters. Empty string if classification is "noise".

Classification guide:
- noise: price movements, analyst upgrades without new info, generic market wrap-ups
- routine: minor product updates, conference appearances, small partnerships
- notable: earnings beat/miss, meaningful product launches, regulatory approvals, notable hires
- high-stake: CEO/CFO departure, merger/acquisition, SEC investigation, major recall, bankruptcy risk, major lawsuit
- 5-star only for: CEO resignation, acquisition announcement, bankruptcy filing, major fraud/SEC action

Return ONLY a JSON array, no explanation, no markdown.

Articles:
"""


def _call_claude(articles: list) -> list:
    import anthropic
    client = anthropic.Anthropic(api_key=_api_key())
    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=8096,
        messages=[{"role": "user", "content": CLASSIFY_PROMPT + json.dumps(articles)}],
    )
    text = message.content[0].text.strip()
    if text.startswith("```"):
        text = "\n".join(text.split("\n")[1:])
    if text.endswith("```"):
        text = text.rsplit("```", 1)[0]
    return json.loads(text.strip())


def _classify_with_claude(raw: dict[str, list]) -> List[dict]:
    """Classify all headlines in batches, return merged list of classified dicts."""
    articles = []
    idx = 0
    for ticker, items in raw.items():
        for item in items:
            articles.append({
                "id": idx,
                "ticker": ticker,
                "title": item["title"],
                "publisher": item["publisher"],
                "link": item["link"],
                "publishedAt": str(item["publishedAt"]),
            })
            idx += 1

    if not articles:
        return []

    total_batches = (len(articles) + BATCH_SIZE - 1) // BATCH_SIZE
    print(f"      Classifying {len(articles)} article(s) in {total_batches} batch(es) via Claude...")
    results = []
    for i in range(0, len(articles), BATCH_SIZE):
        batch = articles[i: i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        print(f"      Batch {batch_num}/{total_batches}...", end=" ", flush=True)
        results.extend(_call_claude(batch))
        print("done")
    return results


def fetch_news(tickers: List[str]) -> List[NewsItem]:
    """
    Fetch and classify news for the given tickers.
    Returns only notable/high-stake items sorted by stars desc.
    Returns [] if ANTHROPIC_API_KEY is not set.
    """
    if not is_enabled():
        return []

    cached = _read_news_cache()
    cache_key = ",".join(sorted(tickers))

    if cache_key in cached:
        print(f"      Using cached news (expires in {NEWS_CACHE_TTL_HOURS}h)")
        raw_items = cached[cache_key]
    else:
        print(f"      Fetching headlines for {len(tickers)} ticker(s):")
        raw_headlines = _fetch_raw_headlines(tickers)
        classified = _classify_with_claude(raw_headlines)

        # Build a lookup: id → classification result
        classified_map = {c["id"]: c for c in classified}

        # Merge classification back into raw articles
        raw_items = []
        idx = 0
        for ticker, items in raw_headlines.items():
            for item in items:
                cl = classified_map.get(idx, {})
                raw_items.append({
                    "ticker": ticker,
                    "title": item["title"],
                    "publisher": item["publisher"],
                    "link": item["link"],
                    "publishedAt": str(item["publishedAt"]),
                    "classification": cl.get("classification", "noise"),
                    "category": cl.get("category", "Other"),
                    "stars": cl.get("stars", 1),
                    "summary": cl.get("summary", ""),
                })
                idx += 1

        cached[cache_key] = raw_items
        _write_news_cache(cached)

    # Filter out noise and routine, convert to NewsItems
    news_items = []
    for item in raw_items:
        if item.get("classification") in ("noise", "routine"):
            continue
        published_at = None
        raw_ts = item.get("publishedAt", "")
        try:
            if raw_ts and raw_ts.isdigit():
                published_at = datetime.fromtimestamp(int(raw_ts))
            elif raw_ts:
                published_at = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
        except Exception:
            pass

        news_items.append(NewsItem(
            ticker=item["ticker"],
            title=item["title"],
            publisher=item["publisher"],
            url=item["link"],
            published_at=published_at,
            category=item["category"],
            summary=item["summary"],
            stars=item["stars"],
            classification=item["classification"],
        ))

    news_items.sort(key=lambda x: x.stars, reverse=True)
    return news_items
