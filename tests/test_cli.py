from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from auto_card import ui as ui_module
from auto_card.cli import main
from auto_card.content import get_role_definition
from auto_card.run import RunSession

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ADVENTURER = get_role_definition("adventurer")
ALCHEMIST = get_role_definition("alchemist")


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return run_cli_raw("--lang", "en", *args)


def run_cli_raw(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "main.py", *args],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


def build_script_for_first_option_strategy(
    path: Path,
    *,
    role_id: str,
    seed: int,
) -> Path:
    role = get_role_definition(role_id)
    session = RunSession(seed=seed, role_id=role_id)
    deck_choices: list[list[str]] = []
    reward_choices: list[str] = []

    while session.phase != "finished":
        deck_choices.append(list(role.starting_deck))
        session.submit_deck_choice(role.starting_deck)
        session.complete_battle_replay()
        if session.phase == "reward_choice":
            reward_choice = session.get_reward_choice_request().options[0]
            reward_choices.append(reward_choice)
            session.submit_reward_choice(reward_choice)

    path.write_text(
        json.dumps(
            {
                "role": role_id,
                "deck_choices": deck_choices,
                "reward_choices": reward_choices,
            }
        )
    )
    return path


def test_cli_validates_content() -> None:
    result = run_cli("validate-content")

    assert result.returncode == 0
    assert "Content validation passed." in result.stdout


def test_cli_runs_default_session_with_script_role(tmp_path: Path) -> None:
    script_path = build_script_for_first_option_strategy(
        tmp_path / "alchemist_run.json",
        role_id="alchemist",
        seed=0,
    )

    result = run_cli("--seed", "0", "--script", str(script_path))

    assert result.returncode == 0
    assert "Run start: Alchemist [alchemist] 44/44 HP." in result.stdout
    assert "Battle 1/6:" in result.stdout


def test_cli_role_flag_overrides_script_role(tmp_path: Path) -> None:
    script_path = build_script_for_first_option_strategy(
        tmp_path / "script.json",
        role_id="adventurer",
        seed=0,
    )
    payload = json.loads(script_path.read_text())
    payload["role"] = "alchemist"
    script_path.write_text(json.dumps(payload))

    result = run_cli(
        "--seed",
        "0",
        "--role",
        "adventurer",
        "--script",
        str(script_path),
    )

    assert result.returncode == 0
    assert "Run start: Adventurer [adventurer] 50/50 HP." in result.stdout


@pytest.mark.parametrize(
    ("enemy", "seed", "role", "expected_name"),
    [
        ("guard", "104", "adventurer", "Guard"),
        ("priest", "2", "alchemist", "Priest"),
    ],
)
def test_cli_accepts_battle_subcommand(
    enemy: str, seed: str, role: str, expected_name: str
) -> None:
    result = run_cli("battle", "--enemy", enemy, "--role", role, "--seed", seed)

    assert result.returncode == 0
    assert f"Seed: {seed}" in result.stdout
    assert expected_name in result.stdout
    assert "Result: Player" in result.stdout


def test_cli_returns_error_for_invalid_script(tmp_path: Path) -> None:
    script_path = tmp_path / "invalid.json"
    script_path.write_text(
        json.dumps(
            {
                "role": "adventurer",
                "deck_choices": [],
                "reward_choices": [],
            }
        )
    )

    result = run_cli("--seed", "19", "--script", str(script_path))

    assert result.returncode == 1
    assert "missing a deck choice for battle 1" in result.stderr


def test_cli_accepts_ui_subcommand(monkeypatch: pytest.MonkeyPatch) -> None:
    observed: dict[str, int | bool | None] = {}

    class FakeApp:
        def __init__(
            self,
            *,
            seed: int,
            role_id: str | None,
            language: str | None,
        ) -> None:
            observed["seed"] = seed
            observed["role_id"] = role_id
            observed["language"] = language

        def run(self) -> None:
            observed["ran"] = True

    monkeypatch.setattr(ui_module, "TextualCardApp", FakeApp)

    result = main(["ui", "--seed", "7", "--role", "adventurer", "--lang", "en"])

    assert result == 0
    assert observed == {
        "seed": 7,
        "role_id": "adventurer",
        "language": "en",
        "ran": True,
    }


def test_cli_help_translates_to_chinese() -> None:
    env = os.environ | {"LANG": "en_US.UTF-8"}

    result = run_cli_raw("--lang", "zh_CN", "--help", env=env)

    assert result.returncode == 0
    assert "用法：" in result.stdout
    assert "运行一整局 Rogue-like 卡牌游戏。" in result.stdout
    assert "当前运行使用的语言。" in result.stdout
