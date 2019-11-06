import argparse
import sys
import random
import csv
import time

def main():
    arg_parser = argparse.ArgumentParser(description='Generates a list of people pairings for a secret santa exchange.')

    arg_parser.add_argument('file', help='path to the csv containing a list of people for the exchange')
    arg_parser.add_argument(
        '-f', '--no-family-match',
        help='do not match families for the exchange (uses surname)',
        dest='no_family_match',
        action='store_true'
    )
    arg_parser.add_argument(
        '-r', '--no-reversals',
        help='do not match people to each other',
        dest='no_reversal_match',
        action='store_true'
    )
    args = arg_parser.parse_args()

    people = load_people(args.file)
    random.shuffle(people, random.seed(time.time()))
    matches = calculate_gift_pairs(people, people.copy(), args.no_family_match, args.no_reversal_match)
    if not matches:
        print("no matches found")
        return
    for giftee, gifter in matches.items():
        print("{} gives to {}".format(gifter, giftee))

def calculate_gift_pairs(gifters, giftees, no_family_match, no_reversal_match, matches = {}, gifter_index = 0):
    if gifter_index >= len(gifters):
        return matches
    gifter = gifters[gifter_index]
    for giftee in giftees:
        if gifter is giftee:
            continue
        if giftee in matches:
            continue
        if no_family_match and gifter.family == giftee.family:
            continue
        if no_reversal_match and gifter in matches and matches[gifter] is giftee:
            continue
        matches[giftee] = gifter
        match = calculate_gift_pairs(gifters, giftees, no_family_match, no_reversal_match, matches, gifter_index + 1)
        if match:
            return matches
        del matches[giftee]
    return None

def load_people(filename):
    people = []
    with open(filename) as people_file:
        reader = csv.reader(people_file, skipinitialspace=True)
        for row in reader:
            if len(row) != 2:
                print("{} has incorrect format: expecting name, family name.".format(row), file=sys.stderr)
                continue

            name, family = row
            person = Person(name, family)

            people.append(person)
    return people

class Person():
    def __init__(self, name, family):
        self.name = name
        self.family = family

    def __str__(self):
        return self.name

    def __repr__(self):
        return "{name} ({family})".format(name=self.name, family=self.family)

if __name__ == '__main__':
    main()
    