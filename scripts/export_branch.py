"""Export a member branch to CSV files.

The branch contains the root member, all recursive descendants, parent-child
relations inside that set, and marriages where both spouses are in the set.
"""

from __future__ import annotations

import argparse
import csv
import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row


def database_url() -> str:
    load_dotenv()
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not configured")
    return url.replace("postgresql+psycopg://", "postgresql://", 1)


def write_csv(path: Path, rows, columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row[column] for column in columns})


def main() -> None:
    parser = argparse.ArgumentParser(description="Export one descendant branch.")
    parser.add_argument("--member-id", type=int, required=True, help="Root member id.")
    parser.add_argument("--output-dir", default="data/branch_export", help="Output directory.")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    with psycopg.connect(database_url()) as conn:
        with conn.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                """
                WITH RECURSIVE branch AS (
                    SELECT id, genealogy_id, 1 AS depth
                    FROM members
                    WHERE id = %s
                    UNION
                    SELECT child.id, child.genealogy_id, branch.depth + 1
                    FROM branch
                    JOIN parent_child_relations rel ON rel.parent_member_id = branch.id
                    JOIN members child ON child.id = rel.child_member_id
                    WHERE branch.depth < 100
                )
                SELECT m.id, m.genealogy_id, m.name, m.gender, m.birth_year, m.death_year, m.biography, m.generation_no
                FROM members m
                JOIN branch ON branch.id = m.id
                ORDER BY m.generation_no, m.id
                """,
                (args.member_id,),
            )
            members = cursor.fetchall()
            if not members:
                raise RuntimeError(f"member {args.member_id} not found")

            member_ids = [row["id"] for row in members]
            cursor.execute(
                """
                SELECT id, genealogy_id, parent_member_id, child_member_id, parent_role
                FROM parent_child_relations
                WHERE parent_member_id = ANY(%s) AND child_member_id = ANY(%s)
                ORDER BY id
                """,
                (member_ids, member_ids),
            )
            parent_child_relations = cursor.fetchall()

            cursor.execute(
                """
                SELECT id, genealogy_id, spouse1_member_id, spouse2_member_id, married_year, ended_year
                FROM marriages
                WHERE spouse1_member_id = ANY(%s) AND spouse2_member_id = ANY(%s)
                ORDER BY id
                """,
                (member_ids, member_ids),
            )
            marriages = cursor.fetchall()

    write_csv(
        output_dir / "members.csv",
        members,
        ["id", "genealogy_id", "name", "gender", "birth_year", "death_year", "biography", "generation_no"],
    )
    write_csv(
        output_dir / "parent_child_relations.csv",
        parent_child_relations,
        ["id", "genealogy_id", "parent_member_id", "child_member_id", "parent_role"],
    )
    write_csv(
        output_dir / "marriages.csv",
        marriages,
        ["id", "genealogy_id", "spouse1_member_id", "spouse2_member_id", "married_year", "ended_year"],
    )

    print(f"Exported branch rooted at member {args.member_id} to {output_dir.resolve()}")
    print(f"- members: {len(members)}")
    print(f"- parent_child_relations: {len(parent_child_relations)}")
    print(f"- marriages: {len(marriages)}")


if __name__ == "__main__":
    main()
