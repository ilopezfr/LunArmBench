"""Confirm scene gravity can be set to Earth and Moon values."""

from __future__ import annotations

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault(
    "SUPERDEX_ASSETS_PATH", str(ROOT / "third_party" / "project_superdex" / "assets")
)


def main() -> int:
    import superdex.physics as physics

    physics.initialize(num_worker_threads=0)
    scene = physics.create_scene("gravity_sanity")
    results = {}
    for name, g in (("earth", 9.81), ("moon", 1.62)):
        scene.set_gravity([0.0, 0.0, -g])
        got = list(scene.get_gravity())
        results[name] = {
            "requested": [0.0, 0.0, -g],
            "reported": got,
            "ok": abs(got[2] + g) < 1e-6,
        }
    physics.destroy_scene(scene)
    physics.shutdown()
    print(json.dumps(results, indent=2))
    return 0 if all(v["ok"] for v in results.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
