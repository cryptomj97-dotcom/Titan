import asyncio
import datetime
from typing import Dict, List, Optional

from .cache import RedisCache
from .crypto_specific import CryptoSpecificFetcher
from .data_quality_gate import DataQualityGate
from .macro_data import MacroDataFetcher
from .market_data import MarketDataFetcher
from .news_data import NewsFetcher
from .schemas import DataPacket, MacroSnapshot, CryptoSpecificMetrics, NewsArticle
from .sentiment import SocialSentiment

FETCH_TIMEOUT = 60  # seconds


class DataPacketBuilder:
    def __init__(self, cache_url: str = "redis://localhost:6379/0"):
        self.market_data = MarketDataFetcher()
        self.news_fetcher = NewsFetcher()
        self.sentiment = SocialSentiment()
        self.crypto_fetcher = CryptoSpecificFetcher()
        self.macro_fetcher = MacroDataFetcher()
        self.cache = RedisCache(cache_url)

    async def _build_ohlcv(self, asset: str, asset_class: str, timeframes: Optional[List[str]] = None):
        if timeframes is None:
            timeframes = ["5m", "1H", "4H", "1D", "1W"]
        results = {}
        for timeframe in timeframes:
            cache_key = f"ohlcv:{asset_class}:{asset}:{timeframe}"
            try:
                ohlcv_data = await asyncio.wait_for(
                    self.cache.fetch_with_cache(
                        cache_key,
                        30,
                        self.market_data.fetch_market_data,
                        asset,
                        asset_class,
                        [timeframe],
                    ),
                    timeout=FETCH_TIMEOUT,
                )
                df = ohlcv_data[timeframe]
                results[timeframe] = df.to_dict(orient="records")
            except asyncio.TimeoutError:
                raise RuntimeError(f"Timeout fetching {timeframe} OHLCV for {asset}")
            except Exception as exc:
                raise RuntimeError(f"Failed to fetch {timeframe} OHLCV: {exc}")
        return results

    async def _build_news(self, asset: str):
        cache_key = f"news:{asset}"
        try:
            news = await asyncio.wait_for(
                self.cache.fetch_with_cache(cache_key, 15 * 60, self.news_fetcher.fetch, asset),
                timeout=FETCH_TIMEOUT,
            )
            return news
        except asyncio.TimeoutError:
            raise RuntimeError(f"Timeout fetching news for {asset}")
        except Exception as exc:
            raise RuntimeError(f"Failed to fetch news: {exc}")

    async def _build_social(self, asset: str):
        symbol = asset.split("/")[0]
        subreddit = {
            "BTC": "Bitcoin",
            "ETH": "ethereum",
            "AAPL": "stocks",
        }.get(symbol.upper(), "CryptoCurrency")
        cache_key = f"social:{asset}:{subreddit}"
        try:
            result = await asyncio.wait_for(
                self.cache.fetch_with_cache(cache_key, 5 * 60, self.sentiment.fetch_reddit_sentiment, subreddit, asset),
                timeout=FETCH_TIMEOUT,
            )
            return result
        except asyncio.TimeoutError:
            return None
        except Exception as exc:
            return None

    async def _build_crypto_specific(self, asset: str):
        cache_key = f"crypto_metrics:{asset}"
        try:
            result = await asyncio.wait_for(
                self.cache.fetch_with_cache(cache_key, 60 * 60, self._fetch_crypto_metrics, asset),
                timeout=FETCH_TIMEOUT,
            )
            return CryptoSpecificMetrics(**result)
        except asyncio.TimeoutError:
            return None
        except Exception as exc:
            return None

    def _fetch_crypto_metrics(self, asset: str) -> Dict:
        try:
            funding = self.crypto_fetcher.fetch_funding_rate(asset)
            oi = self.crypto_fetcher.fetch_open_interest(asset)
        except Exception:
            return {"symbol": asset, "funding_rate": None, "funding_history": None, "open_interest": None, "open_interest_change_pct": None}
        
        return {
            "symbol": asset,
            "funding_rate": funding.get("current"),
            "funding_history": funding.get("history"),
            "open_interest": oi.get("open_interest"),
            "open_interest_change_pct": oi.get("open_interest_change_pct"),
        }

    async def _build_macro(self):
        cache_key = "macro_snapshot"
        try:
            result = await asyncio.wait_for(
                self.cache.fetch_with_cache(cache_key, 60 * 60, self.macro_fetcher.fetch),
                timeout=FETCH_TIMEOUT,
            )
            return MacroSnapshot(**result)
        except asyncio.TimeoutError:
            return MacroSnapshot()
        except Exception:
            return MacroSnapshot()

    async def build(self, asset: str, asset_class: str, timeframes: Optional[List[str]] = None) -> DataPacket:
        assembled_at = datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc).isoformat()
        ohlcv_task = asyncio.create_task(self._build_ohlcv(asset, asset_class, timeframes))
        news_task = asyncio.create_task(self._build_news(asset))
        macro_task = asyncio.create_task(self._build_macro())
        social_task = asyncio.create_task(self._build_social(asset)) if asset_class == "CRYPTO" else None
        crypto_task = asyncio.create_task(self._build_crypto_specific(asset)) if asset_class == "CRYPTO" else None

        ohlcv = await ohlcv_task
        news = await news_task
        macro = await macro_task
        social_sentiment = await social_task if social_task is not None else None
        crypto_metrics = await crypto_task if crypto_task is not None else None

        quality_report = {}
        try:
            quality_report = DataQualityGate.validate({
                "ohlcv": ohlcv,
                "news": news,
            })
        except Exception as exc:
            quality_report = {"passed": False, "details": [str(exc)]}

        return DataPacket(
            asset=asset,
            asset_class=asset_class,
            ohlcv=ohlcv,
            news=[NewsArticle(**article.dict()) for article in news],
            social_sentiment=social_sentiment,
            crypto_metrics=crypto_metrics,
            macro=macro,
            quality_report=quality_report,
            assembled_at=assembled_at,
        )
