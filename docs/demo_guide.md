# 演示指南

本文档用于课堂演示和答辩。

## 1. 准备环境

```powershell
.venv\Scripts\Activate.ps1
flask --app app db upgrade
```

如需演示 10 万级数据：

```powershell
.venv\Scripts\python.exe scripts\seed_data.py --output-dir data\generated
.venv\Scripts\python.exe scripts\import_csv.py --input-dir data\generated --truncate
```

`--truncate` 会清空当前业务表再导入大数据。若只想演示页面功能，可使用小型演示数据：

```powershell
.venv\Scripts\python.exe scripts\create_demo_data.py
```

演示账号：

- 邮箱：`demo@example.com`
- 密码：`demo123456`

## 2. 启动系统

```powershell
flask --app app run
```

浏览器访问：

```text
http://127.0.0.1:5000
```

## 3. 页面演示顺序

1. 打开首页，说明系统目标：多用户、多族谱、成员关系管理、递归查询。
2. 使用演示账号登录。
3. 进入“我的族谱”，打开“演示族谱”或大数据导入后的“实验族谱 1”。
4. 展示 Dashboard：总人数、男性人数、女性人数。
5. 进入成员列表：
   - 按姓名搜索。
   - 新增成员。
   - 编辑成员。
   - 删除成员。
6. 点击某个成员的“关系”：
   - 添加父母。
   - 添加子女。
   - 添加婚姻关系。
   - 展示非法关系会被应用层和数据库约束拦截。
7. 点击“祖先”，展示递归 CTE 向上查询。
8. 点击“后代”，展示递归 CTE 向下查询。
9. 打开“树形预览”，展示缩进树。
10. 在成员列表顶部输入两个成员 ID，点击“亲缘链路”，展示最短亲缘路径和每一步关系类型。
11. 点击“导出成员 CSV”，展示导出功能。

## 4. SQL 与性能演示

验收数据规模：

```powershell
.venv\Scripts\python.exe scripts\db_smoke_test.py
```

生成四代查询性能对比报告：

```powershell
.venv\Scripts\python.exe scripts\explain_performance.py --output docs\performance_results.md
```

脚本会在事务中临时移除父子关系索引测一次无索引计划，然后回滚，再测一次有索引计划。

## 5. 截图清单

- 登录页
- 我的族谱
- 族谱 Dashboard
- 成员列表与搜索
- 成员关系维护
- 祖先查询
- 后代查询
- 树形预览
- 亲缘链路
- CSV 导出结果
- `db_smoke_test.py` 输出
- `docs/performance_results.md` 中的 EXPLAIN 对比
