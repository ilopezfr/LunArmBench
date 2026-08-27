"""LunArmBench SuperDex proof-of-concept package."""

from __future__ import annotations

__version__ = "0.1.0"

try:
    from lunarmbench.environments.lunar_connector_env import register_env

    register_env()
except Exception:
    # SuperDex / Gymnasium may be absent in docs-only or unit-test-only contexts.
    pass
