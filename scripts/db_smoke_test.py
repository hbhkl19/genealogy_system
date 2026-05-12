"""Run database acceptance checks for the genealogy lab."""

from __future__ import annotations

import os

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row


CHECKS = [
    ("genealogy_count", "SELECT COUNT(*) AS value FROM genealogies"),
    ("member_count", "SELECT COUNT(*) AS value FROM members"),
    (
        "max_members_in_one_genealogy",
        """
        SELECT COALESCE(MAX(cnt), 0) AS value
        FROM (
            SELECT genealogy_id, COUNT(*) AS cnt
            FROM members
            GROUP BY genealogy_id
        ) t
        """,
    ),
    ("max_generation_no", "SELECT COALESCE(MAX(generation_no), 0) AS value FROM members"),
    (
        "members_without_edge",
        """
        SELECT COUNT(*) AS value
        FROM members m
        WHERE NOT EXISTS (
            SELECT 1 FROM parent_child_relations p
            WHERE p.parent_member_id = m.id OR p.child_member_id = m.id
        )
        AND NOT EXISTS (
            SELECT 1 FROM marriages s
            WHERE s.spouse1_member_id = m.id OR s.spouse2_member_id = m.id
        )
        """,
    ),
]


def database_url() -> str:
    load_dotenv()
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not configured")
    return url.replace("postgresql+psycopg://", "postgresql://", 1)


def main() -> None:
    with psycopg.connect(database_url(), row_factory=dict_row) as conn:
        with conn.cursor() as cursor:
            results = {}
            for name, sql in CHECKS:
                cursor.execute(sql)
                results[name] = cursor.fetchone()["value"]

    print("Database smoke test:")
    for name, value in results.items():
        print(f"- {name}: {value}")

    pass_large_dataset = (
        results["genealogy_count"] >= 10
        and results["member_count"] >= 100000
        and results["max_members_in_one_genealogy"] >= 50000
        and results["max_generation_no"] >= 30
        and results["members_without_edge"] <= results["member_count"] * 0.01
    )
    print(f"- large_dataset_acceptance: {'PASS' if pass_large_dataset else 'PENDING'}")


if __name__ == "__main__":
    main()
