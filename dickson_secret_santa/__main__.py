import argparse
import datetime
import os
import random
import sys

from .santa import (
    Person, PairingRules, NoPairingError, build_message, generate_pairs,
    households, load_people, load_previous_pairs,
)
from .sms import ConsoleSender, EmailSender, SendError, TextbeltSender


def parse_args(argv=None):
    p = argparse.ArgumentParser(
        prog="dickson_secret_santa",
        description="Generates secret santa pairings and texts each gifter their match.",
        epilog="With no action flag, the script only checks the list and makes "
               "sure a valid pairing exists. Nothing is sent and no pairings are shown.")
    p.add_argument("file", help="CSV of participants: name, household, phone")

    rules = p.add_argument_group("pairing rules")
    rules.add_argument("--allow-family-match", action="store_true",
                       help="allow people to draw someone from their own household")
    rules.add_argument("--allow-reversals", action="store_true",
                       help="allow two people to draw each other")
    rules.add_argument("--avoid", metavar="AUDIT_FILE", action="append", default=[],
                       help="avoid repeating pairings from a previous year's audit file "
                            "(repeatable)")

    msg = p.add_argument_group("message")
    msg.add_argument("--organizer", default="Liam",
                     help="name people should contact with questions (default: Liam)")
    msg.add_argument("--note", help="extra line for the text, e.g. 'Budget is $50.'")

    act = p.add_argument_group("actions (pick one)").add_mutually_exclusive_group()
    act.add_argument("--send", action="store_true",
                     help="generate pairings, save the audit file, and text everyone")
    act.add_argument("--test-email", metavar="ADDRESS",
                     help="trial run: draw throwaway pairings and email every would-be "
                          "text to ADDRESS instead of texting (needs SMTP_* env vars)")
    act.add_argument("--resend", metavar="NAME",
                     help="re-text NAME their match from the saved audit file")
    act.add_argument("--reveal", action="store_true",
                     help="print every pairing to the console (spoils it for you!)")

    p.add_argument("--audit", metavar="PATH",
                   help="audit file location (default: FILE.<year>.audit)")
    p.add_argument("--force", action="store_true",
                   help="overwrite an existing audit file when sending")
    p.add_argument("--dry-run", action="store_true",
                   help="with --send/--test-email/--resend, print messages instead of sending")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    try:
        return run(args)
    except (ValueError, NoPairingError, SendError, FileNotFoundError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


def run(args):
    people = load_people(args.file)
    by_household = households(people)
    audit_path = args.audit or f"{args.file}.{datetime.date.today().year}.audit"
    sender = ConsoleSender() if args.dry_run else None

    def get_sender():
        return sender or TextbeltSender(os.environ.get("TEXTBELT_KEY"))

    if args.resend:
        return resend(args, people, by_household, audit_path, get_sender())

    avoid = set()
    for f in args.avoid:
        avoid |= load_previous_pairs(f)
    rules = PairingRules(args.allow_family_match, args.allow_reversals, avoid)
    pairs = generate_pairs(people, rules)

    print_summary(people, by_household, avoid)

    if args.reveal:
        for gifter, giftee in sorted(pairs.items(), key=lambda kv: kv[0].name):
            print(f"  {gifter.name} -> {giftee.name}")
        return 0

    if args.test_email:
        test_sender = sender or EmailSender(args.test_email)
        print(f"\nTrial run: emailing {len(pairs)} would-be texts to {args.test_email}. "
              "These pairings are throwaway and are not saved.")
        try:
            return deliver(args, pairs, by_household, test_sender)
        finally:
            getattr(test_sender, "close", lambda: None)()

    if not args.send:
        sample = random.choice(people)
        print("\nSample text (match hidden):\n")
        print(build_message(sample, Person("<their match>", ""), by_household,
                            args.organizer, args.note))
        print("\nLooks good. Run with --send to text everyone.")
        return 0

    return send_all(args, people, by_household, pairs, audit_path, get_sender())


def print_summary(people, by_household, avoid):
    print(f"{len(people)} people in {len(by_household)} households:")
    for family, members in by_household.items():
        print(f"  {family}: {', '.join(m.name for m in members)}")
    missing = [p.name for p in people if not p.phone]
    if missing:
        print(f"WARNING: no phone number for {', '.join(missing)}")
    if avoid:
        print(f"Avoiding {len(avoid)} pairings from previous years.")
    print("A valid pairing for everyone was found.")


def send_all(args, people, by_household, pairs, audit_path, sender):
    missing = [p.name for p in people if not p.phone]
    if missing:
        raise ValueError(f"Add phone numbers for {', '.join(missing)} before sending")

    if not args.dry_run:
        if os.path.exists(audit_path) and not args.force:
            raise ValueError(
                f"{audit_path} already exists, so pairings may already have gone out. "
                "Use --resend NAME to re-text someone, or --force to start over.")
        quota = sender.quota_remaining()
        if quota is not None and quota < len(pairs):
            raise SendError(
                f"Textbelt key has {quota} texts left but {len(pairs)} are needed")
        # Save before sending so a partial failure can be fixed with --resend.
        with open(audit_path, "w") as f:
            for gifter, giftee in pairs.items():
                print(f"gifter:{gifter.name} giftee:{giftee.name}", file=f)
        print(f"Saved pairings to {audit_path} (don't peek if you're playing!)")

    return deliver(args, pairs, by_household, sender)


def deliver(args, pairs, by_household, sender):
    failures = []
    for gifter, giftee in pairs.items():
        message = build_message(gifter, giftee, by_household, args.organizer, args.note)
        try:
            sender.send(gifter.phone, message)
            print(f"  sent to {gifter.name}")
        except SendError as e:
            failures.append(gifter.name)
            print(f"  FAILED for {gifter.name}: {e}", file=sys.stderr)

    if failures:
        hint = " Retry each with: --resend NAME" if args.send else ""
        print(f"\n{len(failures)} message(s) failed.{hint}", file=sys.stderr)
        return 1
    print(f"\nAll {len(pairs)} messages sent.")
    return 0


def resend(args, people, by_household, audit_path, sender):
    by_name = {p.name.lower(): p for p in people}
    pairs = dict(load_previous_pairs(audit_path))
    key = args.resend.lower()
    if key not in by_name or key not in pairs:
        raise ValueError(f"{args.resend} isn't in both {args.file} and {audit_path}")
    gifter, giftee = by_name[key], by_name[pairs[key]]
    if not gifter.phone:
        raise ValueError(f"No phone number for {gifter.name}")
    sender.send(gifter.phone, build_message(gifter, giftee, by_household,
                                            args.organizer, args.note))
    print(f"Re-sent {gifter.name}'s match.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
