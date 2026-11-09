"""Offline data invariants and bounded query contracts."""
import threading
from datetime import datetime, timedelta
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

import mongoengine
from mongoengine.queryset import QuerySet
from data.model import User, Cases, Case
from tests.support import connect_test_database, load_module


class DataIntegrityTests(unittest.TestCase):
    def setUp(self):
        connect_test_database()
        User.drop_collection()
        Cases.drop_collection()
        self.service = load_module('data/services/user_service.py').UserService()

    def tearDown(self):
        mongoengine.disconnect()

    def case(self, number=1, kind='WARN', points=100):
        return Case(_id=number, _type=kind, mod_id=2, mod_tag='mod',
                    reason='Original éß', punishment=str(points))

    def seed(self):
        User(_id=101, xp=123, level=4, warn_points=100).save()
        Cases(_id=101, cases=[self.case()]).save()

    def test_same_id_transfer_preserves_every_value(self):
        self.seed()
        before = (User.objects.first().to_mongo(), Cases.objects.first().to_mongo())
        with self.assertRaisesRegex(ValueError, 'different users'):
            self.service.transfer_profile(101, 101)
        self.assertEqual(before, (User.objects.first().to_mongo(), Cases.objects.first().to_mongo()))

    def concurrent(self, operations):
        barrier = threading.Barrier(2)
        def invoke(operation):
            barrier.wait(timeout=3)
            try:
                return operation()
            except ValueError as exc:
                return exc
        with ThreadPoolExecutor(2) as executor:
            results = list(executor.map(invoke, operations))
        self.assertEqual(sum(isinstance(result, ValueError) for result in results), 1)
        self.assertEqual(User.objects.get(_id=101).warn_points, 0)

    def test_concurrent_removals_never_go_negative(self):
        self.seed()
        self.concurrent([lambda: self.service.remove_points(101, 100, self.case(2, 'REMOVEPOINTS')),
                         lambda: self.service.remove_points(101, 100, self.case(3, 'REMOVEPOINTS'))])
        self.assertEqual(len(Cases.objects.get(_id=101).cases), 2)

    def test_removal_and_lift_share_balance_invariant(self):
        self.seed()
        self.concurrent([lambda: self.service.remove_points(101, 100, self.case(2, 'REMOVEPOINTS')),
                         lambda: self.service.lift_warn(101, '1', 'lift', 3, 'other')])
        cases = Cases.objects.get(_id=101).cases
        self.assertEqual(int(cases[0].lifted) + int(len(cases) == 2), 1)

    def test_rejected_deduction_preserves_history(self):
        self.seed()
        before = Cases.objects.first().to_mongo()
        with self.assertRaisesRegex(ValueError, 'negative'):
            self.service.remove_points(101, 101, self.case(2))
        self.assertEqual(before, Cases.objects.first().to_mongo())

    def test_failed_case_append_refunds_deduction(self):
        self.seed()
        with patch.object(self.service, 'add_case', side_effect=RuntimeError('write failed')):
            with self.assertRaises(RuntimeError):
                self.service.remove_points(101, 100, self.case(2))
        self.assertEqual(User.objects.first().warn_points, 100)
        self.assertEqual(len(Cases.objects.first().cases), 1)

    def test_failed_lift_write_refunds_and_preserves_case(self):
        self.seed()
        before = Cases.objects.first().to_mongo()
        original = QuerySet.update_one
        def fail_case_write(query, *args, **kwargs):
            if query._document is Cases:
                raise RuntimeError('write failed')
            return original(query, *args, **kwargs)
        with patch.object(QuerySet, 'update_one', fail_case_write):
            with self.assertRaises(RuntimeError):
                self.service.lift_warn(101, '1', 'lift', 3, 'other')
        self.assertEqual(User.objects.first().warn_points, 100)
        self.assertEqual(before, Cases.objects.first().to_mongo())

    def test_disappearing_case_refunds_lift(self):
        self.seed()
        original = self.service._deduct_points
        def deduct_and_remove(*args):
            original(*args)
            Cases.objects(_id=101).update_one(set__cases=[])
        with patch.object(self.service, '_deduct_points', deduct_and_remove):
            with self.assertRaisesRegex(RuntimeError, 'disappeared'):
                self.service.lift_warn(101, '1', 'lift', 3, 'other')
        self.assertEqual(User.objects.first().warn_points, 100)

    def test_unknown_append_outcome_does_not_refund_committed_case(self):
        self.seed()
        original = self.service.add_case
        def commit_then_fail(*args):
            original(*args)
            raise RuntimeError('lost acknowledgement')
        with patch.object(self.service, 'add_case', commit_then_fail):
            with self.assertRaises(RuntimeError):
                self.service.remove_points(101, 100, self.case(2, 'REMOVEPOINTS'))
        self.assertEqual(User.objects.first().warn_points, 0)
        self.assertEqual(len(Cases.objects.first().cases), 2)

    def history(self):
        cases = []
        for i in range(1, 151):
            case = self.case(i, 'UNMUTE' if i % 7 == 0 else 'WARN')
            case.date = datetime(2020, 1, 1) + timedelta(days=i % 20)
            case.lifted = i % 5 == 0
            case.reason = ['Éß Spam!', 'spam?', 'Temporary mute expired.'][i % 3]
            case.mod_id = 2 if i % 2 else 3
            case.mod_tag = str(case.mod_id)
            cases.append(case)
        Cases(_id=101, cases=cases).save()
        return cases

    def test_bounded_reads_preserve_order_and_exclusions(self):
        cases = self.history()
        visible = [case for case in cases if case._type != 'UNMUTE']
        self.assertEqual(self.service.case_count(101), len(visible))
        self.assertEqual([c._id for c in self.service.case_page(101, 2)],
                         [c._id for c in list(reversed(visible))[10:20]])
        expected = sorted(visible, key=lambda c: c.date)
        self.assertEqual([c._id for c in self.service.rundown(101)],
                         [c._id for c in list(reversed(expected))[:3]])
        expected = sorted([c for c in cases if c._type == 'WARN' and not c.lifted
                           and str(c._id).startswith('1')], key=lambda c: c._id, reverse=True)[:25]
        self.assertEqual([c._id for c in self.service.warning_choices(101, '1')],
                         [c._id for c in expected])
        self.assertEqual(self.service.case_count(999), 0)
        self.assertEqual(self.service.case_page(999, 1), [])
        self.assertEqual(self.service.warning_choices(101, '['), [])

    def test_queries_limit_results_in_database(self):
        self.history()
        collection = Cases._get_collection()
        original = collection.aggregate
        returned_sizes = []
        pipelines = []
        def capture(pipeline, *args, **kwargs):
            pipelines.append(pipeline)
            rows = list(original(pipeline, *args, **kwargs))
            returned_sizes.append(len(rows))
            return iter(rows)
        with patch.object(collection, 'aggregate', capture):
            self.service.rundown(101)
            self.service.warning_choices(101)
            self.service.case_page(101, 1)
        self.assertEqual(returned_sizes, [3, 25, 10])
        self.assertEqual([next(stage['$limit'] for stage in pipeline if '$limit' in stage)
                          for pipeline in pipelines], [3, 25, 10])

    def test_statistics_preserve_unicode_and_totals(self):
        from collections import Counter
        cases = self.history()
        selected = [c for c in cases if c.mod_id == 2]
        normalize = lambda text: ''.join(c for c in text.lower() if c.isalnum() or c == ' ').strip()
        expected = Counter(normalize(c.reason) for c in selected
                           if normalize(c.reason) != 'temporary mute expired')
        result = self.service.fetch_cases_by_mod(2)
        self.assertEqual(result['total'], len(selected))
        self.assertEqual(dict(result['counts']), expected)
        for keyword in ['Éß', 'SPAM', 'mute', 'absent', 'spam?']:
            selected = [c for c in cases if keyword.lower() in c.reason.lower()]
            result = self.service.fetch_cases_by_keyword(keyword)
            self.assertEqual(result['total'], len(selected))
            self.assertEqual(dict(result['counts']), Counter(c.mod_tag for c in selected))


