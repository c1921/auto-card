from __future__ import annotations

import asyncio
from collections import Counter

from textual.widgets import Button, DataTable, Static

from auto_card.content import CARD_ORDER, CARDS, get_role_definition
from auto_card.presentation import format_card_effect, get_card_type
from auto_card.ui import TextualCardApp

ADVENTURER = get_role_definition("adventurer")


def get_table_rows(table: DataTable) -> list[tuple[str, ...]]:
    return [
        tuple(str(cell) for cell in table.get_row_at(index))
        for index in range(table.row_count)
    ]


def find_row_index(table: DataTable, name: str) -> int:
    for index, row in enumerate(get_table_rows(table)):
        if row[0] == name:
            return index
    raise AssertionError(f"Unable to find row for {name}.")


async def add_collection_card(
    app: TextualCardApp,
    pilot,
    *,
    card_name: str,
    copies: int = 1,
) -> None:
    for _ in range(copies):
        collection_table = app.screen.query_one("#collection-table", DataTable)
        collection_table.focus()
        collection_table.move_cursor(row=find_row_index(collection_table, card_name))
        await pilot.pause(0.01)
        await pilot.press("enter")


async def remove_deck_card(
    app: TextualCardApp,
    pilot,
    *,
    card_name: str,
    copies: int = 1,
) -> None:
    for _ in range(copies):
        deck_table = app.screen.query_one("#deck-table", DataTable)
        deck_table.focus()
        deck_table.move_cursor(row=find_row_index(deck_table, card_name))
        await pilot.pause(0.01)
        await pilot.press("enter")


async def start_battle(app: TextualCardApp, pilot) -> None:
    start_button = app.screen.query_one("#start-battle", Button)
    start_button.focus()
    await pilot.pause(0.01)
    await pilot.press("enter")


async def build_base_deck_and_start_battle(app: TextualCardApp, pilot) -> None:
    target_counts = [
        ("Strike", 4),
        ("Heavy Strike", 1),
        ("Fortify", 1),
        ("Recover", 1),
        ("Defend", 3),
    ]
    deck_table = app.screen.query_one("#deck-table", DataTable)
    current_counts = {row[0]: int(row[1]) for row in get_table_rows(deck_table)}
    for card_name, target_count in target_counts:
        missing_count = target_count - current_counts.get(card_name, 0)
        if missing_count > 0:
            await add_collection_card(
                app,
                pilot,
                card_name=card_name,
                copies=missing_count,
            )
    await start_battle(app, pilot)


async def wait_for_screen(app: TextualCardApp, pilot, screen_name: str) -> None:
    for _ in range(200):
        if type(app.screen).__name__ == screen_name:
            return
        await pilot.pause(0.01)
    raise AssertionError(
        f"Timed out waiting for {screen_name}; got {type(app.screen).__name__}."
    )


def build_expected_collection_rows(counts: Counter[str]) -> list[tuple[str, ...]]:
    rows: list[tuple[str, ...]] = []
    for card_id in CARD_ORDER:
        card = CARDS[card_id]
        available_count = counts.get(card_id, 0)
        if not available_count:
            continue
        rows.append(
            (
                card.name,
                get_card_type(card),
                str(card.charge_turns),
                str(available_count),
                format_card_effect(card),
            )
        )
    return rows


def test_textual_role_selection_initializes_session() -> None:
    async def scenario() -> None:
        app = TextualCardApp(
            seed=19,
            language="en",
            battle_delay=0.001,
            end_delay=0.001,
        )
        async with app.run_test() as pilot:
            assert type(app.screen).__name__ == "RoleSelectScreen"
            first_button = app.screen.query_one("#role-1", Button)
            assert "Adventurer" in str(first_button.label)

            await pilot.press("1")
            await wait_for_screen(app, pilot, "DeckBuilderScreen")

            assert app.session.role.id == "adventurer"
            deck_summary = app.screen.query_one("#deck-summary", Static)
            assert "Adventurer (adventurer)" in str(deck_summary.render())

    asyncio.run(scenario())


