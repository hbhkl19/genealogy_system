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


RELATIONSHIP_TRIGGER_SQL = """
DROP TRIGGER IF EXISTS trg_validate_parent_child_relation ON parent_child_relations;
DROP TRIGGER IF EXISTS trg_validate_marriage_relation ON marriages;
DROP TRIGGER IF EXISTS trg_validate_member_existing_relations ON members;

CREATE OR REPLACE FUNCTION validate_parent_child_relation()
RETURNS trigger AS $$
DECLARE
    parent_record members%ROWTYPE;
    child_record members%ROWTYPE;
BEGIN
    SELECT * INTO parent_record FROM members WHERE id = NEW.parent_member_id;
    SELECT * INTO child_record FROM members WHERE id = NEW.child_member_id;

    IF parent_record.id IS NULL OR child_record.id IS NULL THEN
        RAISE EXCEPTION 'parent or child member does not exist';
    END IF;

    IF child_record.genealogy_id <> NEW.genealogy_id THEN
        RAISE EXCEPTION 'child must belong to the same genealogy as the relation record';
    END IF;

    IF NEW.parent_role = 'father'
       AND parent_record.genealogy_id <> NEW.genealogy_id THEN
        RAISE EXCEPTION 'father must belong to the same genealogy as the child';
    END IF;

    IF parent_record.generation_no >= child_record.generation_no THEN
        RAISE EXCEPTION 'parent generation must be less than child generation';
    END IF;

    IF parent_record.birth_year IS NOT NULL
       AND child_record.birth_year IS NOT NULL
       AND parent_record.birth_year >= child_record.birth_year THEN
        RAISE EXCEPTION 'parent birth year must be earlier than child birth year';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION validate_marriage_relation()
RETURNS trigger AS $$
DECLARE
    spouse1_record members%ROWTYPE;
    spouse2_record members%ROWTYPE;
BEGIN
    SELECT * INTO spouse1_record FROM members WHERE id = NEW.spouse1_member_id;
    SELECT * INTO spouse2_record FROM members WHERE id = NEW.spouse2_member_id;

    IF spouse1_record.id IS NULL OR spouse2_record.id IS NULL THEN
        RAISE EXCEPTION 'spouse member does not exist';
    END IF;

    IF spouse1_record.genealogy_id = spouse2_record.genealogy_id THEN
        RAISE EXCEPTION 'spouses must belong to different genealogies';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION validate_member_existing_relations()
RETURNS trigger AS $$
DECLARE
    invalid_count integer;
BEGIN
    SELECT COUNT(*) INTO invalid_count
    FROM parent_child_relations rel
    JOIN members parent_member ON parent_member.id = rel.parent_member_id
    JOIN members child_member ON child_member.id = rel.child_member_id
    WHERE (rel.parent_member_id = NEW.id OR rel.child_member_id = NEW.id)
      AND (
          child_member.genealogy_id <> rel.genealogy_id
          OR (rel.parent_role = 'father' AND parent_member.genealogy_id <> rel.genealogy_id)
          OR parent_member.generation_no >= child_member.generation_no
          OR (
              parent_member.birth_year IS NOT NULL
              AND child_member.birth_year IS NOT NULL
              AND parent_member.birth_year >= child_member.birth_year
          )
      );

    IF invalid_count > 0 THEN
        RAISE EXCEPTION 'member update would violate existing parent-child relations';
    END IF;

    SELECT COUNT(*) INTO invalid_count
    FROM marriages marriage
    JOIN members spouse1_member ON spouse1_member.id = marriage.spouse1_member_id
    JOIN members spouse2_member ON spouse2_member.id = marriage.spouse2_member_id
    WHERE (marriage.spouse1_member_id = NEW.id OR marriage.spouse2_member_id = NEW.id)
      AND spouse1_member.genealogy_id = spouse2_member.genealogy_id;

    IF invalid_count > 0 THEN
        RAISE EXCEPTION 'member update would violate existing marriage relations';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_validate_parent_child_relation
BEFORE INSERT OR UPDATE ON parent_child_relations
FOR EACH ROW
EXECUTE FUNCTION validate_parent_child_relation();

CREATE TRIGGER trg_validate_marriage_relation
BEFORE INSERT OR UPDATE ON marriages
FOR EACH ROW
EXECUTE FUNCTION validate_marriage_relation();

CREATE TRIGGER trg_validate_member_existing_relations
AFTER UPDATE OF genealogy_id, birth_year, generation_no ON members
FOR EACH ROW
EXECUTE FUNCTION validate_member_existing_relations();
"""


def database_url() -> str:
    load_dotenv()
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not configured")
    return url.replace("postgresql+psycopg://", "postgresql://", 1)


def refresh_relationship_triggers(cursor) -> None:
    cursor.execute(RELATIONSHIP_TRIGGER_SQL)
    print("refreshed relationship integrity triggers")


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
    parser.add_argument("--skip-users", action="store_true", help="Skip users.csv (existing users already in DB).")
    parser.add_argument("--append", action="store_true", default=True,
                        help="Append mode: skip missing files, don't truncate (default).")
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

            refresh_relationship_triggers(cursor)

            for table, columns in COPY_ORDER:
                if args.skip_users and table == "users":
                    print(f"skipped users (--skip-users)")
                    continue
                csv_path = input_dir / f"{table}.csv"
                if not csv_path.exists():
                    if args.append:
                        print(f"skipped {csv_path} (file not found, append mode)")
                        continue
                    raise FileNotFoundError(csv_path)
                copy_file(cursor, table, columns, csv_path)
                print(f"imported {csv_path}")

            for table, _columns in COPY_ORDER:
                csv_path = input_dir / f"{table}.csv"
                if not csv_path.exists():
                    continue
                reset_sequence(cursor, table)

    print("CSV import complete.")


if __name__ == "__main__":
    main()
