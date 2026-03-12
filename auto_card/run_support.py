from __future__ import annotations

import random
from collections import Counter
from collections.abc import Callable, Sequence

from auto_card.content import (
    BOSS_ENEMY_ID,
    CARD_ORDER,
    NORMAL_ENEMY_IDS,
    get_enemy_definition,
)
from auto_card.models import BattleResult, EnemyDefinition, RunBattleRecord, RunBattleType

LogEmitter = Callable[[str], None]


def build_battle_record(
    *,
    battle_number: int,
    battle_type: RunBattleType,
    enemy_id: str,
    deck_ids: tuple[str, ...],
    battle_seed: int,
    result: BattleResult,
    reward_options: tuple[str, ...] = (),
    reward_choice: str | None = None,
) -> RunBattleRecord:
    return RunBattleRecord(
        battle_number=battle_number,
        battle_type=battle_type,
        enemy_id=enemy_id,
        deck_ids=deck_ids,
        battle_seed=battle_seed,
        result=result,
        reward_options=reward_options,
        reward_choice=reward_choice,
    )


def canonicalize_card_ids(card_ids: Sequence[str]) -> tuple[str, ...]:
    counts = Counter(card_ids)
    ordered: list[str] = []
    for card_id in CARD_ORDER:
        ordered.extend([card_id] * counts.get(card_id, 0))
    return tuple(ordered)


def format_card_counts(
    card_ids: Sequence[str],
    *,
    cards: dict[str, object],
) -> str:
    counts = Counter(card_ids)
    parts = [
        f"{cards[card_id].name} x{counts[card_id]}"
        for card_id in CARD_ORDER
        if counts.get(card_id, 0)
    ]
    return ", ".join(parts)


def format_card_list(
    card_ids: Sequence[str],
    *,
    cards: dict[str, object],
) -> str:
    return ", ".join(f"{cards[card_id].name} [{card_id}]" for card_id in card_ids)


def choose_enemy(*, battle_type: RunBattleType, rng: random.Random) -> EnemyDefinition:
    if battle_type == "boss":
        return get_enemy_definition(BOSS_ENEMY_ID)
    enemy_id = rng.choice(NORMAL_ENEMY_IDS)
    return get_enemy_definition(enemy_id)


def record_line(
    log_lines: list[str],
    log_emitter: LogEmitter | None,
    line: str,
) -> None:
    log_lines.append(line)
    if log_emitter is not None:
        log_emitter(line)
