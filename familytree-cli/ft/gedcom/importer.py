"""GEDCOM 5.5.1 importer."""

from __future__ import annotations

import re
import uuid
from pathlib import Path


# ---------------------------------------------------------------------------
# Date parsing
# ---------------------------------------------------------------------------

_MONTH_MAP = {
    "JAN": "01", "FEB": "02", "MAR": "03", "APR": "04",
    "MAY": "05", "JUN": "06", "JUL": "07", "AUG": "08",
    "SEP": "09", "OCT": "10", "NOV": "11", "DEC": "12",
}

_QUALIFIER_WORDS = {"ABT", "BEF", "AFT", "EST", "CAL"}


def _parse_gedcom_date(raw: str) -> tuple[str, str | None, str | None]:
    """Parse a GEDCOM date string.

    Returns (iso_date, qualifier, date_to).
    iso_date may be partial (e.g. "1932" or "1932-04").
    """
    raw = raw.strip().upper()
    qualifier: str | None = None
    date_to: str | None = None
    date_str = raw

    # BET ... AND ...
    bet_match = re.match(r"BET\s+(.+?)\s+AND\s+(.+)", raw)
    if bet_match:
        qualifier = "BET"
        date_str = bet_match.group(1).strip()
        date_to = _simple_date(bet_match.group(2).strip())
    else:
        for qual in _QUALIFIER_WORDS:
            if raw.startswith(qual + " "):
                qualifier = qual
                date_str = raw[len(qual):].strip()
                break

    iso = _simple_date(date_str)
    return iso, qualifier, date_to


def _simple_date(raw: str) -> str:
    """Convert a simple GEDCOM date (no qualifier) to ISO format."""
    raw = raw.strip().upper()
    # DD MON YYYY
    m = re.match(r"(\d{1,2})\s+([A-Z]{3})\s+(\d{4})", raw)
    if m:
        day = m.group(1).zfill(2)
        mon = _MONTH_MAP.get(m.group(2), "00")
        year = m.group(3)
        return f"{year}-{mon}-{day}"
    # MON YYYY
    m = re.match(r"([A-Z]{3})\s+(\d{4})", raw)
    if m:
        mon = _MONTH_MAP.get(m.group(1), "00")
        year = m.group(2)
        return f"{year}-{mon}"
    # YYYY
    m = re.match(r"(\d{4})$", raw)
    if m:
        return m.group(1)
    return raw.lower()


# ---------------------------------------------------------------------------
# GEDCOM line parser
# ---------------------------------------------------------------------------

def _parse_lines(text: str) -> list[tuple[int, str, str]]:
    """Parse GEDCOM text into (level, tag_or_xref, value) tuples."""
    lines = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        parts = line.split(None, 2)
        if not parts:
            continue
        try:
            level = int(parts[0])
        except ValueError:
            continue
        tag = parts[1] if len(parts) > 1 else ""
        value = parts[2] if len(parts) > 2 else ""
        lines.append((level, tag, value))
    return lines


# ---------------------------------------------------------------------------
# Record extractor
# ---------------------------------------------------------------------------

def _extract_records(lines: list[tuple[int, str, str]]) -> list[dict]:
    """Split GEDCOM lines into top-level records."""
    records: list[dict] = []
    current: dict | None = None
    for level, tag, value in lines:
        if level == 0:
            if current is not None:
                records.append(current)
            current = {"tag": tag, "value": value, "children": []}
        elif current is not None:
            current["children"].append((level, tag, value))
    if current is not None:
        records.append(current)
    return records


def _children_at(children: list[tuple[int, str, str]], level: int, tag: str) -> list[str]:
    return [v for l, t, v in children if l == level and t == tag]


def _subtree(children: list[tuple[int, str, str]], start_level: int, start_tag: str):
    """Return children of first matching sub-record as a list of (level, tag, value)."""
    in_block = False
    result = []
    for l, t, v in children:
        if not in_block:
            if l == start_level and t == start_tag:
                in_block = True
        else:
            if l <= start_level:
                break
            result.append((l, t, v))
    return result


def _parse_life_event(children: list, level: int, tag: str) -> dict | None:
    """Extract a life event (BIRT/DEAT/BURI) from children."""
    sub = _subtree(children, level, tag)
    if not sub and not any(t == tag for _, t, _ in children):
        return None
    result: dict = {}
    for l, t, v in sub:
        if t == "DATE" and v:
            iso, qual, date_to = _parse_gedcom_date(v)
            result["date"] = iso
            if qual:
                result["date_qualifier"] = qual
            if date_to:
                result["date_to"] = date_to
        elif t == "PLAC" and v:
            result["place"] = v
    return result if result else {}


# ---------------------------------------------------------------------------
# Name parsing
# ---------------------------------------------------------------------------

