# 答辩问答：关键技术细节详解

> 项目：寻根溯源族谱管理系统  
> 面向：教师可能提出的 5 类深入技术问题

---

## 问题一：为什么使用 PostgreSQL？

### 直接回答

选择 PostgreSQL 而非 MySQL 或 SQLite，是因为族谱系统的核心需求——**图遍历**（递归查询祖先/后代/亲缘路径）和**高级索引**——只有 PostgreSQL 能在单一数据库内完整、高效地支持。

### 逐一比较

| 需求 | PostgreSQL 16 | MySQL 8.0 | SQLite |
|------|:--:|:--:|:--:|
| **递归 CTE** | ✅ 完整支持 + CYCLE 子句 | ✅ 支持但无 CYCLE 子句 | ✅ 支持但性能差 |
| **PL/pgSQL 存储过程** | ✅ 完整的过程式语言 | ⚠️ 语法不同，功能受限 | ❌ 无 |
| **GIN 倒排索引** | ✅ 原生支持 pg_trgm | ❌ 无对应功能 | ❌ 无 |
| **EXPLAIN ANALYZE** | ✅ 最详细的执行计划 | ⚠️ 格式不同 | ⚠️ 功能有限 |
| **COPY 协议** | ✅ 二进制批量导入 | ⚠️ LOAD DATA 语法 | ⚠️ .import 命令 |
| **CYCLE 子句** | ✅ 原生环检测 | ❌ 需手动实现 | ❌ 需手动实现 |

### 分点详述

**1. 递归 CTE + CYCLE 子句**

族谱的核心操作——查找某人的所有祖先——本质是在一个有向无环图（DAG）上进行图遍历。PostgreSQL 的 `WITH RECURSIVE` 语法是 SQL 标准定义的方式，而 `CYCLE` 子句（PostgreSQL 14+ 新增）提供了原生的环检测能力：

```sql
WITH RECURSIVE walk AS (
    SELECT ... FROM ...
    UNION
    SELECT ... FROM walk JOIN ...
) CYCLE member_id SET is_cycle USING cycle_path
SELECT ... WHERE NOT is_cycle;
```

MySQL 8.0 虽然支持递归 CTE，但没有 CYCLE 子句。如果图中存在环（例如数据录入错误导致 A→B→C→A），MySQL 的查询会无限循环直至超时。我们的项目在调试阶段确实遇到过此类问题，CYCLE 子句直接解决了它。

**2. pg_trgm 扩展 — GIN trigram 索引**

族谱系统必须支持"按姓名模糊搜索"（如搜索"伟"匹配"周伟"、"刘伟强"等）。这个需求在传统 B-tree 索引下无法实现：

```sql
-- B-tree 只能支持前缀匹配
WHERE name LIKE '周%'   -- ✅ 能用 B-tree

-- 任意位置匹配无法用 B-tree
WHERE name LIKE '%周%'  -- ❌ B-tree 无能无力

-- GIN trigram 可以
WHERE name ILIKE '%周%' -- ✅ pg_trgm 原生支持
```

PostgreSQL 的 pg_trgm 扩展将字符串按三字符滑动窗口拆分，构建倒排索引（类似搜索引擎），天然支持任意位置的模糊匹配。

**3. PL/pgSQL 存储过程**

项目中的 `bfs_reachable()` 函数是一个用 PL/pgSQL 编写的迭代式 BFS 算法：

```sql
CREATE FUNCTION bfs_reachable(INTEGER, INTEGER, INTEGER) 
RETURNS TABLE(...) AS $$
BEGIN
    -- 使用 temp table、CROSS JOIN LATERAL、循环控制等
END;
$$ LANGUAGE plpgsql;
```

这需要数据库支持过程式编程（循环、条件判断、游标、异常处理）。MySQL 的存储过程语法和能力都弱于 PL/pgSQL，SQLite 则完全没有存储过程。

**4. 为什么不用图数据库（Neo4j 等）？**

这是一个合理的问题。族谱确实是图结构。不用图数据库的原因是：

- **课程要求**：数据库课程要求使用关系型数据库，考察范式设计、SQL 编写、索引优化等核心技能
- **证明能力**：在 RDBMS 上实现图遍历，恰恰证明了掌握了数据库的高级特性（递归 CTE、存储函数），这比"直接用图数据库"更能展示能力
- **统一技术栈**：用户系统、权限管理、统计查询都是经典的关系型场景，用 RDBMS 更自然

---

## 问题二：如何理解 `CREATE INDEX ... ON ...`？索引结构和物理优化原理

### 2.1 B-tree 复合索引

以项目中最关键的索引为例：

```sql
CREATE INDEX ix_parent_child_genealogy_parent
ON parent_child_relations(genealogy_id, parent_member_id);
```

**B-tree 内部结构**：

