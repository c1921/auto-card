# Auto Card

Pure command-line prototype for the rogue-like card game MVP.

## Run

```bash
uv run main.py
uv run main.py --seed 19 --script run.json
uv run main.py battle --enemy guard --seed 104
uv run main.py battle --enemy priest --seed 2
```

`main.py` now runs a full 5-fight-plus-boss session by default. Use `battle` to
run the original single-fight simulator.

Scripted runs use a JSON file shaped like this (truncated example):

```json
{
  "deck_choices": [
    ["strike", "strike", "strike", "strike", "defend", "defend", "defend", "heavy_strike", "heavy_strike", "fortify"]
  ],
  "reward_choices": ["fortify"]
}
```

## Test

```bash
uv run pytest
```
