from __future__ import annotations

from auto_card.models import (
    ActiveCardSnapshot,
    BattleOutcome,
    CardDefinition,
    Combatant,
    CombatantSnapshot,
    EnemyDefinition,
    StatusSnapshot,
)
from auto_card.presentation import format_card_effect, format_statuses, get_card_type, status_sort_key


def build_opening_log_lines(
    *,
    player: Combatant,
    enemy: Combatant,
    enemy_definition: EnemyDefinition,
    seed: int,
    deck_size: int,
) -> list[str]:
    weight_text = ", ".join(
        f"{action.name} {action.weight}" for action in enemy_definition.actions
    )
    return [
        (
            f"Battle start: {player.name} {player.hp}/{player.max_hp} HP vs "
            f"{enemy.name} {enemy.hp}/{enemy.max_hp} HP"
        ),
        f"Seed: {seed}",
        f"Enemy actions: {weight_text}",
        f"Starting deck size: {deck_size} cards",
    ]


def build_turn_start_lines(
    *,
    turn: int,
    player: Combatant,
    enemy: Combatant,
) -> tuple[str, ...]:
    return (
        "",
        f"Turn {turn}",
        f"Start: {format_combatant(player)} | {format_combatant(enemy)}",
    )


def build_outcome_line(outcome: BattleOutcome) -> str:
    return (
        "Result: Player victory."
        if outcome == "victory"
        else "Result: Player defeat."
    )


def build_enemy_zero_hp_line(enemy_name: str) -> str:
    return (
        f"{enemy_name} is at 0 HP but still acts before the end-of-turn death check."
    )


def snapshot(combatant: Combatant) -> CombatantSnapshot:
    status_snapshots = tuple(
        sorted(
            (
                StatusSnapshot(kind=kind, value=value)
                for kind, value in combatant.statuses.items()
                if value > 0
            ),
            key=status_sort_key,
        )
    )
    return CombatantSnapshot(
        name=combatant.name,
        max_hp=combatant.max_hp,
        hp=combatant.hp,
        armor=combatant.armor,
        statuses=status_snapshots,
    )


def format_combatant(combatant: Combatant) -> str:
    snapshot_value = snapshot(combatant)
    return (
        f"{combatant.name} HP {combatant.hp}/{combatant.max_hp}, "
        f"Armor {combatant.armor}, Status {format_statuses(snapshot_value.statuses)}"
    )


def build_active_card_snapshot(
    *,
    card: CardDefinition,
    charge_progress: int,
    status_text: str,
) -> ActiveCardSnapshot:
    return ActiveCardSnapshot(
        card_id=card.id,
        name=card.name,
        card_type=get_card_type(card),
        charge_turns=card.charge_turns,
        charge_progress=charge_progress,
        effect_text=format_card_effect(card),
        status_text=status_text,
    )
