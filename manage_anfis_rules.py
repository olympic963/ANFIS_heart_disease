"""
Quan ly luat ANFIS:
- Parse luat tu Luật.txt
- Luu vao bang anfis_rules theo dang ma tran cot co dinh

Bang anfis_rules:
rule_no, age, trestbps, chol, thalach, oldpeak, consequent_text
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import mysql.connector

from db_config import DB_CONFIG

RULES_FILE = Path("Luật.txt")
RULES_TABLE = "anfis_rules"
NOT_USED = "Not used"


@dataclass
class ParsedRule:
    rule_no: int
    conditions: list[str]
    consequent_text: str


def parse_rules_file(path: Path) -> list[ParsedRule]:
    text = path.read_text(encoding="utf-8")
    chunks = [c.strip() for c in re.split(r"\n\s*\n", text) if c.strip()]
    out: list[ParsedRule] = []

    for chunk in chunks:
        lines = [ln.strip() for ln in chunk.splitlines() if ln.strip()]
        if not lines:
            continue
        m_no = re.search(r"Luật\s+(\d+)", lines[0])
        if not m_no:
            continue
        rule_no = int(m_no.group(1))

        conditions: list[str] = []
        consequent = ""
        for ln in lines[1:]:
            line_norm = ln.replace("IF ", "").replace("AND ", "")
            if line_norm.startswith("THEN "):
                consequent = line_norm.replace("THEN ", "").strip()
            else:
                conditions.append(line_norm.strip())

        out.append(ParsedRule(rule_no=rule_no, conditions=conditions, consequent_text=consequent))

    return sorted(out, key=lambda r: r.rule_no)


def map_rule_to_row(rule: ParsedRule) -> tuple:
    row_map = {
        "age": NOT_USED,
        "trestbps": NOT_USED,
        "chol": NOT_USED,
        "thalach": NOT_USED,
        "oldpeak": NOT_USED,
    }

    for cond in rule.conditions:
        m_fuzzy = re.match(r"([a-zA-Z0-9_]+)\s+is\s+([a-zA-Z]+)", cond)
        if m_fuzzy:
            var = m_fuzzy.group(1)
            label = m_fuzzy.group(2).lower()
            if var in row_map:
                row_map[var] = label
            continue

    return (
        rule.rule_no,
        row_map["age"],
        row_map["trestbps"],
        row_map["chol"],
        row_map["thalach"],
        row_map["oldpeak"],
        rule.consequent_text,
    )


def sync_rules_to_db(rules: list[ParsedRule]) -> None:
    conn = mysql.connector.connect(**DB_CONFIG)
    cur = conn.cursor()

    cur.execute(f"DROP TABLE IF EXISTS {RULES_TABLE}")
    cur.execute(
        f"""
        CREATE TABLE {RULES_TABLE} (
            rule_no INT PRIMARY KEY,
            age VARCHAR(32) NOT NULL,
            trestbps VARCHAR(32) NOT NULL,
            chol VARCHAR(32) NOT NULL,
            thalach VARCHAR(32) NOT NULL,
            oldpeak VARCHAR(32) NOT NULL,
            consequent_text TEXT NOT NULL
        )
        """
    )

    cur.executemany(
        f"""
        INSERT INTO {RULES_TABLE} (
            rule_no, age, trestbps, chol, thalach, oldpeak, consequent_text
        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
        [map_rule_to_row(r) for r in rules],
    )

    conn.commit()
    cur.close()
    conn.close()


def main() -> None:
    rules = parse_rules_file(RULES_FILE)
    if not rules:
        raise ValueError("Khong parse duoc luat nao tu Luật.txt")

    sync_rules_to_db(rules)
    print(f"Synced {len(rules)} rules to table {RULES_TABLE}.")


if __name__ == "__main__":
    main()
