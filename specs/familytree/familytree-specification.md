# FamilyTree Specification

**Version:** 0.1 (Draft)
**Status:** Proposal

## Motivation

GEDCOM is the de facto standard for genealogical data exchange, but it has key
limitations for collaborative, distributed work:

- No built-in history or provenance tracking
- No diff/merge semantics — files are monolithic blobs
- No content integrity verification
- Opaque sequential IDs (`@I0001@`) that collide when merging from different sources

This spec defines the **FamilyTree Flat File Format**, a plain-text,
content-addressable format inspired by Git's object model, designed to:

- Version-control ancestry data naturally with Git
- Merge records from multiple sources without ID collisions
- Track provenance — who recorded what, from which source
- Remain human-readable and auditable
- Round-trip with GEDCOM for interoperability

## Core Concepts

A family tree consists of exactly two types of records:

- **Persons** — the individuals
- **Relations** — the links between them

There is no third entity. Events are not standalone records — they are always embedded inside a person or a relation. Every piece of data in the tree belongs to one of these two types.

### Person

A **person** is an individual with attributes describing their identity and life:

- Names (given, surname, alias)
- Sex
- Birth, death, burial (date and place)
- Notes and sources

### Relation

A **relation** links two persons. Relation types:

| Type        | Directional | Description                                                  |
|-------------|-------------|--------------------------------------------------------------|
| `partner`   | No          | Two people in a couple (married, civil union, or common-law) |
| `filiation` | Yes         | From parent to child — biological or adoptive                |

A family unit is expressed as a set of individual relations, not a single record.

Sibling relationships are implicit — two persons sharing a common parent via `filiation`
relations are considered siblings without an explicit link.

## File Format

Each person and each relation is stored as a separate JSON file. The filename is the
record's UUID v4 (e.g. `550e8400-e29b-41d4-a716-446655440000.json`), which is also
stored as the `id` field inside the file.

### Directory Layout

A tree can be stored in a directory with any name. The `.familytree/` subdirectory is the fixed format marker — its presence identifies the directory as a FamilyTree dataset. The tree's stable identity is its UUID, stored in `.familytree/familytree.json`, not derived from the directory name.

```
my-tree/                    ← any name
  .familytree/
    familytree.json
    persons-index.json
    relations-index.json
  persons/
    550e8400-e29b-41d4-a716-446655440000.json
    9b4e11a2-c3d4-e5f6-a7b8-c9d0e1f2a3b4.json
  relations/
    b109de44-f1a2-b3e4-c5d6-e7f8a9b0c1d2.json
  media/
    birth-cert-jane-smith-1932.jpg
    smith-family-photo-1955.jpg
```

The `.familytree/` subdirectory contains `familytree.json` (the control file) and the derived index files. The `media/` directory holds all media files referenced by persons, relations, and events. JSON schemas and the specification document live in `specs/familytree/` and are shared across all trees. The entire `.familytree/` directory and `media/` should be committed to Git alongside persons and relations.

### `media/`

All media files for the tree — photographs, scanned documents, certificates, audio, video — are stored flat in `media/`. There is no required subdirectory structure within `media/`.

`avatar_file` and `media_files` fields on persons, relations, and events reference files by path relative to the tree root (e.g. `media/birth-cert-jane-smith-1932.jpg`). External URLs are also valid values for these fields.

### `familytree.json`

Located at `.familytree/familytree.json`. The single control file for a FamilyTree dataset. Combines format declaration with manually managed dataset decisions. Tooling reads this file to verify compatibility before reading or writing any data.

Schema: `specs/familytree/familytree.schema.json`

```json
{
  "format": "familytree",
  "version": "1.0.0",
  "id": "ce6a0e2e-32aa-4957-b658-9e952b0c6aa3",
  "not_duplicates": []
}
```

| Field           | Required | Description                                                      |
|-----------------|----------|------------------------------------------------------------------|
| `format`        | Yes      | Always `"familytree"` — identifies the format                    |
| `version`       | Yes      | Semantic version of the spec this dataset conforms to            |
| `id`            | Yes      | UUID v4 — the tree's stable identity                             |
| `not_duplicates`| No       | Pairs of persons confirmed distinct (see `ft not-duplicate`)     |

