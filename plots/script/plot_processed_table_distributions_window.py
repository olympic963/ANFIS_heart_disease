"""
Ve phan bo gia tri cho tung thuoc tinh trong bang heart_disease_missing_processed
va hien thi duoi dang cua so (matplotlib window).

Logic giong ban luu anh:
- Bien lien tuc: histogram
- Bien roi rac: bar chart
"""
from __future__ import annotations

import matplotlib.pyplot as plt
import mysql.connector

from db_config import DB_CONFIG

TABLE_NAME = "heart_disease_missing_processed"

CONTINUOUS_COLS = ("age", "trestbps", "chol", "thalach", "oldpeak")
CATEGORICAL_COLS = ("sex", "cp", "fbs", "restecg", "exang")


def fetch_column_values(
    cursor: mysql.connector.cursor.MySQLCursor, column: str
) -> list[float]:
    cursor.execute(f"SELECT {column} FROM {TABLE_NAME} WHERE {column} IS NOT NULL")
    return [float(row[0]) for row in cursor.fetchall()]


def show_continuous_plot(values: list[float], column: str) -> None:
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.hist(values, bins=50, edgecolor="black", alpha=0.8)

    col_min = min(values)
    col_max = max(values)
    ax.set_title(f"{column} distribution | min={col_min:.2f}, max={col_max:.2f}")
    ax.set_xlabel(column)
    ax.set_ylabel("Count")
    ax.grid(axis="y", alpha=0.25)

    fig.tight_layout()
    plt.show()


def show_categorical_plot(values: list[float], column: str) -> None:
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

    fig.tight_layout()
    plt.show()


def main() -> None:
    connection = mysql.connector.connect(**DB_CONFIG)
    cursor = connection.cursor()

    print("Dang hien thi bieu do bien lien tuc...")
    for col in CONTINUOUS_COLS:
        values = fetch_column_values(cursor, col)
        show_continuous_plot(values, col)

    print("Dang hien thi bieu do bien roi rac...")
    for col in CATEGORICAL_COLS:
        values = fetch_column_values(cursor, col)
        show_categorical_plot(values, col)

    cursor.close()
    connection.close()


if __name__ == "__main__":
    main()
