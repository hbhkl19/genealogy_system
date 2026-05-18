from collections import deque

from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError
from sqlalchemy import text

from app.extensions import db
from app.models import Genealogy, Marriage, Member, ParentChildRelation, accessible_genealogy_query


bp = Blueprint("members", __name__)


def parse_optional_int(value):
    value = (value or "").strip()
    if not value:
        return None
    return int(value)


def update_member_from_form(member):
    member.name = request.form.get("name", "").strip()
    member.gender = request.form.get("gender", "unknown")
    member.birth_year = parse_optional_int(request.form.get("birth_year"))
    member.death_year = parse_optional_int(request.form.get("death_year"))
    member.biography = request.form.get("biography", "").strip()
    member.generation_no = parse_optional_int(request.form.get("generation_no")) or 1


def get_member(member_id):
    member = db.session.get(Member, member_id)
    if member is None:
        abort(404)
    genealogy = accessible_genealogy_query(current_user).filter(Genealogy.id == member.genealogy_id).first()
    if genealogy is None:
        abort(404)
    return member


def get_genealogy_member(genealogy_id, member_id):
    if member_id is None:
        return None
    member = db.session.get(Member, member_id)
    if member is None or member.genealogy_id != genealogy_id:
        return None
    return member


def ancestor_payload(member):
    has_parents = db.session.execute(
        text(
            """
            SELECT EXISTS (
                SELECT 1
                FROM parent_child_relations
                WHERE child_member_id = :member_id
            )
            """
        ),
        {"member_id": member.id},
    ).scalar()
    return {
        "id": member.id,
        "name": member.name,
        "gender": member.gender,
        "birth_year": member.birth_year,
        "death_year": member.death_year,
        "generation_no": member.generation_no,
        "has_parents": bool(has_parents),
    }


def validate_parent_child(genealogy_id, parent_id, child_id, parent_role):
    parent = get_genealogy_member(genealogy_id, parent_id)
    child = get_genealogy_member(genealogy_id, child_id)
    if parent is None or child is None:
        return "父母和子女必须属于同一个族谱。"
    if parent.id == child.id:
        return "成员不能成为自己的父母或子女。"
    if parent_role not in {"father", "mother"}:
        return "父母角色只能是 father 或 mother。"
    if parent.birth_year and child.birth_year and parent.birth_year >= child.birth_year:
        return "父母出生年必须早于子女出生年。"
    if parent.generation_no >= child.generation_no:
        return "父母代数必须小于子女代数。"
    existing_role = ParentChildRelation.query.filter_by(
        child_member_id=child.id,
        parent_role=parent_role,
    ).first()
    if existing_role and existing_role.parent_member_id != parent.id:
        return "同一成员最多只能有一个父亲和一个母亲。"
    return None


def add_parent_child(genealogy_id, parent_id, child_id, parent_role):
    error = validate_parent_child(genealogy_id, parent_id, child_id, parent_role)
    if error:
        flash(error, "warning")
        return False

    exists = ParentChildRelation.query.filter_by(
        parent_member_id=parent_id,
        child_member_id=child_id,
    ).first()
    if exists:
        flash("该父母子女关系已经存在。", "info")
        return False

    db.session.add(
        ParentChildRelation(
            genealogy_id=genealogy_id,
            parent_member_id=parent_id,
            child_member_id=child_id,
            parent_role=parent_role,
        )
    )
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        flash("关系保存失败，请检查是否违反唯一约束。", "danger")
        return False
    flash("父母子女关系已保存。", "success")
    return True


