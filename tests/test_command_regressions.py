import subprocess
import sys
import unittest
from tests.support import ROOT


class CommandRegressionTests(unittest.TestCase):
    def test_reported_live_failures_in_isolated_bot(self):
        result = subprocess.run([sys.executable, '-m', 'tests.command_regressions'],
                                cwd=ROOT, capture_output=True, text=True, timeout=40)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
