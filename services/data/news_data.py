import datetime
import re
from typing import Dict, List, Optional

import feedparser
from nltk import download as nltk_download
from nltk.sentiment.vader import SentimentIntensityAnalyzer

from .schemas import NewsArticle


def _ensure_vader():
    try:
        return SentimentIntensityAnalyzer()
    except LookupError:
        nltk_download("vader_lexicon")
        return SentimentIntensityAnalyzer()


class NewsFetcher:
    RSS_SOURCES = {
        "CoinDesk": "https://www.coindesk.com/arc/outboundfeeds/rss/",
        "Cointelegraph": "https://cointelegraph.com/rss",
        "Reuters Business News": "https://www.reutersagency.com/feed/?best-topics=business-finance&post_type=best",
    }

    def __init__(self):
        self._analyzer = _ensure_vader()

    @staticmethod
    def _normalize_title(value: str) -> str:
        return re.sub(r"\s+", " ", value or "").strip()

    @staticmethod
    def _matches_keywords(text: str, symbol: str) -> bool:
        normalized = text.lower()
        symbol = symbol.lower().replace("/", " ").replace("usd", "usd")
        return symbol in normalized or any(token in normalized for token in symbol.split())

    def _score_headline(self, title: str) -> float:
        score = self._analyzer.polarity_scores(title)["compound"]
        return float(max(min(score, 1.0), -1.0))

    def fetch(self, asset: str, limit: int = 40) -> List[NewsArticle]:
        articles: List[NewsArticle] = []
        for name, url in self.RSS_SOURCES.items():
            feed = feedparser.parse(url)
            for entry in feed.entries[: limit]:
                title = self._normalize_title(entry.get("title", ""))
                summary = self._normalize_title(entry.get("summary", entry.get("description", "")))
                if not title:
                    continue
                if asset and not self._matches_keywords(title + " " + summary, asset):
                    continue
                sentiment = self._score_headline(title)
                published = entry.get("published", entry.get("updated", ""))
                published_at = published or datetime.datetime.utcnow().isoformat()
                articles.append(
                    NewsArticle(
                        source=name,
                        title=title,
                        link=entry.get("link", ""),
                        published_at=published_at,
                        sentiment=sentiment,
                        summary=summary,
                    )
                )
                if len(articles) >= limit:
                    break
            if len(articles) >= limit:
                break
        return articles