def add_marriage(genealogy_id, member_id, spouse_id):
    member = get_genealogy_member(genealogy_id, member_id)
    spouse = get_genealogy_member(genealogy_id, spouse_id)
    if member is None or spouse is None:
        flash("配偶双方必须属于同一个族谱。", "warning")
        return False
    if member.id == spouse.id:
        flash("成员不能与自己成婚。", "warning")
        return False

    spouse1_id, spouse2_id = sorted([member.id, spouse.id])
    exists = Marriage.query.filter_by(
        spouse1_member_id=spouse1_id,
        spouse2_member_id=spouse2_id,
    ).first()
    if exists:
        flash("该婚姻关系已经存在。", "info")
        return False

    married_year = parse_optional_int(request.form.get("married_year"))
    ended_year = parse_optional_int(request.form.get("ended_year"))
    if married_year and ended_year and ended_year < married_year:
        flash("婚姻结束年份不能早于结婚年份。", "warning")
        return False

    db.session.add(
        Marriage(
            genealogy_id=genealogy_id,
            spouse1_member_id=spouse1_id,
            spouse2_member_id=spouse2_id,
            married_year=married_year,
            ended_year=ended_year,
        )
    )
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        flash("婚姻关系保存失败，请检查是否重复。", "danger")
        return False
    flash("婚姻关系已保存。", "success")
    return True


@bp.route("/genealogies/<int:genealogy_id>/members/new", methods=["GET", "POST"])
@login_required
def create(genealogy_id):
    genealogy = accessible_genealogy_query(current_user).filter(Genealogy.id == genealogy_id).first()
    if genealogy is None:
        abort(404)

    if request.method == "POST":
        member = Member(
            genealogy_id=genealogy_id,
        )
        update_member_from_form(member)
        if not member.name:
            flash("成员姓名不能为空。", "warning")
            return render_template("members/form.html", genealogy=genealogy, member=member)
        db.session.add(member)
        db.session.commit()
        flash("成员已添加。", "success")
        return redirect(url_for("genealogies.members", id=genealogy_id))

    return render_template("members/form.html", genealogy=genealogy, member=None)


@bp.route("/members/<int:id>/edit", methods=["GET", "POST"])
@login_required
def edit(id):
    member = get_member(id)
    genealogy = db.session.get(Genealogy, member.genealogy_id)

    if request.method == "POST":
        update_member_from_form(member)
        if not member.name:
            flash("成员姓名不能为空。", "warning")
            return render_template("members/form.html", genealogy=genealogy, member=member)
        db.session.commit()
        flash("成员信息已更新。", "success")
        return redirect(url_for("genealogies.members", id=member.genealogy_id))

    return render_template("members/form.html", genealogy=genealogy, member=member)


@bp.route("/members/<int:id>/delete", methods=["POST"])
@login_required
def delete(id):
    member = get_member(id)
    genealogy_id = member.genealogy_id
    db.session.delete(member)
    db.session.commit()
    flash("成员已删除，相关父母子女和婚姻关系已同步移除。", "success")
    return redirect(url_for("genealogies.members", id=genealogy_id))


@bp.route("/members/<int:id>/relations", methods=["GET", "POST"])
@login_required
def relations(id):
    member = get_member(id)
    genealogy_id = member.genealogy_id

    if request.method == "POST":
        action = request.form.get("action")
        if action == "add_parent":
            parent_id = request.form.get("parent_member_id", type=int)
            parent_role = request.form.get("parent_role", "")
            add_parent_child(genealogy_id, parent_id, member.id, parent_role)
        elif action == "add_child":
            child_id = request.form.get("child_member_id", type=int)
            parent_role = request.form.get("parent_role", "")
            add_parent_child(genealogy_id, member.id, child_id, parent_role)
        elif action == "delete_relation":
            relation_id = request.form.get("relation_id", type=int)
            relation = ParentChildRelation.query.filter_by(id=relation_id, genealogy_id=genealogy_id).first()
            if relation:
                db.session.delete(relation)
                db.session.commit()
                flash("父母子女关系已移除。", "success")
        elif action == "add_marriage":
            spouse_id = request.form.get("spouse_member_id", type=int)
            add_marriage(genealogy_id, member.id, spouse_id)
        elif action == "delete_marriage":
            marriage_id = request.form.get("marriage_id", type=int)
            marriage = Marriage.query.filter_by(id=marriage_id).first()
            if marriage and member.id in {marriage.spouse1_member_id, marriage.spouse2_member_id}:
                db.session.delete(marriage)
                db.session.commit()
                flash("婚姻关系已移除。", "success")
        return redirect(url_for("members.relations", id=member.id))

    parent_relations = (
        ParentChildRelation.query.filter_by(child_member_id=member.id)
        .order_by(ParentChildRelation.parent_role)
        .all()
    )
    child_relations = (
        ParentChildRelation.query.filter_by(parent_member_id=member.id)
        .order_by(ParentChildRelation.id)
        .all()
    )
    marriages = (
        Marriage.query.filter(
            (Marriage.spouse1_member_id == member.id) | (Marriage.spouse2_member_id == member.id),
        )
        .order_by(Marriage.id)
        .all()
    )
    return render_template(
        "members/relations.html",
        member=member,
        parent_relations=parent_relations,
        child_relations=child_relations,
        marriages=marriages,
        genealogy_id=genealogy_id,
    )


