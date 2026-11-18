"""The audit file: the saved pairings plus who has been texted.

It is JSON and is rewritten (atomically) after every send, so a crash or a
failed text never loses track of who already got their match. Rerunning
--send only texts people who haven't been sent theirs yet.
"""

import datetime
import json
import os
import re
import tempfile
from dataclasses import asdict, dataclass, field

PENDING, SENT, FAILED = "pending", "sent", "failed"


def _now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


@dataclass
class Entry:
    gifter: str
    giftee: str
    status: str = PENDING
    phone: str | None = None      # number the text went to
    text_id: str | None = None    # Textbelt id, used by --status
    delivery: str | None = None   # last delivery status reported by Textbelt
    error: str | None = None
    sent_at: str | None = None

    def mark_sent(self, phone, text_id):
        self.status, self.phone, self.text_id = SENT, phone, text_id
        self.error, self.delivery, self.sent_at = None, None, _now()

    def mark_failed(self, phone, error):
        self.status, self.phone, self.error = FAILED, phone, str(error)


@dataclass
class Audit:
    path: str
    entries: list[Entry]
    note: str | None = None
    created: str = field(default_factory=_now)

    @classmethod
    def new(cls, path, pairs, note=None):
        entries = [Entry(g.name, r.name) for g, r in pairs.items()]
        return cls(path, entries, note)

    @classmethod
    def load(cls, path):
        with open(path) as f:
            data = json.load(f)
        entries = [Entry(**e) for e in data["entries"]]
        return cls(path, entries, data.get("note"), data.get("created", _now()))

    def save(self):
        data = {"created": self.created, "note": self.note,
                "entries": [asdict(e) for e in self.entries]}
        folder = os.path.dirname(os.path.abspath(self.path))
        fd, tmp = tempfile.mkstemp(dir=folder, prefix=".audit-")
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")
        os.replace(tmp, self.path)

    def find(self, name):
        for entry in self.entries:
            if entry.gifter.lower() == name.lower():
                return entry
        raise ValueError(f"{name} isn't in {self.path}")

    def unsent(self):
        return [e for e in self.entries if e.status != SENT]

    def pairs(self):
        return {(e.gifter.lower(), e.giftee.lower()) for e in self.entries}


def load_previous_pairs(path):
    """(gifter, giftee) name pairs from an audit file, new JSON or the old text format."""
    with open(path) as f:
        text = f.read()
    if text.lstrip().startswith("{"):
        return Audit.load(path).pairs()
    pairs = set()
    for line in text.splitlines():
        m = re.match(r"gifter:(.+?) giftee:(.+)$", line.strip())
        if m:
            pairs.add((m.group(1).lower(), m.group(2).lower()))
    return pairs
