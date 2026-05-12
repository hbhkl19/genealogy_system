"""Generate large genealogy CSV fixtures for PostgreSQL COPY import.

Default output satisfies the course data requirement:
- at least 10 genealogies
- at least 100000 members
- one genealogy with at least 50000 members
- at least 30 generations
- every member has at least one marriage or blood relation edge
"""

from __future__ import annotations

import argparse
import csv
import random
from dataclasses import dataclass
from pathlib import Path

from faker import Faker


DEFAULT_SIZES = [50000] + [6000] * 9
UNMARRIED_RATE = 0.08
BIRTH_SPREAD = 5
LIFESPAN_MIN = 55
LIFESPAN_MAX = 92
RECENT_GENERATIONS_ALIVE = 5

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


def even_generation_counts(total: int, generations: int) -> list[int]:
    if total < generations * 2:
        raise ValueError("total must allow at least two members per generation")

    base = total // generations
    if base % 2:
        base -= 1
    counts = [base] * generations
    remaining = total - sum(counts)
    index = 0
    while remaining > 0:
        counts[index % generations] += 2
        remaining -= 2
        index += 1
    return counts


def open_writer(output_dir: Path, name: str, fieldnames: list[str]):
    output_dir.mkdir(parents=True, exist_ok=True)
    handle = (output_dir / CSV_FILES[name]).open("w", newline="", encoding="utf-8")
    writer = csv.DictWriter(handle, fieldnames=fieldnames)
    writer.writeheader()
    return handle, writer


def member_name(fake: Faker, genealogy_index: int, generation_no: int, local_index: int) -> str:
    return f"G{genealogy_index:02d}-G{generation_no:02d}-{local_index:04d} {fake.name()}"


def birth_year_for(generation_no: int, rng: random.Random) -> int:
    base = 1930 + (generation_no - 1) * 25
    return base + rng.randint(-BIRTH_SPREAD, BIRTH_SPREAD)


def death_year_for(birth_year: int, generation_no: int, total_generations: int, rng: random.Random) -> int | str:
    if generation_no > total_generations - RECENT_GENERATIONS_ALIVE:
        if rng.random() < 0.5:
            return ""
    lifespan = rng.randint(LIFESPAN_MIN, LIFESPAN_MAX)
    return birth_year + lifespan


def write_members_for_genealogy(
    *,
    fake: Faker,
    rng: random.Random,
    genealogy_id: int,
    genealogy_index: int,
    target_size: int,
    generations: int,
    counters: Counters,
    members_writer: csv.DictWriter,
    parent_child_writer: csv.DictWriter,
    marriages_writer: csv.DictWriter,
) -> None:
    generation_counts = even_generation_counts(target_size, generations)
    previous_couples: list[tuple[int, int]] = []

    for generation_no, generation_size in enumerate(generation_counts, start=1):
        current_members: list[int] = []

        for local_index in range(generation_size):
            member_id = counters.member_id
            counters.member_id += 1
            gender = "male" if local_index % 2 == 0 else "female"
            birth_year = birth_year_for(generation_no, rng)
            death_year = death_year_for(birth_year, generation_no, generations, rng)
            biography = (
                f"第 {generation_no} 代成员"
                + (f"，生于 {birth_year}" if birth_year else "")
                + (f"，卒于 {death_year}" if death_year else "")
                + "。"
            )
            members_writer.writerow(
                {
                    "id": member_id,
                    "genealogy_id": genealogy_id,
                    "name": member_name(fake, genealogy_index, generation_no, local_index + 1),
                    "gender": gender,
                    "birth_year": birth_year,
                    "death_year": death_year,
                    "biography": biography,
                    "generation_no": generation_no,
                }
            )
            current_members.append(member_id)

            if previous_couples:
                father_id, mother_id = previous_couples[local_index % len(previous_couples)]
                parent_child_writer.writerow(
                    {
                        "id": counters.parent_child_id,
                        "genealogy_id": genealogy_id,
                        "parent_member_id": father_id,
                        "child_member_id": member_id,
                        "parent_role": "father",
                    }
                )
                counters.parent_child_id += 1
                parent_child_writer.writerow(
                    {
                        "id": counters.parent_child_id,
                        "genealogy_id": genealogy_id,
                        "parent_member_id": mother_id,
                        "child_member_id": member_id,
                        "parent_role": "mother",
                    }
                )
                counters.parent_child_id += 1

        current_couples: list[tuple[int, int]] = []
        for index in range(0, len(current_members), 2):
            spouse1_id = current_members[index]
            spouse2_id = current_members[index + 1]

            if generation_no == 1 or rng.random() >= UNMARRIED_RATE:
                current_couples.append((spouse1_id, spouse2_id))
                married_year = birth_year_for(generation_no, rng) + rng.randint(22, 28)
                marriages_writer.writerow(
                {
                    "id": counters.marriage_id,
                    "genealogy_id": genealogy_id,
                    "spouse1_member_id": min(spouse1_id, spouse2_id),
                    "spouse2_member_id": max(spouse1_id, spouse2_id),
                    "married_year": married_year,
                    "ended_year": "",
                }
            )
            counters.marriage_id += 1

        previous_couples = current_couples


