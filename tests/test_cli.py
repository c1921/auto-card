from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]

BASE_DECK = [
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
]
BOSS_RUN_REWARDS = [
    "fortify",
    "defend",
    "drain_slash",
    "heavy_strike",
    "fortify",
]


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "main.py", *args],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def write_script(
    path: Path,
    *,
    deck_choices: list[list[str]],
    reward_choices: list[str],
) -> Path:
    path.write_text(
        json.dumps(
            {
                "deck_choices": deck_choices,
                "reward_choices": reward_choices,
            }
        )
    )
    return path


def test_cli_runs_default_session_with_script(tmp_path: Path) -> None:
    script_path = write_script(
        tmp_path / "boss_run.json",
        deck_choices=[BASE_DECK] * 6,
        reward_choices=BOSS_RUN_REWARDS,
    )

    result = run_cli("--seed", "19", "--script", str(script_path))

    assert result.returncode == 0
    assert "Run start: Player 50/50 HP." in result.stdout
    assert "Battle 6/6: Boss [boss] (boss)." in result.stdout
    assert "Run result: Defeat on battle 6." in result.stdout


@pytest.mark.parametrize(
    ("enemy", "seed", "expected_name"),
    [
        ("guard", "104", "Guard"),
        ("priest", "2", "Priest"),
    ],
)
def test_cli_accepts_battle_subcommand(
    enemy: str, seed: str, expected_name: str
) -> None:
    result = run_cli("battle", "--enemy", enemy, "--seed", seed)

    assert result.returncode == 0
    assert f"Seed: {seed}" in result.stdout
    assert expected_name in result.stdout
    assert "Result: Player" in result.stdout


def test_cli_returns_error_for_invalid_script(tmp_path: Path) -> None:
    script_path = write_script(
        tmp_path / "invalid.json",
        deck_choices=[],
        reward_choices=[],
    )

    result = run_cli("--seed", "19", "--script", str(script_path))

    assert result.returncode == 1
    assert "missing a deck choice for battle 1" in result.stderr
