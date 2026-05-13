-- ============================================================
-- Task 4.6：EXPLAIN 展示递归 CTE + 索引效果
-- 1) 先 EXPLAIN 无索引版本（临时 DROP 复合索引后执行）
-- 2) 再 EXPLAIN 有索引版本（当前状态）
-- 对比 Seq Scan vs Index Scan 的行数/耗时差异
-- ============================================================
--
-- 参数：:member_id
-- 有索引版本（当前数据库状态）
EXPLAIN (ANALYZE, BUFFERS) WITH RECURSIVE descendants AS (
    SELECT child_member_id AS member_id,
        1 AS depth
    FROM parent_child_relations
    WHERE parent_member_id = :member_id
    UNION
    SELECT p.child_member_id,
        d.depth + 1
    FROM parent_child_relations p
        JOIN descendants d ON p.parent_member_id = d.member_id
    WHERE d.depth < 4
)
SELECT m.id,
    m.name,
    m.generation_no,
    descendants.depth
FROM descendants
    JOIN members m ON m.id = descendants.member_id
ORDER BY descendants.depth,
    m.id;