def generate_dataset(output_dir: Path, sizes: list[int], generations: int, seed: int) -> dict[str, int]:
    fake = Faker("zh_CN")
    Faker.seed(seed)
    rng = random.Random(seed)
    counters = Counters()

    handles = []
    try:
        users_handle, users_writer = open_writer(output_dir, "users", ["id", "username", "email", "password_hash"])
        genealogies_handle, genealogies_writer = open_writer(
            output_dir,
            "genealogies",
            ["id", "name", "description", "owner_id"],
        )
        members_handle, members_writer = open_writer(
            output_dir,
            "members",
            ["id", "genealogy_id", "name", "gender", "birth_year", "death_year", "biography", "generation_no"],
        )
        parent_child_handle, parent_child_writer = open_writer(
            output_dir,
            "parent_child_relations",
            ["id", "genealogy_id", "parent_member_id", "child_member_id", "parent_role"],
        )
        marriages_handle, marriages_writer = open_writer(
            output_dir,
            "marriages",
            ["id", "genealogy_id", "spouse1_member_id", "spouse2_member_id", "married_year", "ended_year"],
        )
        collaborators_handle, collaborators_writer = open_writer(
            output_dir,
            "genealogy_collaborators",
            ["id", "genealogy_id", "user_id", "role"],
        )
        handles.extend(
            [
                users_handle,
                genealogies_handle,
                members_handle,
                parent_child_handle,
                marriages_handle,
                collaborators_handle,
            ]
        )

        users_writer.writerow(
            {
                "id": 1,
                "username": "demo",
                "email": "demo@example.com",
                "password_hash": "pbkdf2:sha256:1000000$demo$replace-after-import",
            }
        )

        for genealogy_index, target_size in enumerate(sizes, start=1):
            genealogies_writer.writerow(
                {
                    "id": genealogy_index,
                    "name": f"实验族谱 {genealogy_index}",
                    "description": f"自动生成族谱，目标成员数 {target_size}。",
                    "owner_id": 1,
                }
            )
            write_members_for_genealogy(
                fake=fake,
                rng=rng,
                genealogy_id=genealogy_index,
                genealogy_index=genealogy_index,
                target_size=target_size,
                generations=generations,
                counters=counters,
                members_writer=members_writer,
                parent_child_writer=parent_child_writer,
                marriages_writer=marriages_writer,
            )

        return {
            "genealogies": len(sizes),
            "members": counters.member_id - 1,
            "parent_child_relations": counters.parent_child_id - 1,
            "marriages": counters.marriage_id - 1,
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
    args = parser.parse_args()

    sizes = parse_sizes(args.sizes)
    summary = generate_dataset(Path(args.output_dir), sizes, args.generations, args.seed)

    print("Generated CSV dataset:")
    for key, value in summary.items():
        print(f"- {key}: {value}")
    print(f"- output_dir: {Path(args.output_dir).resolve()}")


if __name__ == "__main__":
    main()