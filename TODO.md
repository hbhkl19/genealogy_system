# TODO

本文件用于记录“寻根溯源”族谱管理系统的关键开发步骤和每次开发进展。后续每次开发前先看本文件，开发后更新对应状态、日期和备注。

## 状态标记

- `[ ]` 未开始
- `[~]` 进行中
- `[x]` 已完成
- `[!]` 有阻塞或需要确认

## 当前里程碑

### M0 项目基础与环境

- `[x]` 初始化 Git 仓库。
- `[x]` 建立项目目录：`app/`、`scripts/`、`sql/`、`tests/`、`docs/`、`data/`。
- `[x]` 建立 Flask 应用工厂、配置层、扩展初始化和蓝图结构。
- `[x]` 补充 VSCode 配置：推荐扩展、调试配置、任务配置、Python 解释器配置。
- `[x]` 编写 `README.md`，说明主要功能、环境需求、启动方式和项目结构。
- `[~]` 检查本地开发环境。
  - 已确认 `.venv` 可用，Flask、SQLAlchemy、psycopg、pytest 等依赖已安装。
  - 已确认 `flask --app app routes` 可列出路由。
  - 已确认 `pytest` 能通过最小测试。
  - 待处理：当前 `.venv` 是 Python 3.13.3，计划推荐 Python 3.11.x，需要决定是否重建虚拟环境。
  - 已处理：为 VSCode 终端补充 `terminal.integrated.inheritEnv` 和 PostgreSQL 16 常见 `bin` 路径。
  - 已处理：为 pytest 配置禁用 cacheprovider，限制测试收集目录，并将 `pytest-cache-files-*` 加入 `.gitignore`。
  - 待确认：重新打开 VSCode 后，在集成终端执行 `psql --version` 是否可用。

### M1 用户与权限

- `[x]` 实现用户注册、登录、退出。
- `[x]` 实现密码哈希。
- `[x]` 实现登录拦截。
- `[x]` 实现用户只能查看自己创建或受邀参与的族谱。
- `[ ]` 增加更完整的表单校验和错误提示。
- `[ ]` 增加认证相关测试：注册、登录、重复账号、未登录访问重定向。

### M2 族谱管理与协作

- `[x]` 实现族谱创建和列表页。
- `[x]` 实现族谱详情页和 Dashboard 基础统计。
- `[x]` 实现协作者邀请入口。
- `[ ]` 实现族谱编辑和删除。
- `[ ]` 完善协作者角色权限：`viewer` 只读，`editor` 可编辑。
- `[ ]` 增加族谱管理相关测试。

### M3 成员管理与关系维护

- `[x]` 实现成员新增。
- `[x]` 实现成员列表和姓名模糊搜索入口。
- `[x]` 实现成员编辑和删除。
- `[x]` 实现父亲、母亲、子女关系维护页面。
- `[x]` 实现婚姻关系维护页面。
- `[x]` 实现关系合法性校验。
  - 成员不能成为自己的父母或配偶。
  - 同一子女最多一个父亲、一个母亲。
  - 父母出生年应早于子女；当前已做应用层校验，数据库触发器留在 M5 完成。
  - 婚姻关系使用有序成员对避免重复。
- `[x]` 增加成员和关系维护测试。

### M4 递归查询与树形展示

- `[x]` 建立祖先查询路由和递归 CTE 雏形。
- `[x]` 建立亲缘链路查询路由和递归 CTE 雏形。
- `[x]` 建立树形预览页面入口。
- `[x]` 实现直系后代查询页面。
- `[x]` 将树形预览从根节点列表扩展为缩进树或折叠列表。
- `[x]` 优化亲缘链路页面，展示每一段关系类型。
- `[x]` 将最终 SQL 固化到 `sql/queries/`，每类需求只保留一个答辩版本。

### M5 数据库结构、DDL 与约束

- `[x]` 建立核心 SQLAlchemy 模型：`users`、`genealogies`、`genealogy_collaborators`、`members`、`parent_child_relations`、`marriages`。
- `[x]` 编写初版 `sql/schema.sql`。
- `[x]` 编写基础索引：姓名 trigram、父子查询索引、婚姻双方索引。
- `[x]` 接入 Flask-Migrate，生成首个迁移版本。
- `[x]` 编写跨行约束触发器。
- `[x]` 整理 E-R 图、关系模式和 3NF 说明。

