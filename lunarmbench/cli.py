"""Thin CLI entry for the SuperDex POC."""

from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lunarmbench-run")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_ep = sub.add_parser("episode", help="Run one connector insertion episode")
    p_ep.add_argument("--config", default="nominal_moon.yaml")
    p_ep.add_argument("--oracle", action=argparse.BooleanOptionalAction, default=True)
    p_ep.add_argument("--seed", type=int, default=None)

    p_sw = sub.add_parser("sweep", help="Run the compact experiment matrix")
    p_sw.add_argument("--reps", type=int, default=5)
    p_sw.add_argument("--name", default="connector_v0")

    args = parser.parse_args(argv)
    if args.cmd == "episode":
        from scripts.run_connector import main as episode_main

        sys.argv = ["run_connector", "--config", args.config]
        if args.oracle:
            sys.argv.append("--oracle")
        else:
            sys.argv.append("--no-oracle")
        if args.seed is not None:
            sys.argv.extend(["--seed", str(args.seed)])
        return episode_main()
    from scripts.run_sweep import main as sweep_main

    sys.argv = ["run_sweep", "--reps", str(args.reps), "--name", args.name]
    return sweep_main()


if __name__ == "__main__":
    raise SystemExit(main())
