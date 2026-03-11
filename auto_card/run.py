from __future__ import annotations

import random
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from auto_card.battle import run_battle
from auto_card.content import (
    CARDS,
    NORMAL_ENEMY_IDS,
    PLAYER_MAX_HP,
    PLAYER_STARTING_HP,
    REWARD_CARD_IDS,
    RUN_DECK_SIZE,
    STARTING_COLLECTION,
    TOTAL_BATTLE_COUNT,
    get_enemy_definition,
)
from auto_card.models import EnemyDefinition, RunBattleRecord, RunBattleType, RunResult

DeckChooser = Callable[["DeckChoiceRequest"], Sequence[str]]
RewardChooser = Callable[["RewardChoiceRequest"], str]
LogEmitter = Callable[[str], None]


@dataclass(frozen=True)
class DeckChoiceRequest:
    battle_number: int
    total_battles: int
    battle_type: RunBattleType
    enemy: EnemyDefinition
    current_hp: int
    max_hp: int
    collection: tuple[str, ...]


@dataclass(frozen=True)
class RewardChoiceRequest:
    battle_number: int
    enemy: EnemyDefinition
    current_hp: int
    max_hp: int
    collection: tuple[str, ...]
    options: tuple[str, ...]


def play_run(
    *,
    seed: int = 0,
    deck_chooser: DeckChooser,
    reward_chooser: RewardChooser,
    log_emitter: LogEmitter | None = None,
) -> RunResult:
    rng = random.Random(seed)
    current_hp = PLAYER_STARTING_HP
    collection = list(STARTING_COLLECTION)
    battle_records: list[RunBattleRecord] = []
    log_lines: list[str] = []

    _record_line(
        log_lines,
        log_emitter,
        f"Run start: Player {current_hp}/{PLAYER_MAX_HP} HP.",
    )
    _record_line(log_lines, log_emitter, f"Seed: {seed}")
    _record_line(
        log_lines,
        log_emitter,
        f"Starting collection: {format_card_counts(collection)}",
    )

    for battle_number in range(1, TOTAL_BATTLE_COUNT + 1):
        battle_type = "boss" if battle_number == TOTAL_BATTLE_COUNT else "normal"
        enemy = _choose_enemy(battle_type=battle_type, rng=rng)
        collection_view = canonicalize_card_ids(collection)

        _record_line(log_lines, log_emitter, "")
        _record_line(
            log_lines,
            log_emitter,
            (
                f"Battle {battle_number}/{TOTAL_BATTLE_COUNT}: "
                f"{enemy.name} [{enemy.id}] ({battle_type})."
            ),
        )
        _record_line(
            log_lines,
            log_emitter,
            f"Current HP: {current_hp}/{PLAYER_MAX_HP}",
        )
        _record_line(
            log_lines,
            log_emitter,
            f"Collection: {format_card_counts(collection_view)}",
        )

        deck_request = DeckChoiceRequest(
            battle_number=battle_number,
            total_battles=TOTAL_BATTLE_COUNT,
            battle_type=battle_type,
            enemy=enemy,
            current_hp=current_hp,
            max_hp=PLAYER_MAX_HP,
            collection=collection_view,
        )
        deck_ids = tuple(deck_chooser(deck_request))
        validate_deck_choice(deck_ids=deck_ids, collection=collection_view)
        _record_line(
            log_lines,
            log_emitter,
            f"Chosen deck: {format_card_counts(deck_ids)}",
        )

        battle_seed = rng.randint(0, 2**32 - 1)
        _record_line(log_lines, log_emitter, f"Battle seed: {battle_seed}")
        battle_result = run_battle(
            deck_ids=deck_ids,
            enemy_definition=enemy,
            seed=battle_seed,
            player_start_hp=current_hp,
        )
        for line in battle_result.log_lines:
            _record_line(log_lines, log_emitter, line)

        current_hp = battle_result.player.hp
        if battle_result.outcome == "defeat":
            battle_records.append(
                RunBattleRecord(
                    battle_number=battle_number,
                    battle_type=battle_type,
                    enemy_id=enemy.id,
                    deck_ids=deck_ids,
                    battle_seed=battle_seed,
                    result=battle_result,
                )
            )
            _record_line(log_lines, log_emitter, "")
            _record_line(
                log_lines,
                log_emitter,
                f"Run result: Defeat on battle {battle_number}.",
            )
            return RunResult(
                outcome="defeat",
                final_battle_number=battle_number,
                final_hp=current_hp,
                final_collection=canonicalize_card_ids(collection),
                battles=tuple(battle_records),
                log_lines=tuple(log_lines),
                seed=seed,
            )

        if battle_type == "boss":
            battle_records.append(
                RunBattleRecord(
                    battle_number=battle_number,
                    battle_type=battle_type,
                    enemy_id=enemy.id,
                    deck_ids=deck_ids,
                    battle_seed=battle_seed,
                    result=battle_result,
                )
            )
            _record_line(log_lines, log_emitter, "")
            _record_line(log_lines, log_emitter, "Run result: Victory.")
            return RunResult(
                outcome="victory",
                final_battle_number=battle_number,
                final_hp=current_hp,
                final_collection=canonicalize_card_ids(collection),
                battles=tuple(battle_records),
                log_lines=tuple(log_lines),
                seed=seed,
            )

        reward_options = tuple(rng.sample(REWARD_CARD_IDS, k=3))
        _record_line(
            log_lines,
            log_emitter,
            f"Reward options: {format_card_list(reward_options)}",
        )
        reward_request = RewardChoiceRequest(
            battle_number=battle_number,
            enemy=enemy,
            current_hp=current_hp,
            max_hp=PLAYER_MAX_HP,
            collection=collection_view,
            options=reward_options,
        )
        reward_choice = reward_chooser(reward_request)
        validate_reward_choice(reward_choice=reward_choice, options=reward_options)
        collection.append(reward_choice)
        _record_line(
            log_lines,
            log_emitter,
            (
                f"Reward chosen: {CARDS[reward_choice].name} "
                f"[{reward_choice}]"
            ),
        )
        _record_line(
            log_lines,
            log_emitter,
            f"Collection now: {format_card_counts(collection)}",
        )

        battle_records.append(
            RunBattleRecord(
                battle_number=battle_number,
                battle_type=battle_type,
                enemy_id=enemy.id,
                deck_ids=deck_ids,
                battle_seed=battle_seed,
                result=battle_result,
                reward_options=reward_options,
                reward_choice=reward_choice,
            )
        )

    raise RuntimeError("Run ended without reaching a final battle result.")


