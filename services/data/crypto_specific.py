import math
from typing import Dict, Optional

import requests


class CryptoSpecificFetcher:
    BINANCE_FUTURES_FUNDING = "https://fapi.binance.com/fapi/v1/fundingRate"
    BINANCE_FUTURES_OI = "https://fapi.binance.com/fapi/v1/openInterest"

    @staticmethod
    def normalize_symbol(symbol: str) -> str:
        symbol = symbol.upper().replace("/", "")
        if symbol.endswith("USD"):
            symbol = symbol.replace("USD", "USDT")
        return symbol

    def fetch_funding_rate(self, symbol: str, limit: int = 7) -> Dict[str, Optional[float]]:
        normalized = self.normalize_symbol(symbol)
        params = {"symbol": normalized, "limit": limit}
        resp = requests.get(self.BINANCE_FUTURES_FUNDING, params=params, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        if not isinstance(data, list):
            raise RuntimeError("Unexpected funding rate response")
        history = [
            {
                "funding_time": item.get("fundingTime"),
                "funding_rate": float(item.get("fundingRate", 0.0)),
            }
            for item in data
        ]
        current = history[-1]["funding_rate"] if history else None
        return {"current": current, "history": history}

    def fetch_open_interest(self, symbol: str) -> Dict[str, Optional[float]]:
        normalized = self.normalize_symbol(symbol)
        params = {"symbol": normalized}
        resp = requests.get(self.BINANCE_FUTURES_OI, params=params, timeout=20)
        resp.raise_for_status()
        payload = resp.json()
        oi = float(payload.get("openInterest", 0.0))
        return {"open_interest": oi, "open_interest_change_pct": None}
