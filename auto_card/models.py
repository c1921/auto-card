from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

BattleOutcome = Literal["victory", "defeat"]
EffectKind = Literal["damage", "armor", "heal", "apply_status"]
EffectTarget = Literal["self", "opponent"]
StatusKind = Literal["poison", "strength", "stun"]
EnemyActionKind = str
RunBattleType = Literal["normal", "boss"]
RunPhase = Literal["deck_choice", "battle_replay", "reward_choice", "finished"]


@dataclass(frozen=True)
class GameConfig:
    player_name: str
    starting_armor: int
    run_deck_size: int
    normal_battle_count: int
    total_battle_count: int
    reward_option_count: int
    default_role_id: str
    normal_enemy_ids: tuple[str, ...]
    boss_enemy_id: str


@dataclass(frozen=True)
class EffectDefinition:
    kind: EffectKind
    target: EffectTarget
    value: int
    status: StatusKind | None = None


@dataclass(frozen=True)
class CardDefinition:
    id: str
    name: str
    sort_order: int
    charge_turns: int
    effects: tuple[EffectDefinition, ...]
    pools: tuple[str, ...]

    @property
    def is_charge_card(self) -> bool:
        return self.charge_turns > 1


@dataclass(frozen=True)
class EnemyActionDefinition:
    id: str
    name: str
    weight: int
    effects: tuple[EffectDefinition, ...]


@dataclass(frozen=True)
class EnemyDefinition:
    id: str
    name: str
    max_hp: int
    actions: tuple[EnemyActionDefinition, ...]


@dataclass(frozen=True)
class RoleDefinition:
    id: str
    name: str
    description: str
    max_hp: int
    starting_hp: int
    starting_collection: tuple[str, ...]
    starting_deck: tuple[str, ...]
    card_pools: tuple[str, ...]


@dataclass(frozen=True)
class StatusSnapshot:
    kind: StatusKind
    value: int


@dataclass
class Combatant:
    name: str
    max_hp: int
    hp: int
    armor: int = 0
    statuses: dict[StatusKind, int] = field(default_factory=dict)


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
    statuses: tuple[StatusSnapshot, ...]


@dataclass(frozen=True)
class BattleResult:
    outcome: BattleOutcome
    turns: int
    player: CombatantSnapshot
    enemy: CombatantSnapshot
    log_lines: tuple[str, ...]
    seed: int
    enemy_id: str
    role_id: str


@dataclass(frozen=True)
class ActiveCardSnapshot:
    card_id: str
    charge_turns: int
    charge_progress: int
    status_key: str


@dataclass(frozen=True)
class BattleTurnFrame:
    turn: int
    player_start: CombatantSnapshot
    enemy_start: CombatantSnapshot
    player_end: CombatantSnapshot
    enemy_end: CombatantSnapshot
    draw_pile_count: int
    discard_pile_count: int
    active_card: ActiveCardSnapshot | None
    is_charge_blocked: bool
    enemy_action: EnemyActionKind
    enemy_action_name: str
    enemy_action_summary: str
    log_lines: tuple[str, ...]


@dataclass(frozen=True)
class BattleReplay:
    result: BattleResult
    deck_ids: tuple[str, ...]
    opening_log_lines: tuple[str, ...]
    frames: tuple[BattleTurnFrame, ...]


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
    role_id: str
