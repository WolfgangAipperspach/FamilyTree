# FamilyTree CLI Specification

**Version:** 0.1 (Draft)
**Status:** Proposal

## Overview

`ft` is a Python-based command-line tool for creating, editing, querying, and maintaining FamilyTree datasets as defined by the [FamilyTree Specification](../familytree-specs/familytree-specification.md).

It operates on a local directory tree and produces output suitable for human reading and scripting. All mutations write valid JSON conforming to the schemas in `familytree-specs/`.

## Invocation

```
ft [--tree <path>] <command> [subcommand] [options]
```

The `--tree` flag sets the root of the FamilyTree dataset (the directory containing `.familytree.json`). If omitted, `ft` walks up from the current working directory until it finds `.familytree.json`, similar to how Git finds `.git/`.

## Global Options

| Option | Description |
|--------|-------------|
| `--tree <path>` | Explicit path to the tree root |
| `--format <fmt>` | Output format: `text` (default) or `json` |
| `--quiet` | Suppress informational output; only errors to stderr |
| `--version` | Print `ft` version and exit |

## Commands

### `ft init`

Initialise a new FamilyTree dataset in the current directory (or `<path>` if given).

```
ft init [<path>]
```

Creates:
- `.familytree.json` (with a fresh UUID v4)
- `persons/` directory
- `relations/` directory
- `.familytree/` cache directory

Fails if `.familytree.json` already exists.

---

### `ft validate`

Validate all records in the tree against their JSON schemas.

```
ft validate [--strict]
```

- Scans `persons/**/.person.json` and `relations/**/.relation.json` recursively.
- Reports files that fail schema validation with the path, field, and error message.
- `--strict` treats unknown fields as errors (normally they are warnings).
- Exits with code `0` if all records are valid, `1` otherwise.

---

### `ft index`

Rebuild the `.familytree/` cache files (`persons-index.json`, `relations-index.json`).

```
ft index
```

Scans all records and writes the index files. Run this after manual edits or after git operations that change records outside of `ft`.

---

### `ft person`

Subcommands for managing person records.

#### `ft person add`

Interactively create a new person record.

```
ft person add [--folder <relative-path>] [--from-json <file>]
```

- Prompts for required fields (`name.given`, `name.surname`) and optional ones.
- `--folder` sets the subdirectory under `persons/` where the new record folder is created. Defaults to `persons/<given-surname>/`.
- `--from-json` reads initial values from a JSON file instead of prompting.
- Generates a UUID v4 for the new record.
- Writes `persons/<folder>/.person.json` and updates the index.

#### `ft person list`

List all persons in the tree.

```
ft person list [--filter <expr>]
```

Output columns (text mode): UUID (short), full name, birth year, death year.

`--filter` accepts simple expressions, e.g. `surname=Smith`, `birth.year>1800`.

#### `ft person show <uuid>`

Print a person record in a human-readable summary or as raw JSON.

```
ft person show <uuid> [--raw]
```

`--raw` prints the `.person.json` file contents verbatim.

#### `ft person edit <uuid>`

Open the person's `.person.json` in `$EDITOR` for manual editing, then validate on save.

```
ft person edit <uuid>
```

Sets `changed` to the current ISO 8601 datetime before writing.

#### `ft person set <uuid> <field> <value>`

Set a single scalar field on a person record from the command line without opening an editor.

```
ft person set <uuid> birth.date "1932-04-15"
ft person set <uuid> sex M
```

Field paths use dot notation. Updates `changed`. Validates the record after the change.

#### `ft person remove <uuid>`

Remove a person record and its directory.

```
ft person remove <uuid> [--force]
```

- Refuses if the person is referenced by any relation, unless `--force` is given.
- With `--force`, also removes all relations that reference the person.
- Updates the index.

---

### `ft relation`

Subcommands for managing relation records.

#### `ft relation add`

Interactively create a new relation.

```
ft relation add --type <partner|filiation|association> [--folder <relative-path>] [--from-json <file>]
```

Prompts differ by type:

- `filiation`: prompts for `parent` UUID and `child` UUID, optional `pedigree`.
- `partner`: prompts for two person UUIDs, optional `kind`.
- `association`: prompts for `from` UUID, `to` UUID, and `relation` label.

#### `ft relation list`

List all relations.

```
ft relation list [--type <partner|filiation|association>] [--person <uuid>]
```

`--person` filters to relations involving a specific person UUID.

#### `ft relation show <uuid>`

Print a relation record.

```
ft relation show <uuid> [--raw]
```

#### `ft relation edit <uuid>`

Open the relation's `.relation.json` in `$EDITOR`.

```
ft relation edit <uuid>
```

#### `ft relation remove <uuid>`

Remove a relation record and its directory.

```
ft relation remove <uuid>
```

---

### `ft find-duplicates`

Identify persons that are likely duplicates based on name and life-event similarity.

```
ft find-duplicates [--threshold <0-100>]
```

- Compares `name`, `birth.date`, `birth.place`, `death.date` across all persons.
- Reports pairs above the similarity threshold (default: 80).
- Pairs listed in `.familytree.json` `not_duplicates` are suppressed from output.
- Output includes the two UUIDs, names, and similarity score.
- Use `ft not-duplicate <uuid1> <uuid2>` to suppress a pair permanently.

---

### `ft not-duplicate <uuid1> <uuid2>`

Mark two persons as confirmed distinct, suppressing them from `ft find-duplicates` output.

```
ft not-duplicate <uuid1> <uuid2> [--note <text>]
```

Adds an entry to `.familytree.json` `not_duplicates`.

---

### `ft tree`

Print an ASCII ancestry or descendant tree for a person.

```
ft tree <uuid> [--ancestors | --descendants] [--depth <n>]
```

- `--ancestors` (default): walks up via `filiation` relations.
- `--descendants`: walks down via `filiation` relations.
- `--depth` limits the number of generations (default: unlimited).

---

### `ft import`

Import a GEDCOM file into the tree, creating person and relation records.

```
ft import <gedcom-file> [--folder <relative-path>] [--dry-run]
```

- `--dry-run` reports what would be created without writing anything.
- Assigns new UUID v4 to each imported record.
- Attempts to detect duplicates against existing persons and prompts to merge or skip.

---

### `ft export`

Export the tree (or a subset) to a GEDCOM file.

```
ft export [--output <file>] [--persons <uuid,...>] [--gedcom-version <5.5.1|7.0>]
```

- If `--persons` is given, only those persons and their connected relations are exported.
- Defaults to GEDCOM 5.5.1.

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Validation or logic error |
| 2 | Usage / argument error |
| 3 | Tree root not found |

## Index Files

The `.familytree/persons-index.json` and `.familytree/relations-index.json` cache files are maintained automatically by every write command. If they fall out of sync (e.g. after a `git pull`), run `ft index` to rebuild them. All read commands fall back to a full scan when the index is absent.

## Python Package Layout (sketch)

```
familytree-cli/
  ft/
    __main__.py       ← entry point: `python -m ft` or `ft` console script
    cli.py            ← argument parsing (argparse or Click)
    tree.py           ← tree discovery and control-file handling
    person.py         ← person CRUD operations
    relation.py       ← relation CRUD operations
    index.py          ← index build/read helpers
    validate.py       ← JSON Schema validation wrappers
    duplicates.py     ← similarity scoring for find-duplicates
    gedcom/
      importer.py
      exporter.py
  pyproject.toml
  README.md
```
