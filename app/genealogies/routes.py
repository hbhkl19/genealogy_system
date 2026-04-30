from flask import Blueprint, Response, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import func, text

from app.extensions import db
from app.models import (
    Genealogy,
    GenealogyCollaborator,
    Member,
    ParentChildRelation,
    User,
    accessible_genealogy_query,
)


bp = Blueprint("genealogies", __name__, url_prefix="/genealogies")


def get_accessible_genealogy(genealogy_id):
    genealogy = accessible_genealogy_query(current_user).filter(Genealogy.id == genealogy_id).first()
    if genealogy is None:
        abort(404)
    return genealogy


@bp.route("")
@login_required
def index():
    genealogies = accessible_genealogy_query(current_user).order_by(Genealogy.created_at.desc()).all()
    return render_template("genealogies/index.html", genealogies=genealogies)


@bp.route("/new", methods=["GET", "POST"])
@login_required
def create():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()
        if not name:
            flash("族谱名称不能为空。", "warning")
            return render_template("genealogies/form.html", genealogy=None)
        genealogy = Genealogy(name=name, description=description, owner=current_user)
        db.session.add(genealogy)
        db.session.commit()
        flash("族谱已创建。", "success")
        return redirect(url_for("genealogies.detail", id=genealogy.id))
    return render_template("genealogies/form.html", genealogy=None)


@bp.route("/<int:id>")
@login_required
def detail(id):
    genealogy = get_accessible_genealogy(id)
    total = genealogy.members.count()
    gender_rows = (
        db.session.query(Member.gender, func.count(Member.id))
        .filter(Member.genealogy_id == id)
        .group_by(Member.gender)
        .all()
    )
    gender_stats = {gender: count for gender, count in gender_rows}
    return render_template(
        "genealogies/detail.html",
        genealogy=genealogy,
        total=total,
        gender_stats=gender_stats,
    )


@bp.route("/<int:id>/invite", methods=["GET", "POST"])
@login_required
def invite(id):
    genealogy = get_accessible_genealogy(id)
    if genealogy.owner_id != current_user.id:
        abort(403)

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        role = request.form.get("role", "editor")
        user = User.query.filter_by(email=email).first()
        if user is None:
            flash("未找到该邮箱对应的用户。", "warning")
            return render_template("genealogies/invite.html", genealogy=genealogy)
        if user.id == current_user.id:
            flash("创建者无需再次邀请。", "info")
            return render_template("genealogies/invite.html", genealogy=genealogy)
        exists = GenealogyCollaborator.query.filter_by(genealogy_id=id, user_id=user.id).first()
        if exists:
            flash("该用户已经是协作者。", "info")
            return redirect(url_for("genealogies.detail", id=id))
        db.session.add(GenealogyCollaborator(genealogy_id=id, user_id=user.id, role=role))
        db.session.commit()
        flash("协作者已添加。", "success")
        return redirect(url_for("genealogies.detail", id=id))

    return render_template("genealogies/invite.html", genealogy=genealogy)


@bp.route("/<int:id>/members")
@login_required
def members(id):
    genealogy = get_accessible_genealogy(id)
    q = request.args.get("q", "").strip()
    query = Member.query.filter_by(genealogy_id=id)
    if q:
        query = query.filter(Member.name.ilike(f"%{q}%"))
    members = query.order_by(Member.generation_no, Member.id).limit(200).all()
    return render_template("genealogies/members.html", genealogy=genealogy, members=members, q=q)


@bp.route("/<int:id>/tree")
@login_required
def tree(id):
    genealogy = get_accessible_genealogy(id)
    sql = """
        WITH RECURSIVE tree AS (
            SELECT
                m.id,
                m.name,
                m.gender,
                m.generation_no,
                0 AS depth,
                ',' || CAST(m.id AS TEXT) || ',' AS path
            FROM members m
            WHERE m.genealogy_id = :genealogy_id
              AND NOT EXISTS (
                  SELECT 1
                  FROM parent_child_relations p
                  WHERE p.child_member_id = m.id
                    AND p.genealogy_id = :genealogy_id
              )
            UNION ALL
            SELECT
                child.id,
                child.name,
                child.gender,
                child.generation_no,
                tree.depth + 1,
                tree.path || CAST(child.id AS TEXT) || ','
            FROM tree
            JOIN parent_child_relations rel ON rel.parent_member_id = tree.id
            JOIN members child ON child.id = rel.child_member_id
            WHERE rel.genealogy_id = :genealogy_id
              AND tree.depth < 12
              AND tree.path NOT LIKE '%,' || CAST(child.id AS TEXT) || ',%'
        )
        SELECT id, name, gender, generation_no, depth
        FROM tree
        ORDER BY path
        LIMIT 500
    """
    rows = db.session.execute(text(sql), {"genealogy_id": id}).mappings().all()
    return render_template("genealogies/tree.html", genealogy=genealogy, rows=rows)


@bp.route("/<int:id>/export")
@login_required
def export(id):
    genealogy = get_accessible_genealogy(id)
    rows = Member.query.filter_by(genealogy_id=id).order_by(Member.id).all()
    lines = ["id,genealogy_id,name,gender,birth_year,death_year,generation_no"]
    for member in rows:
        lines.append(
            f"{member.id},{member.genealogy_id},{member.name},{member.gender},"
            f"{member.birth_year or ''},{member.death_year or ''},{member.generation_no}"
        )
    return Response(
        "\n".join(lines),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={genealogy.name}_members.csv"},
    )
