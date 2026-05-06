from __future__ import annotations

import csv
from pathlib import Path
from typing import Callable

import mysql.connector

from db_config import DB_CONFIG

DATABASE_NAME = "heart_disease"
TABLE_NAME = "processed_heart_disease"

PROCESSED_DIR = Path("../data") / "processed data"
SOURCE_FILES = [
    "processed.cleveland.data",
    "processed.hungarian.data",
    "processed.switzerland.data",
    "processed.va.data",
]


def parse_int(value: str) -> int | None:
    cleaned = value.strip()
    if cleaned == "?" or cleaned == "":
        return None
    # Some files store integer features with trailing ".0".
    return int(float(cleaned))


def parse_float(value: str) -> float | None:
    cleaned = value.strip()
    if cleaned == "?" or cleaned == "":
        return None
    return float(cleaned)


PARSERS: list[Callable[[str], int | float | None]] = [
    parse_int,   # age
    parse_int,   # sex
    parse_int,   # cp
    parse_float, # trestbps
    parse_float, # chol
    parse_int,   # fbs
    parse_int,   # restecg
    parse_float, # thalach
    parse_int,   # exang
    parse_float, # oldpeak (continuous measurement)
    parse_int,   # slope
    parse_int,   # ca
    parse_int,   # thal
    parse_int,   # num (target)
]


def read_rows() -> list[tuple]:
    rows: list[tuple] = []

    for file_name in SOURCE_FILES:
        file_path = PROCESSED_DIR / file_name
        with file_path.open("r", encoding="utf-8") as file:
            reader = csv.reader(file)
            for line_idx, record in enumerate(reader, start=1):
                if not record:
                    continue
                if len(record) != 14:
                    raise ValueError(
                        f"{file_name} line {line_idx} has {len(record)} columns, expected 14."
                    )

                parsed = [parser(value) for parser, value in zip(PARSERS, record)]
                rows.append((file_name, line_idx, *parsed))

    return rows


def main() -> None:
    base_config = {k: v for k, v in DB_CONFIG.items() if k != "database"}
    connection = mysql.connector.connect(**base_config)
    cursor = connection.cursor()

    cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DATABASE_NAME}")
    cursor.execute(f"USE {DATABASE_NAME}")

    cursor.execute(f"DROP TABLE IF EXISTS {TABLE_NAME}")

    cursor.execute(
        f"""
        CREATE TABLE {TABLE_NAME} (
            id INT AUTO_INCREMENT PRIMARY KEY,
            source_file VARCHAR(64) NOT NULL,
            source_line INT NOT NULL,
            age INT NULL,
            sex TINYINT NULL,
            cp TINYINT NULL,
            trestbps DOUBLE NULL,
            chol DOUBLE NULL,
            fbs TINYINT NULL,
            restecg TINYINT NULL,
            thalach DOUBLE NULL,
            exang TINYINT NULL,
            oldpeak DOUBLE NULL,
            slope TINYINT NULL,
            ca TINYINT NULL,
            thal TINYINT NULL,
            num TINYINT NOT NULL
        )
        """
    )

    rows = read_rows()
    cursor.executemany(
        f"""
        INSERT INTO {TABLE_NAME} (
            source_file, source_line, age, sex, cp, trestbps, chol, fbs, restecg,
            thalach, exang, oldpeak, slope, ca, thal, num
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        )
        """,
        rows,
    )

    connection.commit()

    cursor.execute(f"SELECT COUNT(*) FROM {TABLE_NAME}")
    total = cursor.fetchone()[0]

    print(f"Imported {total} rows into {DATABASE_NAME}.{TABLE_NAME}.")

    cursor.close()
    connection.close()


if __name__ == "__main__":
    main()
