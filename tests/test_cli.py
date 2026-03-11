from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "main.py", *args],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_cli_runs_default_battle() -> None:
    result = run_cli()

    assert result.returncode == 0
    assert "Battle start:" in result.stdout
    assert "Bruiser" in result.stdout
    assert "Result: Player" in result.stdout


@pytest.mark.parametrize(
    ("enemy", "seed", "expected_name"),
    [
        ("guard", "104", "Guard"),
        ("priest", "2", "Priest"),
    ],
)
def test_cli_accepts_enemy_and_seed_arguments(
    enemy: str, seed: str, expected_name: str
) -> None:
    result = run_cli("--enemy", enemy, "--seed", seed)

    assert result.returncode == 0
    assert f"Seed: {seed}" in result.stdout
    assert expected_name in result.stdout
    assert "Result: Player" in result.stdout
