"""Text message delivery via Textbelt (https://textbelt.com).

Textbelt needs no phone number registration, unlike SNS and Twilio, which now
require a verified toll-free or 10DLC number to text US phones. Buy a key at
textbelt.com and export it as TEXTBELT_KEY. The key "textbelt" sends one free
text per day, which is handy for a test.
"""

import json
import urllib.error
import urllib.parse
import urllib.request

TEXTBELT_URL = "https://textbelt.com"


class SendError(Exception):
    pass


class TextbeltSender:
    def __init__(self, key, timeout=30):
        if not key:
            raise SendError("Set TEXTBELT_KEY (buy a key at https://textbelt.com).")
        self.key = key
        self.timeout = timeout

    def quota_remaining(self):
        url = f"{TEXTBELT_URL}/quota/{urllib.parse.quote(self.key)}"
        data = self._request(urllib.request.Request(url))
        return data.get("quotaRemaining")

    def send(self, phone, message):
        body = urllib.parse.urlencode(
            {"phone": phone, "message": message, "key": self.key}).encode()
        data = self._request(urllib.request.Request(
            f"{TEXTBELT_URL}/text", data=body, method="POST"))
        if not data.get("success"):
            raise SendError(data.get("error") or "Textbelt reported a failure")
        return data.get("textId")

    def _request(self, request):
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as resp:
                return json.load(resp)
        except urllib.error.URLError as e:
            raise SendError(f"Could not reach Textbelt: {e}") from e


class ConsoleSender:
    """Prints messages instead of sending them."""

    def quota_remaining(self):
        return None

    def send(self, phone, message):
        print(f"To {phone}:\n{'-' * 30}\n{message}\n{'-' * 30}")
        return "console"
