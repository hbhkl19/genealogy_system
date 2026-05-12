# 更新日志

> 项目：寻根溯源族谱管理系统  
> 日期范围：2026-05-11 — 2026-05-12  
> 累计变更：44 文件, +3300/-97 行, 新建 27 文件

---

## 🔴 核心 Bug 修复

### 递归 CTE 性能优化（3 轮迭代）

**问题**: `export_branch.py` 执行 10+ 分钟未完成，最终因 DiskFull 报错。

**根因**: DAG 结构中成员可通过父亲和母亲双路径到达 → `UNION ALL` 不加去重 → 5 代产生 21 亿次迭代而非 3.3 万次。

**修复轮次**:

| 轮次 | 尝试 | 结果 | 文件 |
|:--:|------|------|------|
| 1 | `path NOT LIKE '%...,id,...,%'` 字符串判断去重 | O(n²) 性能，仍很慢 | `export_branch.py` |
| 2 | PostgreSQL 原生 `CYCLE` 子句 | DiskFull — CYCLE 维护巨大路径数组 | `export_branch.py` |
| 3 | **`UNION ALL` → `UNION`**（一字之改） | 秒级完成 | `export_branch.py` |

**波及修复**: 同步优化全部 6 条递归 CTE：

| 查询 | 文件 | 修改 |
|------|------|------|
| 后代追溯 | `members/routes.py` | `UNION ALL + path NOT LIKE` → `UNION` |
| 祖先追溯 | `members/routes.py`, `01_ancestors.sql` | 同上 |
| 亲缘路径 | `members/routes.py`, `03_relationship_path.sql` | `path NOT LIKE` → `CYCLE` 子句 |
| 族谱树 | `genealogies/routes.py`, `05_tree_preview.sql` | 去掉 `path NOT LIKE` |
| 四代 EXPLAIN | `04_four_generation_explain.sql` | `UNION ALL` → `UNION` |
| 后代查询 SQL | `02_descendants.sql` | `UNION ALL + path NOT LIKE` → `UNION` |

### `create_demo_data.py` 连接失败

**问题**: 执行报错 `password authentication failed`。

**根因**: `load_dotenv()` 在 `from app.config import Config` 之后执行，Config 读到的是默认密码 `123456` 而非 `.env` 中的真实密码。

**修复**: 将 `load_dotenv()` 移到 `app/__init__.py` 模块顶部，在所有 import 之前执行。

### CSV 导出修复（3 轮迭代）

**轮次 1 — 性能卡顿**: 点击导出后浏览器长时间无响应。

- **根因**: `Member.query.filter_by(...).all()` 把全部成员(50K)加载为 ORM 对象，然后 `"\n".join(...)` 拼接巨型字符串，数分钟无法完成。
- **修复**: 原始 SQL 分块流式导出 — 每批 2000 行，`yield` 逐块返回，内存占用恒定，50K 成员秒级响应。

**轮次 2 — UnicodeEncodeError**: HTTP 200 但实际报错 `'latin-1' codec can't encode characters`。

- **根因**: HTTP `Content-Disposition` 头只支持 ASCII/latin-1，中文字段名 `演示族谱_members.csv` 无法编码。
- **修复**: `filename` → `filename*=UTF-8''{url_encoded}` (RFC 5987 标准)。

**轮次 3 — RuntimeError**: `Working outside of application context`。

- **根因**: `generate()` 是惰性生成器，在 Flask 路由函数返回后（应用上下文已退出）才开始执行，此时 `db.session` 无法找到上下文。
- **修复**: `app = current_app._get_current_object()` 在路由内捕获真实 app → 生成器内 `with app.app_context():` 包裹所有 DB 操作。

### 演示族谱家谱逻辑错误

**问题**: 赵一鸣(♂)和赵雨晴(♀)是兄妹，却被设为"赵小宇"的父母。

**修复**: 拆分赵一鸣的配偶为独立人物"秦晓燕♀1996"；新增"孙婷婷♀1999"为赵一飞之妻。

---

## 🔥 数据生成重构

### 引入数据多样性

| 参数 | 旧值 | 新值 |
|------|------|------|
| 出生年份 | `1930 + (gen-1)*25`（全代统一） | `base + random(-5, +5)` |
| 死亡年龄 | 固定 78 岁 | `random(55, 92)` |
| 未婚比例 | 0% | **8%** |
| 第一代婚姻 | 可能未婚空悬 | **强制配对** |
| 姓名格式 | `G01-02-00001-周伟` | `G01-G02-0001 周伟` |
| 传记 | 固定模板 | 含生卒年信息 |

