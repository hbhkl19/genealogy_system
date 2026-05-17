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
    assert summary["members"] >= 30
    assert summary["max_generation_no"] == 5

    members = read_rows(output_dir / "members.csv")
    genealogies = read_rows(output_dir / "genealogies.csv")
    parent_child = read_rows(output_dir / "parent_child_relations.csv")
    marriages = read_rows(output_dir / "marriages.csv")

    assert len(members) == summary["members"]
    assert len(parent_child) == summary["parent_child_relations"]
    assert len(marriages) == summary["marriages"]
    assert len(marriages) > 0

    genealogy_surnames = {row["id"]: row["surname"] for row in genealogies}
    member_by_id = {row["id"]: row for row in members}
    for row in members:
        assert row["name"].startswith(genealogy_surnames[row["genealogy_id"]])

    member_ids = {row["id"] for row in members}
    edge_member_ids = set()
    parent_roles = {}
    for row in parent_child:
        assert row["parent_member_id"] in member_ids
        assert row["child_member_id"] in member_ids
        parent_roles[(row["child_member_id"], row["parent_role"])] = row["parent_member_id"]
        edge_member_ids.add(row["parent_member_id"])
        edge_member_ids.add(row["child_member_id"])
        parent = member_by_id[row["parent_member_id"]]
        child = member_by_id[row["child_member_id"]]
        if row["parent_role"] == "father":
            assert parent["gender"] == "male"
            assert parent["genealogy_id"] == child["genealogy_id"]
            assert child["name"].startswith(genealogy_surnames[parent["genealogy_id"]])
        else:
            assert parent["gender"] == "female"
    for row in marriages:
        assert row["spouse1_member_id"] in member_ids
        assert row["spouse2_member_id"] in member_ids
        assert int(row["spouse1_member_id"]) < int(row["spouse2_member_id"])
        spouse1 = member_by_id[row["spouse1_member_id"]]
        spouse2 = member_by_id[row["spouse2_member_id"]]
        assert spouse1["genealogy_id"] != spouse2["genealogy_id"]
        edge_member_ids.add(row["spouse1_member_id"])
        edge_member_ids.add(row["spouse2_member_id"])

    married_member_ids = {
        member_id
        for row in marriages
        for member_id in (row["spouse1_member_id"], row["spouse2_member_id"])
    }
    for row in parent_child:
        assert row["parent_member_id"] in married_member_ids

    for child_id, father_id in [
        (child_id, parent_id)
        for (child_id, role), parent_id in parent_roles.items()
        if role == "father"
    ]:
        mother_id = parent_roles.get((child_id, "mother"))
        assert mother_id is not None
        father = member_by_id[father_id]
        mother = member_by_id[mother_id]
        assert father["genealogy_id"] != mother["genealogy_id"]

    assert member_ids == edge_member_ids
