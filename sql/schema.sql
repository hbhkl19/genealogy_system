CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(64) NOT NULL UNIQUE,
    email VARCHAR(120) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS genealogies (
    id SERIAL PRIMARY KEY,
    name VARCHAR(120) NOT NULL,
    surname VARCHAR(40),
    revision_year INTEGER,
    description TEXT,
    owner_id INTEGER NOT NULL REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS genealogy_collaborators (
    id SERIAL PRIMARY KEY,
    genealogy_id INTEGER NOT NULL REFERENCES genealogies(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id),
    role VARCHAR(20) NOT NULL DEFAULT 'editor',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_genealogy_collaborator UNIQUE (genealogy_id, user_id),
    CONSTRAINT ck_collaborator_role CHECK (role IN ('viewer', 'editor'))
);

CREATE TABLE IF NOT EXISTS members (
    id SERIAL PRIMARY KEY,
    genealogy_id INTEGER NOT NULL REFERENCES genealogies(id) ON DELETE CASCADE,
    name VARCHAR(120) NOT NULL,
    gender VARCHAR(10) NOT NULL,
    birth_year INTEGER,
    death_year INTEGER,
    biography TEXT,
    generation_no INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_member_gender CHECK (gender IN ('male', 'female', 'unknown')),
    CONSTRAINT ck_member_life_years CHECK (death_year IS NULL OR birth_year IS NULL OR death_year >= birth_year),
    CONSTRAINT ck_member_generation CHECK (generation_no >= 1)
);

CREATE TABLE IF NOT EXISTS parent_child_relations (
    id SERIAL PRIMARY KEY,
    genealogy_id INTEGER NOT NULL REFERENCES genealogies(id) ON DELETE CASCADE,
    parent_member_id INTEGER NOT NULL REFERENCES members(id) ON DELETE CASCADE,
    child_member_id INTEGER NOT NULL REFERENCES members(id) ON DELETE CASCADE,
    parent_role VARCHAR(10) NOT NULL,
    CONSTRAINT uq_parent_child UNIQUE (parent_member_id, child_member_id),
    CONSTRAINT uq_child_parent_role UNIQUE (child_member_id, parent_role),
    CONSTRAINT ck_parent_not_child CHECK (parent_member_id <> child_member_id),
    CONSTRAINT ck_parent_role CHECK (parent_role IN ('father', 'mother'))
);

CREATE TABLE IF NOT EXISTS marriages (
    id SERIAL PRIMARY KEY,
    genealogy_id INTEGER NOT NULL REFERENCES genealogies(id) ON DELETE CASCADE,
    spouse1_member_id INTEGER NOT NULL REFERENCES members(id) ON DELETE CASCADE,
    spouse2_member_id INTEGER NOT NULL REFERENCES members(id) ON DELETE CASCADE,
    married_year INTEGER,
    ended_year INTEGER,
    CONSTRAINT uq_marriage_pair UNIQUE (spouse1_member_id, spouse2_member_id),
    CONSTRAINT ck_marriage_ordered_pair CHECK (spouse1_member_id < spouse2_member_id),
    CONSTRAINT ck_marriage_years CHECK (ended_year IS NULL OR married_year IS NULL OR ended_year >= married_year)
);

CREATE INDEX IF NOT EXISTS ix_genealogies_owner_id ON genealogies(owner_id);
CREATE INDEX IF NOT EXISTS ix_members_genealogy_id ON members(genealogy_id);
CREATE INDEX IF NOT EXISTS ix_members_name_trgm ON members USING gin (name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS ix_parent_child_genealogy_parent ON parent_child_relations(genealogy_id, parent_member_id);
CREATE INDEX IF NOT EXISTS ix_parent_child_genealogy_child ON parent_child_relations(genealogy_id, child_member_id);
CREATE INDEX IF NOT EXISTS ix_marriages_genealogy_spouse1 ON marriages(genealogy_id, spouse1_member_id);
CREATE INDEX IF NOT EXISTS ix_marriages_genealogy_spouse2 ON marriages(genealogy_id, spouse2_member_id);

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

DROP TRIGGER IF EXISTS trg_validate_parent_child_relation ON parent_child_relations;
CREATE TRIGGER trg_validate_parent_child_relation
BEFORE INSERT OR UPDATE ON parent_child_relations
FOR EACH ROW
EXECUTE FUNCTION validate_parent_child_relation();

DROP TRIGGER IF EXISTS trg_validate_marriage_relation ON marriages;
CREATE TRIGGER trg_validate_marriage_relation
BEFORE INSERT OR UPDATE ON marriages
FOR EACH ROW
EXECUTE FUNCTION validate_marriage_relation();

DROP TRIGGER IF EXISTS trg_validate_member_existing_relations ON members;
CREATE TRIGGER trg_validate_member_existing_relations
AFTER UPDATE OF genealogy_id, birth_year, generation_no ON members
FOR EACH ROW
EXECUTE FUNCTION validate_member_existing_relations();

CREATE OR REPLACE FUNCTION bfs_reachable(
    p_genealogy_id INTEGER,
    p_root_id INTEGER,
    p_max_depth INTEGER
) RETURNS TABLE(member_id INTEGER, depth INTEGER) AS $$
DECLARE
    current_depth INTEGER := 0;
    row_count INTEGER;
BEGIN
    CREATE TEMP TABLE IF NOT EXISTS bfs_visited (
        vid INTEGER PRIMARY KEY,
        vdepth INTEGER NOT NULL
    ) ON COMMIT DROP;
    TRUNCATE bfs_visited;

    INSERT INTO bfs_visited VALUES (p_root_id, 0);

    LOOP
        EXIT WHEN current_depth >= p_max_depth;

        INSERT INTO bfs_visited
        SELECT DISTINCT e.to_id, current_depth + 1
        FROM bfs_visited v
        CROSS JOIN LATERAL (
            SELECT parent_member_id AS to_id
            FROM parent_child_relations
            WHERE genealogy_id = p_genealogy_id
              AND child_member_id = v.vid
            UNION ALL
            SELECT child_member_id
            FROM parent_child_relations
            WHERE genealogy_id = p_genealogy_id
              AND parent_member_id = v.vid
            UNION ALL
            SELECT spouse2_member_id
            FROM marriages
            WHERE genealogy_id = p_genealogy_id
              AND spouse1_member_id = v.vid
            UNION ALL
            SELECT spouse1_member_id
            FROM marriages
            WHERE genealogy_id = p_genealogy_id
              AND spouse2_member_id = v.vid
        ) e
        WHERE v.vdepth = current_depth
          AND e.to_id IS NOT NULL
        ON CONFLICT (vid) DO NOTHING;

        GET DIAGNOSTICS row_count = ROW_COUNT;
        EXIT WHEN row_count = 0;
        current_depth := current_depth + 1;
    END LOOP;

    RETURN QUERY SELECT v.vid, v.vdepth FROM bfs_visited v;
END;
$$ LANGUAGE plpgsql;
