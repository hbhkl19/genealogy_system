import csv
from pathlib import Path

from scripts.seed_data import generate_dataset


def read_rows(path: Path):
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_generate_dataset_outputs_consistent_edges():
    output_dir = Path("data/test_pytest_generation")
    summary = generate_dataset(output_dir, sizes=[20, 10], generations=5, seed=1)

    assert summary["genealogies"] == 2
    assert summary["members"] == 30
    assert summary["max_generation_no"] == 5

    members = read_rows(output_dir / "members.csv")
    parent_child = read_rows(output_dir / "parent_child_relations.csv")
    marriages = read_rows(output_dir / "marriages.csv")

    assert len(members) == 30
    assert len(parent_child) == 48
    assert len(marriages) == summary["marriages"]
    assert len(marriages) > 0

    member_ids = {row["id"] for row in members}
    edge_member_ids = set()
    for row in parent_child:
        assert row["parent_member_id"] in member_ids
        assert row["child_member_id"] in member_ids
        edge_member_ids.add(row["parent_member_id"])
        edge_member_ids.add(row["child_member_id"])
    for row in marriages:
        assert row["spouse1_member_id"] in member_ids
        assert row["spouse2_member_id"] in member_ids
        assert int(row["spouse1_member_id"]) < int(row["spouse2_member_id"])
        edge_member_ids.add(row["spouse1_member_id"])
        edge_member_ids.add(row["spouse2_member_id"])

    assert member_ids == edge_member_ids
