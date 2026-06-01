import importlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def module_names() -> list[str]:
    modules = [f"src.{path.stem}" for path in sorted((ROOT / "src").glob("*.py"))]
    modules.extend(
        f"src.models.{path.stem}" for path in sorted((ROOT / "src" / "models").glob("*.py"))
    )
    return modules


@pytest.mark.parametrize("module_name", module_names())
def test_src_modules_import(module_name: str) -> None:
    importlib.import_module(module_name)
