"""Generate realistic Chinese genealogy CSV data for PostgreSQL COPY import.

Design principles:
- Each genealogy represents one patrilineal lineage with a fixed surname
- All marriages are inter-genealogy (avoids close-relative marriage)
- Children belong to the father's genealogy and carry the father's surname
- Generational growth follows a geometric progression from a few founders

Default output:
- 10 genealogies with distinct surnames
- ~110000 total members (50000 + 9×6000)
- 30 generations
"""

from __future__ import annotations

import argparse
import csv
import random
from dataclasses import dataclass
from pathlib import Path

from faker import Faker
from werkzeug.security import generate_password_hash


DEFAULT_SIZES = [50000] + [6000] * 9
BIRTH_SPREAD = 5
LIFESPAN_MIN = 55
LIFESPAN_MAX = 92
RECENT_GENERATIONS_ALIVE = 5

SURNAMES = [
    "张", "李", "王", "赵", "陈",
    "刘", "杨", "黄", "周", "吴",
    "徐", "孙", "马", "朱", "胡",
    "郭", "何", "高", "林", "罗",
]

CSV_FILES = {
    "users": "users.csv",
    "genealogies": "genealogies.csv",
    "members": "members.csv",
    "parent_child_relations": "parent_child_relations.csv",
    "marriages": "marriages.csv",
    "genealogy_collaborators": "genealogy_collaborators.csv",
}


@dataclass
class Counters:
    member_id: int = 1
    parent_child_id: int = 1
    marriage_id: int = 1

    @classmethod
    def with_offset(cls, offset: int) -> "Counters":
        return cls(member_id=1 + offset, parent_child_id=1 + offset, marriage_id=1 + offset)


