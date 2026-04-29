WITH RECURSIVE ancestors AS (
    SELECT parent_member_id AS member_id, child_member_id, 1 AS depth
    FROM parent_child_relations
    WHERE child_member_id = :member_id
    UNION ALL
    SELECT p.parent_member_id, p.child_member_id, a.depth + 1
    FROM parent_child_relations p
    JOIN ancestors a ON p.child_member_id = a.member_id
)
SELECT m.*, ancestors.depth
FROM ancestors
JOIN members m ON m.id = ancestors.member_id
ORDER BY ancestors.depth, m.id;