class LazyMenuTests(unittest.IsolatedAsyncioTestCase):
    async def test_lazy_menu_loads_only_requested_uncached_page(self):
        from types import SimpleNamespace
        from unittest.mock import AsyncMock
        menu_module = load_module('utils/views/menus/menu.py',
                                  {'utils': SimpleNamespace(GIRContext=type('Context', (), {}))})
        loader = AsyncMock(side_effect=lambda page, size: [page])
        formatter = lambda ctx, entries, page, pages: (entries, page, len(pages))
        menu = menu_module.Menu(SimpleNamespace(), [], 10, formatter, False,
                                page_loader=loader, total_entries=123)
        self.assertEqual(await menu.generate_next_embed(), ([1], 1, 13))
        await menu.generate_next_embed()
        loader.assert_awaited_once_with(1, 10)
        menu.current_page = 3
        self.assertEqual(await menu.generate_next_embed(), ([3], 3, 13))
        self.assertEqual(loader.await_count, 2)
        menu.stop()

    async def test_existing_eager_menu_keeps_behavior(self):
        from types import SimpleNamespace
        menu_module = load_module('utils/views/menus/menu.py',
                                  {'utils': SimpleNamespace(GIRContext=type('Context', (), {}))})
        formatter = lambda ctx, entries, page, pages: (entries, page, len(pages))
        menu = menu_module.Menu(SimpleNamespace(), [1, 2, 3], 2, formatter, False)
        self.assertEqual(await menu.generate_next_embed(), ([1, 2], 1, 2))
        menu.current_page = 2
        self.assertEqual(await menu.generate_next_embed(), ([3], 2, 2))
        menu.stop()
