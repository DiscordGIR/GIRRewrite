"""Portable locations for dashboard-managed runtime files."""
import os
from pathlib import Path


def runtime_data_file(filename: str) -> Path:
    """Return a runtime data path, allowing deployments to override the directory."""
    configured = os.environ.get("GIR_DATA_DIR")
    directory = Path(configured).expanduser() if configured else Path.home() / ".gir" / "data"
    return directory / filename
