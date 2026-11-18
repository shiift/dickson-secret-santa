# Dickson Secret Santa

Draws secret santa pairings for the family and texts each person their match.

- Nobody draws someone from their own household, and no two people draw each other
  (both can be turned off).
- Every valid pairing is equally likely, so matches don't depend on file order.
- Optionally avoids repeating last year's pairings.
- Texts go out through [Textbelt](https://textbelt.com), which needs no phone
  number registration. AWS SNS and Twilio now require a verified toll-free or
  10DLC number (with business details) to text US phones.
- Safe to rerun: the audit file records who has been texted, so rerunning `--send`
  only retries the people who haven't been sent their match.
- Pure standard-library Python 3.10+, no dependencies.

A text looks like this (kept within 2 SMS segments; the script refuses to send
anything longer):

```
🎅 Secret Santa: Rob, your match is Kyle!
You can plan with Kyoung-Hi and Mina.
Budget is about $50.
```

## Setup

1. Copy `participants.example.csv` to `participants.csv` (git ignores it) and
   fill in real phone numbers. Format: `name, household, phone`. Lines starting
   with `#` are ignored. Phone numbers can be `206-555-0101` or `+12065550101`.
2. Buy a Textbelt key (about $3 for 50 texts) and export it:
   `export TEXTBELT_KEY=...`
3. For trial runs by email, export SMTP settings. For Gmail, create an
   [app password](https://myaccount.google.com/apppasswords) (needs 2-step
   verification):
   ```sh
   export SMTP_USER=you@gmail.com SMTP_PASSWORD=your-app-password
   # optional: SMTP_HOST (default smtp.gmail.com), SMTP_PORT (587), SMTP_FROM
   ```

Run it with `python3 -m dickson_secret_santa`, or `pip install .` once and use the
`dickson_secret_santa` command.

## Usage

```sh
# Check the list, confirm everyone can be paired, and make sure every possible
# text fits in 2 SMS segments. Nothing is sent and no pairings are shown.
python3 -m dickson_secret_santa participants.csv --note "Budget is about \$50."

# Trial run: draw throwaway pairings and email every would-be text to you.
# Nothing is texted and nothing is saved, so the real draw stays a surprise.
python3 -m dickson_secret_santa participants.example.csv --test-email you+test@gmail.com

# Send for real. Pairings and the note are saved to
# participants.csv.<year>.audit.json, which is updated after every text.
python3 -m dickson_secret_santa participants.csv --send --note "Budget is about \$50."

# Some texts failed? Run --send again (no --note needed; the saved one is reused).
# Only people who weren't sent their match are texted.
python3 -m dickson_secret_santa participants.csv --send

# Check whether each text was delivered (and save the result in the audit file).
python3 -m dickson_secret_santa participants.csv --status

# Someone lost their text or changed numbers? Fix participants.csv if needed,
# then re-send just theirs, with the same match and note.
python3 -m dickson_secret_santa participants.csv --resend Carol

# Next year, avoid repeating this year's matches (old .audit text files work too).
python3 -m dickson_secret_santa participants.csv --send --avoid participants.csv.2026.audit.json
```

`--send --dry-run` prints a throwaway set of texts instead of sending them, and
`--resend NAME --dry-run` prints that person's real text. Both save nothing, but
they show matches. `--reveal` prints the saved pairings. `--force` throws away
this year's audit file and redraws, so anyone already texted would get a new match.

Other options: `--allow-family-match`, `--allow-reversals`, `--audit PATH`.
Run with `-h` for the full list.

## Tests

```sh
python3 -m unittest
```

They also run on GitHub Actions for Python 3.10 to 3.13 on every push.
