import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta


class HistoricalDataSeeder:
    """Seeds historical data for BTC/major assets (2022-2024) for model training."""

    def __init__(self, data_source="mock"):
        self.data_source = data_source
        self.synthetic_seed = 42
        np.random.seed(self.synthetic_seed)

    def _generate_synthetic_ohlcv(
        self,
        start_price: float = 40000,
        days: int = 252,
        volatility: float = 0.025,
        trend: float = 0.0001,
    ) -> List[Dict[str, Any]]:
        """Generate synthetic OHLCV data for backtesting."""
        ohlcv = []
        current_price = start_price
        
        for day in range(days):
            daily_return = np.random.normal(trend, volatility)
            open_price = current_price
            
            intraday_vol = volatility / np.sqrt(4)
            
            intraday_returns = np.random.normal(daily_return / 4, intraday_vol, 4)
            prices_intraday = open_price * np.exp(np.cumsum(intraday_returns))
            
            high_price = np.max(prices_intraday)
            low_price = np.min(prices_intraday)
            close_price = prices_intraday[-1]
            
            volume = np.random.gamma(100, 2) * 1000000
            
            current_price = close_price
            
            ohlcv.append({
                "timestamp": datetime(2022, 1, 1) + timedelta(days=day),
                "open": float(open_price),
                "high": float(high_price),
                "low": float(low_price),
                "close": float(close_price),
                "volume": float(volume),
            })
        
        return ohlcv

    def seed_btc_2022_2024(self) -> Dict[str, List[Dict[str, Any]]]:
        """Seed BTC data for 2022-2024 period."""
        
        btc_data_2022 = self._generate_synthetic_ohlcv(
            start_price=45000,
            days=252,
            volatility=0.035,
            trend=-0.0002,
        )
        
        btc_data_2023 = self._generate_synthetic_ohlcv(
            start_price=16500,
            days=252,
            volatility=0.028,
            trend=0.0008,
        )
        
        btc_data_2024 = self._generate_synthetic_ohlcv(
            start_price=42000,
            days=150,
            volatility=0.022,
            trend=0.0005,
        )
        
        for i, record in enumerate(btc_data_2023):
            record["timestamp"] = datetime(2023, 1, 1) + timedelta(days=i)
        
        for i, record in enumerate(btc_data_2024):
            record["timestamp"] = datetime(2024, 1, 1) + timedelta(days=i)
        
        btc_full_data = btc_data_2022 + btc_data_2023 + btc_data_2024
        
        return {
            "BTC/USDT": btc_full_data,
        }

    def seed_major_assets(self) -> Dict[str, List[Dict[str, Any]]]:
        """Seed data for major assets."""
        assets = {
            "ETH/USDT": (2500, 0.032, 0.0006),
            "SPY": (350, 0.018, 0.0004),
            "EURUSD": (1.05, 0.012, -0.00001),
        }
        
        all_data = {}
        
        for asset_name, (start_price, volatility, trend) in assets.items():
            asset_data_2022 = self._generate_synthetic_ohlcv(
                start_price=start_price,
                days=252,
                volatility=volatility,
                trend=trend,
            )
            
            asset_data_2023 = self._generate_synthetic_ohlcv(
                start_price=asset_data_2022[-1]["close"],
                days=252,
                volatility=volatility * 0.9,
                trend=trend * 1.5,
            )
            
            asset_data_2024 = self._generate_synthetic_ohlcv(
                start_price=asset_data_2023[-1]["close"],
                days=150,
                volatility=volatility * 0.85,
                trend=trend,
            )
            
            for i, record in enumerate(asset_data_2023):
                record["timestamp"] = datetime(2023, 1, 1) + timedelta(days=i)
            
            for i, record in enumerate(asset_data_2024):
                record["timestamp"] = datetime(2024, 1, 1) + timedelta(days=i)
            
            full_data = asset_data_2022 + asset_data_2023 + asset_data_2024
            all_data[asset_name] = full_data
        
        return all_data

    def create_signal_dataset(self, ohlcv_data: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
        """Create labeled dataset for training."""
        training_data = {
            "X": [],
            "y": [],
            "metadata": [],
        }
        
        for asset_name, ohlcv in ohlcv_data.items():
            closes = np.array([candle["close"] for candle in ohlcv])
            volumes = np.array([candle["volume"] for candle in ohlcv])
            
            for i in range(20, len(closes) - 5):
                window_closes = closes[i-20:i]
                window_volumes = volumes[i-20:i]
                
                features = []
                features.append(np.mean(np.diff(window_closes) / window_closes[:-1]))
                features.append(np.std(np.diff(window_closes) / window_closes[:-1]))
                features.append(np.mean(window_volumes))
                features.extend(list(np.diff(window_closes)[-5:] / window_closes[-6:-1]))
                
                future_return = np.log(closes[i+5] / closes[i])
                label = 1 if future_return > 0 else 0
                
                training_data["X"].append(features)
                training_data["y"].append(label)
                training_data["metadata"].append({
                    "asset": asset_name,
                    "timestamp": ohlcv[i]["timestamp"],
                    "price": float(closes[i]),
                })
        
        training_data["X"] = np.array(training_data["X"])
        training_data["y"] = np.array(training_data["y"])
        
        return training_data
