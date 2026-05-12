"""Create a demo genealogy with realistic Chinese family data for presentations.

Generates a 5-generation, 20-member family tree with:
- death years for older generations (supports lifespan queries)
- one lifelong-unmarried elder male (supports task 4.4)
- birth-year variation within generations (supports task 4.5)
- short biographies
"""

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

    genealogy = Genealogy(
        name="演示族谱",
        description="赵氏家族五代演示数据，含真实姓名、生卒年、婚姻与血缘关系，用于课堂 SQL 查询演示。",
        owner=user,
    )
    db.session.add(genealogy)
    db.session.flush()

    # ── Generation 1 (曾祖) ──
    g1_m = Member(genealogy=genealogy, name="赵德厚", gender="male",
                  birth_year=1920, death_year=2005, generation_no=1,
                  biography="赵氏曾祖父，务农为生，一生勤劳俭朴。")
    g1_f = Member(genealogy=genealogy, name="陈秀英", gender="female",
                  birth_year=1923, death_year=2008, generation_no=1,
                  biography="赵氏曾祖母，擅长纺织，邻里称贤。")
    g1_u = Member(genealogy=genealogy, name="赵德广", gender="male",
                  birth_year=1925, death_year=2015, generation_no=1,
                  biography="赵德厚之弟，终身未婚，以木匠手艺闻名乡里。")

    # ── Generation 2 (祖) ──
    g2_a1 = Member(genealogy=genealogy, name="赵明礼", gender="male",
                   birth_year=1945, death_year=2020, generation_no=2,
                   biography="长子，中学教师，桃李满天下。")
    g2_a2 = Member(genealogy=genealogy, name="王兰芳", gender="female",
                   birth_year=1948, death_year=2018, generation_no=2,
                   biography="赵明礼之妻，医护工作者。")
    g2_b1 = Member(genealogy=genealogy, name="赵明义", gender="male",
                   birth_year=1950, death_year=2019, generation_no=2,
                   biography="次子，工程师，参与多项国家基建。")
    g2_b2 = Member(genealogy=genealogy, name="李桂花", gender="female",
                   birth_year=1953, death_year=2023, generation_no=2,
                   biography="赵明义之妻，供销社退休职工。")

    # ── Generation 3 (父) ──
    g3_a1 = Member(genealogy=genealogy, name="赵建国", gender="male",
                   birth_year=1970, generation_no=3,
                   biography="赵明礼长子，企业管理者。")
    g3_a2 = Member(genealogy=genealogy, name="周丽华", gender="female",
                   birth_year=1972, generation_no=3,
                   biography="赵建国之妻，银行职员。")
    g3_b1 = Member(genealogy=genealogy, name="赵建军", gender="male",
                   birth_year=1973, death_year=2024, generation_no=3,
                   biography="赵明义长子，不幸因车祸早逝。")
    g3_b2 = Member(genealogy=genealogy, name="刘雪梅", gender="female",
                   birth_year=1976, generation_no=3,
                   biography="赵建军之妻，小学教师。")

    # ── Generation 4 (子女及配偶) ──
    g4_a1 = Member(genealogy=genealogy, name="赵一鸣", gender="male",
                   birth_year=1995, generation_no=4,
                   biography="赵建国长子，软件工程师。")
    g4_a2 = Member(genealogy=genealogy, name="秦晓燕", gender="female",
                   birth_year=1996, generation_no=4,
                   biography="赵一鸣之妻，中学美术教师。")
    g4_a3 = Member(genealogy=genealogy, name="赵雨晴", gender="female",
                   birth_year=1998, generation_no=4,
                   biography="赵建国之女，在读博士。")
    g4_b1 = Member(genealogy=genealogy, name="赵一飞", gender="male",
                   birth_year=1997, generation_no=4,
                   biography="赵建军长子，医生。")
    g4_b2 = Member(genealogy=genealogy, name="孙婷婷", gender="female",
                   birth_year=1999, generation_no=4,
                   biography="赵一飞之妻，护士。")
    g4_b3 = Member(genealogy=genealogy, name="赵雨欣", gender="female",
                   birth_year=2000, generation_no=4,
                   biography="赵建军之女，设计师。")

    # ── Generation 5 (孙) ──
    g5_a1 = Member(genealogy=genealogy, name="赵小宇", gender="male",
                   birth_year=2020, generation_no=5,
                   biography="赵一鸣之子，活泼好动。")
    g5_a2 = Member(genealogy=genealogy, name="赵小悦", gender="female",
                   birth_year=2022, generation_no=5,
                   biography="赵一鸣之女，聪明伶俐。")
    g5_b1 = Member(genealogy=genealogy, name="赵小航", gender="male",
                   birth_year=2021, generation_no=5,
                   biography="赵一飞之子，爱好足球。")

    all_members = [
        g1_m, g1_f, g1_u,
        g2_a1, g2_a2, g2_b1, g2_b2,
        g3_a1, g3_a2, g3_b1, g3_b2,
        g4_a1, g4_a2, g4_a3, g4_b1, g4_b2, g4_b3,
        g5_a1, g5_a2, g5_b1,
    ]
    db.session.add_all(all_members)
    db.session.flush()

    # ── Parent-Child Relations ──
    rels = [
        # 赵德厚 + 陈秀英 → 赵明礼, 赵明义
        ParentChildRelation(genealogy_id=genealogy.id, parent_member_id=g1_m.id, child_member_id=g2_a1.id, parent_role="father"),
        ParentChildRelation(genealogy_id=genealogy.id, parent_member_id=g1_f.id, child_member_id=g2_a1.id, parent_role="mother"),
        ParentChildRelation(genealogy_id=genealogy.id, parent_member_id=g1_m.id, child_member_id=g2_b1.id, parent_role="father"),
        ParentChildRelation(genealogy_id=genealogy.id, parent_member_id=g1_f.id, child_member_id=g2_b1.id, parent_role="mother"),
        # 赵明礼 + 王兰芳 → 赵建国
        ParentChildRelation(genealogy_id=genealogy.id, parent_member_id=g2_a1.id, child_member_id=g3_a1.id, parent_role="father"),
        ParentChildRelation(genealogy_id=genealogy.id, parent_member_id=g2_a2.id, child_member_id=g3_a1.id, parent_role="mother"),
        # 赵明义 + 李桂花 → 赵建军
        ParentChildRelation(genealogy_id=genealogy.id, parent_member_id=g2_b1.id, child_member_id=g3_b1.id, parent_role="father"),
        ParentChildRelation(genealogy_id=genealogy.id, parent_member_id=g2_b2.id, child_member_id=g3_b1.id, parent_role="mother"),
        # 赵建国 + 周丽华 → 赵一鸣, 赵雨晴
        ParentChildRelation(genealogy_id=genealogy.id, parent_member_id=g3_a1.id, child_member_id=g4_a1.id, parent_role="father"),
        ParentChildRelation(genealogy_id=genealogy.id, parent_member_id=g3_a2.id, child_member_id=g4_a1.id, parent_role="mother"),
        ParentChildRelation(genealogy_id=genealogy.id, parent_member_id=g3_a1.id, child_member_id=g4_a3.id, parent_role="father"),
        ParentChildRelation(genealogy_id=genealogy.id, parent_member_id=g3_a2.id, child_member_id=g4_a3.id, parent_role="mother"),
        # 赵建军 + 刘雪梅 → 赵一飞, 赵雨欣
        ParentChildRelation(genealogy_id=genealogy.id, parent_member_id=g3_b1.id, child_member_id=g4_b1.id, parent_role="father"),
        ParentChildRelation(genealogy_id=genealogy.id, parent_member_id=g3_b2.id, child_member_id=g4_b1.id, parent_role="mother"),
        ParentChildRelation(genealogy_id=genealogy.id, parent_member_id=g3_b1.id, child_member_id=g4_b3.id, parent_role="father"),
        ParentChildRelation(genealogy_id=genealogy.id, parent_member_id=g3_b2.id, child_member_id=g4_b3.id, parent_role="mother"),
        # 赵一鸣 + 秦晓燕 → 赵小宇, 赵小悦
        ParentChildRelation(genealogy_id=genealogy.id, parent_member_id=g4_a1.id, child_member_id=g5_a1.id, parent_role="father"),
        ParentChildRelation(genealogy_id=genealogy.id, parent_member_id=g4_a2.id, child_member_id=g5_a1.id, parent_role="mother"),
        ParentChildRelation(genealogy_id=genealogy.id, parent_member_id=g4_a1.id, child_member_id=g5_a2.id, parent_role="father"),
        ParentChildRelation(genealogy_id=genealogy.id, parent_member_id=g4_a2.id, child_member_id=g5_a2.id, parent_role="mother"),
        # 赵一飞 + 孙婷婷 → 赵小航
        ParentChildRelation(genealogy_id=genealogy.id, parent_member_id=g4_b1.id, child_member_id=g5_b1.id, parent_role="father"),
        ParentChildRelation(genealogy_id=genealogy.id, parent_member_id=g4_b2.id, child_member_id=g5_b1.id, parent_role="mother"),
    ]

    # ── Marriages ──
    mrs = [
        Marriage(genealogy_id=genealogy.id, spouse1_member_id=min(g1_m.id, g1_f.id), spouse2_member_id=max(g1_m.id, g1_f.id), married_year=1944),
        Marriage(genealogy_id=genealogy.id, spouse1_member_id=min(g2_a1.id, g2_a2.id), spouse2_member_id=max(g2_a1.id, g2_a2.id), married_year=1968),
        Marriage(genealogy_id=genealogy.id, spouse1_member_id=min(g2_b1.id, g2_b2.id), spouse2_member_id=max(g2_b1.id, g2_b2.id), married_year=1972),
        Marriage(genealogy_id=genealogy.id, spouse1_member_id=min(g3_a1.id, g3_a2.id), spouse2_member_id=max(g3_a1.id, g3_a2.id), married_year=1993),
        Marriage(genealogy_id=genealogy.id, spouse1_member_id=min(g3_b1.id, g3_b2.id), spouse2_member_id=max(g3_b1.id, g3_b2.id), married_year=1996),
        Marriage(genealogy_id=genealogy.id, spouse1_member_id=min(g4_a1.id, g4_a2.id), spouse2_member_id=max(g4_a1.id, g4_a2.id), married_year=2018),
        Marriage(genealogy_id=genealogy.id, spouse1_member_id=min(g4_b1.id, g4_b2.id), spouse2_member_id=max(g4_b1.id, g4_b2.id), married_year=2020),
    ]

    db.session.add_all(rels + mrs)
    return genealogy


def main() -> None:
    app = create_app()
    with app.app_context():
        user = get_or_create_user()
        genealogy = create_demo_genealogy(user)
        db.session.commit()
        member_count = Member.query.filter_by(genealogy_id=genealogy.id).count()
        print("Demo data ready:")
        print(f"- login:    {DEMO_EMAIL} / {DEMO_PASSWORD}")
        print(f"- genealogy: {genealogy.name} (id={genealogy.id}, {member_count} members)")
        print(f"- features: 5 generations, death years, 1 unmarried elder, birth-year variance")


if __name__ == "__main__":
    main()