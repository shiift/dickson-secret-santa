# Dickson Secret Santa

Draws secret santa pairings for the family and texts each person their match.

- Nobody draws someone from their own household, and no two people draw each other
  (both can be turned off).
- Every valid pairing is equally likely, so matches don't depend on file order.
- Optionally avoids repeating last year's pairings.
- Texts go out through [Textbelt](https://textbelt.com), which needs no phone
  number registration. AWS SNS and Twilio now require a verified toll-free or
  10DLC number (with business details) to text US phones.
- Pure standard-library Python 3.10+, no dependencies.

## Setup

1. Copy `participants.example.csv` to `participants.csv` (git ignores it) and
   fill in real phone numbers. Format: `name, household, phone`. Lines starting
   with `#` are ignored. Phone numbers can be `206-555-0101` or `+12065550101`.
2. Buy a Textbelt key (about $3 for 50 texts) and export it:
   `export TEXTBELT_KEY=...`

## Usage

```sh
# Check the list and confirm everyone can be paired. Nothing is sent or shown.
python3 -m dickson_secret_santa participants.csv --note "Budget is about \$50."

# Send yourself a sample text with a made-up match.
python3 -m dickson_secret_santa participants.csv --test-to 206-555-0112

# Send for real. Pairings are saved to participants.csv.<year>.audit first.
python3 -m dickson_secret_santa participants.csv --send --note "Budget is about \$50."

# Someone lost their text? Re-send just theirs from the audit file.
python3 -m dickson_secret_santa participants.csv --resend Carol

# Next year, avoid repeating this year's matches.
python3 -m dickson_secret_santa participants.csv --send --avoid participants.csv.2026.audit
```

Add `--dry-run` to `--send`, `--test-to` or `--resend` to print the texts instead
of sending them. Note that this shows the real matches, including your own.
`--reveal` prints every pairing without sending anything.

Other options: `--allow-family-match`, `--allow-reversals`, `--organizer NAME`
(default "Liam"), `--audit PATH`, `--force` (overwrite an existing audit file).
Run with `-h` for the full list.

## Tests

```sh
python3 -m unittest
```
