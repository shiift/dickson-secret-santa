"""Loading participants and generating secret santa pairings."""

import csv
import random
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Person:
    name: str
    family: str
    phone: str | None = None

    def __str__(self):
        return self.name


def normalize_phone(raw):
    """Return an E.164 phone number (US default) or None if blank."""
    if raw is None or not raw.strip():
        return None
    raw = raw.strip()
    digits = re.sub(r"\D", "", raw)
    if raw.startswith("+") and 8 <= len(digits) <= 15:
        return "+" + digits
    if len(digits) == 10:
        return "+1" + digits
    if len(digits) == 11 and digits.startswith("1"):
        return "+" + digits
    raise ValueError(f"Can't understand phone number {raw!r}; use e.g. +12065551234")


def load_people(filename):
    """Read `name, family, phone` rows. Blank lines and lines starting with # are skipped."""
    people = []
    with open(filename, newline="") as people_file:
        reader = csv.reader(people_file, skipinitialspace=True)
        for line_no, row in enumerate(reader, start=1):
            row = [cell.strip() for cell in row]
            if not row or not any(row) or row[0].startswith("#"):
                continue
            if len(row) not in (2, 3):
                raise ValueError(
                    f"line {line_no}: expected 'name, family, phone' but got {row}")
            name, family = row[0], row[1]
            if not name or not family:
                raise ValueError(f"line {line_no}: name and family are required")
            phone = normalize_phone(row[2]) if len(row) == 3 else None
            people.append(Person(name, family, phone))

    names = [p.name.lower() for p in people]
    dupes = sorted({n for n in names if names.count(n) > 1})
    if dupes:
        raise ValueError(f"Duplicate names in participant list: {', '.join(dupes)}")
    if len(people) < 2:
        raise ValueError("Need at least two people for a gift exchange")
    return people


def households(people):
    groups = {}
    for person in people:
        groups.setdefault(person.family, []).append(person)
    return groups


def load_previous_pairs(audit_file):
    """Read (gifter, giftee) name pairs from a previous year's audit file."""
    pairs = set()
    with open(audit_file) as f:
        for line in f:
            m = re.match(r"gifter:(.+?) giftee:(.+)$", line.strip())
            if m:
                pairs.add((m.group(1).lower(), m.group(2).lower()))
    return pairs


class PairingRules:
    def __init__(self, allow_family=False, allow_reversals=False, avoid_pairs=()):
        self.allow_family = allow_family
        self.allow_reversals = allow_reversals
        self.avoid_pairs = {(a.lower(), b.lower()) for a, b in avoid_pairs}

    def allowed(self, gifter, giftee):
        if gifter == giftee:
            return False
        if not self.allow_family and gifter.family == giftee.family:
            return False
        if (gifter.name.lower(), giftee.name.lower()) in self.avoid_pairs:
            return False
        return True

    def valid(self, assignment):
        for gifter, giftee in assignment.items():
            if not self.allowed(gifter, giftee):
                return False
            if not self.allow_reversals and assignment.get(giftee) == gifter:
                return False
        return True


class NoPairingError(Exception):
    pass


def generate_pairs(people, rules, rng=None, attempts=200_000):
    """Return {gifter: giftee} covering everyone exactly once.

    Uses rejection sampling: shuffle a full assignment and keep it only if it
    satisfies every rule. Every valid pairing is equally likely, so nobody's
    match depends on the order of the input file. If sampling can't find one,
    an exhaustive search either finds the rare solution or proves none exists.
    """
    rng = rng or random.SystemRandom()
    giftees = list(people)
    for _ in range(attempts):
        rng.shuffle(giftees)
        assignment = dict(zip(people, giftees))
        if rules.valid(assignment):
            return assignment

    result = _exhaustive_search(people, rules, rng)
    if result is None:
        raise NoPairingError(
            "No valid pairing exists with these rules. Usually one household "
            "is more than half the group, or the avoid list is too restrictive.")
    return result


def _exhaustive_search(people, rules, rng):
    order = list(people)
    rng.shuffle(order)
    assignment, taken = {}, set()

    def solve(i):
        if i == len(order):
            return True
        gifter = order[i]
        candidates = [p for p in people if p not in taken and rules.allowed(gifter, p)]
        rng.shuffle(candidates)
        for giftee in candidates:
            if not rules.allow_reversals and assignment.get(giftee) == gifter:
                continue
            assignment[gifter] = giftee
            taken.add(giftee)
            if solve(i + 1):
                return True
            del assignment[gifter]
            taken.discard(giftee)
        return False

    return dict(assignment) if solve(0) else None


def build_message(gifter, giftee, people_by_household, organizer, note=None):
    housemates = [p.name for p in people_by_household.get(gifter.family, []) if p != gifter]
    parts = [
        "🎅❄️ Secret Santa ❄️🎅",
        f"{gifter.name}, your match is {giftee.name}!",
    ]
    if housemates:
        parts.append(
            "You won't be matched with anyone in your household, so feel free "
            f"to plan gifts with {_join_names(housemates)}.")
    if note:
        parts.append(note)
    parts.append(f"Reach out to {organizer} with any questions.")
    return "\n\n".join(parts)


def _join_names(names):
    if len(names) <= 2:
        return " and ".join(names)
    return ", ".join(names[:-1]) + ", and " + names[-1]
