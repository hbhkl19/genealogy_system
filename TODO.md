# TODO

## 2026-05-18 树形预览与祖先查询修正记录

- `[x]` 图形树按成员 ID 定位改为中心布局：目标成员居中，左侧逐代懒加载父母/祖先，右侧逐代懒加载子女/后代。
- `[x]` 图形树定位会清空旧画布，避免根节点模式和中心定位模式混在一起造成布局混乱。
- `[x]` 本轮验证：`pytest` 14 passed，`compileall app scripts migrations` 通过，`flask --app app routes` 通过。
- `[x]` 树形预览缩进树增加“回到初始预览”按钮，按成员 ID 定位后可以重新加载原始根成员预览。
- `[x]` 修正缩进树“展开到第 2/3/5 代”：现在按当前视图根节点计算，定位到某个成员后也能继续批量展开其分支。
- `[x]` 按用户反馈撤回独立的族谱级“祖先查询”入口，继续使用成员列表每行的“祖先”按钮进入 `/members/<id>/ancestors`。
- `[x]` 成员列表与搜索增加“成员 ID”精确搜索，便于快速定位成员后进入祖先查询。
- `[x]` 验证结果：`pytest` 14 passed，`compileall app scripts migrations` 通过，`flask --app app routes` 确认已移除 `/genealogies/<id>/ancestors`。

## 2026-05-17 最终验收前功能补充记录

- `[x]` 祖先查询改为懒加载：`/members/<id>/ancestors` 首屏只显示当前成员和直接父母，点击父母旁 `[+]` 再请求上一代。
- `[x]` 新增祖先懒加载接口：`/members/<id>/ancestor-parents`，只返回指定成员的直接父母和 `has_parents` 标记。
- `[x]` 成员列表增加分页：默认每页 50 条，可切换 75 条，并保留姓名搜索条件和页码跳转。
- `[x]` 缩进树增加按成员 ID 定位：`/genealogies/<id>/tree/member/<member_id>` 返回局部根节点，前端可继续逐层展开后代。
- `[x]` 缩进树 JSON 查询改为 SQLAlchemy 版本，避免测试环境和 PostgreSQL 方言差异影响验收。
- `[x]` 数据生成脚本增加孤立成员补边逻辑，保证生成 CSV 中每个成员至少存在一条血缘或婚姻边。
- `[x]` 验证结果：`pytest` 14 passed，`compileall app scripts migrations` 通过，`flask --app app routes` 可列出新增接口。

本文件用于记录“寻根溯源”族谱管理系统的关键开发步骤、验收状态和每次开发进展。每次继续开发前先看本文件，开发后更新状态。

## 状态标记

- `[ ]` 未开始
- `[~]` 进行中
- `[x]` 已完成
- `[!]` 需要注意或人工补充

## 当前里程碑

### M0 项目基础与环境

- `[x]` 初始化 Git 仓库和项目目录。
- `[x]` 建立 Flask 应用工厂、配置分层、数据库扩展和蓝图结构。
- `[x]` 配置 VSCode 推荐扩展、调试、任务和 pytest。
- `[x]` 编写 README、项目结构说明和启动步骤。
- `[x]` 接入 Flask-Migrate，当前 PostgreSQL 迁移版本为 `a7c9d2f4b601`。

### M1 用户与权限

- `[x]` 用户注册、登录、退出、密码哈希和登录拦截。
- `[x]` 用户只能看到自己创建或受邀参与的族谱。
- `[x]` 协作者表保存 `viewer/editor` 角色。
- `[!]` 可加分：进一步严格区分 `viewer` 只读、`editor` 可编辑。

### M2 族谱管理与协作

- `[x]` 族谱创建、列表、详情和 Dashboard。
- `[x]` 族谱基本信息包含谱名、姓氏、修谱年份、简介、创建用户。
- `[x]` 族谱编辑和删除。
- `[x]` 族谱创建者可邀请协作者。
- `[x]` Dashboard 显示总人数和男女数量。

### M3 成员管理与关系维护

