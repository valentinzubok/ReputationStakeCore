import json
from pathlib import Path

import pytest

from conftest import load_contract

ROOT = Path(__file__).resolve().parents[1]
mod = load_contract(ROOT, "ReputationStake.py")
OWNER = "0x1111111111111111111111111111111111111111"
OTHER = "0x2222222222222222222222222222222222222222"
STAKER = "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
TARGET = "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
URL = "https://test-server.genlayer.com/static/genvm/hello.html"


def test_admin_and_views():
    import genlayer

    c = mod.ReputationStake(OWNER, OWNER)
    genlayer.message.sender_address = OWNER
    assert c.get_owner() == OWNER
    assert c.get_arbiter() == OWNER
    c.set_arbiter(OTHER)
    assert c.get_arbiter() == OTHER
    c.set_fee(OWNER, "25")
    assert json.loads(c.get_fee())["amount"] == "25"
    c.credit_reputation(STAKER, "100")
    genlayer.message.sender_address = STAKER
    c.stake("40", TARGET, "demo purpose")
    stats = json.loads(c.get_stats())
    assert stats["active"] == 1
    assert stats["total_escrowed"] == 40
    active = json.loads(c.list_by_status("active"))
    assert len(active) == 1
    genlayer.message.sender_address = OWNER
    c.release(active[0])
    stats = json.loads(c.get_stats())
    assert stats["released"] == 1


def test_slash_unauthorized():
    import genlayer

    c = mod.ReputationStake(OWNER, OWNER)
    genlayer.message.sender_address = OWNER
    c.credit_reputation(STAKER, "50")
    genlayer.message.sender_address = STAKER
    c.stake("20", TARGET, "work")
    sid = json.loads(c.list_ids())[0]
    genlayer.message.sender_address = TARGET
    with pytest.raises(Exception, match="only arbiter"):
        c.slash(sid, "no", URL)
