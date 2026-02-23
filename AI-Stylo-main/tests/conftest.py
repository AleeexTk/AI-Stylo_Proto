import sys
from pathlib import Path


def _detect_project_root() -> Path:
    current = Path(__file__).resolve()
    for base in [current.parent, *current.parents]:
        if (base / "apps").is_dir():
            return base
    raise RuntimeError("Cannot locate project root containing 'apps' directory")


ROOT = _detect_project_root()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