- `[x]` 成员新增、编辑、删除。
- `[x]` 成员列表和姓名模糊搜索入口。
- `[x]` 父亲、母亲、子女关系维护。
- `[x]` 婚姻关系维护。
- `[x]` 关系合法性校验：不能自关联、同一子女最多一父一母、父母出生年早于子女、父母代数小于子女、婚姻有序去重。

### M4 递归查询与树形展示

- `[x]` 树形预览使用递归 CTE，以缩进层级列表展示，限制深度和行数保证大数据演示稳定。
- `[x]` 祖先查询：输入成员 ID，追溯父辈以上祖先。
- `[x]` 后代查询：输入成员 ID，查询直系后代。
- `[x]` 亲缘链路查询：父母子女关系和婚姻关系双向化后查询可达路径。
- `[x]` 亲缘链路已优化为渐进式双向 BFS，并在 PostgreSQL 中部署 `bfs_reachable()` 函数。
- `[x]` 图形化族谱树已改为懒加载版本：首次不加载全量节点，可加载根成员、按成员 ID 定位，并逐层展开父母或子女。
- `[!]` 可加分：后续可继续增加缩放、拖拽和按成员姓名定位；当前版本优先保证 6000/50000 人大族谱页面不卡死。

### M5 数据库结构、DDL 与约束

- `[x]` 核心表：`users`、`genealogies`、`genealogy_collaborators`、`members`、`parent_child_relations`、`marriages`。
- `[x]` DDL 位于 `sql/schema.sql`。
- `[x]` 索引覆盖姓名模糊查询、父节点查子节点、子节点查父节点、婚姻双方查询。
- `[x]` 数据库触发器覆盖跨行约束。
- `[x]` `docs/data_model.md` 包含 E-R 图、关系模式和 3NF 说明。

### M6 数据生成、导入与导出

- `[x]` `scripts/seed_data.py` 生成至少 10 个族谱、总成员不少于 100000、最大单族谱不少于 50000、至少 30 代。
- `[x]` 生成数据保证每个成员至少有一条血缘或婚姻边。
- `[x]` `scripts/import_csv.py` 使用 PostgreSQL `COPY` 导入 CSV。
- `[x]` `scripts/export_branch.py` 导出某成员及其递归后代分支。
- `[x]` `sql/copy_import.sql` 提供手工 `\copy` 示例。

### M7 SQL 实验与性能优化

- `[x]` `sql/queries/` 覆盖祖先、后代、亲缘链路、树形预览、四代查询 EXPLAIN 和 5 类课程 SQL。
- `[x]` `scripts/explain_performance.py` 可生成有/无索引的四代查询性能对比。
- `[x]` `docs/performance_results.md` 保存执行计划和耗时说明。
- `[x]` `scripts/test_optimized_path.py` 可验证 5 万人族谱上的亲缘链路查询性能。

### M8 演示、报告与验收

- `[x]` `scripts/create_demo_data.py` 创建稳定演示账号：`demo@example.com` / `demo123456`。
- `[x]` 演示族谱为 20 人、5 代，含生卒年、婚姻、血缘、无配偶老年男性和代内出生年份差异。
- `[x]` `docs/demo_guide.md`、`docs/acceptance_guide.md`、`docs/report_outline.md`、`docs/backup_restore.md` 已存在。
- `[!]` 人工补充：最终报告仍需按老师要求插入数据库执行截图、页面截图和备份文件。

## 2026-05-13 队友修改后审查记录

### 已发现并修复的问题

