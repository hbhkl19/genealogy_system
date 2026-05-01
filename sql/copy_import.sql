-- Example PostgreSQL COPY import commands.
-- Adjust the absolute paths before running in psql.

TRUNCATE
    parent_child_relations,
    marriages,
    genealogy_collaborators,
    members,
    genealogies,
    users
RESTART IDENTITY CASCADE;

\copy users (id, username, email, password_hash) FROM 'data/generated/users.csv' WITH (FORMAT csv, HEADER true);
\copy genealogies (id, name, description, owner_id) FROM 'data/generated/genealogies.csv' WITH (FORMAT csv, HEADER true);
\copy genealogy_collaborators (id, genealogy_id, user_id, role) FROM 'data/generated/genealogy_collaborators.csv' WITH (FORMAT csv, HEADER true);
\copy members (id, genealogy_id, name, gender, birth_year, death_year, biography, generation_no) FROM 'data/generated/members.csv' WITH (FORMAT csv, HEADER true);
\copy parent_child_relations (id, genealogy_id, parent_member_id, child_member_id, parent_role) FROM 'data/generated/parent_child_relations.csv' WITH (FORMAT csv, HEADER true);
\copy marriages (id, genealogy_id, spouse1_member_id, spouse2_member_id, married_year, ended_year) FROM 'data/generated/marriages.csv' WITH (FORMAT csv, HEADER true);

SELECT setval(pg_get_serial_sequence('users', 'id'), COALESCE((SELECT MAX(id) FROM users), 1), true);
SELECT setval(pg_get_serial_sequence('genealogies', 'id'), COALESCE((SELECT MAX(id) FROM genealogies), 1), true);
SELECT setval(pg_get_serial_sequence('genealogy_collaborators', 'id'), COALESCE((SELECT MAX(id) FROM genealogy_collaborators), 1), true);
SELECT setval(pg_get_serial_sequence('members', 'id'), COALESCE((SELECT MAX(id) FROM members), 1), true);
SELECT setval(pg_get_serial_sequence('parent_child_relations', 'id'), COALESCE((SELECT MAX(id) FROM parent_child_relations), 1), true);
SELECT setval(pg_get_serial_sequence('marriages', 'id'), COALESCE((SELECT MAX(id) FROM marriages), 1), true);
