from __future__ import annotations

from collections import Counter

from textual import events
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, DataTable, Static

from auto_card.content import RUN_DECK_SIZE
from auto_card.ui.helpers import (
    build_collection_table_rows,
    build_deck_summary_text,
    build_deck_table_rows,
    build_start_battle_label,
)


class DeckBuilderScreen(Screen[None]):
    def __init__(self) -> None:
        super().__init__()
        self._selected_deck: list[str] = []
        self._collection_row_ids: list[str] = []
        self._deck_row_ids: list[str] = []

    def compose(self) -> ComposeResult:
        yield Static("Battle Deck Builder", id="screen-title")
        with Horizontal(id="deck-layout"):
            with Vertical(classes="panel"):
                yield Static("Collection", classes="section-title")
                yield DataTable(id="collection-table")
            with Vertical(classes="panel"):
                yield Static("Battle Deck", classes="section-title")
                yield DataTable(id="deck-table")
        with Horizontal(id="deck-footer", classes="panel footer-panel"):
            yield Static(id="deck-summary")
            yield Static(id="deck-hint")
            yield Button("Start Battle", id="start-battle", variant="success")

    def on_mount(self) -> None:
        collection_table = self.query_one("#collection-table", DataTable)
        collection_table.cursor_type = "row"
        collection_table.add_columns("Name", "Type", "Charge", "Available", "Effect")

        deck_table = self.query_one("#deck-table", DataTable)
        deck_table.cursor_type = "row"
        deck_table.add_columns("Name", "Count", "Charge", "Effect")

    def on_screen_resume(self) -> None:
        self._refresh()
        collection_table = self.query_one("#collection-table", DataTable)
        if collection_table.row_count:
            collection_table.move_cursor(row=0)
        collection_table.focus()

    def reset(self) -> None:
        self._selected_deck = []
        self._collection_row_ids = []
        self._deck_row_ids = []

    def on_key(self, event: events.Key) -> None:
        focused = self.app.focused
        if event.key == "a" and focused is self.query_one("#collection-table", DataTable):
            self._add_selected_collection_card()
            event.stop()
            return
        if event.key in {"d", "backspace"} and focused is self.query_one(
            "#deck-table", DataTable
        ):
            self._remove_selected_deck_card()
            event.stop()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.control.id == "collection-table":
            self._add_card_from_collection_index(event.cursor_row)
            return
        if event.control.id == "deck-table":
            self._remove_card_from_deck_index(event.cursor_row)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id != "start-battle":
            return
        self.app.start_battle(tuple(self._selected_deck))

    def _refresh(self) -> None:
        request = self.app.session.get_deck_choice_request()

        collection_table = self.query_one("#collection-table", DataTable)
        collection_row = collection_table.cursor_row if collection_table.row_count else 0
        selected_collection_card_id = self._selected_row_id(
            self._collection_row_ids,
            collection_row,
        )
        collection_table.clear()
        self._collection_row_ids, collection_rows = build_collection_table_rows(
            collection=request.collection,
            selected_deck=self._selected_deck,
        )
        for row in collection_rows:
            collection_table.add_row(*row)
        self._restore_cursor(
            table=collection_table,
            row_ids=self._collection_row_ids,
            selected_row_id=selected_collection_card_id,
            previous_row=collection_row,
        )

        deck_table = self.query_one("#deck-table", DataTable)
        deck_row = deck_table.cursor_row if deck_table.row_count else 0
        selected_deck_card_id = self._selected_row_id(self._deck_row_ids, deck_row)
        deck_table.clear()
        self._deck_row_ids, deck_rows = build_deck_table_rows(self._selected_deck)
        for row in deck_rows:
            deck_table.add_row(*row)
        self._restore_cursor(
            table=deck_table,
            row_ids=self._deck_row_ids,
            selected_row_id=selected_deck_card_id,
            previous_row=deck_row,
        )

        selected_count = len(self._selected_deck)
        self.query_one("#deck-summary", Static).update(
            build_deck_summary_text(request, selected_count=selected_count)
        )
        self.query_one("#deck-hint", Static).update(
            "Enter/A add • Enter/D/Backspace remove • Tab switch focus"
        )

        start_button = self.query_one("#start-battle", Button)
        start_button.disabled = selected_count != RUN_DECK_SIZE
        start_button.label = build_start_battle_label(selected_count)

    def _add_selected_collection_card(self) -> None:
        table = self.query_one("#collection-table", DataTable)
        if not self._collection_row_ids:
            return
        self._add_card_from_collection_index(table.cursor_row)

    def _add_card_from_collection_index(self, index: int) -> None:
        if len(self._selected_deck) >= RUN_DECK_SIZE:
            return
        if not 0 <= index < len(self._collection_row_ids):
            return

        card_id = self._collection_row_ids[index]
        request = self.app.session.get_deck_choice_request()
        owned_count = Counter(request.collection)[card_id]
        chosen_count = self._selected_deck.count(card_id)
        if chosen_count >= owned_count:
            return

        self._selected_deck.append(card_id)
        self._refresh()

    def _remove_selected_deck_card(self) -> None:
        table = self.query_one("#deck-table", DataTable)
        if not self._deck_row_ids:
            return
        self._remove_card_from_deck_index(table.cursor_row)

    def _remove_card_from_deck_index(self, index: int) -> None:
        if not 0 <= index < len(self._deck_row_ids):
            return
        card_id = self._deck_row_ids[index]
        self._selected_deck.remove(card_id)
        self._refresh()

    def _selected_row_id(self, row_ids: list[str], index: int) -> str | None:
        if 0 <= index < len(row_ids):
            return row_ids[index]
        return None

    def _restore_cursor(
        self,
        *,
        table: DataTable,
        row_ids: list[str],
        selected_row_id: str | None,
        previous_row: int,
    ) -> None:
        if not row_ids:
            return
        if selected_row_id in row_ids:
            table.move_cursor(row=row_ids.index(selected_row_id))
            return
        table.move_cursor(row=min(previous_row, len(row_ids) - 1))
