from __future__ import annotations

from textual.app import App
from textual.binding import Binding

from auto_card.run import RunSession
from auto_card.ui.battle_screen import BattleScreen
from auto_card.ui.deck_builder import DeckBuilderScreen
from auto_card.ui.result_screen import RunResultScreen
from auto_card.ui.reward_screen import RewardScreen


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
