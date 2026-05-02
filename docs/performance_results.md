# 四代查询性能对比

查询成员 ID：`9`

| 场景 | Execution Time |
| --- | --- |
| 临时移除索引 | 0.208 ms |
| 使用索引 | 0.110 ms |

## 临时移除索引执行计划

```text
Sort  (cost=356.08..358.19 rows=845 width=270) (actual time=0.122..0.123 rows=2 loops=1)
  Sort Key: descendants.depth, m.id
  Sort Method: quicksort  Memory: 25kB
  Buffers: shared hit=7
  CTE descendants
    ->  Recursive Union  (cost=4.19..281.11 rows=845 width=8) (actual time=0.026..0.042 rows=2 loops=1)
          Buffers: shared hit=6
          ->  Bitmap Heap Scan on parent_child_relations  (cost=4.19..12.66 rows=5 width=8) (actual time=0.025..0.026 rows=2 loops=1)
                Recheck Cond: (parent_member_id = '9'::smallint)
                Heap Blocks: exact=1
                Buffers: shared hit=5
                ->  Bitmap Index Scan on uq_parent_child  (cost=0.00..4.19 rows=5 width=0) (actual time=0.020..0.020 rows=2 loops=1)
                      Index Cond: (parent_member_id = '9'::smallint)
                      Buffers: shared hit=4
          ->  Hash Join  (cost=1.34..26.00 rows=84 width=8) (actual time=0.014..0.014 rows=0 loops=1)
                Hash Cond: (p.parent_member_id = d.member_id)
                Buffers: shared hit=1
                ->  Seq Scan on parent_child_relations p  (cost=0.00..19.90 rows=990 width=8) (actual time=0.002..0.002 rows=6 loops=1)
                      Buffers: shared hit=1
                ->  Hash  (cost=1.12..1.12 rows=17 width=8) (actual time=0.005..0.005 rows=2 loops=1)
                      Buckets: 1024  Batches: 1  Memory Usage: 9kB
                      ->  WorkTable Scan on descendants d  (cost=0.00..1.12 rows=17 width=8) (actual time=0.001..0.001 rows=2 loops=1)
                            Filter: (depth < 4)
  ->  Hash Join  (cost=14.72..33.89 rows=845 width=270) (actual time=0.094..0.110 rows=2 loops=1)
        Hash Cond: (descendants.member_id = m.id)
        Buffers: shared hit=7
        ->  CTE Scan on descendants  (cost=0.00..16.90 rows=845 width=8) (actual time=0.029..0.045 rows=2 loops=1)
              Buffers: shared hit=6
        ->  Hash  (cost=12.10..12.10 rows=210 width=266) (actual time=0.015..0.015 rows=6 loops=1)
              Buckets: 1024  Batches: 1  Memory Usage: 9kB
              Buffers: shared hit=1
              ->  Seq Scan on members m  (cost=0.00..12.10 rows=210 width=266) (actual time=0.009..0.010 rows=6 loops=1)
                    Buffers: shared hit=1
Planning:
  Buffers: shared hit=110
Planning Time: 3.079 ms
Execution Time: 0.208 ms
```

## 使用索引执行计划

```text
Sort  (cost=356.08..358.19 rows=845 width=270) (actual time=0.049..0.050 rows=2 loops=1)
  Sort Key: descendants.depth, m.id
  Sort Method: quicksort  Memory: 25kB
  Buffers: shared hit=4
  CTE descendants
    ->  Recursive Union  (cost=4.19..281.11 rows=845 width=8) (actual time=0.012..0.026 rows=2 loops=1)
          Buffers: shared hit=3
          ->  Bitmap Heap Scan on parent_child_relations  (cost=4.19..12.66 rows=5 width=8) (actual time=0.010..0.011 rows=2 loops=1)
                Recheck Cond: (parent_member_id = '9'::smallint)
                Heap Blocks: exact=1
                Buffers: shared hit=2
                ->  Bitmap Index Scan on ix_parent_child_relations_parent_member_id  (cost=0.00..4.19 rows=5 width=0) (actual time=0.007..0.007 rows=2 loops=1)
                      Index Cond: (parent_member_id = '9'::smallint)
                      Buffers: shared hit=1
          ->  Hash Join  (cost=1.34..26.00 rows=84 width=8) (actual time=0.012..0.012 rows=0 loops=1)
                Hash Cond: (p.parent_member_id = d.member_id)
                Buffers: shared hit=1
                ->  Seq Scan on parent_child_relations p  (cost=0.00..19.90 rows=990 width=8) (actual time=0.002..0.002 rows=6 loops=1)
                      Buffers: shared hit=1
                ->  Hash  (cost=1.12..1.12 rows=17 width=8) (actual time=0.004..0.004 rows=2 loops=1)
                      Buckets: 1024  Batches: 1  Memory Usage: 9kB
                      ->  WorkTable Scan on descendants d  (cost=0.00..1.12 rows=17 width=8) (actual time=0.002..0.002 rows=2 loops=1)
                            Filter: (depth < 4)
  ->  Hash Join  (cost=14.72..33.89 rows=845 width=270) (actual time=0.029..0.043 rows=2 loops=1)
        Hash Cond: (descendants.member_id = m.id)
        Buffers: shared hit=4
        ->  CTE Scan on descendants  (cost=0.00..16.90 rows=845 width=8) (actual time=0.014..0.027 rows=2 loops=1)
              Buffers: shared hit=3
        ->  Hash  (cost=12.10..12.10 rows=210 width=266) (actual time=0.008..0.008 rows=6 loops=1)
              Buckets: 1024  Batches: 1  Memory Usage: 9kB
              Buffers: shared hit=1
              ->  Seq Scan on members m  (cost=0.00..12.10 rows=210 width=266) (actual time=0.004..0.005 rows=6 loops=1)
                    Buffers: shared hit=1
Planning:
  Buffers: shared hit=74
Planning Time: 2.065 ms
Execution Time: 0.110 ms
```