def _parse_name(raw: str) -> dict:
    """Parse a GEDCOM NAME value like 'Given /Surname/'."""
    m = re.match(r"^(.*?)\s*/([^/]*)/\s*(.*)$", raw.strip())
    if m:
        given_parts = [m.group(1).strip(), m.group(3).strip()]
        given = " ".join(p for p in given_parts if p)
        surname = m.group(2).strip()
    else:
        given = raw.strip()
        surname = ""
    name: dict = {}
    if given:
        name["given"] = given
    if surname:
        name["surname"] = surname
    return name


# ---------------------------------------------------------------------------
# Main import function
# ---------------------------------------------------------------------------

def parse_gedcom(text: str) -> tuple[list[dict], list[dict]]:
    """Parse GEDCOM 5.5.1 text, return (persons, relations).

    Each person has a fresh UUID v4.
    """
    from ft.tree import FAMILYTREE_VERSION

    lines = _parse_lines(text)
    records = _extract_records(lines)

    # xref -> record lookup
    xref_to_record: dict[str, dict] = {}
    for rec in records:
        tag = rec["tag"]
        if tag.startswith("@") and tag.endswith("@"):
            xref_to_record[tag] = rec

    # First pass: assign UUIDs to all INDI records
    xref_to_uuid: dict[str, str] = {}
    for xref, rec in xref_to_record.items():
        if rec["value"] == "INDI":
            xref_to_uuid[xref] = str(uuid.uuid4())

    persons: list[dict] = []
    relations: list[dict] = []
    now_iso = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()

    # Build persons
    for xref, rec in xref_to_record.items():
        if rec["value"] != "INDI":
            continue
        children = rec["children"]
        person_uuid = xref_to_uuid[xref]

        # Name
        name_values = _children_at(children, 1, "NAME")
        name = _parse_name(name_values[0]) if name_values else {}

        # Sex
        sex_values = _children_at(children, 1, "SEX")
        sex = sex_values[0].upper() if sex_values else None
        if sex not in ("M", "F", "X"):
            sex = None

        # Life events
        birth = _parse_life_event(children, 1, "BIRT")
        death = _parse_life_event(children, 1, "DEAT")
        burial = _parse_life_event(children, 1, "BURI")

        data: dict = {
            "uuid": person_uuid,
            "familytree_version": FAMILYTREE_VERSION,
            "name": name,
            "created": now_iso,
            "changed": now_iso,
        }
        if sex:
            data["sex"] = sex
        if birth is not None:
            data["birth"] = birth
        if death is not None:
            data["death"] = death
        if burial is not None:
            data["burial"] = burial

        persons.append(data)

    # Build relations from FAM records
    fam_uuid_counter = [0]
    for xref, rec in xref_to_record.items():
        if rec["value"] != "FAM":
            continue
        children = rec["children"]

        husb_xrefs = _children_at(children, 1, "HUSB")
        wife_xrefs = _children_at(children, 1, "WIFE")
        chil_xrefs = _children_at(children, 1, "CHIL")

        husb_uuids = [xref_to_uuid[x] for x in husb_xrefs if x in xref_to_uuid]
        wife_uuids = [xref_to_uuid[x] for x in wife_xrefs if x in xref_to_uuid]
        chil_uuids = [xref_to_uuid[x] for x in chil_xrefs if x in xref_to_uuid]

        partner_uuids = husb_uuids + wife_uuids

        # Partner relation
        if len(partner_uuids) >= 2:
            partner_rel: dict = {
                "uuid": str(uuid.uuid4()),
                "familytree_version": FAMILYTREE_VERSION,
                "type": "partner",
                "persons": partner_uuids[:2],
                "created": now_iso,
                "changed": now_iso,
            }
            # Marriage event
            marr_sub = _subtree(children, 1, "MARR")
            if marr_sub or any(t == "MARR" for _, t, _ in children):
                partner_rel["kind"] = "marriage"
            relations.append(partner_rel)
        elif len(partner_uuids) == 1:
            # Single partner — still record as a partner if there are children
            pass

        # Filiation relations: one per parent-child combination
        for child_uuid in chil_uuids:
            for parent_uuid in partner_uuids:
                fil_rel: dict = {
                    "uuid": str(uuid.uuid4()),
                    "familytree_version": FAMILYTREE_VERSION,
                    "type": "filiation",
                    "parent": parent_uuid,
                    "child": child_uuid,
                    "created": now_iso,
                    "changed": now_iso,
                }
                relations.append(fil_rel)

    return persons, relations


def import_gedcom_file(path: Path) -> tuple[list[dict], list[dict]]:
    """Read a GEDCOM file and return (persons, relations)."""
    # Try common encodings
    for encoding in ("utf-8-sig", "latin-1", "utf-8"):
        try:
            text = path.read_text(encoding=encoding)
            return parse_gedcom(text)
        except UnicodeDecodeError:
            continue
    raise ValueError(f"Cannot decode GEDCOM file: {path}")