def test_textual_deck_builder_adds_and_removes_cards() -> None:
    async def scenario() -> None:
        app = TextualCardApp(
            seed=19,
            role_id="adventurer",
            language="en",
            battle_delay=0.001,
            end_delay=0.001,
        )
        async with app.run_test() as pilot:
            collection_table = app.screen.query_one("#collection-table", DataTable)
            start_button = app.screen.query_one("#start-battle", Button)
            assert get_table_rows(collection_table)[0] == (
                "Strike",
                "Attack",
                "1",
                "4",
                "Deal 7",
            )
            assert start_button.disabled is True

            await add_collection_card(app, pilot, card_name="Strike")
            collection_table = app.screen.query_one("#collection-table", DataTable)
            deck_table = app.screen.query_one("#deck-table", DataTable)
            assert get_table_rows(collection_table)[0] == (
                "Strike",
                "Attack",
                "1",
                "3",
                "Deal 7",
            )
            assert get_table_rows(deck_table) == [("Strike", "1", "1", "Deal 7")]

            await add_collection_card(app, pilot, card_name="Strike", copies=3)
            collection_table = app.screen.query_one("#collection-table", DataTable)
            deck_table = app.screen.query_one("#deck-table", DataTable)
            assert all(row[0] != "Strike" for row in get_table_rows(collection_table))
            assert get_table_rows(deck_table) == [("Strike", "4", "1", "Deal 7")]

            await remove_deck_card(app, pilot, card_name="Strike")
            collection_table = app.screen.query_one("#collection-table", DataTable)
            deck_table = app.screen.query_one("#deck-table", DataTable)
            start_button = app.screen.query_one("#start-battle", Button)
            assert get_table_rows(collection_table)[0] == (
                "Strike",
                "Attack",
                "1",
                "1",
                "Deal 7",
            )
            assert get_table_rows(deck_table) == [("Strike", "3", "1", "Deal 7")]
            assert start_button.disabled is True

    asyncio.run(scenario())


def test_textual_run_flows_from_battle_to_reward_to_next_deck_choice() -> None:
    async def scenario() -> None:
        app = TextualCardApp(
            seed=19,
            role_id="adventurer",
            language="en",
            battle_delay=0.001,
            end_delay=0.001,
        )
        async with app.run_test() as pilot:
            starting_counts = Counter(app.session.collection)

            await build_base_deck_and_start_battle(app, pilot)
            await wait_for_screen(app, pilot, "RewardScreen")

            reward_request = app.session.get_reward_choice_request()
            chosen_card = reward_request.options[0]

            await pilot.press("1")
            await wait_for_screen(app, pilot, "DeckBuilderScreen")

            assert app.session.phase == "deck_choice"
            assert app.session.battle_number == 2
            assert Counter(app.session.collection)[chosen_card] == (
                starting_counts[chosen_card] + 1
            )

            collection_table = app.screen.query_one("#collection-table", DataTable)
            deck_summary = app.screen.query_one("#deck-summary", Static)
            deck_table = app.screen.query_one("#deck-table", DataTable)
            start_button = app.screen.query_one("#start-battle", Button)
            available_counts = (
                Counter(app.session.collection)
                - Counter(app.screen._selected_deck)
            )
            assert "Battle 2/6" in str(deck_summary.render())
            assert "Adventurer (adventurer)" in str(deck_summary.render())
            assert get_table_rows(collection_table) == build_expected_collection_rows(
                available_counts
            )
            assert get_table_rows(deck_table) == [
                ("Strike", "4", "1", "Deal 7"),
                ("Heavy Strike", "1", "3", "Deal 18"),
                ("Defend", "3", "1", "Gain 5 armor"),
                ("Fortify", "1", "2", "Gain 12 armor"),
                ("Recover", "1", "1", "Heal 3"),
            ]
            assert start_button.disabled is False

    asyncio.run(scenario())


def test_textual_language_toggle_updates_current_screen() -> None:
    async def scenario() -> None:
        app = TextualCardApp(
            seed=19,
            role_id="adventurer",
            language="en",
            battle_delay=0.001,
            end_delay=0.001,
        )
        async with app.run_test() as pilot:
            screen_title = app.screen.query_one("#screen-title", Static)
            start_button = app.screen.query_one("#start-battle", Button)
            deck_summary = app.screen.query_one("#deck-summary", Static)

            assert "Battle Deck Builder" in str(screen_title.render())
            assert str(start_button.label) == "Start Battle (0/10)"

            await pilot.press("l")
            await pilot.pause(0.01)

            assert "战斗组牌" in str(screen_title.render())
            assert str(start_button.label) == "开始战斗（0/10）"
            assert "卡组" in str(deck_summary.render())

    asyncio.run(scenario())