The `id` is the authoritative identity of the tree regardless of the directory name. Tooling and forests reference trees by this UUID. If the file does not exist or `format` is not `"familytree"`, tooling should treat the directory as unrecognised and warn the user.

### `persons-index.json`

Schema: `specs/familytree/persons-index.schema.json`

Located at `.familytree/persons-index.json`. A derived index of all persons, used by tooling for fast lookup, listing, and duplicate detection without reading every person file. Contains one entry per person with the fields most commonly needed for search and display.

```json
[
  {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "name": { "given": "Jane", "surname": "Smith" },
    "sex": "F",
    "birth": { "date": "1932-07-04", "place": "Cork, Ireland" },
    "death": null
  }
]
```

The index is regenerated automatically by tooling whenever a person file is created, updated, or deleted. It is a cache — the person files in `persons/` are always the source of truth.

### `relations-index.json`

Schema: `specs/familytree/relations-index.schema.json`

Located at `.familytree/relations-index.json`. A derived index of all relations, used by tooling for fast traversal, listing, and integrity checking without reading every relation file. Contains one entry per relation with enough information to display the link and resolve both sides.

```json
[
  {
    "id": "b109de44-f1a2-b3e4-c5d6-e7f8a9b0c1d2",
    "type": "filiation",
    "parent": "9b4e11a2-c3d4-e5f6-a7b8-c9d0e1f2a3b4",
    "child": "550e8400-e29b-41d4-a716-446655440000"
  },
  {
    "id": "c3d4e5f6-a7b8-c9d0-e1f2-a3b4c5d6e7f8",
    "type": "partner",
    "persons": [
      "9b4e11a2-c3d4-e5f6-a7b8-c9d0e1f2a3b4",
      "3f7c1d00-e29b-41d4-a716-446655440111"
    ]
  }
]
```

Like `persons-index.json`, this file is regenerated automatically and the relation files in `relations/` are always the source of truth.

### Person File

