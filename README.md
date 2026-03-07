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
- App-level voice volume control (independent in-app TTS level).
- Optional voice input commands (mic control for pause/mute/next-step/quit).
- Pluggable guide retrieval (online fetch + local cache).
- Floating overlay and global hotkeys (mute/pause/force refresh).
- No-task mode scene keyframes (capture visual milestones and infer progress from scene match).
- Multi-frame sampling + temporal stabilizer to reduce hint flicker.
- Optional AI advisor that rewrites one-step hints from current progress context.

## Quick Start

Desktop GUI launcher (recommended on Windows):

```text
start_helper.bat
```

Provider setup helper (interactive, one-click):

```text
configure_ai_provider.bat
```

Default behavior:
- auto-scan and import your Steam library,
- show installed games in a GUI selector,
- start the selected game profile in one click.
- adjust voice volume in GUI (`Voice Volume` slider + `Apply` button).
- toggle AI hint rewriting in GUI (`Enable AI Advisor`).
- choose AI provider in GUI (`AI Provider` dropdown).
- optionally enable mic voice commands (`Enable Voice Input`) and set wake word.

You can also launch GUI directly:

```powershell
gwh gui --config config/default.yaml
```

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

CLI mode from batch (optional):

```text
start_helper.bat cli <game_id> [once|loop]
```

## Hotkeys and Flags

- `Ctrl+Alt+M`: Toggle voice mute.
- `Ctrl+Alt+P`: Pause or resume recognition.
- `Ctrl+Alt+H`: Force an immediate hint refresh.
- `Ctrl+Alt+D`: Cycle hint detail level (L0-L2).
- `Ctrl+Alt+Q`: Stop the loop.
- Optional flags: `--no-overlay`, `--no-hotkeys`.

Voice input (optional):
- GUI toggle: `Enable Voice Input`
- CLI flags: `--voice-input` / `--no-voice-input`
- Supported commands: `静音`, `取消静音`, `暂停`, `继续`, `下一步提示`, `详细`, `退出助手`
- If wake word is configured, command must include it (example: `assistant 暂停`)
- Dependency note: install microphone backend when needed (`pip install SpeechRecognition pyaudio`)

## Steam Integration

- List installed Steam games:

```powershell
gwh steam-list --config config/default.yaml
```

- Interactively select one game and output its `game_id`:

```powershell
gwh steam-select --config config/default.yaml --id-only
```

## Guide Sources

Default preferred guide sources:
- `gamersky.com`
- `3dmgame.com`
- `steamcommunity.com` (Steam Community Guides)

You can change source priority in `config/default.yaml`:

```yaml
guide_source_domains: "gamersky.com,3dmgame.com,steamcommunity.com"
guide_per_source_limit: 2
guide_max_candidates: 8
```

## No-Task Scene Mode

When in-game mission text is missing, you can use scene keyframes:

- GUI: set `Label` + optional `Action Hint`, then click `Capture Current Screen`.
- CLI capture current screen:

```powershell
gwh scene-add-keyframe --config config/default.yaml --game-id steam_214490 --label "castle_gate" --action-text "Talk to the gate guard"
```

- CLI import from an existing screenshot:

```powershell
gwh scene-add-keyframe --config config/default.yaml --game-id steam_214490 --label "boss_room" --image-path "D:\shots\boss.png" --action-text "Defeat the boss"
```

- List keyframes:

```powershell
gwh scene-list-keyframes --config config/default.yaml --game-id steam_214490
```

## AI Advisor (Optional)

The app samples multiple frames each tick, stabilizes state votes over time, and can rewrite the final hint with multiple API providers.

Supported providers (preset config):
- `openai`
- `kimi` (Moonshot)
- `deepseek`
- `qwen` (DashScope compatible endpoint)
- `zhipu` (GLM)
- `anthropic` (Claude Messages API)
- `gemini` (Google Generative Language API)
- `openrouter`
- `xai`
- `ollama` (local, no API key required)

Core config keys (`config/default.yaml`):

```yaml
capture_batch_size: 3
capture_batch_interval_seconds: 0.25
stabilizer_enabled: true
ai_advisor_enabled: true
ai_advisor_provider: openai
ai_advisor_protocol:
ai_advisor_api_key_env:
ai_advisor_model:
ai_advisor_base_url:
ai_advisor_request_path:
ai_advisor_temperature: 0.2
```

Provider quick switch via env vars (no key in code):

```powershell
# Kimi
setx KIMI_API_KEY "your_kimi_key"
setx GWH_AI_ADVISOR_PROVIDER "kimi"
setx GWH_AI_ADVISOR_API_KEY_ENV "KIMI_API_KEY"

# DeepSeek
setx DEEPSEEK_API_KEY "your_deepseek_key"
setx GWH_AI_ADVISOR_PROVIDER "deepseek"
setx GWH_AI_ADVISOR_API_KEY_ENV "DEEPSEEK_API_KEY"

# Anthropic
setx ANTHROPIC_API_KEY "your_anthropic_key"
setx GWH_AI_ADVISOR_PROVIDER "anthropic"
setx GWH_AI_ADVISOR_API_KEY_ENV "ANTHROPIC_API_KEY"

# Gemini
setx GOOGLE_API_KEY "your_google_key"
setx GWH_AI_ADVISOR_PROVIDER "gemini"
setx GWH_AI_ADVISOR_API_KEY_ENV "GOOGLE_API_KEY"
```

One-click interactive setup:

```text
configure_ai_provider.bat
```

Or from launcher:

```text
start_helper.bat provider
```

Scripted setup examples:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/set-ai-provider.ps1 -Provider kimi -ApiKey "sk-..."
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/set-ai-provider.ps1 -Provider deepseek -ApiKey "sk-..."
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/set-ai-provider.ps1 -Provider ollama
```

For custom OpenAI-compatible gateways, set:
- `GWH_AI_ADVISOR_PROVIDER=openai`
- `GWH_AI_ADVISOR_BASE_URL=<your_base_url>`
- `GWH_AI_ADVISOR_MODEL=<your_model>`
- `GWH_AI_ADVISOR_API_KEY_ENV=<your_key_env_name>`

## Database & Cache

The app uses SQLite as the single local state store (default: `data/gamewalk.db`, configurable via `db_path`).

Core tables:
- `games`, `sessions`, `observations`, `progress_states`
- `guide_docs`, `guide_steps`, `retrieval_cache`
- `voice_history`, `steam_apps`, `scene_keyframes`

Useful commands:

```powershell
gwh init-db --config config/default.yaml
python -c "import sqlite3; c=sqlite3.connect('data/gamewalk.db'); print([r[0] for r in c.execute(\"select name from sqlite_master where type='table' order by name\")]); c.close()"
```

Recommendation: back up `data/gamewalk.db` periodically if you want to preserve game profiles, cached guide candidates, and scene keyframes.

## Project Layout

- `src/gamewalk_helper/`: Core application modules.
- `config/default.yaml`: Runtime configuration.
- `tests/`: Unit tests for decision and voice logic.
- `docs/`: Design and architecture notes.
- `scripts/`: Helper scripts for local development.
