"""Test UNION ALL vs UNION in BFS walk CTE."""
import sys, time
sys.path.insert(0, '.')
from dotenv import load_dotenv; load_dotenv()
from app import create_app
from app.extensions import db
from sqlalchemy import text

app = create_app()
with app.app_context():
    gid, start_id, end_id = 1, 114, 514

    edge_sql = """
        SELECT parent_member_id AS from_id, child_member_id AS to_id
        FROM parent_child_relations WHERE genealogy_id = :gid
        UNION ALL SELECT child_member_id, parent_member_id
        FROM parent_child_relations WHERE genealogy_id = :gid
        UNION ALL SELECT spouse1_member_id, spouse2_member_id
        FROM marriages WHERE genealogy_id = :gid
        UNION ALL SELECT spouse2_member_id, spouse1_member_id
        FROM marriages WHERE genealogy_id = :gid
    """

    variants = [
        {
            "label": "UNION ALL walk + GROUP BY at end",
            "walk_mode": "UNION ALL",
            "select": "member_id, MIN(depth) FROM walk WHERE NOT is_cycle GROUP BY member_id",
        },
        {
            "label": "UNION walk (dedup per level)",
            "walk_mode": "UNION",
            "select": "member_id, MIN(depth) FROM walk WHERE NOT is_cycle GROUP BY member_id",
        },
    ]

    for variant in variants:
        print(f"\n{'='*60}", flush=True)
        print(f"Testing: {variant['label']}", flush=True)
        
        for root_id, label in [(start_id, "FWD(114)"), (end_id, "REV(514)")]:
            for max_d in [5, 6, 7, 8, 9, 10]:
                sql = f"""
                    WITH RECURSIVE edges AS NOT MATERIALIZED ({edge_sql}),
                    walk AS (
                        SELECT CAST(:root_id AS INTEGER) AS member_id, 0 AS depth
                        {variant['walk_mode']}
                        SELECT e.to_id, walk.depth + 1
                        FROM walk JOIN edges e ON e.from_id = walk.member_id
                        WHERE walk.depth < {max_d}
                    ) CYCLE member_id SET is_cycle USING cycle_path
                    SELECT {variant['select']}
                """
                t0 = time.perf_counter()
                rows = db.session.execute(text(sql), {"gid": gid, "root_id": root_id}).fetchall()
                elapsed = (time.perf_counter() - t0) * 1000
                n = len(rows)
                max_found = max(r[1] for r in rows) if rows else 0
                print(f"  {label} depth<{max_d}: {elapsed:6.0f}ms  unique_members={n:>6}  max_depth_found={max_found}", flush=True)
                if elapsed > 15000:
                    print(f"    (stopping at {max_d} due to >15s)", flush=True)
                    break

    print("\nTEST COMPLETE", flush=True)