Schema: `specs/familytree/person.schema.json`

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": {
    "given": "Jane",
    "surname": "Smith"
  },
  "sex": "F",
  "birth": { "date": "1932-07-04", "place": "Cork, Ireland" },
  "death": null,
  "avatar_file": null,
  "media_files": [],
  "uncertain": []
}
```

### Relation File

Schema: `specs/familytree/relation.schema.json`

```json
{
  "id": "b109de44-f1a2-b3e4-c5d6-e7f8a9b0c1d2",
  "type": "filiation",
  "parent": "9b4e11a2-c3d4-e5f6-a7b8-c9d0e1f2a3b4",
  "child":  "550e8400-e29b-41d4-a716-446655440000",
  "media_files": [],
  "uncertain": []
}
```

For `partner` relations, use `"persons"` instead of `"from"`/`"to"`:

```json
{
  "id": "c3d4e5f6-a7b8-c9d0-e1f2-a3b4c5d6e7f8",
  "type": "partner",
  "persons": [
    "9b4e11a2-c3d4-e5f6-a7b8-c9d0e1f2a3b4",
    "3f7c1d00-e29b-41d4-a716-446655440111"
  ],
  "media_files": [],
  "uncertain": []
}
```

## Person Fields

### Identity

| Field               | Type         | Required | Description                                        |
|---------------------|--------------|----------|----------------------------------------------------|
| `id`                | UUID v4      | Yes      | Unique identifier, matches filename                |
| `name`              | object       | Yes      | Primary name (see Name Fields)                     |
| `names`             | object[]     | No       | Additional name variants (maiden, immigrant, etc.) |
| `sex`               | `M` `F` `X` | No       | Biological sex                                     |
| `title`             | string       | No       | Nobility or honorific title (Sir, Dame, Duke)      |
| `restriction`       | string       | No       | `confidential`, `locked`, or `privacy`             |
| `changed`           | string       | No       | ISO 8601 datetime of last change                   |

### Name Fields

Applies to both `name` and each entry in `names[]`:

| Field            | Type   | Description                                        |
|------------------|--------|----------------------------------------------------|
| `given`          | string | Given name(s)                                      |
| `surname`        | string | Surname(s)                                         |
| `surname_prefix` | string | Surname prefix (van, de, von)                      |
| `prefix`         | string | Name prefix (Dr., Rev., Sir)                       |
| `suffix`         | string | Name suffix (Jr., III, Esq.)                       |
| `nickname`       | string | Nickname                                           |
| `alias`          | string | Known alias or stage name                          |
| `type`           | string | Name type: `birth`, `maiden`, `immigrant`, `adopted`, `alias`, etc. |
| `phonetic`       | string | Phonetic variation of the full name                |
| `romanized`      | string | Romanized variation of the full name               |
| `note`           | string | Free-text note about this name                     |

### Life Events

| Field          | Type         | Required | Description                         |
|----------------|--------------|----------|-------------------------------------|
| `birth`        | object\|null | No       | Birth event                         |
| `death`        | object\|null | No       | Death event                         |
| `burial`       | object\|null | No       | Burial event                        |

`birth`, `death`, and `burial` each support: `date`, `place`, `coords`, `age`, `cause`, `agency`, `restriction`, `note`, `sources`.

### Personal Attributes & Facts

| Field                  | Type     | Description                                          |
|------------------------|----------|------------------------------------------------------|
| `occupation`           | string[] | Occupation(s), one entry each                        |
| `nationality`          | string   | Nationality or ethnic origin                         |
| `religion`             | string   | Religion                                             |
| `caste`                | string   | Caste name                                           |
| `physical_description` | string   | Physical description                                 |
| `national_id`          | object   | National ID: `{ "value": "…", "type": "passport" }`  |
| `facts`                | object[] | Typed facts: `[{ "type": "…", "value": "…" }]`       |

### Associations

| Field          | Type     | Description                                                      |
|----------------|----------|------------------------------------------------------------------|
| `associations` | object[] | Non-family links to other persons (godfather, witness, employer) |

Each association: `{ "person": uuid, "relation": "godfather", "note": "…", "sources": [] }`

### Media & Notes

| Field         | Type         | Description                              |
|---------------|--------------|------------------------------------------|
| `avatar_file` | string\|null | Path or URL to the person's avatar image |
| `media_files` | string[]     | Paths relative to `media/` or URLs       |
| `notes`       | string[]     | Free-text notes, one entry per note      |
| `sources`     | object[]     | Sources (see Sources section)            |
| `events`      | object[]     | Life events (see Events section)         |
| `uncertain`   | string[]     | Dot-notation paths of uncertain fields   |

### Uncertain Fields

Fields whose values are not fully verified are listed in the `uncertain` array
using dot-notation paths:

```json
{
  "birth": { "date": "1820", "place": "El Bierzo, León, España" },
  "uncertain": ["birth.date", "birth.place"]
}
```

## Relation Fields

### Common Fields

| Field         | Type     | Required | Description                                         |
|---------------|----------|----------|-----------------------------------------------------|
| `id`          | UUID v4  | Yes      | Unique identifier, matches filename                 |
| `type`        | string   | Yes      | `partner` or `filiation`                            |
| `events`      | object[] | No       | Events associated with this relation                |
| `sources`     | object[] | No       | Sources supporting this relation                    |
| `media_files` | string[] | No       | Paths relative to `media/` or URLs                  |
| `notes`       | string[] | No       | Free-text notes                                     |
| `uncertain`   | string[] | No       | Dot-notation paths of uncertain fields              |
| `restriction` | string   | No       | `confidential`, `locked`, or `privacy`              |
| `changed`     | string   | No       | ISO 8601 datetime of last change                    |

### `partner` Fields

| Field     | Type      | Required | Description                       |
|-----------|-----------|----------|-----------------------------------|
| `persons` | UUID v4[] | Yes      | Exactly two persons in the couple |

### `filiation` Fields

| Field      | Type    | Required | Description                                                      |
|------------|---------|----------|------------------------------------------------------------------|
| `parent`   | UUID v4 | Yes      | The parent person                                                |
| `child`    | UUID v4 | Yes      | The child person                                                 |
| `pedigree` | string  | No       | `birth`, `adopted`, `foster`, or `sealing` (default: `birth`)   |
| `status`   | string  | No       | `challenged`, `disproven`, or `proven`                           |

## Events

Beyond `birth`, `death`, and `burial`, a person may have additional life events in an `events` array. Relations also carry events (e.g. a wedding ceremony). Events are never standalone records.

### Event Fields

| Field          | Required | Applies to | Description                                          |
|----------------|----------|------------|------------------------------------------------------|
| `type`         | Yes      | all        | Event type (see below)                               |
| `type_label`   | No       | all        | Human label when `type` is `custom`                  |
| `date`         | No       | all        | Date of the event (see Date Format)                  |
| `place`        | No       | all        | Place of the event (see Place Format)                |
| `coords`       | No       | all        | `{ "lat": …, "lng": … }`                             |
| `age`          | No       | person     | Age of the person at time of event                   |
| `age_partner_a`| No       | partner    | Age of first partner at event                        |
| `age_partner_b`| No       | partner    | Age of second partner at event                       |
| `cause`        | No       | all        | Cause of the event (e.g. cause of death)             |
| `agency`       | No       | all        | Responsible agency or organization                   |
| `religion`     | No       | all        | Religious affiliation of the event                   |
| `restriction`  | No       | all        | `confidential`, `locked`, or `privacy`               |
| `note`         | No       | all        | Free-text note                                       |
| `sources`      | No       | all        | Sources for this event                               |

### Person Event Types

| Type               | Description                         |
|--------------------|-------------------------------------|
| `immigration`      | Arrival in a new country            |
| `emigration`       | Departure from a country            |
| `residence`        | Known place of residence            |
| `military`         | Military service                    |
| `census`           | Census appearance                   |
| `education`        | School or university                |
| `christening`      | Christening                         |
| `adult_christening`| Adult christening                   |
| `cremation`        | Cremation                           |
| `adoption`         | Adoption                            |
| `baptism`          | Baptism                             |
| `bar_mitzvah`      | Bar Mitzvah                         |
| `bat_mitzvah`      | Bat Mitzvah                         |
| `blessing`         | Blessing                            |
| `confirmation`     | Confirmation                        |
| `first_communion`  | First communion                     |
| `ordination`       | Ordination                          |
| `naturalization`   | Naturalization                      |
| `probate`          | Probate                             |
| `will`             | Filing of a will                    |
| `graduation`       | Graduation                          |
| `retirement`       | Retirement                          |
| `custom`           | Any other event (use `type_label`)  |

### Partner Relation Event Types

| Type                  | Description              |
|-----------------------|--------------------------|
| `marriage`            | Wedding ceremony         |
| `divorce`             | Divorce                  |
| `annulment`           | Annulment                |
| `engagement`          | Engagement               |
| `marriage_banns`      | Marriage banns           |
| `marriage_contract`   | Marriage contract        |
| `marriage_licence`    | Marriage licence         |
| `marriage_settlement` | Marriage settlement      |
| `divorce_filing`      | Divorce filing           |
| `census`              | Census (family)          |
| `residence`           | Family residence         |
| `custom`              | Any other event          |

## Date Format

Dates are stored as strings using a subset of ISO 8601, extended to support
partial, approximate, bounded, and range values.

| Pattern                   | Example                     | Meaning                       |
|---------------------------|-----------------------------|-------------------------------|
| `YYYY-MM-DD`              | `1953-12-18`                | Full date                     |
| `YYYY-MM`                 | `1820-06`                   | Month and year only           |
| `YYYY`                    | `1820`                      | Year only                     |
| `~YYYY-MM-DD`             | `~1820-06-12`               | Approximate full date         |
| `~YYYY-MM`                | `~1820-06`                  | Approximate month and year    |
| `~YYYY`                   | `~1820`                     | Approximate year              |
| `<YYYY-MM-DD`             | `<1820-06-12`               | Before a date                 |
| `>YYYY-MM-DD`             | `>1820-06-12`               | After a date                  |
| `YYYY/YYYY`               | `1820/1825`                 | Range between two years       |
| `YYYY-MM-DD/YYYY-MM-DD`   | `1820-06-12/1825-03-01`     | Range between two full dates  |

Uncertain dates (where the value itself is in doubt) are marked via the
`uncertain` array, not the date string itself.

## Place Format

Places are stored as a comma-separated string ordered from most specific
to least specific (city → region → country). Omit levels that are unknown.

```json
"birth": {
  "date": "1932-07-04",
  "place": "Cork, Ireland",
  "coords": { "lat": 51.8985, "lng": -8.4756 }
}
```

`coords` is optional. If present, it contains `lat` and `lng` as decimal degrees.

Include only the levels of place that are known:

```
"Cork, Ireland"        ← full
"Ireland"              ← city unknown
```

Historical place names should be recorded as they were at the time,
with a note if clarification is needed.

## Sources & Provenance

Every person and relation can reference one or more sources via a `sources` array.
Each source is an inline object describing where the data came from.

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": { "given": "Jane", "surname": "Smith" },
  "sources": [
    {
      "title": "Birth certificate – County Cork, 1932",
      "type": "civil-record",
      "file": "media/birth-cert-jane-smith-1932.jpg",
      "date": "2025-11-04",
      "recorded_date": "1932-03-12",
      "page": "Vol. 4, folio 37",
      "text": "Jane Mary Smith, born 12 March 1932, father Patrick Smith, mother Ellen Riordan.",
      "quality": 3,
      "event_type": "birth",
      "role": "subject",
      "note": "Scanned from original document held by family."
    }
  ]
}
```

