-- ============================================================
-- Task 3（补充）：两成员间最短亲缘路径
-- 输入成员 A 和 B 的 ID，输出最短路径的关系标签序列。
-- ============================================================
-- BFS 最短路径：edges CTE 构建双向关系图，
-- walk CTE 做宽度优先搜索，CYCLE 子句防止死循环。
-- 参数：:start_id, :end_id, :genealogy_id

WITH RECURSIVE edges AS (
    SELECT parent_member_id AS from_id, child_member_id AS to_id, 'child' AS relation_type
    FROM parent_child_relations WHERE genealogy_id = :genealogy_id
    UNION
    SELECT child_member_id, parent_member_id, parent_role
    FROM parent_child_relations WHERE genealogy_id = :genealogy_id
    UNION
    SELECT spouse1_member_id, spouse2_member_id, 'spouse'
    FROM marriages WHERE genealogy_id = :genealogy_id
    UNION
    SELECT spouse2_member_id, spouse1_member_id, 'spouse'
    FROM marriages WHERE genealogy_id = :genealogy_id
),
walk AS (
    SELECT :start_id AS member_id,
           ',' || CAST(:start_id AS TEXT) || ',' AS id_path,
           '' AS relation_types,
           0 AS depth
    UNION ALL
    SELECT e.to_id,
           walk.id_path || CAST(e.to_id AS TEXT) || ',',
           walk.relation_types || e.relation_type || ',',
           walk.depth + 1
    FROM walk
    JOIN edges e ON e.from_id = walk.member_id
    WHERE walk.depth < 12
) CYCLE member_id SET is_cycle USING cycle_path
SELECT id_path, relation_types
FROM walk
WHERE member_id = :end_id AND NOT is_cycle
ORDER BY depth
LIMIT 1;