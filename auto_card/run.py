from __future__ import annotations

import random
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from auto_card.battle import run_battle_replay
from auto_card.content import (
    CARDS,
    DEFAULT_ROLE,
    REWARD_OPTION_COUNT,
    RUN_DECK_SIZE,
    TOTAL_BATTLE_COUNT,
    get_role_definition,
    get_role_reward_card_ids,
)
from auto_card.models import (
    BattleReplay,
    EnemyDefinition,
    RoleDefinition,
    RunBattleType,
    RunPhase,
    RunResult,
)
from auto_card.run_support import (
    LogEmitter,
    build_battle_record,
    canonicalize_card_ids as _canonicalize_card_ids,
    choose_enemy as _choose_enemy,
    format_card_counts as _format_card_counts,
    format_card_list as _format_card_list,
    record_line as _record_line,
)

DeckChooser = Callable[["DeckChoiceRequest"], Sequence[str]]
RewardChooser = Callable[["RewardChoiceRequest"], str]


@dataclass(frozen=True)
class DeckChoiceRequest:
    battle_number: int
    total_battles: int
    battle_type: RunBattleType
    enemy: EnemyDefinition
    role: RoleDefinition
    current_hp: int
    max_hp: int
    collection: tuple[str, ...]


@dataclass(frozen=True)
class RewardChoiceRequest:
    battle_number: int
    enemy: EnemyDefinition
    role: RoleDefinition
    current_hp: int
    max_hp: int
    collection: tuple[str, ...]
    options: tuple[str, ...]