@bp.route("/members/<int:id>/ancestors")
@login_required
def ancestors(id):
    member = get_member(id)
    parents = (
        Member.query.join(ParentChildRelation, ParentChildRelation.parent_member_id == Member.id)
        .filter(ParentChildRelation.child_member_id == member.id)
        .order_by(ParentChildRelation.parent_role, Member.id)
        .limit(2)
        .all()
    )
    return render_template(
        "members/ancestors.html",
        member=member,
        parents=[ancestor_payload(parent) for parent in parents],
    )


@bp.route("/members/<int:id>/ancestor-parents")
@login_required
def ancestor_parents(id):
    member = get_member(id)
    parents = (
        Member.query.join(ParentChildRelation, ParentChildRelation.parent_member_id == Member.id)
        .filter(ParentChildRelation.child_member_id == member.id)
        .order_by(ParentChildRelation.parent_role, Member.id)
        .limit(2)
        .all()
    )
    return jsonify({"parents": [ancestor_payload(parent) for parent in parents]})


@bp.route("/members/<int:id>/descendants")
@login_required
def descendants(id):
    member = get_member(id)
    sql = """
        WITH RECURSIVE descendants AS (
            SELECT
                p.child_member_id AS member_id,
                1 AS depth
            FROM parent_child_relations p
            WHERE p.parent_member_id = :member_id
            UNION
            SELECT
                p.child_member_id,
                d.depth + 1
            FROM parent_child_relations p
            JOIN descendants d ON p.parent_member_id = d.member_id
            WHERE d.depth < 12
        )
        SELECT m.id, m.name, m.gender, m.generation_no, descendants.depth
        FROM descendants
        JOIN members m ON m.id = descendants.member_id
        ORDER BY descendants.depth, m.id
    """
    rows = db.session.execute(text(sql), {"member_id": id}).mappings().all()
    return render_template("members/descendants.html", member=member, rows=rows)


EDGE_CTE_NO_REL = """
    SELECT p.parent_member_id AS from_id, p.child_member_id AS to_id
    FROM parent_child_relations p
    JOIN members parent_member ON parent_member.id = p.parent_member_id
    JOIN members child_member ON child_member.id = p.child_member_id
    WHERE p.genealogy_id = ANY(:genealogy_ids)
      AND parent_member.genealogy_id = ANY(:genealogy_ids)
      AND child_member.genealogy_id = ANY(:genealogy_ids)
    UNION ALL
    SELECT p.child_member_id, p.parent_member_id
    FROM parent_child_relations p
    JOIN members parent_member ON parent_member.id = p.parent_member_id
    JOIN members child_member ON child_member.id = p.child_member_id
    WHERE p.genealogy_id = ANY(:genealogy_ids)
      AND parent_member.genealogy_id = ANY(:genealogy_ids)
      AND child_member.genealogy_id = ANY(:genealogy_ids)
    UNION ALL
    SELECT m.spouse1_member_id, m.spouse2_member_id
    FROM marriages m
    JOIN members spouse1 ON spouse1.id = m.spouse1_member_id
    JOIN members spouse2 ON spouse2.id = m.spouse2_member_id
    WHERE m.genealogy_id = ANY(:genealogy_ids)
      AND spouse1.genealogy_id = ANY(:genealogy_ids)
      AND spouse2.genealogy_id = ANY(:genealogy_ids)
    UNION ALL
    SELECT m.spouse2_member_id, m.spouse1_member_id
    FROM marriages m
    JOIN members spouse1 ON spouse1.id = m.spouse1_member_id
    JOIN members spouse2 ON spouse2.id = m.spouse2_member_id
    WHERE m.genealogy_id = ANY(:genealogy_ids)
      AND spouse1.genealogy_id = ANY(:genealogy_ids)
      AND spouse2.genealogy_id = ANY(:genealogy_ids)
"""

