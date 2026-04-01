"""Index management for persons and relations caches."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterator

_CACHE_DIR = ".familytree"
_PERSONS_INDEX = "persons-index.json"
_RELATIONS_INDEX = "relations-index.json"


# ---------------------------------------------------------------------------
# Low-level load / save
# ---------------------------------------------------------------------------

def _load_index(path: Path) -> list:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def _save_index(path: Path, data: list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def load_persons_index(root: Path) -> list:
    return _load_index(root / _CACHE_DIR / _PERSONS_INDEX)


def load_relations_index(root: Path) -> list:
    return _load_index(root / _CACHE_DIR / _RELATIONS_INDEX)


# ---------------------------------------------------------------------------
# Upsert / remove
# ---------------------------------------------------------------------------

def _person_entry(data: dict) -> dict:
    """Extract the index entry fields from a full person record."""
    name = data.get("name") or {}
    entry: dict = {"uuid": data["uuid"]}
    name_entry: dict = {}
    if name.get("given"):
        name_entry["given"] = name["given"]
    if name.get("surname"):
        name_entry["surname"] = name["surname"]
    if name.get("alias"):
        name_entry["alias"] = name["alias"]
    if name_entry:
        entry["name"] = name_entry
    if data.get("sex"):
        entry["sex"] = data["sex"]
    birth = data.get("birth")
    if birth:
        b: dict = {}
        if birth.get("date"):
            b["date"] = birth["date"]
        if birth.get("place"):
            b["place"] = birth["place"]
        if b:
            entry["birth"] = b
    death = data.get("death")
    if death:
        d: dict = {}
        if death.get("date"):
            d["date"] = death["date"]
        if death.get("place"):
            d["place"] = death["place"]
        if d:
            entry["death"] = d
    return entry


def _relation_entry(data: dict) -> dict:
    """Extract the index entry fields from a full relation record."""
    rel_type = data["type"]
    entry: dict = {"uuid": data["uuid"], "type": rel_type}
    if rel_type == "filiation":
        entry["parent"] = data["parent"]
        entry["child"] = data["child"]
    elif rel_type == "partner":
        entry["persons"] = data["persons"]
    elif rel_type == "association":
        entry["from"] = data["from"]
        entry["to"] = data["to"]
        entry["relation"] = data["relation"]
    return entry


def upsert_person(root: Path, data: dict) -> None:
    """Update or append a person entry in the persons index."""
    index = load_persons_index(root)
    entry = _person_entry(data)
    for i, existing in enumerate(index):
        if existing["uuid"] == data["uuid"]:
            index[i] = entry
            break
    else:
        index.append(entry)
    _save_index(root / _CACHE_DIR / _PERSONS_INDEX, index)


def upsert_relation(root: Path, data: dict) -> None:
    """Update or append a relation entry in the relations index."""
    index = load_relations_index(root)
    entry = _relation_entry(data)
    for i, existing in enumerate(index):
        if existing["uuid"] == data["uuid"]:
            index[i] = entry
            break
    else:
        index.append(entry)
    _save_index(root / _CACHE_DIR / _RELATIONS_INDEX, index)


def remove_person(root: Path, person_uuid: str) -> None:
    """Remove a person entry from the persons index."""
    index = load_persons_index(root)
    index = [e for e in index if e["uuid"] != person_uuid]
    _save_index(root / _CACHE_DIR / _PERSONS_INDEX, index)


def remove_relation(root: Path, relation_uuid: str) -> None:
    """Remove a relation entry from the relations index."""
    index = load_relations_index(root)
    index = [e for e in index if e["uuid"] != relation_uuid]
    _save_index(root / _CACHE_DIR / _RELATIONS_INDEX, index)


# ---------------------------------------------------------------------------
# Full rebuild
# ---------------------------------------------------------------------------

def build_index(root: Path) -> tuple[int, int]:
    """Rebuild both index files from scratch by scanning the filesystem.

    Returns (person_count, relation_count).
    """
    from ft.person import scan_persons
    from ft.relation import scan_relations

    persons_index: list = []
    for data, _path in scan_persons(root):
        persons_index.append(_person_entry(data))

    relations_index: list = []
    for data, _path in scan_relations(root):
        relations_index.append(_relation_entry(data))

    _save_index(root / _CACHE_DIR / _PERSONS_INDEX, persons_index)
    _save_index(root / _CACHE_DIR / _RELATIONS_INDEX, relations_index)
    return len(persons_index), len(relations_index)
