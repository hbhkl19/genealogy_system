# 寻根溯源族谱管理系统 — 项目完整文档

> 数据库应用实践课程项目  
> 技术栈：Flask 3 + SQLAlchemy + PostgreSQL 16 + Bootstrap 5  
> 日期：2026-05-12

---

## 一、项目概述

**系统定位**：面向多用户的在线族谱（家谱）数字化管理平台。

**业务背景**：传统纸质家谱难以多人协作维护，查阅效率低。本系统将族谱数字化，
用户可创建属于自己家族的电子族谱，添加历代成员信息，维护血缘与婚姻关系，
并通过 SQL 驱动的统计分析功能洞察家族数据。

**核心能力**：
- 10 族谱、104,000 成员、30 代树 — 满足大规模数据场景
- 基于角色的协作机制 (owner/viewer/editor)
- 7 条 CHECK 约束 + 5 个触发器 — 在数据库层保证数据完整性
- 6 条 Recursive CTE — 覆盖祖先/后代/亲缘路径/族谱树
- 5 类 PPT 要求的 SQL 核心查询 — 各有 Web 展示界面

---

## 二、项目文件结构

```
├── app/                          # Flask 应用
│   ├── __init__.py               # 工厂函数 create_app()
│   ├── config.py                 # DB 连接配置
│   ├── extensions.py             # db, login_manager 扩展
│   ├── models.py                 # 6 个 SQLAlchemy 模型
│   ├── auth/routes.py            # 注册 / 登录 / 退出
│   ├── main/routes.py            # 首页
│   ├── members/routes.py         # 成员 CRUD + 祖先/后代/路径
│   ├── genealogies/routes.py     # 族谱 CRUD + 树形/统计/导出
│   └── templates/                # Jinja2 模板
│       ├── auth/                 # login.html, register.html
│       ├── genealogies/          # list, detail, tree, statistics
│       ├── members/              # form, relations, ancestors, descendants
│       └── relationship/path.html
├── sql/
│   ├── schema.sql                # 建表 + 触发器 + 索引 (DDL)
│   ├── copy_import.sql           # COPY 导入模板
│   └── queries/                  # 9 个独立 SQL 文件
│       ├── 00_validation.sql     # 数据完整性验证
│       ├── 01_ancestors.sql      # 递归 CTE — 向上追溯祖先
│       ├── 02_descendants.sql    # 递归 CTE — 向下追溯后代
│       ├── 03_relationship_path.sql  # BFS 最短亲缘路径
│       ├── 04_four_generation_explain.sql  # EXPLAIN 对比
│       ├── 05_tree_preview.sql   # 族谱树形预览
│       ├── 06_spouse_children.sql     # Task 4.1
│       ├── 07_avg_lifespan_by_generation.sql  # Task 4.3
│       ├── 08_males_over_50_no_spouse.sql     # Task 4.4
│       └── 09_born_before_gen_avg.sql         # Task 4.5
├── scripts/
│   ├── seed_data.py              # 大规模 CSV 数据生成
│   ├── import_csv.py             # COPY 协议批量导入
│   ├── export_branch.py          # 分支递归导出 CSV
│   ├── create_demo_data.py       # 5 代演示族谱（20 人）
│   ├── db_smoke_test.py          # 数据库完整性验收
│   └── explain_performance.py    # EXPLAIN 性能对比报告
├── tests/
│   └── test_database_artifacts.py  # 文档 / 脚本存在性验证
├── docs/
│   ├── data_model.md             # ER 图 + 关系模式 + 范式分析
│   ├── data_pipeline.md          # 数据管道操作指南
│   ├── performance_results.md    # 索引性能对比 (258x)
│   ├── demo_guide.md             # 演示操作指南
│   ├── project_overview.md       # 本文档
│   └── acceptance_guide.md       # 验收演示指导
├── data/generated/               # CSV 中间文件目录
├── .flaskenv                     # Flask 环境变量
├── .env                          # 数据库密码
└── requirements.txt              # Python 依赖
```

---

## 三、对照 PPT 要求逐项说明

### 🟢 一、业务场景