### Source Fields

| Field           | Required | Description                                                              |
|-----------------|----------|--------------------------------------------------------------------------|
| `title`         | Yes      | Short description of the source                                          |
| `type`          | No       | Source type (see below)                                                  |
| `file`          | No       | Path or URL to the source file                                           |
| `date`          | No       | Date the source was created or accessed                                  |
| `recorded_date` | No       | Date the entry was originally recorded in the source                     |
| `page`          | No       | Page, folio, or frame reference within the source                        |
| `text`          | No       | Verbatim transcription of the relevant passage (GEDCOM `SOUR.DATA.TEXT`) |
| `quality`       | No       | Certainty: `0` unreliable · `1` questionable · `2` secondary · `3` primary (GEDCOM `QUAY`) |
| `event_type`    | No       | Type of event recorded in this source (e.g. `birth`, `marriage`)        |
| `role`          | No       | Person's role in the cited event (e.g. `bride`, `witness`, `subject`)   |
| `note`          | No       | Free-text note about the source                                          |

### Source Types

| Value               | Description                          |
|---------------------|--------------------------------------|
| `personal-document` | Handwritten chart, letter, diary     |
| `photograph`        | Photo of a person or document        |
| `civil-record`      | Birth, marriage or death certificate |
| `church-record`     | Baptism, burial register             |
| `census`            | Census record                        |
| `oral`              | Family oral history                  |
| `gedcom`            | Imported from a GEDCOM file          |
| `other`             | Any other source                     |

