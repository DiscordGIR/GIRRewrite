"""Load isolated legacy modules without starting the bot or reading credentials."""
import importlib.util
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load_module(relative_path, stubs=None):
    spec = importlib.util.spec_from_file_location(
        "test_" + relative_path.replace("/", "_").replace(".py", ""),
        ROOT / relative_path,
    )
    module = importlib.util.module_from_spec(spec)
    with patch.dict("sys.modules", stubs or {}):
        spec.loader.exec_module(module)
    return module
