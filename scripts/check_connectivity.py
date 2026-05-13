"""Check graph connectivity between members 114 and 514."""
import sys
sys.path.insert(0, '.')
from dotenv import load_dotenv; load_dotenv()
from app import create_app
from app.extensions import db
from sqlalchemy import text

app = create_app()
with app.app_context():
    # How many connected components / reachable from 114
    sql = """
        WITH RECURSIVE edges AS NOT MATERIALIZED (
            SELECT parent_member_id AS from_id, child_member_id AS to_id FROM parent_child_relations WHERE genealogy_id=1
            UNION ALL
            SELECT child_member_id, parent_member_id FROM parent_child_relations WHERE genealogy_id=1
            UNION ALL
            SELECT spouse1_member_id, spouse2_member_id FROM marriages WHERE genealogy_id=1
            UNION ALL
            SELECT spouse2_member_id, spouse1_member_id FROM marriages WHERE genealogy_id=1
        ),
        walk AS (
            SELECT 114 AS member_id, 0 AS depth
            UNION
            SELECT e.to_id, walk.depth + 1
            FROM walk JOIN edges e ON e.from_id = walk.member_id
            WHERE walk.depth < 30
        ) CYCLE member_id SET is_cycle USING cycle_path
        SELECT COUNT(DISTINCT member_id) FROM walk WHERE NOT is_cycle
    """
    r = db.session.execute(text(sql)).fetchone()
    print(f"Reachable from 114: {r[0]} nodes", flush=True)

    # Distance to 514
    sql2 = """
        WITH RECURSIVE edges AS NOT MATERIALIZED (
            SELECT parent_member_id AS from_id, child_member_id AS to_id FROM parent_child_relations WHERE genealogy_id=1
            UNION ALL
            SELECT child_member_id, parent_member_id FROM parent_child_relations WHERE genealogy_id=1
            UNION ALL
            SELECT spouse1_member_id, spouse2_member_id FROM marriages WHERE genealogy_id=1
            UNION ALL
            SELECT spouse2_member_id, spouse1_member_id FROM marriages WHERE genealogy_id=1
        ),
        walk AS (
            SELECT 114 AS member_id, 0 AS depth
            UNION
            SELECT e.to_id, walk.depth + 1
            FROM walk JOIN edges e ON e.from_id = walk.member_id
            WHERE walk.depth < 30
        ) CYCLE member_id SET is_cycle USING cycle_path
        SELECT MIN(depth) FROM walk WHERE member_id = 514 AND NOT is_cycle
    """
    r = db.session.execute(text(sql2)).fetchone()
    print(f"Distance from 114 to 514: {r[0]}", flush=True)

    # Member info
    r = db.session.execute(text(
        "SELECT id, name, generation_no, gender, birth_year FROM members WHERE id IN (114, 514)"
    )).fetchall()
    for row in r:
        print(f"  member {row[0]}: {row[1]}, gen={row[2]}, gender={row[3]}, birth={row[4]}", flush=True)

    # Root nodes count
    r = db.session.execute(text("""
        SELECT COUNT(DISTINCT parent_member_id) FROM parent_child_relations WHERE genealogy_id=1
        AND parent_member_id NOT IN (
            SELECT child_member_id FROM parent_child_relations WHERE genealogy_id=1
        )
    """)).fetchone()
    print(f"Root nodes (no parents): {r[0]}", flush=True)

    # Distribution of graph component sizes
    r = db.session.execute(text("""
        SELECT generation_no, COUNT(*) FROM members WHERE genealogy_id=1 GROUP BY generation_no ORDER BY generation_no
    """)).fetchall()
    for row in r:
        print(f"  generation={row[0]}: {row[1]} members", flush=True)

    print("CHECK COMPLETE", flush=True)