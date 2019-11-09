import argparse
import sys
import random
import csv
import time
import boto3

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
    arg_parser.add_argument(
        '-s', '--send',
        help='send text message to gifters about their giftee',
        dest='send',
        action='store_true'
    )
    arg_parser.add_argument(
        '-d', '--dry-run',
        help='does not use aws resources, instead prints to console',
        dest='dry_run',
        action='store_true'
    )
    args = arg_parser.parse_args()

    people = load_people(args.file)
    random.shuffle(people, random.seed(time.time()))
    matches = calculate_gift_pairs(people, people.copy(), args.no_family_match, args.no_reversal_match)
    if not matches:
        print("no matches found")
        return
    if args.send:
        if args.no_family_match:
            people_by_household = construct_households(people)
        sns_client = boto3.client('sns', region_name='us-east-1')
        send_sms(sns_client, matches, people_by_household, args.dry_run)

def construct_households(people):
    people_by_household = {}
    for person in people:
        if person.family in people_by_household:
            people_by_household[person.family].append(person)
        else:
            people_by_household[person.family] = [person]
    return people_by_household

def send_sms(sns_client, matches, people_by_household, dry_run):
    for giftee, gifter in matches.items():
        if people_by_household:
            people_in_household = people_by_household[gifter.family]
            household_names = '\nYou cannot be matched with anyone in your "household group". So feel free to plan your gifts with: {}. '.format(
                ', '.join(map(lambda x: str(x), filter(lambda x: x is not gifter, people_in_household))))
        information = 'Reach out to Liam with any questions.'
        message = '🎅❄️ Secret Santa ❄️🎅\n\n{gifter}, your match is {giftee}!\n{household_names}{information}'.format(
            gifter=gifter, giftee=giftee, household_names=household_names or "", information=information)
        message_attribtues = {
            "AWS.SNS.SMS.MaxPrice": {
                "DataType": "Number",
                "StringValue": "10.00"
            }
        }
        if dry_run:
            print("To phone: {}\n--------\n{}\n--------".format(gifter.phone, message))
        else:
            sns_client.publish(PhoneNumber=gifter.phone, Message=message, MessageAttributes=message_attribtues)

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
            if len(row) < 2 or len(row) > 3:
                raise ValueError("{} has incorrect format: expecting name, family name, phone number.".format(row))

            if len(row) == 3:
                name, family, phone = row
            else:
                phone = None
                name, family = row
            person = Person(name, family, phone)

            people.append(person)
    return people

class Person():
    def __init__(self, name, family, phone):
        self.name = name
        self.family = family
        self.phone = phone

    def __str__(self):
        return self.name

    def __repr__(self):
        return "{name} ({family}), tel: {phone}".format(name=self.name, family=self.family, phone=self.phone)

if __name__ == '__main__':
    main()
    