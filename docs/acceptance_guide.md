# 寻根溯源族谱管理系统 — 验收演示指导

> 本文档提供完整的分步验收流程，覆盖 PPT 全部要求。
> 演示账号：`demo@example.com` / `demo123456`

---

## 零、环境准备（演示前 5 分钟）

```bash
cd d:\上课\大三下\数据库\genealogy_system

# 1. 确认数据库连接正常
.venv\Scripts\python.exe -c "from app import create_app; app=create_app(); print('OK')"

# 2. 确认验收测试通过
.venv\Scripts\python.exe scripts\db_smoke_test.py
# 预期: large_dataset_acceptance: PASS

# 3. 启动 Flask
.venv\Scripts\python.exe -m flask run
# 浏览器打开 http://127.0.0.1:5000
```

---

## 一、验收流程总览（15 分钟演示路径）

```
┌──────────────────────────────────────────────────┐
│ 1. 用户系统 (2min)                                │
│    → 登录 demo@example.com                       │
│    → 展示注册/登录/退出功能                        │
├──────────────────────────────────────────────────┤
│ 2. 演示族谱 (3min)                                │
│    → 进入"演示族谱" (5代20人)                     │
│    → 查看成员列表 → 泛搜索成员姓名                 │
│    → 查看树形预览                                 │
├──────────────────────────────────────────────────┤
│ 3. 核心关系查询 (4min)                            │
│    → 祖先追溯 (选第5代成员 → 回溯4层,30位祖先)     │
│    → 后代追溯 (选第1代 → 向下3层)                 │
│    → 亲缘路径 (选两个远亲 → BFS最短路径)          │
├──────────────────────────────────────────────────┤
│ 4. SQL 统计查询 (3min)                            │
│    → /statistics 统计页：5 个查询表格             │
│    → 4.3 平均寿命最长一代                         │
│    → 4.4 >50无配偶男性 (赵德广)                   │
│    → 4.5 出生早于代平均                           │
├──────────────────────────────────────────────────┤
│ 5. 大规模数据 (2min)                              │
│    → 切换到"实验族谱 1" (50,000人,30代)           │
│    → 演示模糊搜索/树形/统计 均秒级响应             │
├──────────────────────────────────────────────────┤
│ 6. 性能对比 (1min)                                │
│    → 展示 performance_results.md                 │
│    → 258× 加速证明                                │
└──────────────────────────────────────────────────┘
```

---

## 二、分步详细操作

### 步骤 1：用户系统验证 (2 分钟)

| 操作 | 路径 | 验收点 |
|------|------|--------|
| 打开首页 | `http://127.0.0.1:5000` | ✅ 显示"注册"/"登录"按钮 |
| 登录 | 用 `demo@example.com` / `demo123456` | ✅ 跳转至族谱列表 |
| （可选演示注册） | `/register` 注册新用户 | ✅ 密码经 werkzeug 哈希加密 |
| （可选退出） | 导航栏"退出" | ✅ 清除 session |

---

### 步骤 2：演示族谱 — 小数据集 (3 分钟)

```
演示族谱结构（5代20人）：

赵德厚♂1920-2005 ═ 陈秀英♀1923-2008              赵德广♂1925-2015 (终身未婚)
  ├─ 赵明礼♂1945-2020 ═ 王兰芳♀1948-2018
  │    └─ 赵建国♂1970 ═ 周丽华♀1972
  │         ├─ 赵一鸣♂1995 ═ 秦晓燕♀1996
  │         │    ├─ 赵小宇♂2020
  │         │    └─ 赵小悦♀2022
  │         └─ 赵雨晴♀1998
  └─ 赵明义♂1950-2019 ═ 李桂花♀1953-2023
       └─ 赵建军♂1973-2024 ═ 刘雪梅♀1976
            ├─ 赵一飞♂1997 ═ 孙婷婷♀1999
            │    └─ 赵小航♂2021
            └─ 赵雨欣♀2000
```

#### 操作流程

| 步骤 | 操作 | 验收点 |
|------|------|--------|
| 2.1 | 族谱列表页 → 点击"演示族谱" | ✅ 族谱详情页：统计卡片（20人，9男11女） |
| 2.2 | 点击"成员列表" | ✅ 分页显示，搜索框可用 |
| 2.3 | 搜索框输入"赵" | ✅ 模糊搜索返回匹配成员 |
| 2.4 | 点击"树形预览" | ✅ 递归缩进树，根节点开始 |
| 2.5 | 点"赵建军"进入编辑 | ✅ 可看到 death_year=2024 等完整信息 |

---

### 步骤 3：核心关系查询验证 (4 分钟)

#### 3.1 祖先查询 (**PPT 4.2**)

| 操作 | 验收点 |
|------|--------|
| 进入成员"赵小宇"详情页 | — |
| 点击"查看祖先" | ✅ Recursive CTE 逐层向上追溯 |
| 检查结果 | ✅ 深度1=赵一鸣/秦晓燕(父母) → 深度2=赵建国/周丽华(祖) → 深度3=赵明礼/王兰芳(曾祖) → 深度4=赵德厚/陈秀英(高祖) |
| **强调** | ✅ **单条 SQL**，`WITH RECURSIVE` + `UNION` 实现 |

