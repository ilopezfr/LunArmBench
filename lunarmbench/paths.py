"""Filesystem helpers for the SuperDex POC."""

from __future__ import annotations

import os
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_ROOT.parent
THIRD_PARTY = REPO_ROOT / "third_party" / "project_superdex"
DEFAULT_ASSETS = THIRD_PARTY / "assets"
CONFIGS_DIR = REPO_ROOT / "configs"
RESULTS_DIR = REPO_ROOT / "results"


def ensure_assets_path() -> Path:
    """Point SuperDex at the cloned asset tree if the caller has not already."""
    assets = Path(os.environ.get("SUPERDEX_ASSETS_PATH", DEFAULT_ASSETS))
    os.environ["SUPERDEX_ASSETS_PATH"] = str(assets)
    if not assets.exists():
        raise FileNotFoundError(
            f"SUPERDEX_ASSETS_PATH does not exist: {assets}. "
            "Clone facebookresearch/project_superdex (stable) into third_party/."
        )
    return assets
