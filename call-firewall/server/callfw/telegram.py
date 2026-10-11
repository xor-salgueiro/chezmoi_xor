"""Telegram notifications."""
from __future__ import annotations

import logging

import httpx

log = logging.getLogger(__name__)


class Telegram:
    def __init__(self, bot_token: str, chat_id: str):
        self._url = f"https://api.telegram.org/bot{bot_token}/sendMessage" if bot_token else ""
        self._chat_id = chat_id

    async def send(self, text: str) -> None:
        if not self._url:
            log.info("telegram disabled: %s", text)
            return
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.post(self._url, json={
                    "chat_id": self._chat_id, "text": text, "disable_web_page_preview": True,
                })
                r.raise_for_status()
        except httpx.HTTPError as exc:
            log.warning("telegram send failed: %s", exc)


def format_message(*, caller: str | None, contact_name: str | None, line: str, outcome: str, result: dict) -> str:
    who = contact_name or result.get("caller_name") or "Desconocido"
    number = caller or "número oculto"
    icon = {"message": "📩", "transfer_missed": "📩", "transferred": "📞", "blocked": "🚫"}.get(outcome, "ℹ️")
    lines = [f"{icon} {who} ({number}) → línea {line}"]
    for label, key in (("Empresa", "company"), ("Motivo", "reason"), ("Devolver a", "callback"),
                       ("Urgencia", "urgency"), ("Resumen", "summary")):
        value = (result.get(key) or "").strip()
        if value:
            lines.append(f"{label}: {value}")
    if outcome == "blocked":
        lines.append("Bloqueado. Para desbloquear: DELETE /api/blocklist/<número>")
    if caller:
        lines.append(f"Llamar: tel:{caller}")
    return "\n".join(lines)
