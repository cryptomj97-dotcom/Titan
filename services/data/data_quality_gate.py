import pandas as pd
from typing import Dict, Any


class DataQualityError(ValueError):
    def __init__(self, message: str, report: Dict[str, Any]):
        super().__init__(message)
        self.report = report


class DataQualityGate:
    MIN_CANDLES = 200
    MAX_NULL_RATIO = 0.02
    FRESHNESS_SECONDS = 300
    MAX_ZSCORE = 6.0
    MAX_GAP_BARS = 5

    @staticmethod
    def _compute_zscores(records: list) -> float:
        if not records:
            return 0.0
        closes = [r.get("close") for r in records if r.get("close") is not None]
        if len(closes) < 2:
            return 0.0
        values = pd.Series(closes, dtype=float)
        return float((values - values.mean()).abs().div(values.std(ddof=0)).max())

    @staticmethod
    def _max_gap(records: list, timeframe: str) -> int:
        if len(records) < 2:
            return 0
        timestamps = [r.get("timestamp") for r in records if r.get("timestamp") is not None]
        if len(timestamps) < 2:
            return 0
        timestamps = pd.to_datetime(timestamps, utc=True).sort_values()
        diffs = pd.Series(timestamps).diff().dt.total_seconds().dropna()
        expected = {
            "5m": 5 * 60,
            "1H": 60 * 60,
            "4H": 4 * 60 * 60,
            "1D": 24 * 60 * 60,
            "1W": 7 * 24 * 60 * 60,
        }.get(timeframe, 60 * 60)
        gaps = ((diffs / expected) - 1).clip(lower=0).round().astype(int)
        return int(gaps.max()) if not gaps.empty else 0

    @classmethod
    def validate(cls, packet: Dict[str, Any]) -> Dict[str, Any]:
        report: Dict[str, Any] = {"passed": True, "details": []}
        ohlcv = packet.get("ohlcv", {})
        if not isinstance(ohlcv, dict) or len(ohlcv) < 3:
            report["passed"] = False
            report["details"].append("At least three timeframes are required.")

        for timeframe, data in ohlcv.items():
            if hasattr(data, "to_dict"):
                records = data.to_dict(orient="records")
            elif isinstance(data, list):
                records = data
            else:
                records = []
            
            if not records:
                report["passed"] = False
                report["details"].append(f"{timeframe} has no data.")
                continue

            if len(records) < cls.MIN_CANDLES:
                report["passed"] = False
                report["details"].append(f"{timeframe} has fewer than {cls.MIN_CANDLES} candles.")
            
            null_count = sum(1 for r in records if any(v is None for v in r.values()))
            null_ratio = null_count / len(records) if records else 0
            if null_ratio > cls.MAX_NULL_RATIO:
                report["passed"] = False
                report["details"].append(f"{timeframe} has too many null values ({null_ratio:.2%}).")
            
            zscore = cls._compute_zscores(records)
            if zscore > cls.MAX_ZSCORE:
                report["passed"] = False
                report["details"].append(f"{timeframe} has an extreme z-score of {zscore:.2f}.")
            
            gap = cls._max_gap(records, timeframe)
            if gap > cls.MAX_GAP_BARS:
                report["passed"] = False
                report["details"].append(f"{timeframe} has a gap of {gap} missing bars.")

        if not packet.get("news"):
            report["passed"] = False
            report["details"].append("No news articles were returned.")

        if not report["passed"]:
            raise DataQualityError("Data quality checks failed", report)

        report["details"].append("Data quality checks passed.")
        return report