## GEDCOM Interoperability

This format is designed to round-trip with GEDCOM 5.5.1. The mapping is:

| GEDCOM              | FamilyTree                              |
|---------------------|-----------------------------------------|
| `INDI`              | `person` file                           |
| `FAM`               | set of `relation` files                 |
| `@I0001@`           | `id` (UUID v4)                          |
| `NAME Given /Sur/`  | `name.given` + `name.surname`           |
| `SEX M`             | `sex: "M"`                              |
| `BIRT DATE PLACE`   | `birth.date` + `birth.place`            |
| `DEAT DATE PLACE`   | `death.date` + `death.place`            |
| `BURI DATE PLACE`   | `burial.date` + `burial.place`          |
| `HUSB` / `WIFE`     | `partner` relation                      |
| `CHIL`              | `filiation` relation                    |
| `PEDI`              | `filiation.pedigree`                    |
| `NAME` parts        | `name.given`, `name.surname`, `name.prefix`, `name.suffix`, `name.surname_prefix` |
| `NAME TYPE`         | `name.type`                             |
| `FONE` / `ROMN`     | `name.phonetic` / `name.romanized`      |
| `TITL`              | `title`                                 |
| `OCCU`              | `occupation[]`                          |
| `NATI`              | `nationality`                           |
| `RELI`              | `religion`                              |
| `CAST`              | `caste`                                 |
| `DSCR`              | `physical_description`                  |
| `IDNO`              | `national_id`                           |
| `ASSO`              | `associations[]`                        |
| `FACT` / `EVEN`     | `facts[]` or `events[]`                 |
| `RESN`              | `restriction`                           |
| `CHAN`              | `changed`                               |
| `SOUR`              | `sources[]` entry                       |
| `SOUR.PAGE`         | `sources[].page`                        |
| `SOUR.DATA.TEXT`    | `sources[].text`                        |
| `SOUR.DATA.DATE`    | `sources[].recorded_date`               |
| `SOUR.QUAY`         | `sources[].quality`                     |
| `SOUR.EVEN`         | `sources[].event_type`                  |
| `SOUR.ROLE`         | `sources[].role`                        |
| `NOTE`              | `notes[]` entry                         |

