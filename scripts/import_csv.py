"""Import generated genealogy CSV files with PostgreSQL COPY."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv


COPY_ORDER = [
    ("users", ["id", "username", "email", "password_hash"]),
    ("genealogies", ["id", "name", "surname", "revision_year", "description", "owner_id"]),
    ("genealogy_collaborators", ["id", "genealogy_id", "user_id", "role"]),
    ("members", ["id", "genealogy_id", "name", "gender", "birth_year", "death_year", "biography", "generation_no"]),
    (
        "parent_child_relations",
        ["id", "genealogy_id", "parent_member_id", "child_member_id", "parent_role"],
    ),
    ("marriages", ["id", "genealogy_id", "spouse1_member_id", "spouse2_member_id", "married_year", "ended_year"]),
]


def database_url() -> str:
    load_dotenv()
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not configured")
    return url.replace("postgresql+psycopg://", "postgresql://", 1)


def copy_file(cursor, table: str, columns: list[str], csv_path: Path) -> None:
    column_sql = ", ".join(columns)
    with cursor.copy(f"COPY {table} ({column_sql}) FROM STDIN WITH (FORMAT CSV, HEADER TRUE)") as copy:
        with csv_path.open("r", encoding="utf-8", newline="") as handle:
            while chunk := handle.read(1024 * 1024):
                copy.write(chunk)


def reset_sequence(cursor, table: str) -> None:
    cursor.execute(
        """
        SELECT setval(
            pg_get_serial_sequence(%s, 'id'),
            COALESCE((SELECT MAX(id) FROM """ + table + """), 1),
            (SELECT MAX(id) FROM """ + table + """) IS NOT NULL
        )
        """,
        (table,),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Import generated CSV files into PostgreSQL.")
    parser.add_argument("--input-dir", default="data/generated", help="Directory containing generated CSV files.")
    parser.add_argument("--truncate", action="store_true", help="Truncate target tables before import.")
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    with psycopg.connect(database_url()) as conn:
        with conn.cursor() as cursor:
            if args.truncate:
                cursor.execute(
                    """
                    TRUNCATE
                        parent_child_relations,
                        marriages,
                        genealogy_collaborators,
                        members,
                        genealogies,
                        users
                    RESTART IDENTITY CASCADE
                    """
                )

            for table, columns in COPY_ORDER:
                csv_path = input_dir / f"{table}.csv"
                if not csv_path.exists():
                    raise FileNotFoundError(csv_path)
                copy_file(cursor, table, columns, csv_path)
                print(f"imported {csv_path}")

            for table, _columns in COPY_ORDER:
                reset_sequence(cursor, table)

    print("CSV import complete.")


if __name__ == "__main__":
    main()
