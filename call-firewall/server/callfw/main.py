"""FastAPI app: Twilio webhooks, ConversationRelay WebSocket and the Android app API."""
from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from urllib.parse import quote
from zoneinfo import ZoneInfo

import anthropic
from fastapi import Depends, FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import Response
from twilio.request_validator import RequestValidator

from . import twiml
from .agent import CallAgent, lang_key
from .config import Line, Settings
from .google_api import Google
from .phone import normalize, region_for_language
from .store import Store
from .telegram import Telegram, format_message
from .triage import Action, CallContext, decide, may_block

log = logging.getLogger("callfw")

TRANSFER_NOTICE = {"es": "Un momento, le paso.", "pt": "Um momento, vou passar a chamada."}
TRANSFER_FAILED = {
    "es": "{owner} no puede atender ahora mismo. Le dejo el recado y le devolverá la llamada. Hasta luego.",
    "pt": "{owner} não pode atender agora. Deixo o recado e ele devolve a chamada. Até logo.",
}
WHISPER = {
    "es": "Llamada de {who}. Motivo: {reason}. Pulse 1 para aceptar.",
    "pt": "Chamada de {who}. Motivo: {reason}. Prima 1 para aceitar.",
}


@dataclass
class Session:
    call_sid: str
    line: Line
    ctx: CallContext
    agent: CallAgent
    contact_name: str | None
    heard_speech: bool = False
    transfer_accepted: bool = False
    tasks: list[asyncio.Task] = field(default_factory=list)


def in_quiet_hours(settings: Settings, now: datetime | None = None) -> bool:
    if not settings.quiet_hours:
        return False
    start, end = settings.quiet_hours
    t = (now or datetime.now(ZoneInfo(settings.timezone))).time()
    return start <= t < end if start < end else (t >= start or t < end)


