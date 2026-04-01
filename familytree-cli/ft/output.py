"""Formatting helpers for CLI output."""

from __future__ import annotations

import json


def full_name(name: dict | None) -> str:
    """Return a formatted full name from a name dict."""
    if not name:
        return "(unknown)"
    parts = []
    if name.get("given"):
        parts.append(name["given"])
    if name.get("surname_prefix"):
        parts.append(name["surname_prefix"])
    if name.get("surname"):
        parts.append(name["surname"])
    return " ".join(parts) if parts else "(unknown)"


def year_from(ev: dict | None) -> str:
    """Return the first 4 characters of ev['date'], or empty string."""
    if not ev:
        return ""
    date = ev.get("date", "")
    return date[:4] if date else ""


def person_summary(data: dict) -> str:
    """Return a one-line summary: [uuid8]  Full Name  (sex)  b.YYYY d.YYYY"""
    uid8 = data.get("uuid", "")[:8]
    name = full_name(data.get("name"))
    sex = data.get("sex", "")
    sex_str = f"({sex})" if sex else ""
    by = year_from(data.get("birth"))
    dy = year_from(data.get("death"))
    birth_str = f"b.{by}" if by else ""
    death_str = f"d.{dy}" if dy else ""
    parts = [f"[{uid8}]", name]
    if sex_str:
        parts.append(sex_str)
    if birth_str:
        parts.append(birth_str)
    if death_str:
        parts.append(death_str)
    return "  ".join(parts)


def person_detail(data: dict) -> str:
    """Return a multiline human-readable description of a person."""
    lines: list[str] = []
    uuid_str = data.get("uuid", "")
    lines.append(f"UUID:    {uuid_str}")
    lines.append(f"Name:    {full_name(data.get('name'))}")

    names = data.get("names", [])
    for alt in names:
        lines.append(f"  Alt:   {full_name(alt)} [{alt.get('type', '')}]")

    sex = data.get("sex", "")
    if sex:
        lines.append(f"Sex:     {sex}")
    gender = data.get("gender", "")
    if gender:
        lines.append(f"Gender:  {gender}")
    title = data.get("title", "")
    if title:
        lines.append(f"Title:   {title}")

    birth = data.get("birth")
    if birth:
        b_date = birth.get("date", "")
        b_place = birth.get("place", "")
        b_parts = [p for p in [b_date, b_place] if p]
        lines.append(f"Birth:   {', '.join(b_parts)}")

    death = data.get("death")
    if death:
        d_date = death.get("date", "")
        d_place = death.get("place", "")
        d_parts = [p for p in [d_date, d_place] if p]
        lines.append(f"Death:   {', '.join(d_parts)}")

    burial = data.get("burial")
    if burial:
        bu_date = burial.get("date", "")
        bu_place = burial.get("place", "")
        bu_parts = [p for p in [bu_date, bu_place] if p]
        lines.append(f"Burial:  {', '.join(bu_parts)}")

    occupations = data.get("occupation", [])
    if occupations:
        lines.append(f"Occup:   {', '.join(occupations)}")

    nationality = data.get("nationality", "")
    if nationality:
        lines.append(f"Nation:  {nationality}")

    biography = data.get("biography", "")
    if biography:
        lines.append(f"Bio:     {biography[:120]}{'...' if len(biography) > 120 else ''}")

    notes = data.get("notes", [])
    for note in notes:
        lines.append(f"Note:    {note}")

    created = data.get("created", "")
    changed = data.get("changed", "")
    if created:
        lines.append(f"Created: {created}")
    if changed:
        lines.append(f"Changed: {changed}")

    return "\n".join(lines)


def index_person_summary(entry: dict) -> str:
    """Format a persons-index entry for list output."""
    uid8 = entry.get("uuid", "")[:8]
    name = entry.get("name") or {}
    display_name = full_name(name) if name else "(unknown)"
    sex = entry.get("sex", "")
    sex_str = f"({sex})" if sex else ""
    by = year_from(entry.get("birth"))
    dy = year_from(entry.get("death"))
    birth_str = f"b.{by}" if by else ""
    death_str = f"d.{dy}" if dy else ""
    parts = [f"[{uid8}]", display_name]
    if sex_str:
        parts.append(sex_str)
    if birth_str:
        parts.append(birth_str)
    if death_str:
        parts.append(death_str)
    return "  ".join(parts)


def relation_summary(data: dict) -> str:
    """Return a one-line summary of a relation record."""
    uid8 = data.get("uuid", "")[:8]
    rel_type = data.get("type", "?")
    details = ""
    if rel_type == "filiation":
        details = f"parent={data.get('parent', '')[:8]}  child={data.get('child', '')[:8]}"
    elif rel_type == "partner":
        persons = data.get("persons", [])
        details = "  ".join(p[:8] for p in persons)
        kind = data.get("kind", "")
        if kind:
            details += f"  [{kind}]"
    elif rel_type == "association":
        from_uuid = data.get("from", "")[:8]
        to_uuid = data.get("to", "")[:8]
        relation = data.get("relation", "")
        details = f"from={from_uuid}  to={to_uuid}  [{relation}]"
    return f"[{uid8}]  {rel_type}  {details}"


def as_json(data) -> str:
    """Return data as indented JSON string."""
    return json.dumps(data, indent=2, ensure_ascii=False)
