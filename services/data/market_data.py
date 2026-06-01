import datetime
from typing import Dict, List, Optional

import ccxt
import pandas as pd
import yfinance as yf


class MarketDataFetcher:
    TIMEFRAME_MAP = {
        "5m": "5m",
        "1H": "1h",
        "4H": "4h",
        "1D": "1d",
        "1W": "1wk",
    }

    def __init__(self):
        self._exchange = ccxt.binance({"enableRateLimit": True})

    @staticmethod
    def normalize_symbol(asset: str, asset_class: str) -> str:
        asset = asset.strip().upper()
        if asset_class == "CRYPTO":
            return asset.replace("/USD", "/USDT").replace("USD", "/USDT")
        if asset_class == "FOREX":
            return asset.replace("/", "") + "=X"
        return asset

    @staticmethod
    def normalize_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
        result = df.copy()
        result = result.rename(columns={
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume",
        })
        if "Adj Close" in result.columns:
            result = result.drop(columns=["Adj Close"])
        result = result["open high low close volume" .split()]
        result.index = pd.to_datetime(result.index, utc=True)
        result = result.reset_index().rename(columns={"index": "timestamp"})
        return result

    def fetch_crypto_ohlcv(self, symbol: str, timeframe: str, limit: int = 500) -> pd.DataFrame:
        binance_symbol = self.normalize_symbol(symbol, "CRYPTO").replace("/", "")
        if timeframe not in self.TIMEFRAME_MAP:
            raise ValueError(f"Unsupported timeframe: {timeframe}")
        exchange_tf = self.TIMEFRAME_MAP[timeframe]
        bars = self._exchange.fetch_ohlcv(binance_symbol, timeframe=exchange_tf, limit=limit)
        frame = pd.DataFrame(bars, columns=["timestamp", "open", "high", "low", "close", "volume"])
        frame["timestamp"] = pd.to_datetime(frame["timestamp"], unit="ms", utc=True)
        return frame

    def fetch_equity_ohlcv(self, symbol: str, timeframe: str, period: str = "1y") -> pd.DataFrame:
        yf_symbol = self.normalize_symbol(symbol, "EQUITY")
        interval = self.TIMEFRAME_MAP.get(timeframe, "1d")
        raw = yf.download(yf_symbol, period=period, interval=interval, progress=False, threads=False)
        if raw.empty:
            raise RuntimeError(f"yfinance returned no data for {yf_symbol} {interval}")
        return self.normalize_ohlcv(raw)

    def fetch_forex_ohlcv(self, symbol: str, timeframe: str, period: str = "1y") -> pd.DataFrame:
        yf_symbol = self.normalize_symbol(symbol, "FOREX")
        interval = self.TIMEFRAME_MAP.get(timeframe, "1H")
        raw = yf.download(yf_symbol, period=period, interval=interval, progress=False, threads=False)
        if raw.empty:
            raise RuntimeError(f"yfinance returned no data for {yf_symbol} {interval}")
        return self.normalize_ohlcv(raw)

    def fetch_market_data(self, asset: str, asset_class: str, timeframes: Optional[List[str]] = None) -> Dict[str, pd.DataFrame]:
        if timeframes is None:
            timeframes = ["5m", "1H", "4H", "1D", "1W"]
        results: Dict[str, pd.DataFrame] = {}
        for timeframe in timeframes:
            if asset_class == "CRYPTO":
                results[timeframe] = self.fetch_crypto_ohlcv(asset, timeframe)
            elif asset_class == "EQUITY":
                results[timeframe] = self.fetch_equity_ohlcv(asset, timeframe)
            elif asset_class == "FOREX":
                results[timeframe] = self.fetch_forex_ohlcv(asset, timeframe)
            else:
                raise ValueError(f"Unsupported asset class: {asset_class}")
        return results
