# Auto Card

Pure command-line prototype for the rogue-like card game MVP.

## Run

```bash
uv run main.py ui
uv run main.py ui --seed 19
uv run main.py
uv run main.py --seed 19 --script run.json
uv run main.py battle --enemy guard --seed 104
uv run main.py battle --enemy priest --seed 2
```

`main.py ui` launches the Textual terminal UI. `main.py` still runs the full
5-fight-plus-boss text session by default, and `battle` runs the original
single-fight simulator.

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
