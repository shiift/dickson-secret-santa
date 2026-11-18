"""Ways to deliver the secret santa messages.

TextbeltSender texts people for real (https://textbelt.com). Textbelt needs no
phone number registration, unlike SNS and Twilio, which now require a verified
toll-free or 10DLC number to text US phones. Buy a key and export TEXTBELT_KEY.

EmailSender sends trial runs to one email address, and ConsoleSender prints.
Every sender is a context manager, so `with make_sender() as s:` cleans up.
"""

import json
import os
import smtplib
import urllib.error
import urllib.parse
import urllib.request
from email.message import EmailMessage

TEXTBELT_URL = "https://textbelt.com"


class SendError(Exception):
    pass


class Sender:
    def send(self, phone, message):
        """Deliver `message`; return an id that `delivery_status` understands, or None."""
        raise NotImplementedError

    def quota_remaining(self):
        """Texts left on the account, or None if unlimited or unknown."""
        return None

    def delivery_status(self, message_id):
        """Carrier delivery status for a sent message, or None if unsupported."""
        return None

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


class TextbeltSender(Sender):
    def __init__(self, key, timeout=30):
        if not key:
            raise SendError("Set TEXTBELT_KEY (buy a key at https://textbelt.com).")
        self.key = key
        self.timeout = timeout

    def send(self, phone, message):
        body = urllib.parse.urlencode(
            {"phone": phone, "message": message, "key": self.key}).encode()
        data = self._request(urllib.request.Request(
            f"{TEXTBELT_URL}/text", data=body, method="POST"))
        if not data.get("success"):
            raise SendError(data.get("error") or "Textbelt reported a failure")
        return data.get("textId")

    def quota_remaining(self):
        data = self._request(urllib.request.Request(
            f"{TEXTBELT_URL}/quota/{urllib.parse.quote(self.key)}"))
        if not data.get("success", True):
            raise SendError(data.get("error") or "Textbelt rejected the key")
        return data.get("quotaRemaining")

    def delivery_status(self, message_id):
        """One of DELIVERED, SENT, SENDING, FAILED, UNKNOWN."""
        data = self._request(urllib.request.Request(
            f"{TEXTBELT_URL}/status/{urllib.parse.quote(str(message_id))}"))
        return data.get("status")

    def _request(self, request):
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as resp:
                return json.load(resp)
        except (urllib.error.URLError, OSError, ValueError) as e:
            raise SendError(f"Could not reach Textbelt: {e}") from e


class EmailSender(Sender):
    """Emails each would-be text to one test address, for trial runs.

    SMTP settings come from the environment:
      SMTP_HOST (default smtp.gmail.com), SMTP_PORT (default 587, STARTTLS),
      SMTP_USER, SMTP_PASSWORD (for Gmail, an app password), SMTP_FROM
      (defaults to SMTP_USER).
    """

    def __init__(self, to_address, env=None):
        env = os.environ if env is None else env
        self.to_address = to_address
        self.host = env.get("SMTP_HOST", "smtp.gmail.com")
        self.port = int(env.get("SMTP_PORT", "587"))
        self.user = env.get("SMTP_USER")
        self.password = env.get("SMTP_PASSWORD")
        self.from_address = env.get("SMTP_FROM") or self.user
        if not (self.user and self.password):
            raise SendError("Set SMTP_USER and SMTP_PASSWORD to send test emails.")
        self._smtp = None

    def send(self, phone, message):
        msg = EmailMessage()
        msg["Subject"] = f"[Secret Santa test] text for {phone or 'no phone'}"
        msg["From"] = self.from_address
        msg["To"] = self.to_address
        msg.set_content(message)
        try:
            if self._smtp is None:
                self._smtp = smtplib.SMTP(self.host, self.port, timeout=30)
                self._smtp.starttls()
                self._smtp.login(self.user, self.password)
            self._smtp.send_message(msg)
        except (smtplib.SMTPException, OSError) as e:
            raise SendError(f"Email failed: {e}") from e
        return None

    def close(self):
        if self._smtp is not None:
            try:
                self._smtp.quit()
            except (smtplib.SMTPException, OSError):
                pass
            self._smtp = None


class ConsoleSender(Sender):
    """Prints messages instead of sending them."""

    def send(self, phone, message):
        print(f"To {phone}:\n{'-' * 30}\n{message}\n{'-' * 30}")
        return None
