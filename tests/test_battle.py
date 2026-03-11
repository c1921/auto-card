from __future__ import annotations

import pytest

from auto_card.battle import (
    apply_damage,
    heal_combatant,
    resolve_card,
    run_battle,
    run_battle_replay,
    simulate_battle,
)
from auto_card.content import CARDS, TEST_DECK, get_enemy_definition
from auto_card.models import Combatant, EnemyActionKind, EnemyDefinition


def constant_action(action: EnemyActionKind):
    def pick(_enemy: EnemyDefinition, _rng) -> EnemyActionKind:
        return action

    return pick


def make_enemy(
    *,
    enemy_id: str,
    name: str,
    max_hp: int,
    attack_value: int = 0,
    defend_value: int = 0,
    heal_value: int = 0,
) -> EnemyDefinition:
    return EnemyDefinition(
        id=enemy_id,
        name=name,
        max_hp=max_hp,
        attack_weight=1,
        defend_weight=1,
        heal_weight=1,
        attack_value=attack_value,
        defend_value=defend_value,
        heal_value=heal_value,
    )


def find_line_index(lines: tuple[str, ...], needle: str) -> int:
    for index, line in enumerate(lines):
        if needle in line:
            return index
    raise AssertionError(f"Could not find '{needle}' in battle log.")


def test_damage_consumes_armor_before_hp() -> None:
    target = Combatant(name="Target", max_hp=50, hp=50, armor=5)

    report = apply_damage(target, 8)

    assert report.blocked == 5
    assert report.hp_lost == 3
    assert target.armor == 0
    assert target.hp == 47


def test_healing_caps_at_max_hp() -> None:
    target = Combatant(name="Target", max_hp=50, hp=49, armor=0)

    report = heal_combatant(target, 3)

    assert report.restored == 1
    assert target.hp == 50


def test_drain_slash_logs_damage_before_heal() -> None:
    player = Combatant(name="Player", max_hp=50, hp=49, armor=0)
    enemy = Combatant(name="Dummy", max_hp=10, hp=10, armor=0)
    log_lines: list[str] = []

    resolve_card(
        card=CARDS["drain_slash"],
        player=player,
        enemy=enemy,
        log_lines=log_lines,
    )

    assert enemy.hp == 6
    assert player.hp == 50
    damage_index = find_line_index(tuple(log_lines), "deals 4 damage")
    heal_index = find_line_index(tuple(log_lines), "heals Player for 1 HP")
    assert damage_index < heal_index


def test_heavy_strike_blocks_following_draw_until_next_turn() -> None:
    enemy = make_enemy(
        enemy_id="training_dummy",
        name="Training Dummy",
        max_hp=22,
        attack_value=0,
    )

    result = run_battle(
        deck_ids=["strike", "heavy_strike"],
        enemy_definition=enemy,
        seed=0,
        enemy_action_picker=constant_action("attack"),
        shuffle_deck=False,
    )

    begin_index = find_line_index(result.log_lines, "begins charging Heavy Strike (1/3)")
    continue_two_index = find_line_index(
        result.log_lines, "continues charging Heavy Strike (2/3)"
    )
    continue_three_index = find_line_index(
        result.log_lines, "continues charging Heavy Strike (3/3)"
    )
    strike_index = find_line_index(result.log_lines, "Player flips Strike.")

    assert result.outcome == "victory"
    assert result.turns == 4
    assert begin_index < continue_two_index < continue_three_index < strike_index


def test_fortify_blocks_following_draw_until_next_turn() -> None:
    enemy = make_enemy(
        enemy_id="slow_dummy",
        name="Slow Dummy",
        max_hp=6,
        attack_value=0,
    )

    result = run_battle(
        deck_ids=["strike", "fortify"],
        enemy_definition=enemy,
        seed=0,
        enemy_action_picker=constant_action("attack"),
        shuffle_deck=False,
    )

    begin_index = find_line_index(result.log_lines, "begins charging Fortify (1/2)")
    resolve_index = find_line_index(
        result.log_lines, "continues charging Fortify (2/2)"
    )
    strike_index = find_line_index(result.log_lines, "Player flips Strike.")

    assert result.outcome == "victory"
    assert result.turns == 3
    assert begin_index < resolve_index < strike_index


