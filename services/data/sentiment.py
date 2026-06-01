import os
import time
from typing import Dict, List, Optional

import praw
from nltk import download as nltk_download
from nltk.sentiment.vader import SentimentIntensityAnalyzer

from .schemas import SocialSentimentResult


def _ensure_vader():
    try:
        return SentimentIntensityAnalyzer()
    except LookupError:
        nltk_download("vader_lexicon")
        return SentimentIntensityAnalyzer()


class SocialSentiment:
    def __init__(self):
        self._analyzer = _ensure_vader()
        self._reddit = None
        self._client_id = os.getenv("REDDIT_CLIENT_ID")
        self._client_secret = os.getenv("REDDIT_CLIENT_SECRET")
        self._user_agent = os.getenv("REDDIT_USER_AGENT", "titan-social-sentiment/0.1")
        if self._client_id and self._client_secret:
            self._reddit = praw.Reddit(
                client_id=self._client_id,
                client_secret=self._client_secret,
                user_agent=self._user_agent,
            )

    def _score_text(self, text: str) -> float:
        return float(self._analyzer.polarity_scores(text).get("compound", 0.0))

    def _normalize_score(self, value: float) -> float:
        return max(min(value, 1.0), -1.0)

    def _score_post(self, title: str, comments: List[str]) -> float:
        scores = [self._score_text(title)]
        scores.extend(self._score_text(comment) for comment in comments if comment)
        if not scores:
            return 0.0
        return self._normalize_score(sum(scores) / len(scores))

    def fetch_reddit_sentiment(self, subreddit: str, symbol: str, limit: int = 30) -> SocialSentimentResult:
        if not self._reddit:
            return SocialSentimentResult(
                source="reddit",
                symbol=symbol,
                composite_score=0.0,
                bullish_pct=0.0,
                bearish_pct=0.0,
                neutral_pct=1.0,
                mention_count=0,
            )

        posts = []
        cutoff = time.time() - 6 * 3600
        for submission in self._reddit.subreddit(subreddit).new(limit=limit):
            if submission.created_utc < cutoff:
                continue
            comments = []
            submission.comments.replace_more(limit=0)
            for comment in submission.comments.list()[:5]:
                comments.append(getattr(comment, "body", ""))
            score = self._score_post(submission.title, comments)
            posts.append(score)

        mention_count = len(posts)
        if mention_count == 0:
            return SocialSentimentResult(
                source="reddit",
                symbol=symbol,
                composite_score=0.0,
                bullish_pct=0.0,
                bearish_pct=0.0,
                neutral_pct=1.0,
                mention_count=0,
            )

        bullish = sum(1 for score in posts if score > 0.1)
        bearish = sum(1 for score in posts if score < -0.1)
        neutral = mention_count - bullish - bearish
        return SocialSentimentResult(
            source="reddit",
            symbol=symbol,
            composite_score=float(sum(posts) / mention_count),
            bullish_pct=float(bullish / mention_count),
            bearish_pct=float(bearish / mention_count),
            neutral_pct=float(neutral / mention_count),
            mention_count=mention_count,
        )
