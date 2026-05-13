import sys, time; sys.path.insert(0, '.')
from dotenv import load_dotenv; load_dotenv()
from app import create_app
from app.extensions import db
from sqlalchemy import text

app = create_app()
with app.app_context():
    gid = 1

    # EXPLAIN the OLD approach (NOT EXISTS)
    print("=== OLD: NOT EXISTS ===")
    r = db.session.execute(text("""
        EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
        SELECT m.id, m.name, m.gender, m.generation_no
        FROM members m
        WHERE m.genealogy_id = :gid
          AND NOT EXISTS (
              SELECT 1 FROM parent_child_relations p
              WHERE p.child_member_id = m.id AND p.genealogy_id = :gid AND p.parent_role = 'father'
          )
          AND (m.gender = 'male' OR NOT EXISTS (
              SELECT 1 FROM marriages mar
              WHERE mar.genealogy_id = :gid AND (mar.spouse1_member_id = m.id OR mar.spouse2_member_id = m.id)
          ))
        ORDER BY m.generation_no, m.id
    """), {"gid": gid}).fetchall()
    for row in r:
        print(row[0])

    print("\n=== NEW: LEFT JOIN anti-join ===")
    r = db.session.execute(text("""
        EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
        SELECT m.id, m.name, m.gender, m.generation_no
        FROM members m
        LEFT JOIN parent_child_relations p ON p.child_member_id = m.id 
            AND p.genealogy_id = :gid AND p.parent_role = 'father'
        LEFT JOIN marriages mar ON mar.genealogy_id = :gid 
            AND (mar.spouse1_member_id = m.id OR mar.spouse2_member_id = m.id)
        WHERE m.genealogy_id = :gid 
          AND p.child_member_id IS NULL
          AND (m.gender = 'male' OR mar.id IS NULL)
        ORDER BY m.generation_no, m.id
    """), {"gid": gid}).fetchall()
    for row in r:
        print(row[0])

    # Timing comparison
    for label, sql in [
        ("OLD NOT EXISTS", """
            SELECT COUNT(*) FROM members m
            WHERE m.genealogy_id = :gid
              AND NOT EXISTS (
                  SELECT 1 FROM parent_child_relations p
                  WHERE p.child_member_id = m.id AND p.genealogy_id = :gid AND p.parent_role = 'father'
              )
              AND (m.gender = 'male' OR NOT EXISTS (
                  SELECT 1 FROM marriages mar
                  WHERE mar.genealogy_id = :gid AND (mar.spouse1_member_id = m.id OR mar.spouse2_member_id = m.id)
              ))
        """),
        ("NEW LEFT JOIN", """
            SELECT COUNT(*) FROM members m
            LEFT JOIN parent_child_relations p ON p.child_member_id = m.id 
                AND p.genealogy_id = :gid AND p.parent_role = 'father'
            LEFT JOIN marriages mar ON mar.genealogy_id = :gid 
                AND (mar.spouse1_member_id = m.id OR mar.spouse2_member_id = m.id)
            WHERE m.genealogy_id = :gid 
              AND p.child_member_id IS NULL
              AND (m.gender = 'male' OR mar.id IS NULL)
        """),
    ]:
        times = []
        for _ in range(5):
            t0 = time.perf_counter()
            db.session.execute(text(sql), {"gid": gid}).fetchone()
            db.session.rollback()
            times.append((time.perf_counter() - t0) * 1000)
        print(f"\n{label}: min={min(times):.0f}ms avg={sum(times)/len(times):.0f}ms max={max(times):.0f}ms")