EDGE_CTE_WITH_REL = """
    SELECT p.parent_member_id AS from_id, p.child_member_id AS to_id, 'child' AS relation_type
    FROM parent_child_relations p
    JOIN members parent_member ON parent_member.id = p.parent_member_id
    JOIN members child_member ON child_member.id = p.child_member_id
    WHERE p.genealogy_id = ANY(:genealogy_ids)
      AND parent_member.genealogy_id = ANY(:genealogy_ids)
      AND child_member.genealogy_id = ANY(:genealogy_ids)
    UNION ALL
    SELECT p.child_member_id, p.parent_member_id, p.parent_role
    FROM parent_child_relations p
    JOIN members parent_member ON parent_member.id = p.parent_member_id
    JOIN members child_member ON child_member.id = p.child_member_id
    WHERE p.genealogy_id = ANY(:genealogy_ids)
      AND parent_member.genealogy_id = ANY(:genealogy_ids)
      AND child_member.genealogy_id = ANY(:genealogy_ids)
    UNION ALL
    SELECT m.spouse1_member_id, m.spouse2_member_id, 'spouse'
    FROM marriages m
    JOIN members spouse1 ON spouse1.id = m.spouse1_member_id
    JOIN members spouse2 ON spouse2.id = m.spouse2_member_id
    WHERE m.genealogy_id = ANY(:genealogy_ids)
      AND spouse1.genealogy_id = ANY(:genealogy_ids)
      AND spouse2.genealogy_id = ANY(:genealogy_ids)
    UNION ALL
    SELECT m.spouse2_member_id, m.spouse1_member_id, 'spouse'
    FROM marriages m
    JOIN members spouse1 ON spouse1.id = m.spouse1_member_id
    JOIN members spouse2 ON spouse2.id = m.spouse2_member_id
    WHERE m.genealogy_id = ANY(:genealogy_ids)
      AND spouse1.genealogy_id = ANY(:genealogy_ids)
      AND spouse2.genealogy_id = ANY(:genealogy_ids)
"""


def accessible_genealogy_ids():
    return [row.id for row in accessible_genealogy_query(current_user).with_entities(Genealogy.id).all()]


def _bfs_reachable(genealogy_ids, root_id, max_depth):
    """Phase 1: fast BFS returning {member_id: min_depth} using UNION-based CTE."""
    sql = (
        "WITH RECURSIVE edges AS NOT MATERIALIZED ("
        + EDGE_CTE_NO_REL + "),\n"
        + "walk AS (\n"
        + "    SELECT CAST(:root_id AS INTEGER) AS member_id, 0 AS depth\n"
        + "    UNION\n"
        + "    SELECT e.to_id, walk.depth + 1\n"
        + "    FROM walk JOIN edges e ON e.from_id = walk.member_id\n"
        + "    WHERE walk.depth < :max_depth\n"
        + ") CYCLE member_id SET is_cycle USING cycle_path\n"
        + "SELECT member_id, MIN(depth) FROM walk WHERE NOT is_cycle GROUP BY member_id"
    )
    rows = db.session.execute(
        text(sql),
        {"genealogy_ids": genealogy_ids, "root_id": root_id, "max_depth": max_depth},
    ).fetchall()
    return {r[0]: r[1] for r in rows}


def _is_sqlite():
    return db.session.get_bind().dialect.name == "sqlite"


