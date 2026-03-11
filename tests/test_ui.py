from __future__ import annotations

import asyncio
from collections import Counter

from textual.widgets import Button, DataTable, Static

from auto_card.ui import TextualCardApp


async def build_base_deck_and_start_battle(app: TextualCardApp, pilot) -> None:
    del app
    await pilot.press("enter", "enter", "enter", "enter")
    await pilot.press("down", "enter", "enter")
    await pilot.press("down", "down", "down", "enter")
    await pilot.press("up", "enter", "enter", "enter")
    await pilot.press("tab", "tab", "enter")


async def wait_for_screen(app: TextualCardApp, pilot, screen_name: str) -> None:
    for _ in range(200):
        if type(app.screen).__name__ == screen_name:
            return
        await pilot.pause(0.01)
    raise AssertionError(
        f"Timed out waiting for {screen_name}; got {type(app.screen).__name__}."
    )


def get_table_rows(table: DataTable) -> list[tuple[str, ...]]:
    return [
        tuple(str(cell) for cell in table.get_row_at(index))
        for index in range(table.row_count)
    ]


def test_textual_deck_builder_adds_and_removes_cards() -> None:
    async def scenario() -> None:
        app = TextualCardApp(seed=19, battle_delay=0.001, end_delay=0.001)
        async with app.run_test() as pilot:
            start_button = app.screen.query_one("#start-battle", Button)
            assert start_button.disabled is True

            await pilot.press("enter")
            deck_table = app.screen.query_one("#deck-table", DataTable)
            assert deck_table.row_count == 1

            await pilot.press("tab", "enter")
            deck_table = app.screen.query_one("#deck-table", DataTable)
            start_button = app.screen.query_one("#start-battle", Button)
            assert deck_table.row_count == 0
            assert start_button.disabled is True

    asyncio.run(scenario())


def test_textual_run_flows_from_battle_to_reward_to_next_deck_choice() -> None:
    async def scenario() -> None:
        app = TextualCardApp(seed=19, battle_delay=0.001, end_delay=0.001)
        async with app.run_test() as pilot:
            starting_counts = Counter(app.session.collection)

            await build_base_deck_and_start_battle(app, pilot)
            await wait_for_screen(app, pilot, "RewardScreen")

            assert type(app.screen).__name__ == "RewardScreen"
            reward_request = app.session.get_reward_choice_request()
            chosen_card = reward_request.options[0]

            await pilot.press("1")
            await wait_for_screen(app, pilot, "DeckBuilderScreen")

            assert type(app.screen).__name__ == "DeckBuilderScreen"
            assert app.session.phase == "deck_choice"
            assert app.session.battle_number == 2
            assert Counter(app.session.collection)[chosen_card] == (
                starting_counts[chosen_card] + 1
            )

            deck_summary = app.screen.query_one("#deck-summary", Static)
            deck_table = app.screen.query_one("#deck-table", DataTable)
            start_button = app.screen.query_one("#start-battle", Button)
            assert "Battle 2/6" in str(deck_summary.render())
            assert "HP 46/50" in str(deck_summary.render())
            assert get_table_rows(deck_table) == [
                ("Strike", "4", "1", "Deal 7"),
                ("Heavy Strike", "2", "3", "Deal 18"),
                ("Defend", "3", "1", "Gain 5 armor"),
                ("Fortify", "1", "2", "Gain 12 armor"),
            ]
            assert start_button.disabled is False

    asyncio.run(scenario())


def test_textual_second_battle_reaches_fresh_reward_screen() -> None:
    async def scenario() -> None:
        app = TextualCardApp(seed=19, battle_delay=0.001, end_delay=0.001)
        async with app.run_test() as pilot:
            await build_base_deck_and_start_battle(app, pilot)
            await wait_for_screen(app, pilot, "RewardScreen")
            await pilot.press("1")
            await wait_for_screen(app, pilot, "DeckBuilderScreen")

            await build_base_deck_and_start_battle(app, pilot)
            await wait_for_screen(app, pilot, "RewardScreen")

            reward_summary = app.screen.query_one("#reward-summary", Static)
            assert app.session.phase == "reward_choice"
            assert app.session.battle_number == 2
            assert "Battle 2 cleared" in str(reward_summary.render())

    asyncio.run(scenario())