**效果**: 修复前 Task 4.3/4.4/4.5 因数据无方差返回空表；修复后全部有结果。

### 演示数据扩充

| 指标 | 旧 | 新 |
|------|----|----|
| 代数 | 3 代 | **5 代** |
| 成员数 | 6 人 | **20 人** |
| 死亡年份 | 全部 NULL | 世代 1-3 有 death_year |
| 未婚成员 | 无 | 赵德广♂1925-2015 终身未婚 |
| 出生年方差 | 无 | 代内 2-5 年差异 |

---

## 📄 新建文件一览

### SQL 查询（6 个）
| 文件 | 对应 PPT |
|------|---------|
| `sql/queries/06_spouse_children.sql` | Task 4.1 配偶及子女 |
| `sql/queries/07_avg_lifespan_by_generation.sql` | Task 4.3 平均寿命 |
| `sql/queries/08_males_over_50_no_spouse.sql` | Task 4.4 无配偶男性 |
| `sql/queries/09_born_before_gen_avg.sql` | Task 4.5 早于代平均 |
| `sql/queries/05_tree_preview.sql` | 族谱树形预览 |
| `sql/queries/00_validation.sql` | 数据完整性验证 |

### Web 模板（1 个）
| 文件 | 说明 |
|------|------|
| `app/templates/genealogies/statistics.html` | 5 类 SQL 查询结果集中展示 |

### 脚本（3 个）
| 文件 | 说明 |
|------|------|
| `scripts/import_csv.py` | PostgreSQL COPY 协议批量导入 |
| `scripts/db_smoke_test.py` | 数据库完整性验收 |
| `scripts/explain_performance.py` | EXPLAIN 对比 + Markdown 报告生成 |

### 测试（2 个）
| 文件 | 说明 |
|------|------|
| `tests/test_database_artifacts.py` | 文档/脚本/迁移存在性验证 |
| `tests/test_data_generation.py` | 数据生成算法验证 |

### 迁移（3 个）
| 文件 | 说明 |
|------|------|
| `migrations/versions/e1b4cdee1b60_initial_schema.py` | 初始建表 |
| `migrations/versions/...add_relation_constraints_and_indexes.py` | FK/UNIQUE/索引 |
| `migrations/versions/8ef1ddc6ab24_*_triggers.py` | 3 函数 + 3 触发器 |

### 文档（7 个）
| 文件 | 说明 |
|------|------|
| `docs/data_model.md` | ER 图 + 关系模式 + 范式分析 |
| `docs/data_pipeline.md` | 数据生成→导入→导出全流程 |
| `docs/performance_results.md` | 258× EXPLAIN 对比 |
| `docs/demo_guide.md` | 演示操作指南 |
| `docs/project_overview.md` | 对照 PPT 项目完整文档 (~330行) |
| `docs/task_checklist.md` | PPT 全部要求逐条对照 |
| `docs/acceptance_guide.md` | 15 分钟验收路径 + 话术 |
| `docs/CHANGELOG.md` | 本文档 |

---

## 🚀 亲缘链路查询性能优化（2026-05-12）

### 问题诊断

50000 人数据集 (239,506 条边) 上 `/relationship/path` 接口耗时 **126 秒**，远超可用标准。

**根因分析**（详见 `profile_output.txt` EXPLAIN ANALYZE 输出）：

| 瓶颈 | 位置 | 严重度 |
|------|------|:--:|
| `UNION ALL` 路径爆炸 — CTE 枚举所有路径而非去重节点 | `routes.py:_bfs_reachable()` | **P0 致命** |
| `CYCLE` 子句磁盘 I/O — 600 万行 cycle_path 数组写入 ~10GB temp | `routes.py:_bfs_reachable()` | **P0 致命** |
| Phase 2 逐条查询 — 每步 1 次 DB 往返，标注关系又 N 次 | `routes.py:_lookup_relations_batch()` | P1 严重 |

**实测数据**（优化前 depth≤12）：
```
walk CTE 行数:      5,954,424 rows  (应为 ~15,000)
磁盘临时 I/O:       temp written 1,387,007 blocks ≈ 10.6 GB
执行时间:           126,865 ms ≈ 126 秒
```

