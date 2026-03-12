from __future__ import annotations

from auto_card.models import CardDefinition, EffectDefinition, StatusSnapshot

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


def get_card_type(card: CardDefinition) -> str:
    categories: set[str] = set()
    for effect in card.effects:
        if effect.kind == "damage":
            categories.add("Attack")
            continue
        if effect.kind == "armor":
            categories.add("Defense")
            continue
        if effect.kind == "heal":
            categories.add("Heal")
            continue
        categories.add("Utility")

    if len(categories) > 1:
        return "Hybrid"
    if categories:
        return next(iter(categories))
    return "Skill"


def format_card_effect(card: CardDefinition) -> str:
    return format_effects(card.effects)


def format_effects(effects: tuple[EffectDefinition, ...]) -> str:
    parts = [format_effect(effect) for effect in effects]
    return ", ".join(parts) if parts else "No effect"


def format_effect(effect: EffectDefinition) -> str:
    if effect.kind == "damage":
        return f"Deal {effect.value}"
    if effect.kind == "armor":
        return f"Gain {effect.value} armor"
    if effect.kind == "heal":
        return f"Heal {effect.value}"
    if effect.status == "strength":
        return f"Gain Strength {effect.value}"
    if effect.status == "poison":
        return f"Apply Poison {effect.value}"
    if effect.status == "stun":
        return "Apply Stun"
    return "Unknown effect"


def format_statuses(statuses: tuple[StatusSnapshot, ...]) -> str:
    if not statuses:
        return "None"
    return ", ".join(format_status(snapshot) for snapshot in statuses)


def format_status(snapshot: StatusSnapshot) -> str:
    label = STATUS_LABELS.get(snapshot.kind, snapshot.kind.title())
    if snapshot.kind == "stun":
        return label if snapshot.value == 1 else f"{label} {snapshot.value}"
    return f"{label} {snapshot.value}"


def status_sort_key(snapshot: StatusSnapshot) -> tuple[int, str]:
    return (STATUS_ORDER.get(snapshot.kind, 99), snapshot.kind)
