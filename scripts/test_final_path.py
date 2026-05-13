"""Test the final optimized relationship path query."""
import sys, time
sys.path.insert(0, '.')
from dotenv import load_dotenv; load_dotenv()
from app import create_app
from app.extensions import db
from sqlalchemy import text
from app.members.routes import _bfs_reachable, _reconstruct_path, _lookup_relations_batch

app = create_app()
with app.app_context():
    gid, start_id, end_id = 1, 114, 514
    print(f"Testing path: {start_id} -> {end_id} (genealogy {gid})", flush=True)

    # Phase 1: progressive bidirectional BFS
    for max_depth in (6, 8, 10, 12, 15):
        print(f"\n--- Trying max_depth={max_depth} ---", flush=True)
        
        t0 = time.perf_counter()
        fwd = _bfs_reachable(gid, start_id, max_depth)
        fwd_t = (time.perf_counter() - t0) * 1000
        
        t0 = time.perf_counter()
        rev = _bfs_reachable(gid, end_id, max_depth)
        rev_t = (time.perf_counter() - t0) * 1000
        
        print(f"  Phase 1: FWD={fwd_t:.0f}ms ({len(fwd)} members), REV={rev_t:.0f}ms ({len(rev)} members)", flush=True)
        
        meeting = set(fwd.keys()) & set(rev.keys())
        if not meeting:
            print(f"  No intersection at depth {max_depth}", flush=True)
            continue
        
        best = min(meeting, key=lambda m: fwd[m] + rev[m])
        fd, rd = fwd[best], rev[best]
        print(f"  Meeting point: {best} (fwd_depth={fd}, rev_depth={rd}, total={fd+rd})", flush=True)

        # Phase 2: reconstruction
        t0 = time.perf_counter()
        fwd_ids, fwd_rels = _reconstruct_path(gid, start_id, best, fd, fwd)
        p2_fwd_t = (time.perf_counter() - t0) * 1000
        
        t0 = time.perf_counter()
        rev_ids, rev_rels = _reconstruct_path(gid, end_id, best, rd, rev)
        p2_rev_t = (time.perf_counter() - t0) * 1000
        
        print(f"  Phase 2: FWD={p2_fwd_t:.0f}ms, REV={p2_rev_t:.0f}ms", flush=True)
        
        if fwd_ids and rev_ids:
            rev_reversed = rev_ids[-2::-1] if len(rev_ids) > 1 else []
            full_ids = fwd_ids + rev_reversed
            
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
            
            print(f"  Path: {len(full_ids)} members, {len(relation_types)} relations", flush=True)
            
            # Get names
            names = db.session.execute(
                text("SELECT id, name, generation_no FROM members WHERE id = ANY(:ids)"),
                {"ids": full_ids}
            ).fetchall()
            name_map = {r[0]: (r[1], r[2]) for r in names}
            
            print(f"\n  Full path:", flush=True)
            labels = {"father": "父亲", "mother": "母亲", "child": "子女", "spouse": "配偶"}
            for i, mid in enumerate(full_ids):
                name, gen = name_map.get(mid, (f"ID={mid}", "?"))
                if i == 0:
                    print(f"    [{gen}] {name}", flush=True)
                else:
                    rel = relation_types[i-1] if i-1 < len(relation_types) else '?'
                    print(f"    [{gen}] {name}  ← {labels.get(rel, rel)}", flush=True)
            
            total_time = (fwd_t + rev_t + p2_fwd_t + p2_rev_t)
            print(f"\n  TOTAL: {total_time:.0f}ms", flush=True)
            break
        else:
            print(f"  Reconstruction failed", flush=True)
    
    print("\nTEST COMPLETE", flush=True)