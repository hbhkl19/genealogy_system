-- ============================================================
-- Task 4.5：找出出生年份早于该辈分平均出生年份的成员
-- 对指定族谱，先按 generation_no 分组计算 avg_birth_year，
-- 再筛选出 birth_year < avg_birth_year_of_generation 的成员。
-- ============================================================
-- 给定 genealogy_id 参数
-- 使用子查询先算出每代的平均出生年份，再 JOIN 筛选
WITH gen_avg AS (
  SELECT genealogy_id,
    generation_no,
    AVG(birth_year)::numeric(6, 2) AS avg_birth_year,
    COUNT(*) AS total_in_gen
  FROM members
  WHERE genealogy_id = :genealogy_id
    AND birth_year IS NOT NULL
  GROUP BY genealogy_id,
    generation_no
)
SELECT m.id,
  m.name,
  m.gender,
  m.birth_year,
  m.generation_no,
  ga.avg_birth_year,
  ROUND((m.birth_year - ga.avg_birth_year)::numeric, 2) AS deviation
FROM members m
  JOIN gen_avg ga ON ga.generation_no = m.generation_no
  AND ga.genealogy_id = m.genealogy_id
WHERE m.genealogy_id = :genealogy_id
  AND m.birth_year IS NOT NULL
  AND m.birth_year < ga.avg_birth_year
ORDER BY m.generation_no,
  m.birth_year,
  m.id;