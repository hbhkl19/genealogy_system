WITH RECURSIVE descendants AS (
    SELECT child_member_id AS member_id, parent_member_id, 1 AS depth
    FROM parent_child_relations
    WHERE parent_member_id = :member_id
    UNION ALL
    SELECT p.child_member_id, p.parent_member_id, d.depth + 1
    FROM parent_child_relations p
    JOIN descendants d ON p.parent_member_id = d.member_id
)
SELECT m.*, descendants.depth
FROM descendants
JOIN members m ON m.id = descendants.member_id
ORDER BY descendants.depth, m.id;
