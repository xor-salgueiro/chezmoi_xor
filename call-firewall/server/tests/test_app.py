import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from callfw.config import Line, Settings
from callfw.main import create_app
from callfw.store import Store

LINE = Line("+34910000000", "+34600000000", "es-ES")
CONTACT = "+34622222222"
STRANGER = "+34633333333"


class FakeGoogle:
    def __init__(self, busy=False):
        self.busy = busy

    async def contacts(self, region="ES"):
        return {CONTACT: "Ana"}

    async def is_busy_now(self):
        return self.busy


class FakeTelegram:
    def __init__(self):
        self.sent = []

    async def send(self, text):
        self.sent.append(text)


class FakeClaude:
    """Returns scripted JSON turns."""

    def __init__(self, turns):
        self.turns = list(turns)
        self.messages = self

    async def create(self, **kw):
        text = json.dumps(self.turns.pop(0))
        return SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text=text)])


def turn(action, say="ok", **kw):
    return {"say": say, "action": action, "caller_name": kw.get("caller_name", ""), "company": "",
            "reason": kw.get("reason", ""), "callback": "", "urgency": "normal", "summary": kw.get("summary", "")}


@pytest.fixture
def make(tmp_path):
    def _make(turns=(), busy=False, **settings_kw):
        settings = Settings(public_base_url="https://cf.test", lines=[LINE], twilio_validate_signature=False,
                            quiet_hours=None, app_api_token="tok", silence_timeout_s=5, **settings_kw)
        store, tg = Store(str(tmp_path / "db.sqlite3")), FakeTelegram()
        app = create_app(settings, store, FakeGoogle(busy), tg, FakeClaude(turns))
        return TestClient(app), store, tg
    return _make


def incoming(client, sid, caller):
    return client.post("/twilio/voice", data={"CallSid": sid, "From": caller, "To": LINE.twilio_number})


def converse(client, sid, utterances):
    with client.websocket_connect("/relay") as ws:
        ws.send_text(json.dumps({"type": "setup", "callSid": sid}))
        out = []
        for u in utterances:
            ws.send_text(json.dumps({"type": "prompt", "voicePrompt": u, "last": True}))
            msg = json.loads(ws.receive_text())
            out.append(msg)
            if msg["type"] == "end":
                break
        return out


def test_blocked_caller_rejected(make):
    client, store, _ = make()
    store.block(STRANGER, "test")
    assert "<Reject" in incoming(client, "CA1", STRANGER).text


def test_own_twilio_number_loop_rejected(make):
    client, _, _ = make()
    assert "<Reject" in incoming(client, "CA1", LINE.twilio_number).text


def test_unknown_caller_message_flow(make):
    client, store, tg = make(turns=[
        turn("continue", "¿Me dice su nombre?", reason="presupuesto"),
        turn("take_message", "Le devolverá la llamada.", caller_name="Luis", reason="presupuesto"),
    ])
    r = incoming(client, "CA2", STRANGER)
    assert "<ConversationRelay" in r.text and 'language="es-ES"' in r.text
    out = converse(client, "CA2", ["Llamo por un presupuesto", "Soy Luis"])
    assert out[0] == {"type": "text", "token": "¿Me dice su nombre?", "last": True}
    assert out[1]["type"] == "end"
    done = client.post("/twilio/relay-done", data={"CallSid": "CA2", "HandoffData": out[1]["handoffData"]})
    assert "Le devolverá la llamada." in done.text and "<Hangup/>" in done.text
    assert "Luis" in tg.sent[0] and "presupuesto" in tg.sent[0]
    assert not store.is_blocked(STRANGER)


def test_spam_gets_blocked(make):
    client, store, tg = make(turns=[turn("block", "Adiós.", summary="Venta de energía")])
    incoming(client, "CA3", STRANGER)
    out = converse(client, "CA3", ["Le llamo de una comercializadora de luz"])
    client.post("/twilio/relay-done", data={"CallSid": "CA3", "HandoffData": out[0]["handoffData"]})
    assert store.is_blocked(STRANGER) and "🚫" in tg.sent[0]


def test_silent_caller_blocked(make):
    client, store, _ = make()
    incoming(client, "CA4", STRANGER)
    client.post("/twilio/relay-done", data={"CallSid": "CA4"})  # hung up, never spoke
    assert store.is_blocked(STRANGER)


def test_silent_contact_never_blocked(make):
    client, store, _ = make()
    incoming(client, "CA5", CONTACT)
    client.post("/twilio/relay-done", data={"CallSid": "CA5"})
    assert not store.is_blocked(CONTACT)


def test_contact_busy_transfer_accepted(make):
    client, _, tg = make(busy=True, turns=[turn("transfer", "Le paso.", reason="urgente")])
    incoming(client, "CA6", CONTACT)
    out = converse(client, "CA6", ["Es urgente"])
    done = client.post("/twilio/relay-done", data={"CallSid": "CA6", "HandoffData": out[0]["handoffData"]})
    assert "<Dial" in done.text and LINE.owner_mobile in done.text and 'callerId="+34910000000"' in done.text
    w = client.post("/twilio/whisper?sid=CA6", data={})
    assert "Ana" in w.text and "<Gather" in w.text
    assert client.post("/twilio/whisper-result?sid=CA6", data={"Digits": "1"}).text.endswith("<Response></Response>")
    client.post("/twilio/dial-done?sid=CA6", data={"DialCallStatus": "completed"})
    assert "📞" in tg.sent[0]


def test_contact_busy_transfer_declined_takes_message(make):
    client, _, tg = make(busy=True, turns=[turn("transfer", "Le paso.", reason="factura")])
    incoming(client, "CA7", CONTACT)
    out = converse(client, "CA7", ["Por la factura"])
    client.post("/twilio/relay-done", data={"CallSid": "CA7", "HandoffData": out[0]["handoffData"]})
    client.post("/twilio/whisper-result?sid=CA7", data={})
    r = client.post("/twilio/dial-done?sid=CA7", data={"DialCallStatus": "no-answer"})
    assert "devolverá la llamada" in r.text and "📩" in tg.sent[0]


def test_api_requires_token(make):
    client, store, _ = make()
    assert client.get("/api/blocklist").status_code == 401
    store.block(STRANGER, "x")
    r = client.get("/api/blocklist", headers={"Authorization": "Bearer tok"})
    assert r.json() == {"numbers": [STRANGER]}
