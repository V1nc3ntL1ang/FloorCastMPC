"""
Utility script to visualize how the grid-search `delta` metric varies with
each hyperparameter in the results CSV file.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Iterable

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
os.environ.setdefault("KMP_INIT_AT_FORK", "FALSE")
os.environ.setdefault("OMP_NUM_THREADS", "1")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


DEFAULT_EXCLUDE_COLUMNS = {
    "delta",
    "baseline_cost",
    "mpc_cost",
    "average_cost",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Plot delta trends against each hyperparameter in a grid-search CSV."
        )
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=Path(
            "/home/v1nc3nt/WinDesktop/SCUT/作业/优化方法/LoadAwareElevator/results/grid_search/grid_search_single_20251103_171629.csv"
        ),
        help="Path to the grid-search CSV file.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(
            "/home/v1nc3nt/WinDesktop/SCUT/作业/优化方法/LoadAwareElevator/results/grid_search/plots"
        ),
        help="Directory where the plots will be saved.",
    )
    parser.add_argument(
        "--exclude",
        type=str,
        nargs="*",
        default=(),
        help=(
            "Additional columns to exclude from plotting. "
            "Useful for metrics that should not be treated as hyperparameters."
        ),
    )
    parser.add_argument(
        "--rolling-window",
        type=int,
        default=None,
        help=(
            "Optional rolling window (number of points) applied to the mean delta "
            "curve to smooth the trend."
        ),
    )
    return parser.parse_args()


def determine_parameter_columns(
    df: pd.DataFrame, exclude_columns: Iterable[str]
) -> list[str]:
    """Return columns considered hyperparameters."""
    exclusion = set(DEFAULT_EXCLUDE_COLUMNS) | set(exclude_columns)
    parameter_columns = [
        column
        for column in df.columns
        if column not in exclusion and pd.api.types.is_numeric_dtype(df[column])
    ]
    if "delta" not in df.columns:
        raise ValueError("CSV must contain a 'delta' column.")
    if not parameter_columns:
        raise ValueError("No numeric columns left to plot after exclusions.")
    return parameter_columns


def plot_delta_vs_parameter(
    df: pd.DataFrame, parameter: str, output_path: Path, rolling_window: int | None
) -> None:
    """Generate scatter and mean trend plots of delta against a single parameter."""
    parameter_series = df[parameter]
    delta_series = df["delta"]

    sorted_indices = parameter_series.argsort()
    sorted_parameter = parameter_series.iloc[sorted_indices]
    sorted_delta = delta_series.iloc[sorted_indices]

    grouped = df.groupby(parameter)["delta"].agg(["mean"]).reset_index()
    grouped = grouped.sort_values(by=parameter)

    mean_delta = grouped["mean"]
    if rolling_window and rolling_window > 1:
        mean_delta = mean_delta.rolling(window=rolling_window, min_periods=1).mean()

    plt.figure(figsize=(8, 5))
    plt.scatter(sorted_parameter, sorted_delta, alpha=0.45, label="delta samples")
    plt.plot(
        grouped[parameter], mean_delta, color="tab:red", linewidth=2, label="mean delta"
    )

    plt.title(f"Delta vs {parameter}")
    plt.xlabel(parameter)
    plt.ylabel("delta")
    plt.legend()
    plt.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=200)
    plt.close()


def main() -> None:
    args = parse_args()

    if not args.csv.exists():
        raise FileNotFoundError(f"CSV file not found: {args.csv}")

    df = pd.read_csv(args.csv)
    parameter_columns = determine_parameter_columns(df, args.exclude)

    args.output_dir.mkdir(parents=True, exist_ok=True)

    for parameter in parameter_columns:
        output_path = args.output_dir / f"delta_vs_{parameter}.png"
        plot_delta_vs_parameter(df, parameter, output_path, args.rolling_window)
        print(f"Saved plot: {output_path}")


if __name__ == "__main__":
    main()
