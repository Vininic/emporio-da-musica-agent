from pathlib import Path

import pytest

from emporio.store import Store

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def store() -> Store:
    return Store(ROOT / "data" / "raw")
