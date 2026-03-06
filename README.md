# GameWalkthroghtHelper

Windows-first, non-invasive walkthrough helper that observes on-screen game progress with OCR/CV and gives real-time voice hints.

## Current scope (V1 foundation)

- Screen observation pipeline (capture -> OCR/CV -> progress decision).
- Auto ROI localization for task/mission text (with optional manual ROI override).
- Local cache and session store with SQLite.
- Rule-based progress scoring with confidence and fallback suggestions.
- Voice cooldown/dedup to avoid repetitive prompts.
- Pluggable guide retrieval (online fetch + local cache).

## Quick start

```powershell
python -m venv .venv
. .\.venv\Scripts\Activate.ps1
pip install -e .[runtime]
gwh init-db --config config/default.yaml
gwh run-once --config config/default.yaml --game-id "MyGame"
```

For continuous monitoring:

```powershell
gwh run-loop --config config/default.yaml --game-id "MyGame"
```

## Project layout

- `src/gamewalk_helper/`: core app modules.
- `config/default.yaml`: runtime configuration.
- `tests/`: unit tests for decision and voice logic.
- `docs/`: design and architecture notes.
- `scripts/`: helper scripts for local development.

