"""
Tao bang trung gian xu ly ngoai lai tu bang da xu ly missing.

Nguon: heart_disease_missing_processed
Quy tac:
- Loai bo ban ghi co trestbps = 0.
- Sau khi loai bo trestbps = 0, tinh lai median va chi thay cac gia tri NULL:
  - trestbps, thalach, oldpeak: median tren cac gia tri khong NULL
  - chol: median tren cac gia tri khong NULL va khac 0

Luu y: khong cap nhat bang SOURCE_TABLE, chi tao bang OUTLIER_TABLE moi.
"""
from __future__ import annotations

from statistics import median

import mysql.connector

from db_config import DB_CONFIG

SOURCE_TABLE = "heart_disease_missing_processed"
OUTLIER_TABLE = "heart_disease_outlier_processed"


def compute_median(
    cursor: mysql.connector.cursor.MySQLCursor, column: str, where_sql: str
) -> float:
    cursor.execute(f"SELECT {column} FROM {SOURCE_TABLE} WHERE {where_sql}")
    values = [float(row[0]) for row in cursor.fetchall()]
    if not values:
        raise ValueError(f"Cannot compute median for {column}: no matching values.")
    return float(median(values))


def main() -> None:
    connection = mysql.connector.connect(**DB_CONFIG)
    cursor = connection.cursor()

    cursor.execute(f"DROP TABLE IF EXISTS {OUTLIER_TABLE}")
    cursor.execute(
        f"""
        CREATE TABLE {OUTLIER_TABLE} LIKE {SOURCE_TABLE}
        """
    )

    # Median tinh tren du lieu sau khi loai bo trestbps = 0
    trestbps_median = compute_median(
        cursor, "trestbps", "trestbps IS NOT NULL AND trestbps <> 0"
    )
    # Theo yeu cau: chol/thalach/oldpeak khong phu thuoc viec loai bo trestbps = 0
    chol_median = compute_median(cursor, "chol", "chol IS NOT NULL AND chol <> 0")
    thalach_median = compute_median(cursor, "thalach", "thalach IS NOT NULL")
    oldpeak_median = compute_median(cursor, "oldpeak", "oldpeak IS NOT NULL")

    cursor.execute(
        f"""
        INSERT INTO {OUTLIER_TABLE} (
            id, source_file, source_line, age, trestbps, chol, thalach, oldpeak, num
        )
        SELECT
            id,
            source_file,
            source_line,
            age,
            CASE
                WHEN trestbps IS NULL THEN %s
                ELSE trestbps
            END AS trestbps,
            CASE
                WHEN chol IS NULL OR chol = 0 THEN %s
                ELSE chol
            END AS chol,
            CASE
                WHEN thalach IS NULL THEN %s
                ELSE thalach
            END AS thalach,
            CASE
                WHEN oldpeak IS NULL THEN %s
                ELSE oldpeak
            END AS oldpeak,
            num
        FROM {SOURCE_TABLE}
        WHERE trestbps IS NULL OR trestbps <> 0
        ORDER BY id
        """,
        (trestbps_median, chol_median, thalach_median, oldpeak_median),
    )

    connection.commit()

    cursor.execute(f"SELECT COUNT(*) FROM {SOURCE_TABLE}")
    source_count = cursor.fetchone()[0]
    cursor.execute(f"SELECT COUNT(*) FROM {OUTLIER_TABLE}")
    outlier_count = cursor.fetchone()[0]
    cursor.execute(f"SELECT COUNT(*) FROM {SOURCE_TABLE} WHERE trestbps = 0")
    dropped_trestbps_zero = cursor.fetchone()[0]
    cursor.execute(
        f"""
        SELECT COUNT(*) FROM {SOURCE_TABLE}
        WHERE (trestbps IS NULL OR trestbps <> 0)
          AND (trestbps IS NULL OR chol IS NULL OR thalach IS NULL OR oldpeak IS NULL)
        """
    )
    replaced_null_count = cursor.fetchone()[0]
    cursor.execute(
        f"""
        SELECT COUNT(*) FROM {SOURCE_TABLE}
        WHERE (trestbps IS NULL OR trestbps <> 0)
          AND chol = 0
        """
    )
    replaced_chol_zero_count = cursor.fetchone()[0]

    print(f"Nguon: {SOURCE_TABLE} -> {source_count} dong")
    print(f"Trung gian: {OUTLIER_TABLE} -> {outlier_count} dong")
    print(f"So dong bi loai do trestbps = 0: {dropped_trestbps_zero}")
    print(f"So dong co it nhat 1 NULL (trestbps/chol/thalach/oldpeak) da duoc dien: {replaced_null_count}")
    print(f"So dong co chol = 0 da duoc thay bang median: {replaced_chol_zero_count}")
    print("Median su dung de dien NULL:")
    print(f"- trestbps: {trestbps_median}")
    print(f"- chol (bo qua gia tri 0 khi tinh median): {chol_median}")
    print(f"- thalach: {thalach_median}")
    print(f"- oldpeak: {oldpeak_median}")

    cursor.close()
    connection.close()


if __name__ == "__main__":
    main()
