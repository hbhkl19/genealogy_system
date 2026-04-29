from datetime import datetime, timezone

from flask_login import UserMixin
from sqlalchemy import CheckConstraint, Index, UniqueConstraint, text
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db, login_manager


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), nullable=False, unique=True, index=True)
    email = db.Column(db.String(120), nullable=False, unique=True, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=db.func.now(),
    )

    genealogies = db.relationship("Genealogy", back_populates="owner", lazy="dynamic")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


class Genealogy(db.Model):
    __tablename__ = "genealogies"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text)
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=db.func.now(),
    )

    owner = db.relationship("User", back_populates="genealogies")
    collaborators = db.relationship(
        "GenealogyCollaborator",
        back_populates="genealogy",
        cascade="all, delete-orphan",
    )
    members = db.relationship(
        "Member",
        back_populates="genealogy",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )


class GenealogyCollaborator(db.Model):
    __tablename__ = "genealogy_collaborators"

    id = db.Column(db.Integer, primary_key=True)
    genealogy_id = db.Column(
        db.Integer,
        db.ForeignKey("genealogies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    role = db.Column(db.String(20), nullable=False, default="editor", server_default="editor")
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=db.func.now(),
    )

    genealogy = db.relationship("Genealogy", back_populates="collaborators")
    user = db.relationship("User")

    __table_args__ = (
        UniqueConstraint("genealogy_id", "user_id", name="uq_genealogy_collaborator"),
        CheckConstraint("role in ('viewer', 'editor')", name="ck_collaborator_role"),
    )


class Member(db.Model):
    __tablename__ = "members"

    id = db.Column(db.Integer, primary_key=True)
    genealogy_id = db.Column(
        db.Integer,
        db.ForeignKey("genealogies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name = db.Column(db.String(120), nullable=False, index=True)
    gender = db.Column(db.String(10), nullable=False)
    birth_year = db.Column(db.Integer)
    death_year = db.Column(db.Integer)
    biography = db.Column(db.Text)
    generation_no = db.Column(db.Integer, nullable=False, default=1, server_default="1")
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=db.func.now(),
    )

    genealogy = db.relationship("Genealogy", back_populates="members")

    __table_args__ = (
        CheckConstraint("gender in ('male', 'female', 'unknown')", name="ck_member_gender"),
        CheckConstraint("death_year is null or birth_year is null or death_year >= birth_year", name="ck_member_life_years"),
        CheckConstraint("generation_no >= 1", name="ck_member_generation"),
        Index("ix_members_name_trgm", "name", postgresql_using="gin", postgresql_ops={"name": "gin_trgm_ops"}),
    )


class ParentChildRelation(db.Model):
    __tablename__ = "parent_child_relations"

    id = db.Column(db.Integer, primary_key=True)
    genealogy_id = db.Column(
        db.Integer,
        db.ForeignKey("genealogies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    parent_member_id = db.Column(
        db.Integer,
        db.ForeignKey("members.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    child_member_id = db.Column(
        db.Integer,
        db.ForeignKey("members.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    parent_role = db.Column(db.String(10), nullable=False)

    parent = db.relationship("Member", foreign_keys=[parent_member_id])
    child = db.relationship("Member", foreign_keys=[child_member_id])

    __table_args__ = (
        UniqueConstraint("parent_member_id", "child_member_id", name="uq_parent_child"),
        CheckConstraint("parent_member_id <> child_member_id", name="ck_parent_not_child"),
        CheckConstraint("parent_role in ('father', 'mother')", name="ck_parent_role"),
        Index("ix_parent_child_genealogy_parent", "genealogy_id", "parent_member_id"),
        Index("ix_parent_child_genealogy_child", "genealogy_id", "child_member_id"),
    )


class Marriage(db.Model):
    __tablename__ = "marriages"

    id = db.Column(db.Integer, primary_key=True)
    genealogy_id = db.Column(
        db.Integer,
        db.ForeignKey("genealogies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    spouse1_member_id = db.Column(
        db.Integer,
        db.ForeignKey("members.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    spouse2_member_id = db.Column(
        db.Integer,
        db.ForeignKey("members.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    married_year = db.Column(db.Integer)
    ended_year = db.Column(db.Integer)

    spouse1 = db.relationship("Member", foreign_keys=[spouse1_member_id])
    spouse2 = db.relationship("Member", foreign_keys=[spouse2_member_id])

    __table_args__ = (
        UniqueConstraint("spouse1_member_id", "spouse2_member_id", name="uq_marriage_pair"),
        CheckConstraint("spouse1_member_id < spouse2_member_id", name="ck_marriage_ordered_pair"),
        CheckConstraint("ended_year is null or married_year is null or ended_year >= married_year", name="ck_marriage_years"),
        Index("ix_marriages_genealogy_spouse1", "genealogy_id", "spouse1_member_id"),
        Index("ix_marriages_genealogy_spouse2", "genealogy_id", "spouse2_member_id"),
    )


def accessible_genealogy_query(user):
    collaborator_subquery = (
        db.session.query(GenealogyCollaborator.genealogy_id)
        .filter(GenealogyCollaborator.user_id == user.id)
        .subquery()
    )
    return Genealogy.query.filter(
        (Genealogy.owner_id == user.id) | (Genealogy.id.in_(collaborator_subquery))
    )


CREATE_TRIGRAM_EXTENSION_SQL = text("CREATE EXTENSION IF NOT EXISTS pg_trgm")