class RunSession:
    def __init__(
        self,
        *,
        seed: int = 0,
        role_id: str | None = None,
        log_emitter: LogEmitter | None = None,
    ) -> None:
        self.seed = seed
        self._rng = random.Random(seed)
        self._log_emitter = log_emitter
        self._role = get_role_definition(role_id or DEFAULT_ROLE.id)
        self._current_hp = self._role.starting_hp
        self._collection = list(self._role.starting_collection)
        self._battle_records = []
        self._log_lines: list[str] = []
        self._phase: RunPhase = "deck_choice"
        self._battle_number = 1
        self._current_battle_type: RunBattleType = "normal"
        self._current_enemy: EnemyDefinition | None = None
        self._current_collection_view: tuple[str, ...] = ()
        self._current_battle_replay: BattleReplay | None = None
        self._current_deck_ids: tuple[str, ...] = ()
        self._current_battle_seed = 0
        self._current_reward_options: tuple[str, ...] = ()
        self._reward_collection_view: tuple[str, ...] = ()
        self._outcome: str | None = None
        self._final_battle_number = 0

        self._record_line(
            f"Run start: {self._role.name} [{self._role.id}] {self._current_hp}/{self._role.max_hp} HP."
        )
        self._record_line(f"Seed: {seed}")
        self._record_line(
            f"Starting collection: {format_card_counts(self._collection)}"
        )
        self._prepare_current_battle()

    @property
    def phase(self) -> RunPhase:
        return self._phase

    @property
    def battle_number(self) -> int:
        return self._battle_number

    @property
    def total_battles(self) -> int:
        return TOTAL_BATTLE_COUNT

    @property
    def current_hp(self) -> int:
        return self._current_hp

    @property
    def role(self) -> RoleDefinition:
        return self._role

    @property
    def max_hp(self) -> int:
        return self._role.max_hp

    @property
    def collection(self) -> tuple[str, ...]:
        return canonicalize_card_ids(self._collection)

    @property
    def current_enemy(self) -> EnemyDefinition:
        if self._current_enemy is None:
            raise RuntimeError("Current enemy is not available.")
        return self._current_enemy

    @property
    def current_battle_type(self) -> RunBattleType:
        return self._current_battle_type

    @property
    def current_battle_replay(self) -> BattleReplay:
        if self._current_battle_replay is None:
            raise RuntimeError("Battle replay is not available.")
        return self._current_battle_replay

    @property
    def log_lines(self) -> tuple[str, ...]:
        return tuple(self._log_lines)

    @property
    def final_outcome(self) -> str | None:
        return self._outcome

    @property
    def next_battle_number(self) -> int | None:
        if self._battle_number >= TOTAL_BATTLE_COUNT:
            return None
        return self._battle_number + 1

    @property
    def next_battle_type(self) -> RunBattleType | None:
        next_battle_number = self.next_battle_number
        if next_battle_number is None:
            return None
        return "boss" if next_battle_number == TOTAL_BATTLE_COUNT else "normal"

    def get_deck_choice_request(self) -> DeckChoiceRequest:
        if self._phase != "deck_choice":
            raise RuntimeError(
                f"Deck choice is not available during phase '{self._phase}'."
            )
        return DeckChoiceRequest(
            battle_number=self._battle_number,
            total_battles=TOTAL_BATTLE_COUNT,
            battle_type=self._current_battle_type,
            enemy=self.current_enemy,
            role=self._role,
            current_hp=self._current_hp,
            max_hp=self._role.max_hp,
            collection=self._current_collection_view,
        )

    def submit_deck_choice(self, deck_ids: Sequence[str]) -> BattleReplay:
        if self._phase != "deck_choice":
            raise RuntimeError(
                f"Deck choice cannot be submitted during phase '{self._phase}'."
            )

        normalized_deck = validate_deck_choice(
            deck_ids=deck_ids,
            collection=self._current_collection_view,
        )
        self._current_deck_ids = normalized_deck
        self._record_line(f"Chosen deck: {format_card_counts(normalized_deck)}")

        self._current_battle_seed = self._rng.randint(0, 2**32 - 1)
        self._record_line(f"Battle seed: {self._current_battle_seed}")

        replay = run_battle_replay(
            deck_ids=normalized_deck,
            enemy_definition=self.current_enemy,
            seed=self._current_battle_seed,
            player_start_hp=self._current_hp,
            role_definition=self._role,
        )
        self._current_battle_replay = replay
        for line in replay.result.log_lines:
            self._record_line(line)

        self._phase = "battle_replay"
        return replay

    def complete_battle_replay(self) -> None:
        if self._phase != "battle_replay":
            raise RuntimeError(
                f"Battle replay cannot be completed during phase '{self._phase}'."
            )

        replay = self.current_battle_replay
        self._current_hp = replay.result.player.hp

        if replay.result.outcome == "defeat":
            self._append_current_battle_record()
            self._record_line("")
            self._record_line(
                f"Run result: Defeat on battle {self._battle_number}."
            )
            self._finish_run(outcome="defeat")
            return

        if self._current_battle_type == "boss":
            self._append_current_battle_record()
            self._record_line("")
            self._record_line("Run result: Victory.")
            self._finish_run(outcome="victory")
            return

        self._enter_reward_choice()

    def get_reward_choice_request(self) -> RewardChoiceRequest:
        if self._phase != "reward_choice":
            raise RuntimeError(
                f"Reward choice is not available during phase '{self._phase}'."
            )
        return RewardChoiceRequest(
            battle_number=self._battle_number,
            enemy=self.current_enemy,
            role=self._role,
            current_hp=self._current_hp,
            max_hp=self._role.max_hp,
            collection=self._reward_collection_view,
            options=self._current_reward_options,
        )

    def submit_reward_choice(self, reward_choice: str) -> None:
        if self._phase != "reward_choice":
            raise RuntimeError(
                f"Reward choice cannot be submitted during phase '{self._phase}'."
            )

        validated_reward = validate_reward_choice(
            reward_choice=reward_choice,
            options=self._current_reward_options,
        )
        self._collection.append(validated_reward)
        self._record_line(
            f"Reward chosen: {CARDS[validated_reward].name} [{validated_reward}]"
        )
        self._record_line(
            f"Collection now: {format_card_counts(self._collection)}"
        )

        self._append_current_battle_record(
            reward_options=self._current_reward_options,
            reward_choice=validated_reward,
        )

        self._battle_number += 1
        self._current_battle_replay = None
        self._current_reward_options = ()
        self._reward_collection_view = ()
        self._phase = "deck_choice"
        self._prepare_current_battle()

    def build_result(self) -> RunResult:
        if self._phase != "finished" or self._outcome is None:
            raise RuntimeError("Run result is only available after the session ends.")

        return RunResult(
            outcome=self._outcome,
            final_battle_number=self._final_battle_number,
            final_hp=self._current_hp,
            final_collection=canonicalize_card_ids(self._collection),
            battles=tuple(self._battle_records),
            log_lines=tuple(self._log_lines),
            seed=self.seed,
            role_id=self._role.id,
        )

    def _append_current_battle_record(
        self,
        *,
        reward_options: tuple[str, ...] = (),
        reward_choice: str | None = None,
    ) -> None:
        self._battle_records.append(
            build_battle_record(
                battle_number=self._battle_number,
                battle_type=self._current_battle_type,
                enemy_id=self.current_enemy.id,
                deck_ids=self._current_deck_ids,
                battle_seed=self._current_battle_seed,
                result=self.current_battle_replay.result,
                reward_options=reward_options,
                reward_choice=reward_choice,
            )
        )

    def _enter_reward_choice(self) -> None:
        reward_pool = get_role_reward_card_ids(self._role.id)
        reward_options = tuple(
            self._rng.sample(reward_pool, k=REWARD_OPTION_COUNT)
        )
        self._current_reward_options = reward_options
        self._reward_collection_view = canonicalize_card_ids(self._collection)
        self._record_line(f"Reward options: {format_card_list(reward_options)}")
        self._phase = "reward_choice"

    def _finish_run(self, *, outcome: str) -> None:
        self._phase = "finished"
        self._outcome = outcome
        self._final_battle_number = self._battle_number

    def _prepare_current_battle(self) -> None:
        self._current_battle_type = (
            "boss" if self._battle_number == TOTAL_BATTLE_COUNT else "normal"
        )
        self._current_enemy = _choose_enemy(
            battle_type=self._current_battle_type,
            rng=self._rng,
        )
        self._current_collection_view = canonicalize_card_ids(self._collection)

        self._record_line("")
        self._record_line(
            (
                f"Battle {self._battle_number}/{TOTAL_BATTLE_COUNT}: "
                f"{self.current_enemy.name} [{self.current_enemy.id}] "
                f"({self._current_battle_type})."
            )
        )
        self._record_line(
            f"Current HP: {self._current_hp}/{self._role.max_hp}"
        )
        self._record_line(
            f"Collection: {format_card_counts(self._current_collection_view)}"
        )

    def _record_line(self, line: str) -> None:
        _record_line(self._log_lines, self._log_emitter, line)


def play_run(
    *,
    seed: int = 0,
    role_id: str | None = None,
    deck_chooser: DeckChooser,
    reward_chooser: RewardChooser,
    log_emitter: LogEmitter | None = None,
) -> RunResult:
    session = RunSession(seed=seed, role_id=role_id, log_emitter=log_emitter)

    while session.phase != "finished":
        deck_request = session.get_deck_choice_request()
        deck_ids = tuple(deck_chooser(deck_request))
        session.submit_deck_choice(deck_ids)
        session.complete_battle_replay()
        if session.phase == "reward_choice":
            reward_request = session.get_reward_choice_request()
            reward_choice = reward_chooser(reward_request)
            session.submit_reward_choice(reward_choice)

    return session.build_result()


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
    return _canonicalize_card_ids(card_ids)


def format_card_counts(card_ids: Sequence[str]) -> str:
    return _format_card_counts(card_ids, cards=CARDS)


def format_card_list(card_ids: Sequence[str]) -> str:
    return _format_card_list(card_ids, cards=CARDS)