- `[x]` `pytest` 失败：亲缘链路优化使用 PostgreSQL `CYCLE`，SQLite 测试库不支持。已增加 SQLite 专用 Python BFS 兜底，不影响 PostgreSQL 正式路径。
- `[x]` 数据生成测试对随机婚姻数写死为 15，和生成逻辑不稳定。已改为校验摘要中的真实婚姻数，并继续校验所有成员至少一条边。
- `[x]` 族谱缺少“姓氏、修谱年份”字段，且没有族谱编辑/删除。已补模型、迁移、表单、列表、详情页和测试。
- `[x]` CSV 生成与 COPY 导入未包含族谱新增字段。已同步更新 `seed_data.py`、`import_csv.py`、`sql/copy_import.sql`。
- `[x]` 演示脚本复用旧“演示族谱”时会得到不完整数据。已改为每次重建稳定演示族谱。
- `[x]` 演示族谱中的无配偶老年男性原本没有任何边。已改为接入血缘树，保留“无配偶男性”查询演示点，同时全库 `members_without_edge = 0`。
- `[x]` `bfs_reachable()` 函数只在 SQL 文件中，没有进入迁移。已新增迁移 `a7c9d2f4b601_add_bfs_reachable_function.py` 并部署到本地 PostgreSQL。
- `[x]` 亲缘链路批量关系标签查询原来按成员 ID 排序，可能打乱路径步序。已改为按路径步骤序号排序。

### 本轮自动验收结果

- `[x]` `flask --app app db current`：`a7c9d2f4b601 (head)`。
- `[x]` `pytest`：`11 passed`。
- `[x]` `compileall app scripts migrations`：通过。
- `[x]` `scripts/db_smoke_test.py`：11 个族谱、104020 个成员、最大单族谱 50000、最大 30 代、孤立成员 0、`large_dataset_acceptance: PASS`。
- `[x]` 页面级巡检：登录、族谱列表、详情、编辑、邀请、成员列表、姓名搜索、树形预览、统计页、关系页、祖先、后代、亲缘链路、CSV 导出均返回 200。
- `[x]` `scripts/test_optimized_path.py`：5 万人族谱亲缘链路测试全部在 5 秒内完成，本轮最慢约 2 秒。

## 2026-05-13 懒加载式图形化族谱树实现记录

- `[x]` 新增 JSON 接口：`/genealogies/<id>/tree-roots`，最多返回 50 个根成员。
- `[x]` 新增 JSON 接口：`/genealogies/<id>/tree-node/<member_id>`，用于按成员 ID 定位。
- `[x]` 新增 JSON 接口：`/genealogies/<id>/tree-node/<member_id>/children`，最多返回一层 100 个子女。
- `[x]` 新增 JSON 接口：`/genealogies/<id>/tree-node/<member_id>/parents`，最多返回 2 个父母。
- `[x]` 树形预览页新增 SVG 图形树工具区，支持加载根成员、按 ID 定位、清空画布、向上/向下展开。
- `[x]` 当前图形画布最多显示 500 个节点，避免再次出现大数据量下浏览器无响应。
- `[x]` 原递归 CTE 缩进树保留在页面下方，但已改为按需加载；默认进入页面不再执行缩进树递归查询。
- `[x]` 新增接口测试：未登录保护、根节点查询、一层子女查询、父母查询、跨族谱成员隔离。
- `[x]` 验证结果：`pytest` 为 `12 passed`，`compileall` 通过，`flask --app app routes` 可列出新增接口。

## 2026-05-13 缩进树大数据加载优化记录

- `[x]` 发现问题：图形树已懒加载，但树页面默认仍会执行缩进树递归 CTE，6000/50000 人族谱打开页面仍可能变慢。
- `[x]` 修复方式：`/genealogies/<id>/tree` 默认不查询缩进树；只有访问 `/genealogies/<id>/tree?show_indent=1` 或点击“加载缩进树”时才执行递归查询。
- `[x]` 页面提示已更新：大族谱优先使用图形树逐层展开，缩进树作为报告截图和备选展示。

## 可加分但非必需的扩展

1. 协作者角色权限细化：`viewer` 只能查看，`editor` 才能新增/编辑/删除。
2. 图形树交互增强：增加缩放、拖拽、节点折叠动画和按姓名搜索定位。
3. 成员详情页：集中展示个人资料、父母、配偶、子女、祖先/后代入口。
4. 导入校验报告：导入 CSV 前检查孤立成员、非法代数、重复婚姻、父母角色冲突。
5. 操作审计日志：记录谁在什么时候修改了成员和关系，报告里会显得更完整。
6. 备份恢复一键任务：把 `pg_dump`、`COPY` 分支导出和 smoke test 串成一个 VSCode task。
