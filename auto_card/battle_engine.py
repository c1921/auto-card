from __future__ import annotations

import random
from dataclasses import dataclass
from typing import TYPE_CHECKING

from auto_card.battle_reporting import build_active_card_snapshot
from auto_card.content import CARDS
from auto_card.models import (
    ActiveCardSnapshot,
    CardDefinition,
    ChargeState,
    Combatant,
    EffectDefinition,
    EnemyActionDefinition,
    EnemyActionKind,
    EnemyDefinition,
    StatusKind,
)
from auto_card.presentation import STATUS_LABELS

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
class StatusReport:
    kind: StatusKind
    previous: int
    current: int


@dataclass(frozen=True)
class PlayerPhaseResult:
    next_charge_state: ChargeState | None
    active_card: ActiveCardSnapshot | None


@dataclass(frozen=True)
class EnemyPhaseResult:
    action_id: EnemyActionKind
    action_name: str
    summary: str


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
    if not _can_take_action(combatant=player, actor_name=player.name, log_lines=log_lines):
        active_card = None
        if charge_state is not None:
            active_card = build_active_card_snapshot(
                card=charge_state.card,
                charge_progress=charge_state.progress,
                status_text="Stunned",
            )
        return PlayerPhaseResult(
            next_charge_state=charge_state,
            active_card=active_card,
        )

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
) -> EnemyPhaseResult:
    if not _can_take_action(combatant=enemy, actor_name=enemy.name, log_lines=log_lines):
        return EnemyPhaseResult(
            action_id="skipped",
            action_name="Skipped",
            summary=f"{enemy.name} skips the action.",
        )

    action_definition = get_enemy_action_definition(enemy_definition, action)
    log_lines.append(f"{enemy.name} uses {action_definition.name}.")
    summary = resolve_effects(
        action_name=action_definition.name,
        effects=action_definition.effects,
        source=enemy,
        target=player,
        source_label=enemy.name,
        target_label=player.name,
        log_lines=log_lines,
    )
    return EnemyPhaseResult(
        action_id=action_definition.id,
        action_name=action_definition.name,
        summary=summary,
    )


def resolve_card(
    *,
    card: CardDefinition,
    player: Combatant,
    enemy: Combatant,
    log_lines: list[str],
) -> None:
    log_lines.append(f"Player resolves {card.name}.")
    resolve_effects(
        action_name=card.name,
        effects=card.effects,
        source=player,
        target=enemy,
        source_label=player.name,
        target_label=enemy.name,
        log_lines=log_lines,
    )


def resolve_effects(
    *,
    action_name: str,
    effects: tuple[EffectDefinition, ...],
    source: Combatant,
    target: Combatant,
    source_label: str,
    target_label: str,
    log_lines: list[str],
) -> str:
    summary_parts: list[str] = []
    for effect in effects:
        recipient = source if effect.target == "self" else target
        recipient_label = source_label if effect.target == "self" else target_label

        if effect.kind == "damage":
            amount = effect.value + source.statuses.get("strength", 0)
            report = apply_damage(recipient, amount)
            log_lines.append(
                f"{action_name} deals {amount} damage to {recipient_label} "
                f"(Armor {report.armor_before}->{report.armor_after}, "
                f"HP {report.hp_before}->{report.hp_after})."
            )
            summary_parts.append(f"damage {amount}")
            continue

        if effect.kind == "armor":
            report = gain_armor(recipient, effect.value)
            log_lines.append(
                f"{action_name} grants {recipient_label} {report.gained} armor "
                f"(Armor {report.armor_before}->{report.armor_after})."
            )
            summary_parts.append(f"armor {report.gained}")
            continue

        if effect.kind == "heal":
            report = heal_combatant(recipient, effect.value)
            log_lines.append(
                f"{action_name} heals {recipient_label} for {report.restored} HP "
                f"(HP {report.hp_before}->{report.hp_after})."
            )
            summary_parts.append(f"heal {report.restored}")
            continue

        if effect.kind == "apply_status" and effect.status is not None:
            report = apply_status(recipient, effect.status, effect.value)
            label = STATUS_LABELS[effect.status]
            log_lines.append(
                f"{action_name} applies {label} {effect.value} to {recipient_label} "
                f"({label} {report.previous}->{report.current})."
            )
            summary_parts.append(f"{label.lower()} {report.current}")
            continue

        raise ValueError(f"Unsupported effect kind: {effect.kind}")

    return ", ".join(summary_parts) if summary_parts else f"{action_name} resolves."


def choose_enemy_action(
    enemy_definition: EnemyDefinition,
    rng: random.Random,
) -> EnemyActionKind:
    total_weight = sum(action.weight for action in enemy_definition.actions)
    if total_weight <= 0:
        raise ValueError(
            f"Enemy '{enemy_definition.id}' must have a positive total action weight."
        )

    roll = rng.randint(1, total_weight)
    cursor = 0
    for action in enemy_definition.actions:
        cursor += action.weight
        if roll <= cursor:
            return action.id

    return enemy_definition.actions[-1].id


def get_enemy_action_definition(
    enemy_definition: EnemyDefinition,
    action_id: str,
) -> EnemyActionDefinition:
    for action in enemy_definition.actions:
        if action.id == action_id:
            return action
    raise ValueError(
        f"Enemy '{enemy_definition.id}' does not define action '{action_id}'."
    )


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
    restored = min(amount, target.max_hp - target.hp)
    target.hp += restored
    return HealReport(
        requested=amount,
        restored=restored,
        hp_before=hp_before,
        hp_after=target.hp,
    )


def apply_status(target: Combatant, kind: StatusKind, value: int) -> StatusReport:
    previous = target.statuses.get(kind, 0)
    current = previous + value
    if current <= 0:
        target.statuses.pop(kind, None)
        current = 0
    else:
        target.statuses[kind] = current
    return StatusReport(kind=kind, previous=previous, current=current)


def determine_outcome(
    player: Combatant,
    enemy: Combatant,
):
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


def validate_player_start_hp(player_start_hp: int, max_hp: int) -> None:
    if not 1 <= player_start_hp <= max_hp:
        raise ValueError(
            f"Player starting HP must be between 1 and {max_hp}; got {player_start_hp}."
        )


def _can_take_action(
    *,
    combatant: Combatant,
    actor_name: str,
    log_lines: list[str],
) -> bool:
    poison = combatant.statuses.get("poison", 0)
    if poison > 0:
        hp_before = combatant.hp
        combatant.hp = max(0, combatant.hp - poison)
        log_lines.append(
            f"{actor_name} suffers {poison} poison damage "
            f"(HP {hp_before}->{combatant.hp})."
        )
        remaining_poison = poison - 1
        if remaining_poison > 0:
            combatant.statuses["poison"] = remaining_poison
            log_lines.append(f"{actor_name} poison decreases to {remaining_poison}.")
        else:
            combatant.statuses.pop("poison", None)
            log_lines.append(f"Poison on {actor_name} wears off.")

    stun = combatant.statuses.get("stun", 0)
    if stun > 0:
        remaining_stun = stun - 1
        if remaining_stun > 0:
            combatant.statuses["stun"] = remaining_stun
        else:
            combatant.statuses.pop("stun", None)
        log_lines.append(f"{actor_name} is stunned and skips the action.")
        return False

    if combatant.hp <= 0:
        log_lines.append(f"{actor_name} cannot act at 0 HP.")
        return False

    return True
