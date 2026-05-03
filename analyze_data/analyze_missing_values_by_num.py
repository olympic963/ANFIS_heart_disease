"""
Chi dung ban ghi day du tat ca 14 thuoc tinh.

Voi moi cot co gia tri thieu (trong tong 920 dong), tren tap day du (299 dong):
theo ting num, in phan bo giong logic cu:
  - bien roi rac: dem so ban ghi theo tung ma trong mien mo ta
  - bien lien tuc: min / max / trung binh ( trong con num do )

Chi doc read_rows() nhu import_processed_to_mysql.

r[2]=age ... r[15]=num
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from import_processed_to_mysql import read_rows

_IDX_FIRST_ATTR = 2
_IDX_LAST_ATTR = 15  # num
_IDX_NUM = 15


@dataclass(frozen=True)
class FeatureSpec:
    name: str
    idx: int
    kind: Literal["discrete", "continuous"]
    domain: tuple[int, ...] | None


FEATURES: tuple[FeatureSpec, ...] = (
    FeatureSpec("age", 2, "continuous", None),
    FeatureSpec("sex", 3, "discrete", (0, 1)),
    FeatureSpec("cp", 4, "discrete", (1, 2, 3, 4)),
    FeatureSpec("trestbps", 5, "continuous", None),
    FeatureSpec("chol", 6, "continuous", None),
    FeatureSpec("fbs", 7, "discrete", (0, 1)),
    FeatureSpec("restecg", 8, "discrete", (0, 1, 2)),
    FeatureSpec("thalach", 9, "continuous", None),
    FeatureSpec("exang", 10, "discrete", (0, 1)),
    FeatureSpec("oldpeak", 11, "continuous", None),
    FeatureSpec("slope", 12, "discrete", (1, 2, 3)),
    FeatureSpec("ca", 13, "discrete", (0, 1, 2, 3)),
    FeatureSpec("thal", 14, "discrete", (3, 6, 7)),
)


def _to_int(value: int | float | None) -> int | None:
    if value is None:
        return None
    fv = float(value)
    ri = round(fv)
    if abs(fv - ri) > 1e-9:
        return None
    return int(ri)


def _is_fully_observed(row: tuple) -> bool:
    return all(row[i] is not None for i in range(_IDX_FIRST_ATTR, _IDX_LAST_ATTR + 1))


def _count_rows_with_value(rows: list[tuple], idx: int, wanted: int) -> int:
    n = 0
    for r in rows:
        iv = _to_int(r[idx])
        if iv == wanted:
            n += 1
    return n


def _missing_count(rows: list[tuple], idx: int) -> int:
    return sum(1 for r in rows if r[idx] is None)


def _continuous_stats(rows: list[tuple], idx: int) -> tuple[float, float, float] | None:
    vals = [float(r[idx]) for r in rows]
    if not vals:
        return None
    return min(vals), max(vals), sum(vals) / len(vals)


def main() -> None:
    rows = read_rows()
    complete = [r for r in rows if _is_fully_observed(r)]

    print(f"Tong so ban ghi (4 file processed): {len(rows)}")
    print(f"Ban ghi day du tat ca thuoc tinh: {len(complete)}")
    print()

    # Chi cac cot co it nhat 1 gia tri thieu trong toan bo tap (tru num)
    with_missing = [
        f
        for f in FEATURES
        if _missing_count(rows, f.idx) > 0 and f.idx != _IDX_NUM
    ]

    print("Cac thuoc tinh co gia tri thieu trong toan bo tap (tru num):")
    for f in with_missing:
        print(f"  - {f.name}: {_missing_count(rows, f.idx)} dong thieu")
    print()

    nums_present = sorted(
        int(x)
        for x in {_to_int(r[_IDX_NUM]) for r in complete}
        if x is not None
    )

    for num in nums_present:
        subset = [r for r in complete if _to_int(r[_IDX_NUM]) == num]
        print(f"=== num = {num} (so ban ghi trong tap day du: {len(subset)}) ===")

        for f in with_missing:
            print(f"  [{f.name}]")

            if f.kind == "discrete":
                assert f.domain is not None
                for v in f.domain:
                    n = _count_rows_with_value(subset, f.idx, v)
                    print(f"    {f.name} = {v}: {n} ban ghi")

            else:
                stats = _continuous_stats(subset, f.idx)
                if stats is None:
                    print("    (khong co du lieu)")
                else:
                    lo, hi, mean = stats
                    print(f"    min = {lo}, max = {hi}, trung_binh = {mean:.4f}")

        print()


if __name__ == "__main__":
    main()
