import unittest

from community_rules import (caps_percent, detect_scam, has_hidden_invite, has_invite,
                             has_suspicious_image_name, is_image_attachment,
                             normalize_obfuscated_text, recent_count)


def test_detects_fake_mrbeast_giveaway():
    assert detect_scam("MrBeast giveaway winner! Claim now at https://mrbeast-gift.example") == "possible fake MrBeast giveaway"


def test_detects_wallet_secret_theft():
    assert detect_scam("Verify your wallet seed phrase now at https://bit.ly/example") == "possible credential or wallet theft"


def test_does_not_flag_normal_scam_discussion():
    assert detect_scam("I saw a video explaining the MrBeast scam yesterday") is None
    assert detect_scam("Steam has a giveaway on its official store") is None
    assert detect_scam("Change your Discord password and scan the QR code in Settings") is None
    assert detect_scam("Use AirDrop to send this from your Apple device") is None


def test_removes_invisible_invite_bypass_characters():
    hidden = "https://disc\u200bord.\u200bgg/example"
    assert normalize_obfuscated_text(hidden) == "https://discord.gg/example"
    assert has_invite(normalize_obfuscated_text(hidden))
    assert has_hidden_invite(hidden)
    assert not has_hidden_invite("https://discord.gg/example")


def test_normalizes_compatibility_characters_and_control_codes():
    assert normalize_obfuscated_text("ｄｉｓｃｏｒｄ．ｇｇ/ab\u202ec") == "discord.gg/abc"


class CommunityRuleTests(unittest.TestCase):
    def test_caps_ignores_numbers_and_punctuation(self):
        self.assertEqual(caps_percent("THIS is 123!"), 67)
        self.assertEqual(caps_percent("123!"), 0)

    def test_discord_invites_are_detected(self):
        self.assertTrue(has_invite("join https://discord.gg/example"))
        self.assertTrue(has_invite("DISCORD.COM/invite/example"))
        self.assertFalse(has_invite("https://example.com"))

    def test_hidden_invites_and_compatibility_characters_are_detected(self):
        hidden = "https://disc\u200bord.\u200bgg/example"
        self.assertTrue(has_hidden_invite(hidden))
        self.assertFalse(has_hidden_invite("https://discord.gg/example"))
        self.assertEqual(normalize_obfuscated_text("ｄｉｓｃｏｒｄ．ｇｇ/ab\u202ec"),
                         "discord.gg/abc")

    def test_only_events_inside_window_count(self):
        self.assertEqual(recent_count([80, 91, 95, 100], 100, 10), 3)

    def test_image_attachment_recognizes_mime_and_filename_fallback(self):
        self.assertTrue(is_image_attachment("image/png", "upload.bin"))
        self.assertTrue(is_image_attachment(None, "Screenshot.HEIC"))
        self.assertFalse(is_image_attachment("application/pdf", "statement.pdf"))

    def test_suspicious_campaign_image_filename_is_narrow(self):
        self.assertTrue(has_suspicious_image_name("1.png"))
        self.assertTrue(has_suspicious_image_name("1.HEIC"))
        self.assertFalse(has_suspicious_image_name("10.png"))
        self.assertFalse(has_suspicious_image_name("photo1.png"))


if __name__ == "__main__":
    unittest.main()
