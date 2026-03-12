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
from auto_card.i18n import _, extract_cli_language, set_language
from auto_card.presentation import get_card_name, get_enemy_name, get_role_name
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
            _(
                "Build deck for battle {battle_number}/{total_battles} "
                "against {enemy_name} [{enemy_id}] "
                "as {role_name} [{role_id}]."
            ).format(
                battle_number=request.battle_number,
                total_battles=request.total_battles,
                enemy_name=get_enemy_name(request.enemy),
                enemy_id=request.enemy.id,
                role_name=get_role_name(request.role),
                role_id=request.role.id,
            )
        )
        print(
            _("Current HP: {current_hp}/{max_hp}").format(
                current_hp=request.current_hp,
                max_hp=request.max_hp,
            )
        )
        print(_("Collection:"))
        for line in _format_collection_lines(request.collection):
            print(f"  {line}")

        while True:
            raw = input(
                _("Enter exactly {deck_size} card ids separated by spaces: ").format(
                    deck_size=RUN_DECK_SIZE
                )
            ).strip()
            deck_ids = tuple(raw.split())
            try:
                return validate_deck_choice(
                    deck_ids=deck_ids, collection=request.collection
                )
            except ValueError as exc:
                print(_("Invalid deck: {error}").format(error=exc))

    def choose_reward(self, request: RewardChoiceRequest) -> str:
        print(
            _(
                "Choose a reward after battle {battle_number} "
                "against {enemy_name} for {role_name}:"
            ).format(
                battle_number=request.battle_number,
                enemy_name=get_enemy_name(request.enemy),
                role_name=get_role_name(request.role),
            )
        )
        for index, card_id in enumerate(request.options, start=1):
            card = CARDS[card_id]
            print(
                _("  {index}. {card_name} [{card_id}]").format(
                    index=index,
                    card_name=get_card_name(card),
                    card_id=card_id,
                )
            )

        while True:
            raw = input(_("Enter 1, 2, or 3: ")).strip()
            if raw not in {"1", "2", "3"}:
                print(_("Invalid reward: enter 1, 2, or 3."))
                continue

            chosen_card_id = request.options[int(raw) - 1]
            try:
                return validate_reward_choice(
                    reward_choice=chosen_card_id,
                    options=request.options,
                )
            except ValueError as exc:
                print(_("Invalid reward: {error}").format(error=exc))


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
                _("Script is missing a deck choice for battle {battle_number}.").format(
                    battle_number=request.battle_number
                )
            )
        deck_ids = self._deck_choices[self._deck_index]
        self._deck_index += 1
        return deck_ids

    def choose_reward(self, request: RewardChoiceRequest) -> str:
        if self._reward_index >= len(self._reward_choices):
            raise ValueError(
                _(
                    "Script is missing a reward choice for battle {battle_number}."
                ).format(battle_number=request.battle_number)
            )
        reward_choice = self._reward_choices[self._reward_index]
        self._reward_index += 1
        return reward_choice


def _add_language_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--lang",
        choices=["en", "zh_CN"],
        default=None,
        help=_("Language to use for the current run."),
    )


def build_run_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="main.py",
        description=_("Run a full rogue-like card game session."),
    )
    _add_language_argument(parser)
    parser.add_argument(
        "--seed",
        type=int,
        default=0,
        help=_("Global RNG seed for the whole run."),
    )
    parser.add_argument(
        "--role",
        choices=sorted(ROLES),
        help=_("Role to start with."),
    )
    parser.add_argument(
        "--script",
        type=Path,
        help=_("JSON file with optional role and scripted deck/reward choices."),
    )
    return parser


def build_ui_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="main.py ui",
        description=_("Run the Textual terminal UI for the rogue-like card game MVP."),
    )
    _add_language_argument(parser)
    parser.add_argument(
        "--seed",
        type=int,
        default=0,
        help=_("Global RNG seed for the whole run."),
    )
    parser.add_argument(
        "--role",
        choices=sorted(ROLES),
        help=_("Role to preselect before entering the UI."),
    )
    return parser


