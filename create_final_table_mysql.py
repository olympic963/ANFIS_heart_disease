"""
Tao bang final tu processed_heart_disease (bang goc, chua split):

  1. Khong dua slope, ca, thal vao bang dich.
  2. Chi giu cac dong ma moi cot con lai deu khong NULL.

Chay sau import_processed_to_mysql.py (va doc lap voi split_missing_records_mysql.py).
"""
from __future__ import annotations

import mysql.connector

from db_config import DB_CONFIG

SOURCE_TABLE = "processed_heart_disease"
FINAL_TABLE = "processed_heart_disease_final"

# Cac cot giu lai (khong co slope, ca, thal)
FINAL_COLUMNS = (
    "id",
    "source_file",
    "source_line",
    "age",
    "sex",
    "cp",
    "trestbps",
    "chol",
    "fbs",
    "restecg",
    "thalach",
    "exang",
    "oldpeak",
    "num",
)

# Dieu kien day du cho cac cot duoc giu (num luon NOT NULL trong schema nhung van kiem tra)
COMPLETE_WITHOUT_SLOPE_CA_THAL = (
    "age IS NOT NULL AND sex IS NOT NULL AND cp IS NOT NULL AND "
    "trestbps IS NOT NULL AND chol IS NOT NULL AND fbs IS NOT NULL AND "
    "restecg IS NOT NULL AND thalach IS NOT NULL AND exang IS NOT NULL AND "
    "oldpeak IS NOT NULL AND num IS NOT NULL"
)


def main() -> None:
    cols_sql = ", ".join(FINAL_COLUMNS)
    connection = mysql.connector.connect(**DB_CONFIG)
    cursor = connection.cursor()

    cursor.execute(f"DROP TABLE IF EXISTS {FINAL_TABLE}")

    cursor.execute(
        f"""
        CREATE TABLE {FINAL_TABLE} (
            id INT NOT NULL PRIMARY KEY,
            source_file VARCHAR(64) NOT NULL,
            source_line INT NOT NULL,
            age INT NOT NULL,
            sex TINYINT NOT NULL,
            cp TINYINT NOT NULL,
            trestbps DOUBLE NOT NULL,
            chol DOUBLE NOT NULL,
            fbs TINYINT NOT NULL,
            restecg TINYINT NOT NULL,
            thalach DOUBLE NOT NULL,
            exang TINYINT NOT NULL,
            oldpeak DOUBLE NOT NULL,
            num TINYINT NOT NULL
        )
        """
    )

    cursor.execute(
        f"""
        INSERT INTO {FINAL_TABLE} ({cols_sql})
        SELECT {cols_sql}
        FROM {SOURCE_TABLE}
        WHERE {COMPLETE_WITHOUT_SLOPE_CA_THAL}
        """
    )

    connection.commit()

    cursor.execute(f"SELECT COUNT(*) FROM {SOURCE_TABLE}")
    n_source = cursor.fetchone()[0]
    cursor.execute(f"SELECT COUNT(*) FROM {FINAL_TABLE}")
    n_final = cursor.fetchone()[0]

    print(f"Bang nguon {SOURCE_TABLE}: {n_source} dong")
    print(f"Bang {FINAL_TABLE}: {n_final} dong (da bo slope/ca/thal, chi giu dong khong thieu o cot con lai)")
    print(f"Loai bo: {n_source - n_final} dong")

    cursor.close()
    connection.close()


if __name__ == "__main__":
    main()