### Import (GEDCOM → FamilyTree)

1. Each `INDI` record → one person JSON file with a new UUID v4
2. Each `FAM` record → one `partner` relation + one `filiation` relation per child
3. GEDCOM `@Ixxx@` IDs are discarded; the UUID becomes the stable identity
4. All `NAME` sub-tags (`GIVN`, `SURN`, `SPFX`, `NPFX`, `NSFX`, `NICK`, `TYPE`, `FONE`, `ROMN`) are mapped to the `name` object
5. All individual event types (`BIRT`, `DEAT`, `BURI`, `IMMI`, `EMIG`, `RESI`, `MILI`, `CENS`, `EDUC`, `CHR`, `CREM`, `ADOP`, `BAPM`, `BARM`, `BASM`, `BLES`, `CHRA`, `CONF`, `FCOM`, `ORDN`, `NATU`, `PROB`, `WILL`, `GRAD`, `RETI`, `EVEN`, `FACT`) are mapped to `events[]` or dedicated fields
6. All `FAM` event types (`MARR`, `DIV`, `ANUL`, `ENGA`, `MARB`, `MARC`, `MARL`, `MARS`, `DIVF`, `CENS`, `RESI`, `EVEN`) are mapped to the partner relation's `events[]`
7. Source citations are mapped to `sources[]` preserving `page`, `text`, `recorded_date`, `quality`, `event_type`, and `role`
8. `RESN` and `CHAN` tags are mapped to `restriction` and `changed`
9. `ASSO` tags are mapped to `associations[]`
10. `FACT`/`EVEN` tags are mapped to `facts[]` or `events[]` depending on context

### Export (FamilyTree → GEDCOM)

1. Each person file → one `INDI` record; UUID stored in a `_UID` custom tag
2. Each `partner` relation → one `FAM` record with all partner events
3. Each `filiation` relation → `CHIL` tag added to the relevant `FAM`; `pedigree` → `PEDI`
4. Sequential `@I0001@`-style IDs are generated for the export only
5. Extended name fields (`prefix`, `suffix`, `surname_prefix`, `phonetic`, `romanized`) are exported to their GEDCOM equivalents
6. Source citation fields (`page`, `text`, `recorded_date`, `quality`, `event_type`, `role`) are exported to `SOUR` sub-tags

## Versioning

A tree directory lives inside a Git repository. Git provides the full version history — every change to any person or relation is tracked as a commit.

### Commit Conventions

Each commit should represent one logical change:

| Change                   | Example commit message                         |
|--------------------------|------------------------------------------------|
| Add a person             | `add: Jane Smith (1932)`                       |
| Correct a field          | `fix: Jane Smith birth date 1932-07-04`        |
| Add a relation           | `add: filiation John Smith → Jane Smith`       |
| Import from GEDCOM       | `import: smith-family.ged (GEDCOM 5.5.1)`      |
| Mark fields as uncertain | `uncertain: birth.date for Jane Smith`         |
| Add a source             | `source: add birth certificate to Jane Smith`  |

