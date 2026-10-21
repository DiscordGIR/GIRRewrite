import asyncio
import ast
from pathlib import Path
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import mongoengine
from data.database import configure_database_pool, database_method, run_database
from data.model import User
from tests.support import connect_test_database, load_module, ROOT


class DatabaseBoundaryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        worker = load_module('utils/worker.py')
        self.pool = worker.BlockingIOPool(workers=2, name='test-db')
        configure_database_pool(self.pool)
        connect_test_database()

    async def asyncTearDown(self):
        await self.pool.close()
        configure_database_pool(None)
        mongoengine.disconnect()

    async def test_slow_repository_does_not_block_loop_and_errors_propagate(self):
        entered = threading.Event()
        release = threading.Event()
        loop_thread = threading.get_ident()

        def operation():
            self.assertNotEqual(threading.get_ident(), loop_thread)
            entered.set()
            if not release.wait(2):
                raise AssertionError('event loop could not release database operation')
            raise ValueError('database failure')

        class Service:
            query = database_method(operation)

        task = asyncio.create_task(Service().query())
        try:
            async def wait_for_worker():
                while not entered.is_set():
                    await asyncio.sleep(0.001)
            await asyncio.wait_for(wait_for_worker(), 1)
            self.assertFalse(task.done())
        finally:
            release.set()
        with self.assertRaisesRegex(ValueError, 'database failure'):
            await task

    async def test_birthdays_are_materialized_and_saves_run_in_worker(self):
        module = load_module('data/services/user_service.py')
        profile = User(_id=888, birthday=[10, 17])
        loop_thread = threading.get_ident()
        collection = User._get_collection()
        original_find = collection.find
        query_threads = []

        def find(*args, **kwargs):
            query_threads.append(threading.get_ident())
            return original_find(*args, **kwargs)

        await run_database(profile.save)
        with patch.object(collection, 'find', side_effect=find):
            birthdays = await module.user_service.retrieve_birthdays([10, 17])
        self.assertIsInstance(birthdays, list)
        self.assertIn(888, [user._id for user in birthdays])
        self.assertTrue(query_threads)
        self.assertNotIn(loop_thread, query_threads)

    async def test_gridfs_reads_and_metadata_stay_in_worker(self):
        if not __import__('os').environ.get('GIR_TEST_MONGO_URI'):
            from mongomock.gridfs import enable_gridfs_integration
            enable_gridfs_integration()
        from data.model import Tag
        tag = Tag(name='boundary-test')
        await run_database(tag.image.put, b'image bytes', content_type='image/gif')
        try:
            contents, content_type = await run_database(
                lambda: (tag.image.read(), tag.image.content_type))
            self.assertEqual(contents, b'image bytes')
            self.assertEqual(content_type, 'image/gif')
        finally:
            await run_database(tag.image.delete)


class PersistenceArchitectureTests(unittest.TestCase):
    def test_bot_service_calls_are_awaited_and_not_executed_at_import(self):
        for path in [ROOT / 'main.py', *(ROOT / 'cogs').rglob('*.py'), *(ROOT / 'utils').rglob('*.py')]:
            tree = ast.parse(path.read_text())
            parents = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
            for node in ast.walk(tree):
                if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                        and isinstance(node.func.value, ast.Name)
                        and node.func.value.id in ('user_service', 'guild_service')):
                    continue
                with self.subTest(path=path.relative_to(ROOT), line=node.lineno):
                    self.assertIsInstance(parents[node], ast.Await)
                    ancestor = parents[node]
                    while ancestor in parents and not isinstance(ancestor, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        ancestor = parents[ancestor]
                    self.assertIsInstance(ancestor, ast.AsyncFunctionDef)
