# familytree-cli

Command-line tool for creating and managing family tree data in the [FamilyTree format](../familytree-specs/familytree-specification.md).

## Installation

```bash
pip install -e familytree-cli/
```

Requires Python 3.10+.

## Concepts

A tree is a directory containing:
- `.familytree.json` — control file (tree UUID + settings)
- `persons/` — person records, each as `<folder>/.person.json`
- `relations/` — relation records, each as `<folder>/.relation.json`
- `.familytree/` — derived index cache (auto-managed)

`ft` auto-detects the tree root by walking up from the current directory, similar to how Git finds `.git/`. Override with `--tree <path>`.

UUIDs can be abbreviated to any unambiguous prefix (minimum 4 characters) in all commands.

## Global options

```
ft [--tree PATH] [--format text|json] [--quiet] <command>
```

## Commands

### Tree management

```bash
ft init [PATH]          # create a new tree (default: current directory)
ft validate [--strict]  # validate all records against JSON schemas
ft index                # rebuild the .familytree/ index cache
```

### Persons

```bash
# Add
ft person add                          # interactive prompts
ft person add --from-json data.json    # pre-fill from a JSON file
ft person add --folder persons/my-dir  # custom folder

# List
ft person list                   # all persons
ft person list --filter sex=F    # filter: field=value (surname, sex, birth.year, …)

# Inspect
ft person show <uuid>            # human-readable summary
ft person show <uuid> --raw      # raw .person.json

# Edit
ft person edit <uuid>            # open in $EDITOR, validates on save
ft person set <uuid> <field> <value>  # set a single field

# Examples for ft person set:
ft person set 88121758 sex M
ft person set 88121758 birth.date "1932-04-15"
ft person set 88121758 birth.place "Paris, France"
ft person set 88121758 living false

# Remove
ft person remove <uuid>          # refuses if relations exist
ft person remove <uuid> --force  # also deletes related relations
```

`--from-json` accepts a partial person object (any fields from `person.schema.json` except `uuid`, `created`, `changed`, which are set automatically).

`ft person set` uses dot-notation for nested fields. Values are parsed as JSON where possible (`true`/`false` → bool, numbers → int/float), otherwise treated as strings.

### Relations

Three relation types:

| Type | Required fields |
|------|----------------|
| `filiation` | `parent` UUID, `child` UUID |
| `partner` | two person UUIDs |
| `association` | `from` UUID, `to` UUID, `relation` label |

```bash
# Add
ft relation add --type filiation    # prompts for parent + child UUIDs
ft relation add --type partner      # prompts for two person UUIDs + optional kind
ft relation add --type association  # prompts for from, to, and relation label
ft relation add --type filiation --from-json rel.json

# List
ft relation list                        # all relations
ft relation list --type filiation       # filter by type
ft relation list --person <uuid>        # all relations involving a person

# Inspect / edit / remove
ft relation show <uuid> [--raw]
ft relation edit <uuid>
ft relation remove <uuid>
```

### Ancestry tree

```bash
ft tree <uuid>                        # ancestor tree (default, depth 5)
ft tree <uuid> --ancestors            # same as default
ft tree <uuid> --descendants          # descendant tree
ft tree <uuid> --descendants --depth 3
```

### Duplicate detection

```bash
ft find-duplicates                   # default threshold: 80/100
ft find-duplicates --threshold 70    # lower = more candidates

ft not-duplicate <uuid1> <uuid2>                  # suppress a pair permanently
ft not-duplicate <uuid1> <uuid2> --note "twins"   # with a reason
```

Scoring weights: surname 30%, given name 20%, birth year 30%, death year 20%.

### GEDCOM import / export

```bash
# Import
ft import family.ged                 # prompts on likely duplicates
ft import family.ged --dry-run       # parse only, nothing written
ft import family.ged --folder persons/imported

# Export
ft export                            # all persons, to stdout
ft export --output family.ged
ft export --output subset.ged --persons <uuid1>,<uuid2>
ft export --output family.ged --gedcom-version 5.5.1   # default
```

Import maps GEDCOM `INDI` records to persons and `FAM` records to partner + filiation relations. Dates are converted between GEDCOM format (`15 APR 1932`) and ISO 8601 (`1932-04-15`).

## Output formats

All list and show commands accept `--format json` for machine-readable output:

```bash
ft --format json person list
ft --format json person show <uuid>
ft --format json relation list --person <uuid>
```

## Exit codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Validation or logic error |
| 2 | Usage / argument error |
| 3 | Tree root not found |
