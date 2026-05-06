"""
Chuan hoa du lieu tu bang da xu ly missing + outlier va luu vao bang moi.

Quy tac:
- Ratio:
    - age, trestbps, chol, thalach, oldpeak -> z-score.
- Ordinal: num -> giu nguyen.
"""
from __future__ import annotations

import json
from pathlib import Path

import mysql.connector

from db_config import DB_CONFIG

SOURCE_TABLE = "heart_disease_outlier_processed"
TARGET_TABLE = "processed_heart_disease_normalized"

CONTINUOUS_COLS = ("age", "trestbps", "chol", "thalach", "oldpeak")
NORMALIZATION_STATS_PATH = Path("../models") / "normalization_stats.json"


def _fetch_mean_std(
    cursor: mysql.connector.cursor.MySQLCursor, column: str
) -> tuple[float, float]:
    cursor.execute(
        f"""
        SELECT AVG({column}), STDDEV_POP({column})
        FROM {SOURCE_TABLE}
        """
    )
    mean_v, std_v = cursor.fetchone()
    if mean_v is None or std_v is None:
        raise ValueError(f"Column {column} has no values.")
    return float(mean_v), float(std_v)


def _z_score(value: float, mean_v: float, std_v: float) -> float:
    if std_v == 0:
        return 0.0
    return (value - mean_v) / std_v


def main() -> None:
    connection = mysql.connector.connect(**DB_CONFIG)
    cursor = connection.cursor()

    cursor.execute(f"DROP TABLE IF EXISTS {TARGET_TABLE}")
    cursor.execute(
        f"""
        CREATE TABLE {TARGET_TABLE} (
            id INT NOT NULL PRIMARY KEY,
            source_file VARCHAR(64) NOT NULL,
            source_line INT NOT NULL,

            age DOUBLE NOT NULL,
            trestbps DOUBLE NOT NULL,
            chol DOUBLE NOT NULL,
            thalach DOUBLE NOT NULL,
            oldpeak DOUBLE NOT NULL,

            num TINYINT NOT NULL
        )
        """
    )

    mean_std: dict[str, tuple[float, float]] = {
        col: _fetch_mean_std(cursor, col) for col in CONTINUOUS_COLS
    }

    cursor.execute(
        f"""
        SELECT
            id, source_file, source_line,
            age, trestbps, chol, thalach, oldpeak,
            num
        FROM {SOURCE_TABLE}
        ORDER BY id
        """
    )
    rows = cursor.fetchall()

    normalized_rows: list[tuple] = []
    for row in rows:
        (
            id_,
            source_file,
            source_line,
            age,
            trestbps,
            chol,
            thalach,
            oldpeak,
            num,
        ) = row

        age_n = _z_score(float(age), *mean_std["age"])
        trestbps_n = _z_score(float(trestbps), *mean_std["trestbps"])
        chol_n = _z_score(float(chol), *mean_std["chol"])
        thalach_n = _z_score(float(thalach), *mean_std["thalach"])
        oldpeak_n = _z_score(float(oldpeak), *mean_std["oldpeak"])

        normalized_rows.append(
            (
                int(id_),
                str(source_file),
                int(source_line),
                age_n,
                trestbps_n,
                chol_n,
                thalach_n,
                oldpeak_n,
                int(num),
            )
        )

    cursor.executemany(
        f"""
        INSERT INTO {TARGET_TABLE} (
            id, source_file, source_line,
            age, trestbps, chol, thalach, oldpeak,
            num
        )
        VALUES (
            %s, %s, %s,
            %s, %s, %s, %s, %s,
            %s
        )
        """,
        normalized_rows,
    )

    connection.commit()

    cursor.execute(f"SELECT COUNT(*) FROM {SOURCE_TABLE}")
    source_count = cursor.fetchone()[0]
    cursor.execute(f"SELECT COUNT(*) FROM {TARGET_TABLE}")
    target_count = cursor.fetchone()[0]

    print(f"Source table: {SOURCE_TABLE} -> {source_count} rows")
    print(f"Target table: {TARGET_TABLE} -> {target_count} rows")
    print("Z-score params used:")
    for col in CONTINUOUS_COLS:
        mean_v, std_v = mean_std[col]
        print(f"- {col}: mean={mean_v}, std={std_v}")

    NORMALIZATION_STATS_PATH.parent.mkdir(parents=True, exist_ok=True)
    NORMALIZATION_STATS_PATH.write_text(
        json.dumps(
            {
                "method": "zscore",
                "source_table": SOURCE_TABLE,
                "target_table": TARGET_TABLE,
                "continuous": {
                    col: {"mean": mean_std[col][0], "std": mean_std[col][1]}
                    for col in CONTINUOUS_COLS
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Saved normalization stats: {NORMALIZATION_STATS_PATH}")

    cursor.close()
    connection.close()


if __name__ == "__main__":
    main()
