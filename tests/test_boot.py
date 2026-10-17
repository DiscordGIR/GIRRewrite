import subprocess
import sys
import unittest
from tests.support import ROOT


class BootTests(unittest.TestCase):
    def test_every_extension_loads_and_resources_close_without_live_services(self):
        result = subprocess.run([sys.executable, "-m", "tests.boot_smoke"], cwd=ROOT,
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