def _sqlite_shortest_path(genealogy_ids, start_id, end_id, max_depth=18):
    """SQLite test fallback for the PostgreSQL-optimized kinship search."""
    graph = {}
    parent_child_rows = ParentChildRelation.query.filter(
        ParentChildRelation.genealogy_id.in_(genealogy_ids)
    ).all()
    for row in parent_child_rows:
        parent = db.session.get(Member, row.parent_member_id)
        child = db.session.get(Member, row.child_member_id)
        if parent.genealogy_id not in genealogy_ids or child.genealogy_id not in genealogy_ids:
            continue
        graph.setdefault(row.parent_member_id, []).append((row.child_member_id, "child"))
        graph.setdefault(row.child_member_id, []).append((row.parent_member_id, row.parent_role))

    marriage_rows = Marriage.query.filter(Marriage.genealogy_id.in_(genealogy_ids)).all()
    for row in marriage_rows:
        spouse1 = db.session.get(Member, row.spouse1_member_id)
        spouse2 = db.session.get(Member, row.spouse2_member_id)
        if spouse1.genealogy_id not in genealogy_ids or spouse2.genealogy_id not in genealogy_ids:
            continue
        graph.setdefault(row.spouse1_member_id, []).append((row.spouse2_member_id, "spouse"))
        graph.setdefault(row.spouse2_member_id, []).append((row.spouse1_member_id, "spouse"))

    queue = deque([(start_id, [start_id], [])])
    visited = {start_id}
    while queue:
        member_id, path_ids, relation_types = queue.popleft()
        if member_id == end_id:
            return path_ids, relation_types
        if len(relation_types) >= max_depth:
            continue
        for next_id, relation_type in graph.get(member_id, []):
            if next_id in visited:
                continue
            visited.add(next_id)
            queue.append((next_id, path_ids + [next_id], relation_types + [relation_type]))
    return None, None


NEIGHBOR_QUERY = """
    SELECT parent_member_id AS nid
    FROM parent_child_relations
    WHERE genealogy_id = ANY(:gids) AND child_member_id = :mid
    UNION ALL
    SELECT child_member_id
    FROM parent_child_relations
    WHERE genealogy_id = ANY(:gids) AND parent_member_id = :mid
    UNION ALL
    SELECT spouse2_member_id
    FROM marriages
    WHERE genealogy_id = ANY(:gids) AND spouse1_member_id = :mid
    UNION ALL
    SELECT spouse1_member_id
    FROM marriages
    WHERE genealogy_id = ANY(:gids) AND spouse2_member_id = :mid
"""


NEIGHBORS_FOR_FRONTIER_QUERY = """
    SELECT p.child_member_id AS from_id, p.parent_member_id AS to_id, p.parent_role AS relation_type
    FROM parent_child_relations p
    JOIN members parent_member ON parent_member.id = p.parent_member_id
    WHERE p.genealogy_id = ANY(:gids)
      AND p.child_member_id = ANY(:frontier)
      AND parent_member.genealogy_id = ANY(:gids)
    UNION ALL
    SELECT p.parent_member_id, p.child_member_id, 'child'
    FROM parent_child_relations p
    JOIN members child_member ON child_member.id = p.child_member_id
    WHERE p.genealogy_id = ANY(:gids)
      AND p.parent_member_id = ANY(:frontier)
      AND child_member.genealogy_id = ANY(:gids)
    UNION ALL
    SELECT m.spouse1_member_id, m.spouse2_member_id, 'spouse'
    FROM marriages m
    JOIN members spouse2 ON spouse2.id = m.spouse2_member_id
    WHERE m.genealogy_id = ANY(:gids)
      AND m.spouse1_member_id = ANY(:frontier)
      AND spouse2.genealogy_id = ANY(:gids)
    UNION ALL
    SELECT m.spouse2_member_id, m.spouse1_member_id, 'spouse'
    FROM marriages m
    JOIN members spouse1 ON spouse1.id = m.spouse1_member_id
    WHERE m.genealogy_id = ANY(:gids)
      AND m.spouse2_member_id = ANY(:frontier)
      AND spouse1.genealogy_id = ANY(:gids)
"""


def _fetch_frontier_neighbors(genealogy_ids, frontier):
    if not frontier:
        return []
    return db.session.execute(
        text(NEIGHBORS_FOR_FRONTIER_QUERY),
        {"gids": genealogy_ids, "frontier": list(frontier)},
    ).mappings().all()


def _reverse_relation_label(relation_type):
    if relation_type == "child":
        return "parent"
    return relation_type


def _build_path_from_parent_map(parent_map, member_id):
    ids = [member_id]
    rels = []
    current = member_id
    while parent_map[current][0] is not None:
        prev_id, relation_type = parent_map[current]
        ids.insert(0, prev_id)
        rels.insert(0, relation_type)
        current = prev_id
    return ids, rels


