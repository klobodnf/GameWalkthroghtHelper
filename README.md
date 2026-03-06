# GameWalkthroghtHelper

A Windows-first, non-invasive walkthrough assistant that observes game progress via OCR/CV and provides real-time voice guidance.

## Languages

- English (default): `README.md`
- 简体中文: [`README.zh-CN.md`](README.zh-CN.md)

## Current Scope (V1 Foundation)

- Screen observation pipeline (capture -> OCR/CV -> progress decision).
- Auto ROI localization for task/mission text (with optional manual ROI override).
- Local cache and session store with SQLite.
- Rule-based progress scoring with confidence and fallback suggestions.
- Voice cooldown/dedup to avoid repetitive prompts.
- Pluggable guide retrieval (online fetch + local cache).
- Floating overlay and global hotkeys (mute/pause/force refresh).

## Quick Start

Double-click launcher (recommended on Windows):

```text
start_helper.bat
```

When no game id is provided, the launcher will:
- scan and import your local Steam library,
- show installed games,
- let you choose one to start with.

CLI setup (manual):

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

## Hotkeys and Flags

- `Ctrl+Alt+M`: Toggle voice mute.
- `Ctrl+Alt+P`: Pause or resume recognition.
- `Ctrl+Alt+H`: Force an immediate hint refresh.
- `Ctrl+Alt+D`: Cycle hint detail level (L0-L2).
- `Ctrl+Alt+Q`: Stop the loop.
- Optional flags: `--no-overlay`, `--no-hotkeys`.

## Steam Integration

- List installed Steam games:

```powershell
gwh steam-list --config config/default.yaml
```

- Interactively select one game and output its `game_id`:

```powershell
gwh steam-select --config config/default.yaml --id-only
```

## Project Layout

- `src/gamewalk_helper/`: Core application modules.
- `config/default.yaml`: Runtime configuration.
- `tests/`: Unit tests for decision and voice logic.
- `docs/`: Design and architecture notes.
- `scripts/`: Helper scripts for local development.
