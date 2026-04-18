"""
Voi cac ban ghi co day du slope, ca, thal (khong '?'),
in tap gia tri duy nhat va khoang min-max cua tung thuoc tinh theo tung gia tri num.
"""
from __future__ import annotations

from collections import defaultdict
from import_processed_to_mysql import read_rows

# read_rows(): (source_file, source_line, age, sex, cp, trestbps, chol, fbs,
#               restecg, thalach, exang, oldpeak, slope, ca, thal, num)
_IDX_SLOPE = 12
_IDX_CA = 13
_IDX_THAL = 14
_IDX_NUM = 15


def main() -> None:
    rows = read_rows()

    complete = [
        r
        for r in rows
        if r[_IDX_SLOPE] is not None and r[_IDX_CA] is not None and r[_IDX_THAL] is not None
    ]

    print(f"Tong so ban ghi: {len(rows)}")
    print(f"Ban ghi day du slope, ca, thal: {len(complete)}")
    print()

    by_file: dict[str, int] = defaultdict(int)
    for r in complete:
        by_file[r[0]] += 1
    print("So ban ghi day du theo tep nguon:")
    for fn in sorted(by_file.keys()):
        print(f"  - {fn}: {by_file[fn]}")
    print()

    by_num: dict[int, dict[str, set[int]]] = defaultdict(
        lambda: {"slope": set(), "ca": set(), "thal": set()}
    )
    for r in complete:
        num = r[_IDX_NUM]
        assert num is not None
        by_num[num]["slope"].add(r[_IDX_SLOPE])
        by_num[num]["ca"].add(r[_IDX_CA])
        by_num[num]["thal"].add(r[_IDX_THAL])

    for num in sorted(by_num.keys()):
        d = by_num[num]
        n_count = sum(1 for r in complete if r[_IDX_NUM] == num)
        print(f"=== num = {num} (so ban ghi trong tap day du: {n_count}) ===")
        for label, key in [("slope", "slope"), ("ca", "ca"), ("thal", "thal")]:
            vals = sorted(d[key])
            print(f"  {label}: gia tri duy nhat = {vals}")
            print(f"    khoang [{min(vals)}, {max(vals)}], so gia tri khac nhau = {len(vals)}")
        print()


if __name__ == "__main__":
    main()
