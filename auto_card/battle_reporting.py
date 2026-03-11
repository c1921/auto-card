from __future__ import annotations

from auto_card.models import (
    ActiveCardSnapshot,
    BattleOutcome,
    CardDefinition,
    Combatant,
    CombatantSnapshot,
    EnemyDefinition,
)
from auto_card.presentation import format_card_effect, get_card_type


def build_opening_log_lines(
    *,
    player: Combatant,
    enemy: Combatant,
    enemy_definition: EnemyDefinition,
    seed: int,
    deck_size: int,
) -> list[str]:
    return [
        (
            f"Battle start: {player.name} {player.hp}/{player.max_hp} HP vs "
            f"{enemy.name} {enemy.hp}/{enemy.max_hp} HP"
        ),
        f"Seed: {seed}",
        (
            "Enemy weights: "
            f"attack {enemy_definition.attack_weight}, "
            f"defend {enemy_definition.defend_weight}, "
            f"heal {enemy_definition.heal_weight}"
        ),
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
    return f"{enemy_name} is at 0 HP but still acts before the end-of-turn death check."


def snapshot(combatant: Combatant) -> CombatantSnapshot:
    return CombatantSnapshot(
        name=combatant.name,
        max_hp=combatant.max_hp,
        hp=combatant.hp,
        armor=combatant.armor,
    )


def format_combatant(combatant: Combatant) -> str:
    return (
        f"{combatant.name} HP {combatant.hp}/{combatant.max_hp}, "
        f"Armor {combatant.armor}"
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
