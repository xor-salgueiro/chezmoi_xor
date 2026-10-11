"""Settings loaded from environment variables."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import time


@dataclass(frozen=True)
class Line:
    twilio_number: str  # receives the forwards of this line
    owner_mobile: str  # the Digi line itself
    language: str  # es-ES | pt-PT


def _parse_lines(raw: str) -> list[Line]:
    lines = []
    for chunk in filter(None, (c.strip() for c in raw.split(","))):
        twilio_number, owner_mobile, language = (p.strip() for p in chunk.split("|"))
        lines.append(Line(twilio_number, owner_mobile, language))
    return lines


def _parse_quiet(raw: str) -> tuple[time, time] | None:
    if not raw.strip():
        return None
    start, end = raw.split("-")
    return time.fromisoformat(start.strip()), time.fromisoformat(end.strip())


def _bool(name: str, default: str) -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes"}


@dataclass(frozen=True)
class Settings:
    public_base_url: str = field(default_factory=lambda: os.getenv("PUBLIC_BASE_URL", "").rstrip("/"))
    owner_name: str = field(default_factory=lambda: os.getenv("OWNER_NAME", "Rui"))
    timezone: str = field(default_factory=lambda: os.getenv("TIMEZONE", "Europe/Madrid"))
    quiet_hours: tuple[time, time] | None = field(default_factory=lambda: _parse_quiet(os.getenv("QUIET_HOURS", "")))
    lines: list[Line] = field(default_factory=lambda: _parse_lines(os.getenv("LINES", "")))
    twilio_auth_token: str = field(default_factory=lambda: os.getenv("TWILIO_AUTH_TOKEN", ""))
    twilio_validate_signature: bool = field(default_factory=lambda: _bool("TWILIO_VALIDATE_SIGNATURE", "true"))
    claude_model: str = field(default_factory=lambda: os.getenv("CLAUDE_MODEL", "claude-haiku-5-5"))
    google_client_id: str = field(default_factory=lambda: os.getenv("GOOGLE_CLIENT_ID", ""))
    google_client_secret: str = field(default_factory=lambda: os.getenv("GOOGLE_CLIENT_SECRET", ""))
    google_refresh_token: str = field(default_factory=lambda: os.getenv("GOOGLE_REFRESH_TOKEN", ""))
    telegram_bot_token: str = field(default_factory=lambda: os.getenv("TELEGRAM_BOT_TOKEN", ""))
    telegram_chat_id: str = field(default_factory=lambda: os.getenv("TELEGRAM_CHAT_ID", ""))
    telegram_notify_blocked: bool = field(default_factory=lambda: _bool("TELEGRAM_NOTIFY_BLOCKED", "true"))
    app_api_token: str = field(default_factory=lambda: os.getenv("APP_API_TOKEN", ""))
    silence_timeout_s: float = field(default_factory=lambda: float(os.getenv("SILENCE_TIMEOUT_S", "10")))
    max_call_s: float = field(default_factory=lambda: float(os.getenv("MAX_CALL_S", "150")))
    transfer_ring_s: int = field(default_factory=lambda: int(os.getenv("TRANSFER_RING_S", "12")))
    db_path: str = field(default_factory=lambda: os.getenv("DB_PATH", "callfw.sqlite3"))

    def line_for(self, twilio_number: str) -> Line | None:
        return next((l for l in self.lines if l.twilio_number == twilio_number), None)

    def is_own_twilio_number(self, number: str) -> bool:
        return any(l.twilio_number == number for l in self.lines)
