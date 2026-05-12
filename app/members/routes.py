from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
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
            marriage = Marriage.query.filter_by(id=marriage_id, genealogy_id=genealogy_id).first()
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
            Marriage.genealogy_id == genealogy_id,
            (Marriage.spouse1_member_id == member.id) | (Marriage.spouse2_member_id == member.id),
        )
        .order_by(Marriage.id)
        .all()
    )
    candidates = (
        Member.query.filter(Member.genealogy_id == genealogy_id, Member.id != member.id)
        .order_by(Member.generation_no, Member.id)
        .limit(500)
        .all()
    )
    return render_template(
        "members/relations.html",
        member=member,
        parent_relations=parent_relations,
        child_relations=child_relations,
        marriages=marriages,
        candidates=candidates,
    )


@bp.route("/members/<int:id>/ancestors")
@login_required
def ancestors(id):
    member = get_member(id)
    sql = """
        WITH RECURSIVE ancestors AS (
            SELECT p.parent_member_id AS member_id, 1 AS depth
            FROM parent_child_relations p
            WHERE p.child_member_id = :member_id
            UNION
            SELECT p.parent_member_id, a.depth + 1
            FROM parent_child_relations p
            JOIN ancestors a ON p.child_member_id = a.member_id
            WHERE a.depth < 10
        )
        SELECT m.id, m.name, m.gender, m.generation_no, ancestors.depth
        FROM ancestors
        JOIN members m ON m.id = ancestors.member_id
        ORDER BY ancestors.depth, m.id
    """
    rows = db.session.execute(text(sql), {"member_id": id}).mappings().all()
    return render_template("members/ancestors.html", member=member, rows=rows)


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
    SELECT parent_member_id AS from_id, child_member_id AS to_id
    FROM parent_child_relations WHERE genealogy_id = :genealogy_id
    UNION ALL
    SELECT child_member_id, parent_member_id
    FROM parent_child_relations WHERE genealogy_id = :genealogy_id
    UNION ALL
    SELECT spouse1_member_id, spouse2_member_id
    FROM marriages WHERE genealogy_id = :genealogy_id
    UNION ALL
    SELECT spouse2_member_id, spouse1_member_id
    FROM marriages WHERE genealogy_id = :genealogy_id
"""

EDGE_CTE_WITH_REL = """
    SELECT parent_member_id AS from_id, child_member_id AS to_id, 'child' AS relation_type
    FROM parent_child_relations WHERE genealogy_id = :genealogy_id
    UNION ALL
    SELECT child_member_id, parent_member_id, parent_role
    FROM parent_child_relations WHERE genealogy_id = :genealogy_id
    UNION ALL
    SELECT spouse1_member_id, spouse2_member_id, 'spouse'
    FROM marriages WHERE genealogy_id = :genealogy_id
    UNION ALL
    SELECT spouse2_member_id, spouse1_member_id, 'spouse'
    FROM marriages WHERE genealogy_id = :genealogy_id
"""


def _bfs_reachable(genealogy_id, root_id, max_depth):
    """Phase 1: fast BFS returning {member_id: min_depth}.
    Prefer stored PL/pgSQL function for deep searches (avoids CTE recursion overhead).
    Falls back to UNION-based CTE if function is not deployed."""
    if max_depth >= 8:
        try:
            rows = db.session.execute(
                text("SELECT member_id, depth FROM bfs_reachable(:gid, :rid, :md)"),
                {"gid": genealogy_id, "rid": root_id, "md": max_depth},
            ).fetchall()
            return {r[0]: r[1] for r in rows}
        except Exception:
            db.session.rollback()

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
        {"genealogy_id": genealogy_id, "root_id": root_id, "max_depth": max_depth},
    ).fetchall()
    return {r[0]: r[1] for r in rows}


NEIGHBOR_QUERY = """
    SELECT parent_member_id AS nid
    FROM parent_child_relations
    WHERE genealogy_id = :gid AND child_member_id = :mid
    UNION ALL
    SELECT child_member_id
    FROM parent_child_relations
    WHERE genealogy_id = :gid AND parent_member_id = :mid
    UNION ALL
    SELECT spouse2_member_id
    FROM marriages
    WHERE genealogy_id = :gid AND spouse1_member_id = :mid
    UNION ALL
    SELECT spouse1_member_id
    FROM marriages
    WHERE genealogy_id = :gid AND spouse2_member_id = :mid
