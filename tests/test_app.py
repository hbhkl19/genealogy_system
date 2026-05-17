import pytest

from app import create_app
from app.config import TestingConfig
from app.extensions import db
from app.models import Genealogy, Marriage, Member, ParentChildRelation, User


@pytest.fixture()
def app():
    app = create_app(TestingConfig)
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


def test_app_routes_load(app):
    routes = {rule.rule for rule in app.url_map.iter_rules()}

    assert "/register" in routes
    assert "/login" in routes
    assert "/genealogies" in routes
    assert "/genealogies/<int:id>/edit" in routes
    assert "/genealogies/<int:id>/delete" in routes
    assert "/genealogies/<int:id>/tree-roots" in routes
    assert "/genealogies/<int:id>/tree-node/<int:member_id>" in routes
    assert "/genealogies/<int:id>/tree-node/<int:member_id>/children" in routes
    assert "/genealogies/<int:id>/tree-node/<int:member_id>/parents" in routes
    assert "/genealogies/<int:id>/tree/member/<int:member_id>" in routes
    assert "/relationship/path" in routes
    assert "/members/<int:id>/edit" in routes
    assert "/members/<int:id>/delete" in routes
    assert "/members/<int:id>/relations" in routes
    assert "/members/<int:id>/ancestor-parents" in routes
    assert "/members/<int:id>/descendants" in routes


def seed_user_genealogy_members():
    user = User(username="tester", email="tester@example.com")
    user.set_password("secret")
    genealogy = Genealogy(name="测试族谱", owner=user)
    father = Member(name="父亲", gender="male", birth_year=1970, generation_no=1, genealogy=genealogy)
    another_father = Member(name="另一父亲", gender="male", birth_year=1968, generation_no=1, genealogy=genealogy)
    mother = Member(name="母亲", gender="female", birth_year=1972, generation_no=1, genealogy=genealogy)
    child = Member(name="孩子", gender="unknown", birth_year=1995, generation_no=2, genealogy=genealogy)
    db.session.add_all([user, genealogy, father, another_father, mother, child])
    db.session.commit()
    return {
        "user_id": user.id,
        "genealogy_id": genealogy.id,
        "father_id": father.id,
        "another_father_id": another_father.id,
        "mother_id": mother.id,
        "child_id": child.id,
    }


def login(client):
    return client.post("/login", data={"account": "tester", "password": "secret"})


