from __future__ import annotations

import mysql.connector


DB_CONFIG = {
    "host": "localhost",
    "port": 3306,
    "user": "root",
    "password": "anacondaxs5",
    "database": "heart_disease",
}

TABLE_NAME = "processed_heart_disease"


def main() -> None:
    connection = mysql.connector.connect(**DB_CONFIG)
    cursor = connection.cursor(dictionary=True)

    cursor.execute(
        f"""
        SELECT
            SUM(age IS NULL) AS age,
            SUM(sex IS NULL) AS sex,
            SUM(cp IS NULL) AS cp,
            SUM(trestbps IS NULL) AS trestbps,
            SUM(chol IS NULL) AS chol,
            SUM(fbs IS NULL) AS fbs,
            SUM(restecg IS NULL) AS restecg,
            SUM(thalach IS NULL) AS thalach,
            SUM(exang IS NULL) AS exang,
            SUM(oldpeak IS NULL) AS oldpeak,
            SUM(slope IS NULL) AS slope,
            SUM(ca IS NULL) AS ca,
            SUM(thal IS NULL) AS thal,
            SUM(num IS NULL) AS num
        FROM {TABLE_NAME}
        """
    )
    missing_by_col = cursor.fetchone()

    cols_with_missing = {k: v for k, v in missing_by_col.items() if v and v > 0}

    print("Cac cot co gia tri thieu (ten cot: so gia tri thieu):")
    if cols_with_missing:
        for col_name, missing_count in cols_with_missing.items():
            print(f"- {col_name}: {missing_count}")
    else:
        print("- Khong co cot nao bi thieu.")

    where_any_null = (
        "age IS NULL OR sex IS NULL OR cp IS NULL OR trestbps IS NULL OR chol IS NULL OR "
        "fbs IS NULL OR restecg IS NULL OR thalach IS NULL OR exang IS NULL OR oldpeak IS NULL OR "
        "slope IS NULL OR ca IS NULL OR thal IS NULL OR num IS NULL"
    )

    cursor.execute(f"SELECT COUNT(*) AS cnt FROM {TABLE_NAME} WHERE {where_any_null}")
    missing_row_count = cursor.fetchone()["cnt"]
    print(f"\nSo ban ghi co chua it nhat 1 gia tri thieu: {missing_row_count}")

    cursor.execute(f"SELECT * FROM {TABLE_NAME} WHERE {where_any_null} ORDER BY id")
    rows_with_missing = cursor.fetchall()

    print("\nDanh sach cac ban ghi co gia tri thieu (day du thong tin):")
    if not rows_with_missing:
        print("- Khong co ban ghi nao bi thieu.")
    else:
        for row in rows_with_missing:
            print(row)

    cursor.close()
    connection.close()


if __name__ == "__main__":
    main()
