"""
Phan tich outlier theo trung binh mau (x_bar) va do lech chuan mau (s)
cho cac thuoc tinh:
age, trestbps, chol, thalach, oldpeak.

Nguong outlier: [x_bar - 2*s, x_bar + 2*s]
Du lieu lay tu bang heart_disease_missing_processed.
"""
from __future__ import annotations

import math

import mysql.connector

from db_config import DB_CONFIG

TABLE_NAME = "heart_disease_missing_processed"
FEATURES = ("age", "trestbps", "chol", "thalach", "oldpeak")


def main() -> None:
    connection = mysql.connector.connect(**DB_CONFIG)
    cursor = connection.cursor(dictionary=True)

    cursor.execute(
        f"""
        SELECT id, age, trestbps, chol, thalach, oldpeak
        FROM {TABLE_NAME}
        ORDER BY id
        """
    )
    rows = cursor.fetchall()

    if not rows:
        print(f"Bang {TABLE_NAME} khong co du lieu.")
        cursor.close()
        connection.close()
        return

    outlier_ids_any: set[int] = set()

    print(f"Tong so ban ghi: {len(rows)}")
    print()

    for feature in FEATURES:
        valid_rows = [r for r in rows if r[feature] is not None]
        values = [float(r[feature]) for r in valid_rows]
        if len(values) < 2:
            print(f"=== {feature} ===")
            print("Khong du du lieu hop le (khong NULL) de tinh do lech chuan mau.")
            print()
            continue
        n = len(values)
        x_bar = sum(values) / n
        s = math.sqrt(sum((v - x_bar) ** 2 for v in values) / (n - 1))

        lower = x_bar - 2 * s
        upper = x_bar + 2 * s

        outlier_ids = [
            int(r["id"])
            for r in valid_rows
            if float(r[feature]) < lower or float(r[feature]) > upper
        ]
        outlier_ids_any.update(outlier_ids)

        print(f"=== {feature} ===")
        print(f"So ban ghi co gia tri (khong NULL): {len(valid_rows)}")
        print(f"x_bar = {x_bar:.6f}")
        print(f"s = {s:.6f}")
        print(f"Khoang [x_bar - 2s, x_bar + 2s] = [{lower:.6f}, {upper:.6f}]")
        print(f"So ban ghi chua outlier cua {feature}: {len(outlier_ids)}")
        print()

    print("=== Tong hop ===")
    print(
        "So ban ghi chua it nhat 1 outlier "
        f"(tren bat ky thuoc tinh nao trong {FEATURES}): {len(outlier_ids_any)}"
    )

    cursor.close()
    connection.close()


if __name__ == "__main__":
    main()
