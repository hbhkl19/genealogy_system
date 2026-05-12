# 物理优化性能对比

> RDBMS: PostgreSQL 16  
> 测试数据: 104,000 成员, 201,070 亲子关系, 103,984 婚姻

---

## 一、索引策略

| 需求 | 索引名 | 类型 | 定义 |
|------|--------|------|------|
| 姓名模糊查询 | `ix_members_name_trgm` | GIN (pg_trgm) | `USING gin (name gin_trgm_ops)` |
| 父节点→子节点 | `ix_parent_child_genealogy_parent` | B-tree 复合 | `(genealogy_id, parent_member_id)` |
| 子节点→父节点 | `ix_parent_child_genealogy_child` | B-tree 复合 | `(genealogy_id, child_member_id)` |
| 配偶关系查找 | `ix_marriages_genealogy_spouse1` | B-tree 复合 | `(genealogy_id, spouse1_member_id)` |
| 配偶关系查找 | `ix_marriages_genealogy_spouse2` | B-tree 复合 | `(genealogy_id, spouse2_member_id)` |

---

## 二、四代查询 EXPLAIN 对比（曾祖父 → 曾孙）

### 场景：无索引（强制 Seq Scan）

```text
Sort  (cost=48218.16..48218.51 rows=142 width=33) (actual time=91.596..91.600 rows=30 loops=1)
  Sort Key: descendants.depth, m.id
  Sort Method: quicksort  Memory: 26kB
  Buffers: shared hit=7203
  CTE descendants
    ->  Recursive Union  (cost=0.00..44953.04 rows=142 width=8) (actual time=0.005..65.636 rows=30 loops=1)
          Buffers: shared hit=5376
          ->  Seq Scan on parent_child_relations  (cost=0.00..3857.38 rows=2 width=8)
                Filter: (parent_member_id = '1'::smallint)
                Rows Removed by Filter: 201068
                Buffers: shared hit=1344
          ->  Hash Join  (cost=0.54..4109.43 rows=14 width=8) (actual time=0.429..14.322 rows=7 loops=4)
                ->  Seq Scan on parent_child_relations p  (cost=0.00..3354.70 rows=201070 width=8)
                      Buffers: shared hit=4032
                ->  Hash  (cost=0.45..0.45 rows=7 width=8)
                      ->  WorkTable Scan on descendants d
                            Filter: (depth < 4)
  ->  Hash Join  (cost=4.62..3260.03 rows=142 width=33) (actual time=66.108..91.508 rows=30 loops=1)
        ->  Seq Scan on members m  (cost=0.00..2864.00 rows=104000 width=29)
              Buffers: shared hit=1824
        ->  Hash  (cost=2.84..2.84 rows=142 width=8)
              ->  CTE Scan on descendants  (cost=0.00..2.84 rows=142 width=8)
Planning Time: 2.222 ms
Execution Time: 91.648 ms
```

**关键指标**: 顺序扫描 parent_child_relations 全表 (201,070 行)，扫描 members 全表 (104,000 行)

### 场景：有索引（Index Only Scan）

```text
Sort  (cost=1423.91..1424.27 rows=142 width=33) (actual time=0.301..0.303 rows=30 loops=1)
  Sort Key: descendants.depth, m.id
  Sort Method: quicksort  Memory: 26kB
  Buffers: shared hit=140
  CTE descendants
    ->  Recursive Union  (cost=0.42..367.97 rows=142 width=8) (actual time=0.108..0.189 rows=30 loops=1)
          Buffers: shared hit=50
          ->  Index Only Scan using uq_parent_child on parent_child_relations
                Index Cond: (parent_member_id = '1'::smallint)
                Heap Fetches: 0
                Buffers: shared hit=7
          ->  Nested Loop  (cost=0.42..35.81 rows=14 width=8) (actual time=0.007..0.018 rows=7 loops=4)
                ->  WorkTable Scan on descendants d
                      Filter: (depth < 4)
                ->  Index Only Scan using uq_parent_child on parent_child_relations p
                      Index Cond: (parent_member_id = d.member_id)
                      Heap Fetches: 0
                      Buffers: shared hit=43
  ->  Nested Loop  (cost=0.29..1050.86 rows=142 width=33) (actual time=0.120..0.288 rows=30 loops=1)
        ->  CTE Scan on descendants
        ->  Index Scan using members_pkey on members m
              Index Cond: (id = descendants.member_id)
              Buffers: shared hit=90
Planning Time: 0.217 ms
Execution Time: 0.355 ms
```

**关键指标**: Index Only Scan 精准定位，Nested Loop 仅处理少量行

### 对比汇总

| 指标 | 无索引 (Seq Scan) | 有索引 (Index Scan) | 提升 |
|------|:---:|:---:|:---:|
| **执行时间** | 91.648 ms | 0.355 ms | **258×** |
| **缓冲区命中** | 7,203 | 140 | **51×** |
| **扫描方式** | Seq Scan (全表) | Index Only Scan | — |
| **扫描行数** | 201,070 + 104,000 | ~30 (索引精确定位) | — |

---

## 三、姓名模糊查询 EXPLAIN 对比

### 查询

```sql
SELECT id, name FROM members WHERE name ILIKE '%周伟%' LIMIT 10
```

### 场景：强制 Seq Scan

| 指标 | 值 |
|------|---|
| 执行时间 | 63.661 ms |
| 缓冲区 | 1,298 |
| 扫描方式 | Seq Scan on members |
| 过滤行数 | 74,032 |

### 场景：强制 GIN trigram 索引

| 指标 | 值 |
|------|---|
| 执行时间 | 163.004 ms (含首次磁盘读取) |
| 缓冲区 | 1,985 (含 685 reads) |
| 扫描方式 | Bitmap Index Scan on ix_members_name_trgm |
| 命中行数 | 104,006 (trigram 匹配极宽，因中文单字 trigram 覆盖率高) |

> **说明**: 对于 2 字中文名 + `%keyword%` 全模糊匹配，Seq Scan 性能更优（trigram 特征过于宽泛）。对于前缀匹配 `LIKE 'keyword%'` 或长文本，GIN trigram 索引优势明显。此索引在项目中已部署，实际 Web 搜索接口通过 `ILIKE` + trigram 索引配合工作。