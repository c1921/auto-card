from __future__ import annotations

from textual.app import App

from auto_card.content import ROLES
from auto_card.i18n import _, set_language, toggle_language
from auto_card.presentation import get_role_name
from auto_card.run import RunSession
from auto_card.ui.battle_screen import BattleScreen
from auto_card.ui.deck_builder import DeckBuilderScreen
from auto_card.ui.result_screen import RunResultScreen
from auto_card.ui.reward_screen import RewardScreen
from auto_card.ui.role_select import RoleSelectScreen


class TextualCardApp(App[None]):
    CSS_PATH = "app.tcss"
    BINDINGS = []

    def __init__(
        self,
        *,
        seed: int = 0,
        role_id: str | None = None,
        language: str | None = None,
        battle_delay: float = 0.2,
        end_delay: float = 0.5,
    ) -> None:
        self.language = set_language(language)
        super().__init__()
        self.seed = seed
        self.battle_delay = battle_delay
        self.end_delay = end_delay
        self._session = RunSession(seed=seed, role_id=role_id) if role_id else None
        self.title = ""
        self.sub_title = ""
        self._refresh_chrome()

    @property
    def session(self) -> RunSession:
        if self._session is None:
            raise RuntimeError(_("Role has not been selected yet."))
        return self._session

    def on_mount(self) -> None:
        self.bind("q", "quit", description=_("Quit"))
        self.bind("l", "toggle_language", description=_("Toggle Language"))
        self.install_screen(RoleSelectScreen(), "role-select")
        self.install_screen(DeckBuilderScreen(), "deck-builder")
        self.install_screen(BattleScreen(), "battle")
        self.install_screen(RewardScreen(), "reward")
        self.install_screen(RunResultScreen(), "result")
        self.push_screen("deck-builder" if self._session is not None else "role-select")

    def select_role(self, role_id: str) -> None:
        self._session = RunSession(seed=self.seed, role_id=role_id)
        self._refresh_chrome()
        self.get_screen("deck-builder").reset()
        self.switch_screen("deck-builder")

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

    def action_toggle_language(self) -> None:
        self.language = toggle_language()
        self._refresh_chrome()
        self._refresh_current_screen_text()

    def _refresh_chrome(self) -> None:
        self.title = _("Auto Card")
        if self._session is None:
            self.sub_title = _("Textual MVP")
            return
        self.sub_title = _("Textual MVP - {role_name}").format(
            role_name=get_role_name(ROLES[self._session.role.id])
        )

    def _refresh_current_screen_text(self) -> None:
        refresh_text = getattr(self.screen, "refresh_text", None)
        if callable(refresh_text):
            refresh_text()
        self.refresh_bindings()
        self.refresh()
