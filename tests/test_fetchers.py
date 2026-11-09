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


class CijSnapshotTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.module = load_module("utils/fetchers.py")

    async def asyncTearDown(self):
        await self.module._cij_cache.close()

    def response(self, payload, error=None):
        import json
        response = Mock()
        response.raise_for_status.side_effect = error
        response.text = AsyncMock(return_value=json.dumps(payload))
        context = AsyncMock()
        context.__aenter__.return_value = response
        self.module.client_session = Mock(closed=False)
        self.module.client_session.get.return_value = context
        return response

    async def test_valid_snapshot_is_immutable_and_all_fields_are_validated(self):
        valid = {key: ["text"] for key in ('intent_cij', 'intent_news', 'verb', 'subject')}
        self.response(valid)
        result = await self.module.get_cij_or_news()
        self.assertEqual(result['subject'], ('text',))
        with self.assertRaises(TypeError):
            result['subject'] = ()
        for key in valid:
            self.module._cij_cache.invalidate('catalog')
            self.response({**valid, key: None})
            self.assertIsNone(await self.module.get_cij_or_news())

    async def test_outage_retains_last_good_and_first_failure_is_safe(self):
        self.response({}, aiohttp.ClientError('offline'))
        self.assertIsNone(await self.module.get_cij_or_news())
        valid = {key: ["text"] for key in ('intent_cij', 'intent_news', 'verb', 'subject')}
        self.response(valid)
        original = await self.module.get_cij_or_news()
        self.module._cij_cache.values['catalog'] = (0, original)
        self.response({}, aiohttp.ClientError('offline'))
        self.assertIs(await self.module.get_cij_or_news(), original)

    async def test_concurrent_feed_requests_share_one_http_request(self):
        import asyncio
        valid = {key: ["text"] for key in ('intent_cij', 'intent_news', 'verb', 'subject')}
        response = self.response(valid)
        entered, release = asyncio.Event(), asyncio.Event()
        async def body():
            import json
            entered.set()
            await release.wait()
            return json.dumps(valid)
        response.text.side_effect = body
        pending = [asyncio.create_task(self.module.get_cij_or_news()) for _ in range(20)]
        await entered.wait()
        release.set()
        results = await asyncio.gather(*pending)
        self.assertTrue(all(result is results[0] for result in results))
        self.module.client_session.get.assert_called_once()
