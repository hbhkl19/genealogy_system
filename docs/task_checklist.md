# PPT 任务对照清单

> 最后更新：2026-05-12（数据多样性已修复，全部 SQL 返回有效结果）

---

## 一、业务场景描述

| # | 要求 | 核心代码 | 状态 |
|---|------|---------|:--:|
| 1 | 族谱管理业务场景 | 完整 CRUD 族谱/成员/关系 | ✅ |
| 2 | 一对多用户-族谱关系 | User 1:N Genealogy | ✅ |
| 3 | 多用户协作 | genealogy_collaborators 表 | ✅ |
| 4 | 分支数量统计（gender） | 族谱详情页统计卡片 | ✅ |
| 5 | genealogy 详情页统计 | 总人数/男女人数统计 | ✅ |
| 6 | 家庭关系（父子+婚姻） | parent_child_relations + marriages | ✅ |
| 7 | 树形预览 | 递归 CTE, 12 层, 500 行限制 | ✅ |
| 8 | SQL 统计查询 | 5 类 SQL 集中展示页 | ✅ |
| 9 | EXPLAIN 性能分析 | EXPLAIN (ANALYZE, BUFFERS) | ✅ |

---

## 二.1 简单应用界面 (12 页+)

| # | 要求 | 路由 | 状态 |
|---|------|------|:--:|
| 1 | 用户注册/登录/退出 | `/register` `/login` `/logout` | ✅ |
| 2 | 族谱列表 | `/genealogies` | ✅ |
| 3 | 创建族谱 | `/genealogies/new` | ✅ |
| 4 | 族谱详情+统计卡片 | `/genealogies/<id>` | ✅ |
| 5 | 邀请协作者 | `/genealogies/<id>/invite` | ✅ |
| 6 | 成员列表+模糊搜索+分页 | `/genealogies/<id>/members` | ✅ |
| 7 | 添加/编辑/删除成员 | `/members/<id>/edit` `/delete` | ✅ |
| 8 | 关系管理（父母/配偶/子女） | `/members/<id>/relations` | ✅ |
| 9 | 递归 CTE 祖先查询 | `/members/<id>/ancestors` | ✅ |
| 10 | 递归 CTE 后代查询 | `/members/<id>/descendants` | ✅ |
| 11 | 亲缘路径查询 | `/relationship/path` | ✅ |
| 12 | 树形预览 | `/genealogies/<id>/tree` | ✅ |
| 13 | SQL 统计页 | `/genealogies/<id>/statistics` | ✅ |
| 14 | CSV 导出 | `/genealogies/<id>/export` | ✅ |

> 共 22 条路由，14 个功能页面。

---

## 二.2 数据库建模与规范化设计

