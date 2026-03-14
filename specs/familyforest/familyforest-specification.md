# FamilyForest Specification

**Version:** 0.1 (Draft)
**Status:** Proposal
**Depends on:** FamilyTree Specification v1.0.0

## Motivation

The FamilyTree format is designed for a single contributor working on one unified dataset. When thousands of contributors each bring their own GEDCOM, a different model is needed:

- Forcing all trees to merge creates conflicts that may be impossible to resolve without domain knowledge
- Different contributors may have legitimately different data for the same person — both versions are valuable
- Identity resolution ("is this person the same as that person?") is a separate concern from data storage
- Trees should remain independently owned and auditable

A **FamilyForest** keeps trees separate and adds a cross-tree identity layer on top. No merging is required. Conflicts become observations, not blockers.

## Core Concepts

### Tree

A **tree** is a single FamilyTree dataset conforming to the FamilyTree spec. Each tree has a UUID v4 as its stable identity, stored in its `.familytree/format.json`. The directory name is a free-form label and is not the identity. Trees are independently valid and self-contained.

### Forest

A **forest** is a named collection of trees stored in a single repository under a `.familyforest/` directory. Trees coexist without merging. The forest provides shared infrastructure for cross-tree discovery and identity resolution.

Forests are classified by scale. The scale is informational — it does not change the format or directory structure, but it signals the intended use and guides tooling expectations around indexing, search performance, and identity-link volume.

| Scale | Name | Trees | Persons (approx.) | Typical use |
|-------|------|-------|-------------------|-------------|
| Small | **grove** | 1–5 | < 1 000 | A family with a few submitted trees |
| Medium | **wood** | 6–50 | 1 000–50 000 | A regional or surname project |
| Large | **forest** | 51–500 | 50 000–1 000 000 | A national or multi-lineage aggregation |
| Very large | **jungle** | 500+ | 1 000 000+ | A global crowdsourced dataset |

The scale is declared in `format.json` via the `scale` field. Tooling uses it to choose between in-memory traversal (grove/wood) and indexed or paginated strategies (forest/jungle).

### Identity Link

An **identity link** is an assertion that a person in one tree is believed to represent the same real individual as a person in another tree. Identity links are stored separately from the trees themselves — they do not modify any person or relation file.

Identity links have a **confidence level**:

| Level      | Meaning                                                  |
|------------|----------------------------------------------------------|
| `certain`  | Confirmed same person — supported by a primary source    |
| `probable` | Strong evidence — matching name, dates, and place        |
| `possible` | Weak evidence — needs further investigation              |
| `rejected` | Confirmed different persons — suppresses future matches  |

## Directory Layout

```
.familyforest/
  format.json
  trees/
    smith-family/               ← any name
      .familytree/
        familytree.json         ← contains the tree UUID
        persons-index.json
        relations-index.json
      persons/
      relations/
      media/
    brown-family/               ← any name
      .familytree/
        ...
  links/
    identity-links.json
  index/
    trees-index.json
```

### `format.json`

Declares the format version and scale of this `.familyforest/` directory.

```json
{
  "format": "familyforest",
  "version": "1.0.0",
  "scale": "grove"
}
```

| Field     | Required | Description                                                    |
|-----------|----------|----------------------------------------------------------------|
| `format`  | Yes      | Always `"familyforest"`                                        |
| `version` | Yes      | Semantic version of the spec this forest conforms to           |
| `scale`   | No       | `"grove"`, `"wood"`, `"forest"`, or `"jungle"` (default: `"grove"`) |

The `scale` field is informational — changing it does not restructure any data.

### `trees/`

Each subdirectory of `trees/` is a tree. The directory name can be any text — it is a local label chosen at import time. The tree's stable identity is the UUID in its `.familytree/familytree.json`, not the directory name. Tooling and identity links reference trees by UUID; the directory name is for human convenience only.

### `links/identity-links.json`

Stores all cross-tree identity links. Each entry links exactly two persons from different trees.

```json
[
  {
    "id": "c8d4f1a2-b3e4-c5d6-e7f8-a9b0c1d2e3f4",
    "persons": [
      { "tree": "ce6a0e2e-32aa-4957-b658-9e952b0c6aa3", "person": "550e8400-e29b-41d4-a716-446655440000" },
      { "tree": "9f1b3d72-a4c5-48e6-b7d8-e9f0a1b2c3d4", "person": "9b4e11a2-c3d4-e5f6-a7b8-c9d0e1f2a3b4" }
    ],
    "confidence": "probable",
    "note": "Same name, birth year, and place across both submissions"
  }
]
```

#### Identity Link Fields