### Branches

Use branches to work on uncertain or speculative data before merging:

```
main                       ← verified data only
research/smith-8th-gen     ← speculative 8th generation ancestors
import/brown-family        ← in-progress GEDCOM import
```

### Tags

Tag stable snapshots for reference:

```
git tag 2026-03-14-review
```

## Multi-Lineage Support

A single repository can hold multiple family lineages. All persons and relations
share the same `persons/` and `relations/` directories — lineage boundaries are
expressed through relations, not through separate directories or tags.

### How lineages connect

Two lineages merge naturally when a `partner` or `filiation` relation references
persons from different lineages. For example:

- **Smith** — paternal lineage
- **Brown** — maternal lineage, connecting via a partner relation
- **Smith-Brown** — descendants shared by both lineages

A person who connects two lineages is a single file referenced by relations from
both sides. There is no duplication. Lineage membership is always derived
from the graph of relations, never from explicit tags.

## Tooling

The FamilyTree format is designed to be usable with any text editor and Git directly. Tooling is optional but recommended for common workflows.

### Suggested CLI Commands

#### `ft validate`

Validates all person and relation JSON files against their schemas. Checks that:
- Each file is valid JSON conforming to `person.schema.json` or `relation.schema.json`
- The `id` field matches the filename (without `.json`)
- All UUID references in relation files resolve to existing person files
- Dates follow the allowed format patterns
- Dot-notation paths in `uncertain` reference fields that exist in the record

Exits with a non-zero status if any file fails validation, making it suitable for use in Git pre-commit hooks.

#### `ft add-person`

Interactive prompt to create a new person file. Generates a UUID v4, writes a new JSON file to `persons/<uuid>.json`, and opens it in the default editor. All fields are optional except `id` and `name`.

#### `ft add-relation <type>`

Creates a new relation file. `<type>` is either `partner` or `filiation`. Prompts for the relevant UUIDs (`persons` for partner, `parent` and `child` for filiation), generates a UUID v4 for the relation, and writes the file to `relations/<uuid>.json`.

#### `ft import-gedcom <file.ged>`

Imports a GEDCOM 5.5.1 file into a FamilyTree dataset:
1. Each `INDI` record becomes a person file with a newly generated UUID v4
2. Each `FAM` record becomes one `partner` relation (if spouses present) plus one `filiation` relation per child
3. GEDCOM `@Ixxx@` IDs are discarded; UUIDs become the stable identity
4. `SOUR` and `NOTE` tags are mapped to `sources[]` and `notes[]`
5. Prints a summary of how many persons and relations were created

#### `ft export-gedcom [output.ged]`

Exports all persons and relations to a GEDCOM 5.5.1 file. Sequential `@I0001@`-style IDs are generated for the export only and do not affect the stored UUIDs. Each person's UUID is preserved in a `_UID` custom tag for round-trip fidelity. Writes to `output.ged` or stdout if no filename is given.

#### `ft show <uuid>`

Displays a single person or relation by UUID in a human-readable format. Resolves UUID references to display names rather than raw identifiers. Automatically detects whether the UUID belongs to a person or a relation.

Example output for a person:
```
Jane Smith  [550e8400-e29b-41d4-a716-446655440000]
Sex:   F
Born:  1932-07-04  Cork, Ireland
```

#### `ft tree <uuid>`

Renders the family tree as an ASCII diagram, rooted at the person identified by `<uuid>`. Traverses `filiation` and `partner` relations. Accepts optional flags:
- `--ancestors` — show ancestors only (default)
- `--descendants` — show descendants only
- `--all` — show both directions

#### `ft list persons`

Lists all persons in `persons/`, one per line, with their UUID, full name, and birth year. Useful for finding UUIDs to pass to other commands.

```
550e8400  Jane Smith   1932
9b4e11a2  John Smith   ~1900
```

#### `ft list relations`

Lists all relations in `relations/`, one per line, showing the relation type and the names of the persons involved.

