import json
from pathlib import Path

import pytest

from conftest import load_contract

ROOT = Path(__file__).resolve().parents[1]
mod = load_contract(ROOT, "ReputationStake.py")
OWNER = "0x1111111111111111111111111111111111111111"
STAKER = "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
TARGET = "0x2222222222222222222222222222222222222222"
OTHER = "0x3333333333333333333333333333333333333333"
URL = "https://test-server.genlayer.com/static/genvm/hello.html"


def _contract():
    return mod.ReputationStake(OWNER, OWNER)


def test_stake_release_by_target():
    import genlayer

    c = _contract()
    genlayer.message.sender_address = OWNER
    c.credit_reputation(STAKER, "500")
    genlayer.message.sender_address = STAKER
    c.stake("200", TARGET, "API access guarantee")
    stake_id = json.loads(c.list_ids())[0]
    # Staker cannot release
    with pytest.raises(Exception, match="only target or owner"):
        c.release(stake_id)
    genlayer.message.sender_address = TARGET
    c.release(stake_id)
    entry = json.loads(c.get_stake(stake_id))
    assert entry["status"] == "released"
    bal = json.loads(c.get_balance(STAKER))
    assert bal["available"] == 500


def test_slash_with_consensus_breach():
    import genlayer

    c = _contract()
    genlayer.message.sender_address = OWNER
    c.credit_reputation(STAKER, "300")
    genlayer.message.sender_address = STAKER
    c.stake("150", TARGET, "course delivery on time")
    stake_id = json.loads(c.list_ids())[0]
    genlayer.message.sender_address = OWNER
    c.slash(stake_id, "delivered late — no course", URL)
    entry = json.loads(c.get_stake(stake_id))
    assert entry["status"] == "slashed"
    assert entry["breach"] is True
    assert entry["evidence_hash"]
    target_bal = json.loads(c.get_balance(TARGET))
    assert target_bal["available"] == 150


def test_slash_aborts_when_no_breach(monkeypatch):
    import genlayer

    monkeypatch.setattr(
        genlayer.nondet,
        "exec_prompt",
        lambda prompt, response_format="json": '{"breach": false}',
    )
    monkeypatch.setattr(genlayer, "exec_prompt", lambda prompt: '{"breach": false}')

    c = _contract()
    genlayer.message.sender_address = OWNER
    c.credit_reputation(STAKER, "100")
    genlayer.message.sender_address = STAKER
    c.stake("50", TARGET, "work")
    stake_id = json.loads(c.list_ids())[0]
    genlayer.message.sender_address = OWNER
    with pytest.raises(Exception, match="did not find breach"):
        c.slash(stake_id, "weak claim", URL)
    entry = json.loads(c.get_stake(stake_id))
    assert entry["status"] == "active"


def test_insufficient_balance():
    import genlayer

    c = _contract()
    genlayer.message.sender_address = STAKER
    with pytest.raises(Exception, match="insufficient"):
        c.stake("10", TARGET, "x")


def test_cannot_stake_to_self():
    import genlayer

    c = _contract()
    genlayer.message.sender_address = OWNER
    c.credit_reputation(STAKER, "100")
    genlayer.message.sender_address = STAKER
    with pytest.raises(Exception, match="yourself"):
        c.stake("10", STAKER, "x")


def test_release_unauthorized():
    import genlayer

    c = _contract()
    genlayer.message.sender_address = OWNER
    c.credit_reputation(STAKER, "100")
    genlayer.message.sender_address = STAKER
    c.stake("50", TARGET, "work")
    stake_id = json.loads(c.list_ids())[0]
    genlayer.message.sender_address = OTHER
    with pytest.raises(Exception, match="only target or owner"):
        c.release(stake_id)
