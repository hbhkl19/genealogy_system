SELECT COUNT(*) AS genealogy_count FROM genealogies;
SELECT COUNT(*) AS member_count FROM members;
SELECT MAX(cnt) AS max_members_in_one_genealogy
FROM (
    SELECT genealogy_id, COUNT(*) AS cnt
    FROM members
    GROUP BY genealogy_id
) t;
SELECT MAX(generation_no) AS max_generation_no FROM members;
