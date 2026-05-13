# PostgreSQL SQL 语法教学：从零开始，以项目实例为教材

> 假设你学过数据库理论（知道表、行、列、主键、外键），但**第一次写 SQL 语句**。  
> 本文以"寻根溯源族谱管理系统"的全部 SQL 查询为实例，逐句拆解语法。  
> 数据库：PostgreSQL 16

---

## 目录

- [第 1 课：SELECT, FROM, WHERE — 最基础的查询](#第-1-课select-from-where--最基础的查询)
- [第 2 课：CASE WHEN, COALESCE, CAST — 条件判断与类型转换](#第-2-课case-when-coalesce-cast--条件判断与类型转换)
- [第 3 课：JOIN — 连接多张表](#第-3-课join--连接多张表)
- [第 4 课：GROUP BY 与聚合函数 — 分组统计](#第-4-课group-by-与聚合函数--分组统计)
- [第 5 课：子查询与 WITH CTE — 查询嵌套与临时表](#第-5-课子查询与-with-cte--查询嵌套与临时表)
- [第 6 课：EXISTS 与 NOT EXISTS — 存在性检查](#第-6-课exists-与-not-exists--存在性检查)
- [第 7 课：WITH RECURSIVE — 递归查询（核心）](#第-7-课with-recursive--递归查询核心)
- [第 8 课：VALUES, ANY, 数组, 字符串拼接 — 高级短语](#第-8-课values-any-数组-字符串拼接--高级短语)
- [第 9 课：PL/pgSQL 存储函数 — 在数据库中写程序](#第-9-课plpgsql-存储函数--在数据库中写程序)

---

## 第 1 课：SELECT, FROM, WHERE — 最基础的查询

### 1.1 语法格式

```sql
SELECT  列名1, 列名2, ...      -- 想要哪些列？用 * 表示全部
FROM    表名                   -- 从哪张表取数据？
WHERE   条件表达式             -- 哪些行符合条件？（可选）
ORDER BY 列名 [ASC|DESC]      -- 按什么排序？（可选）
LIMIT   数量                  -- 最多返回多少行？（可选）
```

**执行顺序**（重要！不是书写顺序）：

```
① FROM    — 确定数据来源（哪张表）
② WHERE   — 逐行过滤（哪行要？哪行不要？）
③ SELECT  — 选取需要的列（投影操作）
④ ORDER BY — 排序
⑤ LIMIT   — 截断
```

### 1.2 实例：查询某个族谱中所有男性成员

项目 [`routes.py`](file:///d:/上课/大三下/数据库/genealogy_system/app/members/routes.py) 中的类似查询：

```sql
SELECT id, name, gender, birth_year, generation_no
FROM members
WHERE genealogy_id = 1
  AND gender = 'male'
ORDER BY generation_no, id
LIMIT 10;
```

**逐词讲解**：

| 关键字/符号 | 含义 | 类比 |
|------------|------|------|
| `SELECT` | 我要查数据 | "请给我..." |
| `id, name, gender, birth_year, generation_no` | 只要这 5 列 | 列清单 |
| `FROM members` | 从 `members` 表查 | 从哪本名册查 |
| `WHERE` | 但要有条件 | "但是..." |
| `genealogy_id = 1` | 只查族谱 1 的人 | 只查某个家族 |
| `AND` | 并且（两个条件都满足） | 同时满足 |
| `gender = 'male'` | 性别是男 | 只要男的 |
| `'male'` | 字符串用**单引号**包裹 | 文本值 |
| `ORDER BY generation_no` | 先按代数排序 | 第 1 代、第 2 代... |
| `ASC` | 升序（默认，从小到大） | 省略了 |
| `LIMIT 10` | 最多 10 行 | 够了 |

**执行过程演示**：

假设 `members` 表有这些数据：

```
members 表（执行前）:
┌────┬──────────┬────────┬───────┬───────────┬──────────┬──────────────┐
│ id │ genealogy_id │ name  │ gender│ birth_year│ death_year│ generation_no│
├────┼──────────────┼───────┼───────┼───────────┼───────────┼──────────────┤
│ 1  │      1       │ 张德海 │ male  │   1920    │   2005    │      1       │
│ 2  │      1       │ 王秀兰 │ female│   1925    │   2010    │      1       │
│ 3  │      1       │ 张大明 │ male  │   1950    │   2018    │      2       │
│ 4  │      1       │ 李淑芬 │ female│   1952    │   NULL    │      2       │
│ 5  │      1       │ 张小明 │ male  │   1980    │   NULL    │      3       │
│ 6  │      2       │ 王建国 │ male  │   1960    │   NULL    │      2       │
└────┴──────────────┴───────┴───────┴───────────┴───────────┴──────────────┘
```

**第 1 步：FROM members** — 定位到 members 表，共 6 行。

**第 2 步：WHERE genealogy_id = 1** — 逐行检查 `genealogy_id` 列：

```
行1: genealogy_id=1 ✅ 保留
行2: genealogy_id=1 ✅ 保留
行3: genealogy_id=1 ✅ 保留
行4: genealogy_id=1 ✅ 保留
行5: genealogy_id=1 ✅ 保留
行6: genealogy_id=2 ❌ 丢弃（不是族谱1的）
```

还剩 5 行。

**第 3 步：AND gender = 'male'** — 继续过滤：

```
行1: gender='male' ✅ 保留
行2: gender='female' ❌ 丢弃
行3: gender='male' ✅ 保留
行4: gender='female' ❌ 丢弃
行5: gender='male' ✅ 保留
```

还剩 3 行。

**第 4 步：SELECT id, name, gender, birth_year, generation_no** — 只保留这 5 列（舍弃 death_year, genealogy_id）：

```
┌────┬────────┬───────┬───────────┬──────────────┐
│ id │  name  │ gender│ birth_year│ generation_no│
├────┼────────┼───────┼───────────┼──────────────┤
│ 1  │ 张德海 │ male  │   1920    │      1       │
│ 3  │ 张大明 │ male  │   1950    │      2       │
│ 5  │ 张小明 │ male  │   1980    │      3       │
└────┴────────┴───────┴───────────┴──────────────┘
```

**第 5 步：ORDER BY generation_no** — 排序。已经是有序的，不变。

**第 6 步：LIMIT 10** — 只有 3 行，全保留。

### 1.3 参数化的写法（防 SQL 注入）

在 Python 代码中，我们**从不直接把用户输入拼进 SQL 字符串**，而是用**参数占位符**：

```python
# ❌ 危险写法（永远不要这样写！）:
sql = f"SELECT * FROM members WHERE id = {user_input}"

# ✅ 安全写法:
sql = "SELECT * FROM members WHERE id = :member_id"
db.session.execute(text(sql), {"member_id": user_input})
```

| 参数风格 | 写法 | 谁在用 |
|---------|------|--------|
| `:name` | `WHERE id = :member_id` | **我们项目**（SQLAlchemy + psycopg） |
| `$1` | `WHERE id = $1` | psycopg 原生 |
| `%s` | `WHERE id = %s` | psycopg 旧版 |
| `?` | `WHERE id = ?` | SQLite |

**原理**：数据库驱动把参数和 SQL **分开发送**，数据库编译 SQL 后再填入参数值。这样即使参数中包含 `'; DROP TABLE members; --` 也不会被执行——它只是一个字符串值。

---

## 第 2 课：CASE WHEN, COALESCE, CAST — 条件判断与类型转换

### 2.1 COALESCE — 取第一个非空值

**语法**：`COALESCE(值1, 值2, 值3, ...)` — 从左到右，返回第一个 **不是 NULL** 的值。

**项目实例**（[`08_males_over_50_no_spouse.sql`](file:///d:/上课/大三下/数据库/genealogy_system/sql/queries/08_males_over_50_no_spouse.sql)）：

```sql
SELECT name,
       COALESCE(death_year, EXTRACT(YEAR FROM CURRENT_DATE)::int) - birth_year AS age
FROM members
WHERE genealogy_id = 1 AND gender = 'male';
```

**逐词讲解**：

| 短语 | 含义 |
|------|------|
| `COALESCE(death_year, ...)` | 如果 `death_year` 不是 NULL，用它；否则用后面的值 |
| `EXTRACT(YEAR FROM CURRENT_DATE)` | 从当前日期中提取年份（如 2026） |
| `::int` | 类型转换：把结果转成整数 |
| `- birth_year` | 减去出生年 = 年龄 |
| `AS age` | 给计算结果起一个**别名**（列名叫 `age`） |

**EXTRACT 详解**：

```sql
CURRENT_DATE            →  '2026-05-12'  (日期类型)
EXTRACT(YEAR FROM CURRENT_DATE)  →  2026.0  (数值类型，但带小数)
EXTRACT(YEAR FROM CURRENT_DATE)::int  →  2026  (整数)
```

`EXTRACT(YEAR FROM 日期)` 是 SQL 标准函数，从日期中挖出年份部分。

**COALESCE 执行演示**：

```
成员表中:
┌────────┬────────────┬───────────┐
│  name  │ birth_year │ death_year│
├────────┼────────────┼───────────┤
│ 张德海 │   1920     │   2005    │  → COALESCE(2005, 2026) = 2005 → age=85
│ 张小明 │   1980     │   NULL    │  → COALESCE(NULL, 2026) = 2026 → age=46
└────────┴────────────┴───────────┘
```

### 2.2 CASE WHEN — 多分支条件判断

**语法**：

```sql
CASE
    WHEN 条件1 THEN 结果1
    WHEN 条件2 THEN 结果2
    ELSE 默认结果
END
```

**项目实例 1**（[`08_males_over_50_no_spouse.sql`](file:///d:/上课/大三下/数据库/genealogy_system/sql/queries/08_males_over_50_no_spouse.sql)）：

```sql
SELECT name,
    CASE
        WHEN death_year IS NOT NULL THEN death_year - birth_year
        ELSE EXTRACT(YEAR FROM CURRENT_DATE)::int - birth_year
    END AS estimated_age
FROM members;
```

**执行演示**（逐行判断）：

```
行: 张德海, birth_year=1920, death_year=2005
  → CASE 进入:
    WHEN death_year IS NOT NULL   → 2005 IS NOT NULL = TRUE
    THEN death_year - birth_year  → 2005 - 1920 = 85
  → estimated_age = 85

行: 张小明, birth_year=1980, death_year=NULL
  → CASE 进入:
    WHEN death_year IS NOT NULL   → NULL IS NOT NULL = FALSE
    → 跳过，进入 ELSE
    ELSE EXTRACT(YEAR FROM CURRENT_DATE)::int - birth_year
    → 2026 - 1980 = 46
  → estimated_age = 46
```

**项目实例 2**（[`_lookup_relations_batch()`](file:///d:/上课/大三下/数据库/genealogy_system/app/members/routes.py#L480-L498)）：

```sql
SELECT CASE
    WHEN EXISTS(SELECT 1 FROM parent_child_relations
                WHERE parent_member_id = :a AND child_member_id = :b) THEN 'child'
    WHEN EXISTS(SELECT 1 FROM parent_child_relations
                WHERE child_member_id = :a AND parent_member_id = :b) THEN 'parent'
    WHEN EXISTS(SELECT 1 FROM marriages
                WHERE (spouse1 = :a AND spouse2 = :b)
                   OR (spouse1 = :b AND spouse2 = :a)) THEN 'spouse'
    ELSE '?'
END AS relation;
```

这个 CASE WHEN 被用来判断两个人之间是什么关系：先检查是不是 "父子"（A 是 B 的父），再检查是不是 "子父"（A 是 B 的子），再检查是不是 "配偶"。**EXISTS 子查询**会在第 6 课详细讲解。

### 2.3 CAST / :: — 类型转换

PostgreSQL 有两种等价的转换语法：

```sql
-- 写法 1: CAST(值 AS 目标类型)
CAST(:root_id AS INTEGER)

-- 写法 2: :: 运算符（PostgreSQL 特有）
:root_id::INTEGER
```

**什么时候需要转换？**

| 场景 | 原因 | 实例 |
|------|------|------|
| 参数类型不确定 | psycopg 可能推断为 SMALLINT，但 CTE 需要 INTEGER | `CAST(:root_id AS INTEGER)` |
| 保留小数精度 | AVG 默认返回的精度不可控 | `AVG(...)::numeric(6,2)` |
| 日期提取后运算 | EXTRACT 返回 numeric 而非 integer | `EXTRACT(...)::int` |

**numeric(6,2) 详解**：

```
numeric(6,2)
       │  │
       │  └── 2 位小数  (如 .35)
       └───── 总共 6 位 (整数部分最多 4 位)
       
例: 1234.56 ✅  (4位整数 + 2位小数 = 6位)
    12345.6 ❌  (5位整数 + 1位小数 = 6位, 但整数部分超了)
```

### 2.4 字符串拼接 — ||

```sql
-- 拼接两个字符串
'Hello' || ' ' || 'World'   →  'Hello World'

-- 拼接数字（自动转字符串）
',' || 100 || ','            →  ',100,'
```

**项目实例**（[树形预览](file:///d:/上课/大三下/数据库/genealogy_system/app/genealogies/routes.py#L117-L153)）：

```sql
SELECT ',' || CAST(id AS TEXT) || ',' AS path FROM members;
-- id=100 → path=',100,'
```

两边加逗号是为了方便后续用 `LIKE '%,100,%'` 精确匹配（避免 `100` 误匹配 `1000`）。

| 函数/语法 | 含义 | 示例 |
|-----------|------|------|
| `||` | 字符串拼接 | `'a' || 'b'` → `'ab'` |
| `CAST(x AS TEXT)` | 数字转字符串 | `CAST(100 AS TEXT)` → `'100'` |
| `x::TEXT` | 同上（简写） | `100::TEXT` → `'100'` |

---

## 第 3 课：JOIN — 连接多张表

### 3.1 为什么需要 JOIN？

族谱系统中，**成员信息**存在 `members` 表，**父子关系**存在 `parent_child_relations` 表。要找"张小明(100)的父亲的名字"，需要同时用到两张表的数据。

### 3.2 INNER JOIN — 内连接

**语法**：

```sql
SELECT ...
FROM 表A
[INNER] JOIN 表B ON 表A.列 = 表B.列
```

**项目实例**（[祖先查询](file:///d:/上课/大三下/数据库/genealogy_system/sql/queries/01_ancestors.sql)）：

```sql
SELECT members.id, members.name, ancestors.depth
FROM ancestors
JOIN members ON members.id = ancestors.member_id
ORDER BY ancestors.depth;
```

**逐词讲解**：

| 短语 | 含义 |
|------|------|
| `FROM ancestors` | 主表是 `ancestors` CTE（一个临时结果集） |
| `JOIN members` | 还要连接 `members` 表 |
| `ON members.id = ancestors.member_id` | **连接条件**：members 的 id 列 等于 ancestors 的 member_id 列 |
| `members.id` | 表名.列名（当两表有同名列时必须加前缀） |

**执行演示**：

```
Step 1: FROM ancestors
  ancestors 临时表:
  ┌───────────┬───────┐
  │ member_id │ depth │
  ├───────────┼───────┤
  │    200    │   1   │
  │    201    │   1   │
  │    300    │   2   │
  └───────────┴───────┘

Step 2: JOIN members ON members.id = ancestors.member_id
  对 ancestors 的每一行，去 members 表中找 id 匹配的行：
  
  ancestors(200,1) + members(id=200, 张大明) → 一行
  ancestors(201,1) + members(id=201, 李淑芬) → 一行
  ancestors(300,2) + members(id=300, 张德海) → 一行

Step 3: SELECT members.id, members.name, ancestors.depth
  ┌────┬────────┬───────┐
  │ id │  name  │ depth │
  ├────┼────────┼───────┤
  │200 │ 张大明 │   1   │
  │201 │ 李淑芬 │   1   │
  │300 │ 张德海 │   2   │
  └────┴────────┴───────┘
```

**INNER JOIN 的核心规则**：只保留**两表都匹配**的行。如果 ancestors 中某个 member_id 在 members 表中不存在，该行被丢弃。

### 3.3 特殊的 JOIN：CASE WHEN 中动态确定连接键

[配偶查询](file:///d:/上课/大三下/数据库/genealogy_system/sql/queries/06_spouse_children.sql)：

```sql
FROM marriages s
JOIN members spouse_member ON (
    CASE
        WHEN s.spouse1_member_id = :member_id THEN s.spouse2_member_id
        ELSE s.spouse1_member_id
    END = spouse_member.id
)
```

**为什么 JOIN 条件这么复杂？**

婚姻表 `marriages` 使用 `spouse1 < spouse2` 的有序对存储。查询"我的配偶"时，不知道我在 spouse1 位置还是 spouse2 位置：

```
marriages:
┌────┬─────────────┬──────────────────┬──────────────────┐
│ id │ genealogy_id│ spouse1_member_id│ spouse2_member_id│  (spouse1 < spouse2)
├────┼─────────────┼──────────────────┼──────────────────┤
│ 1  │      1      │        3         │        4         │  张大明(3) 和 李淑芬(4)
└────┴─────────────┴──────────────────┴──────────────────┘

查询 "张大明(3)的配偶":
  CASE WHEN 3 = 3 THEN 4  → 找 id=4 的成员 → 李淑芬

查询 "李淑芬(4)的配偶":
  CASE WHEN 4 = 3 THEN ... (FALSE) → ELSE 3  → 找 id=3 的成员 → 张大明
```

### 3.4 JOIN 的种类

| JOIN 类型 | SQL 关键字 | 保留规则 |
|-----------|-----------|---------|
| 内连接 | `JOIN` 或 `INNER JOIN` | 两表都匹配才保留 |
| 左连接 | `LEFT JOIN` | 左表全部保留，右表没匹配就填 NULL |
| 右连接 | `RIGHT JOIN` | 右表全部保留（很少用） |
| 全连接 | `FULL JOIN` | 两表全部保留（更少用） |

### 3.5 多表 JOIN 的执行顺序

```sql
FROM tree                              -- 第1张表
JOIN parent_child_relations rel       -- 第2张表
  ON rel.parent_member_id = tree.id
JOIN members child                    -- 第3张表
  ON child.id = rel.child_member_id
```

执行引擎的处理顺序：

```
① tree × rel  (按 ON 条件连接第1和第2张表)
② (tree+rel的结果) × child  (再连接第3张表)
③ WHERE 过滤
④ SELECT 投影
```

每次 JOIN 都会扩大结果集的**列数**（两张表的列拼在一起），然后 ON 条件决定哪些行组合被保留。

---

## 第 4 课：GROUP BY 与聚合函数 — 分组统计

### 4.1 聚合函数

聚合函数把**多行合并成一行**：

| 函数 | 作用 | 示例 |
|------|------|------|
| `COUNT(*)` | 数行数 | `COUNT(*)` → 5 |
| `AVG(列)` | 平均值 | `AVG(age)` → 45.3 |
| `SUM(列)` | 总和 | `SUM(population)` → 10000 |
| `MIN(列)` | 最小值 | `MIN(birth_year)` → 1920 |
| `MAX(列)` | 最大值 | `MAX(birth_year)` → 2020 |

### 4.2 GROUP BY — 分组

**语法**：

```sql
SELECT   分组列, 聚合函数(值列)
FROM     表
GROUP BY 分组列
```

**规则**：SELECT 中**不在聚合函数内的列**，必须出现在 GROUP BY 中。

**项目实例**（[平均寿命查询](file:///d:/上课/大三下/数据库/genealogy_system/sql/queries/07_avg_lifespan_by_generation.sql)）：

```sql
SELECT genealogy_id, generation_no,
       AVG(death_year - birth_year)::numeric(6,2) AS avg_lifespan,
       COUNT(*) AS member_count,
       MIN(birth_year) AS earliest_birth,
       MAX(death_year) AS latest_death
FROM members
WHERE genealogy_id = :genealogy_id
  AND birth_year IS NOT NULL
  AND death_year IS NOT NULL
  AND death_year > birth_year
GROUP BY genealogy_id, generation_no;
```

**执行演示**：

原始数据（WHERE 过滤后）：

```
┌──────────────┬───────────────┬───────────┬───────────┐
│ genealogy_id │ generation_no │ birth_year│ death_year│
├──────────────┼───────────────┼───────────┼───────────┤
│      1       │       1       │   1920    │   2005    │
│      1       │       1       │   1925    │   2010    │
│      1       │       2       │   1950    │   2018    │
│      1       │       2       │   1952    │   2020    │
│      1       │       3       │   1980    │    NULL   │ ← 被过滤（death_year=NULL）
└──────────────┴───────────────┴───────────┴───────────┘
```

**GROUP BY genealogy_id, generation_no** — 分组过程：

```
组1: genealogy_id=1, generation_no=1  → 2 行
    行: (1,1,1920,2005), (1,1,1925,2010)
    AVG(death_year - birth_year) = AVG(85, 85) = 85.00
    COUNT(*) = 2
    MIN(birth_year) = 1920
    MAX(death_year) = 2010

组2: genealogy_id=1, generation_no=2  → 2 行
    行: (1,2,1950,2018), (1,2,1952,2020)
    AVG(death_year - birth_year) = AVG(68, 68) = 68.00
    COUNT(*) = 2
    MIN(birth_year) = 1950
    MAX(death_year) = 2020
```

**最终输出**：

```
┌──────────────┬───────────────┬──────────────┬──────────────┬────────────────┬─────────────┐
│ genealogy_id │ generation_no │ avg_lifespan │ member_count │ earliest_birth │ latest_death│
├──────────────┼───────────────┼──────────────┼──────────────┼────────────────┼─────────────┤
│      1       │       1       │    85.00     │      2       │     1920       │    2010     │
│      1       │       2       │    68.00     │      2       │     1950       │    2020     │
└──────────────┴───────────────┴──────────────┴──────────────┴────────────────┴─────────────┘
```

**GROUP BY 的入参必须出现在 SELECT 中**：

```sql
-- ✅ 正确
SELECT genealogy_id, generation_no, AVG(...)
GROUP BY genealogy_id, generation_no

-- ❌ 错误（generation_no 在 SELECT 中但不在 GROUP BY 中）
SELECT generation_no, AVG(...)
GROUP BY genealogy_id
```

---

## 第 5 课：子查询与 WITH CTE — 查询嵌套与临时表

### 5.1 标量子查询 — 返回单个值

```sql
SELECT name,
       (SELECT COUNT(*) FROM parent_child_relations
        WHERE parent_member_id = members.id) AS children_count
FROM members;
```

子查询在 `SELECT` 中，对主查询的每一行执行一次，返回值作为一个列。

### 5.2 FROM 子查询 — 把查询结果当表用

```sql
SELECT nid FROM (
    SELECT parent_member_id AS nid FROM parent_child_relations
    WHERE genealogy_id = :gid AND child_member_id = :mid
    UNION ALL
    SELECT child_member_id FROM parent_child_relations
    WHERE genealogy_id = :gid AND parent_member_id = :mid
    UNION ALL
    SELECT spouse2_member_id FROM marriages
    WHERE genealogy_id = :gid AND spouse1_member_id = :mid
    UNION ALL
    SELECT spouse1_member_id FROM marriages
    WHERE genealogy_id = :gid AND spouse2_member_id = :mid
) neighbors
WHERE nid = ANY(:candidates) LIMIT 1;
```

**结构分析**：

```
外层查询:
  SELECT nid FROM ( ... ) neighbors    ← 子查询结果叫 "neighbors"
  WHERE nid = ANY(:candidates)

内层子查询 (4 个 UNION ALL):
  #1: 查父母
  #2: 查子女
  #3: 查配偶（正向）
  #4: 查配偶（反向）
  → 结果是一个"邻居列表"
```

括号 `()` 内的子查询像一个**匿名函数**：先执行它得到一个临时表 "neighbors"，然后外层用这个临时表继续查询。这与 Python 的嵌套函数调用类似：

```python
# Python 等价逻辑
neighbors = query1() + query2() + query3() + query4()
result = [n for n in neighbors if n in candidates]
```

### 5.3 WITH CTE — 带名字的临时表

**语法**：

```sql
WITH 临时表名 AS (
    查询语句
)
SELECT ... FROM 临时表名 ...
```

**项目实例**（[出生早于代平均](file:///d:/上课/大三下/数据库/genealogy_system/sql/queries/09_born_before_gen_avg.sql)）：

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
SELECT m.id, m.name, m.birth_year, m.generation_no,
       ga.avg_birth_year
FROM members m
JOIN gen_avg ga ON ga.generation_no = m.generation_no
               AND ga.genealogy_id = m.genealogy_id
WHERE m.birth_year < ga.avg_birth_year;
```

**执行过程**：

```
Step 1: WITH gen_avg AS (...)   — 先执行 CTE
  计算每一代的平均出生年份，存入临时表 gen_avg:
  ┌──────────────┬───────────────┬───────────────┐
  │ genealogy_id │ generation_no │ avg_birth_year│
  ├──────────────┼───────────────┼───────────────┤
  │      1       │       1       │    1922.50    │
  │      1       │       2       │    1951.00    │
  │      1       │       3       │    1981.00    │
  └──────────────┴───────────────┴───────────────┘

Step 2: 主查询 — members 表与 gen_avg 做 JOIN
  对 members 的每一行:
    找到对应 generation_no 的平均值
    比较 birth_year < avg?

  张德海, 1代, birth=1920: 1920 < 1922.50 ✅
  张大明, 2代, birth=1950: 1950 < 1951.00 ✅
  张小明, 3代, birth=1980: 1980 < 1981.00 ✅
```

**WITH CTE vs FROM 子查询的区别**：

| | FROM 子查询 | WITH CTE |
|----|-----------|---------|
| 可读性 | 嵌套，难读 | 先定义再使用，清晰 |
| 复用 | 不能复用 | 可被多次引用 |
| 优化 | 可能被优化器合并 | PostgreSQL 12+ 可被内联 |
| 递归 | 不支持 | **必须用 CTE** |

---

## 第 6 课：EXISTS 与 NOT EXISTS — 存在性检查

### 6.1 EXISTS — "是否存在至少一行"

**语法**：

```sql
WHERE EXISTS (子查询)
```

返回值：子查询至少返回 1 行 → TRUE；0 行 → FALSE。

**项目实例**（[无配偶男性](file:///d:/上课/大三下/数据库/genealogy_system/sql/queries/08_males_over_50_no_spouse.sql)）：

```sql
SELECT m.id, m.name
FROM members m
WHERE m.genealogy_id = :genealogy_id
  AND m.gender = 'male'
  AND NOT EXISTS (
      SELECT 1
      FROM marriages mar
      WHERE mar.genealogy_id = m.genealogy_id
        AND (mar.spouse1_member_id = m.id OR mar.spouse2_member_id = m.id)
  );
```

**逐词讲解**：

| 短语 | 含义 |
|------|------|
| `NOT EXISTS` | "不存在" — 子查询返回 0 行才为 TRUE |
| `SELECT 1` | 不关心查什么列，只关心有没有行（写成 `SELECT *` 也一样） |
| `FROM marriages mar` | 从婚姻表查 |
| `WHERE ... = m.id` | **关联子查询**：引用外层查询的 `m.id` |

**执行演示**：

```
外层查询: 对 members 中每个男性，执行子查询

m = (张德海, id=1):
  子查询:
    SELECT 1 FROM marriages
    WHERE (spouse1 = 1 OR spouse2 = 1) AND genealogy_id = 1
    → 找到 1 行（张德海和王秀兰的婚姻）
    → EXISTS = TRUE
    → NOT EXISTS = FALSE
    → 张德海被排除（他有配偶）

m = (张小明, id=5):
  子查询:
    SELECT 1 FROM marriages
    WHERE (spouse1 = 5 OR spouse2 = 5) AND genealogy_id = 1
    → 0 行
    → EXISTS = FALSE
    → NOT EXISTS = TRUE
    → 张小明被保留（他没有配偶记录）
```

**NOT EXISTS 的执行优势**：

PostgreSQL 会把 `NOT EXISTS` 优化为**反半连接**（Anti Semi Join），每行只要找到第 1 条匹配就立即停止（短路）。这比 `LEFT JOIN ... WHERE ... IS NULL` 高效，因为后者需要扫描全表再过滤。

### 6.2 子查询中的参数引用（关联子查询）

```sql
NOT EXISTS (
    SELECT 1 FROM marriages mar
    WHERE mar.genealogy_id = m.genealogy_id  -- ← 引用了外层的 m
)
```

这叫**关联子查询**（Correlated Subquery）：子查询引用了外层查询的列。对于外层查询的**每一行**，子查询都会用这行的值重新执行一次。

**非关联子查询**（独立执行一次，结果用于外层）：

```sql
WHERE id IN (SELECT member_id FROM some_independent_query)
```

---

## 第 7 课：WITH RECURSIVE — 递归查询（核心）

这是本项目最重要的 SQL 特性。族谱的本质是一个**图**，要找所有祖先/后代，必须在图中不断沿边走下去——这正是递归解决的问题。

### 7.1 语法结构

```sql
WITH RECURSIVE cte_name AS (
    -- 基础查询（第 0 层，只执行一次）
    SELECT ... FROM ... WHERE ...
    
    UNION [ALL]                           -- 去重方式
    
    -- 递归查询（每次都引用 cte_name 自己）
    SELECT ... FROM cte_name JOIN ... WHERE ...
)
SELECT ... FROM cte_name;
```

### 7.2 执行模型：Work Table + Intermediate Table

这是理解递归 CTE 的**钥匙**。PostgreSQL 内部用两张表实现：

```
┌───────────┐     ┌───────────┐     ┌───────────┐
│ Work      │────→│ 执行递归   │────→│Intermediate│
│ Table     │     │ 查询部分   │     │  Table    │
│(本轮输入) │     │           │     │(本轮输出) │
└───────────┘     └───────────┘     └───────────┘
      ↑                                    │
      │                                    │
      └────────────────────────────────────┘
              Intermediate 成为新的 Work Table
```

算法：

```
1. 执行基础查询 → Work Table + 结果集
2. LOOP:
    对 Work Table 执行递归查询 → Intermediate Table
    IF Intermediate Table 为空: BREAK
    Intermediate → 新的 Work Table
    将 Intermediate 追加到结果集
3. RETURN 结果集 (受 UNION/UNION ALL 影响)
```

### 7.3 祖先查询：逐轮演示

```sql
WITH RECURSIVE ancestors AS (
    SELECT p.parent_member_id AS member_id, 1 AS depth
    FROM parent_child_relations p
    WHERE p.child_member_id = 100              -- ← 基础: 查张小明(ID=100)的父母
    
    UNION                                     -- ← 每层去重
    
    SELECT p.parent_member_id, a.depth + 1
    FROM parent_child_relations p
    JOIN ancestors a ON p.child_member_id = a.member_id
    WHERE a.depth < 10
)
SELECT * FROM ancestors ORDER BY depth;
```

**数据准备**：

```
parent_child_relations 表:
┌────┬──────────────┬───────────────────┬──────────────────┬─────────────┐
│ id │ genealogy_id │ parent_member_id  │ child_member_id  │ parent_role │
├────┼──────────────┼───────────────────┼──────────────────┼─────────────┤
│ 1  │      1       │       200         │       100        │   father    │  张大明 是 张小明 的父
│ 2  │      1       │       201         │       100        │   mother    │  李淑芬 是 张小明 的母
│ 3  │      1       │       300         │       200        │   father    │  张德海 是 张大明 的父
│ 4  │      1       │       301         │       200        │   mother    │  王秀兰 是 张大明 的母
│ 5  │      1       │       300         │       201        │   father    │  张德海 是 李淑芬 的父 (同一人!)
│ 6  │      1       │       301         │       201        │   mother    │  王秀兰 是 李淑芬 的母 (同一人!)
└────┴──────────────┴───────────────────┴──────────────────┴─────────────┘
```

**第 1 轮：基础查询**

```
SQL: SELECT parent_member_id, 1 FROM parent_child_relations
     WHERE child_member_id = 100

执行:
  扫描 parent_child_relations 表
  条件: child_member_id = 100
  → 找到行 1: parent_member_id=200
  → 找到行 2: parent_member_id=201

结果:
  ┌───────────┬───────┐
  │ member_id │ depth │
  ├───────────┼───────┤
  │    200    │   1   │
  │    201    │   1   │
  └───────────┴───────┘

Work Table = [(200,1), (201,1)]
结果集     = [(200,1), (201,1)]
```

**第 2 轮：递归查询（处理 Work Table）**

```
SQL: SELECT p.parent_member_id, a.depth + 1
     FROM parent_child_relations p
     JOIN ancestors a ON p.child_member_id = a.member_id
     WHERE a.depth < 10

  这里的 "ancestors a" 实际指向上一轮的 Work Table: [(200,1), (201,1)]

对 Work Table 中每一行执行:
  ① 行 (200,1):
     JOIN: p.child_member_id = 200
     → 扫描 child_member_id = 200
     → 找到行 3: parent=300
     → 找到行 4: parent=301
     → 产出: (300, 1+1=2), (301, 1+1=2)

  ② 行 (201,1):
     JOIN: p.child_member_id = 201
     → 找到行 5: parent=300
     → 找到行 6: parent=301
     → 产出: (300, 2), (301, 2)

UNION 去重前: [(300,2), (301,2), (300,2), (301,2)]
UNION 去重后: [(300,2), (301,2)]

Work Table = [(300,2), (301,2)]
结果集追加 = [(200,1), (201,1), (300,2), (301,2)]
```

**第 3 轮**：

```
Work Table: [(300,2), (301,2)]

对 (300,2): child_member_id = 300 → 假设找到 parent=400 → (400,3)
对 (301,2): child_member_id = 301 → 假设找到 parent=401 → (401,3)

UNION 去重后: [(400,3), (401,3)]

Work Table = [(400,3), (401,3)]
结果集追加 = [..., (400,3), (401,3)]
```

**第 N 轮**：某次递归查询返回 0 行 → 循环终止。

### 7.4 CYCLE 子句：防止死循环

```sql
) CYCLE member_id SET is_cycle USING cycle_path
```

**语法拆解**：

| 部分 | 含义 |
|------|------|
| `CYCLE member_id` | 要检测的列（哪个列形成环？） |
| `SET is_cycle` | 如果检测到环，`is_cycle` 列 = TRUE |
| `USING cycle_path` | 环的路径存放在 `cycle_path` 列中 |

**为什么需要它？**

```
A → B → C → A  形成环
  
没有 CYCLE 子句:
  第0轮: A
  第1轮: B (从A)
  第2轮: C (从B)
  第3轮: A (从C)  ← 已出现过的A又出现, 产生新行
  第4轮: B (从A)
  ... 无限循环直至 depth 上限

有 CYCLE 子句:
  第3轮: 检测到 A 在第0轮出现过
  → 标记 is_cycle = TRUE
  → 第4轮跳过 (不再以该行为基础继续)
```

在最终 `SELECT` 中通过 `WHERE NOT is_cycle` 排除形成环的行。

### 7.5 UNION vs UNION ALL 在递归中的致命差异

以祖先查询的第 2 轮为例，展示了为什么必须用 `UNION`：

```
张大明(200) 和 李淑芬(201) 共享同一对父母 (300, 301)

UNION ALL 不进行去重:
  第 2 轮产出: [(300,2), (301,2), (300,2), (301,2)]
  → Work Table = 4 行

  第 3 轮: 4 行各自扩展
  → 每行找到 2 个父母
  → 产出 4 × 2 = 8 行
  → Work Table = 8 行

  第 4 轮: 8 × 2 = 16 行
  ...指数级增长！(n/4 × 2^depth)

UNION 进行去重:
  第 2 轮产出: [(300,2), (301,2)] ← 去重后
  → Work Table = 2 行

  第 3 轮: 2 × 2 = 4 行 → 去重后可能只有 2~3 行
  ...线性增长！受限于族谱的实际人数
```

**这就是"一字之改"把 126 秒变成 0.2 秒的原理**。`UNION` 把"枚举所有路径"变成了"枚举所有可达节点"。

### 7.6 后代查询的差异

```sql
-- 祖先（向上一代）
SELECT p.parent_member_id, depth + 1
FROM parent_child_relations p
JOIN ancestors a ON p.child_member_id = a.member_id
--                  ^^^^^^^^^^^^^^           ^^^^^^^^^^
--                  "新的子=当前的人"        当前的人

-- 后代（向下一代）  
SELECT p.child_member_id, depth + 1
FROM parent_child_relations p
JOIN descendants d ON p.parent_member_id = d.member_id
--                      ^^^^^^^^^^^^^^^^           ^^^^^^^^^^
--                      "新的父=当前的人"          当前的人
```

两者的 JOIN 条件完全对称，只是 `parent` 和 `child` 的位置互换。

---

## 第 8 课：VALUES, ANY, 数组, 字符串拼接 — 高级短语

### 8.1 VALUES — 构造一个"纸上表格"

```sql
VALUES (1, 'Alice'), (2, 'Bob'), (3, 'Charlie')
```

这就是一个 3 行 2 列的表：

```
column1 │ column2
────────┼────────
   1    │  Alice
   2    │  Bob
   3    │  Charlie
```

可以给它起列名：

```sql
SELECT * FROM (VALUES (1,'Alice'), (2,'Bob')) AS t(id, name);
```

**项目实例**（[`_lookup_relations_batch()`](file:///d:/上课/大三下/数据库/genealogy_system/app/members/routes.py#L498)）：

```sql
FROM (VALUES (CAST(:a0 AS INTEGER), CAST(:b0 AS INTEGER)),
            (CAST(:a1 AS INTEGER), CAST(:b1 AS INTEGER))) AS p(a, b)
```

这构造了一个叫 `p` 的表，有两列 `a` 和 `b`，每行是一个 (成员ID, 成员ID) 对。

**为什么用 VALUES？** 这样可以一次发送多对 ID 给数据库，用一条 SQL 完成多次查询。

### 8.2 ANY — "在列表中"

```sql
WHERE member_id = ANY(:candidates)
```

`:candidates` 是一个 Python 列表 `[200, 201, 202, ...]`，psycopg 驱动自动转为 PostgreSQL 数组。

等价于：

```sql
WHERE member_id IN (200, 201, 202, ...)
```

**项目中的应用**（[`_reconstruct_path()`](file:///d:/上课/大三下/数据库/genealogy_system/app/members/routes.py#L413-L416)）：

```sql
SELECT nid FROM (...) neighbors
WHERE nid = ANY(:candidates) LIMIT 1
```

`candidates` 是深度为 d 的所有成员的 ID 列表。这句话的意思是："查当前节点(300)的所有邻居，但只保留那些深度对得上的"。

**执行方式**：

PostgreSQL 看到 `= ANY(array)` 会展开为：
```
nid = 200 OR nid = 201 OR nid = 202 OR ...
```

然后对每个值走一次索引查找，结果通过位图合并。

### 8.3 PostgreSQL 数组

```sql
-- 创建数组
ARRAY[1, 2, 3]                    →  {1,2,3}
ARRAY[]::TEXT[]                   →  {}     (空文本数组)

-- 数组追加
ARRAY[1] || 2                     →  {1,2}

-- 数组元素类型声明
ARRAY[]::TEXT[]                    ← 明确声明这是文本数组
```

**项目实例**（[`_reconstruct_path_sql()`](file:///d:/上课/大三下/数据库/genealogy_system/app/members/routes.py#L436-L437)）：

```sql
ARRAY[CAST(:start_id AS INTEGER)] AS path,    -- 初始路径: [100]
ARRAY[]::TEXT[] AS rels,                      -- 初始关系: [] (空)

-- 递归中追加:
walk.path || e.to_id,                         -- [100] || 200 = [100, 200]
walk.rels || e.relation_type,                 -- [] || 'parent' = ['parent']
```

与字符串 `',100,200,'` 相比，数组的优势：
1. 类型安全（不是字符串解析）
2. 更好的索引支持（GIN 索引可加速 `@>` 包含运算）
3. 更自然的数据结构

### 8.4 LIMIT 与 OFFSET — 分页

```sql
SELECT * FROM members
WHERE genealogy_id = 1
ORDER BY id
LIMIT 2000 OFFSET 4000;
```

| 子句 | 含义 |
|------|------|
| `LIMIT 2000` | 最多 2000 行 |
| `OFFSET 4000` | 跳过前 4000 行 |

所以这句查的是第 4001 ~ 6000 行。

**CSV 流式导出中的应用**（[`genealogies/routes.py`](file:///d:/上课/大三下/数据库/genealogy_system/app/genealogies/routes.py#L272-L279)）：

```python
offset = 0
while True:
    rows = db.session.execute(
        text("SELECT ... LIMIT 2000 OFFSET :offset"),
        {"offset": offset}
    ).fetchall()
    if not rows: break
    # 处理这 2000 行...
    offset += 2000
```

### 8.5 UNION ALL — 拼接两个查询结果

```sql
SELECT 'spouse' AS kind, ... FROM marriages ...
UNION ALL
SELECT 'child' AS kind, ... FROM parent_child_relations ...
```

**规则**：

| 规则 | 说明 |
|------|------|
| 列数相同 | 上下两个 SELECT 必须有相同数量的列 |
| 类型兼容 | 对应的列类型必须兼容（或可隐式转换） |
| 列名 | 以上面的 SELECT 为准 |
| UNION ALL | 不去重，直接拼接 |
| UNION | 去重后拼接 |

---

## 第 9 课：PL/pgSQL 存储函数 — 在数据库中写程序

数据库不只是存数据，还可以在里面运行程序。PL/pgSQL 是 PostgreSQL 的过程式语言，可以写循环、条件判断和异常处理。

### 9.1 基本语法

```sql
CREATE OR REPLACE FUNCTION 函数名(参数名 类型, ...)
RETURNS 返回类型 AS $$
DECLARE
    变量名 类型;          -- 声明局部变量
BEGIN
    -- 函数体（过程式代码）
    RETURN 值;
END;
$$ LANGUAGE plpgsql;
```

| 部分 | 含义 |
|------|------|
| `CREATE OR REPLACE` | 没有就创建，有就替换 |
| `RETURNS TABLE(...)` | 返回一个表（多行多列） |
| `$$ ... $$` | 函数体定界符（不用考虑引号转义） |
| `DECLARE ... BEGIN ... END` | 变量声明 → 函数体 |
| `LANGUAGE plpgsql` | 声明语言为 PL/pgSQL |

### 9.2 完整实例：bfs_reachable

[`sql/functions/bfs_reachable.sql`](file:///d:/上课/大三下/数据库/genealogy_system/sql/functions/bfs_reachable.sql)：

```sql
CREATE OR REPLACE FUNCTION bfs_reachable(
    p_genealogy_id INTEGER,      -- 参数1: 族谱ID（命名以 p_ 开头是惯例）
    p_root_id INTEGER,           -- 参数2: 起点成员ID
    p_max_depth INTEGER          -- 参数3: 最大搜索深度
) RETURNS TABLE(member_id INTEGER, depth INTEGER) AS $$
DECLARE
    current_depth INTEGER := 0;   -- 变量: 当前搜索深度，初始值 0
    row_count INTEGER;            -- 变量: 本轮新增行数
BEGIN
    -- ① 创建临时表（如果已有就清空）
    CREATE TEMP TABLE IF NOT EXISTS bfs_visited (
        vid INTEGER PRIMARY KEY,       -- 成员ID，主键 = 自动去重
        vdepth INTEGER NOT NULL        -- 最短距离
    ) ON COMMIT DROP;                  -- 事务结束时自动删除
    TRUNCATE bfs_visited;

    -- ② 插入起点（深度 0）
    INSERT INTO bfs_visited VALUES (p_root_id, 0);

    -- ③ 循环 BFS
    LOOP
        EXIT WHEN current_depth >= p_max_depth;   -- 达到深度上限，退出

        -- 查找当前深度所有节点的邻居，插入新深度
        INSERT INTO bfs_visited
        SELECT DISTINCT e.to_id, current_depth + 1
        FROM bfs_visited v
        CROSS JOIN LATERAL (                       -- 对每个 v 行，执行子查询
            SELECT parent_member_id AS to_id
            FROM parent_child_relations
            WHERE genealogy_id = p_genealogy_id
              AND child_member_id = v.vid
            UNION ALL
            SELECT child_member_id
            FROM parent_child_relations
            WHERE genealogy_id = p_genealogy_id
              AND parent_member_id = v.vid
            UNION ALL
            SELECT spouse2_member_id
            FROM marriages
            WHERE genealogy_id = p_genealogy_id
              AND spouse1_member_id = v.vid
            UNION ALL
            SELECT spouse1_member_id
            FROM marriages
            WHERE genealogy_id = p_genealogy_id
              AND spouse2_member_id = v.vid
        ) e
        WHERE v.vdepth = current_depth             -- 只看当前深度的行
          AND e.to_id IS NOT NULL                   -- 邻居存在
        ON CONFLICT (vid) DO NOTHING;               -- 如果已访问过，跳过

        GET DIAGNOSTICS row_count = ROW_COUNT;      -- 获取本轮插入的行数
        EXIT WHEN row_count = 0;                    -- 没有新节点，退出
        
        current_depth := current_depth + 1;         -- 深度 +1
    END LOOP;

    -- ④ 返回全部访问过的节点
    RETURN QUERY SELECT v.vid, v.vdepth FROM bfs_visited v;
END;
$$ LANGUAGE plpgsql;
```

**逐段讲解**：

#### (1) 函数签名

```sql
CREATE OR REPLACE FUNCTION bfs_reachable(
    p_genealogy_id INTEGER,
    p_root_id INTEGER,
    p_max_depth INTEGER
) RETURNS TABLE(member_id INTEGER, depth INTEGER) AS $$
```

- `CREATE OR REPLACE`：第 1 次运行创建函数，之后运行替换（方便迭代开发）
- `p_` 前缀：匈牙利命名法，标识这是参数（parameter），区别于局部变量
- `RETURNS TABLE(...)`：返回多行，每行有 member_id 和 depth 两列
- `$$`：PostgreSQL 的美元引号（dollar quoting），替代单引号。因为函数体里有很多单引号，用 `$$` 就不用每个单引号都写 `''` 转义了

#### (2) 变量声明

```sql
DECLARE
    current_depth INTEGER := 0;
    row_count INTEGER;
```

`:=` 是 PL/pgSQL 的赋值符号。`current_depth` 有初始值 0，`row_count` 没有初始值（默认为 NULL）。

#### (3) 临时表

```sql
CREATE TEMP TABLE IF NOT EXISTS bfs_visited (
    vid INTEGER PRIMARY KEY,
    vdepth INTEGER NOT NULL
) ON COMMIT DROP;
```

| 关键字 | 含义 |
|--------|------|
| `TEMP TABLE` | 临时表：只在当前会话可见，其他连接看不到 |
| `IF NOT EXISTS` | 如果表已存在就不创建 |
| `PRIMARY KEY` | vid 是主键 → 自动建立唯一索引 → `ON CONFLICT` 可以用 |
| `ON COMMIT DROP` | 事务提交时自动删除这张表 |

**为什么列名用 `vid`, `vdepth` 而不是 `member_id`, `depth`？**

因为 `RETURNS TABLE(member_id INTEGER, depth INTEGER)` 定义了输出列名 `member_id` 和 `depth`。如果临时表列名也叫 `member_id`，在 `ON CONFLICT (member_id)` 处会产生歧义——PostgreSQL 不知道你指的是 `RETURNS TABLE` 列还是 temp table 列。用不同的名字 `vid`/`vdepth` 彻底避免这个问题。

#### (4) CROSS JOIN LATERAL

```sql
FROM bfs_visited v
CROSS JOIN LATERAL (子查询) e
```

| 部分 | 含义 |
|------|------|
| `CROSS JOIN` | 笛卡尔积：左表的每行与右表的每行组合 |
| `LATERAL` | **关键**：右面的子查询可以引用左面表的列（`v.vid`, `v.vdepth`），就像 for 循环的嵌套 |
| `(子查询) e` | 子查询结果叫 `e` |

**LATERAL 的执行等效于**：

```python
for v in bfs_visited:
    result = execute_subquery(v.vid, v.vdepth)
    for row in result:
        output(v, row)
```

普通子查询不能引用外部表的列，但 `LATERAL` 允许。对于每行 `v`，子查询都重新执行一次，专门查找 `v.vid` 的邻居。

#### (5) ON CONFLICT DO NOTHING

```sql
INSERT INTO bfs_visited ...
ON CONFLICT (vid) DO NOTHING;
```

| 部分 | 含义 |
|------|------|
| `ON CONFLICT (vid)` | 如果插入时 `vid` 违反主键约束（即：已存在同 ID 的行） |
| `DO NOTHING` | 那就什么也不做（跳过这行，不报错） |

这比"先 SELECT 检查是否存在，再 INSERT"高效得多——一次操作完成，不需要额外的往返查询。

#### (6) 循环控制

```sql
LOOP
    EXIT WHEN condition;    -- 满足条件就跳出
    ...
END LOOP;
```

等价于 Python 的：
```python
while True:
    if condition: break
    ...
```

#### (7) GET DIAGNOSTICS

```sql
GET DIAGNOSTICS row_count = ROW_COUNT;
```

`ROW_COUNT` 是 PostgreSQL 内置变量，记录**上一条 SQL 影响的行数**。`GET DIAGNOSTICS` 把这个值存入变量 `row_count`。

#### (8) 返回结果

```sql
RETURN QUERY SELECT v.vid, v.vdepth FROM bfs_visited v;
```

`RETURN QUERY` 把查询结果逐行追加到函数的返回值中。注意列名要与 `RETURNS TABLE(member_id, depth)` 中的对应：`vid → member_id`, `vdepth → depth`。

### 9.3 调用方式

在 Python 中：

```python
rows = db.session.execute(
    text("SELECT member_id, depth FROM bfs_reachable(:gid, :rid, :md)"),
    {"gid": 1, "rid": 100, "md": 10}
).fetchall()
```

在 psql 命令行中：

```sql
SELECT * FROM bfs_reachable(1, 100, 10);
```

就像调用一个普通的表函数一样。

### 9.4 为什么用存储函数而不是全在 Python 里做？

| 在 Python 中做 | 用存储函数做 |
|---------------|------------|
| 每次查询都要返回数据到 Python | 中间结果留在数据库内存中 |
| 多轮 BFS = 多次网络往返 | 一轮全在数据库内完成 |
| Python 和 DB 之间传输所有中间结果 | 只传最终结果 |

存储函数的本质是**把计算推到数据所在的地方**，减少数据传输。

---

## 总结：SQL 学习路径

```
第1-2课: 基础语法           SELECT, FROM, WHERE, CASE, COALESCE, CAST
    ↓
第3课:   表连接             JOIN, ON, 多表 JOIN
    ↓
第4课:   分组聚合           GROUP BY, AVG, COUNT, MIN, MAX
    ↓
第5课:   查询嵌套           FROM子查询, WITH CTE
    ↓
第6课:   存在性检查         EXISTS, NOT EXISTS, 关联子查询
    ↓
第7课:   递归查询 ⭐         WITH RECURSIVE, UNIX/UNION ALL, CYCLE, 执行模型
    ↓
第8课:   高级短语           VALUES, ANY, 数组, LIMIT/OFFSET
    ↓
第9课:   存储函数           PL/pgSQL, 临时表, LATERAL, 循环
```

建议对照项目中的 [`sql/queries/`](file:///d:/上课/大三下/数据库/genealogy_system/sql/queries/) 目录，逐一阅读每个 `.sql` 文件；再结合 [`sql_reference.md`](file:///d:/上课/大三下/数据库/genealogy_system/docs/sql_reference.md) 和 [`qa_defense.md`](file:///d:/上课/大三下/数据库/genealogy_system/docs/qa_defense.md) 理解设计原理。

---

*文档生成日期: 2026-05-12*