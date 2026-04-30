from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_relationship_trigger_migration_exists():
    migration = ROOT / "migrations" / "versions" / "8ef1ddc6ab24_add_relationship_integrity_triggers.py"
    content = migration.read_text(encoding="utf-8")

    assert "validate_parent_child_relation" in content
    assert "validate_marriage_relation" in content
    assert "validate_member_existing_relations" in content
    assert "trg_validate_parent_child_relation" in content
    assert "trg_validate_marriage_relation" in content


def test_schema_contains_trigger_definitions():
    schema = (ROOT / "sql" / "schema.sql").read_text(encoding="utf-8")

    assert "CREATE OR REPLACE FUNCTION validate_parent_child_relation" in schema
    assert "CREATE TRIGGER trg_validate_parent_child_relation" in schema
    assert "CREATE TRIGGER trg_validate_member_existing_relations" in schema


def test_data_model_document_covers_er_and_3nf():
    document = (ROOT / "docs" / "data_model.md").read_text(encoding="utf-8")

    assert "erDiagram" in document
    assert "关系模式" in document
    assert "3NF" in document
    assert "跨行约束使用 PostgreSQL 触发器" in document
