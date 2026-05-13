-- ============================================================
-- Task 4.4：查询超过 50 岁、且没有配偶的男性成员
-- 年龄以 lifespan（death_year - birth_year）衡量；
-- 若 death_year 为 NULL（仍存活），则以当前年份计算。
-- "无配偶"定义为在 marriages 表中找不到其 ID。
-- ============================================================
-- 给定 genealogy_id 参数
-- 对男性成员，计算 lifespan > 50，且不在 marriages 的任一方
SELECT m.id,
  m.name,
  m.birth_year,
  m.death_year,
  m.generation_no,
  CASE
    WHEN m.death_year IS NOT NULL THEN m.death_year - m.birth_year
    ELSE EXTRACT(
      YEAR
      FROM CURRENT_DATE
    )::int - m.birth_year
  END AS estimated_age
FROM members m
WHERE m.genealogy_id = :genealogy_id
  AND m.gender = 'male'
  AND m.birth_year IS NOT NULL
  AND (
    COALESCE(
      m.death_year,
      EXTRACT(
        YEAR
        FROM CURRENT_DATE
      )::int
    ) - m.birth_year
  ) > 50
  AND NOT EXISTS (
    SELECT 1
    FROM marriages mar
    WHERE mar.genealogy_id = m.genealogy_id
      AND (
        mar.spouse1_member_id = m.id
        OR mar.spouse2_member_id = m.id
      )
  )
ORDER BY estimated_age DESC,
  m.id;