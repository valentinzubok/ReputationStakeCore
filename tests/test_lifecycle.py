"""Lifecycle, access control and validation."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from conftest import load_contract, reset  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
mod = load_contract(ROOT, "ReputationStake.py")
gl = sys.modules["genlayer"]

OWNER = "0x1111111111111111111111111111111111111111"
STAKER = "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
TARGET = "0x2222222222222222222222222222222222222222"
OTHER = "0x3333333333333333333333333333333333333333"

POLICY = "https://test-server.genlayer.com/static/genvm"
URL = "https://test-server.genlayer.com/static/genvm/hello.html"


def _funded(amount="500"):
    reset(gl)
    c = mod.ReputationStake(OWNER, OWNER)
    gl.message.sender_address = OWNER
    c.credit_reputation(STAKER, amount)
    gl.message.sender_address = STAKER
    return c


def test_stake_records_the_policy_it_was_created_with():
    c = _funded()
    c.stake("200", TARGET, "API access guarantee", POLICY)
    sid = json.loads(c.list_ids())[0]
    entry = json.loads(c.get_stake(sid))
    assert entry["evidence_policy"] == [POLICY]
    assert entry["policy_hash"]
    policy = json.loads(c.get_evidence_policy(sid))
    assert policy["evidence_policy"] == [POLICY]


def test_release_is_target_or_owner_only():
    c = _funded()
    c.stake("200", TARGET, "API access guarantee", POLICY)
    sid = json.loads(c.list_ids())[0]
    with pytest.raises(Exception, match="only target or owner"):
        c.release(sid)
    gl.message.sender_address = OTHER
    with pytest.raises(Exception, match="only target or owner"):
        c.release(sid)
    gl.message.sender_address = TARGET
    c.release(sid)
    assert json.loads(c.get_stake(sid))["status"] == "released"
    assert json.loads(c.get_balance(STAKER))["available"] == 500


def test_slash_moves_escrow_when_validators_agree():
    c = _funded("300")
    c.stake("150", TARGET, "publish the hello world page", POLICY)
    sid = json.loads(c.list_ids())[0]
    gl.message.sender_address = OWNER
    gl.page = "This page is empty. The hello world page was never published."
    gl.llm_reply = '{"breach": true}'
    c.slash(sid, "the promised page was never published", URL)
    entry = json.loads(c.get_stake(sid))
    assert entry["status"] == "slashed"
    assert entry["breach"] is True
    assert entry["evidence_hash"] and entry["evidence_source"] == POLICY
    assert json.loads(c.get_balance(TARGET))["available"] == 150


def test_slash_aborts_when_validators_find_no_breach():
    c = _funded("100")
    c.stake("50", TARGET, "work", POLICY)
    sid = json.loads(c.list_ids())[0]
    gl.message.sender_address = OWNER
    gl.llm_reply = '{"breach": false}'
    with pytest.raises(Exception, match="did not find breach"):
        c.slash(sid, "weak claim", URL)
    assert json.loads(c.get_stake(sid))["status"] == "active"
    assert json.loads(c.get_balance(TARGET))["available"] == 0


def test_slash_is_arbiter_only():
    c = _funded("50")
    c.stake("20", TARGET, "work", POLICY)
    sid = json.loads(c.list_ids())[0]
    gl.message.sender_address = TARGET
    with pytest.raises(Exception, match="only arbiter"):
        c.slash(sid, "no", URL)


def test_admin_and_views():
    reset(gl)
    c = mod.ReputationStake(OWNER, OWNER)
    gl.message.sender_address = OWNER
    assert c.get_owner() == OWNER and c.get_arbiter() == OWNER
    c.set_arbiter(OTHER)
    assert c.get_arbiter() == OTHER
    c.set_fee(OWNER, "25")
    assert json.loads(c.get_fee())["amount"] == "25"
    c.credit_reputation(STAKER, "100")
    gl.message.sender_address = STAKER
    c.stake("40", TARGET, "demo purpose", POLICY)
    stats = json.loads(c.get_stats())
    assert stats["active"] == 1 and stats["total_escrowed"] == 40
    active = json.loads(c.list_by_status("active"))
    gl.message.sender_address = OWNER
    c.release(active[0])
    assert json.loads(c.get_stats())["released"] == 1


def test_validation_rules():
    assert mod._parse_amount("100") == 100
    with pytest.raises(Exception, match="positive"):
        mod._parse_amount("0")
    assert mod._normalize_id("stake-1") == "stake-1"
    with pytest.raises(Exception, match="0x address"):
        mod._require_address("user", "not-an-address")

    c = _funded("100")
    with pytest.raises(Exception, match="yourself"):
        c.stake("10", STAKER, "x", POLICY)
    with pytest.raises(Exception, match="insufficient"):
        c.stake("999", TARGET, "x", POLICY)