def _bidirectional_shortest_path(genealogy_ids, start_id, end_id, max_depth=30):
    """Index-friendly bidirectional BFS.

    The old recursive CTE expands against the full edge set. This version only
    queries neighbors for the current frontier, which is much faster on 100k+
    member datasets with low per-member degree.
    """
    forward_frontier = {start_id}
    backward_frontier = {end_id}
    forward_parent = {start_id: (None, None)}
    backward_parent = {end_id: (None, None)}
    forward_depth = {start_id: 0}
    backward_depth = {end_id: 0}

    for _ in range(max_depth):
        expand_forward = len(forward_frontier) <= len(backward_frontier)
        frontier = forward_frontier if expand_forward else backward_frontier
        own_parent = forward_parent if expand_forward else backward_parent
        other_parent = backward_parent if expand_forward else forward_parent
        own_depth = forward_depth if expand_forward else backward_depth
        other_depth = backward_depth if expand_forward else forward_depth
        next_frontier = set()

        for row in _fetch_frontier_neighbors(genealogy_ids, frontier):
            from_id = row["from_id"]
            to_id = row["to_id"]
            relation_type = row["relation_type"]
            if to_id in own_parent:
                continue
            if own_depth[from_id] + 1 > max_depth:
                continue

            own_parent[to_id] = (from_id, relation_type)
            own_depth[to_id] = own_depth[from_id] + 1

            if to_id in other_parent:
                meeting_id = to_id
                left_ids, left_rels = _build_path_from_parent_map(forward_parent, meeting_id)
                right_ids, right_rels_from_end = _build_path_from_parent_map(backward_parent, meeting_id)
                right_ids_to_end = right_ids[-2::-1] if len(right_ids) > 1 else []
                right_rels_to_end = [
                    _reverse_relation_label(relation_type)
                    for relation_type in reversed(right_rels_from_end)
                ]
                return left_ids + right_ids_to_end, left_rels + right_rels_to_end

            next_frontier.add(to_id)

        if expand_forward:
            forward_frontier = next_frontier
        else:
            backward_frontier = next_frontier
        if not forward_frontier or not backward_frontier:
            break
    return None, None


def _reconstruct_path(genealogy_ids, start_id, meeting_id, depth, distances):
    """Phase 2: backtrack from meeting_id to start_id using distances map.
    Does per-step neighbor queries (O(depth) queries, each < 5ms).
    Returns (path_ids_list, relation_labels_list)."""
    # Pre-group distances for fast candidate lookup
    depth_to_members = {}
    for mid, d in distances.items():
        depth_to_members.setdefault(d, []).append(mid)

    path_ids = [meeting_id]
    current = meeting_id
    for d in range(depth - 1, -1, -1):
        candidates = depth_to_members.get(d, [])
        row = db.session.execute(
            text(
                "SELECT nid FROM (" + NEIGHBOR_QUERY + ") neighbors"
                " WHERE nid = ANY(:candidates) LIMIT 1"
            ),
            {"gids": genealogy_ids, "mid": current, "candidates": candidates},
        ).first()
        if not row:
            return None, None
        path_ids.insert(0, row[0])
        current = row[0]

    relations = _lookup_relations_batch(genealogy_ids, path_ids)
    return path_ids, relations


def _reconstruct_path_sql(genealogy_ids, start_id, meeting_id, depth):
    """Fallback Phase 2: SQL-based path reconstruction for deep paths (>6).
    Uses UNION ALL walk with ARRAY path tracking, bounded to known depth."""
    sql = (
        "WITH RECURSIVE edges AS NOT MATERIALIZED (" + EDGE_CTE_WITH_REL + "),\n"
        + "walk AS (\n"
        + "    SELECT CAST(:start_id AS INTEGER) AS member_id,\n"
        + "           ARRAY[CAST(:start_id AS INTEGER)] AS path,\n"
        + "           ARRAY[]::TEXT[] AS rels,\n"
        + "           0 AS depth\n"
        + "    UNION ALL\n"
        + "    SELECT e.to_id,\n"
        + "           walk.path || e.to_id,\n"
        + "           walk.rels || e.relation_type,\n"
        + "           walk.depth + 1\n"
        + "    FROM walk\n"
        + "    JOIN edges e ON e.from_id = walk.member_id\n"
        + "    WHERE walk.depth < :max_depth\n"
        + ") CYCLE member_id SET is_cycle USING cycle_path\n"
        + "SELECT path, rels FROM walk\n"
        + "WHERE member_id = :target_id AND NOT is_cycle\n"
        + "ORDER BY depth LIMIT 1"
    )
    row = db.session.execute(
        text(sql),
        {
            "genealogy_ids": genealogy_ids,
            "start_id": start_id,
            "target_id": meeting_id,
            "max_depth": depth + 1,
        },
    ).first()
    if row is None:
        return None, None
    return list(row.path), list(row.rels)