def test_discard_pile_is_reshuffled_when_draw_pile_is_empty() -> None:
    enemy = make_enemy(
        enemy_id="reshuffle_dummy",
        name="Reshuffle Dummy",
        max_hp=12,
        attack_value=0,
    )

    result = run_battle(
        deck_ids=["strike"],
        enemy_definition=enemy,
        seed=0,
        enemy_action_picker=constant_action("attack"),
        shuffle_deck=False,
    )

    assert result.outcome == "victory"
    assert result.turns == 2
    assert any(
        "reshuffles discard pile into draw pile" in line
        for line in result.log_lines
    )


def test_player_loses_when_both_sides_die_on_same_turn() -> None:
    enemy = make_enemy(
        enemy_id="berserker",
        name="Berserker",
        max_hp=6,
        attack_value=50,
    )

    result = run_battle(
        deck_ids=["strike"],
        enemy_definition=enemy,
        seed=0,
        enemy_action_picker=constant_action("attack"),
        shuffle_deck=False,
    )

    assert result.outcome == "defeat"
    assert result.player.hp == 0
    assert result.enemy.hp == 0
    assert any(
        "still acts before the end-of-turn death check" in line
        for line in result.log_lines
    )


def test_simulate_battle_is_reproducible_for_same_seed() -> None:
    first = simulate_battle("bruiser", seed=0)
    second = simulate_battle("bruiser", seed=0)

    assert first == second


def test_run_battle_accepts_custom_starting_hp() -> None:
    enemy = make_enemy(
        enemy_id="training_dummy",
        name="Training Dummy",
        max_hp=6,
        attack_value=0,
    )

    result = run_battle(
        deck_ids=["strike"],
        enemy_definition=enemy,
        seed=0,
        player_start_hp=17,
        enemy_action_picker=constant_action("attack"),
        shuffle_deck=False,
    )

    assert result.log_lines[0] == "Battle start: Player 17/50 HP vs Training Dummy 6/6 HP"


def test_run_battle_rejects_invalid_starting_hp() -> None:
    enemy = make_enemy(
        enemy_id="training_dummy",
        name="Training Dummy",
        max_hp=6,
        attack_value=0,
    )

    with pytest.raises(ValueError, match="Player starting HP must be between 1 and 50"):
        run_battle(
            deck_ids=["strike"],
            enemy_definition=enemy,
            seed=0,
            player_start_hp=0,
            enemy_action_picker=constant_action("attack"),
            shuffle_deck=False,
        )


def test_run_battle_replay_matches_final_result_and_turn_frames() -> None:
    enemy = make_enemy(
        enemy_id="training_dummy",
        name="Training Dummy",
        max_hp=22,
        attack_value=0,
    )

    result = run_battle(
        deck_ids=["strike", "heavy_strike"],
        enemy_definition=enemy,
        seed=0,
        enemy_action_picker=constant_action("attack"),
        shuffle_deck=False,
    )
    replay = run_battle_replay(
        deck_ids=["strike", "heavy_strike"],
        enemy_definition=enemy,
        seed=0,
        enemy_action_picker=constant_action("attack"),
        shuffle_deck=False,
    )

    assert replay.result == result
    assert len(replay.frames) == result.turns
    assert replay.opening_log_lines == result.log_lines[:4]
    assert replay.frames[0].active_card is not None
    assert replay.frames[0].active_card.name == "Heavy Strike"
    assert replay.frames[0].active_card.charge_progress == 1
    assert replay.frames[0].is_charge_blocked is True
    assert replay.frames[2].active_card is not None
    assert replay.frames[2].active_card.charge_progress == 3
    assert replay.frames[-1].log_lines[-1] == "Result: Player victory."


@pytest.mark.parametrize(
    ("enemy_id", "seed"),
    [
        ("guard", 0),
        ("guard", 1),
        ("guard", 2),
        ("priest", 35),
        ("priest", 71),
        ("priest", 117),
    ],
)
def test_historically_stalling_matchups_resolve_within_explicit_turn_cap(
    enemy_id: str, seed: int
) -> None:
    result = run_battle(
        deck_ids=TEST_DECK,
        enemy_definition=get_enemy_definition(enemy_id),
        seed=seed,
        max_turns=200,
    )

    assert result.turns <= 200
    assert result.outcome in {"victory", "defeat"}
