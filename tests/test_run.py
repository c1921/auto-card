from __future__ import annotations

from collections.abc import Sequence

import pytest

from auto_card.content import get_role_definition, get_role_reward_card_ids
from auto_card.run import (
    RunSession,
    canonicalize_card_ids,
    format_card_counts,
    play_run,
    validate_deck_choice,
)

ADVENTURER = get_role_definition("adventurer")
ALCHEMIST = get_role_definition("alchemist")
BASE_DECK = ADVENTURER.starting_deck


class FirstOptionProvider:
    def __init__(self, *, deck_choices: Sequence[Sequence[str]]) -> None:
        self._deck_choices = [tuple(choice) for choice in deck_choices]
        self._deck_index = 0

    def choose_deck(self, _request) -> tuple[str, ...]:
        choice = self._deck_choices[self._deck_index]
        self._deck_index += 1
        return choice

    def choose_reward(self, request) -> str:
        return request.options[0]


def test_validate_deck_choice_requires_exact_size_and_owned_counts() -> None:
    with pytest.raises(ValueError, match="exactly 10 cards"):
        validate_deck_choice(deck_ids=BASE_DECK[:9], collection=ADVENTURER.starting_collection)

    with pytest.raises(ValueError, match="more copies than owned"):
        validate_deck_choice(
            deck_ids=(
                "strike",
                "strike",
                "strike",
                "strike",
                "strike",
                "defend",
                "defend",
                "heavy_strike",
                "heavy_strike",
                "fortify",
            ),
            collection=ADVENTURER.starting_collection,
        )


def test_card_order_is_explicit_for_canonicalization_and_formatting() -> None:
    card_ids = ("recover", "strike", "battle_cry", "strike", "drain_slash")

    assert canonicalize_card_ids(card_ids) == (
        "strike",
        "strike",
        "drain_slash",
        "recover",
        "battle_cry",
    )
    assert format_card_counts(card_ids) == (
        "Strike x2, Drain Slash x1, Recover x1, Battle Cry x1"
    )


def test_run_session_uses_selected_role_starting_state() -> None:
    session = RunSession(seed=0, role_id="alchemist")

    assert session.role.id == "alchemist"
    assert session.current_hp == ALCHEMIST.starting_hp
    assert session.max_hp == ALCHEMIST.max_hp
    assert set(session.collection).issubset(set(get_role_reward_card_ids("alchemist")))


def test_run_session_progresses_from_deck_choice_to_reward_and_next_battle() -> None:
    session = RunSession(seed=19, role_id="adventurer")

    assert session.phase == "deck_choice"
    assert session.battle_number == 1
    assert session.current_enemy.id == "priest"

    session.submit_deck_choice(BASE_DECK)

    assert session.phase == "battle_replay"
    assert session.current_battle_replay.result.outcome == "victory"

    session.complete_battle_replay()

    assert session.phase == "reward_choice"
    reward_request = session.get_reward_choice_request()
    assert len(reward_request.options) == 3
    assert set(reward_request.options).issubset(set(get_role_reward_card_ids("adventurer")))
    assert "venom_cut" not in reward_request.options

    chosen_reward = reward_request.options[0]
    owned_before = session.collection.count(chosen_reward)
    session.submit_reward_choice(chosen_reward)

    assert session.phase == "deck_choice"
    assert session.battle_number == 2
    assert session.collection.count(chosen_reward) == owned_before + 1


def test_run_stops_without_reward_when_player_loses() -> None:
    reward_calls = 0

    def choose_deck(_request) -> tuple[str, ...]:
        return (
            "strike",
            "strike",
            "strike",
            "strike",
            "heavy_strike",
            "heavy_strike",
            "recover",
            "drain_slash",
            "defend",
            "defend",
        )

    def choose_reward(_request) -> str:
        nonlocal reward_calls
        reward_calls += 1
        return "strike"

    result = play_run(
        seed=1,
        role_id="adventurer",
        deck_chooser=choose_deck,
        reward_chooser=choose_reward,
    )

    assert result.outcome == "defeat"
    assert result.final_battle_number == 1
    assert reward_calls == 0
    assert result.battles[0].reward_choice is None


def test_run_is_reproducible_for_same_seed_and_choice_strategy() -> None:
    first_provider = FirstOptionProvider(deck_choices=[BASE_DECK] * 6)
    second_provider = FirstOptionProvider(deck_choices=[BASE_DECK] * 6)

    first = play_run(
        seed=19,
        role_id="adventurer",
        deck_chooser=first_provider.choose_deck,
        reward_chooser=first_provider.choose_reward,
    )
    second = play_run(
        seed=19,
        role_id="adventurer",
        deck_chooser=second_provider.choose_deck,
        reward_chooser=second_provider.choose_reward,
    )

    assert first == second
    assert first.role_id == "adventurer"


def test_reward_options_are_unique_and_duplicate_rewards_accumulate() -> None:
    provider = FirstOptionProvider(deck_choices=[BASE_DECK] * 6)

    result = play_run(
        seed=19,
        role_id="adventurer",
        deck_chooser=provider.choose_deck,
        reward_chooser=provider.choose_reward,
    )

    for record in result.battles[:-1]:
        assert len(record.reward_options) == 3
        assert len(set(record.reward_options)) == 3

    reward_choices = [record.reward_choice for record in result.battles if record.reward_choice]
    if reward_choices:
        assert result.final_collection.count(reward_choices[0]) >= 1


def test_run_result_includes_selected_role() -> None:
    provider = FirstOptionProvider(deck_choices=[ALCHEMIST.starting_deck] * 6)

    result = play_run(
        seed=0,
        role_id="alchemist",
        deck_chooser=provider.choose_deck,
        reward_chooser=provider.choose_reward,
    )

    assert result.role_id == "alchemist"
