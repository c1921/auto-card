from __future__ import annotations

import random
from dataclasses import dataclass
from typing import TYPE_CHECKING

from auto_card.battle_reporting import build_active_card_snapshot
from auto_card.content import CARDS, PLAYER_MAX_HP
from auto_card.models import (
    ActiveCardSnapshot,
    BattleOutcome,
    CardDefinition,
    ChargeState,
    Combatant,
    EnemyActionKind,
    EnemyDefinition,
)

if TYPE_CHECKING:
    from collections.abc import Sequence


@dataclass(frozen=True)
class DamageReport:
    requested: int
    blocked: int
    hp_lost: int
    armor_before: int
    armor_after: int
    hp_before: int
    hp_after: int


@dataclass(frozen=True)
class ArmorReport:
    gained: int
    armor_before: int
    armor_after: int


@dataclass(frozen=True)
class HealReport:
    requested: int
    restored: int
    hp_before: int
    hp_after: int


@dataclass(frozen=True)
class PlayerPhaseResult:
    next_charge_state: ChargeState | None
    active_card: ActiveCardSnapshot | None


def resolve_player_phase(
    *,
    player: Combatant,
    enemy: Combatant,
    draw_pile: list[str],
    discard_pile: list[str],
    charge_state: ChargeState | None,
    rng: random.Random,
    log_lines: list[str],
) -> PlayerPhaseResult:
    if charge_state is not None:
        charge_state.progress += 1
        card = charge_state.card
        log_lines.append(
            f"Player continues charging {card.name} "
            f"({charge_state.progress}/{card.charge_turns})."
        )
        if charge_state.progress == card.charge_turns:
            resolve_card(card=card, player=player, enemy=enemy, log_lines=log_lines)
            discard_pile.append(card.id)
            log_lines.append(f"{card.name} moves to discard pile.")
            return PlayerPhaseResult(
                next_charge_state=None,
                active_card=build_active_card_snapshot(
                    card=card,
                    charge_progress=charge_state.progress,
                    status_text="Resolved",
                ),
            )
        return PlayerPhaseResult(
            next_charge_state=charge_state,
            active_card=build_active_card_snapshot(
                card=card,
                charge_progress=charge_state.progress,
                status_text="Charging",
            ),
        )

    card = draw_next_card(
        draw_pile=draw_pile,
        discard_pile=discard_pile,
        rng=rng,
        log_lines=log_lines,
    )
    if card is None:
        log_lines.append("Player cannot act this turn.")
        return PlayerPhaseResult(next_charge_state=None, active_card=None)

    log_lines.append(f"Player flips {card.name}.")
    if card.is_charge_card:
        log_lines.append(
            f"Player begins charging {card.name} (1/{card.charge_turns})."
        )
        return PlayerPhaseResult(
            next_charge_state=ChargeState(card=card),
            active_card=build_active_card_snapshot(
                card=card,
                charge_progress=1,
                status_text="Charging",
            ),
        )

    resolve_card(card=card, player=player, enemy=enemy, log_lines=log_lines)
    discard_pile.append(card.id)
    log_lines.append(f"{card.name} moves to discard pile.")
    return PlayerPhaseResult(
        next_charge_state=None,
        active_card=build_active_card_snapshot(
            card=card,
            charge_progress=1,
            status_text="Resolved",
        ),
    )


def resolve_enemy_phase(
    *,
    enemy_definition: EnemyDefinition,
    enemy: Combatant,
    player: Combatant,
    action: EnemyActionKind,
    log_lines: list[str],
) -> str:
    if action == "attack":
        report = apply_damage(player, enemy_definition.attack_value)
        summary = (
            f"{enemy.name} attacks for {enemy_definition.attack_value} damage "
            f"(Player armor {report.armor_before}->{report.armor_after}, "
            f"HP {report.hp_before}->{report.hp_after})."
        )
        log_lines.append(summary)
        return summary

    if action == "defend":
        report = gain_armor(enemy, enemy_definition.defend_value)
        summary = (
            f"{enemy.name} gains {report.gained} armor "
            f"(Armor {report.armor_before}->{report.armor_after})."
        )
        log_lines.append(summary)
        return summary

    if action == "heal":
        report = heal_combatant(enemy, enemy_definition.heal_value)
        summary = (
            f"{enemy.name} heals for {report.restored} HP "
            f"(HP {report.hp_before}->{report.hp_after})."
        )
        log_lines.append(summary)
        return summary

    raise ValueError(f"Unsupported enemy action: {action}")


