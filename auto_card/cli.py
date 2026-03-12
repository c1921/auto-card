from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from auto_card.battle import simulate_battle
from auto_card.content import (
    CARDS,
    CARD_ORDER,
    DEFAULT_ROLE,
    ENEMIES,
    ROLES,
    RUN_DECK_SIZE,
    validate_content,
)
from auto_card.run import (
    DeckChoiceRequest,
    RewardChoiceRequest,
    play_run,
    validate_deck_choice,
    validate_reward_choice,
)


class InteractiveChoiceProvider:
    def choose_deck(self, request: DeckChoiceRequest) -> tuple[str, ...]:
        print(
            (
                f"Build deck for battle {request.battle_number}/{request.total_battles} "
                f"against {request.enemy.name} [{request.enemy.id}] "
                f"as {request.role.name} [{request.role.id}]."
            )
        )
        print(f"Current HP: {request.current_hp}/{request.max_hp}")
        print("Collection:")
        for line in _format_collection_lines(request.collection):
            print(f"  {line}")

        while True:
            raw = input(
                f"Enter exactly {RUN_DECK_SIZE} card ids separated by spaces: "
            ).strip()
            deck_ids = tuple(raw.split())
            try:
                return validate_deck_choice(
                    deck_ids=deck_ids, collection=request.collection
                )
            except ValueError as exc:
                print(f"Invalid deck: {exc}")

    def choose_reward(self, request: RewardChoiceRequest) -> str:
        print(
            (
                f"Choose a reward after battle {request.battle_number} "
                f"against {request.enemy.name} for {request.role.name}:"
            )
        )
        for index, card_id in enumerate(request.options, start=1):
            card = CARDS[card_id]
            print(f"  {index}. {card.name} [{card_id}]")

        while True:
            raw = input("Enter 1, 2, or 3: ").strip()
            if raw not in {"1", "2", "3"}:
                print("Invalid reward: enter 1, 2, or 3.")
                continue

            chosen_card_id = request.options[int(raw) - 1]
            try:
                return validate_reward_choice(
                    reward_choice=chosen_card_id,
                    options=request.options,
                )
            except ValueError as exc:
                print(f"Invalid reward: {exc}")


class ScriptedChoiceProvider:
    def __init__(
        self,
        *,
        deck_choices: Sequence[Sequence[str]],
        reward_choices: Sequence[str],
        role_id: str | None = None,
    ) -> None:
        self._deck_choices = [tuple(choice) for choice in deck_choices]
        self._reward_choices = list(reward_choices)
        self._deck_index = 0
        self._reward_index = 0
        self.role_id = role_id

    def choose_deck(self, request: DeckChoiceRequest) -> tuple[str, ...]:
        if self._deck_index >= len(self._deck_choices):
            raise ValueError(
                "Script is missing a deck choice for "
                f"battle {request.battle_number}."
            )
        deck_ids = self._deck_choices[self._deck_index]
        self._deck_index += 1
        return deck_ids

    def choose_reward(self, request: RewardChoiceRequest) -> str:
        if self._reward_index >= len(self._reward_choices):
            raise ValueError(
                "Script is missing a reward choice for "
                f"battle {request.battle_number}."
            )
        reward_choice = self._reward_choices[self._reward_index]
        self._reward_index += 1
        return reward_choice


def build_run_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="main.py",
        description="Run a full rogue-like card game session.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=0,
        help="Global RNG seed for the whole run.",
    )
    parser.add_argument(
        "--role",
        choices=sorted(ROLES),
        help="Role to start with.",
    )
    parser.add_argument(
        "--script",
        type=Path,
        help="JSON file with optional role and scripted deck/reward choices.",
    )
    return parser


def build_ui_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="main.py ui",
        description="Run the Textual terminal UI for the rogue-like card game MVP.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=0,
        help="Global RNG seed for the whole run.",
    )
    parser.add_argument(
        "--role",
        choices=sorted(ROLES),
        help="Role to preselect before entering the UI.",
    )
    return parser


def build_battle_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="main.py battle",
        description="Run a single rogue-like card battle simulation.",
    )
    parser.add_argument(
        "--enemy",
        choices=sorted(ENEMIES),
        default="bruiser",
        help="Enemy template to fight.",
    )
    parser.add_argument(
        "--role",
        choices=sorted(ROLES),
        help="Role whose starting deck and HP should be used.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=0,
        help="RNG seed used for deck shuffling and enemy actions.",
    )
    return parser


