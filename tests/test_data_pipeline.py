import pytest
import pandas as pd
from services.data.market_data import MarketDataFetcher
from services.data.data_quality_gate import DataQualityGate, DataQualityError


def test_normalize_ohlcv_basic():
    raw = pd.DataFrame(
        {
            "Open": [1.0, 1.5, 1.2],
            "High": [1.1, 1.6, 1.3],
            "Low": [0.9, 1.4, 1.0],
            "Close": [1.05, 1.55, 1.25],
            "Volume": [100, 120, 90],
        },
        index=pd.date_range("2025-01-01", periods=3, freq="D"),
    )

    normalized = MarketDataFetcher.normalize_ohlcv(raw)
    assert list(normalized.columns) == ["timestamp", "open", "high", "low", "close", "volume"]
    assert normalized["open"].tolist() == [1.0, 1.5, 1.2]


def test_data_quality_gate_passes_for_good_data():
    frame = pd.DataFrame(
        {
            "timestamp": pd.date_range("2025-01-01", periods=210, freq="D"),
            "open": [1.0 + i * 0.01 for i in range(210)],
            "high": [1.05 + i * 0.01 for i in range(210)],
            "low": [0.95 + i * 0.01 for i in range(210)],
            "close": [1.02 + i * 0.01 for i in range(210)],
            "volume": [100 + i for i in range(210)],
        }
    )

    packet = {"ohlcv": {"1D": frame, "1W": frame, "4H": frame}, "news": [1]}
    report = DataQualityGate.validate(packet)
    assert report["passed"]


def test_data_quality_gate_rejects_missing_news():
    frame = pd.DataFrame(
        {
            "timestamp": pd.date_range("2025-01-01", periods=210, freq="D"),
            "open": [1.0 + i * 0.01 for i in range(210)],
            "high": [1.05 + i * 0.01 for i in range(210)],
            "low": [0.95 + i * 0.01 for i in range(210)],
            "close": [1.02 + i * 0.01 for i in range(210)],
            "volume": [100 + i for i in range(210)],
        }
    )

    with pytest.raises(DataQualityError):
        DataQualityGate.validate({"ohlcv": {"1D": frame, "1W": frame, "4H": frame}, "news": []})


def test_data_quality_gate_accepts_dataframe_and_record_lists():
    frame = pd.DataFrame(
        {
            "timestamp": pd.date_range("2025-01-01", periods=210, freq="D"),
            "open": [1.0 + i * 0.01 for i in range(210)],
            "high": [1.05 + i * 0.01 for i in range(210)],
            "low": [0.95 + i * 0.01 for i in range(210)],
            "close": [1.02 + i * 0.01 for i in range(210)],
            "volume": [100 + i for i in range(210)],
        }
    )

    report = DataQualityGate.validate(
        {"ohlcv": {"1D": frame, "1W": frame.to_dict(orient="records"), "4H": frame}, "news": [1]}
    )
    assert report["passed"]
