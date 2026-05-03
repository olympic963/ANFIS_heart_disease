from __future__ import annotations

import mysql.connector

from db_config import DB_CONFIG

SOURCE_TABLE = "processed_heart_disease"
COMPLETE_TABLE = "processed_heart_disease_complete"
MISSING_TABLE = "processed_heart_disease_missing"

NULL_CONDITION = (
    "age IS NULL OR sex IS NULL OR cp IS NULL OR trestbps IS NULL OR chol IS NULL OR "
    "fbs IS NULL OR restecg IS NULL OR thalach IS NULL OR exang IS NULL OR oldpeak IS NULL OR "
    "slope IS NULL OR ca IS NULL OR thal IS NULL OR num IS NULL"
)


def main() -> None:
    connection = mysql.connector.connect(**DB_CONFIG)
    cursor = connection.cursor()

    cursor.execute(f"DROP TABLE IF EXISTS {COMPLETE_TABLE}")
    cursor.execute(f"DROP TABLE IF EXISTS {MISSING_TABLE}")

    cursor.execute(f"CREATE TABLE {COMPLETE_TABLE} LIKE {SOURCE_TABLE}")
    cursor.execute(f"CREATE TABLE {MISSING_TABLE} LIKE {SOURCE_TABLE}")

    cursor.execute(
        f"""
        INSERT INTO {COMPLETE_TABLE}
        SELECT *
        FROM {SOURCE_TABLE}
        WHERE NOT ({NULL_CONDITION})
        """
    )

    cursor.execute(
        f"""
        INSERT INTO {MISSING_TABLE}
        SELECT *
        FROM {SOURCE_TABLE}
        WHERE {NULL_CONDITION}
        """
    )

    connection.commit()

    cursor.execute(f"SELECT COUNT(*) FROM {SOURCE_TABLE}")
    source_count = cursor.fetchone()[0]
    cursor.execute(f"SELECT COUNT(*) FROM {COMPLETE_TABLE}")
    complete_count = cursor.fetchone()[0]
    cursor.execute(f"SELECT COUNT(*) FROM {MISSING_TABLE}")
    missing_count = cursor.fetchone()[0]

    print(f"Source rows: {source_count}")
    print(f"Complete rows: {complete_count}")
    print(f"Missing rows: {missing_count}")

    cursor.close()
    connection.close()


if __name__ == "__main__":
    main()