def _lookup_relations_batch(genealogy_ids, path_ids):
    """Batch-lookup relation labels between consecutive members in path.
    Uses a single VALUES-based query instead of O(n) individual queries."""
    if len(path_ids) < 2:
        return []
    n = len(path_ids) - 1

    values_clause = ", ".join(
        f"({i}, CAST(:a{i} AS INTEGER), CAST(:b{i} AS INTEGER))" for i in range(n)
    )
    params = {"gids": genealogy_ids}
    for i in range(n):
        params[f"a{i}"] = path_ids[i]
        params[f"b{i}"] = path_ids[i + 1]

    sql = f"""
        SELECT p.idx, p.a, p.b,
            CASE
                  WHEN EXISTS(SELECT 1 FROM parent_child_relations
                              WHERE parent_member_id=p.a AND child_member_id=p.b
                              AND genealogy_id=ANY(:gids)) THEN 'child'
                  WHEN EXISTS(SELECT 1 FROM parent_child_relations
                              WHERE child_member_id=p.a AND parent_member_id=p.b
                              AND genealogy_id=ANY(:gids)) THEN
                      COALESCE((SELECT parent_role FROM parent_child_relations
                                WHERE child_member_id=p.a AND parent_member_id=p.b
                                AND genealogy_id=ANY(:gids)), 'parent')
                  WHEN EXISTS(SELECT 1 FROM marriages
                              WHERE ((spouse1_member_id=p.a AND spouse2_member_id=p.b)
                                OR (spouse1_member_id=p.b AND spouse2_member_id=p.a))
                                AND genealogy_id=ANY(:gids))
                  THEN 'spouse'
              END AS relation
        FROM (VALUES {values_clause}) AS p(idx, a, b)
        ORDER BY p.idx
    """
    rows = db.session.execute(text(sql), params).fetchall()
    return [r[3] if r[3] else "?" for r in rows]


RELATION_LABELS = {
    "father": "父亲",
    "mother": "母亲",
    "parent": "父母",
    "child": "子女",
    "spouse": "配偶",
}


@bp.route("/relationship/path")
@login_required
def relationship_path():
    member_a_id = request.args.get("a", type=int)
    member_b_id = request.args.get("b", type=int)
    if not member_a_id or not member_b_id:
        flash("请提供 a 和 b 两个成员 ID。", "warning")
        return redirect(url_for("genealogies.index"))

    member_a = get_member(member_a_id)
    member_b = get_member(member_b_id)
    genealogy_ids = accessible_genealogy_ids()
    start_id = member_a.id
    end_id = member_b.id

    if start_id == end_id:
        return render_template(
            "members/path.html",
            member_a=member_a,
            member_b=member_b,
            path_members=[member_a],
            path_steps=[],
        )

    full_path_ids = None
    relation_types = None

    use_sqlite_fallback = _is_sqlite()
    if use_sqlite_fallback:
        full_path_ids, relation_types = _sqlite_shortest_path(genealogy_ids, start_id, end_id)
    else:
        full_path_ids, relation_types = _bidirectional_shortest_path(
            genealogy_ids,
            start_id,
            end_id,
        )

    path_members = []
    path_steps = []
    if full_path_ids:
        path_members = Member.query.filter(Member.id.in_(full_path_ids)).all()
        path_members = sorted(path_members, key=lambda m: full_path_ids.index(m.id))

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

    return render_template(
        "members/path.html",
        member_a=member_a,
        member_b=member_b,
        path_members=path_members,
        path_steps=path_steps,
    )
