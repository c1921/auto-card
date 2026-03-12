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
from auto_card.i18n import _
from auto_card.presentation import (
    format_statuses,
    get_action_name,
    status_sort_key,
)


def build_opening_log_lines(
    *,
    player: Combatant,
    enemy: Combatant,
    enemy_definition: EnemyDefinition,
    seed: int,
    deck_size: int,
) -> list[str]:
    weight_text = ", ".join(
        _("{name} {weight}").format(name=get_action_name(action), weight=action.weight)
        for action in enemy_definition.actions
    )
    return [
        _(
            "Battle start: {player_name} {player_hp}/{player_max_hp} HP vs "
            "{enemy_name} {enemy_hp}/{enemy_max_hp} HP"
        ).format(
            player_name=player.name,
            player_hp=player.hp,
            player_max_hp=player.max_hp,
            enemy_name=enemy.name,
            enemy_hp=enemy.hp,
            enemy_max_hp=enemy.max_hp,
        ),
        _("Seed: {seed}").format(seed=seed),
        _("Enemy actions: {weight_text}").format(weight_text=weight_text),
        _("Starting deck size: {deck_size} cards").format(deck_size=deck_size),
    ]


def build_turn_start_lines(
    *,
    turn: int,
    player: Combatant,
    enemy: Combatant,
) -> tuple[str, ...]:
    return (
        "",
        _("Turn {turn}").format(turn=turn),
        _("Start: {player} | {enemy}").format(
            player=format_combatant(player),
            enemy=format_combatant(enemy),
        ),
    )


def build_outcome_line(outcome: BattleOutcome) -> str:
    return (
        _("Result: Player victory.")
        if outcome == "victory"
        else _("Result: Player defeat.")
    )


def build_enemy_zero_hp_line(enemy_name: str) -> str:
    return _(
        "{enemy_name} is at 0 HP but still acts before the end-of-turn death check."
    ).format(enemy_name=enemy_name)


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
    return _(
        "{name} HP {hp}/{max_hp}, Armor {armor}, Status {statuses}"
    ).format(
        name=combatant.name,
        hp=combatant.hp,
        max_hp=combatant.max_hp,
        armor=combatant.armor,
        statuses=format_statuses(snapshot_value.statuses),
    )


def build_active_card_snapshot(
    *,
    card: CardDefinition,
    charge_progress: int,
    status_key: str,
) -> ActiveCardSnapshot:
    return ActiveCardSnapshot(
        card_id=card.id,
        charge_turns=card.charge_turns,
        charge_progress=charge_progress,
        status_key=status_key,
    )
