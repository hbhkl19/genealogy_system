# 寻根溯源族谱管理系统

这是一个面向课程实验的族谱管理系统，默认技术栈为 `Flask + Jinja2 + Bootstrap + SQLAlchemy + PostgreSQL 16`。当前版本已覆盖课程验收所需的应用界面、数据库建模、模拟数据、导入导出、递归 SQL、索引优化和报告材料骨架。

## 主要功能

- 用户注册、登录、退出和登录拦截。
- 多族谱管理：创建、编辑、删除族谱，查看自己创建或受邀参与的族谱。
- 族谱基本信息：谱名、姓氏、修谱年份、简介、创建用户。
- 协作者邀请：族谱创建者可通过邮箱邀请其他用户参与（viewer/editor 角色）。
- 成员管理：添加/编辑/删除成员、按姓名模糊搜索（GIN trigram 索引加速）、分页。
- 关系管理：添加父母、配偶、子女关系。
- Dashboard 统计：总人数、男女比例。
- 树形预览：递归 CTE 展开全族谱树（12 层、500 行限制）。
- 递归查询：祖先追溯、后代追溯、亲缘最短路径（BFS + CYCLE 子句）。
- SQL 统计页：5 类 PPT 要求查询集中展示。
- CSV 导出：流式分块导出、支持 50K+ 成员。
- 数据库级约束：8 条 CHECK + 3 个跨行触发器。

## 环境需求

- VSCode Stable
- Python 3.11.x 推荐；当前本机 `.venv` 检测到的是 Python 3.13.3，也可以先用于开发验证。
- PostgreSQL 16.x
- Git
- 推荐 VSCode 扩展：
  - `ms-python.python`
  - `ms-python.vscode-pylance`
  - `mtxr.sqltools`
  - `mtxr.sqltools-driver-pg`
  - `ms-azuretools.vscode-docker`

## Python 依赖

依赖已写入 `requirements.txt`：

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## 数据库准备

推荐数据库名为 `genealogy_lab`，并启用 `pg_trgm` 扩展用于姓名模糊查询索引。

```powershell
psql -U postgres -c "CREATE DATABASE genealogy_lab;"
psql -U postgres -d genealogy_lab -c "CREATE EXTENSION IF NOT EXISTS pg_trgm;"
```

`.env` 示例：

```env
FLASK_APP=app
FLASK_ENV=development
SECRET_KEY=dev-secret-key
DATABASE_URL=postgresql+psycopg://postgres:123456@localhost:5432/genealogy_lab
```

## 启动方式

```powershell
.venv\Scripts\Activate.ps1
flask --app app db upgrade
flask --app app routes
flask --app app run
```

浏览器访问：

```text
http://127.0.0.1:5000
```

## 数据生成与导入

生成满足实验规模要求的 CSV：

```powershell
.venv\Scripts\python.exe scripts\seed_data.py --output-dir data\generated
```

导入 PostgreSQL：

```powershell
.venv\Scripts\python.exe scripts\import_csv.py --input-dir data\generated --truncate
```

导出某个成员分支：

```powershell
.venv\Scripts\python.exe scripts\export_branch.py --member-id 1 --output-dir data\branch_export
```

详细说明见 [docs/data_pipeline.md](docs/data_pipeline.md)。

## 演示与报告

创建小型演示账号和演示族谱：

```powershell
.venv\Scripts\python.exe scripts\create_demo_data.py
```

演示账号：

```text
demo@example.com
demo123456
```

数据库验收：

```powershell
.venv\Scripts\python.exe scripts\db_smoke_test.py
```

性能对比：

```powershell
.venv\Scripts\python.exe scripts\explain_performance.py --output docs\performance_results.md
```

演示流程见 [docs/demo_guide.md](docs/demo_guide.md)，验收指导见 [docs/acceptance_guide.md](docs/acceptance_guide.md)，备份恢复见 [docs/backup_restore.md](docs/backup_restore.md)，报告提纲见 [docs/report_outline.md](docs/report_outline.md)。

完整改动记录见 **[CHANGELOG.md](CHANGELOG.md)**。

## 项目结构

```text
app/
  auth/             用户注册、登录、退出
  genealogies/      族谱管理、协作者、成员列表、导出
  members/          成员查询、祖先查询、亲缘链路
  main/             首页
  templates/        Jinja2 页面模板
  static/           CSS 等静态资源
scripts/            数据生成、导入导出脚本
sql/
  queries/          实验 SQL
tests/              pytest 测试
docs/               报告、截图、ER 图等材料
data/               CSV 数据文件
```

## 当前配置检查结果

- `.env` 已存在，包含 Flask 和 PostgreSQL 连接配置。
- `.venv` 已存在，且已安装 Flask、SQLAlchemy、Flask-Login、Flask-Migrate、psycopg、Faker、pytest。
- `.vscode/settings.json` 已配置 Python 解释器、pytest 和 SQLTools 连接。
- 已补充 `.vscode/extensions.json`、`.vscode/launch.json`、`.vscode/tasks.json`。
- 已接入 Flask-Migrate，首个迁移版本位于 `migrations/versions/`。
- 当前目录已是 Git 仓库。
- 当前数据库迁移版本应为 `a7c9d2f4b601 (head)`。

## 文档索引

| 文档 | 说明 |
|------|------|
| [CHANGELOG.md](CHANGELOG.md) | 完整改动记录（自克隆以来所有修改） |
| [docs/project_overview.md](docs/project_overview.md) | 项目完整文档（对照 PPT 要求） |
| [docs/task_checklist.md](docs/task_checklist.md) | PPT 任务逐条对照清单 |
| [docs/acceptance_guide.md](docs/acceptance_guide.md) | 验收演示指导（15 分钟路径） |
| [docs/data_model.md](docs/data_model.md) | ER 图 + 关系模式 + 范式分析 |
| [docs/data_pipeline.md](docs/data_pipeline.md) | 数据管道操作指南 |
| [docs/performance_results.md](docs/performance_results.md) | 索引性能对比 (258×) |
| [docs/demo_guide.md](docs/demo_guide.md) | 演示操作指南 |
