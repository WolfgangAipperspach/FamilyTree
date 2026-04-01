"""Main Click CLI for the ft familytree tool."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Optional

import click

from ft.tree import (
    find_tree_root,
    init_tree,
    load_control,
    save_control,
    TreeNotFoundError,
    TreeExistsError,
    FAMILYTREE_VERSION,
)
from ft.index import (
    load_persons_index,
    load_relations_index,
    upsert_person,
    upsert_relation,
    remove_person,
    remove_relation,
    build_index,
)
from ft.person import (
    scan_persons,
    find_person,
    save_person,
    new_person,
    touch_person,
    delete_person,
)
from ft.relation import (
    scan_relations,
    find_relation,
    save_relation,
    new_relation,
    touch_relation,
    delete_relation,
    relations_for_person,
)
from ft.validate import validate_person, validate_relation, validate_control
from ft.output import (
    full_name,
    year_from,
    person_summary,
    person_detail,
    index_person_summary,
    relation_summary,
    as_json,
)
from ft.duplicates import find_duplicates, score_pair


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _require_root(ctx: click.Context) -> Path:
    root = ctx.obj.get("root")
    if root is None:
        raise click.ClickException(
            "No family tree found. Run 'ft init' to create one."
        )
    return root


def _resolve_uuid(index: list, prefix: str) -> str | None:
    """Return full UUID from a prefix match (min 4 chars)."""
    if len(prefix) < 4:
        return None
    matches = [e["uuid"] for e in index if e["uuid"].startswith(prefix)]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise click.ClickException(
            f"Ambiguous UUID prefix '{prefix}' matches {len(matches)} records."
        )
    return None


def _resolve_person_uuid(root: Path, prefix: str) -> str:
    """Resolve a person UUID from the index, with prefix matching."""
    index = load_persons_index(root)
    # Exact match first
    for e in index:
        if e["uuid"] == prefix:
            return prefix
    resolved = _resolve_uuid(index, prefix)
    if resolved:
        return resolved
    raise click.ClickException(f"Person not found: {prefix}")


def _resolve_relation_uuid(root: Path, prefix: str) -> str:
    """Resolve a relation UUID from the index, with prefix matching."""
    index = load_relations_index(root)
    for e in index:
        if e["uuid"] == prefix:
            return prefix
    resolved = _resolve_uuid(index, prefix)
    if resolved:
        return resolved
    raise click.ClickException(f"Relation not found: {prefix}")


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def _set_nested(data: dict, dot_path: str, value) -> None:
    """Set a value in a nested dict using dot notation."""
    keys = dot_path.split(".")
    obj = data
    for key in keys[:-1]:
        if key not in obj or not isinstance(obj[key], dict):
            obj[key] = {}
        obj = obj[key]
    obj[keys[-1]] = value


# ---------------------------------------------------------------------------
# Main group
# ---------------------------------------------------------------------------

@click.group()
@click.option(
    "--tree",
    "tree_path",
    default=None,
    help="Path to the family tree root (overrides auto-discovery).",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    show_default=True,
    help="Output format.",
)
@click.option(
    "--quiet",
    is_flag=True,
    default=False,
    help="Suppress non-essential output.",
)
@click.version_option("0.1.0")
@click.pass_context
def main(ctx: click.Context, tree_path: str | None, output_format: str, quiet: bool) -> None:
    """ft — familytree CLI."""
    ctx.ensure_object(dict)
    ctx.obj["output_format"] = output_format
    ctx.obj["quiet"] = quiet

    root: Path | None = None
    if tree_path:
        candidate = Path(tree_path).resolve()
        if (candidate / ".familytree.json").exists():
            root = candidate
        else:
            root = None
    else:
        try:
            root = find_tree_root(Path.cwd())
        except TreeNotFoundError:
            root = None

    ctx.obj["root"] = root


# ---------------------------------------------------------------------------
# ft init
# ---------------------------------------------------------------------------

@main.command("init")
@click.argument("path", default=".", type=click.Path())
@click.pass_context
def cmd_init(ctx: click.Context, path: str) -> None:
    """Initialise a new family tree at PATH (default: current directory)."""
    target = Path(path).resolve()
    try:
        data = init_tree(target)
    except TreeExistsError as exc:
        raise click.ClickException(str(exc))
    if not ctx.obj.get("quiet"):
        click.echo(f"Initialised family tree at: {target}")
        click.echo(f"UUID: {data['uuid']}")


# ---------------------------------------------------------------------------
# ft validate
# ---------------------------------------------------------------------------

@main.command("validate")
@click.option("--strict", is_flag=True, default=False, help="Exit 1 even on warnings.")
@click.pass_context
def cmd_validate(ctx: click.Context, strict: bool) -> None:
    """Validate all records in the tree."""
    root = _require_root(ctx)
    errors_found = False

    # Control file
    try:
        ctrl = load_control(root)
        errs = validate_control(ctrl)
        if errs:
            errors_found = True
            click.echo("Control file errors:")
            for e in errs:
                click.echo(f"  - {e}")
    except Exception as exc:
        raise click.ClickException(f"Cannot read control file: {exc}")

    # Persons
    person_errors = 0
    for data, path in scan_persons(root):
        errs = validate_person(data)
        if errs:
            errors_found = True
            person_errors += 1
            click.echo(f"Person {data.get('uuid', path)} errors:")
            for e in errs:
                click.echo(f"  - {e}")

    # Relations
    relation_errors = 0
    for data, path in scan_relations(root):
        errs = validate_relation(data)
        if errs:
            errors_found = True
            relation_errors += 1
            click.echo(f"Relation {data.get('uuid', path)} errors:")
            for e in errs:
                click.echo(f"  - {e}")

    if not errors_found:
        if not ctx.obj.get("quiet"):
            click.echo("All records valid.")
    else:
        sys.exit(1)


# ---------------------------------------------------------------------------
# ft index
# ---------------------------------------------------------------------------

@main.command("index")
@click.pass_context
def cmd_index(ctx: click.Context) -> None:
    """Rebuild the persons and relations index from scratch."""
    root = _require_root(ctx)
    n_persons, n_relations = build_index(root)
    if not ctx.obj.get("quiet"):
        click.echo(f"Indexed {n_persons} persons, {n_relations} relations.")


# ---------------------------------------------------------------------------
# ft person
# ---------------------------------------------------------------------------

@main.group("person")
def person_group() -> None:
    """Manage persons."""


@person_group.command("add")
@click.option("--folder", "folder_path", default=None, help="Custom folder path for the new person.")
@click.option("--from-json", "from_json", default=None, type=click.Path(exists=True), help="Read initial data from a JSON file.")
@click.pass_context
def person_add(ctx: click.Context, folder_path: str | None, from_json: str | None) -> None:
    """Add a new person to the tree."""
    root = _require_root(ctx)
    folder = Path(folder_path).resolve() if folder_path else None

    if from_json:
        with open(from_json, encoding="utf-8") as fh:
            initial = json.load(fh)
        import uuid as _uuid
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        initial["uuid"] = str(_uuid.uuid4())
        initial["familytree_version"] = FAMILYTREE_VERSION
        initial["created"] = now
        initial["changed"] = now
        name = initial.get("name") or {}
        if folder is None:
            from ft.person import _name_slug
            slug = _name_slug(name)
            base = root / "persons" / slug
            candidate = base
            counter = 1
            while (candidate / ".person.json").exists():
                candidate = Path(f"{base}_{counter}")
                counter += 1
            folder = candidate
        save_person(folder, initial)
        data = initial
    else:
        given = click.prompt("Given name", default="")
        surname = click.prompt("Surname", default="")
        name: dict = {}
        if given:
            name["given"] = given
        if surname:
            name["surname"] = surname
        sex_input = click.prompt("Sex (M/F/X/skip)", default="skip")
        sex = sex_input.upper() if sex_input.upper() in ("M", "F", "X") else None

        birth_date = click.prompt("Birth date (YYYY-MM-DD or leave blank)", default="")
        birth_place = click.prompt("Birth place (leave blank to skip)", default="")
        death_date = click.prompt("Death date (YYYY-MM-DD or leave blank)", default="")

        kwargs: dict = {}
        if sex:
            kwargs["sex"] = sex
        birth: dict = {}
        if birth_date:
            birth["date"] = birth_date
        if birth_place:
            birth["place"] = birth_place
        if birth:
            kwargs["birth"] = birth
        if death_date:
            kwargs["death"] = {"date": death_date}

        data, _path = new_person(root, name, folder=folder, **kwargs)

    errs = validate_person(data)
    if errs:
        click.echo("Warning: person data has validation errors:")
        for e in errs:
            click.echo(f"  - {e}", err=True)

    upsert_person(root, data)
    click.echo(data["uuid"])


@person_group.command("list")
@click.option("--filter", "filter_expr", default=None, help="Filter expression e.g. surname=Smith or birth.year=1932")
@click.pass_context
def person_list(ctx: click.Context, filter_expr: str | None) -> None:
    """List all persons in the tree."""
    root = _require_root(ctx)
    index = load_persons_index(root)

    if not index:
        # Fall back to scanning
        index = []
        from ft.index import _person_entry
        for data, _ in scan_persons(root):
            index.append(_person_entry(data))

    # Apply filter
    if filter_expr:
        field, _, value = filter_expr.partition("=")
        field = field.strip()
        value = value.strip()
        filtered = []
        for entry in index:
            if field == "surname":
                match = (entry.get("name") or {}).get("surname", "").lower() == value.lower()
            elif field == "sex":
                match = entry.get("sex", "").upper() == value.upper()
            elif field == "birth.year":
                match = year_from(entry.get("birth")) == value
            elif field == "given":
                match = (entry.get("name") or {}).get("given", "").lower() == value.lower()
            else:
                match = False
            if match:
                filtered.append(entry)
        index = filtered

    output_format = ctx.obj.get("output_format", "text")
    if output_format == "json":
        click.echo(as_json(index))
    else:
        for entry in index:
            click.echo(index_person_summary(entry))


@person_group.command("show")
@click.argument("uuid_prefix")
@click.option("--raw", is_flag=True, default=False, help="Print raw JSON.")
@click.pass_context
def person_show(ctx: click.Context, uuid_prefix: str, raw: bool) -> None:
    """Show details for a person."""
    root = _require_root(ctx)
    person_uuid = _resolve_person_uuid(root, uuid_prefix)
    result = find_person(root, person_uuid)
    if result is None:
        raise click.ClickException(f"Person not found: {person_uuid}")
    data, _path = result

    output_format = ctx.obj.get("output_format", "text")
    if raw or output_format == "json":
        click.echo(as_json(data))
    else:
        click.echo(person_detail(data))


@person_group.command("edit")
@click.argument("uuid_prefix")
@click.pass_context
def person_edit(ctx: click.Context, uuid_prefix: str) -> None:
    """Open a person record in $EDITOR."""
    root = _require_root(ctx)
    person_uuid = _resolve_person_uuid(root, uuid_prefix)
    result = find_person(root, person_uuid)
    if result is None:
        raise click.ClickException(f"Person not found: {person_uuid}")
    data, person_file = result

    original_json = as_json(data)
    edited = click.edit(original_json, extension=".json")
    if edited is None or edited == original_json:
        click.echo("No changes made.")
        return

    try:
        new_data = json.loads(edited)
    except json.JSONDecodeError as exc:
        raise click.ClickException(f"Invalid JSON: {exc}")

    new_data = touch_person(new_data)
    errs = validate_person(new_data)
    if errs:
        click.echo("Warning: person data has validation errors:", err=True)
        for e in errs:
            click.echo(f"  - {e}", err=True)

    save_person(person_file.parent, new_data)
    upsert_person(root, new_data)
    click.echo(f"Saved {person_uuid}")


@person_group.command("set")
@click.argument("uuid_prefix")
@click.argument("field")
@click.argument("value")
@click.pass_context
def person_set(ctx: click.Context, uuid_prefix: str, field: str, value: str) -> None:
    """Set a field on a person using dot-notation (e.g. birth.date)."""
    root = _require_root(ctx)
    person_uuid = _resolve_person_uuid(root, uuid_prefix)
    result = find_person(root, person_uuid)
    if result is None:
        raise click.ClickException(f"Person not found: {person_uuid}")
    data, person_file = result

    # Coerce value
    try:
        coerced = json.loads(value)
    except json.JSONDecodeError:
        coerced = value

    _set_nested(data, field, coerced)
    data = touch_person(data)

    errs = validate_person(data)
    if errs:
        click.echo("Warning: person data has validation errors:", err=True)
        for e in errs:
            click.echo(f"  - {e}", err=True)

    save_person(person_file.parent, data)
    upsert_person(root, data)
    click.echo(f"Set {field} on {person_uuid}")


@person_group.command("remove")
@click.argument("uuid_prefix")
@click.option("--force", is_flag=True, default=False, help="Delete related relations too.")
@click.pass_context
def person_remove(ctx: click.Context, uuid_prefix: str, force: bool) -> None:
    """Remove a person from the tree."""
    root = _require_root(ctx)
    person_uuid = _resolve_person_uuid(root, uuid_prefix)

    rels = relations_for_person(root, person_uuid)
    if rels and not force:
        raise click.ClickException(
            f"Person {person_uuid} has {len(rels)} relation(s). Use --force to also delete them."
        )

    if force:
        for rel_data, _rel_path in rels:
            delete_relation(root, rel_data["uuid"])
            remove_relation(root, rel_data["uuid"])

    folder = delete_person(root, person_uuid)
    if folder is None:
        raise click.ClickException(f"Person not found: {person_uuid}")
    remove_person(root, person_uuid)
    if not ctx.obj.get("quiet"):
        click.echo(f"Removed person {person_uuid}")


# ---------------------------------------------------------------------------
# ft relation
# ---------------------------------------------------------------------------

@main.group("relation")
def relation_group() -> None:
    """Manage relations."""


@relation_group.command("add")
@click.option("--type", "rel_type", required=True, type=click.Choice(["partner", "filiation", "association"]), help="Relation type.")
@click.option("--folder", "folder_path", default=None, help="Custom folder for the new relation.")
@click.option("--from-json", "from_json", default=None, type=click.Path(exists=True), help="Read initial data from a JSON file.")
@click.pass_context
def relation_add(ctx: click.Context, rel_type: str, folder_path: str | None, from_json: str | None) -> None:
    """Add a new relation to the tree."""
    root = _require_root(ctx)
    folder = Path(folder_path).resolve() if folder_path else None

    if from_json:
        with open(from_json, encoding="utf-8") as fh:
            initial = json.load(fh)
        import uuid as _uuid
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        initial["uuid"] = str(_uuid.uuid4())
        initial["familytree_version"] = FAMILYTREE_VERSION
        initial["type"] = rel_type
        initial["created"] = now
        initial["changed"] = now
        if folder is None:
            import re
            slug = re.sub(r"[^a-zA-Z0-9_\-]", "_", rel_type).lower()
            base = root / "relations" / slug
            candidate = base
            counter = 1
            while (candidate / ".relation.json").exists():
                candidate = Path(f"{base}_{counter}")
                counter += 1
            folder = candidate
        save_relation(folder, initial)
        data = initial
    elif rel_type == "filiation":
        parent_prefix = click.prompt("Parent UUID (or prefix)")
        child_prefix = click.prompt("Child UUID (or prefix)")
        pedigree = click.prompt("Pedigree (birth/adopted/foster/... or skip)", default="skip")
        parent_uuid = _resolve_person_uuid(root, parent_prefix)
        child_uuid = _resolve_person_uuid(root, child_prefix)
        kwargs: dict = {"parent": parent_uuid, "child": child_uuid}
        if pedigree != "skip":
            kwargs["pedigree"] = pedigree
        data, _path = new_relation(root, "filiation", folder=folder, **kwargs)
    elif rel_type == "partner":
        p1_prefix = click.prompt("First person UUID (or prefix)")
        p2_prefix = click.prompt("Second person UUID (or prefix)")
        kind = click.prompt("Kind (marriage/civil_union/cohabitation/engagement/custom/skip)", default="skip")
        p1_uuid = _resolve_person_uuid(root, p1_prefix)
        p2_uuid = _resolve_person_uuid(root, p2_prefix)
        kwargs = {"persons": [p1_uuid, p2_uuid]}
        if kind != "skip":
            kwargs["kind"] = kind
        data, _path = new_relation(root, "partner", folder=folder, **kwargs)
    elif rel_type == "association":
        from_prefix = click.prompt("From person UUID (or prefix)")
        to_prefix = click.prompt("To person UUID (or prefix)")
        relation_label = click.prompt("Relation label (e.g. godfather, witness)")
        from_uuid = _resolve_person_uuid(root, from_prefix)
        to_uuid = _resolve_person_uuid(root, to_prefix)
        data, _path = new_relation(
            root, "association", folder=folder,
            **{"from": from_uuid, "to": to_uuid, "relation": relation_label}
        )
    else:
        raise click.ClickException(f"Unknown relation type: {rel_type}")

    errs = validate_relation(data)
    if errs:
        click.echo("Warning: relation data has validation errors:", err=True)
        for e in errs:
            click.echo(f"  - {e}", err=True)

    upsert_relation(root, data)
    click.echo(data["uuid"])


@relation_group.command("list")
@click.option("--type", "rel_type", default=None, help="Filter by relation type.")
@click.option("--person", "person_prefix", default=None, help="Filter by person UUID or prefix.")
@click.pass_context
def relation_list(ctx: click.Context, rel_type: str | None, person_prefix: str | None) -> None:
    """List relations in the tree."""
    root = _require_root(ctx)
    index = load_relations_index(root)

    if not index:
        from ft.index import _relation_entry
        for data, _ in scan_relations(root):
            index.append(_relation_entry(data))

    if rel_type:
        index = [e for e in index if e.get("type") == rel_type]

    if person_prefix:
        person_uuid = _resolve_person_uuid(root, person_prefix)
        filtered = []
        for e in index:
            t = e.get("type")
            if t == "filiation":
                if e.get("parent") == person_uuid or e.get("child") == person_uuid:
                    filtered.append(e)
            elif t == "partner":
                if person_uuid in (e.get("persons") or []):
                    filtered.append(e)
            elif t == "association":
                if e.get("from") == person_uuid or e.get("to") == person_uuid:
                    filtered.append(e)
        index = filtered

    output_format = ctx.obj.get("output_format", "text")
    if output_format == "json":
        click.echo(as_json(index))
    else:
        for entry in index:
            click.echo(relation_summary(entry))


@relation_group.command("show")
@click.argument("uuid_prefix")
@click.option("--raw", is_flag=True, default=False)
@click.pass_context
def relation_show(ctx: click.Context, uuid_prefix: str, raw: bool) -> None:
    """Show details for a relation."""
    root = _require_root(ctx)
    rel_uuid = _resolve_relation_uuid(root, uuid_prefix)
    result = find_relation(root, rel_uuid)
    if result is None:
        raise click.ClickException(f"Relation not found: {rel_uuid}")
    data, _path = result

    output_format = ctx.obj.get("output_format", "text")
    if raw or output_format == "json":
        click.echo(as_json(data))
    else:
        click.echo(relation_summary(data))


@relation_group.command("edit")
@click.argument("uuid_prefix")
@click.pass_context
def relation_edit(ctx: click.Context, uuid_prefix: str) -> None:
    """Open a relation record in $EDITOR."""
    root = _require_root(ctx)
    rel_uuid = _resolve_relation_uuid(root, uuid_prefix)
    result = find_relation(root, rel_uuid)
    if result is None:
        raise click.ClickException(f"Relation not found: {rel_uuid}")
    data, rel_file = result

    original_json = as_json(data)
    edited = click.edit(original_json, extension=".json")
    if edited is None or edited == original_json:
        click.echo("No changes made.")
        return

    try:
        new_data = json.loads(edited)
    except json.JSONDecodeError as exc:
        raise click.ClickException(f"Invalid JSON: {exc}")

    new_data = touch_relation(new_data)
    errs = validate_relation(new_data)
    if errs:
        click.echo("Warning: relation data has validation errors:", err=True)
        for e in errs:
            click.echo(f"  - {e}", err=True)

    save_relation(rel_file.parent, new_data)
    upsert_relation(root, new_data)
    click.echo(f"Saved {rel_uuid}")


@relation_group.command("remove")
@click.argument("uuid_prefix")
@click.pass_context
def relation_remove(ctx: click.Context, uuid_prefix: str) -> None:
    """Remove a relation from the tree."""
    root = _require_root(ctx)
    rel_uuid = _resolve_relation_uuid(root, uuid_prefix)

    folder = delete_relation(root, rel_uuid)
    if folder is None:
        raise click.ClickException(f"Relation not found: {rel_uuid}")
    remove_relation(root, rel_uuid)
    if not ctx.obj.get("quiet"):
        click.echo(f"Removed relation {rel_uuid}")


# ---------------------------------------------------------------------------
# ft find-duplicates
# ---------------------------------------------------------------------------

@main.command("find-duplicates")
@click.option("--threshold", default=80, show_default=True, help="Minimum similarity score (0-100).")
@click.pass_context
def cmd_find_duplicates(ctx: click.Context, threshold: int) -> None:
    """Find potential duplicate persons."""
    root = _require_root(ctx)
    persons = load_persons_index(root)
    ctrl = load_control(root)
    not_dup_pairs = ctrl.get("not_duplicates") or []

    duplicates = find_duplicates(persons, not_dup_pairs, threshold=threshold)

    output_format = ctx.obj.get("output_format", "text")
    if output_format == "json":
        click.echo(as_json(duplicates))
        return

    if not duplicates:
        click.echo("No duplicates found.")
        return

    for pair in duplicates:
        a = pair["person_a"]
        b = pair["person_b"]
        score = pair["score"]
        a_name = full_name(a.get("name"))
        b_name = full_name(b.get("name"))
        click.echo(f"Score {score:3d}  {a['uuid'][:8]} {a_name}  vs  {b['uuid'][:8]} {b_name}")


# ---------------------------------------------------------------------------
# ft not-duplicate
# ---------------------------------------------------------------------------

@main.command("not-duplicate")
@click.argument("uuid1")
@click.argument("uuid2")
@click.option("--note", default=None, help="Reason why these persons are distinct.")
@click.pass_context
def cmd_not_duplicate(ctx: click.Context, uuid1: str, uuid2: str, note: str | None) -> None:
    """Mark two persons as confirmed not-duplicates."""
    root = _require_root(ctx)
    p1_uuid = _resolve_person_uuid(root, uuid1)
    p2_uuid = _resolve_person_uuid(root, uuid2)

    ctrl = load_control(root)
    not_dups = ctrl.get("not_duplicates") or []

    # Check for existing entry
    key = frozenset([p1_uuid, p2_uuid])
    for entry in not_dups:
        if frozenset(entry.get("persons", [])) == key:
            click.echo("Pair already marked as not-duplicate.")
            return

    new_entry: dict = {"persons": [p1_uuid, p2_uuid]}
    if note:
        new_entry["note"] = note
    not_dups.append(new_entry)
    ctrl["not_duplicates"] = not_dups
    save_control(root, ctrl)
    click.echo(f"Marked {p1_uuid[:8]} and {p2_uuid[:8]} as not-duplicates.")


# ---------------------------------------------------------------------------
# ft tree
# ---------------------------------------------------------------------------

@main.command("tree")
@click.argument("uuid_prefix")
@click.option("--ancestors", "direction", flag_value="ancestors", default=True, help="Show ancestors (default).")
@click.option("--descendants", "direction", flag_value="descendants", help="Show descendants.")
@click.option("--depth", default=5, show_default=True, help="Maximum depth.")
@click.pass_context
def cmd_tree(ctx: click.Context, uuid_prefix: str, direction: str, depth: int) -> None:
    """Display an ASCII tree of ancestors or descendants."""
    root = _require_root(ctx)
    person_uuid = _resolve_person_uuid(root, uuid_prefix)

    # Build a quick lookup
    all_persons: dict[str, dict] = {}
    for data, _ in scan_persons(root):
        all_persons[data["uuid"]] = data

    all_relations: list[dict] = []
    for data, _ in scan_relations(root):
        all_relations.append(data)

    def get_parents(puuid: str) -> list[str]:
        parents = []
        for rel in all_relations:
            if rel.get("type") == "filiation" and rel.get("child") == puuid:
                parents.append(rel["parent"])
        return parents

    def get_children(puuid: str) -> list[str]:
        children = []
        for rel in all_relations:
            if rel.get("type") == "filiation" and rel.get("parent") == puuid:
                children.append(rel["child"])
        return children

    def get_partners(puuid: str) -> list[str]:
        partners = []
        for rel in all_relations:
            if rel.get("type") == "partner":
                persons_list = rel.get("persons") or []
                if puuid in persons_list:
                    for p in persons_list:
                        if p != puuid:
                            partners.append(p)
        return partners

    def _person_label(puuid: str) -> str:
        p = all_persons.get(puuid)
        if not p:
            return f"[{puuid[:8]}] (unknown)"
        return index_person_summary({"uuid": puuid, "name": p.get("name"), "sex": p.get("sex"), "birth": p.get("birth"), "death": p.get("death")})

    visited: set[str] = set()

    def print_ancestors(puuid: str, indent: int = 0, current_depth: int = 0) -> None:
        if current_depth > depth or puuid in visited:
            return
        visited.add(puuid)
        prefix = "  " * indent
        label = _person_label(puuid)
        partners = get_partners(puuid)
        partner_str = ""
        if partners:
            partner_labels = [_person_label(p) for p in partners[:2]]
            partner_str = "  + " + " | ".join(partner_labels)
        click.echo(f"{prefix}{label}{partner_str}")
        for parent_uuid in get_parents(puuid):
            print_ancestors(parent_uuid, indent + 1, current_depth + 1)

    def print_descendants(puuid: str, indent: int = 0, current_depth: int = 0) -> None:
        if current_depth > depth or puuid in visited:
            return
        visited.add(puuid)
        prefix = "  " * indent
        label = _person_label(puuid)
        click.echo(f"{prefix}{label}")
        for child_uuid in get_children(puuid):
            print_descendants(child_uuid, indent + 1, current_depth + 1)

    if direction == "ancestors":
        print_ancestors(person_uuid)
    else:
        print_descendants(person_uuid)


# ---------------------------------------------------------------------------
# ft import
# ---------------------------------------------------------------------------

@main.command("import")
@click.argument("gedcom_file", type=click.Path(exists=True))
@click.option("--folder", "folder_path", default=None, help="Base folder override.")
@click.option("--dry-run", is_flag=True, default=False, help="Parse only, do not write.")
@click.pass_context
def cmd_import(ctx: click.Context, gedcom_file: str, folder_path: str | None, dry_run: bool) -> None:
    """Import persons and relations from a GEDCOM file."""
    root = _require_root(ctx)
    from ft.gedcom.importer import import_gedcom_file

    gedcom_path = Path(gedcom_file)
    try:
        persons, relations = import_gedcom_file(gedcom_path)
    except Exception as exc:
        raise click.ClickException(f"Failed to parse GEDCOM: {exc}")

    existing_persons = load_persons_index(root)
    threshold = 85

    written_persons = 0
    written_relations = 0
    skipped_persons = 0

    for person in persons:
        # Check for near-duplicates
        similar = []
        from ft.index import _person_entry
        new_entry = _person_entry(person)
        for ep in existing_persons:
            s = score_pair(new_entry, ep)
            if s >= threshold:
                similar.append((ep, s))

        if similar:
            similar.sort(key=lambda x: x[1], reverse=True)
            best_match, best_score = similar[0]
            best_name = full_name(best_match.get("name"))
            new_name_str = full_name(person.get("name"))
            click.echo(f"\nPossible duplicate (score {best_score}):")
            click.echo(f"  Importing: {new_name_str}  [{person['uuid'][:8]}]")
            click.echo(f"  Existing:  {best_name}  [{best_match['uuid'][:8]}]")
            choice = click.prompt("Action: [s]kip, [m]erge (keep existing), [c]reate new", default="s")
            choice = choice.strip().lower()
            if choice == "s":
                skipped_persons += 1
                continue
            elif choice == "m":
                skipped_persons += 1
                # Replace UUID in relations
                for rel in relations:
                    rel_type = rel.get("type")
                    if rel_type == "filiation":
                        if rel.get("parent") == person["uuid"]:
                            rel["parent"] = best_match["uuid"]
                        if rel.get("child") == person["uuid"]:
                            rel["child"] = best_match["uuid"]
                    elif rel_type == "partner":
                        rel["persons"] = [
                            best_match["uuid"] if p == person["uuid"] else p
                            for p in rel.get("persons", [])
                        ]
                    elif rel_type == "association":
                        if rel.get("from") == person["uuid"]:
                            rel["from"] = best_match["uuid"]
                        if rel.get("to") == person["uuid"]:
                            rel["to"] = best_match["uuid"]
                continue
            # else: create new (fall through)

        if not dry_run:
            # Write the person
            from ft.person import _name_slug, save_person as _save_person
            name = person.get("name") or {}
            slug = _name_slug(name)
            base = root / "persons" / slug
            candidate = base
            counter = 1
            while (candidate / ".person.json").exists():
                candidate = Path(f"{base}_{counter}")
                counter += 1
            _save_person(candidate, person)
            upsert_person(root, person)
            existing_persons.append(_person_entry(person))
        written_persons += 1

    for rel in relations:
        if not dry_run:
            from ft.relation import save_relation as _save_relation
            import re
            rel_type = rel.get("type", "unknown")
            slug = re.sub(r"[^a-zA-Z0-9_\-]", "_", rel_type).lower()
            base = root / "relations" / slug
            candidate = base
            counter = 1
            while (candidate / ".relation.json").exists():
                candidate = Path(f"{base}_{counter}")
                counter += 1
            _save_relation(candidate, rel)
            upsert_relation(root, rel)
        written_relations += 1

    if dry_run:
        click.echo(f"Dry run: would import {written_persons} persons, {written_relations} relations, skip {skipped_persons}.")
    else:
        click.echo(f"Imported {written_persons} persons, {written_relations} relations, skipped {skipped_persons}.")


# ---------------------------------------------------------------------------
# ft export
# ---------------------------------------------------------------------------

@main.command("export")
@click.option("--output", "output_file", default=None, help="Output file (default: stdout).")
@click.option("--persons", "persons_filter", default=None, help="Comma-separated list of person UUIDs to export.")
@click.option("--gedcom-version", "gedcom_version", default="5.5.1", type=click.Choice(["5.5.1", "7.0"]), show_default=True)
@click.pass_context
def cmd_export(ctx: click.Context, output_file: str | None, persons_filter: str | None, gedcom_version: str) -> None:
    """Export the tree (or a subset) as a GEDCOM file."""
    root = _require_root(ctx)
    from ft.gedcom.exporter import export_gedcom

    # Load all persons and relations
    all_persons = [data for data, _ in scan_persons(root)]
    all_relations = [data for data, _ in scan_relations(root)]

    if persons_filter:
        filter_uuids = {u.strip() for u in persons_filter.split(",")}
        # Expand via prefix matching
        index = load_persons_index(root)
        expanded: set[str] = set()
        for prefix in filter_uuids:
            try:
                resolved = _resolve_person_uuid(root, prefix)
                expanded.add(resolved)
            except click.ClickException:
                pass
        filter_uuids = expanded

        # Filter persons
        all_persons = [p for p in all_persons if p["uuid"] in filter_uuids]

        # Filter relations: keep only those where all referenced persons are in the set
        filtered_rels = []
        for rel in all_relations:
            rel_type = rel.get("type")
            if rel_type == "filiation":
                if rel.get("parent") in filter_uuids and rel.get("child") in filter_uuids:
                    filtered_rels.append(rel)
            elif rel_type == "partner":
                if all(p in filter_uuids for p in (rel.get("persons") or [])):
                    filtered_rels.append(rel)
            elif rel_type == "association":
                if rel.get("from") in filter_uuids and rel.get("to") in filter_uuids:
                    filtered_rels.append(rel)
        all_relations = filtered_rels

    gedcom_text = export_gedcom(all_persons, all_relations)

    if output_file:
        Path(output_file).write_text(gedcom_text, encoding="utf-8")
        if not ctx.obj.get("quiet"):
            click.echo(f"Exported to {output_file}")
    else:
        click.echo(gedcom_text, nl=False)
