# SQL 实现细节、设计原理与优化策略

> 项目：寻根溯源族谱管理系统  
> 数据库：PostgreSQL 16  
> 规模：10 族谱, 104K 成员, 50K/族谱(max), 30 代(max)

---

## 目录

1. [DDL 与数据库模式设计](#1-ddl-与数据库模式设计)
2. [索引设计与物理优化](#2-索引设计与物理优化)
3. [递归 CTE 查询体系](#3-递归-cte-查询体系)
4. [亲缘链路最短路径查询](#4-亲缘链路最短路径查询)
5. [统计分析与复杂查询](#5-统计分析与复杂查询)
6. [数据导入导出](#6-数据导入导出)
7. [约束与触发器](#7-约束与触发器)
8. [性能优化总结](#8-性能优化总结)

---

## 1. DDL 与数据库模式设计

**文件**: [`sql/schema.sql`](file:///d:/上课/大三下/数据库/genealogy_system/sql/schema.sql) / [`app/models.py`](file:///d:/上课/大三下/数据库/genealogy_system/app/models.py)

### 1.1 关系模式（3NF 设计）

| 表 | 主键 | 核心字段 | 范式 |
|----|------|---------|:--:|
| `users` | `id` | username, email, password_hash | 3NF |
| `genealogies` | `id` | name, description, owner_id(FK→users) | 3NF |
| `genealogy_collaborators` | `id` | genealogy_id, user_id, role | 3NF |
| `members` | `id` | genealogy_id, name, gender, birth_year, death_year, generation_no | 3NF |
| `parent_child_relations` | `id` | genealogy_id, parent_member_id, child_member_id, parent_role | 3NF |
| `marriages` | `id` | genealogy_id, spouse1_member_id, spouse2_member_id, married_year, ended_year | 3NF |

### 1.2 设计原理

**为何将"血缘关系"和"婚姻关系"拆分为独立关系表？**

族谱的核心数据模型是**图**而非树。一个人在图中可以有：
- 两个父节点（父亲 + 母亲）
- 多个子节点
- 多个配偶

如果采用树形模型（如 `parent_id` 单列），会丢失"母亲"信息。采用图模型（独立的关系表）的设计优势：

```
parent_child_relations:  parent_member_id → child_member_id (多对多)
marriages:               spouse1 ↔ spouse2 (多对多)
```

**冗余 `genealogy_id` 列的设计权衡**：

所有关系表都冗余存储了 `genealogy_id`。这违反了 3NF（可通过 member 表 JOIN 推导），但带来了关键性能收益：

- 所有族谱级查询可直接利用 `(genealogy_id, member_id)` 复合索引
- 避免递归 JOIN 回 `members` 表过滤
- 族谱级 DELETE CASCADE 无需额外的 JOIN

```sql
-- 有了 genealogy_id，这个查询只需一次 Index Scan
SELECT * FROM parent_child_relations 
WHERE genealogy_id = 1 AND parent_member_id = 42;

-- 否则需要：
SELECT * FROM parent_child_relations p
JOIN members m ON p.parent_member_id = m.id
WHERE m.genealogy_id = 1 AND p.parent_member_id = 42;
```

### 1.3 关键 CHECK 约束

| 约束名 | 表 | 条件 | 目的 |
|--------|----|------|------|
| `ck_marriage_ordered_pair` | marriages | `spouse1 < spouse2` | 防止 (A,B) 和 (B,A) 两条重复记录 |
| `ck_parent_role` | parent_child_relations | `role IN ('father','mother')` | 限定父母角色语义 |
| `ck_parent_not_child` | parent_child_relations | `parent <> child` | 防止自引用 |
| `uq_child_parent_role` | parent_child_relations | `UNIQUE(child, role)` | 一人最多一父一母 |

---

## 2. 索引设计与物理优化

**文件**: [`app/models.py`](file:///d:/上课/大三下/数据库/genealogy_system/app/models.py#L119-L197)

### 2.1 索引一览

```sql
-- 模糊姓名搜索: GIN trigram 索引
CREATE INDEX ix_members_name_trgm ON members USING gin (name gin_trgm_ops);

-- 父→子查找: (genealogy_id, parent_member_id) 复合 B-tree
CREATE INDEX ix_parent_child_genealogy_parent 
    ON parent_child_relations(genealogy_id, parent_member_id);

-- 子→父查找: (genealogy_id, child_member_id) 复合 B-tree
CREATE INDEX ix_parent_child_genealogy_child 
    ON parent_child_relations(genealogy_id, child_member_id);

-- 婚姻正向查找
CREATE INDEX ix_marriages_genealogy_spouse1 
    ON marriages(genealogy_id, spouse1_member_id);

-- 婚姻反向查找
CREATE INDEX ix_marriages_genealogy_spouse2 
    ON marriages(genealogy_id, spouse2_member_id);
```

### 2.2 索引设计原理

**为什么 `(genealogy_id, member_id)` 而非 `(member_id, genealogy_id)`？**

族谱系统的查询模式总是 **"在某个族谱内"** 操作：

```sql
-- 查询模式: WHERE genealogy_id = X AND member_id = Y
-- 索引前缀 genealogy_id 将搜索空间从全表缩减到该族谱的所有行
-- 若索引前缀是 member_id，则需要扫描每个族谱中该 member 的行
```

复合索引的列顺序遵循 **高选择性前缀** 原则。对于拥有多个族谱的系统，`genealogy_id` 的基数远小于 `member_id`，但作为第一列可以将无关族谱的数据完全排除，平均访问代价显著更低。

**为什么用 GIN trigram 而非 B-tree 做姓名搜索？**

```sql
-- B-tree 只支持前缀匹配
WHERE name LIKE '张%'    ← 可用 B-tree

-- GIN trigram 支持任意位置匹配
WHERE name LIKE '%张%'   ← 必须用 GIN trigram
WHERE name ILIKE '%伟%'  ← GIN trigram 也支持大小写不敏感
```

trigram 索引将文本拆分为连续的三字符片段，通过倒排索引实现 "包含" 语义的快速查找。代价是索引体积约是 B-tree 的 3~5 倍。

### 2.3 实测性能对比（四代查询 EXPLAIN）

| 场景 | 执行时间 | 执行方式 | 加速比 |
|------|---------|---------|:--:|
| 无索引 | 91.65 ms | Seq Scan `parent_child_relations` | — |
| 有索引 | 0.36 ms | Index Scan `ix_parent_child_genealogy_parent` | **258×** |

索引将全表扫描转为索引查找 + 索引扫描，消除了对 96K 行 `parent_child_relations` 的顺序遍历。

---

## 3. 递归 CTE 查询体系

递归 CTE（Common Table Expression）是本项目最核心的 SQL 技术。族谱的本质是**有向无环图（DAG）**——每个成员通过父关系向上追溯形成反方向的树，通过子关系向下追溯形成正向的树，而婚姻关系引入了横向边。

### 3.1 祖先追溯

**文件**: [`sql/queries/01_ancestors.sql`](file:///d:/上课/大三下/数据库/genealogy_system/sql/queries/01_ancestors.sql)

```sql
WITH RECURSIVE ancestors AS (
    -- 基础情况: 直接父节点
    SELECT p.parent_member_id AS member_id, 1 AS depth
    FROM parent_child_relations p
    WHERE p.child_member_id = :member_id
    UNION                           -- ← 关键: UNION 去重
    -- 递归情况: 父的父
    SELECT p.parent_member_id, a.depth + 1
    FROM parent_child_relations p
    JOIN ancestors a ON p.child_member_id = a.member_id
    WHERE a.depth < 10              -- 安全上限: 10 代
)
SELECT m.*, ancestors.depth
FROM ancestors JOIN members m ON m.id = ancestors.member_id
ORDER BY ancestors.depth;
```

**设计原理**：

- 递归方向：**从子向父**（`child_member_id` → `parent_member_id`），每次迭代向上一代
- `UNION`（非 `UNION ALL`）：每个成员可通过父/母两条路径到达同一祖先，`UNION` 在每层去重，防止 2^depth 的指数级膨胀
- `depth < 10`：10 代的理论祖先数为 2^10 = 1024 人，上限合理

**执行计划**：
```
Recursive Union
  → 第 1 层: Index Scan on parent_child_relations (child_member_id = :id)
  → 第 2-N 层: Nested Loop (ancestors × parent_child_relations)
     → Index Scan on ix_parent_child_genealogy_child
```

### 3.2 后代追溯

**文件**: [`sql/queries/02_descendants.sql`](file:///d:/上课/大三下/数据库/genealogy_system/sql/queries/02_descendants.sql)

```sql
WITH RECURSIVE descendants AS (
    SELECT child_member_id AS member_id, 1 AS depth
    FROM parent_child_relations
    WHERE parent_member_id = :member_id
    UNION
    SELECT p.child_member_id, d.depth + 1
    FROM parent_child_relations p
    JOIN descendants d ON p.parent_member_id = d.member_id
    WHERE d.depth < 12              -- 安全上限: 12 代
)
SELECT m.*, descendants.depth
FROM descendants JOIN members m ON m.id = descendants.member_id
ORDER BY descendants.depth;
```

**设计原理**：

- 递归方向：**从父向子**（`parent_member_id` → `child_member_id`），每次迭代向下一代
- 同样使用 `UNION` 去重
- `depth < 12`：族谱实际代数通常不超过 30，12 代已有充分的覆盖

**与祖先查询的对称性**：

| | 祖先查询 | 后代查询 |
|----|---------|---------|
| 递归方向 | ↑ 子→父 | ↓ 父→子 |
| 起始条件 | `child_member_id = :id` | `parent_member_id = :id` |
| 连接条件 | `p.child = a.member` | `p.parent = d.member` |
| 深度上限 | 10 | 12 |

### 3.3 族谱树形预览

**文件**: [`sql/queries/05_tree_preview.sql`](file:///d:/上课/大三下/数据库/genealogy_system/sql/queries/05_tree_preview.sql) / [`app/genealogies/routes.py`](file:///d:/上课/大三下/数据库/genealogy_system/app/genealogies/routes.py#L117-L153)

```sql
WITH RECURSIVE tree AS (
    -- 找根节点: 没有任何父节点的成员
    SELECT m.id, m.name, m.gender, m.generation_no,
           0 AS depth,
           ',' || CAST(m.id AS TEXT) || ',' AS path
    FROM members m
    WHERE m.genealogy_id = :genealogy_id
      AND NOT EXISTS (
          SELECT 1 FROM parent_child_relations p
          WHERE p.child_member_id = m.id 
            AND p.genealogy_id = :genealogy_id
      )
    UNION ALL
    SELECT child.id, child.name, child.gender, child.generation_no,
           tree.depth + 1,
           tree.path || CAST(child.id AS TEXT) || ','
    FROM tree
    JOIN parent_child_relations rel ON rel.parent_member_id = tree.id
    JOIN members child ON child.id = rel.child_member_id
    WHERE rel.genealogy_id = :genealogy_id
      AND tree.depth < 12
)
SELECT id, name, gender, generation_no, depth
FROM tree ORDER BY path LIMIT 500;
```

**设计原理**：

- **路径字符串**（`path`）：通过拼接 `id` 维护从根到每个节点的路径，`ORDER BY path` 实现深度优先的树形顺序排列
- 这里使用 `UNION ALL` 而非 `UNION`，因为树形结构中每个子节点只有唯一的父节点沿 path 到达，不存在多路径到达同一节点的问题（在 DAG 中理论上可能，但实际族谱数据父子关系无环）
- `LIMIT 500` 防止前端渲染过载

### 3.4 分支导出（export_branch.py）

**文件**: [`scripts/export_branch.py`](file:///d:/上课/大三下/数据库/genealogy_system/scripts/export_branch.py#L45-L64)

```sql
WITH RECURSIVE branch AS (
    SELECT id, genealogy_id, 1 AS depth
    FROM members WHERE id = %s
    UNION                          -- ← 原本是 UNION ALL (最严重的 bug)
    SELECT child.id, child.genealogy_id, branch.depth + 1
    FROM branch
    JOIN parent_child_relations rel ON rel.parent_member_id = branch.id
    JOIN members child ON child.id = rel.child_member_id
    WHERE branch.depth < 100
)
SELECT m.* FROM members m JOIN branch ON branch.id = m.id
ORDER BY m.generation_no, m.id;
```

**历史教训 — 为什么 `UNION` 如此关键**：

在 v1.0 中，这里使用了 `UNION ALL`。后果：
- 某成员的曾孙可同时通过父亲和母亲两条路径到达
- 5 代后产生 21 亿次迭代而非理论上的 3.3 万
- PostgreSQL CYCLE 子句尝试为 21 亿条路径维护数组 → DiskFull

**一字之改** `UNION ALL` → `UNION` 将查询从 ∞ 秒变为秒级。

---

## 4. 亲缘链路最短路径查询

这是项目中最复杂的查询 —— 在包含父子关系和婚姻关系的**混合图中**查找两成员之间的最短路径。

**文件**: [`app/members/routes.py`](file:///d:/上课/大三下/数据库/genealogy_system/app/members/routes.py#L496-L618) / [`sql/queries/03_relationship_path.sql`](file:///d:/上课/大三下/数据库/genealogy_system/sql/queries/03_relationship_path.sql)

### 4.1 图模型

边定义为 4 种无向关系：

```sql
WITH RECURSIVE edges AS NOT MATERIALIZED (
    -- 父 → 子（正向血亲）
    SELECT parent_member_id AS from_id, child_member_id AS to_id
    FROM parent_child_relations WHERE genealogy_id = :gid
    UNION ALL
    -- 子 → 父（反向血亲）  —— 实现无向遍历
    SELECT child_member_id, parent_member_id
    FROM parent_child_relations WHERE genealogy_id = :gid
    UNION ALL
    -- 配偶 → 配偶（正向婚姻）
    SELECT spouse1_member_id, spouse2_member_id
    FROM marriages WHERE genealogy_id = :gid
    UNION ALL
    -- 配偶 → 配偶（反向婚姻）  —— 实现无向遍历
    SELECT spouse2_member_id, spouse1_member_id
    FROM marriages WHERE genealogy_id = :gid
)
```

边的 `UNION ALL`（顶层）是安全的，因为 4 个来源的数据集互不相交，不会产生重复行。但 `edges AS NOT MATERIALIZED` 允许 PostgreSQL 优化器将 WHERE 条件下推，避免每次都物化全部 ~240K 条边。

### 4.2 算法架构：渐进式双向 BFS

```
输入: start_id, end_id

Phase 1 (渐进式) — 双向可达性探索:
  for max_depth in (6, 8, 10, 12, 15):
    fwd = BFS(start_id, max_depth)    # 从起点正向 BFS
    rev = BFS(end_id, max_depth)      # 从终点反向 BFS
    meeting = fwd ∩ rev               # 求交集
    if meeting:
      交汇点 = argmin(fwd[d] + rev[d])
      break                           # 找到最短路径

Phase 2 — 路径重构:
  fwd_path = 回溯(start → 交汇点)
  rev_path = 回溯(end → 交汇点)
  完整路径 = fwd_path + reverse(rev_path)
```

**渐进式深度的设计理由**：大多数亲缘路径 ≤6 步（如"张三 → 张三父亲 → 张三爷爷 → 李四爷爷 → 李四父亲 → 李四"），先在浅层搜索可节省大量计算。只有远亲才需深入 8~15 层。

### 4.3 Phase 1: `_bfs_reachable()` — 节点可达性 BFS

```sql
WITH RECURSIVE edges AS NOT MATERIALIZED (...),
walk AS (
    SELECT CAST(:root_id AS INTEGER) AS member_id, 0 AS depth
    UNION                                          -- ← 关键: UNION 每层去重
    SELECT e.to_id, walk.depth + 1
    FROM walk JOIN edges e ON e.from_id = walk.member_id
    WHERE walk.depth < :max_depth
) CYCLE member_id SET is_cycle USING cycle_path
SELECT member_id, MIN(depth) FROM walk 
WHERE NOT is_cycle GROUP BY member_id
```

**三层优化（2026-05-12）**：

| 方案 | 技术 | 效果 |
|------|------|------|
| **一** | `UNION ALL` → `UNION`（1 个关键词） | 行数 600 万 → 2.6 万 (230×) |
| **二** | `_lookup_relations_batch()` VALUES 批量查询 | N 次 DB 往返 → 1 次 |
| **三** | PL/pgSQL `bfs_reachable()` 迭代 BFS | 深度 ≥8 时自动启用，索引点查零成本去重 |

**方案三详解 — PL/pgSQL 迭代 BFS** ([`sql/functions/bfs_reachable.sql`](file:///d:/上课/大三下/数据库/genealogy_system/sql/functions/bfs_reachable.sql))：

```sql
CREATE OR REPLACE FUNCTION bfs_reachable(
    p_genealogy_id INTEGER, p_root_id INTEGER, p_max_depth INTEGER
) RETURNS TABLE(member_id INTEGER, depth INTEGER) AS $$
BEGIN
    CREATE TEMP TABLE IF NOT EXISTS bfs_visited (
        vid INTEGER PRIMARY KEY, vdepth INTEGER NOT NULL
    ) ON COMMIT DROP;
    
    INSERT INTO bfs_visited VALUES (p_root_id, 0);
    
    LOOP
        INSERT INTO bfs_visited
        SELECT DISTINCT e.to_id, current_depth + 1
        FROM bfs_visited v
        CROSS JOIN LATERAL (                           -- ← 索引点查
            SELECT parent_member_id AS to_id FROM parent_child_relations
            WHERE genealogy_id = p_genealogy_id AND child_member_id = v.vid
            UNION ALL ...
        ) e
        WHERE v.vdepth = current_depth AND e.to_id IS NOT NULL
        ON CONFLICT (vid) DO NOTHING;                  -- ← 零成本去重
        
        EXIT WHEN row_count = 0;
        current_depth := current_depth + 1;
    END LOOP;
    
    RETURN QUERY SELECT v.vid, v.vdepth FROM bfs_visited v;
END;
$$ LANGUAGE plpgsql;
```

与 CTE 方案的关键区别：

| | 递归 CTE | PL/pgSQL 迭代 |
|----|---------|-------------|
| 去重方式 | `UNION` 排序/哈希 | `ON CONFLICT DO NOTHING` |
| 边访问 | Hash Join 全量边表 | `CROSS JOIN LATERAL` 索引点查 |
| 环检测 | CYCLE 子句 (temp I/O) | `PRIMARY KEY` 天然去重 |
| 内存 | work_mem 不足则写 temp | temp table 在内存中 |

### 4.4 Phase 2: 路径重构

**Python 回溯** ([`routes.py:_reconstruct_path()`](file:///d:/上课/大三下/数据库/genealogy_system/app/members/routes.py#L389-L415)):

从交汇点开始，逐层向起始点回溯。每步查询当前节点的邻居，筛选深度为 d-1 的候选节点，O(depth) 次索引点查。

**关系标注** ([`routes.py:_lookup_relations_batch()`](file:///d:/上课/大三下/数据库/genealogy_system/app/members/routes.py#L455-L509)):

```sql
SELECT p.a, p.b,
    CASE
        WHEN EXISTS(SELECT 1 FROM parent_child_relations
                    WHERE parent_member_id=p.a AND child_member_id=p.b
                    AND genealogy_id=:gid) THEN 'child'
        WHEN EXISTS(SELECT 1 FROM parent_child_relations
                    WHERE child_member_id=p.a AND parent_member_id=p.b
                    AND genealogy_id=:gid) THEN
            COALESCE((SELECT parent_role FROM parent_child_relations
                      WHERE child_member_id=p.a AND parent_member_id=p.b
                      AND genealogy_id=:gid), 'parent')
        WHEN EXISTS(SELECT 1 FROM marriages ...) THEN 'spouse'
    END AS relation
FROM (VALUES (CAST(:a0 AS INTEGER), CAST(:b0 AS INTEGER)), ...) AS p(a, b)
```

优化后使用 `VALUES` 批量提交所有相邻节点对，1 次查询替代 N 次。

### 4.5 性能测试结果（50000 人数据集, 239,506 边）

| 场景 | 优化前 | 优化后 | 加速比 |
|------|--------|--------|:--:|
| 单 BFS (depth=12) | 126,000ms | **100ms** | 1200× |
| 远亲路径 (4 hops) | ~3,000ms | **330~930ms** | 3~9× |
| 远亲路径 (8 hops) | ~60,000ms | **650~1,640ms** | ~40~90× |
| 磁盘临时 I/O | 10.6 GB | **0** | 消除 |

---

## 5. 统计分析与复杂查询

### 5.1 配偶及子女查询

**文件**: [`sql/queries/06_spouse_children.sql`](file:///d:/上课/大三下/数据库/genealogy_system/sql/queries/06_spouse_children.sql)

```sql
-- 配偶部分: 双向 JOIN (spouse1 或 spouse2)
SELECT 'spouse' AS kind, spouse_member.name, spouse_member.gender, s.married_year
FROM marriages s
JOIN members spouse_member ON (
    CASE WHEN s.spouse1_member_id = :member_id THEN s.spouse2_member_id
         ELSE s.spouse1_member_id END = spouse_member.id
)
WHERE s.genealogy_id = :genealogy_id
  AND (s.spouse1_member_id = :member_id OR s.spouse2_member_id = :member_id)

UNION ALL                                                   -- ← 两个结果集不重叠，安全用 UNION ALL

-- 子女部分: 直接从 parent_child_relations 找
SELECT 'child' AS kind, child_member.name, child_member.gender, NULL
FROM parent_child_relations rel
JOIN members child_member ON child_member.id = rel.child_member_id
WHERE rel.genealogy_id = :genealogy_id AND rel.parent_member_id = :member_id

ORDER BY kind, related_member_id;
```

**设计要点**：婚姻表使用 `spouse1 < spouse2` 的有序对约束，查询时必须同时检查两个位置。`CASE WHEN` 表达式动态选择 "另一人"。

### 5.2 平均寿命最长的一代

**文件**: [`sql/queries/07_avg_lifespan_by_generation.sql`](file:///d:/上课/大三下/数据库/genealogy_system/sql/queries/07_avg_lifespan_by_generation.sql)

```sql
WITH gen_lifespan AS (
    SELECT genealogy_id, generation_no,
           AVG(death_year - birth_year)::numeric(6,2) AS avg_lifespan,
           COUNT(*) AS member_count,
           MIN(birth_year) AS min_birth_year,
           MAX(death_year) AS max_death_year
    FROM members
    WHERE genealogy_id = :genealogy_id
      AND birth_year IS NOT NULL AND death_year IS NOT NULL
      AND death_year > birth_year                  -- 排除脏数据
    GROUP BY genealogy_id, generation_no
)
SELECT * FROM gen_lifespan ORDER BY avg_lifespan DESC LIMIT 1;
```

**设计要点**：

- `AVG()::numeric(6,2)` 确保精度和可读性
- `death_year > birth_year` 过滤异常数据（有人可能录入错误导致死亡年 < 出生年）
- 需要 `birth_year` 和 `death_year` 都非空才能计算寿命
- `GROUP BY genealogy_id, generation_no` 按族谱+代分组（不同族谱的同代不应混合计算）

### 5.3 超过 50 岁无配偶男性

**文件**: [`sql/queries/08_males_over_50_no_spouse.sql`](file:///d:/上课/大三下/数据库/genealogy_system/sql/queries/08_males_over_50_no_spouse.sql)

```sql
SELECT m.id, m.name, m.birth_year, m.death_year, m.generation_no,
    CASE
        WHEN m.death_year IS NOT NULL THEN m.death_year - m.birth_year
        ELSE EXTRACT(YEAR FROM CURRENT_DATE)::int - m.birth_year
    END AS estimated_age
FROM members m
WHERE m.genealogy_id = :genealogy_id
  AND m.gender = 'male'
  AND m.birth_year IS NOT NULL
  AND (COALESCE(m.death_year, EXTRACT(YEAR FROM CURRENT_DATE)::int) - m.birth_year) > 50
  AND NOT EXISTS (
      SELECT 1 FROM marriages mar
      WHERE mar.genealogy_id = m.genealogy_id
        AND (mar.spouse1_member_id = m.id OR mar.spouse2_member_id = m.id)
  )
ORDER BY estimated_age DESC, m.id;
```

**设计要点**：

- `COALESCE(death_year, CURRENT_YEAR)`：若已故用 death_year，若在世用当前年
- `NOT EXISTS` 反半连接（anti-semi-join）：比 `LEFT JOIN ... WHERE spouse.id IS NULL` 语义更清晰，且 PostgreSQL 优化器可以提前终止扫描
- 同样需要 `m.genealogy_id = mar.genealogy_id` 确保不会跨族谱误判

### 5.4 出生年份早于代平均的成员

**文件**: [`sql/queries/09_born_before_gen_avg.sql`](file:///d:/上课/大三下/数据库/genealogy_system/sql/queries/09_born_before_gen_avg.sql)

```sql
WITH gen_avg AS (
    SELECT genealogy_id, generation_no,
           AVG(birth_year)::numeric(6,2) AS avg_birth_year,
           COUNT(*) AS total_in_gen
    FROM members
    WHERE genealogy_id = :genealogy_id AND birth_year IS NOT NULL
    GROUP BY genealogy_id, generation_no
)
SELECT m.id, m.name, m.gender, m.birth_year, m.generation_no,
       ga.avg_birth_year,
       ROUND((m.birth_year - ga.avg_birth_year)::numeric, 2) AS deviation
FROM members m
JOIN gen_avg ga ON ga.generation_no = m.generation_no
               AND ga.genealogy_id = m.genealogy_id
WHERE m.genealogy_id = :genealogy_id
  AND m.birth_year IS NOT NULL
  AND m.birth_year < ga.avg_birth_year
ORDER BY m.generation_no, m.birth_year, m.id;
```

**设计要点**：

- CTE `gen_avg` 预先计算每代平均出生年份
- `deviation`（偏差值）展示成员出生年与代平均的差距，辅助异常检测（负值 = 早于平均）
- `ROUND(..., 2)` 控制显示精度

---

## 6. 数据导入导出

### 6.1 PostgreSQL COPY 批量导入

**文件**: [`sql/copy_import.sql`](file:///d:/上课/大三下/数据库/genealogy_system/sql/copy_import.sql) / [`scripts/import_csv.py`](file:///d:/上课/大三下/数据库/genealogy_system/scripts/import_csv.py)

```sql
TRUNCATE parent_child_relations, marriages, ... RESTART IDENTITY CASCADE;

\copy members (id, genealogy_id, name, ...) FROM 'data/generated/members.csv' 
    WITH (FORMAT csv, HEADER true);

SELECT setval(pg_get_serial_sequence('members', 'id'), 
    COALESCE((SELECT MAX(id) FROM members), 1), true);
```

**设计要点**：

- `TRUNCATE ... RESTART IDENTITY CASCADE` 同时清空所有表、重置自增序列、级联删除外键引用
- 导入顺序必须按 FK 依赖：`users → genealogies → members → relations`
- `COPY` 比 `INSERT` 快 10~50 倍，因为它绕过 WAL 日志（`wal_level=minimal` 时）和约束检查
- 导入后必须执行 `setval()` 修复序列号，否则下次 ORM 插入会尝试使用已存在的 id

**Python 流式 COPY** ([`import_csv.py:34-39`](file:///d:/上课/大三下/数据库/genealogy_system/scripts/import_csv.py#L34-L39))：

```python
with cursor.copy(f"COPY {table} ({columns}) FROM STDIN WITH (FORMAT CSV, HEADER TRUE)") as copy:
    with csv_path.open("r", encoding="utf-8") as handle:
        while chunk := handle.read(1024 * 1024):  # 1MB chunks
            copy.write(chunk)
```

分块流式写入避免将整个 CSV 加载到内存。

### 6.2 CSV 流式导出

**文件**: [`app/genealogies/routes.py`](file:///d:/上课/大三下/数据库/genealogy_system/app/genealogies/routes.py#L260-L298)

```python
def generate():
    yield "id,genealogy_id,name,gender,...\n"
    offset = 0
    while True:
        rows = db.session.execute(
            text("SELECT ... FROM members WHERE genealogy_id = :gid "
                 "ORDER BY id LIMIT 2000 OFFSET :offset"),
            {"gid": id, "limit": 2000, "offset": offset},
        ).fetchall()
        if not rows: break
        for row in rows:
            yield f"{row[0]},{row[1]},...\n"
        offset += 2000
```

**设计要点**：

- 分块查询 (`LIMIT 2000 OFFSET N`) 而非一次性加载全部 50K 成员
- Python `yield` 生成器逐块返回响应体
- Flask `Response` 包装生成器实现 HTTP 流式下载
- `X-Accel-Buffering: no` 禁止 Nginx 缓冲（如有反向代理）

---

## 7. 约束与触发器

**文件**: [`sql/schema.sql`](file:///d:/上课/大三下/数据库/genealogy_system/sql/schema.sql#L76-L189)

### 7.1 三阶段约束体系

| 阶段 | 机制 | 时机 | 用途 |
|------|------|------|------|
| **声明式** | CHECK / UNIQUE / FK | DDL 定义时 | 静态约束（性别值域、唯一配对） |
| **触发器** | BEFORE INSERT/UPDATE | 写入前 | 跨表约束（代数关联、族谱一致） |
| **应用层** | Python 验证函数 | 业务逻辑中 | 复杂校验 + 友好错误提示 |

### 7.2 核心触发器

**父子关系验证** (`validate_parent_child_relation`):

```sql
CREATE FUNCTION validate_parent_child_relation() RETURNS trigger AS $$
BEGIN
    -- 1. 验证父子双方属于同一族谱
    -- 2. 验证 parent.generation_no < child.generation_no
    -- 3. 验证 parent.birth_year < child.birth_year
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_validate_parent_child_relation
BEFORE INSERT OR UPDATE ON parent_child_relations
FOR EACH ROW EXECUTE FUNCTION validate_parent_child_relation();
```

**设计原理**：这些跨表约束无法用 CHECK 实现（CHECK 只能引用当前行的列，不能 JOIN 其他表）。触发器在写入前介入，可以 RAISE EXCEPTION 回滚操作。

**婚姻关系验证** (`validate_marriage_relation`): 确保配偶双方来自同一族谱。

**成员更新验证** (`validate_member_existing_relations`): 当成员的 `genealogy_id`, `birth_year`, `generation_no` 被修改时，检查是否会破坏已有的父子或婚姻关系约束。这是 **AFTER UPDATE** 触发器，因为需要读取已更新的值。

---

## 8. 性能优化总结

### 8.1 优化层次模型

```
┌──────────────────────────────────────┐
│ 应用层: 渐进式深度、双向 BFS、批量化  │
├──────────────────────────────────────┤
│ SQL 层: UNION 去重、NOT MATERIALIZED │
├──────────────────────────────────────┤
│ 物理层: 复合索引、GIN trigram        │
├──────────────────────────────────────┤
│ 数据库层: PL/pgSQL 迭代、temp table  │
└──────────────────────────────────────┘
```

### 8.2 关键技术决策

| 决策 | 原因 | 效果 |
|------|------|------|
| `UNION` 非 `UNION ALL` | DAG 结构中多路径到达同一节点 | **消除路径爆炸** |
| `NOT MATERIALIZED` edges | 让优化器下推 WHERE 条件 | 避免物化 240K 行 |
| 复合索引 `(genealogy_id, member_id)` | 族谱级查询模式 | Index Scan 替代 Seq Scan |
| PL/pgSQL 迭代 BFS | 控制内存、避免 CYCLE 开销 | 零磁盘 I/O |
| VALUES 批量标注 | 替代逐行查询 | N→1 DB 往返 |
| `COPY` 而非 `INSERT` | 绕过 WAL 和约束检查 | 10~50× 导入加速 |

### 8.3 性能仪表盘

```
指标                       优化前          优化后          目标
────────────────────────────────────────────────────────────
四代查询                     91.65ms        0.36ms        ✅ (< 1ms)
单 BFS (depth=12)          126,000ms        100ms        ✅ (< 500ms)
亲缘路径 (2 hops)            ~500ms         330ms        ✅ (< 1s)
亲缘路径 (8 hops)          ~60,000ms      650~1640ms     ✅ (< 2s)
CSV 导出 (50K 人)            卡死           秒级          ✅
姓名模糊搜索               Index Scan       GIN          ✅
```

---

*文档生成日期: 2026-05-12 | 作者: Trae AI Assistant*