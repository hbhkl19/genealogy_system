WITH RECURSIVE descendants AS (
    SELECT
        child_member_id AS member_id,
        parent_member_id,
        parent_role,
        1 AS depth,
        ',' || CAST(child_member_id AS TEXT) || ',' AS path
    FROM parent_child_relations
    WHERE parent_member_id = :member_id
    UNION ALL
    SELECT
        p.child_member_id,
        p.parent_member_id,
        p.parent_role,
        d.depth + 1,
        d.path || CAST(p.child_member_id AS TEXT) || ','
    FROM parent_child_relations p
    JOIN descendants d ON p.parent_member_id = d.member_id
    WHERE d.depth < 12
      AND d.path NOT LIKE '%,' || CAST(p.child_member_id AS TEXT) || ',%'
)
SELECT m.*, descendants.depth, descendants.parent_role
FROM descendants
JOIN members m ON m.id = descendants.member_id
ORDER BY descendants.path;
