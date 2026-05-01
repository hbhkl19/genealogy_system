# 数据生成、导入与分支导出

本文档对应 M6，说明如何生成课程实验所需的大规模数据、使用 PostgreSQL `COPY` 导入，以及导出某个成员分支。

## 生成 CSV

默认命令会生成 10 个族谱、共 104000 个成员，其中第一个族谱 50000 人，所有族谱均为 30 代。

```powershell
.venv\Scripts\python.exe scripts\seed_data.py --output-dir data\generated
```

默认规模：

- 族谱数：10
- 成员总数：104000
- 最大单族谱成员数：50000
- 最大代际深度：30
- 每个成员至少存在一条婚姻或血缘边

小规模调试示例：

```powershell
.venv\Scripts\python.exe scripts\seed_data.py --output-dir data\test_generated --sizes 20,10 --generations 5
```

生成文件：

- `users.csv`
- `genealogies.csv`
- `genealogy_collaborators.csv`
- `members.csv`
- `parent_child_relations.csv`
- `marriages.csv`

## COPY 导入

推荐使用 Python 导入脚本，它内部调用 PostgreSQL `COPY`。

```powershell
.venv\Scripts\python.exe scripts\import_csv.py --input-dir data\generated --truncate
```

参数说明：

- `--input-dir`：CSV 文件目录。
- `--truncate`：导入前清空目标表并重置序列。该参数会删除当前数据库中的相关业务数据，正式使用前需要确认。

也可以参考 `sql/copy_import.sql`，在 `psql` 中手工执行 `\copy` 命令。

## 导出某个分支

按成员 ID 导出该成员及其所有递归后代，同时导出分支内部父子关系和分支内部婚姻关系。

```powershell
.venv\Scripts\python.exe scripts\export_branch.py --member-id 1 --output-dir data\branch_export
```

导出文件：

- `members.csv`
- `parent_child_relations.csv`
- `marriages.csv`

## 验收 SQL

导入后可执行：

```sql
SELECT COUNT(*) FROM genealogies;
SELECT COUNT(*) FROM members;
SELECT MAX(cnt)
FROM (
    SELECT genealogy_id, COUNT(*) AS cnt
    FROM members
    GROUP BY genealogy_id
) t;
SELECT MAX(generation_no) FROM members;
```

还可以检查是否每个成员至少存在一条婚姻或血缘边：

```sql
SELECT COUNT(*)
FROM members m
WHERE NOT EXISTS (
    SELECT 1
    FROM parent_child_relations p
    WHERE p.parent_member_id = m.id OR p.child_member_id = m.id
)
AND NOT EXISTS (
    SELECT 1
    FROM marriages s
    WHERE s.spouse1_member_id = m.id OR s.spouse2_member_id = m.id
);
```
