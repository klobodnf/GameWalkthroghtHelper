# Architecture (V1)

## Pipeline

1. Capture the active game frame.
2. Auto-locate likely mission/task ROI (or use configured manual ROI), then run OCR; collect optional CV labels.
3. Build an observation event and store it in SQLite.
4. Retrieve candidate guide steps from local cache or online search.
5. Score candidate states and produce a high-confidence next step (or fallback suggestions).
6. Speak the result if cooldown allows, and expose text for overlay UI.
7. Runtime control plane handles global hotkeys (mute/pause/force refresh/detail level).
8. Desktop GUI (Tkinter) provides Steam game selection and start/stop orchestration.
9. Voice coach supports app-level volume control for TTS playback.

## Design rules

- Non-invasive only: no process injection or memory reading.
- Confidence-gated guidance: low confidence never issues hard instructions.
- Cache-first retrieval: minimize repeated network calls for the same task text.
- Deterministic core logic so behavior is testable.
- Pause-safe runtime controls: users can pause recognition without stopping the session.