def test_member_edit_and_relationship_rules(app, client):
    with app.app_context():
        ids = seed_user_genealogy_members()

    login(client)

    response = client.post(
        f"/members/{ids['child_id']}/edit",
        data={
            "name": "孩子甲",
            "gender": "unknown",
            "birth_year": "1995",
            "death_year": "",
            "generation_no": "2",
            "biography": "测试简介",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200

    client.post(
        f"/members/{ids['child_id']}/relations",
        data={
            "action": "add_parent",
            "parent_member_id": ids["father_id"],
            "parent_role": "father",
        },
    )
    client.post(
        f"/members/{ids['child_id']}/relations",
        data={
            "action": "add_parent",
            "parent_member_id": ids["another_father_id"],
            "parent_role": "father",
        },
    )
    client.post(
        f"/members/{ids['child_id']}/relations",
        data={
            "action": "add_parent",
            "parent_member_id": ids["mother_id"],
            "parent_role": "mother",
        },
    )

    with app.app_context():
        child = db.session.get(Member, ids["child_id"])
        assert child.name == "孩子甲"
        assert child.biography == "测试简介"
        assert ParentChildRelation.query.filter_by(child_member_id=ids["child_id"]).count() == 2
        assert ParentChildRelation.query.filter_by(child_member_id=ids["child_id"], parent_role="father").count() == 1


def test_genealogy_profile_edit_and_delete(app, client):
    with app.app_context():
        ids = seed_user_genealogy_members()

    login(client)
    response = client.post(
        f"/genealogies/{ids['genealogy_id']}/edit",
        data={
            "name": "赵氏宗谱",
            "surname": "赵",
            "revision_year": "2026",
            "description": "修订版",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "赵氏宗谱".encode() in response.data

    with app.app_context():
        genealogy = db.session.get(Genealogy, ids["genealogy_id"])
        assert genealogy.surname == "赵"
        assert genealogy.revision_year == 2026

    response = client.post(f"/genealogies/{ids['genealogy_id']}/delete", follow_redirects=True)
    assert response.status_code == 200
    with app.app_context():
        assert db.session.get(Genealogy, ids["genealogy_id"]) is None


def test_marriage_is_ordered_and_not_duplicated(app, client):
    with app.app_context():
        ids = seed_user_genealogy_members()

    login(client)
    payload = {
        "action": "add_marriage",
        "spouse_member_id": ids["mother_id"],
        "married_year": "1990",
        "ended_year": "",
    }
    client.post(f"/members/{ids['father_id']}/relations", data=payload)
    client.post(f"/members/{ids['mother_id']}/relations", data={**payload, "spouse_member_id": ids["father_id"]})

    with app.app_context():
        marriage = Marriage.query.one()
        assert marriage.spouse1_member_id == min(ids["father_id"], ids["mother_id"])
        assert marriage.spouse2_member_id == max(ids["father_id"], ids["mother_id"])
        assert Marriage.query.count() == 1


def test_recursive_views_render_relationships(app, client):
    with app.app_context():
        ids = seed_user_genealogy_members()
        db.session.add(
            ParentChildRelation(
                genealogy_id=ids["genealogy_id"],
                parent_member_id=ids["father_id"],
                child_member_id=ids["child_id"],
                parent_role="father",
            )
        )
        db.session.add(
            Marriage(
                genealogy_id=ids["genealogy_id"],
                spouse1_member_id=min(ids["father_id"], ids["mother_id"]),
                spouse2_member_id=max(ids["father_id"], ids["mother_id"]),
                married_year=1990,
            )
        )
        db.session.commit()

    login(client)

    descendants = client.get(f"/members/{ids['father_id']}/descendants")
    tree = client.get(f"/genealogies/{ids['genealogy_id']}/tree")
    tree_roots = client.get(f"/genealogies/{ids['genealogy_id']}/tree/roots")
    path = client.get(f"/relationship/path?a={ids['father_id']}&b={ids['mother_id']}")

    assert descendants.status_code == 200
    assert "孩子".encode() in descendants.data
    assert tree.status_code == 200
    assert "tree-container".encode() in tree.data
    assert tree_roots.status_code == 200
    assert any(row["id"] == ids["father_id"] for row in tree_roots.json)
    assert path.status_code == 200
    assert "配偶".encode() in path.data


def test_lazy_tree_json_endpoints(app, client):
    with app.app_context():
        ids = seed_user_genealogy_members()
        db.session.add(
            ParentChildRelation(
                genealogy_id=ids["genealogy_id"],
                parent_member_id=ids["father_id"],
                child_member_id=ids["child_id"],
                parent_role="father",
            )
        )
        db.session.add(
            ParentChildRelation(
                genealogy_id=ids["genealogy_id"],
                parent_member_id=ids["mother_id"],
                child_member_id=ids["child_id"],
                parent_role="mother",
            )
        )
        other_user = User(username="other", email="other@example.com")
        other_user.set_password("secret")
        other_genealogy = Genealogy(name="其他族谱", owner=other_user)
        other_member = Member(name="外族成员", gender="unknown", generation_no=1, genealogy=other_genealogy)
        db.session.add_all([other_user, other_genealogy, other_member])
        db.session.commit()
        other_member_id = other_member.id

    unauthenticated = client.get(f"/genealogies/{ids['genealogy_id']}/tree-roots")
    assert unauthenticated.status_code == 302

    login(client)

    roots = client.get(f"/genealogies/{ids['genealogy_id']}/tree-roots")
    assert roots.status_code == 200
    root_ids = {member["id"] for member in roots.json["members"]}
    assert ids["father_id"] in root_ids
    assert ids["child_id"] not in root_ids

    focused = client.get(f"/genealogies/{ids['genealogy_id']}/tree-node/{ids['child_id']}")
    assert focused.status_code == 200
    assert focused.json["member"]["has_parents"] is True

    children = client.get(f"/genealogies/{ids['genealogy_id']}/tree-node/{ids['father_id']}/children")
    assert children.status_code == 200
    assert [member["id"] for member in children.json["members"]] == [ids["child_id"]]

    parents = client.get(f"/genealogies/{ids['genealogy_id']}/tree-node/{ids['child_id']}/parents")
    assert parents.status_code == 200
    assert {member["id"] for member in parents.json["members"]} == {ids["father_id"], ids["mother_id"]}

    mother_children = client.get(f"/genealogies/{ids['genealogy_id']}/tree-node/{ids['mother_id']}/children")
    assert mother_children.status_code == 200
    assert mother_children.json["members"] == []

    cross_genealogy = client.get(f"/genealogies/{ids['genealogy_id']}/tree-node/{other_member_id}")
    assert cross_genealogy.status_code == 404

    indent_focus = client.get(f"/genealogies/{ids['genealogy_id']}/tree/member/{ids['father_id']}")
    assert indent_focus.status_code == 200
    assert indent_focus.json["id"] == ids["father_id"]

    indent_cross_genealogy = client.get(f"/genealogies/{ids['genealogy_id']}/tree/member/{other_member_id}")
    assert indent_cross_genealogy.status_code == 404


def test_lazy_ancestor_tree_loads_one_generation_at_a_time(app, client):
    with app.app_context():
        ids = seed_user_genealogy_members()
        grandfather = Member(name="祖父", gender="male", birth_year=1940, generation_no=1, genealogy_id=ids["genealogy_id"])
        db.session.add(grandfather)
        db.session.flush()
        db.session.add_all(
            [
                ParentChildRelation(
                    genealogy_id=ids["genealogy_id"],
                    parent_member_id=ids["father_id"],
                    child_member_id=ids["child_id"],
                    parent_role="father",
                ),
                ParentChildRelation(
                    genealogy_id=ids["genealogy_id"],
                    parent_member_id=ids["mother_id"],
                    child_member_id=ids["child_id"],
                    parent_role="mother",
                ),
                ParentChildRelation(
                    genealogy_id=ids["genealogy_id"],
                    parent_member_id=grandfather.id,
                    child_member_id=ids["father_id"],
                    parent_role="father",
                ),
            ]
        )
        db.session.commit()
        grandfather_id = grandfather.id

    unauthenticated = client.get(f"/members/{ids['child_id']}/ancestor-parents")
    assert unauthenticated.status_code == 302

    login(client)

    page = client.get(f"/members/{ids['child_id']}/ancestors")
    assert page.status_code == 200
    assert "ancestor-tree".encode() in page.data
    assert "父亲".encode() in page.data
    assert "祖父".encode() not in page.data

    direct_parents = client.get(f"/members/{ids['child_id']}/ancestor-parents")
    assert direct_parents.status_code == 200
    assert {parent["id"] for parent in direct_parents.json["parents"]} == {ids["father_id"], ids["mother_id"]}

    next_generation = client.get(f"/members/{ids['father_id']}/ancestor-parents")
    assert next_generation.status_code == 200
    assert [parent["id"] for parent in next_generation.json["parents"]] == [grandfather_id]


def test_members_list_paginates_and_preserves_search(app, client):
    with app.app_context():
        ids = seed_user_genealogy_members()
        extra_members = [
            Member(
                name=f"分页成员{i:02d}",
                gender="unknown",
                generation_no=2 + i,
                genealogy_id=ids["genealogy_id"],
            )
            for i in range(80)
        ]
        db.session.add_all(extra_members)
        db.session.commit()

    login(client)

    first_page = client.get(f"/genealogies/{ids['genealogy_id']}/members")
    assert first_page.status_code == 200
    assert "共 84 位成员".encode() in first_page.data
    assert "第 1 / 2 页".encode() in first_page.data

    second_page = client.get(f"/genealogies/{ids['genealogy_id']}/members?page=2")
    assert second_page.status_code == 200
    assert "分页成员".encode() in second_page.data

    per_page_75 = client.get(f"/genealogies/{ids['genealogy_id']}/members?per_page=75")
    assert per_page_75.status_code == 200
    assert "第 1 / 2 页".encode() in per_page_75.data

    searched = client.get(f"/genealogies/{ids['genealogy_id']}/members?q=分页成员7&per_page=75")
    assert searched.status_code == 200
    assert 'value="分页成员7"'.encode() in searched.data
    assert "per_page=75".encode() in searched.data

    searched_by_id = client.get(f"/genealogies/{ids['genealogy_id']}/members?member_id={ids['child_id']}")
    assert searched_by_id.status_code == 200
    assert "孩子".encode() in searched_by_id.data
    assert "父亲".encode() not in searched_by_id.data
