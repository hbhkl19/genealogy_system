-- ============================================================
-- Task 4.2（补充）：递归 CTE 向下追溯后代
-- 输入成员 ID，输出其所有后代（按深度排序）。
-- ============================================================
-- UNION 自动去重，防止通过父亲/母亲双路径产生重复后代。
-- depth < 12 作为安全上限。
-- 参数：:member_id
WITH RECURSIVE descendants AS (
    SELECT child_member_id AS member_id,
        1 AS depth
    FROM parent_child_relations
    WHERE parent_member_id = :member_id
    UNION
    SELECT p.child_member_id,
        d.depth + 1
    FROM parent_child_relations p
        JOIN descendants d ON p.parent_member_id = d.member_id
    WHERE d.depth < 12
)
SELECT m.*,
    descendants.depth
FROM descendants
    JOIN members m ON m.id = descendants.member_id
ORDER BY descendants.depth,
    m.id;