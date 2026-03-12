from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import RichLog, Static

from auto_card.i18n import _
from auto_card.models import ActiveCardSnapshot, CombatantSnapshot
from auto_card.ui.helpers import (
    build_current_card_text,
    build_deck_panel_text,
    build_enemy_panel_text,
    build_player_panel_text,
)


class BattleScreen(Screen[None]):
    def __init__(self) -> None:
        super().__init__()
        self._frame_index = 0
        self._is_running = False

    def compose(self) -> ComposeResult:
        yield Static(id="screen-title")
        with Vertical(id="battle-layout"):
            with Horizontal(id="battle-top"):
                yield Static(id="player-panel", classes="panel stat-card")
                yield Static(id="enemy-panel", classes="panel stat-card")
            yield Static(id="current-card-panel", classes="panel hero-card")
            with Horizontal(id="battle-bottom"):
                yield Static(id="deck-panel", classes="panel")
                with Vertical(id="battle-log-panel", classes="panel"):
                    yield Static(id="battle-log-title", classes="section-title")
                    yield RichLog(id="battle-log", wrap=True, highlight=True, markup=False)

    def on_mount(self) -> None:
        self.refresh_text()

    def on_screen_resume(self) -> None:
        self.refresh_text()
        self._frame_index = 0
        self._is_running = True
        replay = self.app.session.current_battle_replay
        battle_log = self.query_one("#battle-log", RichLog)
        battle_log.clear()
        for line in replay.opening_log_lines:
            battle_log.write(line)

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
            build_player_panel_text(
                player=player,
                battle_number=session.battle_number,
                total_battles=session.total_battles,
                role=session.role,
            )
        )
        self.query_one("#enemy-panel", Static).update(
            build_enemy_panel_text(enemy, enemy_name=session.current_enemy.name)
        )

    def _update_current_card(self, active_card: ActiveCardSnapshot | None) -> None:
        self.query_one("#current-card-panel", Static).update(
            build_current_card_text(active_card)
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
            build_deck_panel_text(
                draw_pile_count=draw_pile_count,
                discard_pile_count=discard_pile_count,
                is_charge_blocked=is_charge_blocked,
                deck_ids=replay.deck_ids,
            )
        )

    def refresh_text(self) -> None:
        self.query_one("#screen-title", Static).update(_("Battle Replay"))
        self.query_one("#battle-log-title", Static).update(_("Combat Log"))
        if self.app._session is None or self.app.session.phase != "battle_replay":
            return
        replay = self.app.session.current_battle_replay
        frame_index = min(self._frame_index, len(replay.frames))
        if frame_index == 0:
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
            return

        frame = replay.frames[frame_index - 1]
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