| PPT 要求 | 实现 |
|----------|------|
| 1. 计算机商店 → 族谱管理 | ✅ 完整 CRUD 族谱 + 成员 + 关系 |
| 2. 一对多用户-族谱关系 | ✅ User 1:N Genealogy |
| 3. 多用户协作 multiuser | ✅ genealogy_collaborators (role: viewer/editor) |
| 4. 分支数量统计 | ✅ 完成了所有要求项的数量统计 |
| 5. 年收入 → genealogy详情页统计卡片 | ✅ 总人数 + 性别统计 |
| 6. 贸易细节 → 家庭关系关联 | ✅ 父子 + 婚姻 方向关系 |
| 7. 年终小结 → 树形预览 | ✅ 递归 CTE 12 层缩进树 |
| 8. 新年度利润 → SQL 统计结果 | ✅ 5 查询结果集中展示 |
| 9. 测试并编写结论 → 执行计划 | ✅ EXPLAIN (ANALYZE, BUFFERS) |

> ⚠️ 缺口：Genealogy 缺少 `surname` 姓氏字段（记录为待修）

### 🟢 二.1 简单应用界面

| PPT 要求 | 路由 | 状态 |
|----------|------|:--:|
| 用户注册/登录 | `/register` `/login` `/logout` | ✅ |
| 族谱列表 | `/genealogies` | ✅ |
| 创建族谱 | `/genealogies/new` | ✅ |
| 族谱详情+统计 | `/genealogies/<id>` | ✅ |
| 邀请协作者 | `/genealogies/<id>/invite` | ✅ |
| 成员列表+分页 | `/genealogies/<id>/members` | ✅ |
| 添加/编辑/删除成员 | `/members/<id>/edit` `/delete` | ✅ |
| 编辑关系 | `/members/<id>/relations` | ✅ |
| 祖先/后代查询 | `/members/<id>/ancestors` `/descendants` | ✅ |
| 亲缘路径 | `/relationship/path?a=&b=` | ✅ |
| 树形预览 | `/genealogies/<id>/tree` | ✅ |
| SQL 统计页 | `/genealogies/<id>/statistics` | ✅ |
| CSV 导出 | `/genealogies/<id>/export` | ✅ |

### 🟢 二.2 数据库建模与规范化设计

