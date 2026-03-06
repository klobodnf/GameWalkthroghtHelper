from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
import sqlite3

from .models import GuideStepCandidate, Observation


class Database:
    def __init__(self, db_path: str) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path)
        self._conn.row_factory = sqlite3.Row

    def close(self) -> None:
        self._conn.close()

    def init_schema(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS games (
              game_id TEXT PRIMARY KEY,
              exe_name TEXT,
              window_pattern TEXT,
              language TEXT,
              profile_json TEXT DEFAULT '{}',
              profile_version INTEGER DEFAULT 1,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS sessions (
              session_id INTEGER PRIMARY KEY AUTOINCREMENT,
              game_id TEXT NOT NULL,
              started_at TEXT NOT NULL,
              ended_at TEXT,
              FOREIGN KEY (game_id) REFERENCES games(game_id)
            );

            CREATE TABLE IF NOT EXISTS observations (
              observation_id INTEGER PRIMARY KEY AUTOINCREMENT,
              session_id INTEGER NOT NULL,
              ts TEXT NOT NULL,
              roi TEXT,
              ocr_text TEXT,
              ocr_conf REAL,
              cv_labels TEXT DEFAULT '[]',
              frame_hash TEXT,
              FOREIGN KEY (session_id) REFERENCES sessions(session_id)
            );

            CREATE INDEX IF NOT EXISTS idx_observations_session_ts
              ON observations(session_id, ts);

            CREATE TABLE IF NOT EXISTS guide_docs (
              doc_id INTEGER PRIMARY KEY AUTOINCREMENT,
              game_id TEXT NOT NULL,
              source_url TEXT NOT NULL,
              raw_text TEXT NOT NULL,
              quality_score REAL DEFAULT 0.5,
              fetched_at TEXT NOT NULL,
              UNIQUE(game_id, source_url)
            );

            CREATE VIRTUAL TABLE IF NOT EXISTS guide_docs_fts
              USING fts5(raw_text, content='guide_docs', content_rowid='doc_id');

            CREATE TABLE IF NOT EXISTS guide_steps (
              step_id INTEGER PRIMARY KEY AUTOINCREMENT,
              game_id TEXT NOT NULL,
              state_id TEXT NOT NULL,
              trigger_keywords TEXT DEFAULT '[]',
              cv_keywords TEXT DEFAULT '[]',
              action_text TEXT NOT NULL,
              priority INTEGER DEFAULT 0,
              source_url TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_guide_steps_game_state
              ON guide_steps(game_id, state_id);

            CREATE VIRTUAL TABLE IF NOT EXISTS guide_steps_fts
              USING fts5(action_text, content='guide_steps', content_rowid='step_id');

            CREATE TABLE IF NOT EXISTS progress_states (
              progress_id INTEGER PRIMARY KEY AUTOINCREMENT,
              session_id INTEGER NOT NULL,
              ts TEXT NOT NULL,
              state_id TEXT,
              confidence REAL,
              evidence_observation_id INTEGER,
              next_action TEXT,
              definitive INTEGER NOT NULL DEFAULT 0
            );

            CREATE INDEX IF NOT EXISTS idx_progress_session_ts
              ON progress_states(session_id, ts);

            CREATE TABLE IF NOT EXISTS retrieval_cache (
              cache_key TEXT PRIMARY KEY,
              game_id TEXT NOT NULL,
              query TEXT NOT NULL,
              payload_json TEXT NOT NULL,
              expires_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS voice_history (
              voice_key TEXT PRIMARY KEY,
              game_id TEXT NOT NULL,
              message TEXT NOT NULL,
              cooldown_until TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS steam_apps (
              app_id TEXT PRIMARY KEY,
              name TEXT NOT NULL,
              install_dir TEXT,
              library_path TEXT,
              last_seen_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_steam_apps_name
              ON steam_apps(name);
            """
        )
        self._conn.commit()

    def upsert_game(self, game_id: str, exe_name: str = "", window_pattern: str = "", language: str = "auto") -> None:
        now = _utc_now().isoformat()
        self._conn.execute(
            """
            INSERT INTO games(game_id, exe_name, window_pattern, language, created_at, updated_at)
            VALUES(?, ?, ?, ?, ?, ?)
            ON CONFLICT(game_id) DO UPDATE SET
              exe_name=excluded.exe_name,
              window_pattern=excluded.window_pattern,
              language=excluded.language,
              updated_at=excluded.updated_at
            """,
            (game_id, exe_name, window_pattern, language, now, now),
        )
        self._conn.commit()

    def start_session(self, game_id: str) -> int:
        now = _utc_now().isoformat()
        cur = self._conn.execute(
            "INSERT INTO sessions(game_id, started_at) VALUES(?, ?)",
            (game_id, now),
        )
        self._conn.commit()
        return int(cur.lastrowid)

    def end_session(self, session_id: int) -> None:
        now = _utc_now().isoformat()
        self._conn.execute(
            "UPDATE sessions SET ended_at=? WHERE session_id=?",
            (now, session_id),
        )
        self._conn.commit()

    def add_observation(self, observation: Observation) -> int:
        cur = self._conn.execute(
            """
            INSERT INTO observations(session_id, ts, roi, ocr_text, ocr_conf, cv_labels, frame_hash)
            VALUES(?, ?, ?, ?, ?, ?, ?)
            """,
            (
                observation.session_id,
                observation.timestamp.isoformat(),
                observation.roi,
                observation.task_text,
                observation.task_confidence,
                json.dumps(observation.cv_labels, ensure_ascii=False),
                observation.frame_hash,
            ),
        )
        self._conn.commit()
        return int(cur.lastrowid)

    def save_progress_state(
        self,
        session_id: int,
        state_id: str | None,
        confidence: float,
        evidence_observation_id: int | None,
        next_action: str,
        definitive: bool,
    ) -> None:
        self._conn.execute(
            """
            INSERT INTO progress_states(session_id, ts, state_id, confidence, evidence_observation_id, next_action, definitive)
            VALUES(?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                _utc_now().isoformat(),
                state_id,
                confidence,
                evidence_observation_id,
                next_action,
                int(definitive),
            ),
        )
        self._conn.commit()

    def get_last_progress_state(self, session_id: int) -> str | None:
        row = self._conn.execute(
            """
            SELECT state_id FROM progress_states
            WHERE session_id=?
            ORDER BY progress_id DESC
            LIMIT 1
            """,
            (session_id,),
        ).fetchone()
        if not row:
            return None
        return row["state_id"]

    def get_cache(self, cache_key: str) -> list[GuideStepCandidate] | None:
        row = self._conn.execute(
            """
            SELECT payload_json, expires_at
            FROM retrieval_cache
            WHERE cache_key=?
            """,
            (cache_key,),
        ).fetchone()
        if not row:
            return None
        expires_at = datetime.fromisoformat(row["expires_at"])
        if _utc_now() >= expires_at:
            return None
        payload = json.loads(row["payload_json"])
        return [GuideStepCandidate(**item) for item in payload]

    def set_cache(self, cache_key: str, game_id: str, query: str, steps: list[GuideStepCandidate], ttl_hours: int) -> None:
        now = _utc_now()
        expires = now + timedelta(hours=ttl_hours)
        payload = json.dumps([asdict(candidate) for candidate in steps], ensure_ascii=False)
        self._conn.execute(
            """
            INSERT INTO retrieval_cache(cache_key, game_id, query, payload_json, expires_at, updated_at)
            VALUES(?, ?, ?, ?, ?, ?)
            ON CONFLICT(cache_key) DO UPDATE SET
              payload_json=excluded.payload_json,
              expires_at=excluded.expires_at,
              updated_at=excluded.updated_at
            """,
            (cache_key, game_id, query, payload, expires.isoformat(), now.isoformat()),
        )
        self._conn.commit()

    def should_speak(self, voice_key: str) -> bool:
        row = self._conn.execute(
            """
            SELECT cooldown_until
            FROM voice_history
            WHERE voice_key=?
            """,
            (voice_key,),
        ).fetchone()
        if not row:
            return True
        cooldown_until = datetime.fromisoformat(row["cooldown_until"])
        return _utc_now() >= cooldown_until

    def mark_spoken(self, voice_key: str, game_id: str, message: str, cooldown_seconds: int) -> None:
        now = _utc_now()
        cooldown_until = now + timedelta(seconds=cooldown_seconds)
        self._conn.execute(
            """
            INSERT INTO voice_history(voice_key, game_id, message, cooldown_until, updated_at)
            VALUES(?, ?, ?, ?, ?)
            ON CONFLICT(voice_key) DO UPDATE SET
              game_id=excluded.game_id,
              message=excluded.message,
              cooldown_until=excluded.cooldown_until,
              updated_at=excluded.updated_at
            """,
            (voice_key, game_id, message, cooldown_until.isoformat(), now.isoformat()),
        )
        self._conn.commit()

    def sync_steam_apps(self, apps: list[dict[str, str]]) -> None:
        now = _utc_now().isoformat()
        if not apps:
            return
        for app in apps:
            self._conn.execute(
                """
                INSERT INTO steam_apps(app_id, name, install_dir, library_path, last_seen_at)
                VALUES(?, ?, ?, ?, ?)
                ON CONFLICT(app_id) DO UPDATE SET
                  name=excluded.name,
                  install_dir=excluded.install_dir,
                  library_path=excluded.library_path,
                  last_seen_at=excluded.last_seen_at
                """,
                (
                    app.get("app_id", ""),
                    app.get("name", ""),
                    app.get("install_dir", ""),
                    app.get("library_path", ""),
                    now,
                ),
            )
        self._conn.commit()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)
