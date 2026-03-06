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

## 快速开始

Windows 推荐直接双击启动 GUI：

```text
start_helper.bat
```

默认行为：
- 扫描并导入本机 Steam 库，
- 在 GUI 中列出已安装游戏，
- 选择后即可一键启动辅助流程，
- 可在 GUI 里通过 `Voice Volume` 滑条和 `Apply` 按钮调节语音大小。

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

## 项目结构

- `src/gamewalk_helper/`：核心应用模块。
- `config/default.yaml`：运行配置。
- `tests/`：进度与语音逻辑单元测试。
- `docs/`：设计与架构文档。
- `scripts/`：本地开发脚本。
