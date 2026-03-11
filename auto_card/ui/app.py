from __future__ import annotations

from collections import Counter

from textual import events
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, DataTable, RichLog, Static

from auto_card.content import CARDS, RUN_DECK_SIZE
from auto_card.models import ActiveCardSnapshot, CombatantSnapshot
from auto_card.presentation import format_card_effect, get_card_type
from auto_card.run import RunSession, format_card_counts


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
        collection_counts = Counter(request.collection)
        deck_counts = Counter(self._selected_deck)
        available_counts = collection_counts - deck_counts

        collection_table = self.query_one("#collection-table", DataTable)
        collection_row = collection_table.cursor_row if collection_table.row_count else 0
        selected_collection_card_id = self._selected_row_id(
            self._collection_row_ids,
            collection_row,
        )
        collection_table.clear()
        self._collection_row_ids = []
        for card_id, card in CARDS.items():
            available_count = available_counts.get(card_id, 0)
            if not available_count:
                continue
            self._collection_row_ids.append(card_id)
            collection_table.add_row(
                card.name,
                get_card_type(card),
                str(card.charge_turns),
                str(available_count),
                format_card_effect(card),
            )
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
        self._deck_row_ids = []
        for card_id, count in sorted(
            deck_counts.items(),
            key=lambda item: list(CARDS).index(item[0]),
        ):
            card = CARDS[card_id]
            self._deck_row_ids.append(card_id)
            deck_table.add_row(
                card.name,
                str(count),
                str(card.charge_turns),
                format_card_effect(card),
            )
        self._restore_cursor(
            table=deck_table,
            row_ids=self._deck_row_ids,
            selected_row_id=selected_deck_card_id,
            previous_row=deck_row,
        )

        self.query_one("#deck-summary", Static).update(
            (
                f"Battle {request.battle_number}/{request.total_battles} "
                f"vs {request.enemy.name} [{request.enemy.id}] ({request.battle_type})\n"
                f"HP {request.current_hp}/{request.max_hp} | "
                f"Deck {len(self._selected_deck)}/{RUN_DECK_SIZE}"
            )
        )
        self.query_one("#deck-hint", Static).update(
            "Enter/A add • Enter/D/Backspace remove • Tab switch focus"
        )

        start_button = self.query_one("#start-battle", Button)
        start_button.disabled = len(self._selected_deck) != RUN_DECK_SIZE
        if len(self._selected_deck) == RUN_DECK_SIZE:
            start_button.label = "Start Battle"
        else:
            start_button.label = f"Start Battle ({len(self._selected_deck)}/{RUN_DECK_SIZE})"

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


class BattleScreen(Screen[None]):
    def __init__(self) -> None:
        super().__init__()
        self._frame_index = 0
        self._is_running = False

    def compose(self) -> ComposeResult:
        yield Static("Battle Replay", id="screen-title")
        with Vertical(id="battle-layout"):
            with Horizontal(id="battle-top"):
                yield Static(id="player-panel", classes="panel stat-card")
                yield Static(id="enemy-panel", classes="panel stat-card")
            yield Static(id="current-card-panel", classes="panel hero-card")
            with Horizontal(id="battle-bottom"):
                yield Static(id="deck-panel", classes="panel")
                with Vertical(id="battle-log-panel", classes="panel"):
                    yield Static("Combat Log", classes="section-title")
                    yield RichLog(id="battle-log", wrap=True, highlight=True, markup=False)

    def on_screen_resume(self) -> None:
        self._frame_index = 0
        self._is_running = True
        replay = self.app.session.current_battle_replay
        self.query_one("#battle-log", RichLog).clear()
        for line in replay.opening_log_lines:
            self.query_one("#battle-log", RichLog).write(line)

        first_frame = replay.frames[0]
        self._update_combatant_panels(
            player=first_frame.player_start,
            enemy=first_frame.enemy_start,
        )
        self._update_current_card(None)
        self._update_deck_panel(
            draw_pile_count=len(replay.deck_ids),
            discard_pile_count=0,
            is_charge_blocked=False,
        )
        self._schedule_next_frame(self.app.battle_delay)

    def on_hide(self) -> None:
        self._is_running = False

    def _schedule_next_frame(self, delay: float) -> None:
        if not self._is_running:
            return
        self.set_timer(delay, self._advance_frame)

    def _advance_frame(self) -> None:
        if not self._is_running:
            return

        replay = self.app.session.current_battle_replay
        if self._frame_index >= len(replay.frames):
            self._is_running = False
            self.set_timer(self.app.end_delay, self.app.finish_battle_replay)
            return

        frame = replay.frames[self._frame_index]
        self._frame_index += 1

        self._update_combatant_panels(
            player=frame.player_end,
            enemy=frame.enemy_end,
        )
        self._update_current_card(frame.active_card)
        self._update_deck_panel(
            draw_pile_count=frame.draw_pile_count,
            discard_pile_count=frame.discard_pile_count,
            is_charge_blocked=frame.is_charge_blocked,
        )
        battle_log = self.query_one("#battle-log", RichLog)
        for line in frame.log_lines:
            battle_log.write(line)

        if self._frame_index >= len(replay.frames):
            self._is_running = False
            self.set_timer(self.app.end_delay, self.app.finish_battle_replay)
            return
        self._schedule_next_frame(self.app.battle_delay)

    def _update_combatant_panels(
        self,
        *,
        player: CombatantSnapshot,
        enemy: CombatantSnapshot,
    ) -> None:
        session = self.app.session
        self.query_one("#player-panel", Static).update(
            (
                f"Player\n"
                f"Battle {session.battle_number}/{session.total_battles}\n"
                f"HP {player.hp}/{player.max_hp}\n"
                f"Armor {player.armor}"
            )
        )
        self.query_one("#enemy-panel", Static).update(
            (
                f"{enemy.name}\n"
                f"HP {enemy.hp}/{enemy.max_hp}\n"
                f"Armor {enemy.armor}"
            )
        )

    def _update_current_card(self, active_card: ActiveCardSnapshot | None) -> None:
        if active_card is None:
            self.query_one("#current-card-panel", Static).update(
                "Current Card\nWaiting for the next draw."
            )
            return

        self.query_one("#current-card-panel", Static).update(
            (
                f"{active_card.name}\n"
                f"{active_card.card_type} • {active_card.status_text}\n"
                f"Charge {active_card.charge_progress}/{active_card.charge_turns}\n"
                f"{active_card.effect_text}"
            )
        )

    def _update_deck_panel(
        self,
        *,
        draw_pile_count: int,
        discard_pile_count: int,
        is_charge_blocked: bool,
    ) -> None:
        replay = self.app.session.current_battle_replay
        self.query_one("#deck-panel", Static).update(
            (
                "Deck State\n"
                f"Draw {draw_pile_count}\n"
                f"Discard {discard_pile_count}\n"
                f"Charge Blocked {'Yes' if is_charge_blocked else 'No'}\n"
                f"{format_card_counts(replay.deck_ids)}"
            )
        )