def generation_targets(total_members: int, num_generations: int, founder_count: int = 8) -> list[int]:
    """Calculate target member counts per generation using geometric progression.

    Finds growth rate r such that:
      founder_count * (1 + r + r^2 + ... + r^(G-1)) ≈ total_members

    Returns a list of length num_generations with integer member counts.
    """
    lo, hi = 0.5, 2.5
    for _ in range(60):
        mid = (lo + hi) / 2
        total = founder_count * sum(mid ** i for i in range(num_generations))
        if total < total_members:
            lo = mid
        else:
            hi = mid
    r = (lo + hi) / 2

    targets = [max(2, int(founder_count * r ** i + 0.5)) for i in range(num_generations)]
    targets[0] = founder_count

    diff = total_members - sum(targets)
    if diff > 0:
        per_gen = max(1, diff // num_generations)
        for i in range(num_generations):
            add = min(per_gen, diff)
            targets[i] += add
            diff -= add
            if diff <= 0:
                break
    elif diff < 0:
        per_gen = max(1, -diff // num_generations)
        for i in range(num_generations - 1, -1, -1):
            sub = min(per_gen, -diff)
            if targets[i] - sub >= 2:
                targets[i] -= sub
                diff += sub
            if diff >= 0:
                break

    return targets


def birth_year_for(generation_no: int, rng: random.Random) -> int:
    base = 1930 + (generation_no - 1) * 25
    return base + rng.randint(-BIRTH_SPREAD, BIRTH_SPREAD)


def death_year_for(birth_year: int, generation_no: int, total_generations: int, rng: random.Random) -> int | str:
    if generation_no > total_generations - RECENT_GENERATIONS_ALIVE:
        if rng.random() < 0.5:
            return ""
    lifespan = rng.randint(LIFESPAN_MIN, LIFESPAN_MAX)
    return birth_year + lifespan


def given_name(fake: Faker, gender: str) -> str:
    """Generate a given name (without surname) appropriate for the gender."""
    full = fake.name()
    if len(full) >= 2:
        return full[1:] if len(full) <= 3 else full[0:2]
    return full


def open_writer(output_dir: Path, name: str, fieldnames: list[str]):
    output_dir.mkdir(parents=True, exist_ok=True)
    handle = (output_dir / CSV_FILES[name]).open("w", newline="", encoding="utf-8")
    writer = csv.DictWriter(handle, fieldnames=fieldnames)
    writer.writeheader()
    return handle, writer


def generate_dataset(
    output_dir: Path,
    sizes: list[int],
    generations: int,
    seed: int,
    id_offset: int = 0,
    skip_users: bool = False,
) -> dict[str, int]:
    fake = Faker("zh_CN")
    Faker.seed(seed)
    rng = random.Random(seed)
    counters = Counters.with_offset(id_offset)

    num_genealogies = len(sizes)

    handles = []
    try:
        users_handle, users_writer = open_writer(output_dir, "users", ["id", "username", "email", "password_hash"])
        genealogies_handle, genealogies_writer = open_writer(
            output_dir, "genealogies", ["id", "name", "surname", "revision_year", "description", "owner_id"],
        )
        members_handle, members_writer = open_writer(
            output_dir, "members",
            ["id", "genealogy_id", "name", "gender", "birth_year", "death_year", "biography", "generation_no"],
        )
        parent_child_handle, parent_child_writer = open_writer(
            output_dir, "parent_child_relations",
            ["id", "genealogy_id", "parent_member_id", "child_member_id", "parent_role"],
        )
        marriages_handle, marriages_writer = open_writer(
            output_dir, "marriages",
            ["id", "genealogy_id", "spouse1_member_id", "spouse2_member_id", "married_year", "ended_year"],
        )
        collaborators_handle, collaborators_writer = open_writer(
            output_dir, "genealogy_collaborators",
            ["id", "genealogy_id", "user_id", "role"],
        )
        handles.extend([
            users_handle, genealogies_handle, members_handle,
            parent_child_handle, marriages_handle, collaborators_handle,
        ])

        if not skip_users:
            users_writer.writerow({
                "id": 1, "username": "demo", "email": "demo@example.com",
                "password_hash": generate_password_hash("demo123456"),
            })

        for gi in range(num_genealogies):
            gid = gi + 1 + id_offset
            genealogies_writer.writerow({
                "id": gid,
                "name": f"{SURNAMES[gi]}氏族谱",
                "surname": SURNAMES[gi],
                "revision_year": 2026,
                "description": f"{SURNAMES[gi]}氏家族族谱，目标成员数 {sizes[gi]}。",
                "owner_id": 1,
            })

        per_gen_targets = [
            generation_targets(size, generations, founder_count=8)
            for size in sizes
        ]

        all_gen_members: list[list[list[dict]]] = []
        for gi in range(num_genealogies):
            gen_members_list: list[list[dict]] = []
            for gen_idx in range(generations):
                gen_members_list.append([])
            all_gen_members.append(gen_members_list)

        total_members_written = 0
        all_member_entries: list[dict] = []
        connected_member_ids: set[int] = set()
        marriage_pairs: set[tuple[int, int]] = set()

        for gi, gen_targets in enumerate(per_gen_targets):
            gid = gi + 1 + id_offset
            surname = SURNAMES[gi]
            gen1_count = gen_targets[0]

            for local_idx in range(gen1_count):
                mid = counters.member_id
                counters.member_id += 1
                gender = "male" if local_idx % 2 == 0 else "female"
                name = f"{surname}{given_name(fake, gender)}"
                birth_year = birth_year_for(1, rng)
                death_year = death_year_for(birth_year, 1, generations, rng)
                biography = (
                    f"{surname}氏第1代始祖"
                    + (f"，生于{birth_year}" if birth_year else "")
                    + (f"，卒于{death_year}" if death_year else "")
                    + "。"
                )
                members_writer.writerow({
                    "id": mid, "genealogy_id": gid, "name": name,
                    "gender": gender, "birth_year": birth_year,
                    "death_year": death_year, "biography": biography,
                    "generation_no": 1,
                })
                member_entry = {
                    "id": mid,
                    "gid": gid,
                    "gender": gender,
                    "name": name,
                    "generation_no": 1,
                }
                all_gen_members[gi][0].append({"id": mid, "gender": gender, "name": name})
                all_member_entries.append(member_entry)
                total_members_written += 1

        for gen_idx in range(generations - 1):
            gen_no = gen_idx + 1

            all_males: list[dict] = []
            all_females: list[dict] = []
            for gi in range(num_genealogies):
                for m in all_gen_members[gi][gen_idx]:
                    entry = {**m, "gid": gi + 1 + id_offset}
                    if m["gender"] == "male":
                        all_males.append(entry)
                    else:
                        all_females.append(entry)

            rng.shuffle(all_males)
            rng.shuffle(all_females)

            female_pool = list(all_females)
            marriages_this_gen: list[dict] = []

            for male in all_males:
                found = None
                for fi, female in enumerate(female_pool):
                    if female["gid"] != male["gid"]:
                        found = (fi, female)
                        break
                if found is None:
                    continue
                fi, female = found
                female_pool.pop(fi)
                marriages_this_gen.append({"male": male, "female": female})

            for mar in marriages_this_gen:
                male = mar["male"]
                female = mar["female"]
                married_year = birth_year_for(gen_no, rng) + rng.randint(22, 28)
                marriages_writer.writerow({
                    "id": counters.marriage_id,
                    "genealogy_id": male["gid"],
                    "spouse1_member_id": min(male["id"], female["id"]),
                    "spouse2_member_id": max(male["id"], female["id"]),
                    "married_year": married_year,
                    "ended_year": "",
                })
                marriage_pairs.add((min(male["id"], female["id"]), max(male["id"], female["id"])))
                connected_member_ids.update({male["id"], female["id"]})
                counters.marriage_id += 1

            marriage_index: dict[int, list[dict]] = {}
            for mar in marriages_this_gen:
                mgid = mar["male"]["gid"]
                marriage_index.setdefault(mgid, []).append(mar)

            for gi in range(num_genealogies):
                gid = gi + 1 + id_offset
                surname = SURNAMES[gi]
                couples = marriage_index.get(gid, [])
                target = per_gen_targets[gi][gen_idx + 1]

                if not couples:
                    continue

                per_couple = target // len(couples)
                extra = target % len(couples)
                gi_child_counter = 0

                for ci, couple in enumerate(couples):
                    male = couple["male"]
                    female = couple["female"]
                    n_children = per_couple + (1 if ci < extra else 0)

                    for _ in range(n_children):
                        mid = counters.member_id
                        counters.member_id += 1
                        child_gender = "male" if gi_child_counter % 2 == 0 else "female"
                        gi_child_counter += 1
                        child_name = f"{surname}{given_name(fake, child_gender)}"
                        child_gen = gen_no + 1
                        child_birth = birth_year_for(child_gen, rng)
                        child_death = death_year_for(child_birth, child_gen, generations, rng)
                        child_bio = (
                            f"{surname}氏第{child_gen}代"
                            + (f"，生于{child_birth}" if child_birth else "")
                            + (f"，卒于{child_death}" if child_death else "")
                            + "。"
                        )

                        members_writer.writerow({
                            "id": mid, "genealogy_id": gid, "name": child_name,
                            "gender": child_gender, "birth_year": child_birth,
                            "death_year": child_death, "biography": child_bio,
                            "generation_no": child_gen,
                        })

                        parent_child_writer.writerow({
                            "id": counters.parent_child_id,
                            "genealogy_id": gid,
                            "parent_member_id": male["id"],
                            "child_member_id": mid,
                            "parent_role": "father",
                        })
                        connected_member_ids.update({male["id"], mid})
                        counters.parent_child_id += 1

                        parent_child_writer.writerow({
                            "id": counters.parent_child_id,
                            "genealogy_id": gid,
                            "parent_member_id": female["id"],
                            "child_member_id": mid,
                            "parent_role": "mother",
                        })
                        connected_member_ids.update({female["id"], mid})
                        counters.parent_child_id += 1

                        child_entry = {
                            "id": mid, "gender": child_gender, "name": child_name,
                            "gid": gid, "generation_no": child_gen,
                        }
                        all_gen_members[gi][gen_idx + 1].append({
                            "id": mid, "gender": child_gender, "name": child_name,
                        })
                        all_member_entries.append(child_entry)
                        total_members_written += 1

        isolated_members = [
            member for member in all_member_entries
            if member["id"] not in connected_member_ids
        ]
        for member in isolated_members:
            if member["id"] in connected_member_ids:
                continue
            candidates = [
                candidate for candidate in all_member_entries
                if candidate["id"] != member["id"]
                and (min(member["id"], candidate["id"]), max(member["id"], candidate["id"])) not in marriage_pairs
                and candidate["gid"] != member["gid"]
            ]
            if not candidates:
                continue
            spouse = rng.choice(candidates)
            pair = (min(member["id"], spouse["id"]), max(member["id"], spouse["id"]))
            married_year = birth_year_for(
                max(member.get("generation_no", 1), spouse.get("generation_no", 1)),
                rng,
            ) + rng.randint(22, 28)
            marriages_writer.writerow({
                "id": counters.marriage_id,
                "genealogy_id": member["gid"],
                "spouse1_member_id": pair[0],
                "spouse2_member_id": pair[1],
                "married_year": married_year,
                "ended_year": "",
            })
            marriage_pairs.add(pair)
            connected_member_ids.update({member["id"], spouse["id"]})
            counters.marriage_id += 1

        return {
            "genealogies": num_genealogies,
            "members": total_members_written,
            "parent_child_relations": counters.parent_child_id - 1 - id_offset,
            "marriages": counters.marriage_id - 1 - id_offset,
            "max_genealogy_members": max(sizes),
            "max_generation_no": generations,
        }
    finally:
        for handle in handles:
            handle.close()


def parse_sizes(value: str | None) -> list[int]:
    if not value:
        return DEFAULT_SIZES
    sizes = [int(item.strip()) for item in value.split(",") if item.strip()]
    if len(sizes) < 1:
        raise ValueError("at least one genealogy size is required")
    return sizes


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate genealogy CSV data.")
    parser.add_argument("--output-dir", default="data/generated", help="CSV output directory.")
    parser.add_argument("--sizes", help="Comma-separated genealogy member counts.")
    parser.add_argument("--generations", type=int, default=30, help="Generation count per genealogy.")
    parser.add_argument("--seed", type=int, default=20260501, help="Random seed.")
    parser.add_argument("--id-offset", type=int, default=0,
                        help="Offset added to all generated IDs (for appending to existing data).")
    parser.add_argument("--skip-users", action="store_true",
                        help="Skip generating users.csv (use when appending to existing DB).")
    args = parser.parse_args()

    sizes = parse_sizes(args.sizes)
    summary = generate_dataset(
        Path(args.output_dir), sizes, args.generations, args.seed,
        id_offset=args.id_offset, skip_users=args.skip_users,
    )

    print("Generated CSV dataset:")
    for key, value in summary.items():
        print(f"- {key}: {value}")
    print(f"- output_dir: {Path(args.output_dir).resolve()}")


if __name__ == "__main__":
    main()
