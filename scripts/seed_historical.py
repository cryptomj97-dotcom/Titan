import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict

import numpy as np

# Add repository root to module search path when running as a script.
sys.path.append(str(Path(__file__).resolve().parents[1]))

from services.quant.historical_seeder import HistoricalDataSeeder
from services.quant.ml.signal_scorer import LightGBMSignalScorer


def safe_train_test_split(X: np.ndarray, y: np.ndarray, test_size: float = 0.2, random_state: int = 42):
    if not 0.0 < test_size < 1.0:
        raise ValueError("test_size must be between 0.0 and 1.0")

    indices = np.arange(len(X))
    rng = np.random.default_rng(random_state)
    rng.shuffle(indices)

    split = int(len(indices) * (1.0 - test_size))
    train_idx = indices[:split]
    test_idx = indices[split:]

    return X[train_idx], X[test_idx], y[train_idx], y[test_idx]


def build_training_summary(seed_data: Dict[str, Any], dataset: Dict[str, Any], accuracy: float | None, is_trained: bool) -> Dict[str, Any]:
    asset_counts = {asset: len(records) for asset, records in seed_data.items()}
    label_counts = {
        "bullish": int((dataset["y"] == 1).sum()),
        "bearish": int((dataset["y"] == 0).sum()),
    }

    return {
        "assets": list(seed_data.keys()),
        "asset_counts": asset_counts,
        "dataset_rows": int(len(dataset["X"])),
        "dataset_features": int(dataset["X"].shape[1]) if hasattr(dataset["X"], "shape") else None,
        "label_counts": label_counts,
        "trained": bool(is_trained),
        "validation_accuracy": float(accuracy) if accuracy is not None else None,
    }


def main(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    seeder = HistoricalDataSeeder()
    seed_data = {}
    seed_data.update(seeder.seed_btc_2022_2024())
    seed_data.update(seeder.seed_major_assets())

    dataset = seeder.create_signal_dataset(seed_data)
    if dataset["X"].shape[0] < 10:
        raise RuntimeError("Insufficient seeded rows to train a model.")

    model = LightGBMSignalScorer()
    try:
        from sklearn.model_selection import train_test_split
    except Exception:
        train_test_split = None

    if train_test_split:
        X_train, X_val, y_train, y_val = train_test_split(dataset["X"], dataset["y"], test_size=0.20, random_state=42)
    else:
        X_train, X_val, y_train, y_val = safe_train_test_split(dataset["X"], dataset["y"], test_size=0.20, random_state=42)

    model.fit(X_train, y_train, X_val, y_val)
    accuracy = None
    if model._is_trained:
        predictions = [model.predict(features) for features in X_val]
        truth = y_val.astype(int)
        predicted = [1 if probability > 0.5 else 0 for probability in predictions]
        accuracy = float((np.array(predicted) == np.array(truth)).mean())

    summary = build_training_summary(seed_data, dataset, accuracy, model._is_trained)
    summary_path = output_dir / "historical_training_summary.json"
    dataset_path = output_dir / "historical_signal_dataset.json"

    with summary_path.open("w", encoding="utf-8") as fp:
        json.dump(summary, fp, indent=2, default=str)

    with dataset_path.open("w", encoding="utf-8") as fp:
        json.dump(
            {
                "X": dataset["X"].tolist(),
                "y": dataset["y"].tolist(),
            },
            fp,
            indent=2,
            default=str,
        )

    print(f"Saved seeded dataset to {dataset_path}")
    print(f"Saved training summary to {summary_path}")
    if accuracy is not None:
        print(f"Validation accuracy: {accuracy:.3f}")
    else:
        print("Model training completed with fallback or no model support.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed historical price and signal data for Titan training.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/historical"),
        help="Directory where seed outputs and training summaries will be saved.",
    )
    args = parser.parse_args()
    main(args.output_dir)
