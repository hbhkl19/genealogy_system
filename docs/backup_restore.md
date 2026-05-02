# 备份与恢复

## 备份数据库

推荐使用 `pg_dump`：

```powershell
pg_dump -U postgres -d genealogy_lab -F c -f data\genealogy_lab.backup
```

也可以导出 SQL 文本：

```powershell
pg_dump -U postgres -d genealogy_lab -f data\genealogy_lab.sql
```

## 恢复数据库

创建测试库：

```powershell
createdb -U postgres genealogy_lab_restore
```

恢复自定义格式备份：

```powershell
pg_restore -U postgres -d genealogy_lab_restore data\genealogy_lab.backup
```

恢复 SQL 文本：

```powershell
psql -U postgres -d genealogy_lab_restore -f data\genealogy_lab.sql
```

## CSV 级别备份

生成数据和分支导出均为 CSV，可作为课程实验的轻量备份材料：

```powershell
.venv\Scripts\python.exe scripts\seed_data.py --output-dir data\generated
.venv\Scripts\python.exe scripts\export_branch.py --member-id 1 --output-dir data\branch_export
```
