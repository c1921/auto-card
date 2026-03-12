from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import tomllib
from typing import Any, cast

from auto_card.i18n import _
from auto_card.models import (
    CardDefinition,
    EffectDefinition,
    EnemyActionDefinition,
    EnemyDefinition,
    GameConfig,
    RoleDefinition,
    StatusKind,
)

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
CARD_DIR = DATA_DIR / "cards"
NEUTRAL_POOL_ID = "neutral"
KNOWN_EFFECT_KINDS = {"damage", "armor", "heal", "apply_status"}
KNOWN_EFFECT_TARGETS = {"self", "opponent"}
KNOWN_STATUS_KINDS = {"poison", "strength", "stun"}


@dataclass(frozen=True)
class ContentRegistry:
    game: GameConfig
    cards: dict[str, CardDefinition]
    enemies: dict[str, EnemyDefinition]
    roles: dict[str, RoleDefinition]


def validate_content(data_dir: Path | None = None) -> ContentRegistry:
    root = (data_dir or DATA_DIR).resolve()
    errors: list[str] = []

    game = _parse_game(root / "game.toml", errors)
    cards = _parse_cards(root / "cards", errors)
    roles = _parse_roles(root / "roles.toml", errors)
    enemies = _parse_enemies(root / "enemies.toml", errors)

    if game is not None:
        _validate_game(game, enemies, roles, errors, root / "game.toml")
    if roles:
        _validate_role_pools(cards, roles, errors)
    if game is not None and roles:
        _validate_roles(game, cards, roles, errors, root / "roles.toml")
    if enemies:
        _validate_enemies(enemies, errors, root / "enemies.toml")

    if errors:
        message = "\n".join(f"- {error}" for error in errors)
        raise ValueError(_("Content validation failed:\n{message}").format(message=message))

    if game is None:
        raise ValueError(_("Content validation failed:\n- missing game config."))

    ordered_cards = dict(sorted(cards.items(), key=lambda item: item[1].sort_order))
    return ContentRegistry(
        game=game,
        cards=ordered_cards,
        enemies=enemies,
        roles=roles,
    )


@lru_cache(maxsize=1)
def _load_default_registry() -> ContentRegistry:
    return validate_content()


def load_content() -> ContentRegistry:
    return _load_default_registry()


def _load_toml(path: Path, errors: list[str]) -> dict[str, Any]:
    try:
        with path.open("rb") as handle:
            data = tomllib.load(handle)
    except FileNotFoundError:
        errors.append(_("{path}: file not found.").format(path=path))
        return {}
    except tomllib.TOMLDecodeError as exc:
        errors.append(_("{path}: invalid TOML ({error}).").format(path=path, error=exc))
        return {}

    if not isinstance(data, dict):
        errors.append(_("{path}: root must be a TOML table.").format(path=path))
        return {}
    return data


def _parse_game(path: Path, errors: list[str]) -> GameConfig | None:
    raw = _load_toml(path, errors)
    if not raw:
        return None

    normal_enemy_ids = _string_list(raw.get("normal_enemy_ids"), f"{path}: normal_enemy_ids", errors)
    return GameConfig(
        player_name=_string_value(raw.get("player_name"), f"{path}: player_name", errors),
        starting_armor=_positive_int_value(raw.get("starting_armor"), f"{path}: starting_armor", errors, allow_zero=True),
        run_deck_size=_positive_int_value(raw.get("run_deck_size"), f"{path}: run_deck_size", errors),
        normal_battle_count=_positive_int_value(raw.get("normal_battle_count"), f"{path}: normal_battle_count", errors),
        total_battle_count=_positive_int_value(raw.get("total_battle_count"), f"{path}: total_battle_count", errors),
        reward_option_count=_positive_int_value(raw.get("reward_option_count"), f"{path}: reward_option_count", errors),
        default_role_id=_string_value(raw.get("default_role_id"), f"{path}: default_role_id", errors),
        normal_enemy_ids=tuple(normal_enemy_ids),
        boss_enemy_id=_string_value(raw.get("boss_enemy_id"), f"{path}: boss_enemy_id", errors),
    )


