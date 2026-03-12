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
from auto_card.content import CARDS, get_enemy_definition, get_role_definition
from auto_card.models import (
    Combatant,
    EffectDefinition,
    EnemyActionDefinition,
    EnemyActionKind,
    EnemyDefinition,
)


def constant_action(action: EnemyActionKind):
    def pick(_enemy: EnemyDefinition, _rng) -> EnemyActionKind:
        return action

    return pick


def sequence_action(actions: list[EnemyActionKind]):
    iterator = iter(actions)

    def pick(_enemy: EnemyDefinition, _rng) -> EnemyActionKind:
        return next(iterator)

    return pick


def make_action(
    action_id: str,
    *,
    name: str,
    weight: int = 1,
    effects: tuple[EffectDefinition, ...],
) -> EnemyActionDefinition:
    return EnemyActionDefinition(
        id=action_id,
        name=name,
        weight=weight,
        effects=effects,
    )


def make_enemy(
    *,
    enemy_id: str,
    name: str,
    max_hp: int,
    actions: tuple[EnemyActionDefinition, ...],
) -> EnemyDefinition:
    return EnemyDefinition(
        id=enemy_id,
        name=name,
        max_hp=max_hp,
        actions=actions,
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


def test_strength_increases_later_attack_damage() -> None:
    enemy = make_enemy(
        enemy_id="training_dummy",
        name="Training Dummy",
        max_hp=30,
        actions=(
            make_action(
                "wait",
                name="Wait",
                effects=(EffectDefinition(kind="armor", target="self", value=0),),
            ),
        ),
    )

    result = run_battle(
        deck_ids=["strike", "strike", "battle_cry"],
        enemy_definition=enemy,
        seed=0,
        enemy_action_picker=constant_action("wait"),
        shuffle_deck=False,
    )

    assert any("Battle Cry applies Strength 2 to Player" in line for line in result.log_lines)
    assert any("Strike deals 9 damage" in line for line in result.log_lines)


def test_poison_triggers_before_enemy_action_and_decays() -> None:
    enemy = make_enemy(
        enemy_id="poison_dummy",
        name="Dummy",
        max_hp=7,
        actions=(
            make_action(
                "wait",
                name="Wait",
                effects=(EffectDefinition(kind="armor", target="self", value=0),),
            ),
        ),
    )

    result = run_battle(
        deck_ids=["venom_cut"],
        enemy_definition=enemy,
        seed=0,
        enemy_action_picker=constant_action("wait"),
        shuffle_deck=False,
        role_definition=get_role_definition("alchemist"),
    )

    assert result.outcome == "victory"
    assert any("Dummy suffers 3 poison damage" in line for line in result.log_lines)
    assert any("Dummy poison decreases to 2." in line for line in result.log_lines)
    assert result.enemy.statuses[0].kind == "poison"
    assert result.enemy.statuses[0].value == 2


def test_stun_blocks_charge_progress_for_one_turn() -> None:
    enemy = make_enemy(
        enemy_id="spiker",
        name="Spiker",
        max_hp=18,
        actions=(
            make_action(
                "stun",
                name="Bell Ring",
                effects=(
                    EffectDefinition(
                        kind="apply_status",
                        target="opponent",
                        value=1,
                        status="stun",
                    ),
                ),
            ),
            make_action(
                "wait",
                name="Wait",
                effects=(EffectDefinition(kind="armor", target="self", value=0),),
            ),
        ),
    )

    result = run_battle(
        deck_ids=["heavy_strike"],
        enemy_definition=enemy,
        seed=0,
        enemy_action_picker=sequence_action(["stun", "wait", "wait", "wait"]),
        shuffle_deck=False,
    )

    begin_index = find_line_index(result.log_lines, "begins charging Heavy Strike (1/3)")
    stunned_index = find_line_index(result.log_lines, "Player is stunned and skips the action.")
    continue_two_index = find_line_index(
        result.log_lines, "continues charging Heavy Strike (2/3)"
    )
    continue_three_index = find_line_index(
        result.log_lines, "continues charging Heavy Strike (3/3)"
    )

    assert result.outcome == "victory"
    assert result.turns == 4
    assert begin_index < stunned_index < continue_two_index < continue_three_index


def test_shield_bash_stuns_enemy_and_skips_its_action() -> None:
    enemy = make_enemy(
        enemy_id="fighter",
        name="Fighter",
        max_hp=12,
        actions=(
            make_action(
                "attack",
                name="Punch",
                effects=(EffectDefinition(kind="damage", target="opponent", value=3),),
            ),
        ),
    )

    result = run_battle(
        deck_ids=["strike", "shield_bash"],
        enemy_definition=enemy,
        seed=0,
        enemy_action_picker=constant_action("attack"),
        shuffle_deck=False,
    )

    assert any("Shield Bash applies Stun 1 to Fighter" in line for line in result.log_lines)
    assert any("Fighter is stunned and skips the action." in line for line in result.log_lines)


def test_run_battle_replay_matches_final_result_and_turn_frames() -> None:
    enemy = make_enemy(
        enemy_id="training_dummy",
        name="Training Dummy",
        max_hp=22,
        actions=(
            make_action(
                "wait",
                name="Wait",
                effects=(EffectDefinition(kind="armor", target="self", value=0),),
            ),
        ),
    )

    result = run_battle(
        deck_ids=["strike", "heavy_strike"],
        enemy_definition=enemy,
        seed=0,
        enemy_action_picker=constant_action("wait"),
        shuffle_deck=False,
    )
    replay = run_battle_replay(
        deck_ids=["strike", "heavy_strike"],
        enemy_definition=enemy,
        seed=0,
        enemy_action_picker=constant_action("wait"),
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
        deck_ids=get_role_definition("adventurer").starting_deck,
        enemy_definition=get_enemy_definition(enemy_id),
        seed=seed,
        role_definition=get_role_definition("adventurer"),
        max_turns=200,
    )

    assert result.turns <= 200
    assert result.outcome in {"victory", "defeat"}


def test_simulate_battle_is_reproducible_for_same_seed() -> None:
    first = simulate_battle("bruiser", seed=0, role_id="alchemist")
    second = simulate_battle("bruiser", seed=0, role_id="alchemist")

    assert first == second