def validate_deck_choice(
    *, deck_ids: Sequence[str], collection: Sequence[str]
) -> tuple[str, ...]:
    normalized_deck = tuple(deck_ids)
    if len(normalized_deck) != RUN_DECK_SIZE:
        raise ValueError(
            f"Deck must contain exactly {RUN_DECK_SIZE} cards, "
            f"got {len(normalized_deck)}."
        )

    missing = sorted({card_id for card_id in normalized_deck if card_id not in CARDS})
    if missing:
        raise ValueError(f"Unknown card ids in deck choice: {', '.join(missing)}")

    owned_counts = Counter(collection)
    deck_counts = Counter(normalized_deck)
    overspent = [
        (
            card_id,
            chosen_count,
            owned_counts.get(card_id, 0),
        )
        for card_id, chosen_count in deck_counts.items()
        if chosen_count > owned_counts.get(card_id, 0)
    ]
    if overspent:
        details = ", ".join(
            (
                f"{card_id} ({chosen_count} chosen, "
                f"{owned_count} owned)"
            )
            for card_id, chosen_count, owned_count in sorted(overspent)
        )
        raise ValueError(f"Deck includes more copies than owned: {details}")

    return normalized_deck


def validate_reward_choice(
    *, reward_choice: str, options: Sequence[str]
) -> str:
    if reward_choice not in CARDS:
        raise ValueError(f"Unknown reward card id: {reward_choice}")
    if reward_choice not in options:
        valid = ", ".join(options)
        raise ValueError(
            f"Reward choice must be one of: {valid}. Got {reward_choice}."
        )
    return reward_choice


def canonicalize_card_ids(card_ids: Sequence[str]) -> tuple[str, ...]:
    counts = Counter(card_ids)
    ordered: list[str] = []
    for card_id in REWARD_CARD_IDS:
        ordered.extend([card_id] * counts.get(card_id, 0))
    return tuple(ordered)


def format_card_counts(card_ids: Sequence[str]) -> str:
    counts = Counter(card_ids)
    parts = [
        f"{CARDS[card_id].name} x{counts[card_id]}"
        for card_id in REWARD_CARD_IDS
        if counts.get(card_id, 0)
    ]
    return ", ".join(parts)


def format_card_list(card_ids: Sequence[str]) -> str:
    return ", ".join(f"{CARDS[card_id].name} [{card_id}]" for card_id in card_ids)


def _choose_enemy(*, battle_type: RunBattleType, rng: random.Random) -> EnemyDefinition:
    if battle_type == "boss":
        return get_enemy_definition("boss")
    enemy_id = rng.choice(NORMAL_ENEMY_IDS)
    return get_enemy_definition(enemy_id)


def _record_line(
    log_lines: list[str],
    log_emitter: LogEmitter | None,
    line: str,
) -> None:
    log_lines.append(line)
    if log_emitter is not None:
        log_emitter(line)
