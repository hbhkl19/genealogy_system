"""Comprehensive performance test for the optimized relationship path query.

Tests the three-layer optimization:
  1. UNION (instead of UNION ALL) in walk CTE — dedup per level
  2. Batched _lookup_relations_batch — single VALUES query
  3. PL/pgSQL bfs_reachable() — iterative BFS with temp table

Scenarios:
  A: 50000-member genealogy, close relatives (3-5 hops)
  B: 50000-member genealogy, distant relatives (6-10 hops)
  C: 50000-member genealogy, very distant / unreachable (10-15 hops)
  D: 50000-member genealogy, same person (identity)
"""
import sys, time
sys.path.insert(0, '.')
from dotenv import load_dotenv; load_dotenv()
from app import create_app
from app.extensions import db
from sqlalchemy import text
from app.members.routes import (
    _bfs_reachable, _reconstruct_path, _lookup_relations_batch,
    EDGE_CTE_NO_REL,
)

app = create_app()

def find_test_pairs(genealogy_id):
    """Find diverse test pairs at various distances."""
    pairs = []
    
    # Close: siblings via shared parent (2 hops: child->parent->child)
    rows = db.session.execute(text("""
        SELECT p1.parent_member_id, p2.parent_member_id
        FROM parent_child_relations p1
        JOIN parent_child_relations p2 ON p1.child_member_id = p2.child_member_id
        WHERE p1.genealogy_id = :gid AND p2.genealogy_id = :gid
          AND p1.parent_member_id <> p2.parent_member_id
        LIMIT 2
    """), {"gid": genealogy_id}).fetchall()
    for r in rows:
        pairs.append(("兄弟姐妹 (2 hops)", r[0], r[1]))
    
    # Medium: ancestor chain - use bfs_reachable to find pairs at depth 4-6
    rows = db.session.execute(text(
        "SELECT member_id, depth FROM bfs_reachable(:g, 1, 6) WHERE depth BETWEEN 4 AND 6 LIMIT 4"
    ), {"g": genealogy_id}).fetchall()
    for r in rows:
        pairs.append((f"远亲 (depth={r[1]})", 1, r[0]))
    
    # Distant: use bfs_reachable to find pairs at depth 8-12
    rows = db.session.execute(text(
        "SELECT member_id, depth FROM bfs_reachable(:g, 1, 12) WHERE depth BETWEEN 8 AND 12 LIMIT 4"
    ), {"g": genealogy_id}).fetchall()
    for r in rows:
        pairs.append((f"远亲 (depth={r[1]})", 1, r[0]))
    
    return pairs[:10]  # Max 10 test pairs


def get_member_name(mid):
    r = db.session.execute(
        text("SELECT name, generation_no FROM members WHERE id = :id"),
        {"id": mid}
    ).first()
    return f"{r[1]}代:{r[0]}" if r else f"ID={mid}"


REL_LABELS = {"father": "父亲", "mother": "母亲", "child": "子女", "spouse": "配偶"}


