"""Deeper analysis: check index usage and query execution patterns."""
import sys
sys.path.insert(0, '.')
from dotenv import load_dotenv; load_dotenv()
from app import create_app
from app.extensions import db
from sqlalchemy import text

app = create_app()
with app.app_context():
    gid, start_id, end_id = 1, 114, 514
    params = {"genealogy_id": gid, "start_id": start_id, "end_id": end_id}

    # A: Edge query performance (how fast is scanning ALL edges?)
    print("=" * 60, flush=True)
    print("A. RAW EDGE QUERY PERFORMANCE", flush=True)
    edge_sql = """
        SELECT parent_member_id AS from_id, child_member_id AS to_id FROM parent_child_relations WHERE genealogy_id = 1
        UNION ALL
        SELECT child_member_id, parent_member_id FROM parent_child_relations WHERE genealogy_id = 1
        UNION ALL
        SELECT spouse1_member_id, spouse2_member_id FROM marriages WHERE genealogy_id = 1
        UNION ALL
        SELECT spouse2_member_id, spouse1_member_id FROM marriages WHERE genealogy_id = 1
    """
    import time
    t0 = time.perf_counter()
    r = db.session.execute(text("SELECT COUNT(*) FROM (" + edge_sql + ") t")).fetchone()
    t1 = time.perf_counter()
    print(f"  Total edges: {r[0]}, Time: {(t1-t0)*1000:.0f}ms", flush=True)

    # B: Check if starting from a specific node is faster (point lookup vs scan)
    print(flush=True)
    print("=" * 60, flush=True)
    print("B. POINT LOOKUP vs FULL SCAN for neighbors of specific node", flush=True)
    
    # Point lookup using composite indexes
    point_sql = """
        SELECT parent_member_id AS to_id FROM parent_child_relations WHERE genealogy_id=1 AND child_member_id = 114
        UNION ALL
        SELECT child_member_id FROM parent_child_relations WHERE genealogy_id=1 AND parent_member_id = 114
        UNION ALL
        SELECT spouse2_member_id FROM marriages WHERE genealogy_id=1 AND spouse1_member_id = 114
        UNION ALL
        SELECT spouse1_member_id FROM marriages WHERE genealogy_id=1 AND spouse2_member_id = 114
    """
    t0 = time.perf_counter()
    rows = db.session.execute(text(point_sql)).fetchall()
    t1 = time.perf_counter()
    print(f"  Node 114 neighbors: {[r[0] for r in rows]}, Time: {(t1-t0)*1000:.3f}ms", flush=True)

    # C: Test walk with DISTINCT ON member_id at each level (if UNION helps)
    print(flush=True)
    print("=" * 60, flush=True)
    print("C. WALK CTE: UNION ALL vs UNION (per level)", flush=True)
    
    for mode in ["UNION ALL", "UNION"]:
        walk_sql = f"""
            WITH RECURSIVE edges AS NOT MATERIALIZED (
                SELECT parent_member_id AS from_id, child_member_id AS to_id FROM parent_child_relations WHERE genealogy_id = 1
                UNION ALL
                SELECT child_member_id, parent_member_id FROM parent_child_relations WHERE genealogy_id = 1
                UNION ALL
                SELECT spouse1_member_id, spouse2_member_id FROM marriages WHERE genealogy_id = 1
                UNION ALL
                SELECT spouse2_member_id, spouse1_member_id FROM marriages WHERE genealogy_id = 1
            ),
            walk AS (
                SELECT 114 AS member_id, 0 AS depth
                {mode}
                SELECT e.to_id, walk.depth + 1
                FROM walk JOIN edges e ON e.from_id = walk.member_id
                WHERE walk.depth < 8
            ) CYCLE member_id SET is_cycle USING cycle_path
            SELECT depth, COUNT(*) FROM walk WHERE NOT is_cycle GROUP BY depth ORDER BY depth
        """
        t0 = time.perf_counter()
        rows = db.session.execute(text(walk_sql)).fetchall()
        t1 = time.perf_counter()
        total = sum(r[1] for r in rows)
        print(f"  {mode}: {total} rows in {(t1-t0)*1000:.0f}ms", flush=True)
        for r in rows[:5]:
            print(f"    depth={r[0]}: {r[1]} rows", flush=True)

    # D: Test MATERIALIZED edges + UNION walk
    print(flush=True)
    print("=" * 60, flush=True)
    print("D. COMBINATIONS: (NOT) MATERIALIZED + UNION (ALL)", flush=True)
    # Rather than timing full queries, just check key variants
    
    # Best variant: MATERIALIZED edges + UNION walk (dedup per level)
    best_sql = """
        WITH RECURSIVE edges AS MATERIALIZED (
            SELECT parent_member_id AS from_id, child_member_id AS to_id FROM parent_child_relations WHERE genealogy_id = 1
            UNION ALL
            SELECT child_member_id, parent_member_id FROM parent_child_relations WHERE genealogy_id = 1
            UNION ALL
            SELECT spouse1_member_id, spouse2_member_id FROM marriages WHERE genealogy_id = 1
            UNION ALL
            SELECT spouse2_member_id, spouse1_member_id FROM marriages WHERE genealogy_id = 1
        ),
        walk AS (
            SELECT 114 AS member_id, 0 AS depth
            UNION
            SELECT e.to_id, walk.depth + 1
            FROM walk JOIN edges e ON e.from_id = walk.member_id
            WHERE walk.depth < 8
        ) CYCLE member_id SET is_cycle USING cycle_path
        SELECT depth, COUNT(*) FROM walk WHERE NOT is_cycle GROUP BY depth ORDER BY depth
    """
    t0 = time.perf_counter()
    rows = db.session.execute(text(best_sql)).fetchall()
    t1 = time.perf_counter()
    total = sum(r[1] for r in rows)
    print(f"  MATERIALIZED + UNION: {total} rows in {(t1-t0)*1000:.0f}ms", flush=True)
    for r in rows:
        print(f"    depth={r[0]}: {r[1]} rows", flush=True)

    print(flush=True)
    print("ANALYSIS COMPLETE", flush=True)