def _parse_cards(card_dir: Path, errors: list[str]) -> dict[str, CardDefinition]:
    cards: dict[str, CardDefinition] = {}
    if not card_dir.exists():
        errors.append(_("{path}: directory not found.").format(path=card_dir))
        return cards

    for path in sorted(card_dir.glob("*.toml")):
        raw = _load_toml(path, errors)
        entries = raw.get("cards", [])
        if not isinstance(entries, list):
            errors.append(_("{path}: cards must be an array of tables.").format(path=path))
            continue
        for index, entry in enumerate(entries, start=1):
            if not isinstance(entry, dict):
                errors.append(
                    _("{path}: cards[{index}] must be a table.").format(
                        path=path,
                        index=index - 1,
                    )
                )
                continue
            card = _build_card(entry, path, index, errors)
            if card is None:
                continue
            if card.id in cards:
                errors.append(
                    _("{path}: duplicate card id '{card_id}'.").format(
                        path=path,
                        card_id=card.id,
                    )
                )
                continue
            cards[card.id] = card
    return cards


def _build_card(
    raw: dict[str, Any],
    path: Path,
    index: int,
    errors: list[str],
) -> CardDefinition | None:
    context = f"{path}: cards[{index - 1}]"
    effects_raw = raw.get("effects", [])
    if not isinstance(effects_raw, list):
        errors.append(
            _("{context}: effects must be an array of tables.").format(context=context)
        )
        effects_raw = []
    effects = [
        effect
        for effect in (
            _build_effect(cast(dict[str, Any], effect_raw), f"{context}.effects[{effect_index}]", errors)
            if isinstance(effect_raw, dict)
            else None
            for effect_index, effect_raw in enumerate(effects_raw)
        )
        if effect is not None
    ]
    if not effects:
        errors.append(
            _("{context}: cards must define at least one effect.").format(
                context=context
            )
        )

    pools = _string_list(raw.get("pools"), f"{context}: pools", errors)
    return CardDefinition(
        id=_string_value(raw.get("id"), f"{context}: id", errors),
        name=_string_value(raw.get("name"), f"{context}: name", errors),
        sort_order=_positive_int_value(raw.get("sort_order"), f"{context}: sort_order", errors, allow_zero=True),
        charge_turns=_positive_int_value(raw.get("charge_turns"), f"{context}: charge_turns", errors),
        effects=tuple(effects),
        pools=tuple(pools),
    )


def _build_effect(
    raw: dict[str, Any],
    context: str,
    errors: list[str],
) -> EffectDefinition | None:
    kind = _string_value(raw.get("kind"), f"{context}: kind", errors)
    target = _string_value(raw.get("target"), f"{context}: target", errors)
    value = _positive_int_value(raw.get("value"), f"{context}: value", errors)
    status = raw.get("status")

    if kind not in KNOWN_EFFECT_KINDS:
        errors.append(
            _("{context}: unknown effect kind '{kind}'.").format(
                context=context,
                kind=kind,
            )
        )
    if target not in KNOWN_EFFECT_TARGETS:
        errors.append(
            _("{context}: unknown effect target '{target}'.").format(
                context=context,
                target=target,
            )
        )

    status_value: StatusKind | None = None
    if kind == "apply_status":
        if not isinstance(status, str):
            errors.append(
                _("{context}: apply_status requires a string status.").format(
                    context=context
                )
            )
        elif status not in KNOWN_STATUS_KINDS:
            errors.append(
                _("{context}: unknown status '{status}'.").format(
                    context=context,
                    status=status,
                )
            )
        else:
            status_value = cast(StatusKind, status)
    elif status is not None:
        errors.append(
            _("{context}: only apply_status effects may define status.").format(
                context=context
            )
        )

    return EffectDefinition(
        kind=cast(Any, kind),
        target=cast(Any, target),
        value=value,
        status=status_value,
    )


def _parse_roles(path: Path, errors: list[str]) -> dict[str, RoleDefinition]:
    raw = _load_toml(path, errors)
    roles: dict[str, RoleDefinition] = {}
    entries = raw.get("roles", [])
    if not isinstance(entries, list):
        errors.append(_("{path}: roles must be an array of tables.").format(path=path))
        return roles

    for index, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict):
            errors.append(
                _("{path}: roles[{index}] must be a table.").format(
                    path=path,
                    index=index - 1,
                )
            )
            continue
        role = _build_role(entry, path, index, errors)
        if role is None:
            continue
        if role.id in roles:
            errors.append(
                _("{path}: duplicate role id '{role_id}'.").format(
                    path=path,
                    role_id=role.id,
                )
            )
            continue
        roles[role.id] = role
    return roles


