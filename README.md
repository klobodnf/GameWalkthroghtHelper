# GameWalkthroghtHelper

中文：一个以 Windows 为优先、非侵入式的游戏攻略辅助工具，通过 OCR/CV 观察游戏进度并提供实时语音提示。  
English: A Windows-first, non-invasive walkthrough assistant that observes game progress via OCR/CV and provides real-time voice guidance.

## 当前范围（V1 基础） / Current Scope (V1 Foundation)

- 屏幕观察流水线（抓帧 -> OCR/CV -> 进度决策）  
  Screen observation pipeline (capture -> OCR/CV -> progress decision).
- 任务/目标文本自动 ROI 定位（可手动覆盖）  
  Auto ROI localization for task/mission text (with optional manual ROI override).
- 基于 SQLite 的本地缓存与会话存储  
  Local cache and session store with SQLite.
- 基于规则与置信度的进度评分与候选回退  
  Rule-based progress scoring with confidence and fallback suggestions.
- 语音播报冷却与去重，避免重复打扰  
  Voice cooldown/dedup to avoid repetitive prompts.
- 可插拔攻略检索（在线获取 + 本地缓存）  
  Pluggable guide retrieval (online fetch + local cache).
- 悬浮提示窗与全局热键控制（静音/暂停/强制刷新）  
  Floating overlay and global hotkeys (mute/pause/force refresh).

## 快速开始 / Quick Start

```powershell
python -m venv .venv
. .\.venv\Scripts\Activate.ps1
pip install -e .[runtime]
gwh init-db --config config/default.yaml
gwh run-once --config config/default.yaml --game-id "MyGame"
```

中文：持续监控运行命令  
English: Command for continuous monitoring

```powershell
gwh run-loop --config config/default.yaml --game-id "MyGame"
```

## 热键与参数 / Hotkeys and Flags

- `Ctrl+Alt+M`：切换语音静音 / Toggle voice mute.
- `Ctrl+Alt+P`：暂停或恢复识别 / Pause or resume recognition.
- `Ctrl+Alt+H`：立即刷新并播报一次提示 / Force an immediate hint refresh.
- `Ctrl+Alt+D`：切换提示详细级别（L0-L2） / Cycle hint detail level (L0-L2).
- `Ctrl+Alt+Q`：停止运行 / Stop the loop.
- 关闭组件可用：`--no-overlay`、`--no-hotkeys` / Optional flags: `--no-overlay`, `--no-hotkeys`.

## 项目结构 / Project Layout

- `src/gamewalk_helper/`：核心应用模块 / Core application modules.
- `config/default.yaml`：运行配置 / Runtime configuration.
- `tests/`：进度与语音逻辑单元测试 / Unit tests for decision and voice logic.
- `docs/`：设计与架构文档 / Design and architecture notes.
- `scripts/`：本地开发脚本 / Helper scripts for local development.
