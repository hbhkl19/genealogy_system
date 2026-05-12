-- ============================================================
-- Task 3（补充）：两成员间最短亲缘路径
-- ============================================================
-- 优化策略：双向BFS
--   Phase 1: UNION-based walk（无路径追踪）— 快速找到交汇点
--   Phase 2: targeted BFS（带路径追踪）— 分别从两端到交汇点
-- 关键优化：
--   1. UNION（非 UNION ALL）在递归步骤中阻止同深度重复member_id
--   2. PostgreSQL ARRAY 替代字符串拼接，减少内存开销
--   3. Phase 1 不追踪路径，只记录 (member_id, depth) — 快速去重
--   4. Phase 2 仅在已知短距离（<=10）内追踪路径
--
-- 参数：:genealogy_id, :start_id, :end_id

-- Phase 1 — Forward: members reachable from start
-- (execute this and the reverse query, find intersection in application)
WITH RECURSIVE edges AS NOT MATERIALIZED (
    SELECT parent_member_id AS from_id, child_member_id AS to_id
    FROM parent_child_relations WHERE genealogy_id = :genealogy_id
    UNION ALL
    SELECT child_member_id, parent_member_id
    FROM parent_child_relations WHERE genealogy_id = :genealogy_id
    UNION ALL
    SELECT spouse1_member_id, spouse2_member_id
    FROM marriages WHERE genealogy_id = :genealogy_id
    UNION ALL
    SELECT spouse2_member_id, spouse1_member_id
    FROM marriages WHERE genealogy_id = :genealogy_id
),
walk AS (
    SELECT CAST(:start_id AS INTEGER) AS member_id, 0 AS depth
    UNION
    SELECT e.to_id, walk.depth + 1
    FROM walk
    JOIN edges e ON e.from_id = walk.member_id
    WHERE walk.depth < 10
) CYCLE member_id SET is_cycle USING cycle_path
SELECT member_id, MIN(depth) AS depth
FROM walk
WHERE NOT is_cycle
GROUP BY member_id;

-- Phase 1 — Reverse: same query with :start_id = :end_id

-- Phase 2 — Path reconstruction (from start to meeting point)
-- After finding meeting_id and fwd_depth in application:
WITH RECURSIVE edges AS NOT MATERIALIZED (
    SELECT parent_member_id AS from_id, child_member_id AS to_id, 'child' AS relation_type
    FROM parent_child_relations WHERE genealogy_id = :genealogy_id
    UNION ALL
    SELECT child_member_id, parent_member_id, parent_role
    FROM parent_child_relations WHERE genealogy_id = :genealogy_id
    UNION ALL
    SELECT spouse1_member_id, spouse2_member_id, 'spouse'
    FROM marriages WHERE genealogy_id = :genealogy_id
    UNION ALL
    SELECT spouse2_member_id, spouse1_member_id, 'spouse'
    FROM marriages WHERE genealogy_id = :genealogy_id
),
walk AS (
    SELECT
        CAST(:start_id AS INTEGER) AS member_id,
        ARRAY[CAST(:start_id AS INTEGER)] AS path,
        ARRAY[]::TEXT[] AS rels,
        0 AS depth
    UNION ALL
    SELECT
        e.to_id,
        walk.path || e.to_id,
        walk.rels || e.relation_type,
        walk.depth + 1
    FROM walk
    JOIN edges e ON e.from_id = walk.member_id
    WHERE walk.depth < :meet_depth
) CYCLE member_id SET is_cycle USING cycle_path
SELECT path, rels FROM walk
WHERE member_id = :meeting_id AND NOT is_cycle
ORDER BY depth
LIMIT 1;

-- 同样的 Phase 2 查询用于反向路径（:start_id = :end_id, :meeting_id = meeting_id）