### M6 数据生成、导入与导出

- `[x]` 实现 Faker 数据生成脚本。
- `[x]` 生成至少 10 个族谱。
- `[x]` 生成总成员数不少于 100000。
- `[x]` 生成至少一个不少于 50000 成员的族谱。
- `[x]` 生成至少 30 代传承。
- `[x]` 保证每个成员至少存在一条婚姻或血缘边。
- `[x]` 导出 CSV。
- `[x]` 编写 PostgreSQL `COPY` 导入流程。
- `[x]` 实现某分支导出脚本。
- `[ ]` 将分支导出 CSV 再次导入测试库并复现同一分支数据。

### M7 SQL 实验与性能优化

- `[x]` 建立 `sql/queries/00_validation.sql`。
- `[x]` 建立祖先、后代、亲缘路径和四代查询 EXPLAIN SQL 初版。
- `[x]` 建立树形预览 SQL。
- `[x]` 补齐课程要求的 5 类最终 SQL。
- `[ ]` 对四代查询执行无索引和有索引的 `EXPLAIN (ANALYZE, BUFFERS)`。
- `[ ]` 保存执行计划截图。
- `[ ]` 整理耗时对比表。
- `[ ]` 编写性能优化说明。

### M8 演示、报告与验收

- `[ ]` 准备演示账号和示例族谱。
- `[ ]` 截图保存：注册、登录、族谱管理、成员管理、树形预览、祖先查询、亲缘路径查询。
- `[ ]` 整理数据库备份和恢复说明。
- `[ ]` 整理实验报告。
- `[ ]` 按验收 SQL 验证数据规模。
- `[ ]` 最终运行 `flask --app app routes`、`pytest` 和数据库 smoke test。

## 开发日志

### 2026-04-29

- 完成从零开始的项目骨架。
- 完成 `README.md`、VSCode 配置、基础 Flask 页面、核心模型、初版 SQL 和最小测试。
- 验证结果：
  - `flask --app app routes` 成功。
  - `pytest` 通过，结果为 `1 passed`，但出现 pytest 缓存目录权限警告。
  - Flask 开发服务器可以访问 `http://127.0.0.1:5000`。
- 新增本文件，将后续开发拆分为 M0-M8 里程碑。

### 2026-04-29 第二轮

- 接入 Flask-Migrate，生成 `migrations/` 和首个 `initial schema` 迁移。
- 调整模型和迁移中的时间字段为带时区时间，并补充数据库端默认值。
- 在迁移中补充 `pg_trgm` 扩展、姓名 GIN trigram 索引、父子关系复合索引和婚姻关系复合索引。
- 更新 VSCode 终端环境配置，尝试解决集成终端找不到 `psql` 的问题。
- 更新 pytest 配置和 `.gitignore`，减少缓存权限问题对开发的干扰。

### 2026-04-29 第三轮

- 完成 M3 成员管理与关系维护。
- 新增成员编辑、删除路由和页面入口。
- 新增成员关系维护页面，可添加和移除父母、子女、婚姻关系。
- 增加基础合法性校验：不能自关联、同一子女最多一个父亲和一个母亲、父母出生年早于子女、父母代数小于子女、婚姻关系有序去重。跨行数据库触发器仍按 M5 继续处理。
- 新增迁移 `eb4cc1a0641e_add_relation_constraints_and_indexes.py`，为同一子女同一父母角色添加唯一约束。
- 补充 M3 测试，覆盖成员编辑、父母唯一性和婚姻去重。
- 验证结果：
  - `flask --app app db upgrade` 成功。
  - `flask --app app db current` 返回 `eb4cc1a0641e (head)`。
  - `flask --app app routes` 成功列出 M3 新路由。
  - `pytest` 通过，结果为 `3 passed`。

### 2026-04-29 第四轮