**对应 SQL**: [01_ancestors.sql](sql/queries/01_ancestors.sql)

#### 3.2 后代查询

| 操作 | 验收点 |
|------|--------|
| 进入成员"赵德厚"详情页 | — |
| 点击"查看后代" | ✅ 递归向下，显示 3 代后代 |
| 检查结果 | ✅ 赵明礼/赵明义(子女) → 赵建国/赵建军(孙) → 赵一鸣/赵一飞/赵雨晴/赵雨欣(曾孙) |

**对应 SQL**: [02_descendants.sql](sql/queries/02_descendants.sql)

#### 3.3 亲缘路径查询 (**PPT 关系图探索**)

| 操作 | 验收点 |
|------|--------|
| 访问 `/relationship/path` | — |
| 选择族谱"演示族谱"，起始成员=赵德厚(根)，目标成员=赵小航(远孙) | ✅ 通过亲子关系向下追踪 |
| **强调** | ✅ **BFS 最短路径**，`edges` CTE 构建双向关系图，`walk` CTE + CYCLE 子句防循环 |

**对应 SQL**: [03_relationship_path.sql](sql/queries/03_relationship_path.sql)

---

### 步骤 4：SQL 统计查询验证 (3 分钟)

访问 `http://127.0.0.1:5000/genealogies/{演示族谱ID}/statistics`

> 演示族谱的 ID 可以在 `/genealogies` 列表页看到

#### 4.1 配偶及子女查询 (**PPT 4.1**)

| 查询 | 输入 member_id=赵德厚的ID | 
|------|------|
| 结果 | ✅ 配偶=陈秀英 + 子女=赵明礼, 赵明义 |
| **关键** | ✅ **单条 SQL**，`UNION ALL` 合并配偶/子女两路 |

**对应 SQL**: [06_spouse_children.sql](sql/queries/06_spouse_children.sql)

#### 4.3 平均寿命最长一代 (**PPT 4.3**)

| 查询 | 结果 |
|------|------|
| `GROUP BY generation_no` 统计 | ✅ 展示平均寿命最高的一代及其平均值 |
| **关键** | ✅ 单条 SQL，CTE + AVG + GROUP BY + ORDER BY + LIMIT 1 |

**对应 SQL**: [07_avg_lifespan_by_generation.sql](sql/queries/07_avg_lifespan_by_generation.sql)

#### 4.4 超过 50 岁无配偶男性 (**PPT 4.4**)

| 查询 | 结果 |
|------|------|
| 演示数据中的特例 | ✅ **赵德广** ♂1925-2015, 年龄 90, **终身未婚** |
| **关键** | ✅ `NOT EXISTS` 子查询确保无配偶 |

**对应 SQL**: [08_males_over_50_no_spouse.sql](sql/queries/08_males_over_50_no_spouse.sql)

#### 4.5 出生年份早于代平均 (**PPT 4.5**)

| 查询 | 结果 |
|------|------|
| `WITH CTE 算代平均 → JOIN 筛选` | ✅ 显示出生年 < 该代平均的成员及偏差值 |
| **关键** | ✅ CTE 分两步完成：先算平均再筛选 |

**对应 SQL**: [09_born_before_gen_avg.sql](sql/queries/09_born_before_gen_avg.sql)

> ⚠️ 注意：演示族谱只有 20 人，某些代可能方差小。大规模族谱中的结果更明显。

---

### 步骤 5：大规模数据验证 (2 分钟)

在 `/genealogies` 列表页，切换到"实验族谱 1"（50,000 人）。

| 操作 | 验收点 |
|------|--------|
| 族谱详情页 | ✅ 统计卡片：总人数 50,000，男女比例 |
| 成员列表 | ✅ 分页展示，模糊搜索秒级响应 |
| 搜索"国" | ✅ trigram GIN 索引加速 |
| 树形预览 | ✅ 30 代树，500 行限制，秒级渲染 |
| 统计页 | ✅ **5 类 SQL 全部返回有意义的非空结果** |
| 祖先查询（选深层成员） | ✅ 向上 4+ 层追溯 |
| 亲缘路径（两个任意成员） | ✅ BFS 最短路径 |

---

### 步骤 6：性能对比展示 (1 分钟)

#### 方式一：展示文档

打开 [performance_results.md](docs/performance_results.md)

```
| 场景 | Execution Time |
|------|:---:|
| 无索引 (Seq Scan) | 91.65 ms |
| 有索引 (Index Scan) | 0.36 ms |
| 加速倍数 | **258×** |
```

#### 方式二：现场运行脚本

```bash
.venv\Scripts\python.exe scripts\explain_performance.py
# 自动输出有无索引的 EXPLAIN 对比
```

> **强调**：
> - ✅ 姓名模糊查询：GIN trigram 索引（`pg_trgm` 扩展）
> - ✅ 父节点查子节点：复合 B-tree 索引 `(genealogy_id, parent_member_id)`
> - ✅ 四代查询 258× 加速，缓冲区减少 51×

