"""add relationship integrity triggers

Revision ID: 8ef1ddc6ab24
Revises: eb4cc1a0641e
Create Date: 2026-04-30 19:22:15.034735

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = '8ef1ddc6ab24'
down_revision = 'eb4cc1a0641e'
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE OR REPLACE FUNCTION validate_parent_child_relation()
        RETURNS trigger AS $$
        DECLARE
            parent_record members%ROWTYPE;
            child_record members%ROWTYPE;
        BEGIN
            SELECT * INTO parent_record FROM members WHERE id = NEW.parent_member_id;
            SELECT * INTO child_record FROM members WHERE id = NEW.child_member_id;

            IF parent_record.id IS NULL OR child_record.id IS NULL THEN
                RAISE EXCEPTION 'parent or child member does not exist';
            END IF;

            IF parent_record.genealogy_id <> NEW.genealogy_id
               OR child_record.genealogy_id <> NEW.genealogy_id THEN
                RAISE EXCEPTION 'parent and child must belong to the same genealogy';
            END IF;

            IF parent_record.generation_no >= child_record.generation_no THEN
                RAISE EXCEPTION 'parent generation must be less than child generation';
            END IF;

            IF parent_record.birth_year IS NOT NULL
               AND child_record.birth_year IS NOT NULL
               AND parent_record.birth_year >= child_record.birth_year THEN
                RAISE EXCEPTION 'parent birth year must be earlier than child birth year';
            END IF;

            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION validate_marriage_relation()
        RETURNS trigger AS $$
        DECLARE
            spouse1_record members%ROWTYPE;
            spouse2_record members%ROWTYPE;
        BEGIN
            SELECT * INTO spouse1_record FROM members WHERE id = NEW.spouse1_member_id;
            SELECT * INTO spouse2_record FROM members WHERE id = NEW.spouse2_member_id;

            IF spouse1_record.id IS NULL OR spouse2_record.id IS NULL THEN
                RAISE EXCEPTION 'spouse member does not exist';
            END IF;

            IF spouse1_record.genealogy_id <> NEW.genealogy_id
               OR spouse2_record.genealogy_id <> NEW.genealogy_id THEN
                RAISE EXCEPTION 'spouses must belong to the same genealogy';
            END IF;

            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION validate_member_existing_relations()
        RETURNS trigger AS $$
        DECLARE
            invalid_count integer;
        BEGIN
            SELECT COUNT(*) INTO invalid_count
            FROM parent_child_relations rel
            JOIN members parent_member ON parent_member.id = rel.parent_member_id
            JOIN members child_member ON child_member.id = rel.child_member_id
            WHERE (rel.parent_member_id = NEW.id OR rel.child_member_id = NEW.id)
              AND (
                  parent_member.genealogy_id <> rel.genealogy_id
                  OR child_member.genealogy_id <> rel.genealogy_id
                  OR parent_member.generation_no >= child_member.generation_no
                  OR (
                      parent_member.birth_year IS NOT NULL
                      AND child_member.birth_year IS NOT NULL
                      AND parent_member.birth_year >= child_member.birth_year
                  )
              );

            IF invalid_count > 0 THEN
                RAISE EXCEPTION 'member update would violate existing parent-child relations';
            END IF;

            SELECT COUNT(*) INTO invalid_count
            FROM marriages marriage
            JOIN members spouse1_member ON spouse1_member.id = marriage.spouse1_member_id
            JOIN members spouse2_member ON spouse2_member.id = marriage.spouse2_member_id
            WHERE (marriage.spouse1_member_id = NEW.id OR marriage.spouse2_member_id = NEW.id)
              AND (
                  spouse1_member.genealogy_id <> marriage.genealogy_id
                  OR spouse2_member.genealogy_id <> marriage.genealogy_id
              );

            IF invalid_count > 0 THEN
                RAISE EXCEPTION 'member update would violate existing marriage relations';
            END IF;

            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_validate_parent_child_relation
        BEFORE INSERT OR UPDATE ON parent_child_relations
        FOR EACH ROW
        EXECUTE FUNCTION validate_parent_child_relation();
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_validate_marriage_relation
        BEFORE INSERT OR UPDATE ON marriages
        FOR EACH ROW
        EXECUTE FUNCTION validate_marriage_relation();
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_validate_member_existing_relations
        AFTER UPDATE OF genealogy_id, birth_year, generation_no ON members
        FOR EACH ROW
        EXECUTE FUNCTION validate_member_existing_relations();
        """
    )


def downgrade():
    op.execute("DROP TRIGGER IF EXISTS trg_validate_member_existing_relations ON members;")
    op.execute("DROP TRIGGER IF EXISTS trg_validate_marriage_relation ON marriages;")
    op.execute("DROP TRIGGER IF EXISTS trg_validate_parent_child_relation ON parent_child_relations;")
    op.execute("DROP FUNCTION IF EXISTS validate_member_existing_relations();")
    op.execute("DROP FUNCTION IF EXISTS validate_marriage_relation();")
    op.execute("DROP FUNCTION IF EXISTS validate_parent_child_relation();")
