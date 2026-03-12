from __future__ import annotations

from textual import events
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Static

from auto_card.content import ROLES
from auto_card.ui.helpers import build_role_button_label


class RoleSelectScreen(Screen[None]):
    def compose(self) -> ComposeResult:
        yield Static("Choose Your Role", id="screen-title")
        with Vertical(id="role-layout"):
            yield Static(
                "Pick a role to initialize its starting collection and reward pool.",
                id="role-summary",
                classes="panel",
            )
            with Horizontal(id="role-options"):
                for index, _role in enumerate(ROLES.values(), start=1):
                    yield Button(
                        id=f"role-{index}",
                        classes="role-card",
                        variant="primary",
                    )

    def on_screen_resume(self) -> None:
        for index, role in enumerate(ROLES.values(), start=1):
            button = self.query_one(f"#role-{index}", Button)
            button.label = build_role_button_label(index=index, role=role)
            button.disabled = False
        self.query_one("#role-1", Button).focus()

    def on_key(self, event: events.Key) -> None:
        if event.key in {str(index) for index in range(1, len(ROLES) + 1)}:
            self._choose(int(event.key))
            event.stop()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id is None or not event.button.id.startswith("role-"):
            return
        self._choose(int(event.button.id.split("-")[1]))

    def _choose(self, option_index: int) -> None:
        role = list(ROLES.values())[option_index - 1]
        self.app.select_role(role.id)
