from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Container
from textual.screen import Screen
from textual.widgets import Button, Static

from auto_card.i18n import _
from auto_card.ui.helpers import build_result_summary_text


class RunResultScreen(Screen[None]):
    def compose(self) -> ComposeResult:
        yield Static(id="screen-title")
        with Container(id="result-layout", classes="panel"):
            yield Static(id="result-summary")
            yield Button(id="quit-button", variant="error")

    def on_mount(self) -> None:
        self.refresh_text()

    def on_show(self) -> None:
        self.refresh_text()
        result = self.app.session.build_result()
        self.query_one("#result-summary", Static).update(
            build_result_summary_text(
                result,
                total_battles=self.app.session.total_battles,
            )
        )
        self.query_one("#quit-button", Button).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "quit-button":
            self.app.exit()

    def refresh_text(self) -> None:
        self.query_one("#screen-title", Static).update(_("Run Complete"))
        self.query_one("#quit-button", Button).label = _("Quit")
