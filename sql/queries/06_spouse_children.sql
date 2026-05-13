-- ============================================================
-- Task 4.1：配偶及子女查询
-- 给定一个成员 ID，查询其所有配偶及所有子女。
-- ============================================================
-- 当前：指定 id 为 %(member_id)s，目标族谱 %(genealogy_id)s
-- Web：成员关系页（members/relations）已含此逻辑，SQL 文件供验收使用。
--
-- 配偶是通过 spouse1 / spouse2 反查
-- 子女是从当前成员出发，指向 parent_child_relations 的 child
SELECT 'spouse' AS relationship_type,
  s.id AS record_id,
  spouse_member.id AS related_member_id,
  spouse_member.name AS related_name,
  spouse_member.gender AS related_gender,
  s.married_year
FROM marriages s
  JOIN members spouse_member ON (
    CASE
      WHEN s.spouse1_member_id = :member_id THEN s.spouse2_member_id
      ELSE s.spouse1_member_id
    END = spouse_member.id
  )
WHERE s.genealogy_id = :genealogy_id
  AND (
    s.spouse1_member_id = :member_id
    OR s.spouse2_member_id = :member_id
  )
UNION ALL
SELECT 'child' AS relationship_type,
  rel.id AS record_id,
  child_member.id AS related_member_id,
  child_member.name AS related_name,
  child_member.gender AS related_gender,
  NULL AS married_year
FROM parent_child_relations rel
  JOIN members child_member ON child_member.id = rel.child_member_id
WHERE rel.genealogy_id = :genealogy_id
  AND rel.parent_member_id = :member_id
ORDER BY relationship_type,
  related_member_id;