def build_battle_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="main.py battle",
        description=_("Run a single rogue-like card battle simulation."),
    )
    _add_language_argument(parser)
    parser.add_argument(
        "--enemy",
        choices=sorted(ENEMIES),
        default="bruiser",
        help=_("Enemy template to fight."),
    )
    parser.add_argument(
        "--role",
        choices=sorted(ROLES),
        help=_("Role whose starting deck and HP should be used."),
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=0,
        help=_("RNG seed used for deck shuffling and enemy actions."),
    )
    return parser


def build_validate_content_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="main.py validate-content",
        description=_("Validate all TOML-driven game content."),
    )
    _add_language_argument(parser)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args_list = list(argv) if argv is not None else sys.argv[1:]
    set_language(extract_cli_language(args_list))
    command, command_argv = _split_command(args_list)

    try:
        if command == "battle":
            return _run_battle_mode(command_argv)
        if command == "ui":
            return _run_ui_mode(command_argv)
        if command == "run":
            return _run_session_mode(command_argv)
        if command == "validate-content":
            return _run_validate_content_mode(command_argv)
        return _run_session_mode(args_list)
    except Exception as exc:
        print(_("Error: {error}").format(error=exc), file=sys.stderr)
        return 1


def _run_battle_mode(argv: Sequence[str]) -> int:
    args = build_battle_parser().parse_args(argv)
    set_language(args.lang)
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
    set_language(args.lang)
    app = TextualCardApp(seed=args.seed, role_id=args.role, language=args.lang)
    app.run()
    return 0


def _run_session_mode(argv: Sequence[str]) -> int:
    args = build_run_parser().parse_args(argv)
    set_language(args.lang)
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
    args = build_validate_content_parser().parse_args(argv)
    set_language(args.lang)
    validate_content()
    print(_("Content validation passed."))
    return 0


def _build_choice_provider(script_path: Path | None) -> Any:
    if script_path is None:
        return InteractiveChoiceProvider()
    return _load_scripted_choice_provider(script_path)


def _load_scripted_choice_provider(script_path: Path) -> ScriptedChoiceProvider:
    try:
        payload = json.loads(script_path.read_text())
    except FileNotFoundError as exc:
        raise ValueError(
            _("Script file not found: {script_path}").format(script_path=script_path)
        ) from exc
    except json.JSONDecodeError as exc:
        raise ValueError(
            _("Script file is not valid JSON: {script_path}").format(
                script_path=script_path
            )
        ) from exc

    if not isinstance(payload, dict):
        raise ValueError(_("Script root must be a JSON object."))

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
        raise ValueError(_("Script must define 'deck_choices'."))
    if not isinstance(raw_value, list):
        raise ValueError(_("'deck_choices' must be a JSON array."))

    parsed: list[tuple[str, ...]] = []
    for index, entry in enumerate(raw_value, start=1):
        if not isinstance(entry, list) or not all(
            isinstance(card_id, str) for card_id in entry
        ):
            raise ValueError(
                _("'deck_choices[{index}]' must be an array of card ids.").format(
                    index=index - 1
                )
            )
        parsed.append(tuple(entry))
    return parsed


def _parse_reward_choices(raw_value: Any) -> list[str]:
    if raw_value is None:
        raise ValueError(_("Script must define 'reward_choices'."))
    if not isinstance(raw_value, list) or not all(
        isinstance(card_id, str) for card_id in raw_value
    ):
        raise ValueError(_("'reward_choices' must be an array of card ids."))
    return list(raw_value)


def _parse_role_id(raw_value: Any) -> str | None:
    if raw_value is None:
        return None
    if not isinstance(raw_value, str):
        raise ValueError(_("'role' must be a string if provided."))
    if raw_value not in ROLES:
        valid = ", ".join(sorted(ROLES))
        raise ValueError(_("'role' must be one of: {valid}.").format(valid=valid))
    return raw_value


def _format_collection_lines(collection: Sequence[str]) -> list[str]:
    counts = Counter(collection)
    return [
        _("{card_id}: {card_name} x{count}").format(
            card_id=card_id,
            card_name=get_card_name(CARDS[card_id]),
            count=counts[card_id],
        )
        for card_id in CARD_ORDER
        if counts.get(card_id, 0)
    ]


def _split_command(argv: list[str]) -> tuple[str | None, list[str]]:
    for index, argument in enumerate(argv):
        if argument in {"battle", "ui", "run", "validate-content"}:
            return argument, argv[:index] + argv[index + 1 :]
    return None, argv
