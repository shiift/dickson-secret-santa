"""End-to-end tests of the command line, with a fake Textbelt."""

import contextlib
import io
import json
import os
import shutil
import tempfile
import unittest
from unittest import mock

from dickson_secret_santa.__main__ import main
from dickson_secret_santa.audit import Audit, load_previous_pairs
from dickson_secret_santa.senders import SendError, Sender

HERE = os.path.dirname(__file__)
EXAMPLE = os.path.join(HERE, "..", "participants.example.csv")


class FakeTextbelt(Sender):
    """Stands in for TextbeltSender. Class-level state so tests can inspect it."""
    sent = []          # (phone, message)
    failing = set()    # phones that fail to send
    quota = 1000
    statuses = {}      # text_id -> delivery status
    closed = 0

    def __init__(self, key):
        pass

    @classmethod
    def reset(cls):
        cls.sent, cls.failing, cls.quota, cls.statuses, cls.closed = [], set(), 1000, {}, 0

    def send(self, phone, message):
        if phone in self.failing:
            raise SendError("carrier rejected")
        FakeTextbelt.sent.append((phone, message))
        return f"id-{len(FakeTextbelt.sent)}"

    def quota_remaining(self):
        return self.quota

    def delivery_status(self, message_id):
        return self.statuses.get(message_id, "SENDING")

    def close(self):
        FakeTextbelt.closed += 1


