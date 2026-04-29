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
    assert "/relationship/path" in routes
    assert "/members/<int:id>/edit" in routes
    assert "/members/<int:id>/delete" in routes
    assert "/members/<int:id>/relations" in routes


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
