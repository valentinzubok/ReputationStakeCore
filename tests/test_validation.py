from pathlib import Path

import pytest

from conftest import load_contract

ROOT = Path(__file__).resolve().parents[1]
mod = load_contract(ROOT, "ReputationStake.py")


def test_parse_amount_ok():
    assert mod._parse_amount("100") == 100


def test_parse_amount_rejects_zero():
    with pytest.raises(Exception, match="positive"):
        mod._parse_amount("0")


def test_normalize_id_ok():
    assert mod._normalize_id("stake-1") == "stake-1"


def test_require_address_invalid():
    with pytest.raises(Exception, match="0x address"):
        mod._require_address("user", "not-an-address")


def test_judge_breach_parses():
    out = mod._judge_breach("deliver course", "late", "no course found")
    assert '"breach"' in out
