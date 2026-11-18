import argparse
import datetime
import os
import random
import sys

from .audit import FAILED, SENT, Audit, load_previous_pairs
from .santa import (
    MAX_SEGMENTS, NoPairingError, PairingRules, Person, build_message,
    check_message_length, generate_pairs, households, load_people, sms_segments,
)
from .senders import ConsoleSender, EmailSender, SendError, TextbeltSender


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

    p.add_argument("--note", help="extra line for the text, e.g. 'Budget is $50.' "
                                  "Saved in the audit file and reused on reruns.")

    act = p.add_argument_group("actions (pick one)").add_mutually_exclusive_group()
    act.add_argument("--send", action="store_true",
                     help="draw pairings, save the audit file, and text everyone. "
                          "Rerunning only texts people who haven't been sent theirs.")
    act.add_argument("--test-email", metavar="ADDRESS",
                     help="trial run: draw throwaway pairings and email every would-be "
                          "text to ADDRESS instead of texting (needs SMTP_* env vars)")
    act.add_argument("--resend", metavar="NAME",
                     help="re-text NAME their saved match, even if it was already sent")
    act.add_argument("--status", action="store_true",
                     help="check with Textbelt whether each saved text was delivered")
    act.add_argument("--reveal", action="store_true",
                     help="print the saved pairings (spoils it if you're playing!)")

    p.add_argument("--audit", metavar="PATH",
                   help="audit file location (default: FILE.<year>.audit.json)")
    p.add_argument("--force", action="store_true",
                   help="with --send, throw away the existing audit file and redraw")
    p.add_argument("--dry-run", action="store_true",
                   help="with --send or --resend, print texts instead of sending them "
                        "(and save nothing)")
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
    audit_path = args.audit or f"{args.file}.{datetime.date.today().year}.audit.json"

    def textbelt():
        if args.dry_run:
            return ConsoleSender()
        return TextbeltSender(os.environ.get("TEXTBELT_KEY"))

    if args.resend:
        with textbelt() as sender:
            return resend(args, people, by_household, audit_path, sender)
    if args.status:
        with TextbeltSender(os.environ.get("TEXTBELT_KEY")) as sender:
            return check_status(audit_path, sender)
    if args.reveal:
        return reveal(audit_path)

    avoid = set()
    for f in args.avoid:
        avoid |= load_previous_pairs(f)
    rules = PairingRules(args.allow_family_match, args.allow_reversals, avoid)

    if args.send and not args.dry_run:
        with textbelt() as sender:
            return send_for_real(args, people, by_household, rules, audit_path, sender)

    pairs = generate_pairs(people, rules)
    print_summary(people, by_household, avoid)
    segments = check_message_length(people, rules, by_household, args.note)
    print(f"Longest possible text: {segments} SMS segment(s).")

    if args.send:  # --dry-run
        print("\nDry run: throwaway pairings, nothing saved.\n")
        with ConsoleSender() as sender:
            return deliver(throwaway_entries(pairs), people, by_household, sender, args.note)

    if args.test_email:
        print(f"\nTrial run: emailing {len(pairs)} would-be texts to {args.test_email}. "
              "These pairings are throwaway and are not saved.")
        with EmailSender(args.test_email) as sender:
            return deliver(throwaway_entries(pairs), people, by_household, sender, args.note)

    sample = random.choice(people)
    print("\nSample text (match hidden):\n")
    print(build_message(sample, Person("<their match>", ""), by_household, args.note))
    if os.path.exists(audit_path):
        audit = Audit.load(audit_path)
        total, unsent = len(audit.entries), len(audit.unsent())
        if unsent:
            print(f"\n{audit_path}: {total - unsent} of {total} texts sent. "
                  "Run --send to finish.")
        else:
            print(f"\n{audit_path}: All {total} texts sent. Run --status to check delivery.")
    else:
        print("\nLooks good. Run with --send to text everyone.")
    return 0


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


def throwaway_entries(pairs):
    return Audit.new(None, pairs).entries