def _build_role(
    raw: dict[str, Any],
    path: Path,
    index: int,
    errors: list[str],
) -> RoleDefinition | None:
    context = f"{path}: roles[{index - 1}]"
    return RoleDefinition(
        id=_string_value(raw.get("id"), f"{context}: id", errors),
        name=_string_value(raw.get("name"), f"{context}: name", errors),
        description=_string_value(raw.get("description"), f"{context}: description", errors),
        max_hp=_positive_int_value(raw.get("max_hp"), f"{context}: max_hp", errors),
        starting_hp=_positive_int_value(raw.get("starting_hp"), f"{context}: starting_hp", errors),
        starting_collection=tuple(
            _string_list(raw.get("starting_collection"), f"{context}: starting_collection", errors)
        ),
        starting_deck=tuple(
            _string_list(raw.get("starting_deck"), f"{context}: starting_deck", errors)
        ),
        card_pools=tuple(
            _string_list(raw.get("card_pools"), f"{context}: card_pools", errors)
        ),
    )


def _parse_enemies(path: Path, errors: list[str]) -> dict[str, EnemyDefinition]:
    raw = _load_toml(path, errors)
    enemies: dict[str, EnemyDefinition] = {}
    entries = raw.get("enemies", [])
    if not isinstance(entries, list):
        errors.append(
            _("{path}: enemies must be an array of tables.").format(path=path)
        )
        return enemies

    for index, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict):
            errors.append(
                _("{path}: enemies[{index}] must be a table.").format(
                    path=path,
                    index=index - 1,
                )
            )
            continue
        enemy = _build_enemy(entry, path, index, errors)
        if enemy is None:
            continue
        if enemy.id in enemies:
            errors.append(
                _("{path}: duplicate enemy id '{enemy_id}'.").format(
                    path=path,
                    enemy_id=enemy.id,
                )
            )
            continue
        enemies[enemy.id] = enemy
    return enemies


def _build_enemy(
    raw: dict[str, Any],
    path: Path,
    index: int,
    errors: list[str],
) -> EnemyDefinition | None:
    context = f"{path}: enemies[{index - 1}]"
    actions_raw = raw.get("actions", [])
    if not isinstance(actions_raw, list):
        errors.append(
            _("{context}: actions must be an array of tables.").format(context=context)
        )
        actions_raw = []

    actions = [
        action
        for action in (
            _build_enemy_action(cast(dict[str, Any], action_raw), f"{context}.actions[{action_index}]", errors)
            if isinstance(action_raw, dict)
            else None
            for action_index, action_raw in enumerate(actions_raw)
        )
        if action is not None
    ]
    if not actions:
        errors.append(
            _("{context}: enemies must define at least one action.").format(
                context=context
            )
        )

    return EnemyDefinition(
        id=_string_value(raw.get("id"), f"{context}: id", errors),
        name=_string_value(raw.get("name"), f"{context}: name", errors),
        max_hp=_positive_int_value(raw.get("max_hp"), f"{context}: max_hp", errors),
        actions=tuple(actions),
    )


def _build_enemy_action(
    raw: dict[str, Any],
    context: str,
    errors: list[str],
) -> EnemyActionDefinition | None:
    effects_raw = raw.get("effects", [])
    if not isinstance(effects_raw, list):
        errors.append(
            _("{context}: effects must be an array of tables.").format(context=context)
        )
        effects_raw = []
    effects = [
        effect
        for effect in (
            _build_effect(cast(dict[str, Any], effect_raw), f"{context}.effects[{effect_index}]", errors)
            if isinstance(effect_raw, dict)
            else None
            for effect_index, effect_raw in enumerate(effects_raw)
        )
        if effect is not None
    ]
    if not effects:
        errors.append(
            _("{context}: enemy actions must define at least one effect.").format(
                context=context
            )
        )

    return EnemyActionDefinition(
        id=_string_value(raw.get("id"), f"{context}: id", errors),
        name=_string_value(raw.get("name"), f"{context}: name", errors),
        weight=_positive_int_value(raw.get("weight"), f"{context}: weight", errors),
        effects=tuple(effects),
    )


def _validate_game(
    game: GameConfig,
    enemies: dict[str, EnemyDefinition],
    roles: dict[str, RoleDefinition],
    errors: list[str],
    path: Path,
) -> None:
    if game.total_battle_count != game.normal_battle_count + 1:
        errors.append(
            _(
                "{path}: total_battle_count must equal normal_battle_count + 1."
            ).format(path=path)
        )
    if game.default_role_id not in roles:
        errors.append(
            _("{path}: unknown default_role_id '{role_id}'.").format(
                path=path,
                role_id=game.default_role_id,
            )
        )
    missing_normal_enemies = [enemy_id for enemy_id in game.normal_enemy_ids if enemy_id not in enemies]
    if missing_normal_enemies:
        errors.append(
            _("{path}: unknown normal_enemy_ids {enemy_ids}.").format(
                path=path,
                enemy_ids=", ".join(sorted(missing_normal_enemies)),
            )
        )
    if game.boss_enemy_id not in enemies:
        errors.append(
            _("{path}: unknown boss_enemy_id '{enemy_id}'.").format(
                path=path,
                enemy_id=game.boss_enemy_id,
            )
        )


