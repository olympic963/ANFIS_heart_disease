"""
Phan tich outlier bang boxplot (IQR) cho cac thuoc tinh:
age, trestbps, chol, thalach, oldpeak.

Du lieu lay tu bang heart_disease_missing_processed.
In:
- Q1, Q3, IQR
- can duoi, can tren theo [Q1 - 1.5*IQR, Q3 + 1.5*IQR]
- so ban ghi outlier cua tung thuoc tinh
- so ban ghi co it nhat 1 outlier o bat ky thuoc tinh nao
"""
from __future__ import annotations

import mysql.connector

from db_config import DB_CONFIG

TABLE_NAME = "heart_disease_missing_processed"
FEATURES = ("age", "trestbps", "chol", "thalach", "oldpeak")


def percentile(values: list[float], p: float) -> float:
    """Percentile with linear interpolation on sorted array (0 <= p <= 1)."""
    if not values:
        raise ValueError("Empty values.")
    if len(values) == 1:
        return values[0]

    arr = sorted(values)
    pos = p * (len(arr) - 1)
    low = int(pos)
    high = min(low + 1, len(arr) - 1)
    frac = pos - low
    return arr[low] + (arr[high] - arr[low]) * frac


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
        vals = [float(r[feature]) for r in valid_rows]
        if not vals:
            print(f"=== {feature} ===")
            print("Khong co gia tri hop le (tat ca la NULL), bo qua.")
            print()
            continue
        q1 = percentile(vals, 0.25)
        med = percentile(vals, 0.50)
        q3 = percentile(vals, 0.75)
        iqr = q3 - q1
        lower = q1 - 1.5 * iqr
        upper = q3 + 1.5 * iqr

        outlier_ids = [
            int(r["id"])
            for r in valid_rows
            if float(r[feature]) < lower or float(r[feature]) > upper
        ]
        outlier_ids_any.update(outlier_ids)

        print(f"=== {feature} ===")
        print(f"So ban ghi co gia tri (khong NULL): {len(valid_rows)}")
        print(f"Q1 = {q1:.6f}")
        print(f"Median = {med:.6f}")
        print(f"Q3 = {q3:.6f}")
        print(f"IQR = {iqr:.6f}")
        print(f"Can duoi = Q1 - 1.5*IQR = {lower:.6f}")
        print(f"Can tren = Q3 + 1.5*IQR = {upper:.6f}")
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