| Field        | Required | Description                                              |
|--------------|----------|----------------------------------------------------------|
| `id`         | Yes      | UUID v4 identifying this link                            |
| `persons`    | Yes      | Exactly two entries, each with `tree` UUID and `person` UUID |
| `confidence` | Yes      | `certain`, `probable`, `possible`, or `rejected`         |
| `note`       | No       | Free-text explanation of the link decision               |

Links are unordered — the two persons are equivalent regardless of which appears first.

### `index/trees-index.json`

A derived index of all trees in the forest, regenerated automatically by tooling.

```json
[
  {
    "id": "ce6a0e2e-32aa-4957-b658-9e952b0c6aa3",
    "name": "smith-family",
    "path": "trees/smith-family",
    "person_count": 142,
    "relation_count": 98
  }
]
```

## Tooling

All `ff` commands accept either a tree UUID or its human-readable name (from `trees-index.json`) as the tree identifier. For example, `ce6a0e2e` and `smith-family` are interchangeable if the name `smith-family` is registered in the index.

### `ff list trees`

Lists all trees in the forest with their UUID, name, and person count.

```
ce6a0e2e  smith-family   142 persons   98 relations
9f1b3d72  brown-family    87 persons   61 relations
```

### `ff add-tree [--name <name>] [path]`

Registers a new tree in the forest. Generates a UUID v4 for the tree. If `path` points to an existing tree directory, it is copied into `trees/<uuid>/` and its `format.json` is updated with the new UUID. If no path is given, an empty tree is initialised. The optional `--name` flag sets the human-readable name stored in `trees-index.json`.

### `ff import-gedcom <file.ged> [--name <name>]`

Imports a GEDCOM file as a new named tree. Generates a UUID v4 for the tree. Equivalent to `ft import-gedcom` scoped to the new tree. The GEDCOM source is recorded in each person's `sources[]` array. The optional `--name` flag sets the human-readable name in the index.

### `ff show <tree>/<uuid>`

Displays a person by tree identifier and person UUID. Shows the person's data and lists any identity links to persons in other trees.

```
Jane Smith  [ce6a0e2e / 550e8400]
Sex:   F
Born:  1932-07-04  Cork, Ireland

Identity links:
  probable → 9f1b3d72 (brown-family) / Jane M. Smith  [9b4e11a2]
             "Same name, birth year, and place across both submissions"
```

### `ff tree <tree>/<uuid>`

Renders the family tree rooted at the given person. By default stays within the named tree. With `--follow-links`, traverses `certain` and `probable` identity links to include persons from other trees, showing which tree each person belongs to.

### `ff find-matches`

Scans all trees for potential cross-tree identity matches using the same heuristics as `ft find-duplicates` (name similarity, birth date overlap, birth place similarity), but operating across tree boundaries. Outputs candidate pairs for review.

```
POSSIBLE CROSS-TREE MATCH
  ce6a0e2e (smith-family) / Jane Smith       born 1932-07-04  Cork, Ireland
  9f1b3d72 (brown-family) / Jane M. Smith    born 1932        Cork, Ireland
  Differs: name.given (middle initial), birth.date (partial vs full)
```

### `ff link <tree-a>/<uuid-a> <tree-b>/<uuid-b>`

Creates a cross-tree identity link between two persons. Prompts for confidence level and an optional note. Appends to `links/identity-links.json`.

```
ff link ce6a0e2e/550e8400 9f1b3d72/9b4e11a2 --confidence probable --note "Same birth record"
```

### `ff reject-link <tree-a>/<uuid-a> <tree-b>/<uuid-b>`

Records that two persons are confirmed distinct, setting confidence to `rejected`. This suppresses the pair from future `ff find-matches` output. If a link already exists it is updated; otherwise a new `rejected` link is created.

### `ff list links [tree]`

Lists all identity links, optionally filtered to a specific tree. Shows both sides of each link with confidence level.

```
c8d4f1a2  probable  ce6a0e2e/Jane Smith ↔ 9f1b3d72/Jane M. Smith
```

### `ff validate`

Validates the forest structure:
- Each tree directory contains a valid `.familytree/` dataset (runs `ft validate` per tree)
- All identity links reference existing persons in existing trees
- No identity link references two persons in the same tree (use `ft find-duplicates` for within-tree matches)
- `format.json` is present and version is compatible

## Relationship to FamilyTree

A FamilyForest is a thin coordination layer on top of independent FamilyTree datasets. Each tree inside a forest is fully valid on its own and can be used with `ft` tooling directly by pointing at its `.familytree/` directory. The forest adds only:

- A shared namespace (tree UUIDs with optional human-readable names)
- Cross-tree identity links
- A shared index of trees
- Forest-level tooling (`ff` commands)

A single-contributor workflow needs only the FamilyTree format. The FamilyForest format is intended for multi-contributor or aggregation scenarios where merging is impractical or undesirable.