def create_app(settings: Settings, store: Store, google: Google, telegram: Telegram,
               claude: anthropic.AsyncAnthropic) -> FastAPI:
    app = FastAPI(title="call-firewall")
    sessions: dict[str, Session] = {}
    validator = RequestValidator(settings.twilio_auth_token)

    def url(path: str, **query: str) -> str:
        qs = "&".join(f"{k}={quote(v)}" for k, v in query.items())
        return f"{settings.public_base_url}{path}" + (f"?{qs}" if qs else "")

    async def twilio_form(request: Request) -> dict[str, str]:
        form = {k: str(v) for k, v in (await request.form()).items()}
        if settings.twilio_validate_signature:
            full = f"{settings.public_base_url}{request.url.path}"
            if request.url.query:
                full += f"?{request.url.query}"
            if not validator.validate(full, form, request.headers.get("X-Twilio-Signature", "")):
                raise HTTPException(403, "bad twilio signature")
        return form

    def xml(body: str) -> Response:
        return Response(content=body, media_type="application/xml")

    def require_app_token(request: Request) -> None:
        if not settings.app_api_token or request.headers.get("Authorization") != f"Bearer {settings.app_api_token}":
            raise HTTPException(401)

    async def notify(s: Session, outcome: str, result: dict) -> None:
        store.log_call(s.call_sid, s.ctx.caller, s.line.owner_mobile, s.agent.mode.value, outcome, result)
        if outcome == "blocked" and not settings.telegram_notify_blocked:
            return
        await telegram.send(format_message(caller=s.ctx.caller, contact_name=s.contact_name,
                                           line=s.line.owner_mobile, outcome=outcome, result=result))

    # ---------- Twilio: incoming forwarded call ----------
    @app.post("/twilio/voice")
    async def voice(form: dict = Depends(twilio_form)) -> Response:
        call_sid, to = form.get("CallSid", ""), form.get("To", "")
        line = settings.line_for(to)
        if line is None:
            log.warning("call to unconfigured number %s", to)
            return xml(twiml.response(twiml.reject()))
        region = region_for_language(line.language)
        caller = normalize(form.get("From"), region)
        contacts = await google.contacts(region)
        busy = in_quiet_hours(settings) or await google.is_busy_now()
        ctx = CallContext(
            caller=caller,
            from_own_twilio=caller is not None and settings.is_own_twilio_number(caller),
            is_contact=caller in contacts,
            is_blocked=store.is_blocked(caller),
            owner_busy=busy,
        )
        decision = decide(ctx)
        log.info("call %s from %s line %s -> %s (%s)", call_sid, caller, line.owner_mobile,
                 decision.action.value, decision.reason)
        if decision.action is Action.REJECT:
            store.log_call(call_sid, caller, line.owner_mobile, "-", "rejected", {"reason": decision.reason})
            return xml(twiml.response(twiml.reject()))
        contact_name = contacts.get(caller) if caller else None
        agent = CallAgent(client=claude, model=settings.claude_model, owner=settings.owner_name,
                          language=line.language, mode=decision.mode, caller=caller, contact_name=contact_name)
        sessions[call_sid] = Session(call_sid, line, ctx, agent, contact_name)
        ws_url = settings.public_base_url.replace("https://", "wss://", 1).replace("http://", "ws://", 1) + "/relay"
        return xml(twiml.response(twiml.conversation_relay(
            ws_url, url("/twilio/relay-done"), line.language, agent.greeting)))

    # ---------- ConversationRelay WebSocket ----------
    @app.websocket("/relay")
    async def relay(ws: WebSocket) -> None:
        await ws.accept()
        session: Session | None = None
        ended = asyncio.Event()

        async def end(handoff: dict) -> None:
            if not ended.is_set():
                ended.set()
                await ws.send_text(json.dumps({"type": "end", "handoffData": json.dumps(handoff, ensure_ascii=False)}))

        async def watchdog(s: Session) -> None:
            await asyncio.sleep(settings.silence_timeout_s)
            if not s.heard_speech:
                await end({"action": "silent"})
                return
            await asyncio.sleep(max(0.0, settings.max_call_s - settings.silence_timeout_s))
            await end({**s.agent.fallback(), "action": "take_message"})

        try:
            while not ended.is_set():
                msg = json.loads(await ws.receive_text())
                kind = msg.get("type")
                if kind == "setup":
                    session = sessions.get(msg.get("callSid", ""))
                    if session is None:
                        await end({"action": "silent"})
                        break
                    session.tasks.append(asyncio.create_task(watchdog(session)))
                elif kind == "prompt" and session and msg.get("last", True):
                    text = (msg.get("voicePrompt") or "").strip()
                    if not text:
                        continue
                    session.heard_speech = True
                    result = await session.agent.reply(text)
                    if result["action"] == "continue":
                        await ws.send_text(json.dumps({"type": "text", "token": result["say"], "last": True}))
                    else:
                        # The goodbye/transfer notice is spoken by TwiML after the relay ends.
                        await end(result)
                elif kind == "error":
                    log.error("relay error: %s", msg)
        except WebSocketDisconnect:
            pass
        finally:
            if session:
                for t in session.tasks:
                    t.cancel()

    # ---------- After the relay: act on the outcome ----------
    @app.post("/twilio/relay-done")
    async def relay_done(form: dict = Depends(twilio_form)) -> Response:
        s = sessions.get(form.get("CallSid", ""))
        if s is None:
            return xml(twiml.response(twiml.hangup()))
        lk = lang_key(s.line.language)
        try:
            result = json.loads(form.get("HandoffData") or "{}")
        except json.JSONDecodeError:
            result = {}
        if not result:  # caller hung up: keep what we learnt, or treat as silent
            result = {**s.agent.last, "action": "take_message"} if s.heard_speech else {"action": "silent"}
        action = result.get("action")

        if action in ("silent", "block"):
            sessions.pop(s.call_sid, None)
            if may_block(s.ctx):
                store.block(s.ctx.caller, "silence" if action == "silent" else result.get("summary") or "spam")
            await notify(s, "blocked", {**result, "summary": result.get("summary") or "Sin respuesta (silencio)"})
            return xml(twiml.response(twiml.say(result.get("say", ""), s.line.language), twiml.hangup()))

        if action == "transfer":
            return xml(twiml.response(
                twiml.say(result.get("say") or TRANSFER_NOTICE[lk], s.line.language),
                twiml.dial_owner(s.line.owner_mobile, s.line.twilio_number, settings.transfer_ring_s,
                                 url("/twilio/dial-done", sid=s.call_sid), url("/twilio/whisper", sid=s.call_sid)),
            ))

        sessions.pop(s.call_sid, None)
        await notify(s, "message", result)
        return xml(twiml.response(twiml.say(result.get("say", ""), s.line.language), twiml.hangup()))

    # ---------- Transfer: whisper to the owner before bridging ----------
    @app.post("/twilio/whisper")
    async def whisper(sid: str, form: dict = Depends(twilio_form)) -> Response:
        s = sessions.get(sid)
        if s is None:
            return xml(twiml.response(twiml.hangup()))
        r = s.agent.last
        who = s.contact_name or r.get("caller_name") or "desconocido"
        prompt = WHISPER[lang_key(s.line.language)].format(who=who, reason=r.get("reason") or "-")
        return xml(twiml.response(
            twiml.gather_digit(url("/twilio/whisper-result", sid=sid), prompt, s.line.language), twiml.hangup()))

    @app.post("/twilio/whisper-result")
    async def whisper_result(sid: str, form: dict = Depends(twilio_form)) -> Response:
        s = sessions.get(sid)
        if s is not None and form.get("Digits") == "1":
            s.transfer_accepted = True
            return xml(twiml.response())  # empty -> bridge the call
        return xml(twiml.response(twiml.hangup()))

    @app.post("/twilio/dial-done")
    async def dial_done(sid: str, form: dict = Depends(twilio_form)) -> Response:
        s = sessions.pop(sid, None)
        if s is None:
            return xml(twiml.response(twiml.hangup()))
        if s.transfer_accepted:
            await notify(s, "transferred", s.agent.last)
            return xml(twiml.response(twiml.hangup()))
        await notify(s, "transfer_missed", s.agent.last)
        msg = TRANSFER_FAILED[lang_key(s.line.language)].format(owner=settings.owner_name)
        return xml(twiml.response(twiml.say(msg, s.line.language), twiml.hangup()))

    # ---------- Android app API ----------
    @app.get("/api/blocklist", dependencies=[Depends(require_app_token)])
    async def get_blocklist() -> dict:
        return {"numbers": store.blocklist()}

    @app.post("/api/blocklist", dependencies=[Depends(require_app_token)])
    async def add_block(body: dict) -> dict:
        number = normalize(str(body.get("number", "")))
        if not number:
            raise HTTPException(400, "invalid number")
        store.block(number, "manual")
        return {"ok": True, "number": number}

    @app.delete("/api/blocklist/{number}", dependencies=[Depends(require_app_token)])
    async def remove_block(number: str) -> dict:
        n = normalize(number)
        if n:
            store.unblock(n)
        return {"ok": True}

    @app.get("/health")
    async def health() -> dict:
        return {"ok": True, "active_calls": len(sessions)}

    return app


def build() -> FastAPI:
    """Entry point for uvicorn: `uvicorn callfw.main:build --factory`."""
    logging.basicConfig(level=logging.INFO)
    s = Settings()
    return create_app(
        s, Store(s.db_path),
        Google(s.google_client_id, s.google_client_secret, s.google_refresh_token),
        Telegram(s.telegram_bot_token, s.telegram_chat_id),
        anthropic.AsyncAnthropic(),
    )
