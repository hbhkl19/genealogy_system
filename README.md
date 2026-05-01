# 寻根溯源族谱管理系统

这是一个面向课程实验的族谱管理系统，默认技术栈为 `Flask + Jinja2 + Bootstrap + SQLAlchemy + PostgreSQL 16`。当前版本已搭好可运行的大致框架，后续可以按阶段继续补充大规模数据生成、完整关系维护、性能实验和报告材料。

## 主要功能

- 用户注册、登录、退出和登录拦截。
- 多族谱管理：创建族谱、查看自己创建或受邀参与的族谱。
- 协作者邀请：族谱创建者可通过邮箱邀请其他用户参与。
- 成员管理：添加成员、成员列表、按姓名模糊搜索。
- Dashboard 统计：展示族谱总人数、男性人数、女性人数。
- 树形预览入口：当前先展示根节点成员，后续可扩展为折叠树。
- 递归查询入口：成员祖先查询、两人亲缘链路查询。
- CSV 导出入口：导出某族谱成员基础数据。
- SQL 实验目录：预留祖先、后代、亲缘路径、性能查询和数据校验 SQL。

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
- 当前目录不是 Git 仓库，如需要版本管理可执行 `git init`。
- `rg` 在当前环境中运行时报 `Access is denied`，检查文件时已改用 PowerShell 原生命令。

## 后续实施重点

- 使用 `COPY` 导入生成数据后，准备演示账号和截图材料。
- 完成 `EXPLAIN (ANALYZE, BUFFERS)` 性能对比并保存截图。
- 整理 E-R 图、关系模式、3NF 说明、DDL 和实验报告。
