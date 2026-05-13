"""Quick distance test between 114 and 514."""
import sys, time
sys.path.insert(0, '.')
from dotenv import load_dotenv; load_dotenv()
from app import create_app
from app.extensions import db
from sqlalchemy import text

app = create_app()
with app.app_context():
    sql = """
        WITH RECURSIVE e AS NOT MATERIALIZED (
            SELECT parent_member_id f, child_member_id t FROM parent_child_relations WHERE genealogy_id=1
            UNION ALL SELECT child_member_id, parent_member_id FROM parent_child_relations WHERE genealogy_id=1
            UNION ALL SELECT spouse1_member_id, spouse2_member_id FROM marriages WHERE genealogy_id=1
            UNION ALL SELECT spouse2_member_id, spouse1_member_id FROM marriages WHERE genealogy_id=1
        ),
        w AS (
            SELECT 114 m, 0 d
            UNION
            SELECT e.t, w.d+1
            FROM w JOIN e ON e.f=w.m
            WHERE w.d<20
        ) CYCLE m SET c USING p
        SELECT MIN(d) FROM w WHERE m=514 AND NOT c
    """
    t0 = time.perf_counter()
    r = db.session.execute(text(sql)).fetchone()
    t = (time.perf_counter() - t0) * 1000
    print(f"Distance from 114 to 514: {r[0]} (Time: {t:.0f}ms)", flush=True)

    # Also test bidirectional: forward and back BFS counts at depth 10 each
    for label, sid, eid in [("FWD", 114, 514), ("REV", 514, 114)]:
        s2 = sql.replace("114 m", f"{sid} m").replace("m=514", f"m={eid}")
        t0 = time.perf_counter()
        r = db.session.execute(text(s2)).fetchone()
        t = (time.perf_counter() - t0) * 1000
        print(f"{label} distance {sid}->{eid}: {r[0]} (Time: {t:.0f}ms)", flush=True)