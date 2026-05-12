-- ============================================================
-- Task 4.3：统计平均寿命最长的一代人（辈分）
-- 针对指定族谱，按 generation_no 分组计算平均寿命，
-- 选出平均寿命最高的那一代。
-- ============================================================

-- 给定 genealogy_id 参数，统计目标族谱
-- 仅统计 birth_year 和 death_year 均非空的成员
-- 寿命 = death_year - birth_year
-- 按代分组，按平均寿命降序排列后取 TOP 1

WITH gen_lifespan AS (
    SELECT
        genealogy_id,
        generation_no,
        AVG(death_year - birth_year)::numeric(6,2) AS avg_lifespan,
        COUNT(*) AS member_count,
        MIN(birth_year) AS min_birth_year,
        MAX(death_year) AS max_death_year
    FROM members
    WHERE genealogy_id = :genealogy_id
      AND birth_year IS NOT NULL
      AND death_year IS NOT NULL
      AND death_year > birth_year
    GROUP BY genealogy_id, generation_no
)
SELECT
    genealogy_id,
    generation_no,
    avg_lifespan,
    member_count,
    min_birth_year,
    max_death_year
FROM gen_lifespan
ORDER BY avg_lifespan DESC
LIMIT 1;