- 完成 M4 递归查询与树形展示的可演示版本。
- 新增直系后代查询路由 `/members/<id>/descendants` 和页面。
- 将族谱树形预览改为递归 CTE 缩进树，最多展示 500 行，递归深度限制为 12 层用于页面稳定演示。
- 优化亲缘链路查询，返回每一步关系类型，并在页面展示“父亲、母亲、子女、配偶”等关系标签。
- 新增 `sql/queries/05_tree_preview.sql`，并更新亲缘链路 SQL 输出关系类型。
- 更新祖先和后代 SQL，加入深度限制与循环保护。
- 成员列表增加后代查询入口和亲缘链路查询表单。
- 将递归 CTE 的访问路径从 PostgreSQL 数组改为逗号分隔字符串，兼容 PostgreSQL 和 SQLite 测试库。
- 补充 M4 测试，覆盖后代查询、树形预览和亲缘路径关系标签。
- 验证结果：
  - `flask --app app routes` 成功列出 M4 新路由。
  - `pytest` 通过，结果为 `4 passed`。
  - `compileall` 通过。

### 2026-04-30 第五轮

- 完成 M5 数据库结构、DDL 与约束。
- 新增迁移 `8ef1ddc6ab24_add_relationship_integrity_triggers.py`。
- 新增 PostgreSQL 触发器：
  - `trg_validate_parent_child_relation`：校验父母与子女同族谱、父母代数小于子女、父母出生年早于子女。
  - `trg_validate_marriage_relation`：校验配偶双方属于同一族谱。
  - `trg_validate_member_existing_relations`：更新成员族谱、生年、代数时，防止破坏已有父子或婚姻关系。
- 同步更新 `sql/schema.sql`，让手工建库 DDL 与迁移保持一致。
- 新增 `docs/data_model.md`，包含 E-R 图、关系模式、约束策略、3NF 说明和索引说明。
- 补充数据库工件测试，确保触发器迁移、schema 和数据模型文档存在关键内容。
- 使用事务内 smoke test 验证触发器：
  - 非法父子关系被触发器拒绝。
  - 跨族谱婚姻被触发器拒绝。
  - 测试数据已回滚，不污染开发库。
- 验证结果：
  - `flask --app app db upgrade` 成功。
  - `flask --app app db current` 返回 `8ef1ddc6ab24 (head)`。
  - `flask --app app routes` 成功。
  - `pytest` 通过，结果为 `7 passed`。
  - `compileall app scripts migrations` 成功。

### 2026-05-01 第六轮

- 完成 M6 数据生成、导入与导出主体实现。
- 重写 `scripts/seed_data.py`：
  - 默认生成 10 个族谱。
  - 默认生成 104000 个成员。
  - 最大单族谱 50000 个成员。
  - 每个族谱 30 代。
  - 每个成员至少有一条婚姻或血缘边。
- 新增 `scripts/import_csv.py`，使用 PostgreSQL `COPY` 从 CSV 导入，并支持 `--truncate` 清空重导。
- 重写 `scripts/export_branch.py`，支持按成员 ID 导出该成员及所有递归后代、分支内父子关系和婚姻关系。
- 新增 `sql/copy_import.sql`，提供 psql 手工 `\copy` 导入示例。
- 新增 `docs/data_pipeline.md`，说明生成、导入、分支导出和验收 SQL。
- 新增数据生成测试，校验小规模生成结果的成员数、父子关系、婚姻关系和每个成员至少存在一条边。
- 实际运行默认生成，产出 `data/generated`：
  - 族谱数：10
  - 成员数：104000
  - 最大单族谱成员数：50000
  - 最大代际深度：30
  - 无边成员数：0
  - 父子关系数：201064
  - 婚姻关系数：52000
- 验证结果：
  - `pytest` 通过，结果为 `8 passed`。
  - `compileall app scripts migrations` 成功。
  - `scripts/import_csv.py --help` 成功。
  - `scripts/export_branch.py --help` 成功。

## 下次建议优先级

1. 进入 M7，准备 EXPLAIN 性能对比和截图材料。
2. 将分支导出 CSV 再次导入测试库并复现同一分支数据。
3. 准备演示账号和示例族谱，开始积累报告截图。
4. 继续确认 VSCode 集成终端中 `psql --version` 是否可用。
