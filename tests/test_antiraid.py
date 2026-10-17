"""Run with: python -m unittest discover -s tests -v.

Load the cog with its external services stubbed so tests need neither MongoDB
nor a Discord connection (utils.__init__ normally starts the database).
"""

import base64
import importlib.util
import io
import json
import sys
import types
import unittest
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, Mock, patch

import discord
from discord.ext import commands
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


detection = load_module("antiraid_detection", "utils/antiraid.py")


class DetectionTests(unittest.TestCase):
    def test_hidden_and_compatibility_invites(self):
        for text in ["dis\u200bcord.gg/test", "discord.gg/t\u202eest", "discord.\ngg/test",
                     "ｄｉｓｃｏｒｄ.gg/test", "dsc.gg/t\u00adest"]:
            with self.subTest(text=text):
                self.assertIsNotNone(detection.find_invite(detection.strip_invisible(text)))
                self.assertIsNone(detection.find_invite(text))

    def test_invite_hosts_and_ordinary_links(self):
        for host in ["discord.com/invite", "discordapp.com/invite", "discord.gg",
                     "discordapp.gg/invite", "dsc.gg", "invite.gg", "discord.io",
                     "discord.li", "discord.me", "discord.st"]:
            self.assertIsNotNone(detection.find_invite(host + "/ab-12"))
        self.assertIsNone(detection.find_invite("https://discord.com/channels/1/2/3"))
        self.assertIsNone(detection.find_invite("https://example.com/invite/hello"))

    def test_image_attachment_classification(self):
        for content_type, filename, expected in [
            ("image/png", "no-extension", True), (None, "photo.JPEG", True),
            (None, "photo.avif", True), ("text/plain", "photo.png", False),
            (None, "notes.txt", False),
        ]:
            self.assertEqual(bool(detection.is_image(NS(content_type=content_type, filename=filename))), expected)

    def test_stored_fingerprints_and_thresholds(self):
        for ref in detection.KNOWN_SCAM_IMAGES:
            self.assertEqual(detection.fingerprint_distance(ref, ref), (0, 0))
            self.assertEqual(detection.match_fingerprint(ref), ref["name"])
        ref = {"name": "test", "bits": "0" * 256,
               "colors": base64.b64encode(bytes([100] * 768)).decode()}
        with patch.object(detection, "KNOWN_SCAM_IMAGES", [ref]):
            def candidate(bits, color):
                return {"bits": "1" * bits + "0" * (256 - bits),
                        "colors": base64.b64encode(bytes([100 + color] * 768)).decode()}
            self.assertEqual(detection.match_fingerprint(candidate(24, 8)), "test")
            self.assertIsNone(detection.match_fingerprint(candidate(25, 8)))
            self.assertIsNone(detection.match_fingerprint(candidate(24, 9)))

    def test_sharp_reference_fingerprints(self):
        # Generated using the supplied JS implementation and Sharp 0.33.5.
        fixtures = ROOT / "tests/fixtures/antiraid"
        references = json.loads((fixtures / "fingerprints.json").read_text())
        for name, expected in references.items():
            with self.subTest(name=name):
                self.assertEqual(detection.image_fingerprint((fixtures / name).read_bytes()), expected)

    def test_invalid_and_oversized_images(self):
        with self.assertRaises(Exception):
            detection.image_fingerprint(b"not an image")
        image = Image.new("RGB", (12, 12))
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        with patch.object(detection, "MAX_IMAGE_PIXELS", 100), self.assertRaises(ValueError):
            detection.image_fingerprint(buffer.getvalue())


class DownloadTests(unittest.IsolatedAsyncioTestCase):
    async def test_limits_and_http_failures(self):
        attachment = NS(size=detection.MAX_IMAGE_BYTES + 1, url="https://cdn.invalid/image")
        session = Mock()
        with self.assertRaises(ValueError):
            await detection.download_image(attachment, session)
        session.get.assert_not_called()
        attachment.size = 1
        response = NS(status=302)
        context = AsyncMock()
        context.__aenter__.return_value = response
        session.get.return_value = context
        with self.assertRaises(ValueError):
            await detection.download_image(attachment, session)
        self.assertFalse(session.get.call_args.kwargs["allow_redirects"])
        self.assertEqual(session.get.call_args.kwargs["timeout"].total, 10)

    async def test_streamed_limit_and_success(self):
        async def chunks(_):
            yield b"abc"
            yield b"def"
        response = NS(status=200, content=NS(iter_chunked=chunks))
        context = AsyncMock()
        context.__aenter__.return_value = response
        session = Mock(get=Mock(return_value=context))
        attachment = NS(size=1, url="https://cdn.invalid/image")
        self.assertEqual(await detection.download_image(attachment, session), b"abcdef")
        with patch.object(detection, "MAX_IMAGE_BYTES", 5), self.assertRaises(ValueError):
            await detection.download_image(attachment, session)


class CogTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.cfg = NS(guild_id=1, roles=NS(member_plus=2, moderator=3), channels=NS(reports=4), dev=False)
        utils = types.ModuleType("utils")
        utils.__path__ = [str(ROOT / "utils")]
        utils.cfg = self.cfg
        utils.fetchers = NS(client_session=Mock())
        utils.logger = Mock()
        framework = types.ModuleType("utils.framework")
        framework.MessageTextBucket = NS(custom=commands.BucketType.default)
        framework.gatekeeper = NS(has=Mock(return_value=False))
        framework.check_invokee = AsyncMock()
        framework.find_triggered_raid_phrases = AsyncMock()
        mod = types.ModuleType("utils.mod")
        mod.mute, mod.ban, mod.prepare_ban_log = AsyncMock(), AsyncMock(), Mock()
        views = types.ModuleType("utils.views")
        views.__path__ = [str(ROOT / "utils/views")]
        views.report_raid = views.report_raid_phrase = views.report_spam = AsyncMock()
        menus = types.ModuleType("utils.views.menus")
        menus.__path__ = [str(ROOT / "utils/views/menus")]
        model, services = types.ModuleType("data.model"), types.ModuleType("data.services")
        model.Case = Mock()
        services.guild_service = services.user_service = Mock()
        self.patcher = patch.dict(sys.modules, {
            "utils": utils, "utils.antiraid": detection, "utils.framework": framework,
            "utils.mod": mod, "utils.views": views, "utils.views.menus": menus,
            "data.model": model, "data.services": services,
        })
        self.patcher.start()
        self.addCleanup(self.patcher.stop)
        self.reports = load_module("report_antiraid_test", "utils/views/menus/antiraid.py")
        sys.modules["utils.views.menus.antiraid"] = self.reports
        self.module = load_module("antiraid_cog_test", "cogs/monitors/mod/antiraid.py")
        self.cog = self.module.AntiRaidMonitor(Mock())
        self.cog.send_content_report = AsyncMock()
        self.member = Mock(spec=discord.Member)
        self.member.id = 10
        self.member.bot = False
        self.member.mention = "<@10>"
        self.member.roles = []
        self.member.guild_permissions = NS(administrator=False)
        self.member.top_role = 1
        self.member.timeout = AsyncMock()
        self.guild = NS(id=1, owner_id=20, me=NS(top_role=10, guild_permissions=NS(moderate_members=True)),
                        get_member=Mock(return_value=self.member), get_channel=Mock(), get_role=Mock())
        self.message = NS(guild=self.guild, author=self.member, content="", attachments=[],
                          channel=NS(mention="<#5>"), delete=AsyncMock())
        self.download = patch.object(self.module, "download_image", AsyncMock(return_value=b"image"))
        self.download_mock = self.download.start()
        self.addCleanup(self.download.stop)

    def attachment(self, id=1, name="photo.png"):
        return NS(id=id, filename=name, content_type="image/png")

    async def test_hidden_invite_and_plain_invite(self):
        self.message.content = "dis\u200bcord.gg/test"
        self.assertTrue(await self.cog.hidden_invite(self.message))
        self.member.timeout.assert_awaited_once_with(timedelta(days=7), reason="ads")
        self.assertEqual(self.cog.send_content_report.call_args.kwargs["hidden_count"], 1)
        self.message.delete.reset_mock()
        self.message.content = "discord.gg/test"
        self.assertFalse(await self.cog.hidden_invite(self.message))
        self.message.delete.assert_not_called()

    async def test_image_legacy_rules_and_evidence_before_delete(self):
        for names in [["1.PNG"], ["a.png", "b.png", "c.png", "d.png"]]:
            self.message.attachments = [self.attachment(i, name) for i, name in enumerate(names)]
            async def deleting():
                self.assertGreaterEqual(self.download_mock.await_count, len(names))
            self.message.delete.side_effect = deleting
            self.assertTrue(await self.cog.image_spam(self.message))
            self.assertEqual(len(self.cog.send_content_report.call_args.kwargs["evidence"]), len(names))
            self.download_mock.reset_mock()

    async def test_visual_match_arbitrary_filename_and_safe_failure(self):
        self.message.attachments = [self.attachment()]
        with patch.object(self.module, "image_fingerprint", return_value=detection.KNOWN_SCAM_IMAGES[0]):
            self.assertTrue(await self.cog.image_spam(self.message))
        self.download_mock.assert_awaited_once()  # Reuse scanning bytes as evidence.
        self.message.delete.reset_mock()
        self.download_mock.side_effect = ValueError("too large")
        self.assertFalse(await self.cog.image_spam(self.message))
        self.message.delete.assert_not_called()

    async def test_nonmatching_image_and_member_plus_exemption(self):
        self.message.attachments = [self.attachment()]
        with patch.object(self.module, "image_fingerprint", return_value={}), patch.object(self.module, "match_fingerprint", return_value=None):
            self.assertFalse(await self.cog.image_spam(self.message))
        self.download_mock.reset_mock()
        self.member.roles = [NS(id=2)]
        self.assertFalse(await self.cog.image_spam(self.message))
        self.download_mock.assert_not_called()

    async def test_listener_exemptions_and_short_circuit(self):
        self.member.guild_permissions.administrator = True
        self.cog.hidden_invite = AsyncMock(return_value=True)
        self.cog.image_spam = AsyncMock(return_value=True)
        with patch.object(self.module.gatekeeper, "has", return_value=True):
            await self.cog.on_message(self.message)
        self.cog.hidden_invite.assert_not_called()
        self.member.guild_permissions.administrator = False
        await self.cog.on_message(self.message)
        self.cog.hidden_invite.assert_awaited_once()
        self.cog.image_spam.assert_not_called()
        self.cog.hidden_invite.reset_mock()
        self.member.bot = True
        await self.cog.on_message(self.message)
        self.cog.hidden_invite.assert_not_called()

    async def test_moderation_failures_are_reported_accurately(self):
        error = discord.Forbidden(NS(status=403, reason="Forbidden"), "Forbidden")
        self.message.delete.side_effect = error
        self.member.timeout.side_effect = error
        self.assertEqual(await self.cog.apply_content_moderation(self.message, "test"),
                         "Message deletion failed; Timeout failed")
        self.guild.me.top_role = 1
        self.member.timeout.reset_mock()
        self.assertIn("Cannot timeout", await self.cog.apply_content_moderation(self.message, "test"))
        self.member.timeout.assert_not_called()

    async def test_cooldown_does_not_suppress_moderation(self):
        self.cog.send_content_report = self.module.AntiRaidMonitor.send_content_report.__get__(self.cog)
        with patch.object(self.module, "report_antiraid", AsyncMock(return_value=True)) as send:
            self.message.content = "dis\u200bcord.gg/test"
            await self.cog.hidden_invite(self.message)
            await self.cog.hidden_invite(self.message)
            self.assertEqual(self.message.delete.await_count, 2)
            send.assert_awaited_once()

    async def test_failed_report_can_retry(self):
        self.cog.send_content_report = self.module.AntiRaidMonitor.send_content_report.__get__(self.cog)
        with patch.object(self.module, "report_antiraid", AsyncMock(side_effect=[RuntimeError(), True])) as send:
            await self.cog.send_content_report(self.message)
            await self.cog.send_content_report(self.message)
            self.assertEqual(send.await_count, 2)

    async def test_report_gallery_and_online_pings(self):
        channel = NS(send=AsyncMock())
        self.guild.get_channel.return_value = channel
        online = NS(status=discord.Status.online, id=30, mention="<@30>")
        idle = NS(status=discord.Status.idle, id=31, mention="<@31>")
        self.guild.get_role.return_value = NS(members=[online, idle])
        kwargs = dict(title="test", trigger="test", reason="test", actions="test")
        await self.reports.report_antiraid(self.message, evidence=[("image0.png", b"a"), ("image1.png", b"b")], **kwargs)
        args = channel.send.call_args
        self.assertEqual(args.args[0], "<@30>")
        self.assertEqual([e.url for e in args.kwargs["embeds"]], ["https://discord.com"] * 2)
        self.assertEqual(args.kwargs["embeds"][1].image.url, "attachment://image1.png")
        self.guild.get_role.return_value = NS(members=[idle])
        await self.reports.report_antiraid(self.message, **kwargs)
        self.assertEqual(channel.send.call_args.args[0], "<@&3>")

    async def test_button_permissions_and_gir_ban(self):
        view = self.reports.AntiRaidReportActions(self.member)
        interaction = NS(guild=self.guild, user=NS(id=99), client=NS(fetch_user=AsyncMock()),
                         response=NS(defer=AsyncMock(), send_message=AsyncMock()),
                         followup=NS(send=AsyncMock()), message=NS(delete=AsyncMock()))
        self.assertFalse(await view.interaction_check(interaction))
        with patch.object(self.reports.gatekeeper, "has", return_value=True):
            self.assertTrue(await view.interaction_check(interaction))
        await view.ban_member.callback(interaction)
        self.reports.ban.assert_awaited_once_with(interaction, self.member, mod=interaction.user, reason="compromised account")
        self.reports.check_invokee.assert_awaited_once_with(interaction, self.member)
        interaction.message.delete.assert_awaited_once()
        await view.ban_member.callback(interaction)
        self.reports.ban.assert_awaited_once()

    async def test_failed_ban_keeps_report_and_dismiss_keeps_timeout(self):
        view = self.reports.AntiRaidReportActions(self.member)
        interaction = NS(guild=self.guild, user=NS(id=99), response=NS(defer=AsyncMock()),
                         followup=NS(send=AsyncMock()), message=NS(delete=AsyncMock()))
        self.reports.ban.side_effect = RuntimeError("failed")
        await view.ban_member.callback(interaction)
        interaction.message.delete.assert_not_called()
        self.assertFalse(view.resolved)
        await view.dismiss.callback(interaction)
        interaction.message.delete.assert_awaited_once()
        self.member.timeout.assert_not_called()
