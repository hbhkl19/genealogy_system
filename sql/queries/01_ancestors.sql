-- ============================================================
-- Task 4.2：递归 CTE 向上追溯祖先
-- 输入成员 ID，输出其所有历代祖先（按深度排序）。
-- ============================================================
--
-- 使用 Recursive CTE 从子节点逐层向上查找父节点。
-- UNION（非 UNION ALL）自动去重，避免多路径引入的重复祖先。
-- depth < 10 作为安全上限（10 代约 1024 位理论祖先）。
--
-- 参数：:member_id

WITH RECURSIVE ancestors AS (
    SELECT p.parent_member_id AS member_id, 1 AS depth
    FROM parent_child_relations p
    WHERE p.child_member_id = :member_id
    UNION
    SELECT p.parent_member_id, a.depth + 1
    FROM parent_child_relations p
    JOIN ancestors a ON p.child_member_id = a.member_id
    WHERE a.depth < 10
)
SELECT m.id, m.name, m.gender, m.birth_year, m.death_year, m.generation_no, ancestors.depth
FROM ancestors
JOIN members m ON m.id = ancestors.member_id
ORDER BY ancestors.depth, m.id;
