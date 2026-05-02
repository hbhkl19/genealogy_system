# 实验报告提纲

## 1. 项目概述

- 系统名称：寻根溯源族谱管理系统
- 技术栈：Flask、Jinja2、Bootstrap、SQLAlchemy、PostgreSQL 16
- 目标：完成多用户、多族谱、协作者、成员关系维护、递归查询、数据生成、性能优化与备份恢复。

## 2. 需求与功能

- 用户注册、登录、退出
- 族谱 CRUD 与协作者邀请
- 成员 CRUD
- 父母子女关系维护
- 婚姻关系维护
- 祖先、后代、树形预览、亲缘链路查询
- CSV 导入导出
- 性能对比与 EXPLAIN

## 3. 数据库设计

引用 `docs/data_model.md`：

- E-R 图
- 关系模式
- 主键、外键、唯一约束、CHECK 约束
- 跨行触发器约束
- 3NF 说明

## 4. 数据生成与导入

引用 `docs/data_pipeline.md`：

- Faker 数据生成策略
- 数据规模验收
- COPY 导入流程
- 分支导出流程

## 5. SQL 查询

引用 `sql/queries/`：

- 数据规模验收
- 祖先查询
- 后代查询
- 亲缘路径查询
- 四代查询 EXPLAIN
- 树形预览

## 6. 性能优化

引用 `docs/performance_results.md`：

- 无索引执行计划
- 有索引执行计划
- 执行时间对比
- 索引效果说明

## 7. 系统测试

- `pytest`
- `flask --app app routes`
- `flask --app app db current`
- `scripts/db_smoke_test.py`

## 8. 备份与恢复

引用 `docs/backup_restore.md`。

## 9. 总结

- 已完成课程要求的数据库结构、约束、递归查询、数据规模和性能实验。
- 后续可扩展图形化族谱树、权限细分和更完整的数据导入校验。
