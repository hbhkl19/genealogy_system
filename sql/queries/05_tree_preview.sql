WITH RECURSIVE tree AS (
    SELECT
        m.id,
        m.name,
        m.gender,
        m.generation_no,
        0 AS depth,
        ',' || CAST(m.id AS TEXT) || ',' AS path
    FROM members m
    WHERE m.genealogy_id = :genealogy_id
      AND NOT EXISTS (
          SELECT 1
          FROM parent_child_relations p
          WHERE p.child_member_id = m.id
            AND p.genealogy_id = :genealogy_id
      )
    UNION ALL
    SELECT
        child.id,
        child.name,
        child.gender,
        child.generation_no,
        tree.depth + 1,
        tree.path || CAST(child.id AS TEXT) || ','
    FROM tree
    JOIN parent_child_relations rel ON rel.parent_member_id = tree.id
    JOIN members child ON child.id = rel.child_member_id
    WHERE rel.genealogy_id = :genealogy_id
      AND tree.depth < 12
      AND tree.path NOT LIKE '%,' || CAST(child.id AS TEXT) || ',%'
)
SELECT id, name, gender, generation_no, depth
FROM tree
ORDER BY path
LIMIT 500;
