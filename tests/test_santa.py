import collections
import os
import random
import tempfile
import unittest

from dickson_secret_santa.santa import (
    MAX_SEGMENTS, NoPairingError, PairingRules, Person, build_message,
    check_message_length, generate_pairs, households, load_people, normalize_phone,
    sms_segments,
)

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



class MessageTests(unittest.TestCase):
    def setUp(self):
        self.people = load_people(EXAMPLE)
        self.by_name = {p.name: p for p in self.people}
        self.households = households(self.people)

    def test_message_lists_housemates(self):
        msg = build_message(self.by_name["Rob"], self.by_name["Kyle"], self.households)
        self.assertEqual(
            msg, "🎅 Secret Santa: Rob, your match is Kyle!\nYou can plan with Kyoung-Hi and Mina.")
        solo = build_message(self.by_name["Kyle"], self.by_name["Rob"], self.households,
                             "Budget is $50.")
        self.assertEqual(solo, "🎅 Secret Santa: Kyle, your match is Rob!\nBudget is $50.")

    def test_segment_counting(self):
        self.assertEqual(sms_segments("a" * 160), 1)
        self.assertEqual(sms_segments("a" * 161), 2)
        self.assertEqual(sms_segments("a" * 159 + "€"), 2)  # € takes 2 GSM slots
        self.assertEqual(sms_segments("🎅" + "a" * 68), 1)   # emoji = 2 UCS-2 units
        self.assertEqual(sms_segments("🎅" + "a" * 69), 2)
        self.assertEqual(sms_segments("🎅" + "a" * 132), 2)
        self.assertEqual(sms_segments("🎅" + "a" * 133), 3)

    def test_every_possible_family_text_fits(self):
        rules = PairingRules()
        self.assertLessEqual(
            check_message_length(self.people, rules, self.households,
                                 "Budget is about $50. Gifts by Dec 24."), MAX_SEGMENTS)

    def test_long_note_rejected(self):
        with self.assertRaisesRegex(ValueError, "shorten --note"):
            check_message_length(self.people, PairingRules(), self.households, "x" * 80)


if __name__ == "__main__":
    unittest.main()
