WITH RECURSIVE edges AS (
    SELECT parent_member_id AS from_id, child_member_id AS to_id, 'child' AS relation_type
    FROM parent_child_relations
    WHERE genealogy_id = :genealogy_id
    UNION
    SELECT child_member_id, parent_member_id, parent_role
    FROM parent_child_relations
    WHERE genealogy_id = :genealogy_id
    UNION
    SELECT spouse1_member_id, spouse2_member_id, 'spouse'
    FROM marriages
    WHERE genealogy_id = :genealogy_id
    UNION
    SELECT spouse2_member_id, spouse1_member_id, 'spouse'
    FROM marriages
    WHERE genealogy_id = :genealogy_id
),
walk AS (
    SELECT :start_id AS member_id, ',' || CAST(:start_id AS TEXT) || ',' AS path, '' AS relation_types, 0 AS depth
    UNION ALL
    SELECT e.to_id, walk.path || CAST(e.to_id AS TEXT) || ',', walk.relation_types || e.relation_type || ',', walk.depth + 1
    FROM walk
    JOIN edges e ON e.from_id = walk.member_id
    WHERE walk.depth < 12
      AND walk.path NOT LIKE '%,' || CAST(e.to_id AS TEXT) || ',%'
)
SELECT path, relation_types
FROM walk
WHERE member_id = :end_id
ORDER BY depth
LIMIT 1;
