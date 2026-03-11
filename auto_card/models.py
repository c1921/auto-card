from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

BattleOutcome = Literal["victory", "defeat"]
EnemyActionKind = Literal["attack", "defend", "heal"]
RunBattleType = Literal["normal", "boss"]


@dataclass(frozen=True)
class CardDefinition:
    id: str
    name: str
    charge_turns: int
    damage: int = 0
    armor_gain: int = 0
    heal: int = 0

    @property
    def is_charge_card(self) -> bool:
        return self.charge_turns > 1


@dataclass(frozen=True)
class EnemyDefinition:
    id: str
    name: str
    max_hp: int
    attack_weight: int
    defend_weight: int
    heal_weight: int
    attack_value: int
    defend_value: int
    heal_value: int


@dataclass
class Combatant:
    name: str
    max_hp: int
    hp: int
    armor: int = 0


@dataclass
class ChargeState:
    card: CardDefinition
    progress: int = 1


@dataclass(frozen=True)
class CombatantSnapshot:
    name: str
    max_hp: int
    hp: int
    armor: int


@dataclass(frozen=True)
class BattleResult:
    outcome: BattleOutcome
    turns: int
    player: CombatantSnapshot
    enemy: CombatantSnapshot
    log_lines: tuple[str, ...]
    seed: int
    enemy_id: str


@dataclass(frozen=True)
class RunBattleRecord:
    battle_number: int
    battle_type: RunBattleType
    enemy_id: str
    deck_ids: tuple[str, ...]
    battle_seed: int
    result: BattleResult
    reward_options: tuple[str, ...] = ()
    reward_choice: str | None = None


@dataclass(frozen=True)
class RunResult:
    outcome: BattleOutcome
    final_battle_number: int
    final_hp: int
    final_collection: tuple[str, ...]
    battles: tuple[RunBattleRecord, ...]
    log_lines: tuple[str, ...]
    seed: int
