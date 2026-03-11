from __future__ import annotations

import random
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from auto_card.content import (
    CARDS,
    PLAYER_MAX_HP,
    PLAYER_NAME,
    PLAYER_STARTING_ARMOR,
    PLAYER_STARTING_HP,
    TEST_DECK,
    get_enemy_definition,
)
from auto_card.models import (
    BattleOutcome,
    BattleResult,
    CardDefinition,
    ChargeState,
    Combatant,
    CombatantSnapshot,
    EnemyActionKind,
    EnemyDefinition,
)

MAX_BATTLE_TURNS = 200
EnemyActionPicker = Callable[[EnemyDefinition, random.Random], EnemyActionKind]


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
    max_turns: int = MAX_BATTLE_TURNS,
    shuffle_deck: bool = True,
) -> BattleResult:
    _validate_deck(deck_ids)
    _validate_player_start_hp(player_start_hp)

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
    draw_pile = list(deck_ids)
    if shuffle_deck:
        rng.shuffle(draw_pile)
    discard_pile: list[str] = []
    charge_state: ChargeState | None = None
    pick_enemy_action = enemy_action_picker or choose_enemy_action

    log_lines = [
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
        f"Starting deck size: {len(draw_pile)} cards",
    ]

    for turn in range(1, max_turns + 1):
        log_lines.append("")
        log_lines.append(f"Turn {turn}")
        log_lines.append(
            f"Start: {format_combatant(player)} | {format_combatant(enemy)}"
        )

        charge_state = resolve_player_phase(
            player=player,
            enemy=enemy,
            draw_pile=draw_pile,
            discard_pile=discard_pile,
            charge_state=charge_state,
            rng=rng,
            log_lines=log_lines,
        )

        if enemy.hp <= 0:
            log_lines.append(
                f"{enemy.name} is at 0 HP but still acts before the end-of-turn death check."
            )

        enemy_action = pick_enemy_action(enemy_definition, rng)
        resolve_enemy_phase(
            enemy_definition=enemy_definition,
            enemy=enemy,
            player=player,
            action=enemy_action,
            log_lines=log_lines,
        )

        log_lines.append(
            f"End: {format_combatant(player)} | {format_combatant(enemy)}"
        )

        outcome = determine_outcome(player, enemy)
        if outcome is not None:
            log_lines.append(
                "Result: Player victory."
                if outcome == "victory"
                else "Result: Player defeat."
            )
            return BattleResult(
                outcome=outcome,
                turns=turn,
                player=snapshot(player),
                enemy=snapshot(enemy),
                log_lines=tuple(log_lines),
                seed=seed,
                enemy_id=enemy_definition.id,
            )

    raise RuntimeError(
        f"Battle exceeded {max_turns} turns without reaching a result."
    )


def resolve_player_phase(
    *,
    player: Combatant,
    enemy: Combatant,
    draw_pile: list[str],
    discard_pile: list[str],
    charge_state: ChargeState | None,
    rng: random.Random,
    log_lines: list[str],
) -> ChargeState | None:
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
            return None
        return charge_state

    card = draw_next_card(
        draw_pile=draw_pile,
        discard_pile=discard_pile,
        rng=rng,
        log_lines=log_lines,
    )
    if card is None:
        log_lines.append("Player cannot act this turn.")
        return None

    log_lines.append(f"Player flips {card.name}.")
    if card.is_charge_card:
        log_lines.append(
            f"Player begins charging {card.name} (1/{card.charge_turns})."
        )
        return ChargeState(card=card)

    resolve_card(card=card, player=player, enemy=enemy, log_lines=log_lines)
    discard_pile.append(card.id)
    log_lines.append(f"{card.name} moves to discard pile.")
    return None


def resolve_enemy_phase(
    *,
    enemy_definition: EnemyDefinition,
    enemy: Combatant,
    player: Combatant,
    action: EnemyActionKind,
    log_lines: list[str],
) -> None:
    if action == "attack":
        report = apply_damage(player, enemy_definition.attack_value)
        log_lines.append(
            f"{enemy.name} attacks for {enemy_definition.attack_value} damage "
            f"(Player armor {report.armor_before}->{report.armor_after}, "
            f"HP {report.hp_before}->{report.hp_after})."
        )
        return

    if action == "defend":
        report = gain_armor(enemy, enemy_definition.defend_value)
        log_lines.append(
            f"{enemy.name} gains {report.gained} armor "
            f"(Armor {report.armor_before}->{report.armor_after})."
        )
        return

    if action == "heal":
        report = heal_combatant(enemy, enemy_definition.heal_value)
        log_lines.append(
            f"{enemy.name} heals for {report.restored} HP "
            f"(HP {report.hp_before}->{report.hp_after})."
        )
        return

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


def _validate_deck(deck_ids: Sequence[str]) -> None:
    missing = sorted({card_id for card_id in deck_ids if card_id not in CARDS})
    if missing:
        missing_text = ", ".join(missing)
        raise ValueError(f"Unknown card ids in deck: {missing_text}")


def _validate_player_start_hp(player_start_hp: int) -> None:
    if not 1 <= player_start_hp <= PLAYER_MAX_HP:
        raise ValueError(
            f"Player starting HP must be between 1 and {PLAYER_MAX_HP}, "
            f"got {player_start_hp}."
        )
