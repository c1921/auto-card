from __future__ import annotations

from auto_card.models import CardDefinition, EnemyDefinition

PLAYER_NAME = "Player"
PLAYER_MAX_HP = 50
PLAYER_STARTING_HP = 50
PLAYER_STARTING_ARMOR = 0
RUN_DECK_SIZE = 10
NORMAL_BATTLE_COUNT = 5
TOTAL_BATTLE_COUNT = 6

CARDS: dict[str, CardDefinition] = {
    "strike": CardDefinition(
        id="strike",
        name="Strike",
        charge_turns=1,
        damage=7,
    ),
    "heavy_strike": CardDefinition(
        id="heavy_strike",
        name="Heavy Strike",
        charge_turns=3,
        damage=18,
    ),
    "drain_slash": CardDefinition(
        id="drain_slash",
        name="Drain Slash",
        charge_turns=1,
        damage=4,
        heal=2,
    ),
    "defend": CardDefinition(
        id="defend",
        name="Defend",
        charge_turns=1,
        armor_gain=5,
    ),
    "fortify": CardDefinition(
        id="fortify",
        name="Fortify",
        charge_turns=2,
        armor_gain=12,
    ),
    "recover": CardDefinition(
        id="recover",
        name="Recover",
        charge_turns=1,
        heal=3,
    ),
}

STARTING_COLLECTION: list[str] = [
    "strike",
    "strike",
    "strike",
    "strike",
    "defend",
    "defend",
    "defend",
    "heavy_strike",
    "heavy_strike",
    "fortify",
    "recover",
    "drain_slash",
]

TEST_DECK: list[str] = [
    "strike",
    "strike",
    "strike",
    "strike",
    "defend",
    "defend",
    "defend",
    "heavy_strike",
    "fortify",
    "recover",
]

NORMAL_ENEMY_IDS: tuple[str, ...] = ("bruiser", "guard", "priest")
REWARD_CARD_IDS: tuple[str, ...] = tuple(CARDS)

ENEMIES: dict[str, EnemyDefinition] = {
    "bruiser": EnemyDefinition(
        id="bruiser",
        name="Bruiser",
        max_hp=45,
        attack_weight=70,
        defend_weight=20,
        heal_weight=10,
        attack_value=7,
        defend_value=4,
        heal_value=2,
    ),
    "guard": EnemyDefinition(
        id="guard",
        name="Guard",
        max_hp=55,
        attack_weight=35,
        defend_weight=40,
        heal_weight=15,
        attack_value=5,
        defend_value=5,
        heal_value=2,
    ),
    "priest": EnemyDefinition(
        id="priest",
        name="Priest",
        max_hp=42,
        attack_weight=30,
        defend_weight=20,
        heal_weight=40,
        attack_value=4,
        defend_value=4,
        heal_value=3,
    ),
    "boss": EnemyDefinition(
        id="boss",
        name="Boss",
        max_hp=72,
        attack_weight=40,
        defend_weight=30,
        heal_weight=30,
        attack_value=8,
        defend_value=6,
        heal_value=4,
    ),
}


def get_enemy_definition(enemy_id: str) -> EnemyDefinition:
    try:
        return ENEMIES[enemy_id]
    except KeyError as exc:
        valid_ids = ", ".join(sorted(ENEMIES))
        raise ValueError(f"Unknown enemy '{enemy_id}'. Expected one of: {valid_ids}") from exc
