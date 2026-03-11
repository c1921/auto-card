from __future__ import annotations

import random
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from auto_card.battle_engine import (
    apply_damage,
    choose_enemy_action,
    determine_outcome,
    heal_combatant,
    resolve_card,
    resolve_enemy_phase,
    resolve_player_phase,
    validate_deck,
    validate_player_start_hp,
)
from auto_card.battle_reporting import (
    build_enemy_zero_hp_line,
    build_opening_log_lines,
    build_outcome_line,
    build_turn_start_lines,
    format_combatant,
    snapshot,
)
from auto_card.content import (
    PLAYER_MAX_HP,
    PLAYER_NAME,
    PLAYER_STARTING_ARMOR,
    PLAYER_STARTING_HP,
    TEST_DECK,
    get_enemy_definition,
)
from auto_card.models import (
    BattleReplay,
    BattleResult,
    BattleTurnFrame,
    ChargeState,
    Combatant,
    EnemyActionKind,
    EnemyDefinition,
)

EnemyActionPicker = Callable[[EnemyDefinition, random.Random], EnemyActionKind]
__all__ = [
    "apply_damage",
    "heal_combatant",
    "resolve_card",
    "run_battle",
    "run_battle_replay",
    "simulate_battle",
]


@dataclass(frozen=True)
class BattleSimulationArtifacts:
    result: BattleResult
    replay: BattleReplay


def simulate_battle(enemy_id: str, seed: int = 0) -> BattleResult:
    enemy_definition = get_enemy_definition(enemy_id)
    return run_battle(
        deck_ids=TEST_DECK,
        enemy_definition=enemy_definition,
        seed=seed,
    )


def run_battle(
    deck_ids: Sequence[str],
    enemy_definition: EnemyDefinition,
    seed: int,
    player_start_hp: int = PLAYER_STARTING_HP,
    enemy_action_picker: EnemyActionPicker | None = None,
    max_turns: int | None = None,
    shuffle_deck: bool = True,
) -> BattleResult:
    return _simulate_battle(
        deck_ids=deck_ids,
        enemy_definition=enemy_definition,
        seed=seed,
        player_start_hp=player_start_hp,
        enemy_action_picker=enemy_action_picker,
        max_turns=max_turns,
        shuffle_deck=shuffle_deck,
    ).result


def run_battle_replay(
    deck_ids: Sequence[str],
    enemy_definition: EnemyDefinition,
    seed: int,
    player_start_hp: int = PLAYER_STARTING_HP,
    enemy_action_picker: EnemyActionPicker | None = None,
    max_turns: int | None = None,
    shuffle_deck: bool = True,
) -> BattleReplay:
    return _simulate_battle(
        deck_ids=deck_ids,
        enemy_definition=enemy_definition,
        seed=seed,
        player_start_hp=player_start_hp,
        enemy_action_picker=enemy_action_picker,
        max_turns=max_turns,
        shuffle_deck=shuffle_deck,
    ).replay


def _simulate_battle(
    *,
    deck_ids: Sequence[str],
    enemy_definition: EnemyDefinition,
    seed: int,
    player_start_hp: int,
    enemy_action_picker: EnemyActionPicker | None,
    max_turns: int | None,
    shuffle_deck: bool,
) -> BattleSimulationArtifacts:
    normalized_deck = tuple(deck_ids)
    validate_deck(normalized_deck)
    validate_player_start_hp(player_start_hp)

    rng = random.Random(seed)
    player = Combatant(
        name=PLAYER_NAME,
        max_hp=PLAYER_MAX_HP,
        hp=player_start_hp,
        armor=PLAYER_STARTING_ARMOR,
    )
    enemy = Combatant(
        name=enemy_definition.name,
        max_hp=enemy_definition.max_hp,
        hp=enemy_definition.max_hp,
        armor=0,
    )
    draw_pile = list(normalized_deck)
    if shuffle_deck:
        rng.shuffle(draw_pile)
    discard_pile: list[str] = []
    charge_state: ChargeState | None = None
    pick_enemy_action = enemy_action_picker or choose_enemy_action

    log_lines = build_opening_log_lines(
        player=player,
        enemy=enemy,
        enemy_definition=enemy_definition,
        seed=seed,
        deck_size=len(draw_pile),
    )
    opening_log_lines = tuple(log_lines)
    frames: list[BattleTurnFrame] = []

    turn = 0
    while True:
        turn += 1
        turn_log_start = len(log_lines)
        log_lines.extend(
            build_turn_start_lines(turn=turn, player=player, enemy=enemy)
        )
        player_start = snapshot(player)
        enemy_start = snapshot(enemy)

        player_phase = resolve_player_phase(
            player=player,
            enemy=enemy,
            draw_pile=draw_pile,
            discard_pile=discard_pile,
            charge_state=charge_state,
            rng=rng,
            log_lines=log_lines,
        )
        charge_state = player_phase.next_charge_state

        if enemy.hp <= 0:
            log_lines.append(build_enemy_zero_hp_line(enemy.name))

        enemy_action = pick_enemy_action(enemy_definition, rng)
        enemy_action_summary = resolve_enemy_phase(
            enemy_definition=enemy_definition,
            enemy=enemy,
            player=player,
            action=enemy_action,
            log_lines=log_lines,
        )

        player_end = snapshot(player)
        enemy_end = snapshot(enemy)
        log_lines.append(
            f"End: {format_combatant(player)} | {format_combatant(enemy)}"
        )

        outcome = determine_outcome(player, enemy)
        if outcome is not None:
            log_lines.append(build_outcome_line(outcome))

        frames.append(
            BattleTurnFrame(
                turn=turn,
                player_start=player_start,
                enemy_start=enemy_start,
                player_end=player_end,
                enemy_end=enemy_end,
                draw_pile_count=len(draw_pile),
                discard_pile_count=len(discard_pile),
                active_card=player_phase.active_card,
                is_charge_blocked=charge_state is not None,
                enemy_action=enemy_action,
                enemy_action_summary=enemy_action_summary,
                log_lines=tuple(log_lines[turn_log_start:]),
            )
        )

        if outcome is not None:
            return _build_battle_artifacts(
                outcome=outcome,
                turn=turn,
                player_end=player_end,
                enemy_end=enemy_end,
                log_lines=log_lines,
                seed=seed,
                enemy_id=enemy_definition.id,
                normalized_deck=normalized_deck,
                opening_log_lines=opening_log_lines,
                frames=frames,
            )

        if max_turns is not None and turn >= max_turns:
            raise RuntimeError(
                f"Battle exceeded {max_turns} turns without reaching a result."
            )


def _build_battle_artifacts(
    *,
    outcome: str,
    turn: int,
    player_end,
    enemy_end,
    log_lines: list[str],
    seed: int,
    enemy_id: str,
    normalized_deck: tuple[str, ...],
    opening_log_lines: tuple[str, ...],
    frames: list[BattleTurnFrame],
) -> BattleSimulationArtifacts:
    result = BattleResult(
        outcome=outcome,
        turns=turn,
        player=player_end,
        enemy=enemy_end,
        log_lines=tuple(log_lines),
        seed=seed,
        enemy_id=enemy_id,
    )
    return BattleSimulationArtifacts(
        result=result,
        replay=BattleReplay(
            result=result,
            deck_ids=normalized_deck,
            opening_log_lines=opening_log_lines,
            frames=tuple(frames),
        ),
    )