---

## 三、验收员独立验证清单

### 命令行验证（不需要启动 Web）

```bash
# 数据库完整性
.venv\Scripts\python.exe scripts\db_smoke_test.py
# 预期: large_dataset_acceptance: PASS

# 触发器测试（父亲出生年 < 子女出生年）
psql -U postgres -d genealogy_db << 'EOF'
-- 以下 INSERT 会触发 EXCEPTION 而失败（证明触发器生效）
-- 预期报错: parent birth year must be earlier than child birth year
EOF

# 索引存在性
.venv\Scripts\python.exe -m pytest tests/test_database_artifacts.py -v
# 预期: 5 passed
```

### Web 界面验证

| 检查项 | 操作 | 预期 |
|--------|------|------|
| 登录 | `demo@example.com` / `demo123456` | 跳转族谱列表 |
| 功能页面数 | 统计所有功能页面 | **≥14 个** |
| 示范族谱 | 点击"演示族谱" | 20 人 |
| 树形预览 | 演示族谱 → 树形 | 递归缩进树 |
| 祖先 → 可交互 | 赵小宇 → 祖先 | 4 层回溯 |
| 后代 → 可交互 | 赵德厚 → 后代 | 3 层展开 |
| 亲缘路径 | 赵德厚 → 赵小航 | 最短路径 + 关系标签 |
| SQL 统计页 | 统计 | **5 表格均非空** |
| 大规模数据 | 实验族谱 1 | 50K 人 |
| 模糊搜索 | 实验族谱 1 → 成员 → 搜索 | 秒级响应 |
| CSV 导出 | 实验族谱 1 → 导出 | CSV 文件下载 |

---

## 四、演示话术参考

### 开场（项目定位）
> "我们设计的是一个**在线族谱管理系统**。传统纸质族谱维护困难、不便于协作，
> 我们将这个业务流程数字化，用 Flask + PostgreSQL 实现。"

### 数据库设计亮点
> "我们的数据库设计满足 **3NF**，6 张核心表，8 条 CHECK 约束，
> 还用了 **3 个触发器**实现跨行业务规则——比如'父亲的出生年份必须早于子女'，
> 这在 PPT 要求中明确提到，我们通过 `trg_validate_parent_child_relation` 触发器
> 在数据库层面强制执行。"

### SQL 核心查询
> "PPT 要求的 5 类 SQL 全部用**单条 SQL**实现，页面 `/statistics` 集中展示。
> 其中 4.2 的递归祖先追溯使用了 `WITH RECURSIVE` CTE，
> 5 代成员可以向上追溯到完整的 4 层二叉祖先树。"

### 性能优化
> "我们设计了 GIN trigram 索引（`pg_trgm` 扩展）用于姓名模糊搜索，
> 复合 B-tree 索引用于父子节点查询。
> **EXPLAIN 对比显示 258 倍加速**，从全表扫描 91ms 降到索引扫描 0.36ms。
> 具体执行计划都在 [performance_results.md](docs/performance_results.md)。"

### 数据规模
> "我们生成了 10 个族谱、共 104,000 成员、30 代深度的数据集，
> 其中最大的族谱包含 50,000 人。
> 使用 PostgreSQL COPY 协议，全部导入只需几秒。
> 所有成员的生卒年有随机变异，部分成员未婚，保证所有 SQL 统计查询都返回有意义的结果。"

---

## 五、常见问题预案

| 问题 | 回答 |
|------|------|
| "为什么树形预览只有 500 行？" | "递归 CTE+缩进渲染对浏览器有性能压力，500 行/12 层作为安全上限。技术上无限制。" |
| "模糊搜索为什么能秒级？" | "因为我们用了 GIN trigram 索引 + pg_trgm 扩展，`ILIKE '%张%'` 走 Bitmap Index Scan。" |
| "祖先法改了为什么会变慢？" | "如果用 UNION ALL 不加去重，在 DAG 结构下会出现指数路径爆炸。我们用了 UNION 自动去重。" |
| "大型数据怎么生成的？" | "seed_data.py 用 Faker 中文库 + 二进制配对算法逐代生成，纯内存+流式CSV写入，无中间瓶颈。" |

---

## 六、快速命令速查

```bash
# 环境
.venv\Scripts\activate

# 验收
.venv\Scripts\python.exe scripts\db_smoke_test.py
.venv\Scripts\python.exe -m pytest tests\ -v

# 启动
.venv\Scripts\python.exe -m flask run

# 数据重建（如需）
.venv\Scripts\python.exe scripts\seed_data.py --output-dir data\generated
.venv\Scripts\python.exe scripts\import_csv.py --input-dir data\generated --truncate
.venv\Scripts\python.exe scripts\create_demo_data.py

# 性能报告
.venv\Scripts\python.exe scripts\explain_performance.py

# 分支导出
.venv\Scripts\python.exe scripts\export_branch.py -m <ID> -o export.csv

# 数据库备份
pg_dump -U postgres genealogy_db > backup.sql
```

---

*验收指导文档 · 最后更新 2026-05-12*