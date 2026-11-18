import collections
import os
import random
import tempfile
import unittest
from unittest import mock

from dickson_secret_santa.santa import (
    NoPairingError, PairingRules, Person, build_message, generate_pairs,
    households, load_people, load_previous_pairs, normalize_phone,
)
from dickson_secret_santa.__main__ import main

HERE = os.path.dirname(__file__)
EXAMPLE = os.path.join(HERE, "..", "participants.example.csv")


class PairingTests(unittest.TestCase):
    def setUp(self):
        self.people = load_people(EXAMPLE)

    def check(self, pairs, rules):
        self.assertEqual(set(pairs), set(self.people))           # everyone gives
        self.assertEqual(set(pairs.values()), set(self.people))  # everyone receives
        self.assertTrue(rules.valid(pairs))

    def test_family_list_always_pairs_everyone(self):
        rules = PairingRules()
        rng = random.Random(1)
        for _ in range(2000):
            pairs = generate_pairs(self.people, rules, rng)
            self.check(pairs, rules)
            for gifter, giftee in pairs.items():
                self.assertNotEqual(gifter.family, giftee.family)
                self.assertIsNot(pairs[giftee], gifter)

    def test_matches_are_spread_out(self):
        rng = random.Random(2)
        rob = next(p for p in self.people if p.name == "Rob")
        counts = collections.Counter(
            generate_pairs(self.people, PairingRules(), rng)[rob].name for _ in range(3000))
        # Rob can draw any of the 10 people outside his household.
        self.assertEqual(len(counts), 10)
        self.assertGreater(min(counts.values()), 150)

    def test_avoid_previous_year(self):
        rng = random.Random(3)
        last_year = generate_pairs(self.people, PairingRules(), rng)
        avoid = {(g.name, r.name) for g, r in last_year.items()}
        rules = PairingRules(avoid_pairs=avoid)
        for _ in range(200):
            pairs = generate_pairs(self.people, rules, rng)
            self.check(pairs, rules)
            for g, r in pairs.items():
                self.assertIsNot(last_year[g], r)

    def test_impossible_household_split(self):
        people = [Person(n, "Big") for n in "ABCD"] + [Person("E", "Small")]
        with self.assertRaises(NoPairingError):
            generate_pairs(people, PairingRules(), random.Random(0), attempts=50)

    def test_exhaustive_fallback_finds_solution(self):
        rules = PairingRules()
        pairs = generate_pairs(self.people, rules, random.Random(4), attempts=0)
        self.check(pairs, rules)


class ParsingTests(unittest.TestCase):
    def test_phone_formats(self):
        self.assertEqual(normalize_phone("(206) 555-0101"), "+12065550101")
        self.assertEqual(normalize_phone("1-206-555-0101"), "+12065550101")
        self.assertEqual(normalize_phone("+44 7700 900123"), "+447700900123")
        self.assertIsNone(normalize_phone(""))
        with self.assertRaises(ValueError):
            normalize_phone("555-0101")

    def test_duplicate_names_rejected(self):
        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as f:
            f.write("Tim, A\nTim, B\n")
        self.addCleanup(os.remove, f.name)
        with self.assertRaises(ValueError):
            load_people(f.name)

    def test_message_lists_housemates(self):
        people = load_people(EXAMPLE)
        by_name = {p.name: p for p in people}
        msg = build_message(by_name["Rob"], by_name["Kyle"], households(people), "Liam")
        self.assertIn("Rob, your match is Kyle!", msg)
        self.assertIn("Kyoung-Hi and Mina", msg)
        solo = build_message(by_name["Kyle"], by_name["Rob"], households(people), "Liam")
        self.assertNotIn("household", solo)


class CliTests(unittest.TestCase):
    def test_dry_run_send_and_resend(self):
        with tempfile.TemporaryDirectory() as d:
            audit = os.path.join(d, "x.audit")
            self.assertEqual(main([EXAMPLE, "--send", "--dry-run", "--audit", audit]), 0)
            self.assertFalse(os.path.exists(audit))  # dry runs don't save pairings

            with open(audit, "w") as f:
                f.write("gifter:Liam giftee:Carol\n")
            self.assertEqual(
                main([EXAMPLE, "--resend", "liam", "--dry-run", "--audit", audit]), 0)
            self.assertEqual(load_previous_pairs(audit), {("liam", "carol")})

    def test_test_email_never_saves_pairings(self):
        with tempfile.TemporaryDirectory() as d:
            audit = os.path.join(d, "x.audit")
            with mock.patch("smtplib.SMTP") as smtp_cls, mock.patch.dict(
                    os.environ, {"SMTP_USER": "me@gmail.com", "SMTP_PASSWORD": "pw"}):
                self.assertEqual(
                    main([EXAMPLE, "--test-email", "me+test@gmail.com", "--audit", audit]), 0)
            self.assertEqual(smtp_cls.return_value.send_message.call_count, 13)
            self.assertFalse(os.path.exists(audit))

    def test_check_only(self):
        self.assertEqual(main([EXAMPLE]), 0)


if __name__ == "__main__":
    unittest.main()