"""


def _reconstruct_path(genealogy_id, start_id, meeting_id, depth, distances):
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
            {"gid": genealogy_id, "mid": current, "candidates": candidates},
        ).first()
        if not row:
            return None, None
        path_ids.insert(0, row[0])
        current = row[0]

    relations = _lookup_relations_batch(genealogy_id, path_ids)
    return path_ids, relations


def _reconstruct_path_sql(genealogy_id, start_id, meeting_id, depth):
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
            "genealogy_id": genealogy_id,
            "start_id": start_id,
            "target_id": meeting_id,
            "max_depth": depth + 1,
        },
    ).first()
    if row is None:
        return None, None
    return list(row.path), list(row.rels)


def _lookup_relations_batch(genealogy_id, path_ids):
    """Batch-lookup relation labels between consecutive members in path.
    Uses a single VALUES-based query instead of O(n) individual queries."""
    if len(path_ids) < 2:
        return []
    n = len(path_ids) - 1
    gid = genealogy_id

    values_clause = ", ".join(f"(CAST(:a{i} AS INTEGER), CAST(:b{i} AS INTEGER))" for i in range(n))
    params = {"gid": gid}
    for i in range(n):
        params[f"a{i}"] = path_ids[i]
        params[f"b{i}"] = path_ids[i + 1]

    sql = f"""
        SELECT p.a, p.b,
            CASE
                WHEN EXISTS(SELECT 1 FROM parent_child_relations
                            WHERE parent_member_id=p.a AND child_member_id=p.b
                            AND genealogy_id=:gid) THEN 'child'
                WHEN EXISTS(SELECT 1 FROM parent_child_relations
                            WHERE child_member_id=p.a AND parent_member_id=p.b
                            AND genealogy_id=:gid) THEN
                    COALESCE((SELECT parent_role FROM parent_child_relations
                              WHERE child_member_id=p.a AND parent_member_id=p.b
                              AND genealogy_id=:gid), 'parent')
                WHEN EXISTS(SELECT 1 FROM marriages
                            WHERE genealogy_id=:gid
                            AND ((spouse1_member_id=p.a AND spouse2_member_id=p.b)
                              OR (spouse1_member_id=p.b AND spouse2_member_id=p.a)))
                THEN 'spouse'
            END AS relation
        FROM (VALUES {values_clause}) AS p(a, b)
        ORDER BY p.a
    """
    rows = db.session.execute(text(sql), params).fetchall()
    return [r[2] if r[2] else "?" for r in rows]


RELATION_LABELS = {
    "father": "父亲",
    "mother": "母亲",
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
    if member_a.genealogy_id != member_b.genealogy_id:
        abort(404)

    gid = member_a.genealogy_id
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

    # --- Progressive bidirectional BFS ---
    # Try shallow depths first (fast for common close relations)
    for max_depth in (6, 8, 10, 12, 15):
        fwd = _bfs_reachable(gid, start_id, max_depth)
        rev = _bfs_reachable(gid, end_id, max_depth)
        meeting = set(fwd.keys()) & set(rev.keys())

        if meeting:
            best = min(meeting, key=lambda m: fwd[m] + rev[m])
            fwd_depth = fwd[best]
            rev_depth = rev[best]

            # --- Phase 2: reconstruct both halves ---
            # Python backtracking: O(depth) per-step queries (each < 5ms with indexes)
            fwd_ids, fwd_rels = _reconstruct_path(gid, start_id, best, fwd_depth, fwd)
            rev_ids, rev_rels = _reconstruct_path(gid, end_id, best, rev_depth, rev)

            if fwd_ids and rev_ids:
                fwd_ids = list(fwd_ids)
                rev_ids = list(rev_ids)
                rev_reversed = rev_ids[-2::-1] if len(rev_ids) > 1 else []

                full_path_ids = fwd_ids + rev_reversed

                # Combine relation labels
                relation_types = list(fwd_rels)
                rev_rels_list = list(rev_rels)
                for i in range(len(rev_rels_list) - 1, -1, -1):
                    rev_rel = rev_rels_list[i]
                    if rev_rel == "child":
                        relation_types.append("parent")
                    elif rev_rel == "spouse":
                        relation_types.append("spouse")
                    else:
                        relation_types.append(rev_rel)
                break

        if max_depth >= 15:
            break

    # --- Last resort: legacy single-direction BFS ---
    if full_path_ids is None:
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
            + "    FROM walk\n"
            + "    JOIN edges e ON e.from_id = walk.member_id\n"
            + "    WHERE walk.depth < 18\n"
            + ") CYCLE member_id SET is_cycle USING cycle_path\n"
            + "SELECT id_path, relation_types FROM walk\n"
            + "WHERE member_id = :end_id AND NOT is_cycle\n"
            + "ORDER BY depth LIMIT 1"
        )
        row = db.session.execute(
            text(legacy_sql),
            {"genealogy_id": gid, "start_id": start_id, "end_id": end_id},
        ).first()
        if row:
            full_path_ids = [int(v) for v in row.id_path.strip(",").split(",") if v]
            relation_types = [v for v in row.relation_types.strip(",").split(",") if v]

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
