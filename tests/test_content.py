from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from auto_card.content import (
    CARD_ORDER,
    CARDS,
    DATA_DIR,
    ROLES,
    get_role_reward_card_ids,
    validate_content,
)


def test_default_content_loads_roles_cards_and_reward_pools() -> None:
    registry = validate_content()

    assert set(registry.roles) == {"adventurer", "alchemist"}
    assert CARD_ORDER == tuple(CARDS)
    assert "battle_cry" in get_role_reward_card_ids("adventurer")
    assert "shield_bash" in get_role_reward_card_ids("adventurer")
    assert "venom_cut" not in get_role_reward_card_ids("adventurer")
    assert "venom_cut" in get_role_reward_card_ids("alchemist")
    assert "battle_cry" not in get_role_reward_card_ids("alchemist")
    assert registry.roles["alchemist"].starting_hp == 44


def test_validate_content_rejects_unknown_status_reference(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    shutil.copytree(DATA_DIR, data_dir)

    adventurer_cards = data_dir / "cards" / "adventurer.toml"
    adventurer_cards.write_text(
        adventurer_cards.read_text().replace('status = "strength"', 'status = "rage"', 1)
    )

    with pytest.raises(ValueError, match="unknown status 'rage'"):
        validate_content(data_dir)


def test_each_role_reward_pool_has_enough_cards() -> None:
    for role_id in ROLES:
        assert len(get_role_reward_card_ids(role_id)) >= 3
