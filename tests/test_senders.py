import io
import json
import smtplib
import unittest
import urllib.parse
from unittest import mock

from dickson_secret_santa.senders import EmailSender, SendError, TextbeltSender


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

    def test_delivery_status(self):
        with mock.patch("urllib.request.urlopen",
                        return_value=fake_response({"status": "DELIVERED"})) as m:
            self.assertEqual(TextbeltSender("k").delivery_status("42"), "DELIVERED")
        self.assertEqual(m.call_args[0][0].full_url, "https://textbelt.com/status/42")

    def test_bad_key_on_quota(self):
        with mock.patch("urllib.request.urlopen",
                        return_value=fake_response({"success": False, "error": "Bad key"})):
            with self.assertRaisesRegex(SendError, "Bad key"):
                TextbeltSender("k").quota_remaining()

    def test_missing_key(self):
        with self.assertRaises(SendError):
            TextbeltSender(None)


class EmailTests(unittest.TestCase):
    ENV = {"SMTP_USER": "me@gmail.com", "SMTP_PASSWORD": "app-pw"}

    def test_emails_reuse_one_connection(self):
        with mock.patch("smtplib.SMTP") as smtp_cls:
            with EmailSender("test@example.com", env=self.ENV) as sender:
                sender.send("+12065550101", "Rob, your match is Kyle!")
                sender.send(None, "Carol, your match is Tim!")
        smtp_cls.assert_called_once_with("smtp.gmail.com", 587, timeout=30)
        conn = smtp_cls.return_value
        conn.starttls.assert_called_once()
        conn.login.assert_called_once_with("me@gmail.com", "app-pw")
        sent = [c.args[0] for c in conn.send_message.call_args_list]
        self.assertEqual(len(sent), 2)
        self.assertEqual(sent[0]["To"], "test@example.com")
        self.assertEqual(sent[0]["From"], "me@gmail.com")
        self.assertIn("+12065550101", sent[0]["Subject"])
        self.assertIn("Rob, your match is Kyle!", sent[0].get_content())
        conn.quit.assert_called_once()

    def test_missing_credentials(self):
        with self.assertRaises(SendError):
            EmailSender("test@example.com", env={})

    def test_smtp_error_becomes_send_error(self):
        with mock.patch("smtplib.SMTP") as smtp_cls:
            smtp_cls.return_value.login.side_effect = smtplib.SMTPAuthenticationError(535, b"bad")
            with self.assertRaisesRegex(SendError, "Email failed"):
                EmailSender("t@example.com", env=self.ENV).send("+1", "hi")


if __name__ == "__main__":
    unittest.main()
