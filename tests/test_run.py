from __future__ import annotations

from collections.abc import Sequence

import pytest

from auto_card.run import play_run, validate_deck_choice

BASE_DECK = (
    "strike",
    "strike",
    "strike",
    "strike",
    "defend",
    "defend",
    "defend",
    "heavy_strike",
    "heavy_strike",
    "fortify",
)
SECOND_BATTLE_DOUBLE_FORTIFY_DECK = (
    "strike",
    "strike",
    "strike",
    "defend",
    "defend",
    "defend",
    "heavy_strike",
    "heavy_strike",
    "fortify",
    "fortify",
)
BOSS_RUN_REWARDS = (
    "fortify",
    "defend",
    "drain_slash",
    "heavy_strike",
    "fortify",
)


class SequenceProvider:
    def __init__(
        self,
        *,
        deck_choices: Sequence[Sequence[str]],
        reward_choices: Sequence[str],
    ) -> None:
        self._deck_choices = [tuple(choice) for choice in deck_choices]
        self._reward_choices = list(reward_choices)
        self._deck_index = 0
        self._reward_index = 0

    def choose_deck(self, _request) -> tuple[str, ...]:
        choice = self._deck_choices[self._deck_index]
        self._deck_index += 1
        return choice

    def choose_reward(self, _request) -> str:
        choice = self._reward_choices[self._reward_index]
        self._reward_index += 1
        return choice


def test_validate_deck_choice_requires_exact_size_and_owned_counts() -> None:
    with pytest.raises(ValueError, match="exactly 10 cards"):
        validate_deck_choice(deck_ids=BASE_DECK[:9], collection=BASE_DECK)

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
            collection=BASE_DECK,
        )


def test_run_reaches_boss_after_five_normal_battles() -> None:
    provider = SequenceProvider(
        deck_choices=[BASE_DECK] * 6,
        reward_choices=BOSS_RUN_REWARDS,
    )

    result = play_run(
        seed=19,
        deck_chooser=provider.choose_deck,
        reward_chooser=provider.choose_reward,
    )

    assert result.final_battle_number == 6
    assert len(result.battles) == 6
    assert [record.enemy_id for record in result.battles[:5]] == [
        "priest",
        "priest",
        "guard",
        "priest",
        "priest",
    ]
    assert result.battles[-1].enemy_id == "boss"


def test_rewarded_card_is_added_to_collection_before_next_battle() -> None:
    provider = SequenceProvider(
        deck_choices=[
            BASE_DECK,
            SECOND_BATTLE_DOUBLE_FORTIFY_DECK,
            BASE_DECK,
            BASE_DECK,
            BASE_DECK,
            BASE_DECK,
        ],
        reward_choices=BOSS_RUN_REWARDS,
    )

    result = play_run(
        seed=19,
        deck_chooser=provider.choose_deck,
        reward_chooser=provider.choose_reward,
    )

    assert result.battles[0].reward_choice == "fortify"
    assert result.battles[1].deck_ids.count("fortify") == 2


def test_current_hp_carries_across_battles_but_armor_resets() -> None:
    provider = SequenceProvider(
        deck_choices=[BASE_DECK] * 6,
        reward_choices=BOSS_RUN_REWARDS,
    )

    result = play_run(
        seed=19,
        deck_chooser=provider.choose_deck,
        reward_chooser=provider.choose_reward,
    )

    first_battle = result.battles[0]
    second_battle = result.battles[1]

    assert first_battle.result.player.hp == 40
    assert first_battle.result.player.armor == 21
    assert second_battle.result.log_lines[0] == (
        "Battle start: Player 40/50 HP vs Priest 42/42 HP"
    )
    assert (
        "Start: Player HP 40/50, Armor 0 | Priest HP 42/42, Armor 0"
        in second_battle.result.log_lines
    )


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
        seed=0,
        deck_chooser=choose_deck,
        reward_chooser=choose_reward,
    )

    assert result.outcome == "defeat"
    assert result.final_battle_number == 1
    assert reward_calls == 0
    assert result.battles[0].reward_choice is None


def test_run_is_reproducible_for_same_seed_and_choices() -> None:
    first_provider = SequenceProvider(
        deck_choices=[BASE_DECK] * 6,
        reward_choices=BOSS_RUN_REWARDS,
    )
    second_provider = SequenceProvider(
        deck_choices=[BASE_DECK] * 6,
        reward_choices=BOSS_RUN_REWARDS,
    )

    first = play_run(
        seed=19,
        deck_chooser=first_provider.choose_deck,
        reward_chooser=first_provider.choose_reward,
    )
    second = play_run(
        seed=19,
        deck_chooser=second_provider.choose_deck,
        reward_chooser=second_provider.choose_reward,
    )

    assert first == second


def test_reward_options_are_unique_and_duplicate_rewards_accumulate() -> None:
    provider = SequenceProvider(
        deck_choices=[BASE_DECK] * 6,
        reward_choices=BOSS_RUN_REWARDS,
    )

    result = play_run(
        seed=19,
        deck_chooser=provider.choose_deck,
        reward_chooser=provider.choose_reward,
    )

    for record in result.battles[:-1]:
        assert len(record.reward_options) == 3
        assert len(set(record.reward_options)) == 3

    assert result.final_collection.count("fortify") == 3
