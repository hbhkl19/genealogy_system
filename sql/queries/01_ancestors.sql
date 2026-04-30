WITH RECURSIVE ancestors AS (
    SELECT
        parent_member_id AS member_id,
        child_member_id,
        1 AS depth,
        ',' || CAST(parent_member_id AS TEXT) || ',' AS path
    FROM parent_child_relations
    WHERE child_member_id = :member_id
    UNION ALL
    SELECT
        p.parent_member_id,
        p.child_member_id,
        a.depth + 1,
        a.path || CAST(p.parent_member_id AS TEXT) || ','
    FROM parent_child_relations p
    JOIN ancestors a ON p.child_member_id = a.member_id
    WHERE a.depth < 12
      AND a.path NOT LIKE '%,' || CAST(p.parent_member_id AS TEXT) || ',%'
)
SELECT m.*, ancestors.depth
FROM ancestors
JOIN members m ON m.id = ancestors.member_id
ORDER BY ancestors.path;
