from __future__ import annotations

from collections import Counter

from textual import events
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Static

from auto_card.ui.helpers import (
    build_reward_button_label,
    build_reward_summary_text,
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
            build_reward_summary_text(
                request,
                next_battle_number=self.app.session.next_battle_number,
                total_battles=self.app.session.total_battles,
                next_battle_type=self.app.session.next_battle_type,
            )
        )
        for index, card_id in enumerate(request.options, start=1):
            button = self.query_one(f"#reward-{index}", Button)
            button.label = build_reward_button_label(
                index=index,
                card_id=card_id,
                owned_count=owned_counts.get(card_id, 0),
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
