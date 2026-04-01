"""GEDCOM 5.5.1 exporter."""

from __future__ import annotations

import re
from datetime import date as _date


_MONTH_ABBR = {
    "01": "JAN", "02": "FEB", "03": "MAR", "04": "APR",
    "05": "MAY", "06": "JUN", "07": "JUL", "08": "AUG",
    "09": "SEP", "10": "OCT", "11": "NOV", "12": "DEC",
}


def _iso_to_gedcom_date(iso: str | None, qualifier: str | None = None, date_to: str | None = None) -> str | None:
    """Convert an ISO date string to GEDCOM date format."""
    if not iso:
        return None
    iso = iso.strip()

    # Build base date string
    m_full = re.match(r"(\d{4})-(\d{2})-(\d{2})$", iso)
    m_mon = re.match(r"(\d{4})-(\d{2})$", iso)
    m_year = re.match(r"(\d{4})$", iso)

    if m_full:
        day = m_full.group(3).lstrip("0") or "1"
        mon = _MONTH_ABBR.get(m_full.group(2), "")
        year = m_full.group(1)
        base = f"{day} {mon} {year}" if mon else year
    elif m_mon:
        mon = _MONTH_ABBR.get(m_mon.group(2), "")
        year = m_mon.group(1)
        base = f"{mon} {year}" if mon else year
    elif m_year:
        base = m_year.group(1)
    else:
        return iso.upper()

    if qualifier == "BET" and date_to:
        date_to_ged = _iso_to_gedcom_date(date_to)
        return f"BET {base} AND {date_to_ged}"
    if qualifier:
        return f"{qualifier} {base}"
    return base


def _indi_xref(idx: int) -> str:
    return f"@I{idx:04d}@"


def _fam_xref(idx: int) -> str:
    return f"@F{idx:04d}@"


def _write_life_event(lines: list[str], tag: str, ev: dict | None) -> None:
    if ev is None:
        return
    lines.append(f"1 {tag}")
    date_str = _iso_to_gedcom_date(
        ev.get("date"), ev.get("date_qualifier"), ev.get("date_to")
    )
    if date_str:
        lines.append(f"2 DATE {date_str}")
    if ev.get("place"):
        lines.append(f"2 PLAC {ev['place']}")


def _format_name(name: dict | None) -> str:
    if not name:
        return "/Unknown/"
    given = name.get("given", "")
    surname = name.get("surname", "")
    prefix = name.get("surname_prefix", "")
    full_surname = " ".join(p for p in [prefix, surname] if p)
    if full_surname:
        return f"{given} /{full_surname}/".strip()
    return given or "/Unknown/"


def export_gedcom(persons: list[dict], relations: list[dict]) -> str:
    """Export persons and relations to a GEDCOM 5.5.1 string."""
    lines: list[str] = []

    # HEAD
    lines.append("0 HEAD")
    lines.append("1 GEDC")
    lines.append("2 VERS 5.5.1")
    lines.append("2 FORM LINEAGE-LINKED")
    lines.append("1 CHAR UTF-8")
    lines.append("1 SOUR familytree-cli")
    lines.append("2 VERS 0.1.0")

    # Assign INDI xrefs
    uuid_to_indi: dict[str, str] = {}
    for idx, person in enumerate(persons, start=1):
        xref = _indi_xref(idx)
        uuid_to_indi[person["uuid"]] = xref

    # INDI records
    for person in persons:
        xref = uuid_to_indi[person["uuid"]]
        lines.append(f"0 {xref} INDI")

        name = person.get("name") or {}
        lines.append(f"1 NAME {_format_name(name)}")
        if name.get("given"):
            lines.append(f"2 GIVN {name['given']}")
        if name.get("surname"):
            lines.append(f"2 SURN {name['surname']}")

        sex = person.get("sex", "")
        if sex:
            lines.append(f"1 SEX {sex}")

        _write_life_event(lines, "BIRT", person.get("birth"))
        _write_life_event(lines, "DEAT", person.get("death"))
        _write_life_event(lines, "BURI", person.get("burial"))

    # Identify partner relations and their children
    partner_relations = [r for r in relations if r.get("type") == "partner"]
    filiation_relations = [r for r in relations if r.get("type") == "filiation"]

    # Map each partner pair to a FAM
    fam_records: list[dict] = []
    for partner_rel in partner_relations:
        persons_list = partner_rel.get("persons", [])
        fam_records.append({
            "uuid": partner_rel["uuid"],
            "persons": persons_list,
            "kind": partner_rel.get("kind"),
            "children": [],
        })

    # For each filiation, find the matching FAM (partner relation containing both parents)
    # Group children by parent set
    # Build parent -> list of fam records mapping
    parent_to_fam: dict[str, list[dict]] = {}
    for fam in fam_records:
        for p_uuid in fam["persons"]:
            parent_to_fam.setdefault(p_uuid, []).append(fam)

    # Assign children to FAMs
    assigned_children: set[tuple[str, str]] = set()  # (child_uuid, fam_uuid)
    for fil in filiation_relations:
        parent_uuid = fil.get("parent")
        child_uuid = fil.get("child")
        if not parent_uuid or not child_uuid:
            continue
        # Find FAM that contains this parent
        fams_for_parent = parent_to_fam.get(parent_uuid, [])
        if fams_for_parent:
            # Prefer first (oldest) FAM for simplicity; dedup by child
            target_fam = fams_for_parent[0]
            key = (child_uuid, target_fam["uuid"])
            if key not in assigned_children:
                assigned_children.add(key)
                target_fam["children"].append(child_uuid)
        else:
            # No partner relation — create a synthetic FAM
            synthetic = {
                "uuid": f"synthetic-{parent_uuid}-{child_uuid}",
                "persons": [parent_uuid],
                "kind": None,
                "children": [child_uuid],
            }
            key = (child_uuid, synthetic["uuid"])
            if key not in assigned_children:
                assigned_children.add(key)
                fam_records.append(synthetic)
                parent_to_fam.setdefault(parent_uuid, []).append(synthetic)

    # FAM records
    for fam_idx, fam in enumerate(fam_records, start=1):
        fam_xref = _fam_xref(fam_idx)
        lines.append(f"0 {fam_xref} FAM")

        persons_in_fam = fam.get("persons", [])
        if len(persons_in_fam) >= 1:
            p1_xref = uuid_to_indi.get(persons_in_fam[0])
            if p1_xref:
                lines.append(f"1 HUSB {p1_xref}")
        if len(persons_in_fam) >= 2:
            p2_xref = uuid_to_indi.get(persons_in_fam[1])
            if p2_xref:
                lines.append(f"1 WIFE {p2_xref}")

        kind = fam.get("kind")
        if kind == "marriage":
            lines.append("1 MARR")

        for child_uuid in fam.get("children", []):
            child_xref = uuid_to_indi.get(child_uuid)
            if child_xref:
                lines.append(f"1 CHIL {child_xref}")

    lines.append("0 TRLR")
    return "\n".join(lines) + "\n"
