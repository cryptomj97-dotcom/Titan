import datetime
import os
from typing import Dict, Optional

import requests


class MacroDataFetcher:
    FRED_BASE = "https://api.stlouisfed.org/fred/series/observations"
    FOMC_DATES = [
        "2026-06-24",
        "2026-08-05",
        "2026-09-16",
        "2026-11-05",
        "2027-01-28",
        "2027-03-17",
    ]

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("FRED_API_KEY")

    def _fetch_series(self, series_id: str) -> Optional[float]:
        if not self.api_key:
            return None
        params = {
            "series_id": series_id,
            "api_key": self.api_key,
            "file_type": "json",
            "limit": 1,
        }
        resp = requests.get(self.FRED_BASE, params=params, timeout=20)
        resp.raise_for_status()
        payload = resp.json()
        observations = payload.get("observations", [])
        if not observations:
            return None
        return float(observations[-1].get("value", "nan"))

    def _next_fomc(self) -> Dict[str, Optional[str]]:
        now = datetime.datetime.utcnow().date()
        next_dates = [datetime.datetime.fromisoformat(date).date() for date in self.FOMC_DATES]
        future = [date for date in next_dates if date >= now]
        if not future:
            return {"next_fomc_date": None, "days_to_fomc": None}
        next_date = min(future)
        return {
            "next_fomc_date": next_date.isoformat(),
            "days_to_fomc": (next_date - now).days,
        }

    def fetch(self) -> Dict[str, Optional[float]]:
        fed_rate = self._fetch_series("FEDFUNDS")
        treasury_10y = self._fetch_series("DGS10")
        fomc = self._next_fomc()
        return {
            "fed_rate": fed_rate,
            "treasury_10y": treasury_10y,
            "next_fomc_date": fomc["next_fomc_date"],
            "days_to_fomc": fomc["days_to_fomc"],
        }
