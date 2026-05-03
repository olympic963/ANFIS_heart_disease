"""
Ve phan bo gia tri cho tung thuoc tinh trong bang heart_disease_outlier_processed
va luu thanh anh PNG.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import mysql.connector

from db_config import DB_CONFIG

TABLE_NAME = "heart_disease_outlier_processed"
OUTPUT_DIR = Path("..") / "outlier_processed"

CONTINUOUS_COLS = ("age", "trestbps", "chol", "thalach", "oldpeak")
CATEGORICAL_COLS = ("sex", "cp", "fbs", "restecg", "exang")


def fetch_column_values(
    cursor: mysql.connector.cursor.MySQLCursor, column: str
) -> list[float]:
    cursor.execute(f"SELECT {column} FROM {TABLE_NAME}")
    return [float(row[0]) for row in cursor.fetchall()]


def save_continuous_plot(values: list[float], column: str, output_dir: Path) -> None:
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.hist(values, bins=25, edgecolor="black", alpha=0.8)

    col_min = min(values)
    col_max = max(values)
    ax.set_title(f"{column} distribution | min={col_min:.2f}, max={col_max:.2f}")
    ax.set_xlabel(column)
    ax.set_ylabel("Count")
    ax.grid(axis="y", alpha=0.25)

    output_path = output_dir / f"{column}_hist.png"
    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)


def save_categorical_plot(values: list[float], column: str, output_dir: Path) -> None:
    int_values = [int(v) for v in values]
    categories = sorted(set(int_values))
    counts = [int_values.count(c) for c in categories]

    fig, ax = plt.subplots(figsize=(8, 5))
    bars = ax.bar([str(c) for c in categories], counts)
    ax.set_title(
        f"{column} distribution | domain={categories}, min={min(categories)}, max={max(categories)}"
    )
    ax.set_xlabel(column)
    ax.set_ylabel("Count")
    ax.grid(axis="y", alpha=0.25)

    for bar, cnt in zip(bars, counts):
        ax.text(
            bar.get_x() + bar.get_width() / 2.0,
            bar.get_height(),
            str(cnt),
            ha="center",
            va="bottom",
            fontsize=9,
        )

    output_path = output_dir / f"{column}_bar.png"
    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    connection = mysql.connector.connect(**DB_CONFIG)
    cursor = connection.cursor()

    for col in CONTINUOUS_COLS:
        values = fetch_column_values(cursor, col)
        save_continuous_plot(values, col, OUTPUT_DIR)
        print(f"Saved: {OUTPUT_DIR / (col + '_hist.png')}")

    for col in CATEGORICAL_COLS:
        values = fetch_column_values(cursor, col)
        save_categorical_plot(values, col, OUTPUT_DIR)
        print(f"Saved: {OUTPUT_DIR / (col + '_bar.png')}")

    cursor.close()
    connection.close()

    print("\nDone. All charts were saved to:")
    print(str(OUTPUT_DIR))


if __name__ == "__main__":
    main()