B-tree（平衡多路搜索树）是 PostgreSQL 的默认索引类型。它维护键值的有序排列，每个节点可以包含多个键和子节点指针，树的高度非常低（通常 2~4 层）。

```
B-tree 结构示意:
                     [1,42 | 1,108 | ...]
                    /        |          \
              [1,5|1,12]  [1,50|1,66]  [1,200|...]
              /    |    \                   |
          叶子 → 叶子 → 叶子           叶子 → 指向数据行
          (1,5,R1)                       的 CTID
          (1,12,R3)
```

对于复合索引 `(genealogy_id, parent_member_id)`，键的排序规则是**先按 genealogy_id 排序，genealogy_id 相同时再按 parent_member_id 排序**。这决定了它能高效处理的查询模式。

**它能加速的查询**：
```sql
-- ✅ 前缀匹配: 精确定位到 genealogy_id=1 的所有行，再二分查找 parent=42
WHERE genealogy_id = 1 AND parent_member_id = 42

-- ✅ 前缀匹配: 精确定位 genealogy_id=1，但需扫描该族谱下所有 parent
WHERE genealogy_id = 1

-- ❌ 不能加速: parent_member_id 不是索引前缀，索引键分布在整棵树中
WHERE parent_member_id = 42
```

这就像电话簿：先按姓排序，再按名排序。你很容易找到 "王" 姓下叫 "伟" 的人，但很难找到所有叫 "伟" 的人——他们在每个姓氏下分散着。

**为什么 genealogy_id 放前面而非 member_id？**

```sql
-- 如果索引是 (parent_member_id, genealogy_id):
-- 好处: WHERE parent_member_id = 42 能精确定位
-- 坏处: WHERE genealogy_id = 1 需要扫描整棵树

-- 如果索引是 (genealogy_id, parent_member_id):
-- 好处: 族谱级查询精确定位到该族谱的所有行
-- 坏处: 单独查某个 member 需要扫描所有族谱

-- 我们的查询模式 99% 是 "在某个族谱内操作"
-- → 选择 (genealogy_id, parent_member_id)
```

### 2.2 GIN trigram 索引

```sql
CREATE INDEX ix_members_name_trgm 
ON members USING gin (name gin_trgm_ops);
```

**GIN（Generalized Inverted Index，通用倒排索引）** 的结构与 B-tree 完全不同：

```
原始数据:
  成员名 "周伟" → trigram 分词: {"周","伟","周伟"}

GIN 内部结构 (倒排索引):
  
  KEY "周" → [行1, 行5, 行42, ...]   ← "周"出现在哪些行的name中
  KEY "伟" → [行3, 行7, 行42, ...]   ← "伟"出现在哪些行的name中
  KEY "周伟" → [行42, ...]            ← "周伟"出现在哪些行的name中
```

**查询执行过程**（以 `WHERE name ILIKE '%周%'` 为例）：

1. PostgreSQL 将查询字符串 "周" 分解为 trigram 集合
2. 在 GIN 索引中查找每个 trigram 对应的行 ID 列表
3. 取所有列表的**交集**
4. 得到候选行，回到主表（Heap）验证完整条件（消除误匹配）

**GIN vs B-tree 的物理区别**：

| 特性 | B-tree | GIN |
|------|--------|-----|
| 索引结构 | 平衡树，键值有序 | 倒排表，键→行ID列表 |
| 适用查询 | 等值、范围、前缀 | 包含、全文搜索、数组 |
| 一个键对应 | 一个行 | 多个行（倒排列表） |
| 更新代价 | O(log n) | 较高（需更新多个倒排列表） |
| 体积 | 较小 | 约 3~5 倍于 B-tree |

### 2.3 什么是 Index Only Scan？

在 EXPLAIN 输出中看到的 "Index Only Scan"：

```text
->  Index Only Scan using uq_parent_child on parent_child_relations
    Index Cond: (parent_member_id = '1'::smallint)
    Heap Fetches: 0                              ← 关键！
```

**原理**：当查询需要的所有列都**包含在索引中**时，PostgreSQL 可以**只读索引不访问数据表**。

```
普通 Index Scan:
  索引 → 找到 CTID → 去 Heap（数据表）读完整行
  需要 2 次 I/O

Index Only Scan:
  索引 → 直接返回索引中已有的列值
  需要 1 次 I/O

条件: 查询的列必须全部在索引键中 且 Visibility Map 标记该页为 "全部可见"
```

在我们的项目中，`parent_child_relations` 的查询只用到 `parent_member_id` 列（已在索引中），且不访问 `parent_role` 等其他列，因此 PostgreSQL 可以执行 Index Only Scan。

### 2.4 物理优化总结