def build_validate_content_parser() -> argparse.ArgumentParser:
    return argparse.ArgumentParser(
        prog="main.py validate-content",
        description="Validate all TOML-driven game content.",
    )


def main(argv: Sequence[str] | None = None) -> int:
    args_list = list(argv) if argv is not None else sys.argv[1:]
    command = args_list[0] if args_list else None

    try:
        if command == "battle":
            return _run_battle_mode(args_list[1:])
        if command == "ui":
            return _run_ui_mode(args_list[1:])
        if command == "run":
            return _run_session_mode(args_list[1:])
        if command == "validate-content":
            return _run_validate_content_mode(args_list[1:])
        return _run_session_mode(args_list)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


def _run_battle_mode(argv: Sequence[str]) -> int:
    args = build_battle_parser().parse_args(argv)
    result = simulate_battle(
        enemy_id=args.enemy,
        seed=args.seed,
        role_id=args.role or DEFAULT_ROLE.id,
    )
    for line in result.log_lines:
        print(line)
    return 0


def _run_ui_mode(argv: Sequence[str]) -> int:
    from auto_card.ui import TextualCardApp

    args = build_ui_parser().parse_args(argv)
    app = TextualCardApp(seed=args.seed, role_id=args.role)
    app.run()
    return 0


def _run_session_mode(argv: Sequence[str]) -> int:
    args = build_run_parser().parse_args(argv)
    provider = _build_choice_provider(script_path=args.script)
    role_id = args.role or getattr(provider, "role_id", None) or DEFAULT_ROLE.id
    play_run(
        seed=args.seed,
        role_id=role_id,
        deck_chooser=provider.choose_deck,
        reward_chooser=provider.choose_reward,
        log_emitter=print,
    )
    return 0


def _run_validate_content_mode(argv: Sequence[str]) -> int:
    build_validate_content_parser().parse_args(argv)
    validate_content()
    print("Content validation passed.")
    return 0


def _build_choice_provider(script_path: Path | None) -> Any:
    if script_path is None:
        return InteractiveChoiceProvider()
    return _load_scripted_choice_provider(script_path)


def _load_scripted_choice_provider(script_path: Path) -> ScriptedChoiceProvider:
    try:
        payload = json.loads(script_path.read_text())
    except FileNotFoundError as exc:
        raise ValueError(f"Script file not found: {script_path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Script file is not valid JSON: {script_path}"
        ) from exc

    if not isinstance(payload, dict):
        raise ValueError("Script root must be a JSON object.")

    deck_choices = _parse_deck_choices(payload.get("deck_choices"))
    reward_choices = _parse_reward_choices(payload.get("reward_choices"))
    role_id = _parse_role_id(payload.get("role"))
    return ScriptedChoiceProvider(
        deck_choices=deck_choices,
        reward_choices=reward_choices,
        role_id=role_id,
    )


def _parse_deck_choices(raw_value: Any) -> list[tuple[str, ...]]:
    if raw_value is None:
        raise ValueError("Script must define 'deck_choices'.")
    if not isinstance(raw_value, list):
        raise ValueError("'deck_choices' must be a JSON array.")

    parsed: list[tuple[str, ...]] = []
    for index, entry in enumerate(raw_value, start=1):
        if not isinstance(entry, list) or not all(
            isinstance(card_id, str) for card_id in entry
        ):
            raise ValueError(
                f"'deck_choices[{index - 1}]' must be an array of card ids."
            )
        parsed.append(tuple(entry))
    return parsed


def _parse_reward_choices(raw_value: Any) -> list[str]:
    if raw_value is None:
        raise ValueError("Script must define 'reward_choices'.")
    if not isinstance(raw_value, list) or not all(
        isinstance(card_id, str) for card_id in raw_value
    ):
        raise ValueError("'reward_choices' must be an array of card ids.")
    return list(raw_value)


def _parse_role_id(raw_value: Any) -> str | None:
    if raw_value is None:
        return None
    if not isinstance(raw_value, str):
        raise ValueError("'role' must be a string if provided.")
    if raw_value not in ROLES:
        valid = ", ".join(sorted(ROLES))
        raise ValueError(f"'role' must be one of: {valid}.")
    return raw_value


def _format_collection_lines(collection: Sequence[str]) -> list[str]:
    counts = Counter(collection)
    return [
        f"{card_id}: {CARDS[card_id].name} x{counts[card_id]}"
        for card_id in CARD_ORDER
        if counts.get(card_id, 0)
    ]
