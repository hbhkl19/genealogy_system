from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import text

from app.extensions import db
from app.models import Genealogy, Marriage, Member, ParentChildRelation, accessible_genealogy_query


bp = Blueprint("members", __name__)


def get_member(member_id):
    member = db.session.get(Member, member_id)
    if member is None:
        abort(404)
    genealogy = accessible_genealogy_query(current_user).filter(Genealogy.id == member.genealogy_id).first()
    if genealogy is None:
        abort(404)
    return member


@bp.route("/genealogies/<int:genealogy_id>/members/new", methods=["GET", "POST"])
@login_required
def create(genealogy_id):
    genealogy = accessible_genealogy_query(current_user).filter(Genealogy.id == genealogy_id).first()
    if genealogy is None:
        abort(404)

    if request.method == "POST":
        member = Member(
            genealogy_id=genealogy_id,
            name=request.form.get("name", "").strip(),
            gender=request.form.get("gender", "unknown"),
            birth_year=request.form.get("birth_year") or None,
            death_year=request.form.get("death_year") or None,
            biography=request.form.get("biography", "").strip(),
            generation_no=request.form.get("generation_no") or 1,
        )
        if not member.name:
            flash("成员姓名不能为空。", "warning")
            return render_template("members/form.html", genealogy=genealogy, member=member)
        db.session.add(member)
        db.session.commit()
        flash("成员已添加。", "success")
        return redirect(url_for("genealogies.members", id=genealogy_id))

    return render_template("members/form.html", genealogy=genealogy, member=None)


@bp.route("/members/<int:id>/ancestors")
@login_required
def ancestors(id):
    member = get_member(id)
    sql = """
        WITH RECURSIVE ancestors AS (
            SELECT p.parent_member_id AS member_id, 1 AS depth
            FROM parent_child_relations p
            WHERE p.child_member_id = :member_id
            UNION ALL
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

    sql = """
        WITH RECURSIVE edges AS (
            SELECT parent_member_id AS from_id, child_member_id AS to_id FROM parent_child_relations
            WHERE genealogy_id = :genealogy_id
            UNION
            SELECT child_member_id, parent_member_id FROM parent_child_relations
            WHERE genealogy_id = :genealogy_id
            UNION
            SELECT spouse1_member_id, spouse2_member_id FROM marriages
            WHERE genealogy_id = :genealogy_id
            UNION
            SELECT spouse2_member_id, spouse1_member_id FROM marriages
            WHERE genealogy_id = :genealogy_id
        ),
        walk AS (
            SELECT :start_id AS member_id, ARRAY[:start_id] AS path, 0 AS depth
            UNION ALL
            SELECT e.to_id, walk.path || e.to_id, walk.depth + 1
            FROM walk
            JOIN edges e ON e.from_id = walk.member_id
            WHERE walk.depth < 12 AND NOT e.to_id = ANY(walk.path)
        )
        SELECT path FROM walk
        WHERE member_id = :end_id
        ORDER BY depth
        LIMIT 1
    """
    row = db.session.execute(
        text(sql),
        {"genealogy_id": member_a.genealogy_id, "start_id": member_a.id, "end_id": member_b.id},
    ).first()
    path_members = []
    if row:
        path_members = Member.query.filter(Member.id.in_(row.path)).all()
        path_members = sorted(path_members, key=lambda item: row.path.index(item.id))
    return render_template(
        "members/path.html",
        member_a=member_a,
        member_b=member_b,
        path_members=path_members,
    )