def _validate_role_pools(
    cards: dict[str, CardDefinition],
    roles: dict[str, RoleDefinition],
    errors: list[str],
) -> None:
    known_pools = {NEUTRAL_POOL_ID, *roles}
    for card in cards.values():
        if not card.pools:
            errors.append(
                _("card '{card_id}' must belong to at least one pool.").format(
                    card_id=card.id
                )
            )
            continue
        unknown_pools = [pool for pool in card.pools if pool not in known_pools]
        if unknown_pools:
            errors.append(
                _("card '{card_id}' references unknown pools {pool_ids}.").format(
                    card_id=card.id,
                    pool_ids=", ".join(sorted(unknown_pools)),
                )
            )

    for role in roles.values():
        if not role.card_pools:
            errors.append(
                _("role '{role_id}' must expose at least one pool.").format(
                    role_id=role.id
                )
            )
            continue
        unknown_pools = [
            pool
            for pool in role.card_pools
            if pool != NEUTRAL_POOL_ID and pool not in roles
        ]
        if unknown_pools:
            errors.append(
                _("role '{role_id}' references unknown card pools {pool_ids}.").format(
                    role_id=role.id,
                    pool_ids=", ".join(sorted(unknown_pools)),
                )
            )


def _validate_roles(
    game: GameConfig,
    cards: dict[str, CardDefinition],
    roles: dict[str, RoleDefinition],
    errors: list[str],
    path: Path,
) -> None:
    for role in roles.values():
        if role.starting_hp > role.max_hp:
            errors.append(
                _("{path}: role '{role_id}' has starting_hp above max_hp.").format(
                    path=path,
                    role_id=role.id,
                )
            )
        if len(role.starting_deck) != game.run_deck_size:
            errors.append(
                _(
                    "{path}: role '{role_id}' starting_deck must contain exactly {deck_size} cards."
                ).format(
                    path=path,
                    role_id=role.id,
                    deck_size=game.run_deck_size,
                )
            )

        accessible_cards = set(get_role_reward_card_ids(role.id, cards=cards, roles=roles))
        missing_collection = sorted(
            {card_id for card_id in role.starting_collection if card_id not in cards}
        )
        if missing_collection:
            errors.append(
                _(
                    "{path}: role '{role_id}' starting_collection references unknown cards {card_ids}."
                ).format(
                    path=path,
                    role_id=role.id,
                    card_ids=", ".join(missing_collection),
                )
            )
        missing_deck = sorted(
            {card_id for card_id in role.starting_deck if card_id not in cards}
        )
        if missing_deck:
            errors.append(
                _(
                    "{path}: role '{role_id}' starting_deck references unknown cards {card_ids}."
                ).format(
                    path=path,
                    role_id=role.id,
                    card_ids=", ".join(missing_deck),
                )
            )

        inaccessible_cards = sorted(
            {
                card_id
                for card_id in role.starting_collection + role.starting_deck
                if card_id in cards and card_id not in accessible_cards
            }
        )
        if inaccessible_cards:
            errors.append(
                _("{path}: role '{role_id}' cannot access cards {card_ids}.").format(
                    path=path,
                    role_id=role.id,
                    card_ids=", ".join(inaccessible_cards),
                )
            )

        collection_counts = Counter(role.starting_collection)
        deck_counts = Counter(role.starting_deck)
        overspent = sorted(
            card_id
            for card_id, count in deck_counts.items()
            if count > collection_counts.get(card_id, 0)
        )
        if overspent:
            errors.append(
                _(
                    "{path}: role '{role_id}' starting_deck uses more copies than owned for {card_ids}."
                ).format(
                    path=path,
                    role_id=role.id,
                    card_ids=", ".join(overspent),
                )
            )

        reward_pool = get_role_reward_card_ids(role.id, cards=cards, roles=roles)
        if len(reward_pool) < game.reward_option_count:
            errors.append(
                _(
                    "{path}: role '{role_id}' reward pool must contain at least {card_count} cards."
                ).format(
                    path=path,
                    role_id=role.id,
                    card_count=game.reward_option_count,
                )
            )


