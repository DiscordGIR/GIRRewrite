import unittest
from unittest.mock import AsyncMock, Mock

import aiohttp
from tests.support import load_module


class FetcherTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.module = load_module("utils/fetchers.py")

    async def test_session_is_reused_and_closed(self):
        await self.module.init_client_session()
        original = self.module.client_session
        await self.module.init_client_session()
        async with self.module.shared_session() as session:
            self.assertIs(session, original)
        self.assertFalse(original.closed)
        await self.module.close_client_session()
        self.assertTrue(original.closed)
        self.assertIsNone(self.module.client_session)
        await self.module.close_client_session()

    def response(self, payload=None, error=None):
        response = Mock()
        response.raise_for_status.side_effect = error
        response.json = AsyncMock(return_value=payload)
        context = AsyncMock()
        context.__aenter__.return_value = response
        self.module.client_session = Mock()
        self.module.client_session.get.return_value = context
        return response

    async def test_catalog_failure_preserves_last_good_snapshot(self):
        payload = {"ios": [], "group": [], "device": {}}
        self.response(payload)
        self.assertEqual(await self.module.get_ios_cfw.__wrapped__(), payload)
        self.response(error=aiohttp.ClientError("unavailable"))
        self.assertEqual(await self.module.get_ios_cfw.__wrapped__(), payload)

    async def test_first_catalog_failure_is_explicit(self):
        self.response(error=aiohttp.ClientError("unavailable"))
        with self.assertRaises(aiohttp.ClientError):
            await self.module.get_ios_cfw.__wrapped__()

    async def test_invalid_scam_feed_is_rejected(self):
        response = self.response()
        response.text = AsyncMock(return_value='{"scamjburls": "invalid"}')
        with self.assertRaises(ValueError):
            await self.module.fetch_scam_urls.__wrapped__()