| # | 要求 | 证据 | 状态 |
|---|------|------|:--:|
| 1 | ER 图绘制（实体/属性/联系类型） | [data_model.md](docs/data_model.md) Mermaid | ✅ |
| 2 | 关系模式转换（6 表） | [data_model.md](docs/data_model.md#L74-L138) | ✅ |
| 3 | 范式分析 ≥ 3NF | [data_model.md](docs/data_model.md#L127-L138) | ✅ |
| 4 | PK / FK 约束 | [schema.sql](sql/schema.sql#L3-L66) | ✅ |
| 5 | CHECK 约束（8 条） | [models.py](app/models.py) __table_args__ | ✅ |
| 6 | "父亲出生年早于子女" | 触发器 `trg_validate_parent_child_relation` | ✅ |
| 7 | 跨行触发器（5 个） | [schema.sql](sql/schema.sql#L76-L189) | ✅ |

---

## 二.3 数据生成与导入导出

| # | 要求 | 实现 | 状态 |
|---|------|------|:--:|
| 1 | 10 族谱 | seed_data.py 默认配置 | ✅ |
| 2 | 104,000 成员 | 50K + 6K×9 = 104K | ✅ |
| 3 | 1 族谱 ≥ 50,000 成员 | 实验族谱 1 = 50,000 | ✅ |
| 4 | 30 代 | generations=30 | ✅ |
| 5 | 数据多样性（生卒方差） | birth ±5 年, lifespan 55~92 | ✅ |
| 6 | 数据多样性（未婚成员） | 8% 未婚率 | ✅ |
| 7 | 快速导入 | COPY 协议 (import_csv.py) | ✅ |
| 8 | 分支导出 | export_branch.py | ✅ |
| 9 | 数据验收 | db_smoke_test.py (PASS) | ✅ |

---

## 二.4 SQL 核心功能编写 (DML & Query)

| # | 要求 | SQL 文件 | 数据库验证 | Web 展示 |
|---|------|---------|:--:|:--:|
| 4.1 | 配偶及子女（单 SQL） | [06_spouse_children.sql](sql/queries/06_spouse_children.sql) | ✅ 2子+1配偶 | ✅ 统计页 |
| 4.2 | 递归 CTE 祖先追溯 | [01_ancestors.sql](sql/queries/01_ancestors.sql) | ✅ 30位祖先 | ✅ /ancestors |
| 4.3 | 平均寿命最长一代 | [07_avg_lifespan_by_generation.sql](sql/queries/07_avg_lifespan_by_generation.sql) | ✅ gen=28, 74.5岁 | ✅ 统计页 |
| 4.4 | >50 岁无配偶男性 | [08_males_over_50_no_spouse.sql](sql/queries/08_males_over_50_no_spouse.sql) | ✅ 多人结果 | ✅ 统计页 |
| 4.5 | 出生年份早于代平均 | [09_born_before_gen_avg.sql](sql/queries/09_born_before_gen_avg.sql) | ✅ 有偏差结果 | ✅ 统计页 |
| 4.6 | EXPLAIN 性能对比 | [04_four_generation_explain.sql](sql/queries/04_four_generation_explain.sql) | — | ✅ 文档 |

> 修复前 4.3/4.4/4.5 因数据无方差返回空表，现已全部修复。

---

## 二.5 物理优化与索引设计

| # | 要求 | 实现 | 效果 |
|---|------|------|------|
| 1 | 模糊查询索引 | GIN trigram `ix_members_name_trgm` | Bitmap Index Scan |
| 2 | 父→子查询索引 | 复合 B-tree `ix_parent_child_genealogy_parent` | Index Only Scan |
| 3 | 四代查询 EXPLAIN（无索引） | Seq Scan 全表 91.65 ms | — |
| 4 | 四代查询 EXPLAIN（有索引） | Index Only Scan 0.36 ms | **258×** |
| 5 | 性能报告 | [performance_results.md](docs/performance_results.md) | 完整对比表格 |

---

## 二.6 验收材料

| # | 要求 | 文档 | 状态 |
|---|------|------|:--:|
| 1 | 项目完整文档 | [project_overview.md](docs/project_overview.md) | ✅ |
| 2 | 验收演示指导 | [acceptance_guide.md](docs/acceptance_guide.md) | ✅ |
| 3 | pg_dump 数据库备份 | `data/backup/genealogy_backup_*.sql` | ⬜ 待执行 |
| 4 | 性能测试脚本 | `explain_performance.py` | ✅ |
| 5 | 测试用例 | `tests/test_database_artifacts.py` | ✅ |
| 6 | 报告大纲 | `docs/report_outline.md` | ⬜ 待创建 |

---

## 📋 汇总

| 板块 | 条目 | 完成 | 待修 |
|------|:--:|:--:|:--:|
| 一、业务场景 | 9 | 9 | 0 |
| 二.1 应用界面 | 14 | 14 | 0 |
| 二.2 数据库建模 | 7 | 7 | 0 |
| 二.3 数据生成 | 9 | 9 | 0 |
| 二.4 SQL 核心 | 6 | 6 | 0 |
| 二.5 物理优化 | 5 | 5 | 0 |
| 二.6 验收材料 | 6 | 4 | 2 |

### 待完成任务

| 任务 | 优先级 | 说明 |
|------|:--:|------|
| pg_dump 备份 | 🔴 | `pg_dump -U postgres genealogy_db > backup.sql` |
| report_outline.md | 🟡 | 课程报告大纲模板 |
| Genealogy 加 surname 字段 | 🟡 | PPT 要求中的 "姓氏" 字段缺口 |