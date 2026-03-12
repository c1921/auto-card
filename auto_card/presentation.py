from __future__ import annotations

from auto_card.i18n import _
from auto_card.models import (
    BattleOutcome,
    CardDefinition,
    EffectDefinition,
    EnemyActionDefinition,
    EnemyDefinition,
    RoleDefinition,
    RunBattleType,
    StatusSnapshot,
)

STATUS_LABELS = {
    "poison": "Poison",
    "strength": "Strength",
    "stun": "Stun",
}
STATUS_ORDER = {
    "strength": 0,
    "poison": 1,
    "stun": 2,
}
ACTIVE_CARD_STATUS_LABELS = {
    "charging": "Charging",
    "resolved": "Resolved",
    "stunned": "Stunned",
}


def translate_text(text: str) -> str:
    return _(text)


def get_role_name(role: RoleDefinition) -> str:
    return _(role.name)


def get_role_description(role: RoleDefinition) -> str:
    return _(role.description)


def get_enemy_name(enemy: EnemyDefinition) -> str:
    return _(enemy.name)


def get_action_name(action: EnemyActionDefinition) -> str:
    return _(action.name)


def get_card_name(card: CardDefinition) -> str:
    return _(card.name)


def get_card_type(card: CardDefinition) -> str:
    card_type = get_card_type_key(card)
    return _(card_type.title())


def get_card_type_key(card: CardDefinition) -> str:
    categories: set[str] = set()
    for effect in card.effects:
        if effect.kind == "damage":
            categories.add("attack")
            continue
        if effect.kind == "armor":
            categories.add("defense")
            continue
        if effect.kind == "heal":
            categories.add("heal")
            continue
        categories.add("utility")

    if len(categories) > 1:
        return "hybrid"
    if categories:
        return next(iter(categories))
    return "skill"


def format_battle_type(battle_type: RunBattleType) -> str:
    if battle_type == "boss":
        return _("Boss")
    return _("Normal")


def format_outcome(outcome: BattleOutcome) -> str:
    if outcome == "victory":
        return _("Victory")
    return _("Defeat")


def format_bool(value: bool) -> str:
    if value:
        return _("Yes")
    return _("No")


def format_active_card_status(status_key: str) -> str:
    return _(ACTIVE_CARD_STATUS_LABELS.get(status_key, status_key.title()))


def format_card_effect(card: CardDefinition) -> str:
    return format_effects(card.effects)


def format_effects(effects: tuple[EffectDefinition, ...]) -> str:
    parts = [format_effect(effect) for effect in effects]
    return ", ".join(parts) if parts else _("No effect")


def format_effect(effect: EffectDefinition) -> str:
    if effect.kind == "damage":
        return _("Deal {value}").format(value=effect.value)
    if effect.kind == "armor":
        return _("Gain {value} armor").format(value=effect.value)
    if effect.kind == "heal":
        return _("Heal {value}").format(value=effect.value)
    if effect.status == "strength":
        return _("Gain Strength {value}").format(value=effect.value)
    if effect.status == "poison":
        return _("Apply Poison {value}").format(value=effect.value)
    if effect.status == "stun":
        return _("Apply Stun")
    return _("Unknown effect")


def format_statuses(statuses: tuple[StatusSnapshot, ...]) -> str:
    if not statuses:
        return _("None")
    return ", ".join(format_status(snapshot) for snapshot in statuses)


def format_status(snapshot: StatusSnapshot) -> str:
    label = _(STATUS_LABELS.get(snapshot.kind, snapshot.kind.title()))
    if snapshot.kind == "stun":
        return label if snapshot.value == 1 else _("{label} {value}").format(
            label=label,
            value=snapshot.value,
        )
    return _("{label} {value}").format(label=label, value=snapshot.value)


def status_sort_key(snapshot: StatusSnapshot) -> tuple[int, str]:
    return (STATUS_ORDER.get(snapshot.kind, 99), snapshot.kind)
