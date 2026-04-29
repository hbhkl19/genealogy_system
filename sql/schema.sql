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
