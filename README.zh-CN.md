# GameWalkthroghtHelper

一个以 Windows 为优先、非侵入式的游戏攻略辅助工具，通过 OCR/CV 观察游戏进度并提供实时语音提示。

## 语言版本

- English (默认): [`README.md`](README.md)
- 简体中文: `README.zh-CN.md`

## 当前范围（V1 基础）

- 屏幕观察流水线（抓帧 -> OCR/CV -> 进度决策）。
- 任务/目标文本自动 ROI 定位（可手动覆盖）。
- 基于 SQLite 的本地缓存与会话存储。
- 基于规则与置信度的进度评分与候选回退。
- 语音播报冷却与去重，避免重复打扰。
- 应用内语音音量调节（独立 TTS 音量控制）。
- 可插拔攻略检索（在线获取 + 本地缓存）。
- 悬浮提示窗与全局热键控制（静音/暂停/强制刷新）。
- 无任务文本场景关键帧模式（通过画面里程碑匹配推断进度）。
- 多帧采样 + 时序稳定器，降低提示抖动。
- 可选 AI 提示改写（基于当前进度上下文输出下一步）。

## 快速开始

Windows 推荐直接双击启动 GUI：

```text
start_helper.bat
```

提供商配置助手（交互式一键配置）：

```text
configure_ai_provider.bat
```

默认行为：
- 扫描并导入本机 Steam 库，
- 在 GUI 中列出已安装游戏，
- 选择后即可一键启动辅助流程，
- 可在 GUI 里通过 `Voice Volume` 滑条和 `Apply` 按钮调节语音大小。
- 可在 GUI 中通过 `Enable AI Advisor` 开关控制 AI 提示改写。
- 可在 GUI 中通过 `AI Provider` 下拉框选择 AI 提供商。

也可以直接命令行打开 GUI：

```powershell
gwh gui --config config/default.yaml
```

手动命令行方式：

```powershell
python -m venv .venv
. .\.venv\Scripts\Activate.ps1
pip install -e .[runtime]
gwh init-db --config config/default.yaml
gwh run-once --config config/default.yaml --game-id "MyGame"
```

持续监控运行命令：

```powershell
gwh run-loop --config config/default.yaml --game-id "MyGame"
```

批处理 CLI 模式（可选）：

```text
start_helper.bat cli <game_id> [once|loop]
```

## 热键与参数

- `Ctrl+Alt+M`：切换语音静音。
- `Ctrl+Alt+P`：暂停或恢复识别。
- `Ctrl+Alt+H`：立即刷新并播报一次提示。
- `Ctrl+Alt+D`：切换提示详细级别（L0-L2）。
- `Ctrl+Alt+Q`：停止运行。
- 可选参数：`--no-overlay`、`--no-hotkeys`。

## Steam 集成

- 列出已安装 Steam 游戏：

```powershell
gwh steam-list --config config/default.yaml
```

- 交互式选择 Steam 游戏并输出 `game_id`：

```powershell
gwh steam-select --config config/default.yaml --id-only
```

## 攻略来源

默认优先来源：
- `gamersky.com`（游民星空）
- `3dmgame.com`（3DM）
- `steamcommunity.com`（Steam 社区指南）

可在 `config/default.yaml` 调整优先级与数量：

```yaml
guide_source_domains: "gamersky.com,3dmgame.com,steamcommunity.com"
guide_per_source_limit: 2
guide_max_candidates: 8
```

## 无任务场景模式

当游戏里没有任务文本时，可用场景关键帧：

- GUI：填写 `Label` 和可选 `Action Hint`，点击 `Capture Current Screen`。
- CLI 抓当前屏幕保存关键帧：

```powershell
gwh scene-add-keyframe --config config/default.yaml --game-id steam_214490 --label "castle_gate" --action-text "与门卫对话"
```

- CLI 从已有截图导入：

```powershell
gwh scene-add-keyframe --config config/default.yaml --game-id steam_214490 --label "boss_room" --image-path "D:\shots\boss.png" --action-text "击败 Boss"
```

- 查看该游戏关键帧：

```powershell
gwh scene-list-keyframes --config config/default.yaml --game-id steam_214490
```

## AI 提示增强（可选）

每个识别周期可抓取多帧并做时序稳定，再通过多种 API 提供商改写最终提示语。

内置支持（预设配置）：
- `openai`
- `kimi`（Moonshot）
- `deepseek`
- `qwen`（DashScope 兼容接口）
- `zhipu`（GLM）
- `anthropic`（Claude Messages API）
- `gemini`（Google Generative Language API）
- `openrouter`
- `xai`
- `ollama`（本地模型，不需要 API Key）

核心配置（`config/default.yaml`）：

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

通过环境变量快速切换（不把 Key 写入代码）：

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

一键交互配置：

```text
configure_ai_provider.bat
```

或通过启动器：

```text
start_helper.bat provider
```

脚本参数方式示例：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/set-ai-provider.ps1 -Provider kimi -ApiKey "sk-..."
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/set-ai-provider.ps1 -Provider deepseek -ApiKey "sk-..."
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/set-ai-provider.ps1 -Provider ollama
```

如果是自定义 OpenAI 兼容网关，可设置：
- `GWH_AI_ADVISOR_PROVIDER=openai`
- `GWH_AI_ADVISOR_BASE_URL=<你的接口地址>`
- `GWH_AI_ADVISOR_MODEL=<你的模型名>`
- `GWH_AI_ADVISOR_API_KEY_ENV=<你的Key环境变量名>`

## 数据库与缓存

程序使用 SQLite 作为本地唯一状态库（默认：`data/gamewalk.db`，可通过 `db_path` 配置修改）。

核心表：
- `games`、`sessions`、`observations`、`progress_states`
- `guide_docs`、`guide_steps`、`retrieval_cache`
- `voice_history`、`steam_apps`、`scene_keyframes`

常用命令：

```powershell
gwh init-db --config config/default.yaml
python -c "import sqlite3; c=sqlite3.connect('data/gamewalk.db'); print([r[0] for r in c.execute(\"select name from sqlite_master where type='table' order by name\")]); c.close()"
```

建议：定期备份 `data/gamewalk.db`，可保留游戏画像、攻略缓存与场景关键帧数据。

## 项目结构

- `src/gamewalk_helper/`：核心应用模块。
- `config/default.yaml`：运行配置。
- `tests/`：进度与语音逻辑单元测试。
- `docs/`：设计与架构文档。
- `scripts/`：本地开发脚本。
