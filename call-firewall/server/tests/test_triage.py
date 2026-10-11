from callfw.triage import Action, CallContext, Mode, decide, may_block


def ctx(**kw):
    base = dict(caller="+34611111111", from_own_twilio=False, is_contact=False, is_blocked=False, owner_busy=False)
    return CallContext(**{**base, **kw})


def test_loop_is_rejected_first():
    assert decide(ctx(from_own_twilio=True, is_contact=True)).action is Action.REJECT


def test_blocked_rejected():
    assert decide(ctx(is_blocked=True)).action is Action.REJECT


def test_contact_busy_goes_to_transfer_mode():
    d = decide(ctx(is_contact=True, owner_busy=True))
    assert (d.action, d.mode) == (Action.AGENT, Mode.CONTACT_BUSY)


def test_contact_free_but_missed_takes_message():
    assert decide(ctx(is_contact=True)).mode is Mode.CONTACT_MISSED


def test_unknown_and_hidden_are_screened():
    assert decide(ctx()).mode is Mode.UNKNOWN
    assert decide(ctx(caller=None)).mode is Mode.UNKNOWN


def test_only_identified_non_contacts_can_be_blocked():
    assert may_block(ctx())
    assert not may_block(ctx(caller=None))
    assert not may_block(ctx(is_contact=True))
