import pytest

from callfw.agent import parse_turn
from callfw.phone import normalize


def test_normalize():
    assert normalize("600 11 22 33", "ES") == "+34600112233"
    assert normalize("912 345 678", "PT") == "+351912345678"
    assert normalize("+351 912 345 678", "ES") == "+351912345678"
    assert normalize("anonymous") is None
    assert normalize("") is None


def test_parse_turn_fills_defaults():
    t = parse_turn('{"say": "Hola", "action": "continue"}')
    assert t["reason"] == "" and t["urgency"] == "normal"


@pytest.mark.parametrize("bad", ["not json", '{"say": "x", "action": "dance"}', "[]"])
def test_parse_turn_rejects_bad(bad):
    with pytest.raises(ValueError):
        parse_turn(bad)
