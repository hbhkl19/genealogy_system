-- ============================================================
-- BFS reachable nodes stored function
-- 比递归 CTE 更高效的 BFS 实现：
--   1. 使用迭代而非递归，完全控制每层行为
--   2. CROSS JOIN LATERAL 直接走索引点查（每条边 <1ms）
--   3. ON CONFLICT DO NOTHING 零成本去重
--   4. 无 CYCLE 子句开销
--
-- Usage: SELECT * FROM bfs_reachable(genealogy_id, start_id, max_depth);
-- ============================================================

CREATE OR REPLACE FUNCTION bfs_reachable(
    p_genealogy_id INTEGER,
    p_root_id INTEGER,
    p_max_depth INTEGER
) RETURNS TABLE(member_id INTEGER, depth INTEGER) AS $$
DECLARE
    current_depth INTEGER := 0;
    row_count INTEGER;
BEGIN
    CREATE TEMP TABLE IF NOT EXISTS bfs_visited (
        vid INTEGER PRIMARY KEY,
        vdepth INTEGER NOT NULL
    ) ON COMMIT DROP;
    TRUNCATE bfs_visited;

    INSERT INTO bfs_visited VALUES (p_root_id, 0);

    LOOP
        EXIT WHEN current_depth >= p_max_depth;

        INSERT INTO bfs_visited
        SELECT DISTINCT e.to_id, current_depth + 1
        FROM bfs_visited v
        CROSS JOIN LATERAL (
            SELECT parent_member_id AS to_id
            FROM parent_child_relations
            WHERE genealogy_id = p_genealogy_id
              AND child_member_id = v.vid
            UNION ALL
            SELECT child_member_id
            FROM parent_child_relations
            WHERE genealogy_id = p_genealogy_id
              AND parent_member_id = v.vid
            UNION ALL
            SELECT spouse2_member_id
            FROM marriages
            WHERE genealogy_id = p_genealogy_id
              AND spouse1_member_id = v.vid
            UNION ALL
            SELECT spouse1_member_id
            FROM marriages
            WHERE genealogy_id = p_genealogy_id
              AND spouse2_member_id = v.vid
        ) e
        WHERE v.vdepth = current_depth
          AND e.to_id IS NOT NULL
        ON CONFLICT (vid) DO NOTHING;

        GET DIAGNOSTICS row_count = ROW_COUNT;
        EXIT WHEN row_count = 0;
        current_depth := current_depth + 1;
    END LOOP;

    RETURN QUERY SELECT v.vid, v.vdepth FROM bfs_visited v;
END;
$$ LANGUAGE plpgsql;