```
查询在没有索引时:
  Seq Scan: 逐行读取整个表（201,070 行）→ 91ms

查询在有索引时:
  Index Only Scan: B-tree 二分定位 → 读索引页 → 返回 → 0.35ms
  
加速比: 258×
I/O 量: 7,203 buffers → 140 buffers (51× 减少)
```

---

## 问题三：递归 CTE 的详细执行过程与数据表操作原理

### 3.0 预备知识：递归 CTE 语法

```sql
WITH RECURSIVE cte_name AS (
    -- 1. 基础查询（非递归部分，只执行一次）
    SELECT ... FROM ... WHERE ...
    
    UNION [ALL]                         -- ← 关键：UNION 或 UNION ALL
    
    -- 2. 递归查询（引用 cte_name 自身）
    SELECT ... FROM cte_name JOIN ... WHERE ...
)
SELECT ... FROM cte_name;
```

**执行模型**：PostgreSQL 使用**双表法**（Work Table + Intermediate Table）：

```
Step 1: 执行基础查询，结果放入 Work Table
Step 2: 用 Work Table 执行递归查询，新结果放入 Intermediate Table
Step 3: Intermediate Table 成为新的 Work Table
Step 4: 重复 Step 2-3，直到递归查询返回 0 行
Step 5: 所有轮的 Work Table 的并集（受 UNION/UNION ALL 影响）为最终结果
```

### 3.1 祖先追溯的逐轮执行过程