### 三层优化方案

#### 方案一：`UNION ALL` → `UNION`（1 个关键词）

- **文件**: `app/members/routes.py` — `_bfs_reachable()` 函数
- **原理**: `UNION` 在每层递归中对 `(member_id, depth)` 去重 → 每层每节点仅保留 1 行
- **效果**: walk CTE 行数 600 万 → **2.6 万**（230× 减少），CYCLE 磁盘 I/O 完全消除

#### 方案二：批量合并关系标注查询

- **文件**: `app/members/routes.py` — `_lookup_relations_batch()` 函数
- **原理**: 将 O(n) 次逐条 `CASE WHEN EXISTS` 查询合并为 1 次 `VALUES` 批量查询
- **效果**: N 次数据库往返 → **1 次**，消除 ~90% Phase 2 延迟

#### 方案三：PL/pgSQL 迭代 BFS 存储函数

- **文件**: `sql/functions/bfs_reachable.sql`（新建）
- **原理**: `CROSS JOIN LATERAL` 索引点查 + temp table + `ON CONFLICT DO NOTHING` 零成本去重
- **对比**: 深度 ≥8 时自动启用；深度 ≤6 时回退 UNION CTE（已足够快）

### 性能对比

| 指标 | 优化前 | 优化后 | 加速比 |
|------|--------|--------|:--:|
| 单 BFS (depth=12) | 126,000ms | **100ms** | **~1200×** |
| 单 BFS (depth=15) | 无法完成 | **200ms** | ∞ |
| 完整路径查询 (2 hops) | ~500ms | **330ms** | 1.5× |
| 完整路径查询 (4 hops) | ~3000ms | **330~930ms** | 3~9× |
| 完整路径查询 (8 hops) | ~60000ms | **650~1640ms** | **~40~90×** |
| 磁盘临时 I/O | 10.6 GB | **0** | 消除 |
| walk CTE 行数 | 600 万 | **2.6 万** | 230× |

**50000 人数据集 11 场景实测**：
```
最慢查询:  1,638 ms  (1.6 秒)
平均耗时:    596 ms
所有查询均在 2 秒内完成 ← 满足 "数秒内响应" 需求
```

### 新增文件

| 文件 | 说明 |
|------|------|
| `sql/functions/bfs_reachable.sql` | PL/pgSQL 迭代 BFS 函数 |
| `scripts/test_optimized_path.py` | 亲缘路径综合性能测试脚本 |
| `scripts/test_final_path.py` | 路径查询功能验证脚本 |

### 修改文件

| 文件 | 修改量 | 关键变更 |
|------|:--:|------|
| `app/members/routes.py` | +18/-13 | `_bfs_reachable`: UNION ALL→UNION + 函数回退; `_lookup_relations_batch`: VALUES 批量查询 |

---

## 📝 重要修改文件

| 文件 | 修改量 | 关键变更 |
|------|:--:|------|
| `app/members/routes.py` | +327 | 递归 CTE 优化、祖先/后代/路径路由、亲缘链路三层优化 |
| `scripts/seed_data.py` | +263 | 数据多样性重构 |
| `app/models.py` | +48 | CHECK 约束 + 索引定义 |
| `sql/schema.sql` | +124 | 完整 DDL + 触发器 + 索引 |
| `app/genealogies/routes.py` | +50 | 统计页路由 + CSV 流式导出 |
| `scripts/export_branch.py` | +112 | UNION 递归 CTE + CLI |
| `app/static/css/app.css` | +55 | 统计页样式 |
| `tests/test_app.py` | +157 | CRUD 规则验证 + 路由加载测试 |

---

## 📊 最终验收状态

```
db_smoke_test:            PASS  (10族谱/104K人/50Kmax/30代/0孤立)
pytest (10 tests):        PASS
SQL 查询 4.1-4.5:         全部返回有效结果
Web 路由 (22条):          全部可用
索引:                     5 个 (GIN trigram + 4×B-tree 复合)
触发器:                   3 个 (父子/婚姻/成员更新)
存储函数:                 4 个 (3 约束验证 + 1 BFS)
EXPLAIN 加速:             258× (91.65ms → 0.36ms)
亲缘链路查询 (50K 人):    0.3~1.6 秒, ~40~1200× 加速
```