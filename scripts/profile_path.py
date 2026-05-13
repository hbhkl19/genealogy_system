"""Comprehensive profiling for relationship path query performance bottlenecks."""
import sys, time
sys.path.insert(0, '.')
from dotenv import load_dotenv; load_dotenv()
from app import create_app
from app.extensions import db
from sqlalchemy import text

app = create_app()
with app.app_context():
    gid, start_id, end_id = 1, 114, 514
    params = {"genealogy_id": gid, "start_id": start_id, "end_id": end_id}

    # 1. Data statistics
    print("=" * 60, flush=True)
    print("1. DATA STATISTICS (genealogy_id=1)", flush=True)
    for q in [
        ("members", "SELECT COUNT(*) FROM members WHERE genealogy_id=1"),
        ("parent_child_relations", "SELECT COUNT(*) FROM parent_child_relations WHERE genealogy_id=1"),
        ("marriages", "SELECT COUNT(*) FROM marriages WHERE genealogy_id=1"),
        ("distinct parents", "SELECT COUNT(DISTINCT parent_member_id) FROM parent_child_relations WHERE genealogy_id=1"),
        ("distinct children", "SELECT COUNT(DISTINCT child_member_id) FROM parent_child_relations WHERE genealogy_id=1"),
    ]:
        r = db.session.execute(text(q[1])).fetchone()
        print(f"  {q[0]}: {r[0]}", flush=True)

    r = db.session.execute(text(
        "SELECT (SELECT COUNT(*) FROM parent_child_relations WHERE genealogy_id=1) * 2 "
        "+ (SELECT COUNT(*) FROM marriages WHERE genealogy_id=1) * 2 AS total_edges"
    )).fetchone()
    print(f"  Total edge count (2*pcr + 2*marriages): {r[0]}", flush=True)

    # Average degree per node
    r = db.session.execute(text("""
        WITH degree_stats AS (
            SELECT parent_member_id AS node_id, COUNT(*) AS deg FROM parent_child_relations WHERE genealogy_id=1 GROUP BY parent_member_id
            UNION ALL
            SELECT child_member_id, COUNT(*) FROM parent_child_relations WHERE genealogy_id=1 GROUP BY child_member_id
            UNION ALL
            SELECT spouse1_member_id, COUNT(*) FROM marriages WHERE genealogy_id=1 GROUP BY spouse1_member_id
            UNION ALL
            SELECT spouse2_member_id, COUNT(*) FROM marriages WHERE genealogy_id=1 GROUP BY spouse2_member_id
        )
        SELECT AVG(deg), MAX(deg), COUNT(DISTINCT node_id) FROM degree_stats
    """)).fetchone()
    print(f"  Avg degree: {r[0]:.2f}, Max degree: {r[1]}, Distinct nodes in edges: {r[2]}", flush=True)

    # 2. EXPLAIN (no ANALYZE) for query plan
    print(flush=True)
    print("=" * 60, flush=True)
    print("2. EXPLAIN (NO ANALYZE - plan only)", flush=True)
    sql_base = """
        WITH RECURSIVE edges AS NOT MATERIALIZED (
            SELECT parent_member_id AS from_id, child_member_id AS to_id, 'child' AS relation_type FROM parent_child_relations WHERE genealogy_id = :genealogy_id
            UNION ALL
            SELECT child_member_id, parent_member_id, parent_role FROM parent_child_relations WHERE genealogy_id = :genealogy_id
            UNION ALL
            SELECT spouse1_member_id, spouse2_member_id, 'spouse' FROM marriages WHERE genealogy_id = :genealogy_id
            UNION ALL
            SELECT spouse2_member_id, spouse1_member_id, 'spouse' FROM marriages WHERE genealogy_id = :genealogy_id
        ),
        walk AS (
            SELECT CAST(:start_id AS INTEGER) AS member_id,
                   ',' || CAST(:start_id AS TEXT) || ',' AS id_path,
                   '' AS relation_types, 0 AS depth
            UNION ALL
            SELECT e.to_id,
                   walk.id_path || CAST(e.to_id AS TEXT) || ',',
                   walk.relation_types || e.relation_type || ',',
                   walk.depth + 1
            FROM walk JOIN edges e ON e.from_id = walk.member_id
            WHERE walk.depth < 8
        ) CYCLE member_id SET is_cycle USING cycle_path
        SELECT id_path, relation_types FROM walk
        WHERE member_id = :end_id AND NOT is_cycle
        ORDER BY depth LIMIT 1
    """
    rows = db.session.execute(text("EXPLAIN " + sql_base), params).fetchall()
    for r in rows:
        print(f"  {r[0]}", flush=True)

    # 3. Timed query execution at different depths
    print(flush=True)
    print("=" * 60, flush=True)
    print("3. TIMED QUERY at various depth limits", flush=True)
    for depth_limit in [2, 3, 4, 5, 6, 7, 8]:
        s = sql_base.replace("walk.depth < 8", f"walk.depth < {depth_limit}")
        start_t = time.perf_counter()
        row = db.session.execute(text(s), params).first()
        elapsed = time.perf_counter() - start_t
        found = "NO"
        if row:
            ids = [int(x) for x in row.id_path.strip(",").split(",") if x]
            found = f"YES (len={len(ids)-1})"
        print(f"  depth<{depth_limit}: {elapsed*1000:6.0f}ms  found={found}", flush=True)

    # 4. Count walk rows GROUP BY depth
    print(flush=True)
    print("=" * 60, flush=True)
    print("4. WALK ROWS PER DEPTH (8 levels)", flush=True)
    count_sql = """
        WITH RECURSIVE edges AS NOT MATERIALIZED (
            SELECT parent_member_id AS from_id, child_member_id AS to_id FROM parent_child_relations WHERE genealogy_id = :genealogy_id
            UNION ALL
            SELECT child_member_id, parent_member_id FROM parent_child_relations WHERE genealogy_id = :genealogy_id
            UNION ALL
            SELECT spouse1_member_id, spouse2_member_id FROM marriages WHERE genealogy_id = :genealogy_id
            UNION ALL
            SELECT spouse2_member_id, spouse1_member_id FROM marriages WHERE genealogy_id = :genealogy_id
        ),
        walk AS (
            SELECT CAST(:start_id AS INTEGER) AS member_id, 0 AS depth
            UNION ALL
            SELECT e.to_id, walk.depth + 1
            FROM walk JOIN edges e ON e.from_id = walk.member_id
            WHERE walk.depth < 8
        ) CYCLE member_id SET is_cycle USING cycle_path
        SELECT depth, COUNT(*) FROM walk WHERE NOT is_cycle GROUP BY depth ORDER BY depth
    """
    rows = db.session.execute(text(count_sql), params).fetchall()
    total = 0
    for r in rows:
        total += r[1]
        print(f"  depth={r[0]}: {r[1]:>8} rows (cumulative={total})", flush=True)
    print(f"  Total non-cycle rows: {total}", flush=True)

    # 5. MATERIALIZED vs NOT MATERIALIZED comparison
    print(flush=True)
    print("=" * 60, flush=True)
    print("5. MATERIALIZED vs NOT MATERIALIZED edges", flush=True)
    sql_not_mat = sql_base
    sql_mat = sql_base.replace("NOT MATERIALIZED", "MATERIALIZED")
    for label, sql_v in [("NOT MATERIALIZED", sql_not_mat), ("MATERIALIZED", sql_mat)]:
        best = 999999
        for depth_limit in [4, 6]:
            s = sql_v.replace("walk.depth < 8", f"walk.depth < {depth_limit}")
            start_t = time.perf_counter()
            row = db.session.execute(text(s), params).first()
            elapsed = time.perf_counter() - start_t
            found = "NO"
            if row:
                ids = [int(x) for x in row.id_path.strip(",").split(",") if x]
                found = f"len={len(ids)-1}"
            print(f"  {label} depth<{depth_limit}: {elapsed*1000:6.0f}ms  found={found}", flush=True)

    # 6. Bidirectional BFS proof-of-concept
    print(flush=True)
    print("=" * 60, flush=True)
    print("6. BIDIRECTIONAL BFS (depth<6 each side)", flush=True)
    fwd_sql = """
        WITH RECURSIVE edges AS NOT MATERIALIZED (
            SELECT parent_member_id AS from_id, child_member_id AS to_id FROM parent_child_relations WHERE genealogy_id = :genealogy_id
            UNION ALL
            SELECT child_member_id, parent_member_id FROM parent_child_relations WHERE genealogy_id = :genealogy_id
            UNION ALL
            SELECT spouse1_member_id, spouse2_member_id FROM marriages WHERE genealogy_id = :genealogy_id
            UNION ALL
            SELECT spouse2_member_id, spouse1_member_id FROM marriages WHERE genealogy_id = :genealogy_id
        ),
        walk AS (
            SELECT CAST(:start_id AS INTEGER) AS member_id,
                   ',' || CAST(:start_id AS TEXT) || ',' AS id_path,
                   0 AS depth
            UNION ALL
            SELECT e.to_id,
                   walk.id_path || CAST(e.to_id AS TEXT) || ',',
                   walk.depth + 1
            FROM walk JOIN edges e ON e.from_id = walk.member_id
            WHERE walk.depth < 6
        ) CYCLE member_id SET is_cycle USING cycle_path
        SELECT member_id, id_path FROM walk WHERE NOT is_cycle
    """
    t0 = time.perf_counter()
    fwd_rows = db.session.execute(text(fwd_sql), params).fetchall()
    fwd_t = time.perf_counter() - t0
    fwd_dict = {}
    for r in fwd_rows:
        if r[0] not in fwd_dict or len(fwd_dict[r[0]]) > len(r[1]):
            fwd_dict[r[0]] = r[1]

    rev_params = {"genealogy_id": gid, "start_id": end_id}
    t0 = time.perf_counter()
    rev_rows = db.session.execute(text(fwd_sql), rev_params).fetchall()
    rev_t = time.perf_counter() - t0
    rev_dict = {}
    for r in rev_rows:
        if r[0] not in rev_dict or len(rev_dict[r[0]]) > len(r[1]):
            rev_dict[r[0]] = r[1]

    inter = set(fwd_dict.keys()) & set(rev_dict.keys())
    print(f"  Forward BFS: {fwd_t*1000:.0f}ms, {len(fwd_dict)} unique nodes", flush=True)
    print(f"  Reverse BFS: {rev_t*1000:.0f}ms, {len(rev_dict)} unique nodes", flush=True)
    print(f"  Intersection: {len(inter)} nodes", flush=True)
    if inter:
        meet = list(inter)[0]
        f_part = fwd_dict[meet].strip(",")
        r_part = rev_dict[meet].strip(",")
        r_rev = ",".join(r_part.split(",")[::-1][1:])
        full = f_part + r_rev
        print(f"  Meeting point: {meet}", flush=True)
        print(f"  Path: {full}", flush=True)
        print(f"  Total length: {len(full.split(','))} nodes", flush=True)

    # 7. Dedicated index test for edges query
    print(flush=True)
    print("=" * 60, flush=True)
    print("7. INDEXES ON PARENT_CHILD_RELATIONS AND MARRIAGES", flush=True)
    for idx_sql in [
        "SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'parent_child_relations'",
        "SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'marriages'",
    ]:
        rows = db.session.execute(text(idx_sql)).fetchall()
        for r in rows:
            print(f"  {r[0]}: {r[1]}", flush=True)

    print(flush=True)
    print("=" * 60, flush=True)
    print("PROFILING COMPLETE", flush=True)