| PPT 要求 | 实现位置 | 状态 |
|----------|---------|:--:|
| ER 图 (Mermaid) | [data_model.md](docs/data_model.md) | ✅ |
| 6 实体 + 属性 + 联系类型 | [data_model.md](docs/data_model.md) | ✅ |
| 6 张关系表 | [data_model.md](docs/data_model.md) + [schema.sql](sql/schema.sql) | ✅ |
| 范式 ≥ 3NF | [data_model.md](docs/data_model.md) + [project_overview.md](docs/project_overview.md) | ✅ |
| PK + FK 设计 | [schema.sql:L3-L66](sql/schema.sql#L3-L66) | ✅ |
| CHECK 约束 (7 条) | [schema.sql:L39-L41](sql/schema.sql#L39) ... | ✅ |
| "父亲出生年早于子女" | 触发器 `trg_validate_parent_child_relation` | ✅ |

### 🟢 二.3 数据生成与导入导出

| PPT 要求 | 脚本/工具 | 状态 |
|----------|----------|:--:|
| 10 族谱 / 104K 成员 / 30 代 | `seed_data.py` | ✅ |
| 1 族谱 ≥ 50K 成员 | `seed_data.py` (第一个族谱 = 50K) | ✅ |
| 数据多样性（生卒方差、未婚成员） | `seed_data.py` (已引入随机变异) | ✅ |
| 快速导入 | `import_csv.py` (COPY 协议) | ✅ |
| 分支导出 | `export_branch.py` | ✅ |
| 数据验收 | `db_smoke_test.py` (PASS) | ✅ |

### 🟢 二.4 SQL 核心功能

| # | 查询 | SQL 文件 | 单条 SQL | Web 展示 |
|---|------|---------|:--:|:--:|
| 4.1 | 配偶及子女 | [06_spouse_children.sql](sql/queries/06_spouse_children.sql) | ✅ | 统计页 |
| 4.2 | 递归 CTE 祖先 | [01_ancestors.sql](sql/queries/01_ancestors.sql) | ✅ | /ancestors |
| 4.3 | 平均寿命最长代 | [07_avg_lifespan_by_generation.sql](sql/queries/07_avg_lifespan_by_generation.sql) | ✅ | 统计页 |
| 4.4 | >50 无配偶男 | [08_males_over_50_no_spouse.sql](sql/queries/08_males_over_50_no_spouse.sql) | ✅ | 统计页 |
| 4.5 | 出生早于代平均 | [09_born_before_gen_avg.sql](sql/queries/09_born_before_gen_avg.sql) | ✅ | 统计页 |
| 4.6 | EXPLAIN 对比 | [04_four_generation_explain.sql](sql/queries/04_four_generation_explain.sql) | — | [performance_results.md](docs/performance_results.md) |

> 修复后的数据 **全部有结果**，不再出现空表情况。

### 🟢 二.5 物理优化与索引

| PPT 要求 | 实现 | 效果 |
|----------|------|------|
| 姓名模糊查询索引 | GIN trigram `ix_members_name_trgm` | Bitmap Index Scan |
| 父节点→子节点索引 | 复合 B-tree `ix_parent_child_genealogy_parent` | Index Only Scan |
| 四代查询 EXPLAIN 对比 | [performance_results.md](docs/performance_results.md) | **258×** 加速 |
| 额外性能索引 | 配偶/子节点的复合索引各 2 个 | 全链路优化 |

---

## 四、数据库设计

### 4.1 6 张核心表

```
users ───< genealogies ───< genealogy_collaborators
                │
                ├──< members ───< parent_child_relations ─── members (parent)
                │               └──< parent_child_relations ─── members (child)
                │
                └──< marriages ───< members (spouse1/spouse2)
```

### 4.2 CHECK 约束

| 表 | 约束 | 描述 |
|----|------|------|
| genealogy_collaborators | `ck_collaborator_role` | role IN ('viewer','editor') |
| members | `ck_member_gender` | gender IN ('male','female','unknown') |
| members | `ck_member_life_years` | death_year >= birth_year |
| members | `ck_member_generation` | generation_no >= 1 |
| parent_child_relations | `ck_parent_not_child` | parent_id <> child_id |
| parent_child_relations | `ck_parent_role` | role IN ('father','mother') |
| marriages | `ck_marriage_ordered_pair` | spouse1_id < spouse2_id |
| marriages | `ck_marriage_years` | ended_year >= married_year |

### 4.3 触发器（跨行约束）

| 触发器 | 触发时机 | 功能 |
|--------|---------|------|
| `trg_validate_parent_child_relation` | BEFORE INSERT/UPDATE | 父亲出生年 < 子女，同族谱，代数递增 |
| `trg_validate_marriage_relation` | BEFORE INSERT/UPDATE | 配偶同族谱 |
| `trg_validate_member_existing_relations` | AFTER UPDATE | 更新成员不破坏已有关系 |

### 4.4 索引

| 索引 | 类型 | 用途 |
|------|------|------|
| `ix_members_name_trgm` | GIN trigram | 中文姓名模糊搜索 |
| `ix_parent_child_genealogy_parent` | B-tree 复合 | 父→子递归 JOIN |
| `ix_parent_child_genealogy_child` | B-tree 复合 | 子→父递归 JOIN |
| `ix_marriages_genealogy_spouse1` | B-tree 复合 | 配偶查询 |
| `ix_marriages_genealogy_spouse2` | B-tree 复合 | 配偶查询 |

### 4.5 范式

全部 6 张表达到 **3NF**，无传递依赖，无部分函数依赖。
核心设计选择：多值关系（父子/婚姻/协作）全部拆为独立关联表。

---

## 五、Web 路由完整清单（22 条）

### Auth
| 方法 | URL | 功能 |
|------|-----|------|
| GET/POST | `/register` | 用户注册 |
| GET/POST | `/login` | 用户登录 |
| GET | `/logout` | 用户退出 |

### 首页
| 方法 | URL | 功能 |
|------|-----|------|
| GET | `/` | 首页（已登录跳 /genealogies） |

### 族谱
| 方法 | URL | 功能 |
|------|-----|------|
| GET | `/genealogies` | 族谱列表 |
| GET/POST | `/genealogies/new` | 创建族谱 |
| GET | `/genealogies/<id>` | 族谱详情+统计 |
| GET/POST | `/genealogies/<id>/invite` | 邀请协作者 |
| GET | `/genealogies/<id>/members` | 成员列表(模糊搜索+分页) |
| GET | `/genealogies/<id>/tree` | 树形预览 |
| GET | `/genealogies/<id>/statistics` | 5 类 SQL 查询 |
| GET | `/genealogies/<id>/export` | CSV 导出 |

### 成员
| 方法 | URL | 功能 |
|------|-----|------|
| GET/POST | `/genealogies/<id>/members/new` | 添加成员 |
| GET/POST | `/members/<id>/edit` | 编辑成员 |
| POST | `/members/<id>/delete` | 删除成员 |
| GET/POST | `/members/<id>/relations` | 编辑关系 |
| GET | `/members/<id>/ancestors` | 递归CTE祖先 |
| GET | `/members/<id>/descendants` | 递归CTE后代 |

### 关系探索
| 方法 | URL | 功能 |
|------|-----|------|
| GET/POST | `/relationship/path` | 亲缘最短路径 |

---

## 六、典型用户操作流程

```
1. 注册/登录            → /register  → /login
2. 创建族谱              → /genealogies/new
3. 查看族谱              → /genealogies/<id>  (统计卡片)
4. 添加成员              → /genealogies/<id>/members/new
5. 编辑关系              → /members/<id>/relations (添加父母/配偶/子女)
6. 树形预览              → /genealogies/<id>/tree
7. 探索祖先              → /members/<id>/ancestors
8. 探索后代              → /members/<id>/descendants
9. 查找亲缘路径          → /relationship/path?a=1&b=100
10. 查看 SQL 统计        → /genealogies/<id>/statistics (5 类查询结果)
11. 导出成员 CSV          → /genealogies/<id>/export
```

## 七、数据管道操作流程

```bash
# 0. 建库建表
psql -U postgres -c "CREATE DATABASE genealogy_db;"
psql -U postgres -d genealogy_db -f sql/schema.sql

# 1. 生成 CSV
.venv\Scripts\python.exe scripts\seed_data.py --output-dir data\generated

# 2. 导入
.venv\Scripts\python.exe scripts\import_csv.py --input-dir data\generated --truncate

# 3. 验收
.venv\Scripts\python.exe scripts\db_smoke_test.py

# 4. 创建演示数据
.venv\Scripts\python.exe scripts\create_demo_data.py

# 5. 性能报告
.venv\Scripts\python.exe scripts\explain_performance.py

# 6. 分支导出
.venv\Scripts\python.exe scripts\export_branch.py -m <member_id> -o output.csv
```

详见 [data_pipeline.md](docs/data_pipeline.md)。

---

## 八、技术亮点

| 技术 | 应用 |
|------|------|
| `pg_trgm` GIN 索引 | 中文姓名 `ILIKE '%keyword%'` 模糊搜索 |
| `WITH RECURSIVE` + `UNION` | 祖先/后代/亲缘/树形 6 条递归 CTE |
| PostgreSQL `CYCLE` 子句 | 亲缘路径防死循环 |
| COPY 协议 | 104K 成员秒级导入 |
| EXPLAIN (ANALYZE, BUFFERS) | 性能报告 258× 加速证明 |
| CHECK 约束 + 触发器 | 数据库层强制执行业务规则 |
| Composite Index | genealogy_id + parent/child 加速递归 JOIN |

---

## 九、演示账号

| 字段 | 值 |
|------|-----|
| 邮箱 | `demo@example.com` |
| 密码 | `demo123456` |
| 族谱 | "演示族谱" (5 代 20 人) |
| 特点 | 含死亡年份、终身未婚成员、出生年方差 |

大规模数据族谱：`实验族谱 1` ~ `实验族谱 10`（共 104K 成员）。

---

*文档最后更新: 2026-05-12 · 对照 PPT 全部要求逐项确认*