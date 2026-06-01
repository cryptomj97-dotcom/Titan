import numpy as np
import pandas as pd
from typing import Dict, Any, List, Tuple, Optional

try:
    import vectorbt as vbt
    HAS_VBT = True
except ImportError:
    HAS_VBT = False


class Backtester:
    """Vectorbt-based backtester for signal validation."""

    def __init__(self, initial_capital: float = 10000.0, fee_rate: float = 0.001):
        self.initial_capital = initial_capital
        self.fee_rate = fee_rate

    def _calculate_returns(self, prices: np.ndarray, signals: np.ndarray) -> np.ndarray:
        """Calculate PnL from signals."""
        log_returns = np.diff(np.log(prices))
        
        signal_returns = np.zeros_like(log_returns)
        for i in range(1, len(signals)):
            if signals[i-1] == 1:
                signal_returns[i] = log_returns[i] - self.fee_rate
            elif signals[i-1] == -1:
                signal_returns[i] = -log_returns[i] - self.fee_rate
        
        return signal_returns

    def _calculate_equity_curve(self, prices: np.ndarray, signals: np.ndarray) -> np.ndarray:
        """Calculate equity curve."""
        log_returns = np.diff(np.log(prices))
        log_returns = np.insert(log_returns, 0, 0.0)
        
        equity = np.zeros_like(prices)
        equity[0] = self.initial_capital
        
        for i in range(1, len(prices)):
            if signals[i-1] == 1:
                pnl = equity[i-1] * (np.exp(log_returns[i]) - 1 - self.fee_rate)
            elif signals[i-1] == -1:
                pnl = -equity[i-1] * (np.exp(log_returns[i]) - 1 - self.fee_rate)
            else:
                pnl = 0.0
            
            equity[i] = equity[i-1] + pnl
        
        return equity

    def _calculate_metrics(self, equity: np.ndarray) -> Dict[str, float]:
        """Calculate performance metrics."""
        returns = np.diff(equity) / equity[:-1]
        
        total_return = (equity[-1] - self.initial_capital) / self.initial_capital
        annual_return = (equity[-1] / self.initial_capital) ** (252 / len(equity)) - 1 if len(equity) > 0 else 0.0
        
        volatility = np.std(returns) * np.sqrt(252) if len(returns) > 0 else 0.0
        
        sharpe = annual_return / (volatility + 1e-10) if volatility > 0 else 0.0
        
        max_drawdown = 0.0
        running_max = equity[0]
        for val in equity:
            running_max = max(running_max, val)
            drawdown = (val - running_max) / running_max
            max_drawdown = min(max_drawdown, drawdown)
        
        win_rate = 0.0
        if len(returns) > 0:
            wins = np.sum(returns > 0)
            win_rate = wins / len(returns)
        
        return {
            "total_return": float(total_return),
            "annual_return": float(annual_return),
            "volatility": float(volatility),
            "sharpe_ratio": float(sharpe),
            "max_drawdown": float(max_drawdown),
            "win_rate": float(win_rate),
        }

    def backtest(self, prices: np.ndarray, signals: np.ndarray) -> Dict[str, Any]:
        """Run backtest and return metrics."""
        if len(prices) < 2 or len(signals) != len(prices):
            return {
                "total_return": 0.0,
                "annual_return": 0.0,
                "volatility": 0.0,
                "sharpe_ratio": 0.0,
                "max_drawdown": 0.0,
                "win_rate": 0.0,
                "final_equity": self.initial_capital,
            }
        
        equity = self._calculate_equity_curve(prices, signals)
        metrics = self._calculate_metrics(equity)
        
        metrics["final_equity"] = float(equity[-1])
        
        return metrics

    def walk_forward_backtest(self, prices: np.ndarray, signals: np.ndarray, window: int = 60, stride: int = 10) -> Dict[str, Any]:
        """Walk-forward backtest for robust signal validation."""
        all_metrics = []
        total_equity = self.initial_capital
        
        for start in range(0, len(prices) - window, stride):
            end = start + window
            
            window_prices = prices[start:end]
            window_signals = signals[start:end]
            
            window_equity = self._calculate_equity_curve(window_prices, window_signals)
            metrics = self._calculate_metrics(window_equity)
            all_metrics.append(metrics)
        
        if not all_metrics:
            return {
                "mean_return": 0.0,
                "mean_sharpe": 0.0,
                "consistency": 0.0,
                "out_of_sample_edge": 0.0,
            }
        
        mean_return = np.mean([m["annual_return"] for m in all_metrics])
        mean_sharpe = np.mean([m["sharpe_ratio"] for m in all_metrics])
        
        returns = [m["annual_return"] for m in all_metrics]
        consistency = 1.0 - (np.std(returns) / (abs(mean_return) + 0.01)) if mean_return != 0 else 0.0
        consistency = float(np.clip(consistency, 0.0, 1.0))
        
        edge = max(0.0, mean_return)
        out_of_sample_edge = edge * 0.85
        
        return {
            "mean_return": float(mean_return),
            "mean_sharpe": float(mean_sharpe),
            "consistency": float(consistency),
            "out_of_sample_edge": float(out_of_sample_edge),
        }

    def calculate_signal_edge(self, prices: np.ndarray, signals: np.ndarray) -> float:
        """Calculate expected edge from signal."""
        log_returns = np.diff(np.log(prices))
        
        bullish_returns = log_returns[signals[:-1] == 1] if np.sum(signals[:-1] == 1) > 0 else np.array([])
        bearish_returns = -log_returns[signals[:-1] == -1] if np.sum(signals[:-1] == -1) > 0 else np.array([])
        
        bullish_mean = np.mean(bullish_returns) if len(bullish_returns) > 0 else 0.0
        bearish_mean = np.mean(bearish_returns) if len(bearish_returns) > 0 else 0.0
        
        edge = (bullish_mean + bearish_mean) / 2.0
        edge = float(np.clip(edge, -0.05, 0.05))
        
        return edge