def resolve_card(
    *,
    card: CardDefinition,
    player: Combatant,
    enemy: Combatant,
    log_lines: list[str],
) -> None:
    log_lines.append(f"Player resolves {card.name}.")

    if card.damage:
        report = apply_damage(enemy, card.damage)
        log_lines.append(
            f"{card.name} deals {card.damage} damage to {enemy.name} "
            f"(Armor {report.armor_before}->{report.armor_after}, "
            f"HP {report.hp_before}->{report.hp_after})."
        )

    if card.armor_gain:
        report = gain_armor(player, card.armor_gain)
        log_lines.append(
            f"{card.name} grants Player {report.gained} armor "
            f"(Armor {report.armor_before}->{report.armor_after})."
        )

    if card.heal:
        report = heal_combatant(player, card.heal)
        log_lines.append(
            f"{card.name} heals Player for {report.restored} HP "
            f"(HP {report.hp_before}->{report.hp_after})."
        )


def choose_enemy_action(
    enemy_definition: EnemyDefinition,
    rng: random.Random,
) -> EnemyActionKind:
    total_weight = (
        enemy_definition.attack_weight
        + enemy_definition.defend_weight
        + enemy_definition.heal_weight
    )
    if total_weight <= 0:
        raise ValueError(
            f"Enemy '{enemy_definition.id}' must have a positive total action weight."
        )

    roll = rng.randint(1, total_weight)
    if roll <= enemy_definition.attack_weight:
        return "attack"
    if roll <= enemy_definition.attack_weight + enemy_definition.defend_weight:
        return "defend"
    return "heal"


def draw_next_card(
    *,
    draw_pile: list[str],
    discard_pile: list[str],
    rng: random.Random,
    log_lines: list[str],
) -> CardDefinition | None:
    if not draw_pile and discard_pile:
        draw_pile.extend(discard_pile)
        discard_pile.clear()
        rng.shuffle(draw_pile)
        log_lines.append(
            f"Player reshuffles discard pile into draw pile ({len(draw_pile)} cards)."
        )

    if not draw_pile:
        return None

    card_id = draw_pile.pop()
    return CARDS[card_id]


def apply_damage(target: Combatant, amount: int) -> DamageReport:
    armor_before = target.armor
    hp_before = target.hp
    blocked = min(target.armor, amount)
    hp_lost = amount - blocked

    target.armor -= blocked
    target.hp = max(0, target.hp - hp_lost)

    return DamageReport(
        requested=amount,
        blocked=blocked,
        hp_lost=hp_lost,
        armor_before=armor_before,
        armor_after=target.armor,
        hp_before=hp_before,
        hp_after=target.hp,
    )


def gain_armor(target: Combatant, amount: int) -> ArmorReport:
    armor_before = target.armor
    target.armor += amount
    return ArmorReport(
        gained=amount,
        armor_before=armor_before,
        armor_after=target.armor,
    )


def heal_combatant(target: Combatant, amount: int) -> HealReport:
    hp_before = target.hp
    target.hp = min(target.max_hp, target.hp + amount)
    restored = target.hp - hp_before
    return HealReport(
        requested=amount,
        restored=restored,
        hp_before=hp_before,
        hp_after=target.hp,
    )


def determine_outcome(
    player: Combatant, enemy: Combatant
) -> BattleOutcome | None:
    if player.hp <= 0 and enemy.hp <= 0:
        return "defeat"
    if player.hp <= 0:
        return "defeat"
    if enemy.hp <= 0:
        return "victory"
    return None


def validate_deck(deck_ids: Sequence[str]) -> None:
    missing = sorted({card_id for card_id in deck_ids if card_id not in CARDS})
    if missing:
        missing_text = ", ".join(missing)
        raise ValueError(f"Unknown card ids in deck: {missing_text}")


def validate_player_start_hp(player_start_hp: int) -> None:
    if not 1 <= player_start_hp <= PLAYER_MAX_HP:
        raise ValueError(
            f"Player starting HP must be between 1 and {PLAYER_MAX_HP}, "
            f"got {player_start_hp}."
        )
