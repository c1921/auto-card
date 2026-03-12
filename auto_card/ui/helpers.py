from __future__ import annotations

from collections import Counter

from auto_card.content import (
    CARD_ORDER,
    CARD_ORDER_INDEX,
    CARDS,
    RUN_DECK_SIZE,
    get_role_definition,
)
from auto_card.i18n import _
from auto_card.models import (
    ActiveCardSnapshot,
    CombatantSnapshot,
    RoleDefinition,
    RunResult,
)
from auto_card.presentation import (
    format_active_card_status,
    format_battle_type,
    format_bool,
    format_card_effect,
    format_outcome,
    format_statuses,
    get_card_name,
    get_card_type,
    get_enemy_name,
    get_role_description,
    get_role_name,
)
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
                get_card_name(card),
                get_card_type(card),
                str(card.charge_turns),
                str(available_count),
                format_card_effect(card),
            )
        )

    return row_ids, rows


def build_deck_table_rows(
    selected_deck: list[str],
) -> tuple[list[str], list[tuple[str, ...]]]:
    deck_counts = Counter(selected_deck)
    ordered_card_ids = sorted(
        deck_counts,
        key=lambda card_id: CARD_ORDER_INDEX[card_id],
    )
    row_ids: list[str] = []
    rows: list[tuple[str, ...]] = []

    for card_id in ordered_card_ids:
        card = CARDS[card_id]
        row_ids.append(card_id)
        rows.append(
            (
                get_card_name(card),
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
    return _(
        "{role_name} ({role_id})\n"
        "Battle {battle_number}/{total_battles} "
        "vs {enemy_name} ({enemy_id}) ({battle_type})\n"
        "HP {current_hp}/{max_hp} | "
        "Deck {selected_count}/{deck_size}"
    ).format(
        role_name=get_role_name(request.role),
        role_id=request.role.id,
        battle_number=request.battle_number,
        total_battles=request.total_battles,
        enemy_name=get_enemy_name(request.enemy),
        enemy_id=request.enemy.id,
        battle_type=format_battle_type(request.battle_type),
        current_hp=request.current_hp,
        max_hp=request.max_hp,
        selected_count=selected_count,
        deck_size=RUN_DECK_SIZE,
    )


def build_start_battle_label(selected_count: int) -> str:
    if selected_count == RUN_DECK_SIZE:
        return _("Start Battle")
    return _("Start Battle ({selected_count}/{deck_size})").format(
        selected_count=selected_count,
        deck_size=RUN_DECK_SIZE,
    )


def build_player_panel_text(
    *,
    player: CombatantSnapshot,
    battle_number: int,
    total_battles: int,
    role: RoleDefinition,
) -> str:
    return _(
        "{role_name}\n"
        "Battle {battle_number}/{total_battles}\n"
        "HP {hp}/{max_hp}\n"
        "Armor {armor}\n"
        "Status {statuses}"
    ).format(
        role_name=get_role_name(role),
        battle_number=battle_number,
        total_battles=total_battles,
        hp=player.hp,
        max_hp=player.max_hp,
        armor=player.armor,
        statuses=format_statuses(player.statuses),
    )


def build_enemy_panel_text(enemy: CombatantSnapshot, *, enemy_name: str) -> str:
    return _(
        "{enemy_name}\n"
        "HP {hp}/{max_hp}\n"
        "Armor {armor}\n"
        "Status {statuses}"
    ).format(
        enemy_name=_(enemy_name),
        hp=enemy.hp,
        max_hp=enemy.max_hp,
        armor=enemy.armor,
        statuses=format_statuses(enemy.statuses),
    )


def build_current_card_text(active_card: ActiveCardSnapshot | None) -> str:
    if active_card is None:
        return _("Current Card\nWaiting for the next draw.")

    card = CARDS[active_card.card_id]
    return (
        _(
            "{card_name}\n"
            "{card_type} • {status}\n"
            "Charge {charge_progress}/{charge_turns}\n"
            "{effect_text}"
        ).format(
            card_name=get_card_name(card),
            card_type=get_card_type(card),
            status=format_active_card_status(active_card.status_key),
            charge_progress=active_card.charge_progress,
            charge_turns=active_card.charge_turns,
            effect_text=format_card_effect(card),
        )
    )


def build_deck_panel_text(
    *,
    draw_pile_count: int,
    discard_pile_count: int,
    is_charge_blocked: bool,
    deck_ids: tuple[str, ...],
) -> str:
    return _(
        "Deck State\n"
        "Draw {draw_pile_count}\n"
        "Discard {discard_pile_count}\n"
        "Charge Blocked {charge_blocked}\n"
        "{card_counts}"
    ).format(
        draw_pile_count=draw_pile_count,
        discard_pile_count=discard_pile_count,
        charge_blocked=format_bool(is_charge_blocked),
        card_counts=format_card_counts(deck_ids),
    )


def build_reward_summary_text(
    request: RewardChoiceRequest,
    *,
    next_battle_number: int | None,
    total_battles: int,
    next_battle_type: str | None,
) -> str:
    next_text = _("Complete")
    if next_battle_number is not None and next_battle_type is not None:
        next_text = _("battle {battle_number}/{total_battles} ({battle_type})").format(
            battle_number=next_battle_number,
            total_battles=total_battles,
            battle_type=format_battle_type(next_battle_type),
        )
    return _(
        "{role_name} ({role_id})\n"
        "HP {current_hp}/{max_hp}\n"
        "Battle {battle_number} cleared against {enemy_name}\n"
        "Next: {next_text}"
    ).format(
        role_name=get_role_name(request.role),
        role_id=request.role.id,
        current_hp=request.current_hp,
        max_hp=request.max_hp,
        battle_number=request.battle_number,
        enemy_name=get_enemy_name(request.enemy),
        next_text=next_text,
    )


def build_reward_button_label(
    *,
    index: int,
    card_id: str,
    owned_count: int,
) -> str:
    card = CARDS[card_id]
    return _(
        "{index}. {card_name}\n"
        "{card_type} • Charge {charge_turns}\n"
        "{effect_text}\n"
        "Owned {owned_count}"
    ).format(
        index=index,
        card_name=get_card_name(card),
        card_type=get_card_type(card),
        charge_turns=card.charge_turns,
        effect_text=format_card_effect(card),
        owned_count=owned_count,
    )


def build_result_summary_text(
    result: RunResult,
    *,
    total_battles: int,
) -> str:
    return _(
        "{outcome_text}\n"
        "Role {role_name} ({role_id})\n"
        "Reached battle {final_battle_number}/{total_battles}\n"
        "Final HP {final_hp}\n"
        "Collection {collection}"
    ).format(
        outcome_text=format_outcome(result.outcome),
        role_name=get_role_name(get_role_definition(result.role_id)),
        role_id=result.role_id,
        final_battle_number=result.final_battle_number,
        total_battles=total_battles,
        final_hp=result.final_hp,
        collection=format_card_counts(result.final_collection),
    )


def build_role_button_label(
    *,
    index: int,
    role: RoleDefinition,
) -> str:
    return _("{index}. {role_name}\nHP {starting_hp}/{max_hp}\n{description}").format(
        index=index,
        role_name=get_role_name(role),
        starting_hp=role.starting_hp,
        max_hp=role.max_hp,
        description=get_role_description(role),
    )