def _validate_enemies(
    enemies: dict[str, EnemyDefinition],
    errors: list[str],
    path: Path,
) -> None:
    for enemy in enemies.values():
        action_ids = [action.id for action in enemy.actions]
        duplicate_ids = sorted(
            action_id
            for action_id, count in Counter(action_ids).items()
            if count > 1
        )
        if duplicate_ids:
            errors.append(
                _("{path}: enemy '{enemy_id}' has duplicate action ids {action_ids}.").format(
                    path=path,
                    enemy_id=enemy.id,
                    action_ids=", ".join(duplicate_ids),
                )
            )
        total_weight = sum(action.weight for action in enemy.actions)
        if total_weight <= 0:
            errors.append(
                _("{path}: enemy '{enemy_id}' must have positive total action weight.").format(
                    path=path,
                    enemy_id=enemy.id,
                )
            )


def _string_value(value: Any, context: str, errors: list[str]) -> str:
    if not isinstance(value, str) or not value:
        errors.append(
            _("{context} must be a non-empty string.").format(context=context)
        )
        return ""
    return value


def _positive_int_value(
    value: Any,
    context: str,
    errors: list[str],
    *,
    allow_zero: bool = False,
) -> int:
    if not isinstance(value, int):
        errors.append(_("{context} must be an integer.").format(context=context))
        return 0
    if allow_zero and value < 0:
        errors.append(_("{context} must be at least 0.").format(context=context))
        return 0
    if not allow_zero and value <= 0:
        errors.append(_("{context} must be greater than 0.").format(context=context))
        return 0
    return value


def _string_list(value: Any, context: str, errors: list[str]) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(entry, str) and entry for entry in value):
        errors.append(
            _("{context} must be an array of non-empty strings.").format(
                context=context
            )
        )
        return []
    return list(value)


def get_role_reward_card_ids(
    role_id: str,
    *,
    cards: dict[str, CardDefinition] | None = None,
    roles: dict[str, RoleDefinition] | None = None,
) -> tuple[str, ...]:
    card_registry = cards or CARDS
    role_registry = roles or ROLES
    role = role_registry[role_id]
    return tuple(
        card.id
        for card in card_registry.values()
        if any(pool in role.card_pools for pool in card.pools)
    )


def get_card_definition(card_id: str) -> CardDefinition:
    try:
        return CARDS[card_id]
    except KeyError as exc:
        valid_ids = ", ".join(sorted(CARDS))
        raise ValueError(
            _("Unknown card '{card_id}'. Expected one of: {valid_ids}").format(
                card_id=card_id,
                valid_ids=valid_ids,
            )
        ) from exc


def get_enemy_definition(enemy_id: str) -> EnemyDefinition:
    try:
        return ENEMIES[enemy_id]
    except KeyError as exc:
        valid_ids = ", ".join(sorted(ENEMIES))
        raise ValueError(
            _("Unknown enemy '{enemy_id}'. Expected one of: {valid_ids}").format(
                enemy_id=enemy_id,
                valid_ids=valid_ids,
            )
        ) from exc


def get_role_definition(role_id: str) -> RoleDefinition:
    try:
        return ROLES[role_id]
    except KeyError as exc:
        valid_ids = ", ".join(sorted(ROLES))
        raise ValueError(
            _("Unknown role '{role_id}'. Expected one of: {valid_ids}").format(
                role_id=role_id,
                valid_ids=valid_ids,
            )
        ) from exc


REGISTRY = load_content()
GAME_CONFIG = REGISTRY.game
CARDS = REGISTRY.cards
ENEMIES = REGISTRY.enemies
ROLES = REGISTRY.roles
DEFAULT_ROLE = ROLES[GAME_CONFIG.default_role_id]

PLAYER_NAME = GAME_CONFIG.player_name
PLAYER_STARTING_ARMOR = GAME_CONFIG.starting_armor
RUN_DECK_SIZE = GAME_CONFIG.run_deck_size
NORMAL_BATTLE_COUNT = GAME_CONFIG.normal_battle_count
TOTAL_BATTLE_COUNT = GAME_CONFIG.total_battle_count
REWARD_OPTION_COUNT = GAME_CONFIG.reward_option_count
NORMAL_ENEMY_IDS = GAME_CONFIG.normal_enemy_ids
BOSS_ENEMY_ID = GAME_CONFIG.boss_enemy_id

CARD_ORDER = tuple(CARDS)
CARD_ORDER_INDEX = {card_id: index for index, card_id in enumerate(CARD_ORDER)}
PLAYER_MAX_HP = DEFAULT_ROLE.max_hp
PLAYER_STARTING_HP = DEFAULT_ROLE.starting_hp
STARTING_COLLECTION = list(DEFAULT_ROLE.starting_collection)
TEST_DECK = list(DEFAULT_ROLE.starting_deck)
REWARD_CARD_IDS = get_role_reward_card_ids(DEFAULT_ROLE.id)
