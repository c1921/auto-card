from __future__ import annotations

from collections import Counter

from auto_card.content import CARDS, CARD_ORDER, CARD_ORDER_INDEX, RUN_DECK_SIZE
from auto_card.models import ActiveCardSnapshot, CombatantSnapshot, RunResult
from auto_card.presentation import format_card_effect, get_card_type
from auto_card.run import DeckChoiceRequest, RewardChoiceRequest, format_card_counts


def build_collection_table_rows(
    *,
    collection: tuple[str, ...],
    selected_deck: list[str],
) -> tuple[list[str], list[tuple[str, ...]]]:
    collection_counts = Counter(collection)
    deck_counts = Counter(selected_deck)
    available_counts = collection_counts - deck_counts
    row_ids: list[str] = []
    rows: list[tuple[str, ...]] = []

    for card_id in CARD_ORDER:
        available_count = available_counts.get(card_id, 0)
        if not available_count:
            continue
        card = CARDS[card_id]
        row_ids.append(card_id)
        rows.append(
            (
                card.name,
                get_card_type(card),
                str(card.charge_turns),
                str(available_count),
                format_card_effect(card),
            )
        )

    return row_ids, rows


def build_deck_table_rows(selected_deck: list[str]) -> tuple[list[str], list[tuple[str, ...]]]:
    deck_counts = Counter(selected_deck)
    ordered_card_ids = sorted(deck_counts, key=lambda card_id: CARD_ORDER_INDEX[card_id])
    row_ids: list[str] = []
    rows: list[tuple[str, ...]] = []

    for card_id in ordered_card_ids:
        card = CARDS[card_id]
        row_ids.append(card_id)
        rows.append(
            (
                card.name,
                str(deck_counts[card_id]),
                str(card.charge_turns),
                format_card_effect(card),
            )
        )

    return row_ids, rows


def build_deck_summary_text(
    request: DeckChoiceRequest,
    *,
    selected_count: int,
) -> str:
    return (
        f"Battle {request.battle_number}/{request.total_battles} "
        f"vs {request.enemy.name} [{request.enemy.id}] ({request.battle_type})\n"
        f"HP {request.current_hp}/{request.max_hp} | "
        f"Deck {selected_count}/{RUN_DECK_SIZE}"
    )


def build_start_battle_label(selected_count: int) -> str:
    if selected_count == RUN_DECK_SIZE:
        return "Start Battle"
    return f"Start Battle ({selected_count}/{RUN_DECK_SIZE})"


def build_player_panel_text(
    *,
    player: CombatantSnapshot,
    battle_number: int,
    total_battles: int,
) -> str:
    return (
        f"Player\n"
        f"Battle {battle_number}/{total_battles}\n"
        f"HP {player.hp}/{player.max_hp}\n"
        f"Armor {player.armor}"
    )


def build_enemy_panel_text(enemy: CombatantSnapshot) -> str:
    return (
        f"{enemy.name}\n"
        f"HP {enemy.hp}/{enemy.max_hp}\n"
        f"Armor {enemy.armor}"
    )


def build_current_card_text(active_card: ActiveCardSnapshot | None) -> str:
    if active_card is None:
        return "Current Card\nWaiting for the next draw."

    return (
        f"{active_card.name}\n"
        f"{active_card.card_type} • {active_card.status_text}\n"
        f"Charge {active_card.charge_progress}/{active_card.charge_turns}\n"
        f"{active_card.effect_text}"
    )


def build_deck_panel_text(
    *,
    draw_pile_count: int,
    discard_pile_count: int,
    is_charge_blocked: bool,
    deck_ids: tuple[str, ...],
) -> str:
    return (
        "Deck State\n"
        f"Draw {draw_pile_count}\n"
        f"Discard {discard_pile_count}\n"
        f"Charge Blocked {'Yes' if is_charge_blocked else 'No'}\n"
        f"{format_card_counts(deck_ids)}"
    )


def build_reward_summary_text(
    request: RewardChoiceRequest,
    *,
    next_battle_number: int | None,
    total_battles: int,
    next_battle_type: str | None,
) -> str:
    return (
        f"HP {request.current_hp}/{request.max_hp}\n"
        f"Battle {request.battle_number} cleared against {request.enemy.name}\n"
        f"Next: battle {next_battle_number}/{total_battles} "
        f"({next_battle_type})"
    )


def build_reward_button_label(
    *,
    index: int,
    card_id: str,
    owned_count: int,
) -> str:
    card = CARDS[card_id]
    return (
        f"{index}. {card.name}\n"
        f"{get_card_type(card)} • Charge {card.charge_turns}\n"
        f"{format_card_effect(card)}\n"
        f"Owned {owned_count}"
    )


def build_result_summary_text(
    result: RunResult,
    *,
    total_battles: int,
) -> str:
    outcome_text = "Victory" if result.outcome == "victory" else "Defeat"
    return (
        f"{outcome_text}\n"
        f"Reached battle {result.final_battle_number}/{total_battles}\n"
        f"Final HP {result.final_hp}\n"
        f"Collection {format_card_counts(result.final_collection)}"
    )
