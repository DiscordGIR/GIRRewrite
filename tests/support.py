"""Load isolated legacy modules without starting the bot or reading credentials."""
import importlib.util
import os
from pathlib import Path
from urllib.parse import urlparse
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def connect_test_database():
    import mongoengine
    import mongomock
    uri = os.environ.get("GIR_TEST_MONGO_URI")
    if uri:
        if urlparse(uri).path not in ("", "/", "/gir_tests"):
            raise ValueError("Integration tests may only use the gir_tests database")
        return mongoengine.connect("gir_tests", host=uri, uuidRepresentation="standard")
    return mongoengine.connect("gir_tests", mongo_client_class=mongomock.MongoClient,
                               uuidRepresentation="standard")


def load_module(relative_path, stubs=None, module_name=None):
    spec = importlib.util.spec_from_file_location(
        module_name or "test_" + relative_path.replace("/", "_").replace(".py", ""),
        ROOT / relative_path,
    )
    module = importlib.util.module_from_spec(spec)
    with patch.dict("sys.modules", stubs or {}):
        spec.loader.exec_module(module)
    return module
