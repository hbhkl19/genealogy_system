WITH RECURSIVE edges AS (
    SELECT parent_member_id AS from_id, child_member_id AS to_id
    FROM parent_child_relations
    WHERE genealogy_id = :genealogy_id
    UNION
    SELECT child_member_id, parent_member_id
    FROM parent_child_relations
    WHERE genealogy_id = :genealogy_id
    UNION
    SELECT spouse1_member_id, spouse2_member_id
    FROM marriages
    WHERE genealogy_id = :genealogy_id
    UNION
    SELECT spouse2_member_id, spouse1_member_id
    FROM marriages
    WHERE genealogy_id = :genealogy_id
),
walk AS (
    SELECT :start_id AS member_id, ARRAY[:start_id] AS path, 0 AS depth
    UNION ALL
    SELECT e.to_id, walk.path || e.to_id, walk.depth + 1
    FROM walk
    JOIN edges e ON e.from_id = walk.member_id
    WHERE walk.depth < 12
      AND NOT e.to_id = ANY(walk.path)
)
SELECT path
FROM walk
WHERE member_id = :end_id
ORDER BY depth
LIMIT 1;
