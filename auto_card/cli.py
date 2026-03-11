from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from auto_card.battle import simulate_battle
from auto_card.content import ENEMIES


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a single rogue-like card battle simulation."
    )
    parser.add_argument(
        "--enemy",
        choices=sorted(ENEMIES),
        default="bruiser",
        help="Enemy template to fight.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=0,
        help="RNG seed used for deck shuffling and enemy actions.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        result = simulate_battle(enemy_id=args.enemy, seed=args.seed)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    for line in result.log_lines:
        print(line)
    return 0
