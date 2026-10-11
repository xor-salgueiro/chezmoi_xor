"""Minimal TwiML builders (string based, attribute-escaped)."""
from __future__ import annotations

from xml.sax.saxutils import escape, quoteattr


def _attrs(**kw) -> str:
    return "".join(f" {k.replace('_', '')}={quoteattr(str(v))}" for k, v in kw.items() if v is not None)


def response(*parts: str) -> str:
    return '<?xml version="1.0" encoding="UTF-8"?><Response>' + "".join(parts) + "</Response>"


def say(text: str, language: str) -> str:
    return f"<Say{_attrs(language=language)}>{escape(text)}</Say>" if text else ""


def hangup() -> str:
    return "<Hangup/>"


def reject() -> str:
    return '<Reject reason="busy"/>'


def conversation_relay(ws_url: str, action_url: str, language: str, greeting: str) -> str:
    relay = f"<ConversationRelay{_attrs(url=ws_url, language=language, welcomeGreeting=greeting)}/>"
    return f"<Connect{_attrs(action=action_url)}>{relay}</Connect>"


def dial_owner(number: str, caller_id: str, timeout: int, action_url: str, whisper_url: str) -> str:
    inner = f"<Number{_attrs(url=whisper_url)}>{escape(number)}</Number>"
    return f"<Dial{_attrs(callerId=caller_id, timeout=timeout, action=action_url)}>{inner}</Dial>"


def gather_digit(action_url: str, prompt: str, language: str, timeout: int = 6) -> str:
    return f"<Gather{_attrs(numDigits=1, action=action_url, timeout=timeout)}>{say(prompt, language)}</Gather>"
