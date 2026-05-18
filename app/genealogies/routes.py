from urllib.parse import quote

from flask import Blueprint, Response, abort, current_app, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import func, text

from app.extensions import db
from app.models import (
    Genealogy,
    GenealogyCollaborator,
    Marriage,
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


def parse_optional_int(value):
    value = (value or "").strip()
    if not value:
        return None
    return int(value)


def update_genealogy_from_form(genealogy):
    genealogy.name = request.form.get("name", "").strip()
    genealogy.surname = request.form.get("surname", "").strip() or None
    genealogy.revision_year = parse_optional_int(request.form.get("revision_year"))
    genealogy.description = request.form.get("description", "").strip()


def member_payload(member):
    has_children = db.session.execute(
        text(
            """
            SELECT EXISTS (
                SELECT 1
                FROM parent_child_relations
                WHERE genealogy_id = :genealogy_id
                  AND parent_member_id = :member_id
            )
            """
        ),
        {"genealogy_id": member.genealogy_id, "member_id": member.id},
    ).scalar()
    has_parents = db.session.execute(
        text(
            """
            SELECT EXISTS (
                SELECT 1
                FROM parent_child_relations
                WHERE genealogy_id = :genealogy_id
                  AND child_member_id = :member_id
                  AND parent_role = 'father'
            )
            """
        ),
        {"genealogy_id": member.genealogy_id, "member_id": member.id},
    ).scalar()
    return {
        "id": member.id,
        "name": member.name,
        "gender": member.gender,
        "birth_year": member.birth_year,
        "death_year": member.death_year,
        "generation_no": member.generation_no,
        "has_children": bool(has_children),
        "has_parents": bool(has_parents),
        "spouses": indent_tree_spouses(member),
    }


def indent_tree_spouses(member):
    marriages = (
        Marriage.query.filter(
            (Marriage.spouse1_member_id == member.id)
            | (Marriage.spouse2_member_id == member.id)
        )
        .order_by(Marriage.id)
        .all()
    )
    spouse_ids = [
        marriage.spouse2_member_id
        if marriage.spouse1_member_id == member.id
        else marriage.spouse1_member_id
        for marriage in marriages
    ]
    if not spouse_ids:
        return []
    spouse_map = {
        spouse.id: spouse
        for spouse in Member.query.filter(
            Member.id.in_(spouse_ids),
        ).all()
    }
    return [
        {
            "id": spouse.id,
            "name": spouse.name,
            "gender": spouse.gender,
        }
        for spouse_id in spouse_ids
        if (spouse := spouse_map.get(spouse_id)) is not None
    ]


def indent_member_payload(member):
    has_children = ParentChildRelation.query.filter(
        ParentChildRelation.genealogy_id == member.genealogy_id,
        ParentChildRelation.parent_member_id == member.id,
    ).first() is not None
    return {
        "id": member.id,
        "name": member.name,
        "gender": member.gender,
        "generation_no": member.generation_no,
        "birth_year": member.birth_year or 0,
        "has_children": has_children,
        "spouses": indent_tree_spouses(member),
    }


def get_genealogy_member_or_404(genealogy_id, member_id):
    member = Member.query.filter_by(id=member_id, genealogy_id=genealogy_id).first()
    if member is None:
        abort(404)
    return member


@bp.route("")
@login_required
def index():
    genealogies = accessible_genealogy_query(current_user).order_by(Genealogy.created_at.desc()).all()
    return render_template("genealogies/index.html", genealogies=genealogies)


@bp.route("/new", methods=["GET", "POST"])
@login_required
def create():
    if request.method == "POST":
        genealogy = Genealogy(owner=current_user)
        update_genealogy_from_form(genealogy)
        if not genealogy.name:
            flash("族谱名称不能为空。", "warning")
            return render_template("genealogies/form.html", genealogy=None)
        db.session.add(genealogy)
        db.session.commit()
        flash("族谱已创建。", "success")
        return redirect(url_for("genealogies.detail", id=genealogy.id))
    return render_template("genealogies/form.html", genealogy=None)


@bp.route("/<int:id>/edit", methods=["GET", "POST"])
@login_required
def edit(id):
    genealogy = get_accessible_genealogy(id)
    if request.method == "POST":
        update_genealogy_from_form(genealogy)
        if not genealogy.name:
            flash("族谱名称不能为空。", "warning")
            return render_template("genealogies/form.html", genealogy=genealogy)
        db.session.commit()
        flash("族谱信息已更新。", "success")
        return redirect(url_for("genealogies.detail", id=genealogy.id))
    return render_template("genealogies/form.html", genealogy=genealogy)


@bp.route("/<int:id>/delete", methods=["POST"])
@login_required
def delete(id):
    genealogy = get_accessible_genealogy(id)
    if genealogy.owner_id != current_user.id:
        abort(403)
    db.session.delete(genealogy)
    db.session.commit()
    flash("族谱已删除，成员和关系已同步移除。", "success")
    return redirect(url_for("genealogies.index"))


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
    member_id = request.args.get("member_id", type=int)
    page = max(request.args.get("page", 1, type=int) or 1, 1)
    per_page = request.args.get("per_page", 50, type=int) or 50
    if per_page not in {50, 75}:
        per_page = 50
    query = Member.query.filter_by(genealogy_id=id)
    if member_id:
        query = query.filter(Member.id == member_id)
    if q:
        query = query.filter(Member.name.ilike(f"%{q}%"))
    total = query.count()
    pages = max((total + per_page - 1) // per_page, 1)
    page = min(page, pages)
    members = (
        query.order_by(Member.generation_no, Member.id)
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    return render_template(
        "genealogies/members.html",
        genealogy=genealogy,
        members=members,
        q=q,
        member_id=member_id,
        page=page,
        per_page=per_page,
        total=total,
        pages=pages,
        start_page=max(1, page - 2),
        end_page=min(pages, page + 2),
    )


@bp.route("/<int:id>/tree")
@login_required
def tree(id):
    genealogy = get_accessible_genealogy(id)
    return render_template("genealogies/tree.html", genealogy=genealogy)


@bp.route("/<int:id>/tree/roots")
@login_required
def tree_roots(id):
    get_accessible_genealogy(id)
    has_father = ParentChildRelation.query.filter(
        ParentChildRelation.genealogy_id == id,
        ParentChildRelation.child_member_id == Member.id,
        ParentChildRelation.parent_role == "father",
    ).exists()
    roots = (
        Member.query.filter(Member.genealogy_id == id)
        .filter(~has_father)
        .order_by(Member.generation_no, Member.id)
        .all()
    )
    return jsonify([indent_member_payload(member) for member in roots])


@bp.route("/<int:id>/tree/children/<int:member_id>")
@login_required
def tree_children(id, member_id):
    get_accessible_genealogy(id)
    member = get_genealogy_member_or_404(id, member_id)
    children = (
        Member.query.join(ParentChildRelation, ParentChildRelation.child_member_id == Member.id)
        .filter(
            ParentChildRelation.genealogy_id == id,
            ParentChildRelation.parent_member_id == member_id,
        )
        .order_by(Member.birth_year, Member.id)
        .all()
    )
    return jsonify({
        "member": {"id": member.id, "name": member.name, "gender": member.gender},
        "spouses": indent_tree_spouses(member),
        "children": [indent_member_payload(child) for child in children],
    })


@bp.route("/<int:id>/tree/member/<int:member_id>")
@login_required
def tree_member(id, member_id):
    get_accessible_genealogy(id)
    member = Member.query.filter_by(id=member_id, genealogy_id=id).first()
    if member is None:
        abort(404)
    return jsonify(indent_member_payload(member))


@bp.route("/<int:id>/tree-roots")
@login_required
def svg_tree_roots(id):
    get_accessible_genealogy(id)
    limit = min(request.args.get("limit", 50, type=int) or 50, 50)
    roots = (
        Member.query.filter(Member.genealogy_id == id)
        .filter(
            ~ParentChildRelation.query.filter(
                ParentChildRelation.genealogy_id == id,
                ParentChildRelation.child_member_id == Member.id,
            ).exists()
        )
        .order_by(Member.generation_no, Member.id)
        .limit(limit)
        .all()
    )
    return jsonify({"members": [member_payload(member) for member in roots]})


@bp.route("/<int:id>/tree-node/<int:member_id>")
@login_required
def svg_tree_node(id, member_id):
    get_accessible_genealogy(id)
    member = get_genealogy_member_or_404(id, member_id)
    return jsonify({"member": member_payload(member)})


@bp.route("/<int:id>/tree-node/<int:member_id>/children")
@login_required
def svg_tree_node_children(id, member_id):
    get_accessible_genealogy(id)
    member = get_genealogy_member_or_404(id, member_id)
    if member.gender == "female":
        return jsonify({"members": []})
    limit = min(request.args.get("limit", 100, type=int) or 100, 100)
    children = (
        Member.query.join(ParentChildRelation, ParentChildRelation.child_member_id == Member.id)
        .filter(
            ParentChildRelation.genealogy_id == id,
            ParentChildRelation.parent_member_id == member_id,
        )
        .order_by(Member.generation_no, Member.id)
        .limit(limit)
        .all()
    )
    return jsonify({"members": [member_payload(member) for member in children]})


@bp.route("/<int:id>/tree-node/<int:member_id>/parents")
@login_required
def svg_tree_node_parents(id, member_id):
    get_accessible_genealogy(id)
    get_genealogy_member_or_404(id, member_id)
    parents = (
        Member.query.join(ParentChildRelation, ParentChildRelation.parent_member_id == Member.id)
        .filter(
            ParentChildRelation.genealogy_id == id,
            ParentChildRelation.child_member_id == member_id,
        )
        .order_by(ParentChildRelation.parent_role, Member.id)
        .limit(2)
        .all()
    )
    return jsonify({"members": [member_payload(member) for member in parents]})


@bp.route("/<int:id>/statistics")
@login_required
def statistics(id):
    genealogy = get_accessible_genealogy(id)

    spouse_children = db.session.execute(
        text("""
            SELECT 'spouse' AS kind, spouse_member.name, spouse_member.gender,
                   s.married_year
            FROM marriages s
            JOIN members spouse_member ON (
                CASE WHEN s.spouse1_member_id = :member_id THEN s.spouse2_member_id
                     ELSE s.spouse1_member_id
                END = spouse_member.id
            )
            WHERE s.genealogy_id = :genealogy_id
              AND (s.spouse1_member_id = :member_id OR s.spouse2_member_id = :member_id)
            UNION ALL
            SELECT 'child' AS kind, child_member.name, child_member.gender, NULL
            FROM parent_child_relations rel
            JOIN members child_member ON child_member.id = rel.child_member_id
            WHERE rel.genealogy_id = :genealogy_id
              AND rel.parent_member_id = :member_id
            ORDER BY kind, name
        """),
        {"genealogy_id": id, "member_id": 1},
    ).mappings().all()

    lifespan_gen = db.session.execute(
        text("""
            WITH gen_lifespan AS (
                SELECT genealogy_id, generation_no,
                       AVG(death_year - birth_year)::numeric(6,2) AS avg_lifespan,
                       COUNT(*) AS member_count
                FROM members
                WHERE genealogy_id = :genealogy_id
                  AND birth_year IS NOT NULL AND death_year IS NOT NULL
                  AND death_year > birth_year
                GROUP BY genealogy_id, generation_no
            )
            SELECT genealogy_id, generation_no, avg_lifespan, member_count
            FROM gen_lifespan
            ORDER BY avg_lifespan DESC
            LIMIT 1
        """),
        {"genealogy_id": id},
    ).mappings().first()

    males_no_spouse = db.session.execute(
        text("""
            SELECT m.id, m.name, m.birth_year, m.death_year, m.generation_no,
                   COALESCE(m.death_year, EXTRACT(YEAR FROM CURRENT_DATE)::int) - m.birth_year AS est_age
            FROM members m
            WHERE m.genealogy_id = :genealogy_id
              AND m.gender = 'male'
              AND m.birth_year IS NOT NULL
              AND (COALESCE(m.death_year, EXTRACT(YEAR FROM CURRENT_DATE)::int) - m.birth_year) > 50
              AND NOT EXISTS (
                  SELECT 1 FROM marriages mar
                  WHERE mar.genealogy_id = m.genealogy_id
                    AND (mar.spouse1_member_id = m.id OR mar.spouse2_member_id = m.id)
              )
            ORDER BY est_age DESC
            LIMIT 20
        """),
        {"genealogy_id": id},
    ).mappings().all()

    born_before_avg = db.session.execute(
        text("""
            WITH gen_avg AS (
                SELECT genealogy_id, generation_no,
                       AVG(birth_year)::numeric(6,2) AS avg_birth_year,
                       COUNT(*) AS total_in_gen
                FROM members
                WHERE genealogy_id = :genealogy_id AND birth_year IS NOT NULL
                GROUP BY genealogy_id, generation_no
            )
            SELECT m.id, m.name, m.gender, m.birth_year, m.generation_no,
                   ga.avg_birth_year,
                   ROUND((m.birth_year - ga.avg_birth_year)::numeric, 2) AS deviation
            FROM members m
            JOIN gen_avg ga ON ga.generation_no = m.generation_no
                           AND ga.genealogy_id = m.genealogy_id
            WHERE m.genealogy_id = :genealogy_id
              AND m.birth_year IS NOT NULL
              AND m.birth_year < ga.avg_birth_year
            ORDER BY m.generation_no, m.birth_year, m.id
            LIMIT 20
        """),
        {"genealogy_id": id},
    ).mappings().all()

    return render_template(
        "genealogies/statistics.html",
        genealogy=genealogy,
        spouse_children=spouse_children,
        lifespan_gen=lifespan_gen,
        males_no_spouse=males_no_spouse,
        born_before_avg=born_before_avg,
    )


@bp.route("/<int:id>/export")
@login_required
def export(id):
    genealogy = get_accessible_genealogy(id)
    app = current_app._get_current_object()

    def generate():
        yield "id,genealogy_id,name,gender,birth_year,death_year,generation_no\n"
        offset = 0
        chunk_size = 2000
        with app.app_context():
            while True:
                rows = db.session.execute(
                    text(
                        "SELECT id, genealogy_id, name, gender, birth_year, death_year, generation_no "
                        "FROM members WHERE genealogy_id = :gid "
                        "ORDER BY id LIMIT :limit OFFSET :offset"
                    ),
                    {"gid": id, "limit": chunk_size, "offset": offset},
                ).fetchall()
                if not rows:
                    break
                for row in rows:
                    birth = row[4] if row[4] is not None else ""
                    death = row[5] if row[5] is not None else ""
                    yield f"{row[0]},{row[1]},{row[2]},{row[3]},{birth},{death},{row[6]}\n"
                offset += chunk_size

    safe_filename = quote(f"{genealogy.name}_members.csv")
    return Response(
        generate(),
        mimetype="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": (
                f"attachment; filename*=UTF-8''{safe_filename}"
            ),
            "X-Accel-Buffering": "no",
        },
    )


@bp.route("/<int:id>/members/search")
@login_required
def search_members(id):
    get_accessible_genealogy(id)
    query = (request.args.get("q", "") or "").strip()
    exclude_id = request.args.get("exclude", type=int)
    if not query:
        return jsonify([])
    limit = min(request.args.get("limit", 20, type=int) or 20, 50)
    base = Member.query.filter(Member.genealogy_id == id)
    if exclude_id:
        base = base.filter(Member.id != exclude_id)
    results = []
    seen = set()
    try:
        mid = int(query)
        exact = base.filter(Member.id == mid).first()
        if exact:
            results.append({"id": exact.id, "name": exact.name, "gender": exact.gender, "generation_no": exact.generation_no, "birth_year": exact.birth_year})
            seen.add(exact.id)
    except ValueError:
        pass
    fuzzy = base.filter(Member.name.ilike(f"%{query}%")).order_by(Member.name).limit(limit).all()
    for m in fuzzy:
        if m.id not in seen:
            results.append({"id": m.id, "name": m.name, "gender": m.gender, "generation_no": m.generation_no, "birth_year": m.birth_year})
            seen.add(m.id)
    return jsonify(results[:limit])