def send_for_real(args, people, by_household, rules, audit_path, sender):
    missing = [p.name for p in people if not p.phone]
    if missing:
        raise ValueError(f"Add phone numbers for {', '.join(missing)} before sending")

    if os.path.exists(audit_path) and not args.force:
        audit = Audit.load(audit_path)
        check_matches_people(audit, people)
        if args.note is not None and args.note != audit.note:
            raise ValueError(
                f"These pairings were drawn with --note {audit.note!r}. Rerun without "
                "--note (the saved one is reused) so everyone gets the same text.")
        print(f"Resuming {audit_path}: "
              f"{len(audit.entries) - len(audit.unsent())} of {len(audit.entries)} already sent.")
    else:
        if os.path.exists(audit_path):
            print(f"--force: replacing {audit_path} with a new draw.")
        audit = Audit.new(audit_path, generate_pairs(people, rules), args.note)

    pending = audit.unsent()
    if not pending:
        print("Everyone has been sent their match. Use --status to check delivery.")
        return 0

    by_name = {p.name.lower(): p for p in people}
    segments = max(sms_segments(build_message(
        by_name[e.gifter.lower()], by_name[e.giftee.lower()], by_household, audit.note))
        for e in pending)
    if segments > MAX_SEGMENTS:
        raise ValueError(f"Some texts would be {segments} SMS segments; shorten the note.")
    quota = sender.quota_remaining()
    needed = len(pending) * segments  # in case Textbelt bills per segment
    if quota is not None and quota < needed:
        raise SendError(f"Textbelt key has {quota} credits left; need up to {needed}")

    audit.save()
    print(f"Pairings saved to {audit_path} (don't peek if you're playing!)")
    return deliver(pending, people, by_household, sender, audit.note, audit.save)


def check_matches_people(audit, people):
    names = {p.name.lower() for p in people}
    in_audit = {e.gifter.lower() for e in audit.entries}
    if names != in_audit:
        raise ValueError(
            f"The participant list changed since {audit.path} was drawn. "
            "Use --force to redraw (people already texted would get a new match).")


def deliver(entries, people, by_household, sender, note, save=lambda: None):
    by_name = {p.name.lower(): p for p in people}
    failures = []
    for entry in entries:
        gifter, giftee = by_name[entry.gifter.lower()], by_name[entry.giftee.lower()]
        message = build_message(gifter, giftee, by_household, note)
        try:
            entry.mark_sent(gifter.phone, sender.send(gifter.phone, message))
            print(f"  sent to {gifter.name}")
        except SendError as e:
            entry.mark_failed(gifter.phone, e)
            failures.append(gifter.name)
            print(f"  FAILED for {gifter.name}: {e}", file=sys.stderr)
        save()

    if failures:
        print(f"\n{len(failures)} message(s) failed. Rerun the same command to retry "
              "just those.", file=sys.stderr)
        return 1
    print(f"\nAll {len(entries)} messages sent.")
    return 0


def resend(args, people, by_household, audit_path, sender):
    audit = Audit.load(audit_path)
    entry = audit.find(args.resend)
    by_name = {p.name.lower(): p for p in people}
    gifter = by_name.get(entry.gifter.lower())
    giftee = by_name.get(entry.giftee.lower())
    if not gifter or not giftee:
        raise ValueError(f"{entry.gifter} or their match is missing from {args.file}")
    if not gifter.phone:
        raise ValueError(f"No phone number for {gifter.name}")
    message = build_message(gifter, giftee, by_household, audit.note)
    try:
        entry.mark_sent(gifter.phone, sender.send(gifter.phone, message))
    except SendError as e:
        entry.mark_failed(gifter.phone, e)
        raise
    finally:
        if not args.dry_run:
            audit.save()
    print(f"Re-sent {gifter.name}'s match.")
    return 0


def check_status(audit_path, sender):
    audit = Audit.load(audit_path)
    problems = 0
    for entry in audit.entries:
        if entry.status == SENT and entry.text_id and entry.delivery != "DELIVERED":
            try:
                entry.delivery = sender.delivery_status(entry.text_id)
            except SendError as e:
                entry.delivery = f"unknown ({e})"
        if entry.status == SENT:
            shown = entry.delivery or "sent (no delivery info)"
        elif entry.status == FAILED:
            shown = f"FAILED to send: {entry.error}"
        else:
            shown = "not sent yet"
        if entry.delivery != "DELIVERED":
            problems += 1
        print(f"  {entry.gifter:<12} {shown}")
    audit.save()
    if problems:
        print(f"\n{problems} not confirmed delivered. Carriers can be slow to report; "
              "check again later, or --resend NAME.")
        return 1
    print(f"\nAll {len(audit.entries)} texts delivered.")
    return 0


def reveal(audit_path):
    audit = Audit.load(audit_path)
    for entry in sorted(audit.entries, key=lambda e: e.gifter):
        print(f"  {entry.gifter} -> {entry.giftee}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