**SQL**：[`sql/queries/01_ancestors.sql`](file:///d:/上课/大三下/数据库/genealogy_system/sql/queries/01_ancestors.sql)

```sql
WITH RECURSIVE ancestors AS (
    SELECT p.parent_member_id AS member_id, 1 AS depth          -- (A) 基础
    FROM parent_child_relations p
    WHERE p.child_member_id = :member_id
    UNION                                                        -- (B) 去重
    SELECT p.parent_member_id, a.depth + 1                       -- (C) 递归
    FROM parent_child_relations p
    JOIN ancestors a ON p.child_member_id = a.member_id
    WHERE a.depth < 10
)
SELECT m.*, ancestors.depth
FROM ancestors JOIN members m ON m.id = ancestors.member_id;
```

假设查询 `member_id = 100`（张小明），`parent_child_relations` 表中有以下相关数据：

```
parent_member_id | child_member_id | parent_role
       200       |      100        |   father     ← 张小明 的父
       201       |      100        |   mother     ← 张小明 的母
       300       |      200        |   father     ← 张小明父 的父
       301       |      200        |   mother     ← 张小明父 的母
       300       |      201        |   father     ← 张小明母 的父 (与上面同一人!)
       301       |      201        |   mother     ← 张小明母 的母 (与上面同一人!)
```

**第 1 轮（基础查询）**：

```
执行 (A):
  SELECT parent_member_id FROM parent_child_relations WHERE child_member_id = 100;
  扫描 child_member_id 索引 → 找到 2 行
  
  结果:
  ┌───────────┬───────┐
  │ member_id │ depth │
  ├───────────┼───────┤
  │    200    │   1   │   ← 父亲
  │    201    │   1   │   ← 母亲
  └───────────┴───────┘

  → 放入 Work Table: [(200,1), (201,1)]
  → 放入结果集: [(200,1), (201,1)]
```

**第 2 轮**：

```
执行 (C):  
  SELECT p.parent_member_id, a.depth + 1
  FROM parent_child_relations p
  JOIN ancestors a ON p.child_member_id = a.member_id
  WHERE a.depth < 10
  
  a 的当前值（上一轮的 Work Table）: [(200,1), (201,1)]
  
  对于 (200,1):
    child_member_id = 200 → 索引扫描 child_member_id = 200
    → 找到 (300,200,'father'), (301,200,'mother')
    → 产出: (300,2), (301,2)
  
  对于 (201,1):
    child_member_id = 201 → 索引扫描 child_member_id = 201
    → 找到 (300,201,'father'), (301,201,'mother')
    → 产出: (300,2), (301,2)
  
  去重前产出: [(300,2), (301,2), (300,2), (301,2)]
  
  UNION 去重: 去除重复的 (300,2) 和 (301,2)
  → 放入 Work Table: [(300,2), (301,2)]
  → 追加到结果集: [(200,1),(201,1),(300,2),(301,2)]
```

**第 3 轮**：

```
Work Table: [(300,2), (301,2)]

对于 (300,2): child_member_id = 300 → 索引扫描 → 假设找到 (400,300,'father')
对于 (301,2): child_member_id = 301 → 索引扫描 → 假设找到 (402,301,'father')

产出（UNION 去重后）: [(400,3), (402,3)]
→ 放入 Work Table，追加到结果集
```

**终止条件**：某轮的 `Work Table` 为空，或 `depth >= 10`。

**最终结果集**：所有轮次的并集，按 depth 排序输出。

```
最终输出:
┌────┬──────────┬───────┐
│ id │   name   │ depth │
├────┼──────────┼───────┤
│200 │ 张大明   │   1   │   ← 父
│201 │ 李淑芬   │   1   │   ← 母
│300 │ 张德海   │   2   │   ← 爷爷
│301 │ 王秀兰   │   2   │   ← 奶奶
│400 │ 张宗耀   │   3   │   ← 曾祖
│402 │ ...      │   3   │
└────┴──────────┴───────┘
```

**关键点**：张小明父(200)和张小明母(201)共享同一对父母(300,301)，如果没有 `UNION`，第 2 轮会产生重复的 (300,2) 和 (301,2)，并在后续轮次中指数级放大（每代 2^n 个祖先，重复路径 2×2×2...）。

### 3.2 后代追溯的逐轮执行过程

**SQL**：[`sql/queries/02_descendants.sql`](file:///d:/上课/大三下/数据库/genealogy_system/sql/queries/02_descendants.sql)

```sql
WITH RECURSIVE descendants AS (
    SELECT child_member_id AS member_id, 1 AS depth
    FROM parent_child_relations
    WHERE parent_member_id = :member_id
    UNION
    SELECT p.child_member_id, d.depth + 1
    FROM parent_child_relations p
    JOIN descendants d ON p.parent_member_id = d.member_id
    WHERE d.depth < 12
)
SELECT m.*, descendants.depth
FROM descendants JOIN members m ON m.id = descendants.member_id;
```

**与祖先查询的对称差异**：

| | 祖先查询 | 后代查询 |
|----|---------|---------|
| 起始条件 | `child_member_id = :id`（我是子，找我的父） | `parent_member_id = :id`（我是父，找我的子） |
| JOIN 条件 | `p.child = a.member`（当前人作为子） | `p.parent = d.member`（当前人作为父） |
| 遍历方向 | ↑ 向上（子→父→父的父→...） | ↓ 向下（父→子→子的子→...） |

假设查询 `member_id = 300`（张德海，爷爷），表中有：

```
parent_member_id | child_member_id
      300        |      200        ← 张德海的子
      300        |      201        ← 张德海的子
      200        |      100        ← 张德海的孙 (通过张大明)
      200        |      101        ← 张德海的孙
      201        |      102        ← 张德海的孙 (通过李淑芬)
```

**第 1 轮（基础）**：

```
WHERE parent_member_id = 300
→ 索引扫描 ix_parent_child_genealogy_parent, genealogy_id=1, parent=300
→ 找到: (200,1), (201,1)
→ Work Table: [(200,1), (201,1)]
```

**第 2 轮**：

```
JOIN descendants d ON p.parent_member_id = d.member_id
d 当前: (200,1): 找 parent = 200 → (100,2), (101,2)
       (201,1): 找 parent = 201 → (102,2)
→ Work Table: [(100,2), (101,2), (102,2)]
```

**第 3 轮及以后**：继续向下，直到没有更多后代或 depth >= 12。

### 3.3 族谱树形预览的逐轮执行过程

**SQL**：[`app/genealogies/routes.py`](file:///d:/上课/大三下/数据库/genealogy_system/app/genealogies/routes.py#L117-L153)

```sql
WITH RECURSIVE tree AS (
    SELECT m.id, m.name, m.gender, m.generation_no,
           0 AS depth,
           ',' || CAST(m.id AS TEXT) || ',' AS path        -- ← 路径字符串
    FROM members m
    WHERE m.genealogy_id = :genealogy_id
      AND NOT EXISTS (
          SELECT 1 FROM parent_child_relations p
          WHERE p.child_member_id = m.id 
            AND p.genealogy_id = :genealogy_id
      )
    UNION ALL                                              -- ← 注意: UNION ALL
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

**与祖先/后代查询的核心区别**：

这里的递归从**所有根节点**同时开始（`NOT EXISTS` 找出所有无父节点的成员），而非从某个指定成员开始。

**为什么这里用 `UNION ALL` 而非 `UNION`？**

在树形展开中，每个子节点只能通过一个父节点到达（一个人只有一个生物学父亲/母亲），不存在"多路径到达同一节点"的问题。因此不需要去重，`UNION ALL` 更快。

**path 字符串的作用**：

```sql
-- 初始: ',300,'           (根节点 ID=300)
-- 子:   ',300,200,'       (路径: 300 → 200)
-- 孙:   ',300,200,100,'   (路径: 300 → 200 → 100)
```

`ORDER BY path` 使得输出按深度优先排列（同一分支连续，类似族谱的竖排格式），而不是按 depth 将所有同代人堆在一起。

**第 1 轮**：

```
NOT EXISTS (子查) → 找到所有 child_member_id 从未出现在 child 位置的成员
这些是族谱的最早一代（第一代祖先）

假设找到:
  (300, 张德海, 3代, depth=0, path=',300,')
  (301, 王秀兰, 3代, depth=0, path=',301,')
→ Work Table: [300, 301]
```

**第 2 轮**：

```
对 300: parent_member_id = 300 → (200, 张大明), (201, 李淑芬)
  产出: (200, ..., depth=1, path=',300,200,')
        (201, ..., depth=1, path=',300,201,')

对 301: parent_member_id = 301 → (200, 张大明), (201, 李淑芬) [假设共同子]
  产出: (200, ..., depth=1, path=',301,200,')  ← 同一人，不同 path
        (201, ..., depth=1, path=',301,201,')  ← 同一人，不同 path
```

注意：这里张大明(200)出现了两次！因为他是张德海和王秀兰的共同子女。但在 path 层面这是两条不同的"到达路径"，各有自己的上下文。这正是用 `UNION ALL` 的原因——保留两条路径以正确展示树形结构。

最终 `ORDER BY path` 会输出：
```
',300,'
',300,200,'
',300,200,100,'
',300,200,101,'
',300,201,'
',300,201,102,'
',301,'
',301,200,'
...
```

这是**按族谱分支排列**的深度优先遍历顺序。

### 3.4 UNION vs UNION ALL 的深入对比

| | UNION | UNION ALL |
|----|-------|-----------|
| 去重 | ✅ 是（排序或哈希） | ❌ 否 |
| 性能 | 较慢（需去重开销） | 较快 |
| 适用 | 多路径→同一节点（祖先/后代/分支导出） | 唯一路径（树形预览） |
| 示例 | 祖先：同一个人可以通过父线和母线到达同一祖先 | 树形：每个子节点只通过一个父节点到达 |

**关键判断准则**：如果父路径和母路径都通向同一个人，我需要他出现几次？

- 祖先查询：1 次（我在找"谁是我的祖先"，不是"通过谁是谁的祖先"）
- 树形预览：2 次（需要分别挂在父亲和母亲的树下）

---

## 问题四：分支导出功能

### 4.1 功能说明

**是的，项目支持导出族谱的某一部分分支。** 通过 `scripts/export_branch.py` 脚本实现。

### 4.2 功能描述

给定一个成员 ID，将该成员及其**所有后代**导出为 3 个 CSV 文件：
- `members.csv` — 该分支的所有成员
- `parent_child_relations.csv` — 分支内的所有亲子关系
- `marriages.csv` — 分支内配偶双方都在的婚姻关系

### 4.3 使用方法

```bash
# 导出 ID=1 的成员及其所有后代
.venv\Scripts\python.exe scripts\export_branch.py --member-id 1

# 指定输出目录
.venv\Scripts\python.exe scripts\export_branch.py --member-id 1 --output-dir data/my_branch
```

**输出示例**：

```
Exported branch rooted at member 1 to D:\...\data\branch_export
- members: 847
- parent_child_relations: 823
- marriages: 391
```

### 4.4 实现原理

**核心 SQL**：[`scripts/export_branch.py`](file:///d:/上课/大三下/数据库/genealogy_system/scripts/export_branch.py#L45-L64)

```sql
WITH RECURSIVE branch AS (
    -- 基础: 指定成员自身
    SELECT id, genealogy_id, 1 AS depth
    FROM members WHERE id = %s
    
    UNION  -- ← 关键: UNION 去重（同一个后代可能通过多条路径到达）
    
    -- 递归: 所有后代
    SELECT child.id, child.genealogy_id, branch.depth + 1
    FROM branch
    JOIN parent_child_relations rel ON rel.parent_member_id = branch.id
    JOIN members child ON child.id = rel.child_member_id
    WHERE branch.depth < 100
)
SELECT m.* FROM members m JOIN branch ON branch.id = m.id;
```

**执行流程**：

```
第 1 轮: member_id = 1 → Work Table: [(1)]
第 2 轮: 查 member_id=1 的所有子女 → [(2), (3), (4)]
第 3 轮: 查 (2)(3)(4) 各自的所有子女 → [(5), (6), ...]
...
第 N 轮: 某轮找不到任何子节点 → 终止
        或 depth >= 100 → 安全终止
```

**注意**：这里同样是 `UNION` 而非 `UNION ALL`。因为在多代族谱中，同一后代可能通过多条路径（如父系和母系各算一次）被重复纳入。`UNION` 确保每个成员只导出一次。

**婚姻关系导出**：

```sql
SELECT id, genealogy_id, spouse1_member_id, spouse2_member_id, married_year, ended_year
FROM marriages
WHERE spouse1_member_id = ANY(%s)    -- 配偶1在分支成员列表中
  AND spouse2_member_id = ANY(%s)    -- 配偶2也在分支成员列表中
```

只有配偶**双方都在**该分支中时，婚姻关系才被导出。例如：如果张大明娶了另一族谱的李小芳，则这段婚姻不会被导出（李小芳不在本分支中）。

---

## 问题五：其它查询的详细执行过程

### 5.1 配偶及子女查询

**SQL**：[`sql/queries/06_spouse_children.sql`](file:///d:/上课/大三下/数据库/genealogy_system/sql/queries/06_spouse_children.sql)

```sql
SELECT 'spouse' AS relationship_type,
       spouse_member.id, spouse_member.name, spouse_member.gender,
       s.married_year
FROM marriages s
JOIN members spouse_member ON (
    CASE WHEN s.spouse1_member_id = :member_id THEN s.spouse2_member_id
         ELSE s.spouse1_member_id
    END = spouse_member.id
)
WHERE s.genealogy_id = :genealogy_id
  AND (s.spouse1_member_id = :member_id OR s.spouse2_member_id = :member_id)

UNION ALL

SELECT 'child' AS relationship_type,
       child_member.id, child_member.name, child_member.gender,
       NULL AS married_year
FROM parent_child_relations rel
JOIN members child_member ON child_member.id = rel.child_member_id
WHERE rel.genealogy_id = :genealogy_id
  AND rel.parent_member_id = :member_id

ORDER BY relationship_type, related_member_id;
```

**数据表操作原理**：

查询分为两个独立的 SELECT，用 `UNION ALL` 拼接。

**上半部分（配偶查询）**：

```
WHERE (s.spouse1_member_id = :id OR s.spouse2_member_id = :id)
  ↓
索引扫描: ix_marriages_genealogy_spouse1 (先查左) + ix_marriages_genealogy_spouse2 (再查右)
  ↓
对每行结果，CASE WHEN 决定 "另一方" 是谁:
  如果 my_id = spouse1 → 配偶是 spouse2
  如果 my_id = spouse2 → 配偶是 spouse1
  ↓
JOIN members 获取配偶详细信息
```

SQL 优化器会将这个 OR 条件分解为 BitmapOr 操作：
```
BitmapOr
  ├── Bitmap Index Scan on ix_marriages_genealogy_spouse1
  └── Bitmap Index Scan on ix_marriages_genealogy_spouse2
```

两个索引扫描的结果通过位图合并（去重），效率很高。

**`CASE WHEN` 的设计理由**：

婚姻表使用 `spouse1 < spouse2` 的排序约束，所以在不知道当前成员 ID 的情况下，无法预先知道它在 spouse1 还是 spouse2 位置。`CASE WHEN` 动态解析为"除我之外的那个人"。

**下半部分（子女查询）**：

```
WHERE rel.parent_member_id = :id
  ↓
索引扫描: ix_parent_child_genealogy_parent (genealogy_id, parent_member_id)
  ↓
JOIN members 获取子女详细信息
```

**为什么用 `UNION ALL`？**

配偶集合和子女集合互不相交（一个人不会同时是某人的配偶和子女），所以安全使用 `UNION ALL` 拼接，无去重开销。

### 5.2 平均寿命最长的一代

**SQL**：[`sql/queries/07_avg_lifespan_by_generation.sql`](file:///d:/上课/大三下/数据库/genealogy_system/sql/queries/07_avg_lifespan_by_generation.sql)

```sql
WITH gen_lifespan AS (
    SELECT genealogy_id, generation_no,
           AVG(death_year - birth_year)::numeric(6,2) AS avg_lifespan,
           COUNT(*) AS member_count,
           MIN(birth_year), MAX(death_year)
    FROM members
    WHERE genealogy_id = :genealogy_id
      AND birth_year IS NOT NULL
      AND death_year IS NOT NULL
      AND death_year > birth_year
    GROUP BY genealogy_id, generation_no
)
SELECT * FROM gen_lifespan
ORDER BY avg_lifespan DESC LIMIT 1;
```

**执行过程**：

```
Step 1: WHERE 过滤
  genealogy_id = :gid → 索引扫描 ix_members_genealogy_id
  birth_year IS NOT NULL AND death_year IS NOT NULL → 过滤 NULL 行
  death_year > birth_year → 过滤异常数据

Step 2: GROUP BY 分组聚合
  按 (genealogy_id, generation_no) 分组
  对每组计算:
    AVG(death_year - birth_year) → 均值，转为 numeric(6,2)
    COUNT(*) → 该代有效人数
    MIN(birth_year) → 最早出生年
    MAX(death_year) → 最晚去世年

Step 3: 排序取 TOP 1
  ORDER BY avg_lifespan DESC → 按平均寿命降序
  LIMIT 1 → 只取第一行（最长寿的那一代）
```

**`::numeric(6,2)` 的含义**：

这是 PostgreSQL 的**类型转换**语法，等价于 `CAST(AVG(...) AS numeric(6,2))`。`numeric(6,2)` 表示最多 6 位数字（其中 2 位小数），如 `78.35`。不指定精度的话，AVG 返回的精度可能不一致。

**为什么需要 `GROUP BY genealogy_id`？**

虽然 WHERE 已经过滤了 `genealogy_id = :gid`，但 SQL 标准要求 SELECT 中的非聚合列必须出现在 GROUP BY 中。加上 `genealogy_id` 也使得这个 CTE 可以在其他上下文中复用（去掉 WHERE 条件后仍合法）。

### 5.3 超过 50 岁无配偶男性

**SQL**：[`sql/queries/08_males_over_50_no_spouse.sql`](file:///d:/上课/大三下/数据库/genealogy_system/sql/queries/08_males_over_50_no_spouse.sql)

```sql
SELECT m.*, 
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

**执行过程 — WHERE 子句逐条件分析**：

```
条件 1: genealogy_id = :gid
  索引扫描 ix_members_genealogy_id → 缩小到目标族谱

条件 2: gender = 'male'
  在已筛选的行上逐一检查 gender 列 → 过滤女性

条件 3: birth_year IS NOT NULL
  过滤出生年未知的成员（无法计算年龄）

条件 4: (COALESCE(death_year, CURRENT_YEAR) - birth_year) > 50
  COALESCE 函数: 如果 death_year 有值就用它，否则用当前年份
  计算年龄 > 50 才通过
  
条件 5: NOT EXISTS (子查询)
  对每个候选成员，执行子查询:
    SELECT 1 FROM marriages
    WHERE (spouse1 = m.id OR spouse2 = m.id) AND genealogy_id = m.genealogy_id
    
  两路索引扫描:
    ix_marriages_genealogy_spouse1 → 查 m.id 是否作为 spouse1
    ix_marriages_genealogy_spouse2 → 查 m.id 是否作为 spouse2
    
  子查询的短路特性: 只要找到 1 行就停止（SELECT 1 而非 SELECT *）
  
  NOT EXISTS: 子查询返回 0 行 = TRUE（确实无配偶）
```

**`NOT EXISTS` 的执行优势**：

```
反半连接 (Anti-Semi-Join):
  
  对 members 的每一行 m:
    查 marriages: m.id 是否在 spouse1 或 spouse2 中?
    → 是: 跳过此人
    → 否: 保留此人
    → 找到第一次匹配就立即停止（短路）
```

这与 `LEFT JOIN ... WHERE spouse.id IS NULL` 相比：
- `NOT EXISTS` 语义更清晰（"不存在配偶记录"）
- 短路特性：找到一条配偶记录就停止，不需要扫描剩余
- PostgreSQL 优化器会将 NOT EXISTS 转为 ANTI JOIN 执行计划

**`COALESCE` 的双重使用**：

```sql
-- 在 SELECT 中: 显示用的估算年龄
CASE WHEN death_year IS NOT NULL THEN death_year - birth_year
     ELSE EXTRACT(YEAR FROM CURRENT_DATE)::int - birth_year
END AS estimated_age

-- 在 WHERE 中: 筛选用的计算年龄
(COALESCE(death_year, EXTRACT(YEAR FROM CURRENT_DATE)::int) - birth_year) > 50
```

WHERE 中使用 `COALESCE`（一行表达式），SELECT 中使用 `CASE WHEN`（更清晰展示逻辑）。两处计算逻辑等效但写法不同——这是为了代码可读性。

### 5.4 出生年份早于代平均的成员

**SQL**：[`sql/queries/09_born_before_gen_avg.sql`](file:///d:/上课/大三下/数据库/genealogy_system/sql/queries/09_born_before_gen_avg.sql)

```sql
WITH gen_avg AS (
    SELECT genealogy_id, generation_no,
           AVG(birth_year)::numeric(6,2) AS avg_birth_year,
           COUNT(*) AS total_in_gen
    FROM members
    WHERE genealogy_id = :genealogy_id
      AND birth_year IS NOT NULL
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

**执行过程**：

```
Phase 1: CTE gen_avg — 计算每代平均值
  ┌──────────────────────────────────────┐
  │ genealogy_id │ generation_no │ avg   │
  ├──────────────┼───────────────┼───────┤
  │      1       │      1        │ 1925  │  第 1 代平均出生年
  │      1       │      2        │ 1955  │  第 2 代平均出生年
  │      1       │      3        │ 1982  │  第 3 代平均出生年
  │     ...      │     ...       │  ...  │
  └──────────────┴───────────────┴───────┘
  
  输入: members 表中 genealogy_id=1 且有 birth_year 的行
  操作: GROUP BY generation_no → AVG(birth_year) 每代人平均
  输出: CTE 临时表 gen_avg (通常存在内存中)

Phase 2: 主查询 JOIN + 筛选
  对 members 表的每一行:
    → 通过 (generation_no, genealogy_id) JOIN gen_avg
    → 拿到 "这一代的平均出生年"
    → 比较: 我的出生年 < 代平均?
    → 是 → 输出; 否 → 跳过
  
  输出时计算 deviation:
    birth_year - avg_birth_year = 负值（早于平均）
    例如: 1920 - 1925 = -5.00 ← 早于平均 5 年
```

**deviation 列的含义**：

```
deviation = 成员的 birth_year - 该代 avg_birth_year

负数 = 早于平均（年长于同龄人）
正数 = 晚于平均（年轻于同龄人）
零   = 正好等于平均

查询筛选 deviation < 0 的成员（也就是 birth_year < avg）
```

**`ROUND(...::numeric, 2)` 的两步转换**：

```sql
ROUND((m.birth_year - ga.avg_birth_year)::numeric, 2)
      └──────────整数减法──────────┘  └──转型──┘  └四舍五入┘
```

1. `birth_year - avg_birth_year`：整数减 numeric，结果自动为 numeric
2. `::numeric`：显式确保类型为 numeric（此处是冗余的，但作为文档说明意图）
3. `ROUND(..., 2)`：四舍五入保留 2 位小数

### 5.5 CSV 流式导出查询

**SQL**：[`app/genealogies/routes.py`](file:///d:/上课/大三下/数据库/genealogy_system/app/genealogies/routes.py#L272-L279)

```sql
-- 分块查询，每批 2000 行
SELECT id, genealogy_id, name, gender, birth_year, death_year, generation_no
FROM members
WHERE genealogy_id = :gid
ORDER BY id
LIMIT :limit OFFSET :offset
```

**执行过程（分 25 批，总计 50,000 行）**：

```
第 1 批: LIMIT 2000 OFFSET 0
  Index Scan on ix_members_genealogy_id
  → 读取 genealogy_id=X 的前 2000 行
  → yield 给 HTTP 响应流

第 2 批: LIMIT 2000 OFFSET 2000
  → 跳过前 2000 行，读取接下来的 2000 行
  → yield

...

第 25 批: LIMIT 2000 OFFSET 48000
  → 读取最后 2000 行
  → yield

第 26 批: 查询返回 0 行 → 终止循环 → 响应结束
```

**为什么不一次查询全部 50,000 行？**

- 内存：50,000 个 ORM 对象 ≈ 几百 MB 内存
- 分块查询：每次只在内存中保留 2000 行 ≈ 几 MB
- HTTP 流式传输：客户端一边接收一边写入磁盘，无需等待全部数据准备好

### 5.6 分支导出中的关系过滤查询

**SQL**：[`scripts/export_branch.py`](file:///d:/上课/大三下/数据库/genealogy_system/scripts/export_branch.py#L70-L89)

```sql
-- 亲子关系: 父和子都在分支内
SELECT id, genealogy_id, parent_member_id, child_member_id, parent_role
FROM parent_child_relations
WHERE parent_member_id = ANY(%s) AND child_member_id = ANY(%s)

-- 婚姻关系: 配偶双方都在分支内
SELECT id, genealogy_id, spouse1_member_id, spouse2_member_id, married_year, ended_year
FROM marriages
WHERE spouse1_member_id = ANY(%s) AND spouse2_member_id = ANY(%s)
```

**`= ANY(array)` 的执行方式**：

```sql
WHERE parent_member_id = ANY(ARRAY[2, 3, 4, 5, ..., 847])
```

PostgreSQL 会将此转换为：
```
parent_member_id = 2 OR parent_member_id = 3 OR ... OR parent_member_id = 847
```

但执行时使用 **BitmapOr + 多个索引扫描**，而非逐行检查：

```
BitmapOr
  ├── Index Scan: parent_member_id = 2
  ├── Index Scan: parent_member_id = 3
  ├── ...
  └── Index Scan: parent_member_id = 847
```

每个值的索引扫描结果通过位图合并，然后**去重后一次性回表**。对于 847 个值，这意味着最多 847 次索引查找，但只需 1 次表访问。

**与 IN 子句的等价性**：

```sql
WHERE parent_member_id = ANY(ARRAY[2,3,4])   -- PostgreSQL 原生写法
WHERE parent_member_id IN (2, 3, 4)           -- 标准 SQL 等价写法
```

psycopg 驱动支持直接传递 Python 列表给 `ANY()`：
```python
cursor.execute("... WHERE parent_member_id = ANY(%s)", (member_ids,))
```

这比手动拼接 `IN (?, ?, ?, ...)` 更安全（防止注入）且更简洁。

---

*文档生成日期: 2026-05-12*