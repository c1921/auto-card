from __future__ import annotations

from auto_card.models import CardDefinition


def get_card_type(card: CardDefinition) -> str:
    categories = [
        bool(card.damage),
        bool(card.armor_gain),
        bool(card.heal),
    ]
    active_category_count = sum(categories)
    if active_category_count > 1:
        return "Hybrid"
    if card.damage:
        return "Attack"
    if card.armor_gain:
        return "Defense"
    if card.heal:
        return "Heal"
    return "Skill"


def format_card_effect(card: CardDefinition) -> str:
    effects: list[str] = []
    if card.damage:
        effects.append(f"Deal {card.damage}")
    if card.armor_gain:
        effects.append(f"Gain {card.armor_gain} armor")
    if card.heal:
        effects.append(f"Heal {card.heal}")
    return ", ".join(effects) if effects else "No effect"
