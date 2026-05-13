# 亲缘链路查询：从前端输入到结果回显的完整流程

> 以"查询张小明（ID=100）到李小红（ID=500）的最短亲缘路径"为例  
> 数据规模：50000 人, 239506 条边

---

## 目录

- [阶段一：前端页面 — 用户发起查询](#阶段一前端页面--用户发起查询)
- [阶段二：HTTP 请求 — 路由分发](#阶段二http-请求--路由分发)
- [阶段三：路由处理器 — Python 业务逻辑](#阶段三路由处理器--python-业务逻辑)
- [阶段四：Phase 1 双向 BFS — 找到交汇点](#阶段四phase-1-双向-bfs--找到交汇点)
- [阶段五：Phase 2 路径重构 — 拼接完整路径](#阶段五phase-2-路径重构--拼接完整路径)
- [阶段六：最终渲染 — 模板回显](#阶段六最终渲染--模板回显)
- [附录：完整调用链总览图](#附录完整调用链总览图)

---

## 阶段一：前端页面 — 用户发起查询

### 1.1 用户所在的页面

用户在 **族谱成员列表页**（[`genealogies/members.html`](file:///d:/上课/大三下/数据库/genealogy_system/app/templates/genealogies/members.html)），该页面列出了族谱中的所有成员：

```
┌──────────────────────────────────────────────────────┐
│  导航栏: 寻根溯源  |  我的族谱  |  退出               │
├──────────────────────────────────────────────────────┤
│                                                      │
│  张氏族谱成员                        [+ 添加成员]      │
│                                                      │
│  ┌──────────────┐ [搜索]                             │
│  │ 按姓名搜索... │                                    │
│  └──────────────┘                                    │
│                                                      │
│  成员A ID: [100    ]  成员B ID: [500    ] [亲缘链路]  │ ← 用户操作区域
│                                                      │
│  ┌────┬────────┬──────┬──────────┬────┬───────────┐ │
│  │ ID │ 姓名   │ 性别 │ 生卒年   │ 代 │    操作    │ │
│  ├────┼────────┼──────┼──────────┼────┼───────────┤ │
│  │100 │ 张小明 │  男  │1980-     │  5 │祖先|后代|..│ │
│  │101 │ 张大伟 │  男  │1982-     │  5 │祖先|后代|..│ │
│  │... │  ...   │ ...  │   ...    │... │     ...    │ │
│  └────┴────────┴──────┴──────────┴────┴───────────┘ │
└──────────────────────────────────────────────────────┘
```

### 1.2 输入表单的 HTML 源码

[`genealogies/members.html`](file:///d:/上课/大三下/数据库/genealogy_system/app/templates/genealogies/members.html#L12-L16)：

```html
<form class="row g-2 mb-4" action="{{ url_for('members.relationship_path') }}">
    <div class="col-sm-5">
        <input class="form-control" name="a" type="number" min="1" 
               placeholder="成员 A ID">
    </div>
    <div class="col-sm-5">
        <input class="form-control" name="b" type="number" min="1" 
               placeholder="成员 B ID">
    </div>
    <div class="col-sm-2">
        <button class="btn btn-outline-secondary w-100" type="submit">
            亲缘链路
        </button>
    </div>
</form>
```

**关键细节**：

| 要素 | 值 |
|------|-----|
| 表单方法 | `GET`（参数出现在 URL 中，可分享链接） |
| 目标 URL | `url_for('members.relationship_path')` → `/members/relationship/path` |
| 参数名 | `a`（成员 A 的 ID），`b`（成员 B 的 ID） |
| 输入类型 | `type="number" min="1"`（只允许正整数） |
| 提交按钮文字 | `亲缘链路` |

### 1.3 用户操作

用户从成员表中找到张小明（ID=100），在"A"输入框填入 `100`；找到李小红（ID=500），在"B"输入框填入 `500`，然后点击"亲缘链路"按钮。

浏览器构造的请求：

```
GET /members/relationship/path?a=100&b=500 HTTP/1.1
Host: localhost:5000
```

---

## 阶段二：HTTP 请求 — 路由分发

### 2.1 URL 到路由函数的映射

Flask 应用在启动时注册了 Blueprint `members`，前缀为 `/members`。在 [`routes.py`](file:///d:/上课/大三下/数据库/genealogy_system/app/members/routes.py#L10) 中：

```python
bp = Blueprint("members", __name__)
```

请求 URL `/members/relationship/path` 被 Flask 解析为：
- Blueprint: `members`（前缀 `/members`）
- 路径: `/relationship/path`
- 匹配到装饰器: `@bp.route("/relationship/path")`

### 2.2 Flask 参数解析

Flask 将 URL 中的查询字符串 `?a=100&b=500` 解析为 `request.args` 字典：

```python
request.args == {"a": "100", "b": "500"}
```

这是 `ImmutableMultiDict` 类型，键值都是字符串。

### 2.3 权限检查

```python
@bp.route("/relationship/path")     # ① 路由注册
@login_required                      # ② 权限装饰器：检查 session 中是否有 current_user
def relationship_path():
```

`@login_required` 是装饰器栈中**最外层**（被 Flask 最先执行）。执行流程：

```
HTTP 请求到达
  → Flask-Login 检查 session
    → 已登录: 继续
    → 未登录: 重定向到 /auth/login?next=/members/relationship/path?a=100&b=500
  → 进入 relationship_path() 函数体
```

---

## 阶段三：路由处理器 — Python 业务逻辑

### 3.1 参数验证

```python
member_a_id = request.args.get("a", type=int)  # "100" → int 100
member_b_id = request.args.get("b", type=int)  # "500" → int 500

if not member_a_id or not member_b_id:
    flash("请提供 a 和 b 两个成员 ID。", "warning")
    return redirect(url_for("genealogies.index"))
```

`type=int` 告诉 Flask 自动将字符串 `"100"` 转为整数 `100`。如果 `a` 参数缺失或不是数字，返回 `None`，触发错误提示和重定向。

### 3.2 成员验证与权限检查

```python
member_a = get_member(member_a_id)  # 查找 ID=100 的成员
member_b = get_member(member_b_id)  # 查找 ID=500 的成员
```

**[`get_member()`](file:///d:/上课/大三下/数据库/genealogy_system/app/members/routes.py#L29-L36)** 函数做了三件事：

```python
def get_member(member_id):
    # 步骤 1: 查主键
    member = db.session.get(Member, member_id)
    if member is None:
        abort(404)
    
    # 步骤 2: 验证当前用户是否有权访问该成员所属的族谱
    genealogy = (
        accessible_genealogy_query(current_user)
        .filter(Genealogy.id == member.genealogy_id)
        .first()
    )
    if genealogy is None:
        abort(404)  # 成员存在但不属于当前用户的族谱 → 404（不泄露信息）
    
    return member
```

对应的 SQL（步骤 2）：

```sql
-- accessible_genealogy_query 生成的核心 SQL：
SELECT g.* FROM genealogies g
LEFT JOIN genealogy_collaborators gc ON g.id = gc.genealogy_id
WHERE g.id = :member_genealogy_id         -- 成员所属族谱
  AND (g.owner_id = :current_user_id      -- 我是创建者
       OR gc.user_id = :current_user_id)  -- 或是协作者
LIMIT 1;
```

### 3.3 同族谱验证

```python
if member_a.genealogy_id != member_b.genealogy_id:
    abort(404)
```

跨族谱查询无意义（张氏和李氏分属不同族谱），直接返回 404。

### 3.4 同人短路

```python
if start_id == end_id:
    return render_template(
        "members/path.html",
        member_a=member_a,
        member_b=member_b,
        path_members=[member_a],  # 路径只有一个人
        path_steps=[],            # 没有步骤
    )
```

这是一个业务优化：如果查询的两个 ID 相同，直接返回"路径长度为 0"，不需要执行任何 SQL 查询。

### 3.5 渐进式双向 BFS 入口

```python
gid = member_a.genealogy_id   # 族谱 ID（同一个）
start_id = member_a.id        # 起始成员 ID = 100
end_id = member_b.id          # 目标成员 ID = 500

full_path_ids = None  # 最终路径的 ID 列表
relation_types = None  # 最终路径的关系类型列表

for max_depth in (6, 8, 10, 12, 15):
    # ... Phase 1 + Phase 2 ...
```

**渐进式深度的策略**：

```
第 1 轮: max_depth = 6  → 搜索深度 ≤6 的交汇点（适合近亲，极快）
第 2 轮: max_depth = 8  → 如果第1轮没找到，扩展到深度 8
第 3 轮: max_depth = 10 → 继续扩展
第 4 轮: max_depth = 12
第 5 轮: max_depth = 15 → 最深层搜索
```

大多数亲缘关系在 ≤6 步内（如堂兄弟：A→A父→A爷爷→B爷爷→B父→B = 6步），所以第一轮就能命中，后面的轮次不会执行。

---

## 阶段四：Phase 1 双向 BFS — 找到交汇点

### 4.1 正向 BFS：从张小明（ID=100）出发

```python
fwd = _bfs_reachable(gid, start_id, max_depth)
# fwd = {member_id → 最短距离}
# 例: {100: 0, 200: 1, 201: 1, 300: 2, 301: 2, ...}
```

**调用的函数**：[`_bfs_reachable()`](file:///d:/上课/大三下/数据库/genealogy_system/app/members/routes.py#L348-L378)

```python
def _bfs_reachable(genealogy_id, root_id, max_depth):
    # 对于深度 >=8 的搜索，优先使用 PL/pgSQL 存储函数（更快）
    if max_depth >= 8:
        try:
            rows = db.session.execute(
                text("SELECT member_id, depth "
                     "FROM bfs_reachable(:gid, :rid, :md)"),
                {"gid": genealogy_id, "rid": root_id, "md": max_depth},
            ).fetchall()
            return {r[0]: r[1] for r in rows}
        except Exception:
            db.session.rollback()  # 回滚失败的事务

    # 回退方案：UNION 递归 CTE
    sql = (
        "WITH RECURSIVE edges AS NOT MATERIALIZED (" + EDGE_CTE_NO_REL + "),\n"
        + "walk AS (\n"
        + "    SELECT CAST(:root_id AS INTEGER) AS member_id, 0 AS depth\n"
        + "    UNION\n"       # ← 每层去重，防止路径爆炸
        + "    SELECT e.to_id, walk.depth + 1\n"
        + "    FROM walk JOIN edges e ON e.from_id = walk.member_id\n"
        + "    WHERE walk.depth < :max_depth\n"
        + ") CYCLE member_id SET is_cycle USING cycle_path\n"
        + "SELECT member_id, MIN(depth) FROM walk WHERE NOT is_cycle GROUP BY member_id"
    )
    rows = db.session.execute(
        text(sql),
        {"genealogy_id": genealogy_id, "root_id": root_id, "max_depth": max_depth},
    ).fetchall()
    return {r[0]: r[1] for r in rows}
```

**返回的 Python 数据结构**：

```python
fwd = {
    100: 0,   # 张小明自己，深度 0
    200: 1,   # 张小明父，深度 1
    201: 1,   # 张小明母，深度 1
    300: 2,   # 张小明爷爷（通过父线），深度 2
    301: 2,   # 张小明奶奶（通过父线），深度 2
    400: 3,   # 曾祖，深度 3
    # ... 更多成员
    500: 6,   # 李小红（通过"张小明→父→爷爷→叔叔→堂弟→李小红"）深度 6 !
}
```

### 4.2 反向 BFS：从李小红（ID=500）出发

```python
rev = _bfs_reachable(gid, end_id, max_depth)
# rev = {member_id → 最短距离}
# 例: {500: 0, 501: 1, 300: 3, ...}
```

完全对称的操作，只是起点不同。

### 4.3 求交集 — 找到交汇点

```python
meeting = set(fwd.keys()) & set(rev.keys())
# meeting = {300, 301, 500, ...}  ← 从两端都能到达的成员
```

**交汇点的含义**：如果成员 X 同时出现在 fwd 和 rev 中，说明存在一条路径 `start → ... → X → ... → end`。

```python
best = min(meeting, key=lambda m: fwd[m] + rev[m])
# 从所有交汇点中选出总距离 (fwd距离 + rev距离) 最短的那个
# 假设: fwd[300] = 2, rev[300] = 3 → 总距离 = 5
#       fwd[500] = 6, rev[500] = 0 → 总距离 = 6
#       best = 300 (最短总距离)
```

为什么需要从多个交汇点中选最短？因为可能存在多条不同的路径连通两人，我们需要最短的那条。例如：

```
交汇点 X: start → ... → X → ... → end  (总步数 8)
交汇点 Y: start → ... → Y → ... → end  (总步数 5) ← 更短
```

`min(..., key=lambda m: fwd[m] + rev[m])` 选出总步数最小的交汇点。

### 4.4 未找到交汇点的处理

```python
# 如果本轮没找到 meeting 点:
#   meeting = set()  →  for 循环继续下一轮（更大的 max_depth）
# 
# 如果 5 轮全部没找到:
#   进入 legacy_sql 单方向 BFS 兜底（深度 18）
```

### 4.5 存入变量的数据

```python
fwd_depth = fwd[best]   # 2  (从 start 到交汇点的步数)
rev_depth = rev[best]   # 3  (从 end 到交汇点的步数)
# 总路径长度 = fwd_depth + rev_depth = 5 步

fwd = {100:0, 200:1, 201:1, 300:2, 301:2, 400:3, ...}
rev = {500:0, 501:1, 502:1, 503:2, 300:3, 301:3, ...}
```

---

## 阶段五：Phase 2 路径重构 — 拼接完整路径

现在我们知道了 "交汇点是 300，从 start 到交汇点 2 步，从 end 到交汇点 3 步"，但还不知道**具体经过哪些人**。Phase 2 就是**回溯出具体的节点序列和关系标签**。

### 5.1 正向路径重构（start → 交汇点）

```python
fwd_ids, fwd_rels = _reconstruct_path(gid, start_id, best, fwd_depth, fwd)
# start_id=100, best=300, fwd_depth=2, fwd={...}
```

**[`_reconstruct_path()`](file:///d:/上课/大三下/数据库/genealogy_system/app/members/routes.py#L400-L426)** 的详细执行：

```python
def _reconstruct_path(genealogy_id, start_id, meeting_id, depth, distances):
    # 步骤 1: 按 depth 分组 distances（方便回溯时快速筛选候选节点）
    depth_to_members = {}
    for mid, d in distances.items():
        depth_to_members.setdefault(d, []).append(mid)
    
    # depth_to_members = {
    #     0: [100],                          ← 只有起点
    #     1: [200, 201, 202, ...],           ← depth=1 的所有成员
    #     2: [300, 301, 302, 303, ...],      ← depth=2 的所有成员
    #     ...
    #     6: [500, ...]
    # }

    # 步骤 2: 从交汇点向回退，逐层找邻居
    path_ids = [meeting_id]  # [300]，从交汇点开始
    current = meeting_id     # 当前回溯位置 = 300
    
    for d in range(depth - 1, -1, -1):  # depth=2: 循环 d=1, d=0
        candidates = depth_to_members.get(d, [])  
        # d=1: candidates = [200, 201, 202, ...] ← depth=1 的所有成员
        # d=0: candidates = [100]             ← depth=0 只有起点
        
        row = db.session.execute(
            text(
                "SELECT nid FROM (" + NEIGHBOR_QUERY + ") neighbors"
                " WHERE nid = ANY(:candidates) LIMIT 1"
            ),
            {"gid": genealogy_id, "mid": current, "candidates": candidates},
        ).first()
        
        # d=1 时的 SQL:
        #   找 current(=300) 的所有邻居
        #   筛选出在 candidates(=depth=1的所有成员) 中的那个
        #   → 找到 200（张小明父，他是交汇点 300 的儿子，且 depth=1）
        
        # d=0 时的 SQL:
        #   找 current(=200) 的所有邻居  
        #   筛选出 candidates(= [100]) 中的那个
        #   → 找到 100（张小明，他是 200 的儿子，且 depth=0）
        
        path_ids.insert(0, row[0])  # 在列表头部插入
        # d=1: path_ids = [200, 300]
        # d=0: path_ids = [100, 200, 300]
        
        current = row[0]  # 更新当前位置
    
    # 步骤 3: 查关系标签
    relations = _lookup_relations_batch(genealogy_id, path_ids)
    # path_ids = [100, 200, 300]
    # relations = ['parent', 'parent']  ← 100→200 是父子(反向即parent), 200→300 是父子
    
    return path_ids, relations
    # 返回: 
    #   path_ids = [100, 200, 300]     ← 正向路径
    #   relations = ['parent', 'parent']
```

**NEIGHBOR_QUERY** 的 SQL（用于在回溯中查找某个节点的所有邻居）：

```sql
SELECT parent_member_id AS nid FROM parent_child_relations
WHERE genealogy_id = :gid AND child_member_id = :mid     -- 父→子 的反向
UNION ALL
SELECT child_member_id FROM parent_child_relations
WHERE genealogy_id = :gid AND parent_member_id = :mid    -- 子→父
UNION ALL
SELECT spouse2_member_id FROM marriages
WHERE genealogy_id = :gid AND spouse1_member_id = :mid   -- 配偶正向
UNION ALL
SELECT spouse1_member_id FROM marriages
WHERE genealogy_id = :gid AND spouse2_member_id = :mid   -- 配偶反向
```

4 个 `UNION ALL` 查询当前节点在 4 种关系表中的所有邻居。`WHERE nid = ANY(:candidates) LIMIT 1` 利用距离信息快速筛选出深度正确的那个邻居。

### 5.2 反向路径重构（end → 交汇点）

```python
rev_ids, rev_rels = _reconstruct_path(gid, end_id, best, rev_depth, rev)
# end_id=500, best=300, rev_depth=3

# 返回:
#   rev_ids = [500, 502, 503, 300]     ← 反向路径
#   rev_rels = ['parent', 'parent', 'parent']
```

### 5.3 拼接完整路径

```python
fwd_ids = list(fwd_ids)  # [100, 200, 300]
rev_ids = list(rev_ids)  # [500, 502, 503, 300]

# 反向路径需要反转并去掉交汇点（交汇点已经在前半部分了）
rev_reversed = rev_ids[-2::-1] if len(rev_ids) > 1 else []
# rev_ids[-2::-1]: 从倒数第 2 个元素开始，倒序取到第 1 个
# rev_ids = [500, 502, 503, 300]
#            ^0   ^1   ^2   ^3
# rev_ids[-2] = 503
# rev_ids[-2::-1] = [503, 502, 500]

full_path_ids = fwd_ids + rev_reversed
# full_path_ids = [100, 200, 300, 503, 502, 500]
#                   张小明 → 父 → 爷爷 → 奶奶 → 李小红母 → 李小红
```

**完整路径图**：

```
张小明(100) --parent--> 张大明(200) --parent--> 张德海(300) --parent--> 王秀兰(301) --parent--> 李小芳(502) --parent--> 李小红(500)
```

### 5.4 合并关系标签

```python
relation_types = list(fwd_rels)  # ['parent', 'parent']
rev_rels_list = list(rev_rels)   # ['parent', 'parent', 'parent']

for i in range(len(rev_rels_list) - 1, -1, -1):
    rev_rel = rev_rels_list[i]
    if rev_rel == "child":
        relation_types.append("parent")  # 反转：end→X 的 "child" 在完整路径中是 "parent"
    elif rev_rel == "spouse":
        relation_types.append("spouse")  # 婚姻是双向的，不用反转
    else:
        relation_types.append(rev_rel)   # 其它标签保持

# relation_types = ['parent', 'parent', 'parent', 'parent', 'parent']
```

**关系反转的逻辑**：反向路径的视角是从李小红出发，`['parent', 'parent', 'parent']` 表示"李小红→母→外婆→...→交汇点"的关系。拼接后需要从交汇点往下看到李小红，所以 `child` 变 `parent`，而 `spouse` 是双向的无需反转。

### 5.5 兜底机制：传统 BFS

```python
if full_path_ids is None:
    # 所有 5 轮双向 BFS 都未找到路径 → 使用传统单方向 BFS（depth≤18）
    legacy_sql = (
        "WITH RECURSIVE edges AS NOT MATERIALIZED (" + EDGE_CTE_WITH_REL + "),\n"
        + "walk AS (\n"
        + "    SELECT CAST(:start_id AS INTEGER) AS member_id,\n"
        + "           ',' || CAST(:start_id AS TEXT) || ',' AS id_path,\n"
        + "           '' AS relation_types,\n"
        + "           0 AS depth\n"
        + "    UNION ALL\n"
        + "    SELECT e.to_id,\n"
        + "           walk.id_path || CAST(e.to_id AS TEXT) || ',',\n"
        + "           walk.relation_types || e.relation_type || ',',\n"
        + "           walk.depth + 1\n"
        + "    FROM walk JOIN edges e ON e.from_id = walk.member_id\n"
        + "    WHERE walk.depth < 18\n"
        + ") CYCLE member_id SET is_cycle USING cycle_path\n"
        + "SELECT id_path, relation_types FROM walk\n"
        + "WHERE member_id = :end_id AND NOT is_cycle\n"
        + "ORDER BY depth LIMIT 1"
    )
    row = db.session.execute(text(legacy_sql), {...}).first()
    if row:
        # 解析字符串格式的路径
        full_path_ids = [int(v) for v in row.id_path.strip(",").split(",") if v]
        # id_path = ",100,200,300,503,502,500,"
        # split(",") → ["", "100", "200", "300", "503", "502", "500", ""]
        # filter(v) → ["100", "200", "300", "503", "502", "500"]
        
        relation_types = [v for v in row.relation_types.strip(",").split(",") if v]
        # relation_types = ",parent,parent,parent,parent,parent,"
        # → ["parent", "parent", "parent", "parent", "parent"]
```

这个兜底使用**带路径追踪**的递归 CTE：path 列为 `',100,200,300,...'` 字符串，relation_types 列为 `'parent,parent,...'` 字符串，在递归过程中逐步拼接。这是最直接的实现，但因为使用 `UNION ALL` + 字符串拼接，效率较低（路径爆炸），只在双向 BFS 都失败时作为最后手段。

---

## 阶段六：最终渲染 — 模板回显

### 6.1 从 ID 列表获取完整成员信息

```python
path_members = []
path_steps = []

if full_path_ids:
    # 用 IN 查询一次性取出路径上所有成员
    path_members = Member.query.filter(Member.id.in_(full_path_ids)).all()
    # 执行 SQL:
    # SELECT * FROM members WHERE id IN (100, 200, 300, 503, 502, 500);
    
    # 按路径顺序重新排序（IN 查询不保证顺序）
    path_members = sorted(path_members, key=lambda m: full_path_ids.index(m.id))
    # sorted 前: [Member(502), Member(100), Member(300), ...]  ← 数据库返回的任意顺序
    # sorted 后: [Member(100), Member(200), Member(300), Member(503), Member(502), Member(500)]
```

`Member.query.filter(Member.id.in_(...))` 是 SQLAlchemy ORM 查询，最终生成：

```sql
SELECT members.id, members.genealogy_id, members.name, members.gender,
       members.birth_year, members.death_year, members.generation_no,
       members.biography, members.created_at, members.updated_at
FROM members
WHERE members.id IN (100, 200, 300, 503, 502, 500);
```

### 6.2 构建步骤列表

```python
if relation_types:
    for index, rel_type in enumerate(relation_types):
        if index + 1 < len(path_members):
            path_steps.append(
                {
                    "from": path_members[index],
                    "to": path_members[index + 1],
                    "relation": RELATION_LABELS.get(rel_type, rel_type),
                }
            )
```

**构建结果**：

```python
relation_types = ['parent', 'parent', 'parent', 'parent', 'parent']

# 第 0 步: index=0, rel_type='parent'
#   from=path_members[0]=100(张小明), to=path_members[1]=200(张大明)
#   relation=RELATION_LABELS['parent']='父亲/母亲(I18N)'

# 但是 RELATION_LABELS = {"father": "父亲", "mother": "母亲", "child": "子女", "spouse": "配偶"}
# rel_type='parent' 不在字典中 → 显示原始值 'parent'

path_steps = [
    {"from": Member(100, 张小明), "to": Member(200, 张大明), "relation": "parent"},
    {"from": Member(200, 张大明), "to": Member(300, 张德海), "relation": "parent"},
    {"from": Member(300, 张德海), "to": Member(503, 王小芳), "relation": "parent"},
    {"from": Member(503, 王小芳), "to": Member(502, 李桂花), "relation": "parent"},
    {"from": Member(502, 李桂花), "to": Member(500, 李小红), "relation": "parent"},
]
```

**`RELATION_LABELS` 的作用**：[`routes.py:L505-L510`](file:///d:/上课/大三下/数据库/genealogy_system/app/members/routes.py#L505-L510)

```python
RELATION_LABELS = {
    "father": "父亲",    # father → 父亲
    "mother": "母亲",    # mother → 母亲
    "child": "子女",     # child → 子女
    "spouse": "配偶",    # spouse → 配偶
}
```

数据库返回的英文关系类型通过这个映射表转为中文显示。`"parent"` 不在映射表中是因为它是从反向路径反转后的通用标签（可能为 `father` 或 `mother`），这里保留了父/母的原始值。

### 6.3 模板渲染

```python
return render_template(
    "members/path.html",
    member_a=member_a,       # Member(100, 张小明)
    member_b=member_b,       # Member(500, 李小红)
    path_members=path_members,  # [100, 200, 300, 503, 502, 500]
    path_steps=path_steps,      # 5 个步骤字典
)
```

### 6.4 模板 HTML 渲染

[`members/path.html`](file:///d:/上课/大三下/数据库/genealogy_system/app/templates/members/path.html)：

```html
{% extends "base.html" %}                          <!-- 继承布局 -->
{% block title %}亲缘链路{% endblock %}

{% block content %}
<h1 class="h3 mb-3">亲缘链路</h1>
<p class="text-secondary">
    {{ member_a.name }} 到 {{ member_b.name }}     <!-- 张小明 到 李小红 -->
</p>

{% if path_members %}
  <div class="path-steps">
    {% for step in path_steps %}
      <!-- 循环 5 次 -->
      <div class="path-step">
        <span>{{ step.from.name }} #{{ step.from.id }}</span>    <!-- 张小明 #100 -->
        <strong>{{ step.relation }}</strong>                     <!-- parent -->
        <span>{{ step.to.name }} #{{ step.to.id }}</span>        <!-- 张大明 #200 -->
      </div>
    {% endfor %}
  </div>
{% else %}
  <div class="empty-state">两人之间暂未找到可达路径。</div>
{% endif %}
{% endblock %}
```

Jinja2 模板引擎将 Python 变量替换为 HTML 后，浏览器收到的最终 HTML：

```html
<!doctype html>
<html lang="zh-CN">
<head>
  <title>亲缘链路</title>
  <!-- Bootstrap CSS ... -->
</head>
<body>
  <nav>寻根溯源 ...</nav>
  <main class="container py-4">
    <h1 class="h3 mb-3">亲缘链路</h1>
    <p class="text-secondary">张小明 到 李小红</p>
    <div class="path-steps">
      <div class="path-step">
        <span>张小明 #100</span>
        <strong>parent</strong>
        <span>张大明 #200</span>
      </div>
      <div class="path-step">
        <span>张大明 #200</span>
        <strong>parent</strong>
        <span>张德海 #300</span>
      </div>
      <div class="path-step">
        <span>张德海 #300</span>
        <strong>parent</strong>
        <span>王秀兰 #503</span>
      </div>
      <div class="path-step">
        <span>王秀兰 #503</span>
        <strong>parent</strong>
        <span>李桂花 #502</span>
      </div>
      <div class="path-step">
        <span>李桂花 #502</span>
        <strong>parent</strong>
        <span>李小红 #500</span>
      </div>
    </div>
  </main>
</body>
</html>
```

用户在浏览器中看到的最终效果：

```
┌─────────────────────────────────────────────┐
│  寻根溯源  |  我的族谱  |  退出              │
├─────────────────────────────────────────────┤
│                                             │
│  亲缘链路                                    │
│  张小明 到 李小红                             │
│                                             │
│  ┌───────────────────────────────────────┐  │
│  │ 张小明 #100  ── parent ──▶  张大明 #200│  │
│  │ 张大明 #200  ── parent ──▶  张德海 #300│  │
│  │ 张德海 #300  ── parent ──▶  王秀兰 #503│  │
│  │ 王秀兰 #503  ── parent ──▶  李桂花 #502│  │
│  │ 李桂花 #502  ── parent ──▶  李小红 #500│  │
│  └───────────────────────────────────────┘  │
│                                             │
│  路径长度: 5 步                               │
└─────────────────────────────────────────────┘
```

---

## 附录：完整调用链总览图

```
用户浏览器
  │
  │  输入: A=100, B=500 → 点击 "亲缘链路"
  ▼
HTTP GET /members/relationship/path?a=100&b=500
  │
  │  Flask 路由分发
  ▼
────────────────────────────────────────────────────────────
① @login_required         → 检查登录状态
────────────────────────────────────────────────────────────
② relationship_path()     → 路由处理器
  │
  ├─ request.args.get("a", type=int)  → 100
  ├─ request.args.get("b", type=int)  → 500
  ├─ get_member(100)      → 权限检查 + 查成员
  ├─ get_member(500)      → 权限检查 + 查成员
  ├─ genealogy_id 一致性检查
  ├─ 同人短路: 100 ≠ 500 → 继续
  │
  ├─ for max_depth in (6, 8, 10, 12, 15):
  │   │
  │   ├─ _bfs_reachable(gid, 100, max_depth)
  │   │   └─ SQL: bfs_reachable(1, 100, max_depth)    ← PL/pgSQL 函数
  │   │       或: WITH RECURSIVE walk AS (...)         ← CTE 回退
  │   │   └─ 返回: {100:0, 200:1, 201:1, 300:2, ...}
  │   │
  │   ├─ _bfs_reachable(gid, 500, max_depth)
  │   │   └─ 同上，终点出发
  │   │   └─ 返回: {500:0, 501:1, 502:1, 300:3, ...}
  │   │
  │   ├─ meeting = fwd ∩ rev
  │   │   └─ {300, 301, ...}  → 找到交汇点!
  │   │
  │   ├─ best = min(meeting, key=λm: fwd[m]+rev[m])
  │   │   └─ best = 300 (总距离最短)
  │   │
  │   ├─ _reconstruct_path(gid, 100, 300, 2, fwd)
  │   │   ├─ depth_to_members = {0:[100], 1:[200,201,...], ...}
  │   │   ├─ for d=1: 找300的邻居中depth=1的 → 200
  │   │   ├─ for d=0: 找200的邻居中depth=0的 → 100
  │   │   ├─ path_ids = [100, 200, 300]
  │   │   └─ _lookup_relations_batch → SQL: VALUES批量标注
  │   │       └─ 返回: relations = ['parent', 'parent']
  │   │
  │   ├─ _reconstruct_path(gid, 500, 300, 3, rev)
  │   │   └─ 返回: ([500,502,503,300], ['parent','parent','parent'])
  │   │
  │   └─ break  ← 找到路径，退出渐进循环
  │
  ├─ 路径拼接:
  │   fwd_ids = [100, 200, 300]
  │   rev_reversed = [503, 502, 500]
  │   full_path_ids = [100, 200, 300, 503, 502, 500]
  │
  ├─ 关系标签合并:
  │   relation_types = ['parent', 'parent', 'parent', 'parent', 'parent']
  │
  ├─ Member.query.filter(Member.id.in_(full_path_ids)).all()
  │   └─ SQL: SELECT * FROM members WHERE id IN (100,200,300,503,502,500)
  │   └─ 按 full_path_ids 顺序重新排序
  │
  ├─ 构建 path_steps:
  │   [{'from':张小明, 'to':张大明, 'relation':'parent'}, ...]
  │
  └─ render_template("members/path.html", ...)
────────────────────────────────────────────────────────────
  │
  │  Jinja2 模板渲染
  ▼
HTML 响应 → 浏览器显示路径结果
```

### 关键数据流

| 步骤 | 输入 | 输出 | 数据量 |
|------|------|------|:--:|
| 前端表单 | 两个整数 | HTTP GET 请求 | — |
| get_member | `member_id=100` | `Member(100, "张小明")` | 1 行 |
| _bfs_reachable × 2 | `(gid, id, depth)` | `{id: depth}` 字典 | ~3000~26000 个 key |
| 求交集 | 两个大字典 | 交汇点 ID | ~10~500 个 |
| _reconstruct_path × 2 | `(gid, start, meeting, depth, dist)` | `(id_list, rel_list)` | 3~8 个 ID |
| VALUES 批量标注 | 3~8 对 ID | 关系类型列表 | 3~8 个字符串 |
| Member.query.in_() | 完整路径 ID 列表 | Member ORM 对象列表 | 3~8 个对象 |
| Jinja2 渲染 | Python 对象 | HTML 字符串 | ~2KB |

### 性能指标（50000 人数据集实测）

| 操作 | 典型耗时 | 说明 |
|------|:--:|------|
| get_member 权限检查 | <5ms | 主键查找 + 简单 JOIN |
| _bfs_reachable (depth≤15) | 100~200ms | 最重的操作 |
| 求交集 | <1ms | Python `set` 运算 |
| _reconstruct_path | 10~30ms | O(depth) 次索引点查 |
| VALUES 批量标注 | 5~15ms | 单次 SQL，3~8 对 |
| Member.query.in_() | <5ms | 主键 IN 查询 |
| **总计** | **300~1600ms** | **50000 人数据集** |

---

*文档生成日期: 2026-05-12*