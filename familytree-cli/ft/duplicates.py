"""Duplicate person detection."""

from __future__ import annotations

from difflib import SequenceMatcher


def _sim(a: str, b: str) -> float:
    """Return similarity ratio between two strings (0.0–1.0)."""
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def _year(ev: dict | None) -> str | None:
    """Extract a 4-digit year string from an event dict, or None."""
    if not ev:
        return None
    date = ev.get("date", "")
    if date and len(date) >= 4 and date[:4].isdigit():
        return date[:4]
    return None


def score_pair(a: dict, b: dict) -> int:
    """Score two persons-index entries for similarity (0–100).

    Weights:
      - surname   30 %
      - given     20 %
      - birth yr  30 %
      - death yr  20 %

    Year components are skipped (weight redistributed proportionally) when
    dates are absent in both entries.
    """
    a_name = a.get("name") or {}
    b_name = b.get("name") or {}

    given_sim = _sim(a_name.get("given", ""), b_name.get("given", ""))
    surname_sim = _sim(a_name.get("surname", ""), b_name.get("surname", ""))

    a_birth_yr = _year(a.get("birth"))
    b_birth_yr = _year(b.get("birth"))
    a_death_yr = _year(a.get("death"))
    b_death_yr = _year(b.get("death"))

    has_birth = a_birth_yr is not None or b_birth_yr is not None
    has_death = a_death_yr is not None or b_death_yr is not None

    # Build weighted components dynamically
    components: list[tuple[float, float]] = []  # (weight, score)
    components.append((30.0, surname_sim * 100))
    components.append((20.0, given_sim * 100))

    if has_birth:
        birth_score = 100.0 if (a_birth_yr and b_birth_yr and a_birth_yr == b_birth_yr) else 0.0
        components.append((30.0, birth_score))
    if has_death:
        death_score = 100.0 if (a_death_yr and b_death_yr and a_death_yr == b_death_yr) else 0.0
        components.append((20.0, death_score))

    total_weight = sum(w for w, _ in components)
    if total_weight == 0:
        return 0
    raw = sum(w * s for w, s in components) / total_weight
    return round(raw)


def find_duplicates(
    persons: list[dict],
    not_dup_pairs: list[dict],
    threshold: int = 80,
) -> list[dict]:
    """Return pairs of persons that score >= threshold, sorted descending by score.

    *not_dup_pairs* is the ``not_duplicates`` list from the control file.
    Each entry has ``{"persons": [uuid_a, uuid_b]}``.

    Returns list of ``{"person_a": entry, "person_b": entry, "score": int}``.
    """
    # Build a set of suppressed pairs (order-insensitive)
    suppressed: set[frozenset[str]] = set()
    for pair in not_dup_pairs:
        uuids = pair.get("persons", [])
        if len(uuids) == 2:
            suppressed.add(frozenset(uuids))

    results: list[dict] = []
    n = len(persons)
    for i in range(n):
        for j in range(i + 1, n):
            a = persons[i]
            b = persons[j]
            key = frozenset([a["uuid"], b["uuid"]])
            if key in suppressed:
                continue
            score = score_pair(a, b)
            if score >= threshold:
                results.append({"person_a": a, "person_b": b, "score": score})

    results.sort(key=lambda x: x["score"], reverse=True)
    return results
