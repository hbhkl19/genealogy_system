"""Create a small demo account and genealogy without deleting existing data."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import create_app
from app.extensions import db
from app.models import Genealogy, Marriage, Member, ParentChildRelation, User


DEMO_EMAIL = "demo@example.com"
DEMO_PASSWORD = "demo123456"


def get_or_create_user() -> User:
    user = User.query.filter_by(email=DEMO_EMAIL).first()
    if user:
        user.set_password(DEMO_PASSWORD)
        return user
    user = User(username="demo", email=DEMO_EMAIL)
    user.set_password(DEMO_PASSWORD)
    db.session.add(user)
    db.session.flush()
    return user


def create_demo_genealogy(user: User) -> Genealogy:
    existing = Genealogy.query.filter_by(owner_id=user.id, name="演示族谱").first()
    if existing:
        return existing

    genealogy = Genealogy(name="演示族谱", description="用于课堂演示的三代小型族谱。", owner=user)
    db.session.add(genealogy)
    db.session.flush()

    members = [
        Member(genealogy=genealogy, name="赵明德", gender="male", birth_year=1940, generation_no=1),
        Member(genealogy=genealogy, name="李秀兰", gender="female", birth_year=1942, generation_no=1),
        Member(genealogy=genealogy, name="赵建国", gender="male", birth_year=1968, generation_no=2),
        Member(genealogy=genealogy, name="王芳", gender="female", birth_year=1970, generation_no=2),
        Member(genealogy=genealogy, name="赵一鸣", gender="male", birth_year=1995, generation_no=3),
        Member(genealogy=genealogy, name="赵雨晴", gender="female", birth_year=1998, generation_no=3),
    ]
    db.session.add_all(members)
    db.session.flush()

    grandfather, grandmother, father, mother, son, daughter = members
    relations = [
        ParentChildRelation(genealogy_id=genealogy.id, parent_member_id=grandfather.id, child_member_id=father.id, parent_role="father"),
        ParentChildRelation(genealogy_id=genealogy.id, parent_member_id=grandmother.id, child_member_id=father.id, parent_role="mother"),
        ParentChildRelation(genealogy_id=genealogy.id, parent_member_id=father.id, child_member_id=son.id, parent_role="father"),
        ParentChildRelation(genealogy_id=genealogy.id, parent_member_id=mother.id, child_member_id=son.id, parent_role="mother"),
        ParentChildRelation(genealogy_id=genealogy.id, parent_member_id=father.id, child_member_id=daughter.id, parent_role="father"),
        ParentChildRelation(genealogy_id=genealogy.id, parent_member_id=mother.id, child_member_id=daughter.id, parent_role="mother"),
    ]
    marriages = [
        Marriage(genealogy_id=genealogy.id, spouse1_member_id=min(grandfather.id, grandmother.id), spouse2_member_id=max(grandfather.id, grandmother.id), married_year=1965),
        Marriage(genealogy_id=genealogy.id, spouse1_member_id=min(father.id, mother.id), spouse2_member_id=max(father.id, mother.id), married_year=1992),
    ]
    db.session.add_all(relations + marriages)
    return genealogy


def main() -> None:
    app = create_app()
    with app.app_context():
        user = get_or_create_user()
        genealogy = create_demo_genealogy(user)
        db.session.commit()
        print("Demo data ready:")
        print(f"- login email: {DEMO_EMAIL}")
        print(f"- login password: {DEMO_PASSWORD}")
        print(f"- genealogy id: {genealogy.id}")


if __name__ == "__main__":
    main()
