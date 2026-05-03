"""
Tạo bảng final từ processed_heart_disease (bảng gốc, chưa split):

  1. Chỉ giữ các thuộc tính: age, trestbps, chol, thalach, oldpeak và num.
  2. Không loại dòng có thiếu.
  3. Không điền missing ở bước này (giữ nguyên NULL để xử lý ở bước outlier).

Chạy sau import_processed_to_mysql.py (độc lập với split_missing_records_mysql.py).
"""
from __future__ import annotations

import mysql.connector

from db_config import DB_CONFIG

SOURCE_TABLE = "processed_heart_disease"
MISSING_PROCESSED_TABLE = "heart_disease_missing_processed"

FINAL_COLUMNS = (
    "id",
    "source_file",
    "source_line",
    "age",
    "trestbps",
    "chol",
    "thalach",
    "oldpeak",
    "num",
)

SELECT_SOURCE_SQL = (
    "SELECT id, source_file, source_line, age, trestbps, chol, "
    "thalach, oldpeak, num "
    f"FROM {SOURCE_TABLE} ORDER BY id"
)


def main() -> None:
    cols_sql = ", ".join(FINAL_COLUMNS)
    connection = mysql.connector.connect(**DB_CONFIG)
    cursor = connection.cursor()

    cursor.execute(f"DROP TABLE IF EXISTS {MISSING_PROCESSED_TABLE}")

    cursor.execute(
        f"""
        CREATE TABLE {MISSING_PROCESSED_TABLE} (
            id INT NOT NULL PRIMARY KEY,
            source_file VARCHAR(64) NOT NULL,
            source_line INT NOT NULL,
            age INT NOT NULL,
            trestbps DOUBLE NULL,
            chol DOUBLE NULL,
            thalach DOUBLE NULL,
            oldpeak DOUBLE NULL,
            num TINYINT NOT NULL
        )
        """
    )

    cursor.execute(SELECT_SOURCE_SQL)
    source_rows = cursor.fetchall()

    final_rows: list[tuple] = []
    for row in source_rows:
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

        final_rows.append(
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
            )
        )

    cursor.executemany(
        f"""
        INSERT INTO {MISSING_PROCESSED_TABLE} ({cols_sql})
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        final_rows,
    )

    connection.commit()

    cursor.execute(f"SELECT COUNT(*) FROM {SOURCE_TABLE}")
    n_source = cursor.fetchone()[0]
    cursor.execute(f"SELECT COUNT(*) FROM {MISSING_PROCESSED_TABLE}")
    n_final = cursor.fetchone()[0]

    print(f"Bảng nguồn {SOURCE_TABLE}: {n_source} dòng")
    print(
        f"Bảng {MISSING_PROCESSED_TABLE}: {n_final} dòng "
        "(chỉ giữ age/trestbps/chol/thalach/oldpeak/num; giữ nguyên NULL)"
    )
    print(f"Số dòng giữ lại: {n_final} / {n_source}")

    cursor.close()
    connection.close()


if __name__ == "__main__":
    main()
