import io
import json
import unittest
import urllib.parse
from unittest import mock

from dickson_secret_santa.sms import SendError, TextbeltSender


def fake_response(payload):
    resp = io.BytesIO(json.dumps(payload).encode())
    resp.__enter__ = lambda s=resp: s
    resp.__exit__ = lambda *a: None
    return resp


class TextbeltTests(unittest.TestCase):
    def test_send_posts_form(self):
        with mock.patch("urllib.request.urlopen",
                        return_value=fake_response({"success": True, "textId": "42"})) as m:
            self.assertEqual(TextbeltSender("k").send("+12065550101", "hi 🎅"), "42")
        req = m.call_args[0][0]
        self.assertEqual(req.full_url, "https://textbelt.com/text")
        form = urllib.parse.parse_qs(req.data.decode())
        self.assertEqual(form, {"phone": ["+12065550101"], "message": ["hi 🎅"], "key": ["k"]})

    def test_send_failure_raises(self):
        with mock.patch("urllib.request.urlopen",
                        return_value=fake_response({"success": False, "error": "Out of quota"})):
            with self.assertRaisesRegex(SendError, "Out of quota"):
                TextbeltSender("k").send("+12065550101", "hi")

    def test_quota(self):
        with mock.patch("urllib.request.urlopen",
                        return_value=fake_response({"success": True, "quotaRemaining": 37})):
            self.assertEqual(TextbeltSender("k").quota_remaining(), 37)

    def test_missing_key(self):
        with self.assertRaises(SendError):
            TextbeltSender(None)


if __name__ == "__main__":
    unittest.main()
