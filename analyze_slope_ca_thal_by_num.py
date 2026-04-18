"""
Tan so (so ban ghi) theo ting gia tri trong mien mo ta tai lieu cho 3 thuoc tinh
bi thieu nhieu nhat: slope, ca, thal.
Du lieu doc qua read_rows() giong import_processed_to_mysql.
"""
from __future__ import annotations

from dataclasses import dataclass
from import_processed_to_mysql import read_rows

# read_rows(): (source_file, source_line, age, sex, cp, trestbps, chol, fbs,
#               restecg, thalach, exang, oldpeak, slope, ca, thal, num)


@dataclass(frozen=True)
class DiscreteAttr:
    name: str
    idx: int
    domain: tuple[int, ...]


ATTRS: tuple[DiscreteAttr, ...] = (
    DiscreteAttr("slope", 12, (1, 2, 3)),
    DiscreteAttr("ca", 13, (0, 1, 2, 3)),
    DiscreteAttr("thal", 14, (3, 6, 7)),
)


def _to_int_category(value: int | float | None) -> int | None:
    if value is None:
        return None
    fv = float(value)
    ri = round(fv)
    if abs(fv - ri) > 1e-9:
        return None
    return int(ri)


def count_by_domain(
    rows: list[tuple],
    attr: DiscreteAttr,
) -> tuple[dict[int, int], int, int]:
    """Tra ve (dem theo tung gia tri trong mien, so thieu, so ngoai mien)."""
    domain_set = set(attr.domain)
    counts = {v: 0 for v in attr.domain}
    missing = 0
    other = 0

    for r in rows:
        raw = r[attr.idx]
        if raw is None:
            missing += 1
            continue
        cat = _to_int_category(raw)
        if cat is None or cat not in domain_set:
            other += 1
        else:
            counts[cat] += 1

    return counts, missing, other


def print_discrete_block(rows: list[tuple], attr: DiscreteAttr) -> None:
    counts, missing, other = count_by_domain(rows, attr)
    print(f"--- {attr.name} ---")
    print(f"  Mien mo ta: {list(attr.domain)}")
    total_in_domain = sum(counts.values())
    for v in attr.domain:
        print(f"    {attr.name} = {v}: {counts[v]} ban ghi")
    print(f"  Tong ban ghi co {attr.name} trong mien: {total_in_domain}")
    print(f"  Gia tri thieu (?): {missing}")
    if other:
        print(f"  Gia tri ngoai mien (khong nap vao bang): {other}")
    print()


def main() -> None:
    rows = read_rows()
    n = len(rows)

    print(f"Tong so ban ghi (4 file processed): {n}")
    print()
    print("Tan so theo mien gia tri: slope, ca, thal (theo tai lieu mo ta)")
    print()

    for attr in ATTRS:
        print_discrete_block(rows, attr)


if __name__ == "__main__":
    main()
