"""Generate EXPLAIN comparisons for the four-generation descendant query.

The no-index plan is measured inside a transaction and rolled back, so existing
indexes are restored automatically.
"""

from __future__ import annotations

import argparse
import os
import re
from pathlib import Path

import psycopg
from dotenv import load_dotenv


INDEX_SQL = [
    "ix_parent_child_genealogy_parent",
    "ix_parent_child_genealogy_child",
    "ix_parent_child_relations_parent_member_id",
    "ix_parent_child_relations_child_member_id",
    "ix_parent_child_relations_genealogy_id",
]

FOUR_GENERATION_QUERY = """
WITH RECURSIVE descendants AS (
    SELECT child_member_id AS member_id, 1 AS depth
    FROM parent_child_relations
    WHERE parent_member_id = %(member_id)s
    UNION ALL
    SELECT p.child_member_id, d.depth + 1
    FROM parent_child_relations p
    JOIN descendants d ON p.parent_member_id = d.member_id
    WHERE d.depth < 4
)
SELECT m.id, m.name, m.generation_no, descendants.depth
FROM descendants
JOIN members m ON m.id = descendants.member_id
ORDER BY descendants.depth, m.id
"""


def database_url() -> str:
    load_dotenv()
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not configured")
    return url.replace("postgresql+psycopg://", "postgresql://", 1)


def find_default_member(cursor) -> int | None:
    cursor.execute(
        """
        SELECT parent_member_id
        FROM parent_child_relations
        GROUP BY parent_member_id
        ORDER BY COUNT(*) DESC, parent_member_id
        LIMIT 1
        """
    )
    row = cursor.fetchone()
    return row[0] if row else None


def explain(cursor, member_id: int) -> str:
    cursor.execute(
        "EXPLAIN (ANALYZE, BUFFERS) " + FOUR_GENERATION_QUERY,
        {"member_id": member_id},
    )
    return "\n".join(row[0] for row in cursor.fetchall())


def execution_time(plan: str) -> str:
    match = re.search(r"Execution Time: ([0-9.]+ ms)", plan)
    return match.group(1) if match else "unknown"


def write_report(output: Path, member_id: int, no_index_plan: str, indexed_plan: str) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        f"""# 四代查询性能对比

查询成员 ID：`{member_id}`

| 场景 | Execution Time |
| --- | --- |
| 临时移除索引 | {execution_time(no_index_plan)} |
| 使用索引 | {execution_time(indexed_plan)} |

## 临时移除索引执行计划

```text
{no_index_plan}
```

## 使用索引执行计划

```text
{indexed_plan}
```
""",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run EXPLAIN comparison for four-generation query.")
    parser.add_argument("--member-id", type=int, help="Root member id for the query.")
    parser.add_argument("--output", default="docs/performance_results.md", help="Markdown report path.")
    args = parser.parse_args()

    with psycopg.connect(database_url(), autocommit=True) as conn:
        with conn.cursor() as cursor:
            member_id = args.member_id or find_default_member(cursor)
            if member_id is None:
                raise RuntimeError("No parent-child data found. Import or create data first.")

            cursor.execute("BEGIN")
            try:
                for index_name in INDEX_SQL:
                    cursor.execute(f"DROP INDEX IF EXISTS {index_name}")
                no_index_plan = explain(cursor, member_id)
            finally:
                cursor.execute("ROLLBACK")

            indexed_plan = explain(cursor, member_id)

    output = Path(args.output)
    write_report(output, member_id, no_index_plan, indexed_plan)
    print(f"Performance report written to {output.resolve()}")
    print(f"- without indexes: {execution_time(no_index_plan)}")
    print(f"- with indexes: {execution_time(indexed_plan)}")


if __name__ == "__main__":
    main()