with app.app_context():
    gid = 1
    total_members = db.session.execute(
        text("SELECT COUNT(*) FROM members WHERE genealogy_id=:g"), {"g": gid}
    ).fetchone()[0]
    total_edges = db.session.execute(text(
        "SELECT (SELECT COUNT(*) FROM parent_child_relations WHERE genealogy_id=:g)*2 "
        "+ (SELECT COUNT(*) FROM marriages WHERE genealogy_id=:g)*2"
    ), {"g": gid}).fetchone()[0]

    print("=" * 70)
    print(f"  亲缘链路查询性能测试 (族谱 ID={gid}, {total_members}人, {total_edges}边)")
    print("=" * 70)

    # --- Step 1: verify PL/pgSQL function exists ---
    print("\n[0] PL/pgSQL 函数检查")
    t0 = time.perf_counter()
    try:
        r = db.session.execute(text(
            "SELECT COUNT(*) FROM bfs_reachable(:g, :r, :d)"
        ), {"g": gid, "r": 1, "d": 1}).fetchone()
        print(f"  bfs_reachable() 可用 (测试返回 {r[0]} 行, {(time.perf_counter()-t0)*1000:.0f}ms)")
    except Exception as e:
        print(f"  bfs_reachable() 不可用, 将使用 CTE 回退: {e}")

    # --- Step 2: raw BFS timing at various depths ---
    print("\n[1] 单节点 BFS 各深度耗时对比")
    
    # Use member 1 as test root
    for depth in [4, 6, 8, 10, 12, 15]:
        # CTE approach (UNION)
        t0 = time.perf_counter()
        cte_result = _bfs_reachable(gid, 1, depth)
        cte_t = (time.perf_counter() - t0) * 1000
        
        print(f"  depth<={depth}: {len(cte_result):>6} members, CTE={cte_t:>7.0f}ms", end="")
        
        # PL/pgSQL approach
        try:
            t0 = time.perf_counter()
            rows = db.session.execute(text(
                "SELECT member_id, depth FROM bfs_reachable(:g, :r, :d)"
            ), {"g": gid, "r": 1, "d": depth}).fetchall()
            func_result = {r[0]: r[1] for r in rows}
            func_t = (time.perf_counter() - t0) * 1000
            print(f", func={func_t:>7.0f}ms", end="")
            if func_result != cte_result:
                print(f" ← MISMATCH!", end="")
        except Exception:
            print(f", func=N/A", end="")
        print()

    # --- Step 3: Full path query for various pairs ---
    print("\n[2] 完整亲缘路径查询")
    
    test_pairs = find_test_pairs(gid)
    test_pairs.append(("自反 (0 hops)", 1, 1))  # Identity
    
    all_times = []
    
    for label, sid, eid in test_pairs:
        print(f"\n  场景: {label}")
        print(f"    起始: {get_member_name(sid)} (ID={sid})")
        print(f"    目标: {get_member_name(eid)} (ID={eid})")
        
        start_time = time.perf_counter()
        
        if sid == eid:
            print(f"    结果: 同一人, 路径长度 0")
            all_times.append((time.perf_counter() - start_time) * 1000)
            continue
        
        # Progressive bidirectional BFS
        found = False
        for max_depth in (6, 8, 10, 12, 15):
            t0 = time.perf_counter()
            fwd = _bfs_reachable(gid, sid, max_depth)
            fwd_t = (time.perf_counter() - t0) * 1000
            
            t0 = time.perf_counter()
            rev = _bfs_reachable(gid, eid, max_depth)
            rev_t = (time.perf_counter() - t0) * 1000
            
            meeting = set(fwd.keys()) & set(rev.keys())
            
            if meeting:
                best = min(meeting, key=lambda m: fwd[m] + rev[m])
                fd, rd = fwd[best], rev[best]
                
                t0 = time.perf_counter()
                fwd_ids, fwd_rels = _reconstruct_path(gid, sid, best, fd, fwd)
                p2_fwd_t = (time.perf_counter() - t0) * 1000
                
                t0 = time.perf_counter()
                rev_ids, rev_rels = _reconstruct_path(gid, eid, best, rd, rev)
                p2_rev_t = (time.perf_counter() - t0) * 1000
                
                if fwd_ids and rev_ids:
                    rev_reversed = rev_ids[-2::-1] if len(rev_ids) > 1 else []
                    full_ids = list(fwd_ids) + rev_reversed
                    
                    relation_types = list(fwd_rels)
                    rev_rels_list = list(rev_rels)
                    for i in range(len(rev_rels_list) - 1, -1, -1):
                        rrel = rev_rels_list[i]
                        if rrel == 'child':
                            relation_types.append('parent')
                        elif rrel == 'spouse':
                            relation_types.append('spouse')
                        else:
                            relation_types.append(rrel)
                    
                    total_time = (time.perf_counter() - start_time) * 1000
                    all_times.append(total_time)
                    
                    print(f"    找到交汇点: {best} (fwd={fd}, rev={rd})")
                    print(f"    Phase1: fwd={fwd_t:.0f}ms ({len(fwd)} nodes), rev={rev_t:.0f}ms ({len(rev)} nodes)")
                    print(f"    Phase2: fwd={p2_fwd_t:.0f}ms, rev={p2_rev_t:.0f}ms")
                    print(f"    路径: {len(full_ids)} 节点, {len(relation_types)} 步")
                    
                    # Show path summary
                    path_str = " → ".join(
                        f"{get_member_name(mid)}" 
                        for mid in full_ids[:8]
                    )
                    if len(full_ids) > 8:
                        path_str += " → ..."
                    print(f"    {path_str}")
                    
                    found = True
                    break
            
            if max_depth >= 15:
                break
        
        if not found:
            total_time = (time.perf_counter() - start_time) * 1000
            all_times.append(total_time)
            print(f"    未找到路径 (已搜索至 depth=15)")
    
    # --- Summary ---
    print("\n" + "=" * 70)
    print("  测试总结")
    print("=" * 70)
    
    if all_times:
        valid_times = [t for t in all_times if t > 0]
        print(f"  测试场景数:     {len(all_times)}")
        print(f"  最慢查询:       {max(all_times):.0f}ms")
        print(f"  平均耗时:       {sum(all_times)/len(all_times):.0f}ms")
        
        if all(t < 5000 for t in all_times):
            print(f"\n  [OK] 所有查询均在 5 秒内完成！")
            if all(t < 1000 for t in all_times):
                print(f"  [OK] 所有查询均在 1 秒内完成！远超预期！")
        elif max(all_times) < 10000:
            print(f"\n  [OK] 最大耗时 {max(all_times):.0f}ms < 10s，符合要求。")
        else:
            print(f"\n  [WARN] 最慢查询 {max(all_times):.0f}ms，仍需优化")
    else:
        print("  未记录有效测试")

    print()
    print("测试完成")