class CliTestCase(unittest.TestCase):
    def setUp(self):
        FakeTextbelt.reset()
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir)
        self.csv = os.path.join(self.dir, "participants.csv")
        shutil.copy(EXAMPLE, self.csv)
        self.audit = os.path.join(self.dir, "test.audit.json")
        patcher = mock.patch("dickson_secret_santa.__main__.TextbeltSender", FakeTextbelt)
        patcher.start()
        self.addCleanup(patcher.stop)

    def run_cli(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main([self.csv, "--audit", self.audit, *args])
        return code, out.getvalue() + err.getvalue()

    def phone_of(self, name):
        with open(self.csv) as f:
            for line in f:
                if line.startswith(name + ","):
                    return "+" + line.rsplit("+", 1)[1].strip()

    def load(self):
        return Audit.load(self.audit)


class SendTests(CliTestCase):
    def test_send_texts_everyone_and_records_it(self):
        code, out = self.run_cli("--send", "--note", "Budget is $50.")
        self.assertEqual(code, 0, out)
        self.assertEqual(len(FakeTextbelt.sent), 13)
        self.assertEqual(FakeTextbelt.closed, 1)
        audit = self.load()
        self.assertEqual(audit.note, "Budget is $50.")
        self.assertTrue(all(e.status == "sent" and e.text_id for e in audit.entries))
        self.assertTrue(all(m.endswith("Budget is $50.") for _, m in FakeTextbelt.sent))
        # Output never reveals who drew whom.
        for e in audit.entries:
            self.assertNotIn(f"match is {e.giftee}", out)

    def test_rerun_after_partial_failure_only_retries_failures(self):
        FakeTextbelt.failing = {self.phone_of("Carol"), self.phone_of("Kyle")}
        code, out = self.run_cli("--send", "--note", "Budget is $50.")
        self.assertEqual(code, 1)
        self.assertIn("Rerun the same command", out)
        first = self.load()
        self.assertEqual(sorted(e.gifter for e in first.unsent()), ["Carol", "Kyle"])
        self.assertEqual(first.find("Carol").error, "carrier rejected")
        self.assertEqual(len(FakeTextbelt.sent), 11)

        FakeTextbelt.failing = set()
        code, out = self.run_cli("--send")  # note is reused from the audit
        self.assertEqual(code, 0, out)
        self.assertEqual(len(FakeTextbelt.sent), 13)
        self.assertEqual([p for p, _ in FakeTextbelt.sent[11:]],
                         [e.phone for e in first.entries if e.gifter in ("Carol", "Kyle")])
        self.assertTrue(FakeTextbelt.sent[-1][1].endswith("Budget is $50."))
        second = self.load()
        self.assertEqual({(e.gifter, e.giftee) for e in first.entries},
                         {(e.gifter, e.giftee) for e in second.entries})  # same draw

        code, out = self.run_cli("--send")  # third run: nothing left to do
        self.assertEqual(code, 0)
        self.assertIn("Everyone has been sent", out)
        self.assertEqual(len(FakeTextbelt.sent), 13)

    def test_resume_rejects_a_different_note(self):
        FakeTextbelt.failing = {self.phone_of("Carol")}
        self.run_cli("--send", "--note", "Budget is $50.")
        code, out = self.run_cli("--send", "--note", "Budget is $25.")
        self.assertEqual(code, 1)
        self.assertIn("Rerun without --note", out)

    def test_resume_rejects_changed_participants(self):
        FakeTextbelt.failing = {self.phone_of("Carol")}
        self.run_cli("--send")
        with open(self.csv, "a") as f:
            f.write("Kim, Nana, +12065550199\n")
        code, out = self.run_cli("--send")
        self.assertEqual(code, 1)
        self.assertIn("participant list changed", out)

    def test_force_redraws(self):
        self.run_cli("--send")
        first_created = self.load().created
        code, out = self.run_cli("--send", "--force")
        self.assertEqual(code, 0, out)
        self.assertEqual(len(FakeTextbelt.sent), 26)
        self.assertIn("--force: replacing", out)
        self.assertGreaterEqual(self.load().created, first_created)

    def test_quota_checked_before_anything_is_sent_or_saved(self):
        FakeTextbelt.quota = 5
        code, out = self.run_cli("--send")
        self.assertEqual(code, 1)
        self.assertIn("credits left", out)
        self.assertEqual(FakeTextbelt.sent, [])
        self.assertFalse(os.path.exists(self.audit))

    def test_dry_run_sends_and_saves_nothing(self):
        code, out = self.run_cli("--send", "--dry-run")
        self.assertEqual(code, 0, out)
        self.assertEqual(FakeTextbelt.sent, [])
        self.assertFalse(os.path.exists(self.audit))
        self.assertEqual(out.count("Secret Santa:"), 13)

    def test_missing_phone_blocks_send(self):
        with open(self.csv, "a") as f:
            f.write("Kim, Nana\n")
        code, out = self.run_cli("--send")
        self.assertEqual(code, 1)
        self.assertIn("Add phone numbers for Kim", out)


class ResendAndStatusTests(CliTestCase):
    def test_resend_uses_saved_pairing_and_note(self):
        self.run_cli("--send", "--note", "Budget is $50.")
        carol = self.load().find("Carol")
        code, out = self.run_cli("--resend", "carol")
        self.assertEqual(code, 0, out)
        phone, message = FakeTextbelt.sent[-1]
        self.assertEqual(phone, self.phone_of("Carol"))
        self.assertIn(f"Carol, your match is {carol.giftee}!", message)
        self.assertTrue(message.endswith("Budget is $50."))
        self.assertEqual(self.load().find("Carol").text_id, "id-14")

    def test_resend_failure_is_recorded(self):
        self.run_cli("--send")
        FakeTextbelt.failing = {self.phone_of("Carol")}
        code, out = self.run_cli("--resend", "Carol")
        self.assertEqual(code, 1)
        self.assertEqual(self.load().find("Carol").status, "failed")

    def test_status_polls_and_saves_delivery(self):
        FakeTextbelt.failing = {self.phone_of("Kyle")}
        self.run_cli("--send")
        audit = self.load()
        FakeTextbelt.statuses = {e.text_id: "DELIVERED" for e in audit.entries
                                 if e.text_id and e.gifter != "Carol"}
        code, out = self.run_cli("--status")
        self.assertEqual(code, 1)
        self.assertIn("2 not confirmed delivered", out)
        self.assertRegex(out, r"Carol\s+SENDING")
        self.assertRegex(out, r"Kyle\s+FAILED to send: carrier rejected")
        self.assertEqual(self.load().find("Rob").delivery, "DELIVERED")

        # Delivered texts aren't polled again; the rest are.
        FakeTextbelt.failing = set()
        self.run_cli("--send")
        FakeTextbelt.statuses = {e.text_id: "DELIVERED" for e in self.load().entries}
        with mock.patch.object(FakeTextbelt, "delivery_status",
                               autospec=True, side_effect=lambda s, i: "DELIVERED") as poll:
            code, out = self.run_cli("--status")
        self.assertEqual(code, 0, out)
        self.assertIn("All 13 texts delivered", out)
        self.assertEqual(poll.call_count, 2)

    def test_reveal(self):
        self.run_cli("--send")
        code, out = self.run_cli("--reveal")
        self.assertEqual(code, 0)
        self.assertEqual(out.count("->"), 13)


class OtherModeTests(CliTestCase):
    def test_check_only_reports_progress(self):
        code, out = self.run_cli()
        self.assertEqual(code, 0)
        self.assertIn("Run with --send", out)
        FakeTextbelt.failing = {self.phone_of("Carol")}
        self.run_cli("--send")
        code, out = self.run_cli()
        self.assertIn("12 of 13 texts sent. Run --send to finish", out)
        FakeTextbelt.failing = set()
        self.run_cli("--send")
        code, out = self.run_cli()
        self.assertIn("All 13 texts sent. Run --status", out)

    def test_test_email_never_saves_pairings(self):
        with mock.patch("smtplib.SMTP") as smtp_cls, mock.patch.dict(
                os.environ, {"SMTP_USER": "me@gmail.com", "SMTP_PASSWORD": "pw"}):
            code, out = self.run_cli("--test-email", "me+test@gmail.com")
        self.assertEqual(code, 0, out)
        self.assertEqual(smtp_cls.return_value.send_message.call_count, 13)
        smtp_cls.return_value.quit.assert_called_once()
        self.assertFalse(os.path.exists(self.audit))
        self.assertEqual(FakeTextbelt.sent, [])

    def test_avoid_reads_json_and_legacy_audits(self):
        self.run_cli("--send")
        new_pairs = load_previous_pairs(self.audit)
        self.assertEqual(len(new_pairs), 13)
        legacy = os.path.join(self.dir, "2019.audit")
        with open(legacy, "w") as f:
            f.write("gifter:Liam giftee:Carol\ngifter:Carol giftee:Tim\n")
        self.assertEqual(load_previous_pairs(legacy), {("liam", "carol"), ("carol", "tim")})
        code, out = self.run_cli("--avoid", self.audit, "--avoid", legacy)
        self.assertEqual(code, 0, out)
        expected = len(new_pairs | load_previous_pairs(legacy))  # draws can overlap
        self.assertIn(f"Avoiding {expected} pairings", out)

    def test_audit_file_is_valid_json_after_each_send(self):
        seen = []
        real_send = FakeTextbelt.send

        def spy(self_, phone, message):
            with open(self.audit) as f:
                seen.append(json.load(f))  # parses mid-run
            return real_send(self_, phone, message)

        with mock.patch.object(FakeTextbelt, "send", spy):
            self.run_cli("--send")
        sent_counts = [sum(e["status"] == "sent" for e in d["entries"]) for d in seen]
        self.assertEqual(sent_counts, list(range(13)))


if __name__ == "__main__":
    unittest.main()