```
b109de44  filiation  John Smith → Jane Smith
c3d4e5f6  partner    John Smith + Mary Brown
```

#### `ft check`

Checks referential integrity across the entire dataset without validating schema:
- Every UUID referenced in a relation file exists as a person file
- No orphaned relation files reference non-existent persons
- No duplicate UUIDs exist across persons or relations

Intended as a quick sanity check after manual edits or merges.

#### `ft find-duplicates`

Scans all person files and reports likely duplicates — persons who may represent the same individual. Matching is based on a combination of fields:
- Identical or very similar full name (given + surname)
- Overlapping birth date (exact, partial, or within a configurable year range)
- Same or similar birth place

Outputs a list of candidate pairs with the differing fields and the UUIDs of both records. Does not modify any files.

```
POSSIBLE DUPLICATE
  550e8400  Jane Smith        born 1932-07-04  Cork, Ireland
  a1b2c3d4  Jane M. Smith     born 1932        Cork, Ireland
  Differs:  name.given (middle initial absent), birth.date (partial vs full)
```

#### `ft merge <uuid-keep> <uuid-discard>`

Merges two person records into one, keeping `<uuid-keep>` as the surviving record and deleting `<uuid-discard>`. Before merging:
1. Displays a field-by-field diff of both records
2. For each conflicting field, prompts the user to choose which value to keep (or enter a new value)
3. Updates all relation files that reference `<uuid-discard>` to point to `<uuid-keep>`
4. Appends a note to the surviving record indicating the merge and the discarded UUID
5. Deletes `<uuid-discard>.json`

The operation is staged as a Git working-tree change and not committed automatically, allowing review before `git commit`.

#### `ft not-duplicate <uuid-a> <uuid-b>`

Marks two persons as confirmed distinct, suppressing them from future `ft find-duplicates` output. The pair is appended to `.familytree/familytree.json`. An optional `--note` flag records the reason.

```
ft not-duplicate 550e8400 a1b2c3d4 --note "Same name, different generation"
```

The pair is appended to the `not_duplicates` array in `.familytree/familytree.json`. Pairs are unordered — checked regardless of which UUID appears first. The entry is created automatically if it does not exist.

## Tree Import

Importing an external `.familytree/` dataset into an existing one can produce four distinct situations that must each be handled:

| Case | UUID match | Data match | Action |
|------|------------|------------|--------|
| 1    | No         | —          | Import freely — no conflict |
| 2    | Yes        | Yes        | Skip — already present, idempotent |
| 3    | Yes        | No         | Conflict — same stable identity, data diverged |
| 4    | No         | Potentially same person | Flag as possible duplicate for manual review |

Content equality (cases 2 and 3) is determined by computing `sha256` of each file's content at import time. Hashes are not stored — they are computed on the fly for comparison only.

### Case 1 — No overlap

Files whose UUIDs do not exist in the target tree are copied directly into `persons/` and `relations/`.

### Case 2 — Identical UUID and data

The UUID exists in the target tree and the SHA-256 of both files is identical. No action is taken. This is idempotent and expected when importing from a shared source that has not changed.

### Case 3 — Same UUID, different data

The UUID exists in the target tree but the SHA-256 differs — the same person or relation has been edited independently in each tree. This is treated as a conflict:

1. Both versions are shown side by side with a field-level diff
2. The user chooses which value to keep for each conflicting field, or enters a new value
3. The resolved record is written and staged for commit

### Case 4 — Distinct UUID, possibly same person

Detected by `ft find-duplicates` after the import completes. The user then resolves each flagged pair with either `ft merge` or `ft not-duplicate`.

### `ft import-tree <path>`

Imports a `.familytree/` directory from `<path>` into the current tree, handling all four cases above:

1. Scans all person and relation files in the source
2. For each file: computes SHA-256 of source and target content, then skips (case 2), copies (case 1), or queues for conflict resolution (case 3)
3. Resolves conflicts interactively before writing
4. Runs `ft find-duplicates` automatically after import and reports case 4 pairs
5. Stages all changes for review before `git commit`
