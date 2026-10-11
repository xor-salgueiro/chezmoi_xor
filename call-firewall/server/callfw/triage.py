"""Pure triage rules. No I/O: easy to test and reason about.

A call only reaches the server when the owner's phone did not take it
(rejected by the app, not answered, busy or unreachable) and the carrier
forwarded it to the line's Twilio number.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Action(str, Enum):
    REJECT = "reject"  # hang up without speaking
    AGENT = "agent"  # AI assistant answers


class Mode(str, Enum):
    CONTACT_BUSY = "contact_busy"  # R2: ask reason, then offer transfer to owner
    CONTACT_MISSED = "contact_missed"  # contact, owner free but did not answer: take message
    UNKNOWN = "unknown"  # R3: screen, take message, promise callback


@dataclass(frozen=True)
class CallContext:
    caller: str | None  # E.164, None when hidden
    from_own_twilio: bool  # our own transfer leg bounced back (loop)
    is_contact: bool
    is_blocked: bool
    owner_busy: bool


@dataclass(frozen=True)
class Decision:
    action: Action
    mode: Mode | None = None
    reason: str = ""


def decide(ctx: CallContext) -> Decision:
    if ctx.from_own_twilio:
        return Decision(Action.REJECT, reason="forwarding loop")
    if ctx.is_blocked:  # R5
        return Decision(Action.REJECT, reason="blocklist")
    if ctx.is_contact:
        if ctx.owner_busy:
            return Decision(Action.AGENT, Mode.CONTACT_BUSY, "contact while busy")
        return Decision(Action.AGENT, Mode.CONTACT_MISSED, "contact not answered")
    return Decision(Action.AGENT, Mode.UNKNOWN, "unknown or hidden caller")


def may_block(ctx: CallContext) -> bool:
    """R4 applies only to callers we can identify and who are not contacts."""
    return ctx.caller is not None and not ctx.is_contact