class RewardScreen(Screen[None]):
    def compose(self) -> ComposeResult:
        yield Static("Choose One Reward", id="screen-title")
        with Vertical(id="reward-layout"):
            yield Static(id="reward-summary", classes="panel")
            with Horizontal(id="reward-options"):
                yield Button(id="reward-1", classes="reward-card", variant="primary")
                yield Button(id="reward-2", classes="reward-card", variant="primary")
                yield Button(id="reward-3", classes="reward-card", variant="primary")

    def on_screen_resume(self) -> None:
        request = self.app.session.get_reward_choice_request()
        owned_counts = Counter(request.collection)
        self.query_one("#reward-summary", Static).update(
            (
                f"HP {request.current_hp}/{request.max_hp}\n"
                f"Battle {request.battle_number} cleared against {request.enemy.name}\n"
                f"Next: battle {self.app.session.next_battle_number}/{self.app.session.total_battles} "
                f"({self.app.session.next_battle_type})"
            )
        )
        for index, card_id in enumerate(request.options, start=1):
            card = CARDS[card_id]
            button = self.query_one(f"#reward-{index}", Button)
            button.label = (
                f"{index}. {card.name}\n"
                f"{get_card_type(card)} • Charge {card.charge_turns}\n"
                f"{format_card_effect(card)}\n"
                f"Owned {owned_counts.get(card_id, 0)}"
            )
            button.disabled = False
        self.query_one("#reward-1", Button).focus()

    def on_key(self, event: events.Key) -> None:
        if event.key in {"1", "2", "3"}:
            self._choose(int(event.key))
            event.stop()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id is None or not event.button.id.startswith("reward-"):
            return
        self._choose(int(event.button.id.split("-")[1]))

    def _choose(self, option_index: int) -> None:
        request = self.app.session.get_reward_choice_request()
        self.app.choose_reward(request.options[option_index - 1])


class RunResultScreen(Screen[None]):
    def compose(self) -> ComposeResult:
        yield Static("Run Complete", id="screen-title")
        with Container(id="result-layout", classes="panel"):
            yield Static(id="result-summary")
            yield Button("Quit", id="quit-button", variant="error")

    def on_show(self) -> None:
        result = self.app.session.build_result()
        outcome_text = "Victory" if result.outcome == "victory" else "Defeat"
        self.query_one("#result-summary", Static).update(
            (
                f"{outcome_text}\n"
                f"Reached battle {result.final_battle_number}/{self.app.session.total_battles}\n"
                f"Final HP {result.final_hp}\n"
                f"Collection {format_card_counts(result.final_collection)}"
            )
        )
        self.query_one("#quit-button", Button).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "quit-button":
            self.app.exit()


class TextualCardApp(App[None]):
    CSS_PATH = "app.tcss"
    BINDINGS = [Binding("q", "quit", "Quit")]

    def __init__(
        self,
        *,
        seed: int = 0,
        battle_delay: float = 0.2,
        end_delay: float = 0.5,
    ) -> None:
        super().__init__()
        self.seed = seed
        self.battle_delay = battle_delay
        self.end_delay = end_delay
        self.session = RunSession(seed=seed)
        self.title = "Auto Card"
        self.sub_title = "Textual MVP"

    def on_mount(self) -> None:
        self.install_screen(DeckBuilderScreen(), "deck-builder")
        self.install_screen(BattleScreen(), "battle")
        self.install_screen(RewardScreen(), "reward")
        self.install_screen(RunResultScreen(), "result")
        self.push_screen("deck-builder")

    def start_battle(self, deck_ids: tuple[str, ...]) -> None:
        self.session.submit_deck_choice(deck_ids)
        self.switch_screen("battle")

    def finish_battle_replay(self) -> None:
        self.session.complete_battle_replay()
        if self.session.phase == "reward_choice":
            self.switch_screen("reward")
            return
        self.switch_screen("result")

    def choose_reward(self, reward_choice: str) -> None:
        self.session.submit_reward_choice(reward_choice)
        self.switch_screen("deck-builder")
